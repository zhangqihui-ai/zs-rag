import { ref } from 'vue'

/** 子页面覆盖 Layout 顶栏标题与面包屑末级文案（离开页面时需清空）。 */
export const layoutPageTitleOverride = ref<string | null>(null)
export const layoutBreadcrumbTailOverride = ref<string | null>(null)
/** 对话页：点击面包屑「对话」时回到聊天列表（由 ChatView 注册）。 */
export const layoutChatHomeHandler = ref<(() => void) | null>(null)
/** 子页面请求 Layout 使用铺满型一屏布局（无页面级纵向滚动条）。 */
export const layoutFillPageOverride = ref<boolean | null>(null)

export function useLayoutPageContext() {
  function setPageContext(options: { title?: string | null; breadcrumbTail?: string | null }) {
    if ('title' in options) {
      layoutPageTitleOverride.value = options.title?.trim() || null
    }
    if ('breadcrumbTail' in options) {
      layoutBreadcrumbTailOverride.value = options.breadcrumbTail?.trim() || null
    }
  }

  function setChatHomeHandler(handler: (() => void) | null) {
    layoutChatHomeHandler.value = handler
  }

  function setFillPage(enabled: boolean | null) {
    layoutFillPageOverride.value = enabled
  }

  function clearPageContext() {
    layoutPageTitleOverride.value = null
    layoutBreadcrumbTailOverride.value = null
    layoutChatHomeHandler.value = null
    layoutFillPageOverride.value = null
  }

  return {
    setPageContext,
    setChatHomeHandler,
    setFillPage,
    clearPageContext,
    layoutPageTitleOverride,
    layoutBreadcrumbTailOverride,
  }
}
