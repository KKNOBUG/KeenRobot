<script setup>
defineOptions({ name: 'McpManage' })

import CommonPage from '@/components/page/CommonPage.vue'
</script>

<template>
  <CommonPage show-footer>
    <div class="page-placeholder">
      <p class="title">MCP管理</p>
      <p class="desc">内容开发中，敬请期待</p>
    </div>
  </CommonPage>
</template>

<style scoped>
.page-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  color: var(--n-text-color-3, #999);
}

.title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 8px;
}

.desc {
  font-size: 13px;
}
</style>
