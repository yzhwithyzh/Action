/**
 * 官网访客鉴权 —— 全站首个鉴权基建。
 *
 * 本仓此前零鉴权：无 Pinia、无 `useState`、无 `plugins/`、无 `middleware/`，
 * `useSiteRequest()` 也不注入任何 header。这里把三件事一次性收敛掉：
 *
 *  1. **令牌存放**：`useCookie('action_token')` 存 token（不是 localStorage —— 后者
 *     在 SSR/预渲染期不存在），`useState('auth-guest')` 存访客信息。`nuxt.config.ts`
 *     是 `nitro.preset: 'static'`，**全站构建期预渲染**，所以 `useState` 的初值必须
 *     是 `null`，`fetchMe()` 只能在 `onMounted` 之后调；「先渲染未登录态、水合后切成
 *     已登录」是静态站的固有代价，不是 bug。
 *  2. **信封不对称**：`/auth/register` 与 `/auth/login` 用 `model_content`，`token`
 *     与 `guest` 铺在**顶层**；`/auth/me` 用 `data`；`/auth/email-code` 只回 `msg`。
 *     页面一律不碰原始响应，只看下面几个方法的返回值。
 *  3. **中文错误文案 → 当前语言**：后端 msg 全是中文硬编码，映射表见
 *     `./authValidation` 的 `BACKEND_MESSAGE_KEYS`。
 *
 * 为什么不复用 `useSiteRequest()`：它的 `buildUrl` 前缀虽然正好覆盖 auth 接口，
 * 但它不注入任何 header，改它会波及全部 8 个页面的取数。
 *
 * 纯逻辑（跳转目标校验、后端文案映射表、表单校验）在 `./authValidation`，那边零
 * Nuxt 依赖、可直接单测。
 */
import {
  backendMessageKey,
  isHeaderSafeToken,
} from './authValidation'

/** 访客信息（对应后端 GuestPublicInfoModel，刻意不含 user_id） */
export interface GuestInfo {
  email: string
  username: string
  institution: string | null
  position: string | null
}

/** 后端信封。token/guest 是 register 与 login 的顶层字段，data 是 me 的 */
interface AuthEnvelope {
  code: number
  msg?: string
  token?: string
  guest?: GuestInfo
  data?: GuestInfo
}

/** 统一调用结果。`message` 已按当前语言翻译好，页面直接塞进 `.fmsg` */
export interface AuthResult {
  ok: boolean
  message: string
}

interface AuthOutcome extends AuthResult {
  envelope?: AuthEnvelope
}

/** 注册入参（与后端 GuestRegisterModel 的驼峰别名一致） */
export interface RegisterPayload {
  email: string
  code: string
  username: string
  institution: string | null
  position: string | null
  password: string
  confirmPassword: string
}

/** 登录入参：`code` 与 `password` 二选一，两个都传会被后端的 model_validator 拒 */
export interface LoginPayload {
  email: string
  code?: string
  password?: string
}

const OK_CODE = 200
const UNAUTHORIZED = 401
/** 与 cookie 的 maxAge 一致：后端 JWT 默认 24 小时 */
const TOKEN_MAX_AGE = 86400

/**
 * 单次请求的上限。
 *
 * 没有这条时，一个悬挂的连接会让 promise 永不 settle：页面的
 * `finally { submitting.value = false }` 永不执行 → 按钮永久禁用 → 整张表单不可用，
 * 用户只能刷新，填过的内容全丢。
 */
const REQUEST_TIMEOUT = 15000

/**
 * 匿名接口：**不能**带 `Authorization`。
 *
 * 这三个接口后端本来就不看 header，但只要带上，一个被篡改成含非 Latin-1 字符的
 * cookie 就会在 `new Headers()` 处抛 `TypeError`，把登录/注册一起锁死——用户连
 * 自救的入口都没有。
 */
const ANONYMOUS_PATHS = ['/auth/login', '/auth/register', '/auth/email-code']

/**
 * Redis 不可用时后端也走 401。
 *
 * `common/aspect/guest_auth.py` 在 Redis 抖动时抛
 * `AuthException(message='服务暂时不可用，请稍后重试')`，经 `ResponseUtil.unauthorized`
 * 变成 `code=401` 的信封（HTTP 仍是 200）。把它当成「token 过期」去清 cookie，等于
 * Redis 抖一下就把全站在线访客静默踢光。
 */
const SERVICE_UNAVAILABLE_MSG = '服务暂时不可用，请稍后重试'

/**
 * 是否是超时/中止导致的失败
 *
 * @param err `$fetch` 抛出的异常
 * @returns 命中则应显示「请求超时」而不是笼统的「网络异常」
 */
function isTimeoutError(err: unknown): boolean {
  const e = err as { name?: string; message?: string; cause?: { name?: string } }
  const names = [e?.name, e?.cause?.name]

  return names.includes('AbortError') || names.includes('TimeoutError') || /timeout|aborted/i.test(e?.message ?? '')
}

// 注：`resolveRedirect` 与后端文案映射表已迁到 `./authValidation`（纯函数、可单测）。
// 那边同在 `composables/` 下，Nuxt 一样会自动导入，页面无需改 import。
// 这里**刻意不再 re-export**：同名符号在两个 composables 文件里各导出一次会让
// unimport 的自动导入表出现重复键。

export function useAuth() {
  const { t } = useI18n()
  const { public: { apiBase } } = useRuntimeConfig()

  // 同一份 cookie 在多个组件里各 useCookie 一次会拿到各自的 ref，Nuxt 靠
  // BroadcastChannel / CookieStore 在同文档内互相同步（nuxt/dist/app/composables/cookie.js），
  // 所以登录页写入的 token，顶栏那份 ref 也能看到。
  const token = useCookie<string | null>('action_token', {
    maxAge: TOKEN_MAX_AGE,
    sameSite: 'lax',
    secure: !import.meta.dev,
    default: () => null,
  })
  // 初值必须是 null：全站构建期预渲染，任何非空初值都会被烤进静态 HTML
  const guest = useState<GuestInfo | null>('auth-guest', () => null)
  const isLoggedIn = computed(() => !!guest.value)

  /** 清空本地登录态（token 与访客信息必须同进同退） */
  const clearAuth = () => {
    token.value = null
    guest.value = null
  }

  /**
   * 后端中文 msg → 当前语言文案；未命中原样返回并 warn。
   *
   * 未命中一律「原样显示后端 msg + `console.warn`」，不静默吞掉——后端改了文案这件
   * 事必须是可观测的信号，而不是让英文界面悄悄冒出中文。
   */
  const translate = (msg?: string | null): string => {
    const raw = (msg ?? '').trim()
    if (!raw) return t('auth.err.unknown')
    const key = backendMessageKey(raw)
    if (key) return t(key)
    console.warn(`[useAuth] 后端文案未命中映射表，按原文显示：${raw}`)

    return raw
  }

  /**
   * 构造请求头。
   *
   * 匿名接口一律不带 `Authorization`；token 值不适合进 header（cookie 被篡改）时
   * 直接清掉本地登录态，绝不能让一个坏 cookie 把后续所有请求——包括登录本身——
   * 卡在 `new Headers()` 的 `TypeError` 上。
   *
   * @param path 接口路径
   * @param sentToken 本次请求发出时的 token 快照
   * @returns header 对象；token 不可用时返回不带 header 的空对象
   */
  const buildHeaders = (path: string, sentToken: string | null): Record<string, string> => {
    try {
      if (ANONYMOUS_PATHS.includes(path) || !sentToken) return {}
      if (!isHeaderSafeToken(sentToken)) {
        clearAuth()

        return {}
      }

      return { Authorization: `Bearer ${sentToken}` }
    } catch {
      // 兜底：header 构造本身出任何意外，都按「这个 token 用不了」处理
      clearAuth()

      return {}
    }
  }

  /**
   * 带 Authorization 的请求。
   *
   * 401 的处理有两条例外，缺一条就会误杀有效登录态：
   *  1. msg 是「服务暂时不可用」时是 **Redis 抖动**，不是 token 过期——不清登录态；
   *  2. 只有「这条响应对应的 token 仍是当前 token」才清——顶栏 `fetchMe` 挂 60 秒
   *     期间用户已重新登录拿到新 token，迟到的 401 不许把新会话删掉。
   */
  const call = async (path: string, method: 'GET' | 'POST', body?: unknown): Promise<AuthOutcome> => {
    // 发出前捕获当时的 token，401 回来时用它判断这条响应是不是「过期的过期」
    const sentToken = token.value
    const headers = buildHeaders(path, sentToken)
    const dropStaleAuth = () => {
      if (token.value === sentToken) clearAuth()
    }

    try {
      const res = await $fetch<AuthEnvelope>(`${apiBase}/action/site${path}`, {
        method,
        body,
        headers,
        timeout: REQUEST_TIMEOUT,
      })
      if (res?.code === UNAUTHORIZED) {
        if ((res.msg ?? '').trim() === SERVICE_UNAVAILABLE_MSG) return { ok: false, message: translate(res.msg) }
        dropStaleAuth()

        return { ok: false, message: t('auth.err.sessionExpired') }
      }
      if (res?.code !== OK_CODE) return { ok: false, message: translate(res?.msg) }

      return { ok: true, message: '', envelope: res }
    } catch (err: unknown) {
      const status = (err as { status?: number; statusCode?: number })?.status
        ?? (err as { statusCode?: number })?.statusCode
      // 本站信封（限流走的是**真 HTTP 429**，$fetch 会抛，body 仍是 {code,msg}）
      const envelopeMsg = (err as { data?: { msg?: unknown } })?.data?.msg
      const backendMsg = typeof envelopeMsg === 'string' ? envelopeMsg.trim() : ''

      if (status === UNAUTHORIZED) {
        if (backendMsg === SERVICE_UNAVAILABLE_MSG) return { ok: false, message: translate(backendMsg) }
        dropStaleAuth()

        return { ok: false, message: t('auth.err.sessionExpired') }
      }
      // FastAPI 的 422 响应体是 {"detail":[{loc:[...], msg:...}]}，不是本站的 {code,msg}
      // 信封，$fetch 会直接抛。这里取第一条校验错误告诉用户是哪个字段，而不是笼统一句
      // 「提交失败」。（写法照 pages/collaborate.vue:74-85）
      const detail = (err as { data?: { detail?: Array<{ loc?: unknown[]; msg?: string }> } })?.data?.detail
      const first = Array.isArray(detail) ? detail[0] : undefined
      if (first?.msg) {
        const field = Array.isArray(first.loc) ? String(first.loc[first.loc.length - 1]) : ''

        return { ok: false, message: `${t('auth.err.fieldError')}${field ? field + ' — ' : ''}${first.msg}` }
      }
      // 后端准备好的中文提示不能丢：把「请求过于频繁」退化成「网络异常」，用户会立刻
      // 重试、把滑动窗口继续顶满，永远出不来。
      if (backendMsg) return { ok: false, message: translate(backendMsg) }
      if (isTimeoutError(err)) return { ok: false, message: t('auth.err.timeout') }

      return { ok: false, message: t('auth.err.network') }
    }
  }

  /** 写入登录态。token 与 guest 在 register/login 的信封**顶层**，不在 data 里 */
  const applyAuth = (envelope?: AuthEnvelope): boolean => {
    if (!envelope?.token || !envelope?.guest) return false
    token.value = envelope.token
    guest.value = envelope.guest

    return true
  }

  /**
   * 发送邮箱验证码
   *
   * @param email 邮箱
   * @param scene 场景（register 注册 / login 登录）
   * @param sourceLang 邮件正文语言
   */
  const sendCode = async (email: string, scene: 'register' | 'login', sourceLang: string): Promise<AuthResult> => {
    return await call('/auth/email-code', 'POST', { email, scene, sourceLang })
  }

  /** 注册；成功即写入登录态 */
  const register = async (payload: RegisterPayload): Promise<AuthResult> => {
    const res = await call('/auth/register', 'POST', payload)
    if (res.ok && !applyAuth(res.envelope)) return { ok: false, message: t('auth.err.unknown') }

    return res
  }

  /** 登录；成功即写入登录态 */
  const login = async (payload: LoginPayload): Promise<AuthResult> => {
    const res = await call('/auth/login', 'POST', payload)
    if (res.ok && !applyAuth(res.envelope)) return { ok: false, message: t('auth.err.unknown') }

    return res
  }

  /** 登出：先撤销服务端会话，**接口失败也必须清本地**，否则用户退不出去 */
  const logout = async (): Promise<void> => {
    try {
      await call('/auth/logout', 'POST')
    } finally {
      clearAuth()
    }
  }

  /**
   * 回填当前访客信息（`/auth/me` 的访客信息在 `data` 里）。
   *
   * **只能在 `onMounted` 之后调**：全站预渲染，构建期调用会把访客信息烤进静态 HTML。
   * 401 已在 `call` 里静默清掉登录态；其余失败保持未登录态，不打扰用户。
   */
  const fetchMe = async (): Promise<void> => {
    if (!token.value) {
      guest.value = null

      return
    }
    const res = await call('/auth/me', 'GET')
    if (res.ok && res.envelope?.data) guest.value = res.envelope.data
  }

  /**
   * 带登录态调用官网接口。
   *
   * 暴露 `call` 是给报告助手这类「需要访客身份的业务接口」用的（如第三步的 checklist 校验）：
   * 401 清理、限流提示、FastAPI 422 字段错误、超时文案这几件事只该有一份实现。
   */
  return { guest, isLoggedIn, sendCode, register, login, logout, fetchMe, authedCall: call }
}
