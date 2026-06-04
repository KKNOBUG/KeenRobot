import { lStorage } from '@/utils'

export const activeTag = lStorage.get('activeTag')
export const tags = lStorage.get('tags')
export const WITHOUT_TAG_PATHS = ['/404', '/login']
export const WORKBENCH_TAG_PATH = '/workbench'

function sortTagsWithWorkbenchFirst(tagList) {
  const workbench = tagList.filter((t) => t.path === WORKBENCH_TAG_PATH)
  const rest = tagList.filter((t) => t.path !== WORKBENCH_TAG_PATH)
  return [...workbench, ...rest]
}

export { sortTagsWithWorkbenchFirst }
