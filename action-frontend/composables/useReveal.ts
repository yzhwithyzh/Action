/**
 * 滚动揭示动画 —— 迁移自各页内联脚本中重复的 .reveal 逻辑。
 *
 * 与原实现保持一致：
 *  - 尊重 prefers-reduced-motion，降级为直接显示
 *  - 不支持 IntersectionObserver 时同样直接显示（避免内容永久隐藏）
 *  - 元素进入视口后加 .is-visible 并取消观察（一次性）
 */
export function useReveal(rootSelector = '.reveal') {
  let io: IntersectionObserver | null = null

  const showAll = (els: Element[]) => {
    for (const el of els) el.classList.add('is-visible')
  }

  onMounted(() => {
    const els = Array.from(document.querySelectorAll(rootSelector))
    if (!els.length) return

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce || !('IntersectionObserver' in window)) {
      showAll(els)
      return
    }

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
    for (const el of els) io.observe(el)
  })

  onBeforeUnmount(() => {
    io?.disconnect()
    io = null
  })
}
