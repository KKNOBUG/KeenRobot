import { defineStore } from 'pinia'
import { activeTag, tags, WITHOUT_TAG_PATHS, WORKBENCH_TAG_PATH } from './helpers.js'
import { router } from '@/router'
import { lStorage } from '@/utils'

function sortTagsWithWorkbenchFirst(tagList) {
  const workbench = tagList.filter((t) => t.path === WORKBENCH_TAG_PATH)
  const rest = tagList.filter((t) => t.path !== WORKBENCH_TAG_PATH)
  return [...workbench, ...rest]
}

export const useTagsStore = defineStore('tag', {
  state() {
    return {
      tags: tags ? sortTagsWithWorkbenchFirst(tags) : [],
      activeTag: activeTag || '',
    }
  },
  getters: {
    activeIndex() {
      return this.tags.findIndex((item) => item.path === this.activeTag)
    },
  },
  actions: {
    setActiveTag(path) {
      this.activeTag = path
      lStorage.set('activeTag', path)
    },
    setTags(newTags) {
      this.tags = sortTagsWithWorkbenchFirst(newTags)
      lStorage.set('tags', this.tags)
    },
    addTag(tag = {}) {
      this.setActiveTag(tag.path)
      if (WITHOUT_TAG_PATHS.includes(tag.path) || this.tags.some((item) => item.path === tag.path)) {
        return
      }
      this.setTags([...this.tags, tag])
    },
    removeTag(path) {
      if (path === WORKBENCH_TAG_PATH) return
      if (path === this.activeTag) {
        if (this.activeIndex > 0) {
          router.push(this.tags[this.activeIndex - 1].path)
        } else if (this.tags.length > 1) {
          router.push(this.tags[this.activeIndex + 1].path)
        }
      }
      this.setTags(this.tags.filter((item) => item.path !== path))
    },
    removeOther(curPath = this.activeTag) {
      const keep = this.tags.filter(
        (tag) => tag.path === curPath || tag.path === WORKBENCH_TAG_PATH
      )
      this.setTags(keep)
      if (curPath !== this.activeTag) {
        router.push(this.tags[this.tags.length - 1].path)
      }
    },
    removeLeft(curPath) {
      if (curPath === WORKBENCH_TAG_PATH) return
      const curIndex = this.tags.findIndex((item) => item.path === curPath)
      const filterTags = this.tags.filter(
        (item, index) => index >= curIndex || item.path === WORKBENCH_TAG_PATH
      )
      this.setTags(filterTags)
      if (!filterTags.find((item) => item.path === this.activeTag)) {
        router.push(filterTags[filterTags.length - 1].path)
      }
    },
    removeRight(curPath) {
      if (curPath === WORKBENCH_TAG_PATH) return
      const curIndex = this.tags.findIndex((item) => item.path === curPath)
      const filterTags = this.tags.filter(
        (item, index) => index <= curIndex || item.path === WORKBENCH_TAG_PATH
      )
      this.setTags(filterTags)
      if (!filterTags.find((item) => item.path === this.activeTag)) {
        router.push(filterTags[filterTags.length - 1].path)
      }
    },
    resetTags() {
      this.setTags([])
      this.setActiveTag('')
    },
  },
})
