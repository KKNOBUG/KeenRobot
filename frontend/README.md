# KeenRobot 前端

企业级 RAG 智能问答系统的前端应用，基于 Vue 3 + Vite 构建。提供登录认证、工作台、SSE 流式智能聊天、知识库管理、模型配置、Skills/MCP 管理、任务中心调度界面，通过 `/api` 前缀与后端 FastAPI 联调。

> **路径说明**：浏览器与 Axios 请求使用 **`/api` 前缀**（由 `VITE_BASE_API` 配置）。开发环境下 Vite 代理会**去掉 `/api`** 再转发到后端。例如：
>
> `GET /api/conversations/` → `GET http://<BACKEND_URL>/conversations/`
>
> 后端接口契约详见 [../backend/README.md](../backend/README.md)。

---

## 目录

- [功能简介](#功能简介)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [环境变量与构建配置](#环境变量与构建配置)
- [请求封装与认证](#请求封装与认证)
- [路由与页面清单](#路由与页面清单)
- [API 调用清单（前端视角）](#api-调用清单前端视角)
- [核心页面处理流程与调用链](#核心页面处理流程与调用链)
- [布局与状态管理](#布局与状态管理)
- [聊天与 RAG 相关组件说明](#聊天与-rag-相关组件说明)
- [与后端的协作约定](#与后端的协作约定)
- [常见问题](#常见问题)
- [相关文档](#相关文档)

---

## 功能简介

| 页面/模块 | 路由 | 能力 |
|-----------|------|------|
| **登录** | `/login` | 用户名密码登录，获取 JWT，记住表单 |
| **工作台** | `/workbench` | 欢迎页、用户信息展示（无 API 调用） |
| **智能聊天** | `/ai-manage/chat` | 多轮 SSE 对话、知识库/Skills/MCP 选择、模型切换、深度思考、历史会话 |
| **知识库管理** | `/ai-manage/knowledge-base` | 知识库 CRUD、PDF 上传、文档列表、分块查看、失败重试 |
| **模型管理** | `/ai-manage/model` | 当前用户 ModelConfig CRUD、设为默认、连接与 RAG 参数表单 |
| **MCP 管理** | `/ai-manage/mcp` | MCP 服务注册 CRUD |
| **Skills 管理** | `/ai-manage/skills` | Agent 技能 CRUD |
| **任务中心** | `/ai-manage/task-center` | 任务定义、启停调度、立即执行、执行记录 Tab |
| **个人中心** | `/profile` | 展示 userStore 缓存的用户信息 |
| **错误页** | `/error-page/*`、`/403`、`/404` | 401/403/404/500 静态页 |

侧边栏菜单来自 `basicRoutes` 中带 `meta.title` 且非 `isHidden` 的路由（`permission` store 的 `menus` getter）。

---

## 技术栈

| 类别 | 技术 | 在前端的用途 |
|------|------|--------------|
| 框架 | Vue 3.5 | 组合式 API（`<script setup>`） |
| 构建 | Vite 5.4 | 开发服务器、HMR、生产打包 |
| 路由 | Vue Router 4.4 | SPA 路由、守卫、动态 404 |
| 状态 | Pinia 2.2 | 用户、权限菜单、多页签、主题/语言 |
| UI | Naive UI 2.44 | 表格、表单、布局、消息提示 |
| 样式 | UnoCSS 0.55 + Sass | 原子类 + 全局 SCSS |
| HTTP | Axios 1.7 | 常规 REST 请求 |
| 流式/SSE | 原生 fetch + ReadableStream | 聊天流、文件上传 |
| Markdown | marked 18 | 助手消息渲染 |
| 工具 | @vueuse/core、dayjs、lodash-es | 暗色模式、日期、工具函数 |
| 国际化 | vue-i18n 9.14 | 中/英切换（`i18n/`） |
| 图标 | @iconify/vue、vite-plugin-svg-icons | 图标与 SVG 雪碧图 |

完整依赖见 `package.json`。项目含 `pnpm-lock.yaml`，**推荐** `pnpm install`，兼容 `npm install`。

---

## 项目结构

```
frontend/
├── build/
│   ├── constant.js              # BACKEND_URL、PROXY_CONFIG（开发代理）
│   ├── config/                  # Vite define 等
│   ├── plugin/                  # 自动导入、SVG、HTML 插件
│   └── utils.js                 # 路径工具、env 转换
├── i18n/                        # vue-i18n 语言包（cn/en）
├── public/                      # 静态资源、favicon、loading
├── settings/                    # Naive UI 主题覆盖（theme.json）
├── src/
│   ├── api/
│   │   └── index.js             # API 封装；chatStream、uploadDocument 独立导出
│   ├── components/
│   │   ├── chat/                # ChatModelSelector、ChatFeaturePicker 等
│   │   ├── common/              # AppProvider、ScrollX、AppFooter
│   │   ├── icon/                # TheIcon、SvgIcon、AppIcon
│   │   ├── page/                # AppPage、CommonPage
│   │   ├── query-bar/           # QueryBar、QueryBarItem
│   │   ├── table/               # CrudTable、CrudModal
│   │   └── MessageBubble.vue    # 聊天气泡（Markdown）
│   ├── composables/
│   │   └── useCRUD.js           # 通用增删改查弹窗逻辑
│   ├── layout/                  # 侧栏、顶栏、Tags、AppMain
│   ├── router/
│   │   ├── routes/index.js      # 静态路由表
│   │   └── guard/               # loading、auth、title 守卫
│   ├── store/modules/           # user、permission、tags、app
│   ├── styles/                  # reset.css、global.scss
│   ├── utils/
│   │   ├── http/                # Axios 实例、拦截器、鉴权辅助
│   │   ├── auth/                # token 读写
│   │   └── storage/             # lStorage 封装
│   ├── views/
│   │   ├── login/               # 登录页
│   │   ├── workbench/           # 工作台
│   │   ├── chat/                # 智能聊天
│   │   ├── knowledge-base/      # 知识库管理
│   │   ├── ai-manage/           # model、mcp、skills、task-center
│   │   ├── profile/             # 个人中心
│   │   └── error-page/          # 错误页
│   ├── App.vue
│   └── main.js                  # 入口：store → router → i18n
├── .env.development             # 开发环境变量
├── .env.production              # 生产环境变量
├── vite.config.js
├── package.json
└── pnpm-lock.yaml
```

---

## 环境要求

| 项 | 要求 |
|----|------|
| Node.js | **≥ 18**（Vite 5 推荐） |
| 包管理 | pnpm（推荐）或 npm |
| 后端 | FastAPI 已启动且地址与 `build/constant.js` 中 `BACKEND_URL` 一致（默认端口 **8519**） |
| 浏览器 | 现代浏览器；智能聊天需支持 **fetch + ReadableStream（SSE）** |

---

## 快速开始

### 1. 安装依赖

```bash
cd frontend
pnpm install
# 或
npm install
```

**主要依赖作用：**

| 依赖 | 作用 |
|------|------|
| `vue` / `vue-router` / `pinia` | 视图、路由、全局状态 |
| `vite` / `@vitejs/plugin-vue` | 开发与构建 |
| `naive-ui` | UI 组件库 |
| `axios` | REST API（baseURL = `VITE_BASE_API`） |
| `unocss` + 相关 unplugin | 原子 CSS、组件/图标自动导入 |
| `marked` | 聊天 Markdown 渲染 |
| `vue-i18n` | 国际化 |
| `@vueuse/core` | 暗色模式等组合式工具 |

### 2. 配置联调地址

| 文件/位置 | 变量/项 | 说明 |
|-----------|---------|------|
| `.env.development` | `VITE_PUBLIC_PATH`、`VITE_USE_PROXY`、`VITE_BASE_API` | 开发代理开关（默认 `VITE_USE_PROXY=true`）与 API 前缀（默认 `/api`） |
| `.env.production` | `VITE_BASE_API` 等 | 生产构建时的 API 前缀 |
| `build/constant.js` | **`BACKEND_URL`** | 开发代理目标，**部署前改为本机后端**，如 `http://127.0.0.1:8519` |
| `vite.config.js` | `VITE_PORT` | 开发服务器端口；未在 `.env` 配置时使用 Vite 默认 **5173** |

代理规则（`PROXY_CONFIG`）：

```
浏览器  http://localhost:<VITE_PORT>/api/base/auth/access_token
   ↓ rewrite 去掉 /api
后端    http://<BACKEND_URL>/base/auth/access_token
```

### 3. 启动开发服务器

```bash
pnpm dev
# 或
npm run dev
```

确保后端已运行（见 [backend/README.md](../backend/README.md) 快速开始）。

### 4. 构建与预览

```bash
pnpm build      # 产物输出 dist/
pnpm preview    # 本地预览生产构建
```

### 5. 启动后使用教程

1. 浏览器访问 `http://localhost:<端口>/login`
2. 使用后端 seed 账号登录（默认 **`admin` / `123456`**，见 backend README）
3. 登录成功后跳转 `/workbench`，从侧栏进入：
   - **智能聊天**：选择知识库（可选）、模型（有 ModelConfig 时）、发送问题
   - **知识库管理**：新建 KB → 上传 **PDF** → 查看分块
   - **模型管理**：创建 ModelConfig，可设默认
4. **任务中心**需后端 Celery Worker + Beat 运行，见 [backend/README.md](../backend/README.md#5-启动-celery任务调度必需)

---

## 环境变量与构建配置

### 开发环境（`.env.development`）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VITE_PUBLIC_PATH` | `/` | 静态资源公共路径 |
| `VITE_USE_PROXY` | `true` | 开发时是否启用 Vite 代理 |
| `VITE_BASE_API` | `/api` | Axios / fetch 的 API 前缀 |

### 生产环境（`.env.production`）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VITE_PUBLIC_PATH` | `/` | 部署子路径（如 `/app/` 需带首尾斜杠） |
| `VITE_BASE_API` | `/api` | 生产环境 API 前缀 |

### 生产部署要点

1. `pnpm build` 生成 `dist/`
2. 使用 Nginx 等托管静态文件，`try_files` 回退到 `index.html`（SPA）
3. **必须**配置 `/api` 反向代理到后端，并去掉前缀（与开发代理一致）：

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8519/;   # 注意末尾 /，等价于 rewrite 去掉 /api
    proxy_set_header Host $host;
    proxy_set_header token $http_token;    # 若需透传自定义 header
}
```

4. 生产构建**不会**使用 Vite dev proxy；未配置 Nginx 反代时 API 请求会 404。

---

## 请求封装与认证

### Axios 常规请求

```
src/utils/http/index.js
  → createAxios({ baseURL: import.meta.env.VITE_BASE_API || '/api' })
  → interceptors.js: reqResolve / resResolve
```

| 环节 | 行为 |
|------|------|
| 请求 | 默认在 Header 添加 **`token: <jwt>`**；`noNeedToken: true` 时不带 Token（登录/注册） |
| 成功 | `code === '000000' && status === 'success'` → `Promise.resolve(data)` |
| 失败 | 弹出 Naive UI 消息；`400401` 等鉴权失败 → `handleUnauthorized()` |

### Token 存储

- 键名：`access_token`（`utils/auth/token.js`，经 `lStorage` 持久化）
- 登录：`login/index.vue` → `setToken(res.data.access_token)`

### 响应错误码

业务 `code` 定义于后端 `enums/base_error_enum.py`，前端常见：

| code | 含义 | 前端处理 |
|------|------|----------|
| `000000` | 成功 | 正常返回 `data` |
| `400401` | 鉴权失败 | `handleUnauthorized` → 登出并跳转 `/login` |
| `400403` | 无权限 | 错误提示 |
| `400404` | 资源不存在 | 错误提示 |
| `999999` | 通用失败 | 错误提示 |

### 特殊请求（不走 Axios）

**文件上传** — `uploadDocument(kbId, file)`：

- 原生 `fetch`，`FormData` 字段 `file`
- Header 手动设置 `token`
- 成功判断：`body.code === '000000'`

**SSE 流式聊天** — `chatStream(...)`：

- `POST ${VITE_BASE_API}/chat/stream`，JSON body
- 解析 `event:` / `data:` 行；事件类型：`meta`、`token`、`reasoning`、`done`、`error`
- 返回 `{ abort }`，内部使用 `AbortController`

**`payload()`**（`api/index.js`）：`res?.data ?? res`，用于部分接口直接取业务数据。

---

## 路由与页面清单

守卫：`setupRouterGuard` 顺序为 **pageLoading → auth → pageTitle**。

| 路径 | 路由 name | 组件 | meta | 需登录 | 主要 API |
|------|-----------|------|------|--------|----------|
| `/` | — | redirect → `/workbench` | — | 是 | — |
| `/login` | Login | `views/login/index.vue` | 隐藏 | 否 | `login` |
| `/workbench` | Workbench | `views/workbench/index.vue` | 工作台 | 是 | —（读 userStore） |
| `/ai-manage/chat` | Chat | `views/chat/index.vue` | 智能聊天, keepAlive | 是 | 对话、聊天 SSE、KB、Model、Skills、MCP |
| `/ai-manage/knowledge-base` | KnowledgeBase | `views/knowledge-base/index.vue` | 知识库管理 | 是 | knowledge-bases CRUD、upload、chunks |
| `/ai-manage/model` | ModelManage | `views/ai-manage/model/index.vue` | 模型管理 | 是 | model-configs CRUD、default |
| `/ai-manage/mcp` | McpManage | `views/ai-manage/mcp/index.vue` | MCP管理 | 是 | mcp-servers CRUD |
| `/ai-manage/skills` | SkillsManage | `views/ai-manage/skills/index.vue` | Skills管理 | 是 | skills CRUD |
| `/ai-manage/task-center` | TaskCenter | `views/ai-manage/task-center/index.vue` | 任务中心 | 是 | task-center 全套 |
| `/profile` | Profile | `views/profile/index.vue` | 个人中心, 隐藏 | 是 | —（userStore） |
| `/error-page/401` 等 | ERROR-* | `views/error-page/*.vue` | 错误页 | 是 | — |
| `/:pathMatch(.*)*` | NotFound | redirect `/404` | 隐藏 | — | 登录后动态注册 |

**auth-guard** 白名单：`/login`、`/404`。无 Token 访问其他路径 → `/login?redirect=...`；已登录访问 `/login` → `/`。

---

## API 调用清单（前端视角）

前缀均为 **`/api`**（即 `VITE_BASE_API`）；「后端路径」为代理 rewrite 后实际请求路径。

### 认证与用户

| 封装函数 | 方法 | 前端路径 | 后端路径 | 调用位置 |
|----------|------|----------|----------|----------|
| `login` | POST | `/api/base/auth/access_token` | `/base/auth/access_token` | `login/index.vue` |
| `register` | POST | `/api/user/create` | `/user/create` | （已封装，登录页未用） |
| `getUserInfo` | POST | `/api/base/auth/userinfo` | `/base/auth/userinfo` | `userStore.getUserInfo` |
| `logout` | POST | `/api/user/logout` | `/user/logout` | `userStore.logout` |

### 对话与聊天

| 封装函数 | 方法 | 前端路径 | 后端路径 | 调用位置 |
|----------|------|----------|----------|----------|
| `fetchConversations` | GET | `/api/conversations/` | `/conversations/` | `chat/index.vue` |
| `fetchConversation` | GET | `/api/conversations/{id}` | `/conversations/{id}` | `chat/index.vue` |
| `deleteConversation` | DELETE | `/api/conversations/{id}` | `/conversations/{id}` | `chat/index.vue` |
| `chatStream` | POST (SSE) | `/api/chat/stream` | `/chat/stream` | `chat/index.vue` |

**`chatStream` 请求体要点：** `question`、`conversation_id?`、`knowledge_base_ids`、`model_config_id?`（无配置传 `null`）、`enable_thinking`、`skill_ids`、`mcp_ids`。

### 知识库

| 封装函数 | 方法 | 前端路径 | 调用位置 |
|----------|------|----------|----------|
| `fetchKnowledgeBases` | GET | `/api/knowledge-bases/` | chat、knowledge-base |
| `createKnowledgeBase` | POST | `/api/knowledge-bases/` | knowledge-base |
| `updateKnowledgeBase` | PUT | `/api/knowledge-bases/{id}` | knowledge-base |
| `deleteKnowledgeBase` | DELETE | `/api/knowledge-bases/{id}` | knowledge-base |
| `fetchDocuments` | GET | `/api/knowledge-bases/{id}/documents` | knowledge-base |
| `uploadDocument` | POST (fetch) | `/api/knowledge-bases/{id}/documents` | knowledge-base |
| `retryDocument` | POST | `/api/.../documents/{docId}/retry` | knowledge-base |
| `deleteDocument` | DELETE | `/api/.../documents/{docId}` | knowledge-base |
| `fetchChunks` | GET | `/api/.../chunks?document_id=` | knowledge-base |

### 模型配置

| 封装函数 | 方法 | 前端路径 | 调用位置 |
|----------|------|----------|----------|
| `fetchModelConfigs` | GET | `/api/model-configs/` | chat、model |
| `createModelConfig` | POST | `/api/model-configs/` | model |
| `updateModelConfig` | PUT | `/api/model-configs/{id}` | model |
| `deleteModelConfig` | DELETE | `/api/model-configs/{id}` | model |
| `setDefaultModelConfig` | POST | `/api/model-configs/{id}/default` | model |

### Skills / MCP

| 封装函数 | 方法 | 前端路径 | 调用位置 |
|----------|------|----------|----------|
| `fetchSkills` | GET | `/api/skills/?search=&manage=` | chat、skills |
| `createSkill` / `updateSkill` / `deleteSkill` | * | `/api/skills/` | skills |
| `fetchMcpServers` | GET | `/api/mcp-servers/?search=&manage=` | chat、mcp |
| `createMcpServer` / … | * | `/api/mcp-servers/` | mcp |

### 任务中心

| 封装函数 | 方法 | 前端路径 | 说明 |
|----------|------|----------|------|
| `fetchTaskCenterPresets` | GET | `/api/task-center/presets` | 模板与调度选项 |
| `searchTasks` | POST | `/api/task-center/search` | 任务列表 |
| `createTask` / `updateTask` | POST | `/api/task-center/create` 等 | JSON Body |
| `deleteTask` | DELETE | `/api/task-center/delete` | Query: `task_id` |
| `runTask` / `startTask` / `stopTask` | POST | `/api/task-center/run` 等 | **FormData：`task_id`** |
| `searchTaskRecords` | POST | `/api/task-center/record/search` | 执行记录 Tab |

---

## 核心页面处理流程与调用链

### 1. 登录

```
login/index.vue :: handleLogin()
  → api.login({ username, password })     → POST /api/base/auth/access_token
  → setToken(data.access_token)           → lStorage['access_token']
  → userStore.getUserInfo()               → POST /api/base/auth/userinfo
  → addDynamicRoutes()                    → 注册 NOT_FOUND 路由
  → router.push(redirect || '/')
```

### 2. 智能聊天 SSE

```
chat/index.vue :: onMounted
  → loadConversations / loadKnowledgeBases / loadModelConfigs / loadSkills / loadMcps
  → 可选：route.query.conversation → fetchConversation

chat/index.vue :: sendMessage()
  → 校验知识库（空 KB 时 confirm）
  → chatStream(question, convId, selectedKBs, modelConfigId, enableThinking, skills, mcps, callbacks)
      → POST /api/chat/stream
      → onMeta: 更新 conversation_id、URL ?conversation=
      → onReasoning / onToken: 更新 messages、process_trace
      → onDone: usage、刷新会话列表
  → streamController.abort() 可中断
```

**条件 UI：**

- `showModelSelector`：`modelConfigs.length > 0` 才渲染 `ChatModelSelector`
- `showDeepThinking`：所选配置 `model_thinking === true` 才显示 `ChatDeepThinkingToggle`
- 发送时 `enable_thinking` 仅当 `showDeepThinking && enableDeepThinking`

### 3. 知识库管理

```
knowledge-base/index.vue
  → fetchKnowledgeBases / createKnowledgeBase / updateKnowledgeBase / deleteKnowledgeBase
  → selectKB → fetchDocuments
  → uploadDocument(kbId, file)   [fetch + FormData，非 Axios]
  → viewChunks → fetchChunks(kbId, docId)   Query: document_id
  → retryDocument / deleteDocument
```

### 4. 模型管理

```
ai-manage/model/index.vue
  → useCRUD({ doCreate, doUpdate, doDelete })
  → CrudTable + fetchModelList → api.fetchModelConfigs（前端本地 filter）
  → handleSetDefault → api.setDefaultModelConfig
  → buildPayload：llm_api_key 含 *** 时不提交（更新场景）
```

### 5. 任务中心

```
ai-manage/task-center/index.vue
  → onMounted: fetchTaskCenterPresets
  → Tab「任务」: searchTasks、useCRUD 创建/更新
  → handleRun / handleStart / handleStop: FormData(task_id)
  → Tab「执行记录」: searchTaskRecords
```

### 6. 路由守卫

```
createAuthGuard
  → 无 token + 非白名单 → /login?redirect=
  → 有 token + /login → /
```

---

## 布局与状态管理

### Layout（`layout/index.vue`）

- **Sidebar**：菜单来自 `permissionStore.menus`
- **Header**：折叠、面包屑、全屏、主题、语言、用户头像/登出
- **Tags**：多页签（`tags` store），配合 `keepAlive` 缓存页面
- **AppMain**：`<router-view>` 渲染区

### Pinia Stores

| Store | 文件 | 职责 |
|-------|------|------|
| `user` | `store/modules/user/index.js` | `userInfo`、`getUserInfo`、`logout`（清 token/tags/permission/router） |
| `permission` | `store/modules/permission/index.js` | `menus`（过滤 hidden）、`routes` |
| `tags` | `store/modules/tags/index.js` | 已打开页签、affix、缓存 key |
| `app` | `store/modules/app/index.js` | 侧栏折叠、暗色模式、locale、页面 reload |

### 路由守卫链（`router/guard/index.js`）

1. `page-loading-guard` — 顶栏 loading
2. `auth-guard` — Token 校验
3. `page-title-guard` — 文档标题

### 通用 CRUD 模式

```
useCRUD({ name, initForm, doCreate, doDelete, doUpdate, refresh })
  + CrudTable（QueryBar 搜索、分页）
  + CrudModal（新增/编辑表单）
```

用于：模型管理、MCP、Skills、任务中心（任务 Tab）。

---

## 聊天与 RAG 相关组件说明

| 组件 | 文件 | 说明 |
|------|------|------|
| `ChatModelSelector` | `components/chat/ChatModelSelector.vue` | 下拉选择 ModelConfig；主显 `llm_model_name`（label），副显 `config_name`（sublabel）；无配置时不渲染 |
| `ChatDeepThinkingToggle` | `components/chat/ChatDeepThinkingToggle.vue` | 深度思考开关；仅 `model_thinking=true` 时由父组件展示 |
| `ChatFeaturePicker` | `components/chat/ChatFeaturePicker.vue` | 知识库 / Skills / MCP 多选 Popover |
| `ChatTurnNodes` | `components/chat/ChatTurnNodes.vue` | 对话轮次节点导航 |
| `ChatProcessTrace` | `components/chat/ChatProcessTrace.vue` | 推理过程追踪展示 |
| `MessageBubble` | `components/MessageBubble.vue` | 用户/助手气泡；助手内容经 **marked** 渲染 Markdown |
| `MiddleEllipsisText` | `components/chat/MiddleEllipsisText.vue` | 长标题中间省略 |

---

## 与后端的协作约定

| 约定 | 说明 |
|------|------|
| **路径** | 前端 `/api/*` → 代理 rewrite → 后端 `/*` |
| **认证** | Header 字段名 `token`，非 Bearer |
| **响应体** | `{ code, status, message, data, total }`；错误码见 backend `base_error_enum.py` |
| **CORS** | 开发走 Vite 代理，同源无跨域；生产依赖 Nginx 反代或后端 CORS |
| **上传/SSE** | 须手动 `fetch` 并设置 `token`；不走 Axios 拦截器链的成功封装 |
| **ModelConfig** | 无配置时聊天仍可用（后端 `.env` 兜底）；前端不传 `model_config_id` |
| **知识库** | 当前后端仅解析 **PDF**；Embedding 未配时检索降级（见 backend README） |
| **任务中心** | 定时执行依赖后端 Celery，见 backend README |

详细接口参数与边界：[../backend/README.md](../backend/README.md)

---

## 常见问题

### 接口 404 或 Network Error

1. 后端是否已启动
2. `build/constant.js` 中 `BACKEND_URL` 是否指向正确地址（端口 **8519**）
3. 开发环境 `VITE_USE_PROXY` 是否为 `true`
4. 生产环境是否配置了 Nginx `/api` 反代（不能依赖 Vite proxy）

### 登录后立即跳回登录页

- Token 未写入：检查登录响应 `data.access_token`
- 后续请求返回 `400401`：Token 过期或被吊销；检查 Header 是否为 `token`
- `getUserInfo` 失败会触发拦截器登出

### 聊天页没有模型下拉

属预期：当前用户无 ModelConfig（`fetchModelConfigs` 返回空）。聊天仍可用，请求中 `model_config_id: null`。

### 知识库上传失败

- 仅 **PDF** 可解析；`.docx`/`.txt` 会报错
- 后端需配置 `EMBEDDING_API_KEY`（见 backend README）
- 上传走 `fetch`，需在 Network 面板确认 `token` Header

### SSE 无输出或中断

- Network 查看 `POST /api/chat/stream` 是否为 `text/event-stream`
- 确认 `event:` 行解析正常（`meta` / `token` / `done`）
- 检查后端 LLM Key 与知识库配置

### 构建后 API 全部失败

生产包不包含 Vite 代理。必须在 Web 服务器配置 `/api` → 后端的反向代理。

### 开发端口冲突

在 `.env.development` 增加 `VITE_PORT=3100`（或任意可用端口），重启 `pnpm dev`。

### 任务中心「立即执行」无记录

后端 Celery Worker 须运行；见 [backend README — Celery 启动](../backend/README.md#5-启动-celery任务调度必需)。

---

*文档最后更新：2026-06-16*
