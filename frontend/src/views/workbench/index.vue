<template>
  <AppPage :show-footer="false">
    <div flex-1>
      <n-card rounded-10>
        <div flex items-center justify-between>
          <div flex items-center>
            <img rounded-full width="80" :src="userStore.avatar" alt="avatar" />
            <div ml-10>
              <p text-20 font-semibold>
                {{
                  $t('views.workbench.text_hello', {
                    timer: currentTimePeriod(true),
                    alias: userStore.alias,
                    username: userStore.username,
                  })
                }}
              </p>
              <p mt-5 text-14 op-60>{{ $t('views.workbench.text_welcome', { welcome: welcomeMessage }) }}</p>
              <p mt-5 text-14 op-60>{{ $t('views.workbench.text_last_login', { lastLogin: userStore.lastLogin }) }}</p>
            </div>
          </div>
          <div class="statistic-container">
            <n-space :size="20" :wrap="false">
              <n-card v-for="item in statisticData" :key="item.id" class="statistic-card">
                <n-statistic v-bind="item" />
              </n-card>
            </n-space>
          </div>
        </div>
      </n-card>

      <n-card
        :title="$t('views.workbench.label_project')"
        size="small"
        :segmented="true"
        mt-15
        rounded-10
      >
        <template #header-extra>
          <n-button text type="primary">{{ $t('views.workbench.label_more') }}</n-button>
        </template>
        <div flex flex-wrap justify-between>
          <n-card
            v-for="i in 6"
            :key="i"
            class="mb-10 mt-10 w-300 cursor-pointer"
            hover:card-shadow
            title="KeenRobot"
            size="small"
          >
            <p op-60>{{ dummyText }}</p>
          </n-card>
        </div>
      </n-card>
    </div>
  </AppPage>
</template>

<script setup>
defineOptions({ name: 'Workbench' })

import { useUserStore } from '@/store'
import { useI18n } from 'vue-i18n'
import { currentTimePeriod } from '@/utils'

const dummyText = '基于 Vue3、FastAPI、Naive UI 的智能问答管理平台'
const { t } = useI18n({ useScope: 'global' })
const userStore = useUserStore()

const randomNumber = Math.floor(Math.random() * 20) + 1
const welcomeMessage = computed(() => t(`welcome.${randomNumber}`))

const statisticData = computed(() => [
  { id: 0, label: t('views.workbench.label_number_of_items'), value: '1' },
  { id: 1, label: t('views.workbench.label_number_of_kbs'), value: '3' },
  { id: 2, label: t('views.workbench.label_number_of_models'), value: '2' },
  { id: 3, label: t('views.workbench.label_number_of_agents'), value: '0' },
])
</script>

<style scoped>
.statistic-container {
  max-width: 55%;
  overflow-x: auto;
}

.statistic-card {
  width: 150px;
  border: 1px solid #e5e5e5;
  border-radius: 12px;
  background-color: var(--n-color-embedded);
  box-shadow: 5px 5px 5px rgba(0, 0, 0, 0.01);
  padding: 5px;
  transition: border-color 0.3s;
}

.statistic-card:hover {
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
  border-color: #f4511e;
}
</style>
