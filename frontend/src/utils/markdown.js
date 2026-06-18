import { marked } from 'marked'

marked.use({
  gfm: true,
  breaks: true,
})

/**
 * 将 Markdown 文本渲染为 HTML（助手消息展示用）。
 * 流式阶段请使用纯文本，结束后再调用以避免中间态解析错误。
 */
export function renderMarkdown(text) {
  if (!text) return ''
  try {
    return marked.parse(text, { async: false })
  } catch {
    return text
  }
}
