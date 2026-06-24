import { marked } from 'marked'
import katex from 'katex'

marked.use({
  gfm: true,
  breaks: true,
})

const MATH_PLACEHOLDER = '⟦MATH:'

function isLikelyLatex(content) {
  const text = (content || '').trim()
  if (!text) return false
  return /\\[a-zA-Z]+|[\^_{=+\-*/]|\\frac|\\div|\\text|\\sqrt|\\sum|\\int|\\approx/.test(text)
}

function pushMathBlock(blocks, latex, displayMode) {
  const id = blocks.length
  blocks.push({ latex: latex.trim(), displayMode })
  return `${MATH_PLACEHOLDER}${id}⟧`
}

function protectMath(text, blocks) {
  let source = text || ''

  // 块级：$$ ... $$
  source = source.replace(/\$\$([\s\S]+?)\$\$/g, (_, latex) => (
    pushMathBlock(blocks, latex, true)
  ))

  // 块级：\[ ... \]
  source = source.replace(/\\\[([\s\S]+?)\\\]/g, (_, latex) => (
    pushMathBlock(blocks, latex, true)
  ))

  // 块级：模型常用的 [ \n latex \n ] 或 [ latex ]
  source = source.replace(/^\[\s*\n([\s\S]*?\n)\s*\]/gm, (match, body) => (
    isLikelyLatex(body) ? pushMathBlock(blocks, body, true) : match
  ))
  source = source.replace(/^\[\s*([^\]\n]+)\s*\]$/gm, (match, body) => (
    isLikelyLatex(body) ? pushMathBlock(blocks, body, true) : match
  ))

  // 行内：\( ... \)
  source = source.replace(/\\\((.+?)\\\)/g, (_, latex) => (
    pushMathBlock(blocks, latex, false)
  ))

  // 行内：$ ... $（排除 $$）
  source = source.replace(/(?<!\$)\$(?!\$)([^\$\n]+?)\$(?!\$)/g, (_, latex) => (
    pushMathBlock(blocks, latex, false)
  ))

  return source
}

function renderKatex(latex, displayMode) {
  try {
    return katex.renderToString(latex, {
      displayMode,
      throwOnError: false,
      strict: 'ignore',
      trust: false,
    })
  } catch {
    return displayMode ? `<pre class="math-fallback">${latex}</pre>` : `<code>${latex}</code>`
  }
}

function restoreMath(html, blocks) {
  if (!blocks.length) return html
  let result = html.replace(/⟦MATH:(\d+)⟧/g, (_, id) => {
    const block = blocks[Number(id)]
    if (!block) return ''
    const rendered = renderKatex(block.latex, block.displayMode)
    return block.displayMode
      ? `<div class="math-display">${rendered}</div>`
      : rendered
  })
  // 避免块级公式被包进 <p>，并修正 breaks 导致的 <p>...<br><div>
  result = result.replace(/<p>([^<]*?)<br>\s*(<div class="math-display">)/g, '<p>$1</p>$2')
  result = result.replace(/<p>\s*(<div class="math-display">[\s\S]*?<\/div>)\s*<\/p>/g, '$1')
  return result
}

/**
 * 将 Markdown 文本渲染为 HTML（助手消息展示用）。
 * 支持 KaTeX：$$...$$、\\[...\\]、$...$、\\(...\\)，以及 [ \\frac{...} ] 块。
 * 流式阶段请使用纯文本，结束后再调用以避免中间态解析错误。
 */
export function renderMarkdown(text) {
  if (!text) return ''
  try {
    const blocks = []
    const protectedText = protectMath(text, blocks)
    const html = marked.parse(protectedText, { async: false })
    return restoreMath(html, blocks)
  } catch {
    return text
  }
}
