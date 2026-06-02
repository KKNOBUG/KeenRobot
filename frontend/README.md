# 前端 - 企业级 RAG 问答系统

基于 Vue 3 + Vite 构建的前端应用。

## 技术栈

- **Vue 3** - 渐进式 JavaScript 框架
- **Vite** - 下一代前端构建工具
- **Vue Router** - 官方路由管理器
- **自定义组件** - 轻量级 UI 组件

## 安装和运行

### 1. 安装依赖

```bash
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

默认访问地址：http://localhost:3001

### 3. 构建生产版本

```bash
npm run build
```

构建产物将输出到 `dist/` 目录。

### 4. 预览生产构建

```bash
npm run preview
```

## 配置

### API 地址配置

前端默认连接后端 API 地址：`http://localhost:8000`

如需修改，请编辑 `src/api/index.js` 文件：

```javascript
const API_BASE_URL = 'http://localhost:8000';
```

### 端口配置

如需修改前端开发服务器端口，请编辑 `vite.config.js`：

```javascript
server: {
  port: 3001  // 修改为你想要的端口
}
```

## 项目结构

```
frontend/
├── src/
│   ├── api/           # API 调用封装
│   ├── components/    # 可复用组件
│   ├── views/         # 页面组件
│   ├── router/        # 路由配置
│   ├── App.vue        # 根组件
│   ├── main.js        # 入口文件
│   └── style.css      # 全局样式
├── public/            # 静态资源
├── index.html         # HTML 模板
├── vite.config.js     # Vite 配置
└── package.json       # 依赖配置
```

## 功能模块

- **登录/注册** - 用户认证页面
- **对话** - RAG 智能问答界面
- **知识库** - 知识库管理界面

## 开发说明

- 使用 `<script setup>` 语法
- 组件化开发
- 响应式设计
- 支持热更新（HMR）

## 注意事项

1. 确保后端服务已启动
2. 检查 CORS 配置（后端已配置允许前端访问）
3. 首次使用请先注册账号
