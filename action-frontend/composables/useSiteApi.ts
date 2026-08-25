/**
 * 官网公开接口的取数与双语选值。
 *
 * 后端出参统一为 `{ code, msg, rows|data, total }` 的信封（RuoYi 风格），
 * 且业务字段一律是驼峰 + `*Zh`/`*En` 成对。这里把两件事收敛掉：
 *  - 拼 apiBase、拆信封、失败时返回空值而不抛（任一区域挂掉不许整页白屏）
 *  - 按当前 locale 选中英文，且 `*En` 缺失时回落中文
 *
 * 不要在页面里硬编码 `http://127.0.0.1:9099`：dev 下 `apiBase` 是 `/dev-api`，
 * 由 `nuxt.config.ts` 的 routeRules 代理到后端；生产走 Nginx 等价配置。
 */

import type { MaybeRefOrGetter } from 'vue'

/** 接口信封 */
interface Envelope<T> {
  code: number
  msg?: string
  rows?: T
  data?: T
  total?: number
  pageNum?: number
  pageSize?: number
  hasNext?: boolean
}

/** 取数选项 */
interface SiteFetchOptions {
  /**
   * 关掉「hydration 之后再跟后端对一次」（默认是**开着**的）。
   *
   * 站点是 `nitro.preset: 'static'`，数据在 **构建期** 就烤进 HTML，之后不会自己变。
   * 不重取就意味着：后台改了内容，官网要等下一次 `npm run generate` 才看得见。
   * 重取不影响首屏 —— 首屏仍是预渲染的静态 HTML（SEO 与首屏速度不变），
   * hydration 完成后再跟后端对一次，有变化就换掉。
   *
   * **默认开、而不是逐页 opt-in**：这个开关原先叫 `swr`、默认关，于是有后台维护页、
   * 却没人记得开开关的内容就永远停在构建期快照上 —— `/implementation` 的 CFIR/ERIC/RE-AIM、
   * `/assistant` 的研究类型与 checklist 都是这样（当初判断「几乎不变」，后来都进了后台管理页）。
   * 漏开的表现是「后台点了保存、官网纹丝不动」，和后端挂了长得一样，每次都要重查一遍。
   * 一次多发一个几 KB 的 JSON 请求，换掉整类问题，值。
   *
   * 只有确认某个口「构建期取一次就永远够用」时才传 `false`，且写清理由。
   */
  revalidate?: boolean
  /** 查询参数（仅 `useSiteObject` 用；`useSiteList` 有独立的 query 形参） */
  query?: MaybeRefOrGetter<Record<string, unknown>>
}

/**
 * 客户端侧的重取策略，两件事：
 *
 *  1. 默认每次进入页面都重取一次 —— 覆盖首屏 hydration 和后续路由切换。
 *     路由切换时 Nuxt 会命中 payload extraction 的 `nuxtApp.static.data` 直接复用构建期
 *     快照、根本不发请求，所以这里必须显式 refresh，不能指望「切走再回来」自己刷新。
 *  2. 只要构建期那次取数是失败的（payload 里带 `_errors`），就在客户端补一次。
 *     历史上出过一次：`npm run generate` 时后端没起来，5 个页面把 502 烤进了静态产物，
 *     线上首屏直接开天窗。这层兜底让它自愈。
 *
 * **必须是 `onNuxtReady`，不能是 `onMounted` —— 这一条是这个文件里最容易踩的坑，
 * 换回去会让整套重取静默失效（曾经就是这样，症状是「后台改完刷多少次都是旧的」）。**
 * 原因在 Nuxt 的 `useAsyncData.execute()`：只要 `nuxtApp.isHydrating` 为真，
 * 它就先问 `getCachedData()`，而默认实现在 hydration 期间**无视 `refresh:manual`**
 * 直接返回 `nuxtApp.payload.data[key]`（静态站里就是 `_payload.json` 那份构建期快照），
 * 于是 `refresh()` 立刻用旧数据 resolve，**一个网络请求都不发**。
 * 而 `isHydrating` 要到 `app:suspense:resolve` 才置 false，那是在页面组件 `onMounted`
 * **之后**。`onNuxtReady` 正好挂在这个钩子上（`plugins/site-texts.ts` 用的也是它，
 * 所以后台文案一直能刷出来、列表数据却不能 —— 差别就在这里）。
 */
function useClientRevalidate(result: { refresh: () => Promise<void>; error: { value: unknown } }, enabled: boolean) {
  if (!import.meta.client || !getCurrentInstance()) return

  // onNuxtReady 不跟组件生命周期绑定（内部还排了一次 requestIdleCallback），
  // 页面在这之前被切走时不该再往一个已卸载的组件里灌数据
  let alive = true
  onBeforeUnmount(() => {
    alive = false
  })

  onNuxtReady(() => {
    if (!alive) return
    if (enabled || result.error.value) void result.refresh()
  })
}

/**
 * 业务码校验。
 *
 * 信封是「HTTP 200 + code 500」风格，业务错误进不了 `onResponseError`。不判这个 code，
 * 后端报错就会被下面的 `default` 兜成空数组、静默渲染成「这块内容本来就没有」；
 * 构建期发生就等于把空白烤进静态产物，而且 `error` 为空、客户端也不会补取（W28）。
 *
 * 判了之后：抛出 → `error` 有值 → 上面的 `useClientRevalidate` 在客户端补一次；
 * 页面拿到的仍是 `default`，不会白屏。网关吐 HTML 错误页（`res` 是字符串）也走这条。
 */
function assertOk<T extends { code?: number; msg?: string }>(res: T, path: string): T {
  if (!res || typeof res !== 'object' || res.code !== 200) {
    const code = (res as { code?: unknown })?.code
    const msg = (res as { msg?: unknown })?.msg
    throw new Error(`[useSiteApi] ${path} 返回业务失败：code=${String(code)} msg=${String(msg ?? '')}`)
  }

  return res
}

function buildUrl(apiBase: string, path: string): string {
  return `${apiBase}/action/site${path}`
}

/**
 * 后端出参未做白名单裁剪（`ResponseUtil` 直接返回 JSONResponse，`response_model` 只生成文档），
 * 于是 `remark`（内部迁移备注）、`delFlag`、审计字段会一路进到 Nuxt 的 hydration payload，
 * 也就是**公开页面的 HTML 源码**里。前端用不到这些字段，在取数时就地剥掉：
 * 既缩小 payload，也不把内部注记暴露给任何查看源码的人。
 * 根治仍需后端出参白名单化（deferred-work.md 的 W10 / W22）。
 */
const INTERNAL_FIELDS = ['remark', 'delFlag', 'createBy', 'createTime', 'updateBy', 'updateTime']

function stripInternal<T>(value: T): T {
  if (Array.isArray(value)) return value.map((v) => stripInternal(v)) as unknown as T
  if (value && typeof value === 'object') {
    const out: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if (INTERNAL_FIELDS.includes(k)) continue
      out[k] = stripInternal(v)
    }

    return out as T
  }

  return value
}

/**
 * 取分页列表接口（出参在 `rows` 里）。
 *
 * @param path `/action/site` 之后的路径，如 `/news`
 * @param query 查询参数。**传 computed / getter 即为响应式**：值一变就自动重取，
 *   分页与筛选就是靠这个走后端的（见 `pages/news/index.vue`）。传普通对象则等同于固定参数。
 * @param key useFetch 的缓存键，同一页面多次取数时须各自唯一
 * @param opts 见 `SiteFetchOptions`。**不用为「后台会改」做任何事**，重取是默认行为
 */
export function useSiteList<T>(
  path: string,
  query: MaybeRefOrGetter<Record<string, unknown>> = {},
  key?: string,
  opts: SiteFetchOptions = {},
) {
  const { public: { apiBase } } = useRuntimeConfig()

  /**
   * 归一成 computed 再交给 useFetch —— useFetch 内部把 options 塞进 `reactive()` 深度侦听，
   * ref/computed 会被解包并跟踪，但**普通函数 getter 不会**。这里统一包一层，
   * 调用方传对象、ref 还是 getter 都能正确触发重取。
   */
  const queryRef = computed(() => toValue(query))

  const result = useFetch<Envelope<T[]>>(() => buildUrl(apiBase, path), {
    query: queryRef,
    key: key ?? `site-list:${path}`,
    // HTTP 层失败不抛到页面：useAsyncData 会把它收进 error、data 落到下面的 default，
    // 页面只会少一块内容。业务层失败由 assertOk 补一道，两者最终都落在 error 上
    transform: (res): Envelope<T[]> => stripInternal(assertOk(res, path)),
    default: (): Envelope<T[]> => ({ code: 0, rows: [] }),
    onResponseError({ response }) {
      console.error(`[useSiteList] ${path} 取数失败`, response?.status, response?._data)
    },
    onRequestError({ error }) {
      // 后端进程完全不可达时只有这个钩子会响，不挂等于控制台一片安静
      console.error(`[useSiteList] ${path} 请求未送达`, error)
    },
  })

  useClientRevalidate(result, opts.revalidate !== false)

  return result
}

/**
 * 取单体/树形接口（出参在 `data` 里）。
 *
 * `opts.query` 用于出参在 `data`、但需要按参数取的接口（如报告助手按规范代号取 checklist 条目）。
 * 与 `useSiteList` 的 `query` 同样支持 ref/getter，变化即重取。
 */
export function useSiteObject<T>(path: string, key?: string, opts: SiteFetchOptions = {}) {
  const { public: { apiBase } } = useRuntimeConfig()
  const queryRef = computed(() => (opts.query ? toValue(opts.query) : undefined))

  const result = useFetch<Envelope<T>>(() => buildUrl(apiBase, path), {
    query: queryRef,
    key: key ?? `site-object:${path}`,
    transform: (res): Envelope<T> => stripInternal(assertOk(res, path)),
    default: (): Envelope<T> => ({ code: 0 }),
    onResponseError({ response }) {
      console.error(`[useSiteObject] ${path} 取数失败`, response?.status, response?._data)
    },
    onRequestError({ error }) {
      console.error(`[useSiteObject] ${path} 请求未送达`, error)
    },
  })

  useClientRevalidate(result, opts.revalidate !== false)

  return result
}

/**
 * 拼公开接口的地址，供**由浏览器自己发起请求**的场景用（`<iframe src>` / `<a href>`）。
 * 这类请求不走 useFetch，也就拿不到 `apiBase` —— 但同样不能在页面里硬编码后端地址。
 */
export function useSiteUrl() {
  const { public: { apiBase } } = useRuntimeConfig()

  return (path: string) => buildUrl(apiBase, path)
}

/**
 * 按需取数（用于点击后才请求的场景，如 srd 的「运行评估」）。
 * 与上面两个不同：它不参与 SSR 预渲染，失败时抛给调用方自己处理。
 */
export function useSiteRequest() {
  const { public: { apiBase } } = useRuntimeConfig()

  return {
    /** GET，返回信封里的 data */
    async get<T>(path: string): Promise<T | null> {
      const res = await $fetch<Envelope<T>>(buildUrl(apiBase, path))
      return res?.code === 200 ? (res.data ?? null) : null
    },
    /** POST，返回整个信封，调用方自己看 code */
    async post<T>(path: string, body: unknown): Promise<Envelope<T>> {
      return await $fetch<Envelope<T>>(buildUrl(apiBase, path), { method: 'POST', body })
    },
  }
}

/**
 * 双语选值。
 *
 * `pick(row, 'title')` → locale 为 zh 取 `titleZh`；为 en 取 `titleEn`，
 * **`titleEn` 为空串或 null 时回落 `titleZh`**。
 * 回落是硬需求不是防御：`action_guideline.name_en` 有 4 条是合成值，
 * 数据侧缺英文时不回落会在英文界面留白。
 */
export function useBilingual() {
  const { locale } = useI18n()

  const pick = (row: Record<string, unknown> | null | undefined, field: string): string => {
    if (!row) return ''
    const zh = row[`${field}Zh`]
    const en = row[`${field}En`]
    const zhText = zh == null ? '' : String(zh)
    const enText = en == null ? '' : String(en)

    return locale.value === 'en' ? (enText || zhText) : zhText
  }

  const isEn = computed(() => locale.value === 'en')

  return { pick, isEn }
}
