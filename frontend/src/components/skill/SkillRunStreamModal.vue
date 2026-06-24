<script setup>
import { ref, watch } from 'vue'
import { NButton, NModal, NSpace, NSpin } from 'naive-ui'

import ChatProcessTrace from '@/components/chat/ChatProcessTrace.vue'
import { skillRunStream } from '@/api'

const props = defineProps({
  show: { type: Boolean, default: false },
  runId: { type: String, default: '' },
  title: { type: String, default: 'Skill 执行进度' },
})

const emit = defineEmits(['update:show', 'finished'])

const streaming = ref(false)
const processTrace = ref([])
const summary = ref('')
const streamController = ref(null)

watch(
  () => [props.show, props.runId],
  () => {
    if (!props.show || !props.runId) {
      resetState()
      return
    }
    resetState()
    startStream(props.runId)
  },
)

function resetState() {
  if (streamController.value) {
    streamController.value.abort()
    streamController.value = null
  }
  streaming.value = false
  processTrace.value = []
  summary.value = ''
}

function close() {
  emit('update:show', false)
}

function startStream(runId) {
  streaming.value = true
  streamController.value = skillRunStream(runId, {
    onProcess(data) {
      if (data?.process_trace) {
        processTrace.value = data.process_trace
      } else if (data?.step) {
        const trace = [...processTrace.value]
        const idx = trace.findIndex(
          (item) => item.type === 'skill' && item.name === data.step.name,
        )
        if (idx >= 0) trace[idx] = data.step
        else trace.push(data.step)
        processTrace.value = trace
      }
    },
    onToken(token) {
      summary.value += token
    },
    onDone(data) {
      summary.value = data.content || summary.value
      if (data.process_trace) processTrace.value = data.process_trace
      streaming.value = false
      emit('finished', { runId, summary: summary.value })
    },
    onError(err) {
      streaming.value = false
      window.$message?.error(err?.message || '执行失败')
      emit('finished', { runId, error: err?.message })
    },
  })
}
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    :title="title"
    style="width: 720px; max-width: 96vw"
    @update:show="emit('update:show', $event)"
  >
    <NSpin :show="streaming && !processTrace.length && !summary">
      <ChatProcessTrace :steps="processTrace" :streaming="streaming" />
      <div v-if="summary" class="skill-run-stream__text">{{ summary }}</div>
    </NSpin>
    <template #footer>
      <NSpace justify="end">
        <NButton @click="close">{{ streaming ? '后台继续' : '关闭' }}</NButton>
      </NSpace>
    </template>
  </NModal>
</template>

<style scoped lang="scss">
.skill-run-stream__text {
  margin-top: 12px;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}
</style>
