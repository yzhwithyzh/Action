/**
 * 百度统计（hm.baidu.com）。
 *
 * 不直接把官方那段 <script> 塞进 app.head：官网水合后是 SPA，站内跳转不重新加载页面，
 * hm.js 只会记下落地那一页 —— 点进新闻、规范详情都不算 PV。所以首屏由 hm.js 自己记，
 * 之后每次路由切换手动补一条 `_trackPageview`。
 *
 * 开发期不加载，免得本机调试的访问混进正式统计。
 */
const HM_ID = 'df20b3527772c7d4ff75f75cebf8f0b4'

declare global {
  interface Window { _hmt?: unknown[][] }
}

export default defineNuxtPlugin(() => {
  if (import.meta.dev) return

  window._hmt = window._hmt || []
  const hm = document.createElement('script')
  hm.src = `https://hm.baidu.com/hm.js?${HM_ID}`
  hm.async = true
  document.head.appendChild(hm)

  const router = useRouter()
  router.afterEach((to, from) => {
    // 首屏那次由 hm.js 加载时自己记；只改 query/hash 的不算新页面
    if (!from.matched.length || to.path === from.path) return
    window._hmt!.push(['_trackPageview', to.fullPath])
  })
})
