<script setup>
import ErrorPageContent from './ErrorPageContent.vue'
</script>

<template>
  <!-- SVG: unauthorized.svg -->
  <ErrorPageContent icon="unauthorized" code="401" message="未授权，请先登录" />
</template>
