import { onMounted, onUnmounted } from 'vue'

/**
 * Calls `fn` now and then every `intervalMs` while the component is mounted.
 * Pauses while the browser tab is hidden (Page Visibility API) and refreshes
 * immediately when the tab becomes visible again.
 */
export function usePolling(fn: () => unknown, intervalMs: number): void {
  let timer: ReturnType<typeof setInterval> | undefined

  function start() {
    stop()
    fn()
    timer = setInterval(fn, intervalMs)
  }

  function stop() {
    clearInterval(timer)
    timer = undefined
  }

  function onVisibilityChange() {
    if (document.visibilityState === 'visible') start()
    else stop()
  }

  onMounted(() => {
    start()
    document.addEventListener('visibilitychange', onVisibilityChange)
  })

  onUnmounted(() => {
    stop()
    document.removeEventListener('visibilitychange', onVisibilityChange)
  })
}
