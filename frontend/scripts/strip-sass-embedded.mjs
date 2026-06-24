/**
 * Vite 会优先加载 sass-embedded，其在 macOS 13 上会触发 VM 初始化失败。
 * 安装后移除可选依赖 sass-embedded，保留 dart-sass（sass 包）即可。
 */
import { readdirSync, rmSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const pnpmDir = join(here, '..', 'node_modules', '.pnpm')

try {
  for (const name of readdirSync(pnpmDir)) {
    if (name.startsWith('sass-embedded')) {
      rmSync(join(pnpmDir, name), { recursive: true, force: true })
    }
  }
} catch {
  // node_modules 尚未就绪时忽略
}
