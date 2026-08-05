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
   * 开启「先展示快照、后台再取一次」（stale-while-revalidate）。
   *
   * 站点是 `nitro.preset: 'static'`，数据在 **构建期** 就烤进 HTML，之后不会自己变。
   * 对后台可随时增删的内容（新闻/动态），不开这个开关就意味着：后台发了新稿，
   * 官网要等下一次 `npm run generate` 才看得见。开了之后首屏仍是预渲染的静态 HTML
   * （SEO 与首屏速度不变），hydration 后再跟后端对一次，有变化就换掉。
   *
   * 对几乎不变的内容（报告规范库、CFIR/ERIC/RE-AIM 词条）不要开：多一个请求没有收益。
   */
  swr?: boolean
  /** 查询参数（仅 `useSiteObject` 用；`useSiteList` 有独立的 query 形参） */
  query?: MaybeRefOrGetter<Record<string, unknown>>
}

/**
 * 客户端侧的重取策略，两件事：
 *
 *  1. `swr` 打开时，每次组件挂载都重取一次 —— 覆盖首屏 hydration 和后续路由切换。
 *     路由切换时 Nuxt 会命中 payload extraction 的 `nuxtApp.static.data` 直接复用构建期
 *     快照、根本不发请求，所以这里必须显式 refresh，不能指望「切走再回来」自己刷新。
 *  2. **无论开没开 `swr`**，只要构建期那次取数是失败的（payload 里带 `_errors`），
 *     就在客户端补一次。历史上出过一次：`npm run generate` 时后端没起来，
 *     5 个页面把 502 烤进了静态产物，线上首屏直接开天窗。这层兜底让它自愈。
 *
 * 用 `onMounted` 而不是在 setup 里直接调，是为了不破坏 SSR/预渲染那次取数；
 * `refresh()` 在新响应回来前会保留旧 `data`，所以不会闪空。
 */
function useClientRevalidate(result: { refresh: () => Promise<void>; error: { value: unknown } }, swr: boolean) {
  if (!import.meta.client || !getCurrentInstance()) return

  onMounted(() => {
    if (swr || result.error.value) void result.refresh()
  })
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
 * @param opts `{ swr: true }` 表示这块内容后台可随时变，见 `SiteFetchOptions`
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
    // 失败不抛：交给下面的 transform / default 兜住，页面只会少一块内容
    transform: (res): Envelope<T[]> => stripInternal(res),
    default: (): Envelope<T[]> => ({ code: 0, rows: [] }),
    onResponseError({ response }) {
      console.error(`[useSiteList] ${path} 取数失败`, response?.status, response?._data)
    },
  })

  useClientRevalidate(result, opts.swr === true)

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
    transform: (res): Envelope<T> => stripInternal(res),
    default: (): Envelope<T> => ({ code: 0 }),
    onResponseError({ response }) {
      console.error(`[useSiteObject] ${path} 取数失败`, response?.status, response?._data)
    },
  })

  useClientRevalidate(result, opts.swr === true)

  return result
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
