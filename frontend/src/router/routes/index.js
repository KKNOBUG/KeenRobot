const Layout = () => import('@/layout/index.vue')

export const basicRoutes = [
  {
    path: '/',
    redirect: '/workbench',
    meta: { order: 0 },
  },
  {
    name: 'Workbench',
    path: '/workbench',
    component: Layout,
    children: [
      {
        path: '',
        component: () => import('@/views/workbench/index.vue'),
        name: 'WorkbenchDefault',
        meta: {
          title: '工作台',
          icon: 'icon-park-outline:workbench',
          affix: true,
          keepAlive: true,
          componentName: 'Workbench',
        },
      },
    ],
    meta: { order: 1 },
  },
  {
    name: 'AiManage',
    path: '/ai-manage',
    component: Layout,
    redirect: '/ai-manage/chat',
    meta: {
      title: 'AI管理',
      icon: 'mdi:robot-outline',
      order: 2,
    },
    children: [
      {
        name: 'Chat',
        path: 'chat',
        component: () => import('@/views/chat/index.vue'),
        meta: {
          title: '智能聊天',
          icon: 'mdi:chat-outline',
          keepAlive: true,
          componentName: 'Chat',
        },
      },
      {
        name: 'KnowledgeBase',
        path: 'knowledge-base',
        component: () => import('@/views/knowledge-base/index.vue'),
        meta: {
          title: '知识库管理',
          icon: 'mdi:book-open-outline',
          keepAlive: true,
          componentName: 'KnowledgeBase',
        },
      },
      {
        name: 'ModelManage',
        path: 'model',
        component: () => import('@/views/ai-manage/model/index.vue'),
        meta: {
          title: '模型管理',
          icon: 'mdi:brain',
          keepAlive: true,
          componentName: 'ModelManage',
        },
      },
      {
        name: 'McpManage',
        path: 'mcp',
        component: () => import('@/views/ai-manage/mcp/index.vue'),
        meta: {
          title: 'MCP管理',
          icon: 'mdi:connection',
          keepAlive: true,
          componentName: 'McpManage',
        },
      },
      {
        name: 'SkillsManage',
        path: 'skills',
        component: () => import('@/views/ai-manage/skills/index.vue'),
        meta: {
          title: 'Skills管理',
          icon: 'mdi:puzzle-outline',
          keepAlive: true,
          componentName: 'SkillsManage',
        },
      },
      {
        name: 'TaskCenter',
        path: 'task-center',
        component: () => import('@/views/ai-manage/task-center/index.vue'),
        meta: {
          title: '任务中心',
          icon: 'mdi:clock-outline',
          keepAlive: true,
          componentName: 'TaskCenter',
        },
      },
    ],
  },
  {
    name: 'Profile',
    path: '/profile',
    component: Layout,
    isHidden: true,
    children: [
      {
        path: '',
        component: () => import('@/views/profile/index.vue'),
        name: 'ProfileDefault',
        meta: {
          title: '个人中心',
          icon: 'mdi:account',
          affix: true,
        },
      },
    ],
    meta: { order: 99 },
  },
  {
    name: 'ErrorPage',
    path: '/error-page',
    component: Layout,
    redirect: '/error-page/404',
    meta: {
      title: '错误页面',
      icon: 'mdi:alert-circle-outline',
      order: 99,
    },
    children: [
      {
        name: 'ERROR-401',
        path: '401',
        component: () => import('@/views/error-page/401.vue'),
        meta: { title: '401', icon: 'material-symbols:authenticator' },
      },
      {
        name: 'ERROR-403',
        path: '403',
        component: () => import('@/views/error-page/403.vue'),
        meta: { title: '403', icon: 'solar:forbidden-circle-line-duotone' },
      },
      {
        name: 'ERROR-404',
        path: '404',
        component: () => import('@/views/error-page/404.vue'),
        meta: { title: '404', icon: 'tabler:error-404' },
      },
      {
        name: 'ERROR-500',
        path: '500',
        component: () => import('@/views/error-page/500.vue'),
        meta: { title: '500', icon: 'clarity:rack-server-outline-alerted' },
      },
    ],
  },
  {
    name: 'Error403',
    path: '/403',
    component: () => import('@/views/error-page/403.vue'),
    isHidden: true,
  },
  {
    name: 'Error404',
    path: '/404',
    component: () => import('@/views/error-page/404.vue'),
    isHidden: true,
  },
  {
    name: 'Login',
    path: '/login',
    component: () => import('@/views/login/index.vue'),
    isHidden: true,
    meta: { title: '登录页' },
  },
]

export const NOT_FOUND_ROUTE = {
  name: 'NotFound',
  path: '/:pathMatch(.*)*',
  redirect: '/404',
  isHidden: true,
}

export const EMPTY_ROUTE = {
  name: 'Empty',
  path: '/:pathMatch(.*)*',
  component: null,
}
