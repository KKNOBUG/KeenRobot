# SVG 资源说明

本目录 SVG 均来自 **KeenRunner_frontend/src/assets/svg/**。

## 背景图（非 SVG）

| 文件 | 用途 | 引用位置 |
|------|------|----------|
| `src/assets/images/login_bg.webp` | 登录页全屏背景 | `views/login/index.vue`（来自 KeenRunner） |

## 引用方式

使用 `<AppIcon name="文件名" />`（见 `src/components/icon/AppIcon.vue`），  
或在 script 中 `import url from '@/assets/svg/xxx.svg?url'`。

**请勿**在 template 中写 `src="../assets/svg/..."`，Vite 无法解析会导致图片破损。

## SVG 文件清单

| 文件名 | 用途 | 引用位置 |
|--------|------|----------|
| `logo_new.svg` | 品牌 Logo（侧边栏、登录页标题） | `layout/index.vue`、`views/login/index.vue` |
| `front-page.svg` | 登录页左侧插图 | `views/login/index.vue` |
| `favicon_logo.svg` | 浏览器图标（已复制到 `public/favicon.svg`） | `index.html` |
| `unauthorized.svg` | 401 未授权错误页 | `views/error-page/401.vue` |
| `forbidden.svg` | 403 禁止访问错误页 | `views/error-page/403.vue` |
| `not-found.svg` | 404 页面不存在 | `views/error-page/404.vue` |
| `server-error.svg` | 500 服务器错误 | `views/error-page/500.vue` |

## 新增 SVG

1. 将 `.svg` 文件放入本目录
2. 在本 README 表格中补充说明
3. 通过 `<AppIcon name="文件名" />` 引用（name 不含 `.svg` 后缀）
