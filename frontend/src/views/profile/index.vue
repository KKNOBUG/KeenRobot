<template>
  <CommonPage :show-header="false">
    <n-card rounded-10>
      <div flex items-center>
        <img :src="userStore.avatar" h-80 w-80 rounded-full alt="avatar" />
        <div ml-20>
          <p text-20 font-semibold>{{ userStore.username }}</p>
          <p mt-8 op-60>{{ userStore.email }}</p>
        </div>
      </div>
    </n-card>
  </CommonPage>
</template>

<script setup>
import CommonPage from '@/components/page/CommonPage.vue'
import { useUserStore } from '@/store'

const userStore = useUserStore()
</script>
