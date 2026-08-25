/**
 * 把后台改过的官网文案盖到 i18n 之上。
 *
 * 官网 934 条版面文字（标题/导语/正文段落/按钮字）原本只存在于 `i18n/locales/{zh,en}.json`，
 * 改一个字就要改代码 + 重新 `npm run generate`。现在这批文案在库里有一份可编辑副本
 * （`action_site_text`，后台「站点文案管理」页维护），本插件在应用启动时取回**被改过的那些**
 * 并 merge 进 vue-i18n。
 *
 * 三点决定了它长这样：
 *
 * 1. **接口只返回改过的词条，不是全部 934 条。**
 *    这层挂在每一个页面上，整包返回等于给每份 HTML 的 hydration payload 白压约 120KB。
 *    没人改过时接口返回 `{zh:{},en:{}}`，代价接近于零。
 *
 * 2. **构建期取一次，客户端再取一次。**
 *    站点是 `nitro.preset: 'static'`：构建期这次取数会跟着 `useState` 进 payload，
 *    于是预渲染出来的 HTML 里就带着当时的文案（SEO 与首屏都拿到正确内容），客户端从 payload
 *    还原、同步 merge，**不会有 hydration 不匹配**。挂载后再取一次，后台改完文案访客刷新即见
 *    —— 这与 `useSiteApi` 默认的 hydration 后重取是同一套路数（连挂的钩子都一样是
 *    `onNuxtReady`，原因见那个文件里关于 `isHydrating` 的长注释），只是这里作用于文案。
 *    搜索引擎看到的仍是上次构建的快照，那要靠后台的「重新生成官网」按钮。
 *
 * 3. **切语言后要重新 merge，而且要 merge 两次。**
 *    locale 消息是按语言加载的，加载动作会覆盖掉我们先前 merge 进去的那一份。
 *    不挂 `i18n:localeSwitched` 这个钩子，表现就是「首屏文案是新的，切一次语言变回旧的」。
 *    但**只挂钩子不够**（`strategy: 'no_prefix'` 特有，见下面 `patchSetLocale` 的注释）：
 *    钩子发完之后 `setLocale` 还会再加载一遍该语言的 JSON，把刚补上的覆盖项又盖掉。
 *
 * 取数失败一律当作「没有覆盖项」静默放过：这一层挂在所有页面上，
 * 接口挂掉的正确表现是官网显示代码里的默认文案，而不是整站白屏。
 */

/** 后端 `/action/site/texts` 的出参：键为完整 i18n 键（`index.s052`），值为改过的文案 */
interface TextOverrides {
  zh: Record<string, string>
  en: Record<string, string>
}

interface OverridesEnvelope {
  code: number
  data?: TextOverrides
}

const EMPTY: TextOverrides = { zh: {}, en: {} }

/**
 * 预渲染期的取数结果缓存。
 *
 * 插件对每条路由各跑一次 setup，62 条路由就是 62 次一模一样的请求 —— 而整个 `nuxt generate`
 * 跑在同一个 Nitro 进程里，取一次就够。只在 `import.meta.prerender` 下启用：
 * 哪天改成 `preset: 'node-server'` 实时 SSR，这个缓存会把文案钉死在进程启动那一刻。
 */
let prerenderCache: Promise<TextOverrides> | null = null

/** 取数失败只提醒一次。不加这个开关，预渲染时同一条错误会连刷 62 遍，把真正的构建日志淹掉 */
let warned = false

/**
 * 把 `a.b.c` 形式的扁平键还原成嵌套对象。
 *
 * vue-i18n 的 `t('index.s052')` 走的是**路径解析**，消息树里得真有 `index` → `s052` 这层结构；
 * 直接 merge 一个字面量带点的键（`{'index.s052': '…'}`）是查不到的。
 *
 * @param flat 扁平键值对
 * @returns 嵌套的消息对象
 */
function unflatten(flat: Record<string, string>): Record<string, unknown> {
  const root: Record<string, unknown> = {}

  for (const [path, value] of Object.entries(flat)) {
    const segments = path.split('.')
    let node = root
    for (let i = 0; i < segments.length - 1; i++) {
      const key = segments[i]!
      // 已存在的同名叶子（字符串）不能当容器用，遇到就让位给对象，否则后面的赋值会静默丢失
      if (typeof node[key] !== 'object' || node[key] === null) node[key] = {}
      node = node[key] as Record<string, unknown>
    }
    node[segments[segments.length - 1]!] = value
  }

  return root
}

export default defineNuxtPlugin({
  name: 'action:site-texts',
  // i18n 实例得先就位才谈得上往里 merge
  dependsOn: ['i18n:plugin'],

  async setup(nuxtApp) {
    const { public: { apiBase } } = useRuntimeConfig()
    // useState 而非普通变量：构建期取到的值要经 payload 交给客户端，客户端才能同步 merge
    const overrides = useState<TextOverrides>('site-text-overrides', () => EMPTY)

    const fetchOverrides = async (): Promise<TextOverrides> => {
      const url = `${apiBase}/action/site/texts`
      try {
        const res = await $fetch<OverridesEnvelope>(url)

        return res?.code === 200 && res.data ? { zh: res.data.zh ?? {}, en: res.data.en ?? {} } : EMPTY
      } catch (e) {
        if (!warned) {
          warned = true
          const status = (e as { status?: number })?.status
          // 404 基本只有一个原因，直接把结论写出来，省得下一个人再从堆栈往回查
          const hint =
            status === 404
              ? '后端没有这个接口 —— 多半是后端进程还是加这条路由之前启动的，重启后端即可。'
              : '接口不可达。'
          console.warn(`[site-texts] ${hint} 本次改用打包进来的默认文案（${url}，${status ?? e}）`)
        }

        return EMPTY
      }
    }

    /** 预渲染期整个构建只取一次，其余场景每次都取 */
    const fetchOnce = (): Promise<TextOverrides> => {
      if (!import.meta.prerender) return fetchOverrides()
      prerenderCache ??= fetchOverrides()

      return prerenderCache
    }

    /** vue-i18n 全局 composer 里本插件用到的那两个方法 */
    interface I18nTarget {
      mergeLocaleMessage?: (locale: string, messages: Record<string, unknown>) => void
      setLocale?: (locale: string) => Promise<void>
    }

    const apply = () => {
      const i18n = nuxtApp.$i18n as I18nTarget
      if (!i18n?.mergeLocaleMessage) return
      for (const locale of ['zh', 'en'] as const) {
        const flat = overrides.value[locale]
        if (flat && Object.keys(flat).length) i18n.mergeLocaleMessage(locale, unflatten(flat))
      }
    }

    /**
     * 包一层 `setLocale`，等它整条链跑完再补一次覆盖项。
     *
     * **`i18n:localeSwitched` 钩子发得太早，光靠它切一次语言就会退回默认文案。**
     * `strategy: 'no_prefix'` 下 @nuxtjs/i18n 的 `composer.setLocale` 是这么走的
     * （`dist/runtime/plugins/i18n.js` 的 `composer.setLocale`）：
     *
     *   1. `loadAndSetLocale()` —— 内部 `loadLocale()` 把该语言的 JSON merge 进消息树
     *      （覆盖项在这一步被默认文案盖掉），设好 locale，然后发 `i18n:localeSwitched`；
     *      下面那个钩子在此补回覆盖项
     *   2. 回到 `setLocale` 里，因为是 `no_prefix`，**再 `loadLocaleMessages(locale)` 一遍**
     *      —— 同一份 JSON 又 merge 一次，刚补回去的覆盖项第二次被盖掉
     *
     * 于是表现成「后台改过的那句，切一次语言就变回代码里的原文」。这里在第 2 步之后再 apply。
     * 钩子仍然保留：它覆盖的是不经 `setLocale` 的路径（初次语言探测重定向等）。
     * apply 幂等且只 merge 被改过的那几条，多跑一次可以忽略不计。
     */
    const patchSetLocale = () => {
      const i18n = nuxtApp.$i18n as I18nTarget
      const original = i18n.setLocale?.bind(i18n)
      if (!original) return
      // 组件里的 `useI18n().setLocale` 最终也是 `Reflect.apply(globalComposer.setLocale, ...)`，
      // 打在全局 composer 上这一处即可，页面无需改动
      i18n.setLocale = async (locale: string) => {
        await original(locale)
        apply()
      }
    }

    if (import.meta.server) overrides.value = await fetchOnce()
    apply()

    if (import.meta.client) {
      // 挂载后重取：预渲染那次是构建时的快照，后台此后改过的文案要在这里补上
      onNuxtReady(async () => {
        overrides.value = await fetchOverrides()
        apply()
      })
      // 切语言会（重新）加载该语言的消息，把 merge 进去的覆盖项冲掉，这里补回来。
      // 这个钩子发得早于 setLocale 里最后那次加载，所以还需要下面那层包装，两者缺一不可
      nuxtApp.hook('i18n:localeSwitched', () => apply())
      patchSetLocale()
    }
  },
})
