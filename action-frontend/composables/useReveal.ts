/**
 * 滚动揭示动画 —— 迁移自各页内联脚本中重复的 .reveal 逻辑。
 *
 * 与原实现保持一致：
 *  - 尊重 prefers-reduced-motion，降级为直接显示
 *  - 不支持 IntersectionObserver 时同样直接显示（避免内容永久隐藏）
 *  - 元素进入视口后加 .is-visible 并取消观察（一次性）
 *
 * 返回的 `rescan()` 供**列表在挂载后还会换内容**的页面调用（如 /news 的筛选与翻页）：
 * 观察者只在 onMounted 建立一次，v-for 换出来的新节点没人观察，会永远停在
 * `.reveal{opacity:0}` 上——即「点了筛选，行数对但一片空白」。数据变更后调一次即可。
 */
export function useReveal(rootSelector = '.reveal') {
  let io: IntersectionObserver | null = null
  /** 已处理过的节点，避免 rescan 重复观察（Vue 复用 DOM 时同一节点会被多次扫到） */
  let handled = new WeakSet<Element>()
  let mounted = false

  const showAll = (els: Element[]) => {
    for (const el of els) el.classList.add('is-visible')
  }

  const scan = () => {
    const els = Array.from(document.querySelectorAll(rootSelector)).filter((el) => !handled.has(el))
    if (!els.length) return
    for (const el of els) handled.add(el)

    // io 为 null 说明降级了（reduced-motion / 不支持 IO），新节点同样直接显示
    if (!io) {
      showAll(els)
      return
    }
    for (const el of els) io.observe(el)
  }

  onMounted(() => {
    mounted = true

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (!reduce && 'IntersectionObserver' in window) {
      io = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (!entry.isIntersecting) continue
            entry.target.classList.add('is-visible')
            io?.unobserve(entry.target)
          }
        },
        { rootMargin: '0px 0px -10% 0px', threshold: 0.06 },
      )
    }

    scan()
  })

  onBeforeUnmount(() => {
    mounted = false
    io?.disconnect()
    io = null
    handled = new WeakSet<Element>()
  })

  /** 列表内容换过之后调用；等 DOM 打完补丁再扫，否则扫到的还是旧节点 */
  const rescan = async () => {
    if (!mounted) return
    await nextTick()
    scan()
  }

  return { rescan }
}
