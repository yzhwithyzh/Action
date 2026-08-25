/**
 * 滚动揭示动画 —— 迁移自各页内联脚本中重复的 .reveal 逻辑。
 *
 * 与原实现保持一致：
 *  - 尊重 prefers-reduced-motion，降级为直接显示
 *  - 不支持 IntersectionObserver 时同样直接显示（避免内容永久隐藏）
 *  - 元素进入视口后打上「已揭示」标记并取消观察（一次性）
 *
 * **标记用 `data-revealed` 属性而不是 `is-visible` 类**，这一条是硬约束不是风格选择：
 * 揭示是在 Vue 之外用 DOM API 打的，而 Vue 的 patchClass 在 `:class` 绑定变化时会
 * 整个重写 `el.className`，把外人加的类连带抹掉。`pages/guidelines.vue` 的规范卡片
 * 同时带 `class="gl-card reveal"` 和 `:class="{ hide }"`，点一下筛选 chip 就撞上这条：
 * 卡片丢了标记退回 `opacity:0`，而 `rescan()` 因为节点在 `handled` 里也救不回来
 * —— 表现就是「点了筛选按钮，卡片全部消失」。属性不在 Vue 的 patch 范围内，不会被覆盖。
 *
 * **挂载后新插进 DOM 的 `.reveal` 由 MutationObserver 自动接管**，页面不用管。
 * 这一条是根治性的：`useSiteApi` 现在默认会在 hydration 之后跟后端重取一次，于是
 * **任何**一块接口数据都可能在挂载后换掉 v-for 出来的节点；而观察者只在 onMounted 建立一次，
 * 没人观察的新节点会永远停在 `.reveal{opacity:0}` 上 —— 即「数据对、行数对，但整块空白」。
 * 以前靠每个页面自己 `watch(rows, rescan)`，这是个「谁忘了谁踩」的约定，
 * 而漏掉的表现（一片空白）又和「后台还没填内容」长得一模一样，极难归因。
 *
 * 返回的 `rescan()` 保留给「DOM 变化不体现为节点新增」的场景手动补一刀，正常不需要调。
 *
 * 返回的 `revealNow()` 供**从 display:none 切回可见**的页面调用（如 about/guidelines 的
 * 子栏目 Tab）：这类节点 IntersectionObserver 也会补触发，但会先空一帧再淡入。
 */
/** 打上「已揭示」标记。唯一写入点，页面不要自己去操作 class/属性 */
function mark(el: Element) {
  el.setAttribute('data-revealed', '')
}

export function useReveal(rootSelector = '.reveal') {
  let io: IntersectionObserver | null = null
  /** 监听 DOM 里新出现的 `.reveal`（接口重取、筛选、翻页换出来的节点） */
  let mo: MutationObserver | null = null
  /** 已处理过的节点，避免 rescan 重复观察（Vue 复用 DOM 时同一节点会被多次扫到） */
  let handled = new WeakSet<Element>()
  let mounted = false
  /** 同一帧内的多次 DOM 变更合并成一次扫描 */
  let scanQueued = false

  const showAll = (els: Element[]) => {
    for (const el of els) mark(el)
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

  /** 一帧一次：DOM 打完补丁再扫，且不为同一批变更重复 querySelectorAll */
  const scheduleScan = () => {
    if (scanQueued || !mounted) return
    scanQueued = true
    requestAnimationFrame(() => {
      scanQueued = false
      if (mounted) scan()
    })
  }

  onMounted(() => {
    mounted = true

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (!reduce && 'IntersectionObserver' in window) {
      io = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (!entry.isIntersecting) continue
            mark(entry.target)
            io?.unobserve(entry.target)
          }
        },
        { rootMargin: '0px 0px -10% 0px', threshold: 0.06 },
      )
    }

    scan()

    if ('MutationObserver' in window) {
      mo = new MutationObserver((records) => {
        // 只关心「有元素被插进来」。文本节点改动（srd 的进度条、倒计时之类）每秒能触发很多次，
        // 那些节点早已在 handled 里，为它们扫一遍全文档是纯浪费
        for (const r of records) {
          for (const node of r.addedNodes) {
            if (node.nodeType !== Node.ELEMENT_NODE) continue
            scheduleScan()

            return
          }
        }
      })
      mo.observe(document.body, { childList: true, subtree: true })
    }
  })

  onBeforeUnmount(() => {
    mounted = false
    io?.disconnect()
    io = null
    mo?.disconnect()
    mo = null
    handled = new WeakSet<Element>()
  })

  /** 列表内容换过之后调用；等 DOM 打完补丁再扫，否则扫到的还是旧节点 */
  const rescan = async () => {
    if (!mounted) return
    await nextTick()
    scan()
  }

  /**
   * 立刻揭示某个容器内的全部 `.reveal`（不等观察者）。
   *
   * @param root 容器元素或其 id
   */
  const revealNow = (root: Element | string | null) => {
    const el = typeof root === 'string' ? document.getElementById(root) : root
    if (!el) return
    for (const child of el.querySelectorAll(rootSelector)) {
      handled.add(child)
      mark(child)
    }
  }

  return { rescan, revealNow }
}
