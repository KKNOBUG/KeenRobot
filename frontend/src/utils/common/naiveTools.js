import { isNullOrUndef } from '@/utils'

export function setupMessage(NMessage) {
  let loadingMessage = null

  class Message {
    removeMessage(message = loadingMessage, duration = 2000) {
      setTimeout(() => {
        if (message) {
          message.destroy()
          message = null
        }
      }, duration)
    }

    showMessage(type, content, option = {}) {
      if (loadingMessage && loadingMessage.type === 'loading') {
        loadingMessage.type = type
        loadingMessage.content = content
        if (type !== 'loading') {
          this.removeMessage(loadingMessage, option.duration)
        }
      } else {
        const message = NMessage[type](content, option)
        if (type === 'loading') {
          loadingMessage = message
        }
      }
    }

    loading(content, option = {}) {
      this.showMessage('loading', content, { duration: 0, ...option })
    }

    success(content, option = {}) {
      this.showMessage('success', content, option)
    }

    error(content, option = {}) {
      this.showMessage('error', content, option)
    }

    info(content, option = {}) {
      this.showMessage('info', content, option)
    }

    warning(content, option = {}) {
      this.showMessage('warning', content, option)
    }
  }

  return new Message()
}

export function setupDialog(NDialog) {
  NDialog.confirm = function (option = {}) {
    const showIcon = !isNullOrUndef(option.title)
    return NDialog[option.type || 'warning']({
      showIcon,
      positiveText: '确定',
      negativeText: '取消',
      onPositiveClick: option.confirm,
      onNegativeClick: option.cancel,
      onMaskClick: option.cancel,
      ...option,
    })
  }

  return NDialog
}
