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

/** 接口信封 */
interface Envelope<T> {
  code: number
  msg?: string
  rows?: T
  data?: T
  total?: number
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
 * @param query 查询参数，如 `{ pageNum: 1, pageSize: 50 }`
 * @param key useFetch 的缓存键，同一页面多次取数时须各自唯一
 */
export function useSiteList<T>(path: string, query: Record<string, unknown> = {}, key?: string) {
  const { public: { apiBase } } = useRuntimeConfig()

  return useFetch<Envelope<T[]>>(() => buildUrl(apiBase, path), {
    query,
    key: key ?? `site-list:${path}`,
    // 失败不抛：交给下面的 transform / default 兜住，页面只会少一块内容
    transform: (res): Envelope<T[]> => stripInternal(res),
    default: (): Envelope<T[]> => ({ code: 0, rows: [] }),
    onResponseError({ response }) {
      console.error(`[useSiteList] ${path} 取数失败`, response?.status, response?._data)
    },
  })
}

/**
 * 取单体/树形接口（出参在 `data` 里）。
 */
export function useSiteObject<T>(path: string, key?: string) {
  const { public: { apiBase } } = useRuntimeConfig()

  return useFetch<Envelope<T>>(() => buildUrl(apiBase, path), {
    key: key ?? `site-object:${path}`,
    transform: (res): Envelope<T> => stripInternal(res),
    default: (): Envelope<T> => ({ code: 0 }),
    onResponseError({ response }) {
      console.error(`[useSiteObject] ${path} 取数失败`, response?.status, response?._data)
    },
  })
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
