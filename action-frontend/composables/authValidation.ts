/**
 * 访客鉴权的**纯逻辑层** —— 零 Nuxt / 零 Vue 依赖，可直接被 vitest `import`。
 *
 * 这里收的是原先散在 `pages/login.vue` 与 `pages/register.vue` 里各写一遍、
 * 且不可测的东西：跳转目标校验、后端文案映射、表单校验、倒计时余量计算。
 * 两个页面只保留「取值 → 调校验 → 显示 `t(key)`」这一层，校验规则本身单点维护。
 *
 * 约定：所有校验函数**返回 i18n key 或 `null`**，不返回已翻译的文案 ——
 * 翻译要靠 `useI18n()`，那是组件上下文里的东西，放进来就没法单测了。
 */

/** 后端 `GuestRegisterModel` / `GuestLoginModel` 的长度上限（字符按**码点**计） */
export const AUTH_LIMITS = {
  email: 50,
  code: 6,
  username: 30,
  institution: 300,
  position: 100,
  passwordMin: 6,
  passwordMax: 50,
  /** bcrypt 的硬上限，后端 `action_vo.py` 在入参层按 UTF-8 字节拦 */
  passwordMaxBytes: 72,
} as const

/** 验证码重发冷却，与后端 Redis 冷却窗口一致 */
export const AUTH_RESEND_SECONDS = 60

export const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
export const CODE_PATTERN = /^\d{6}$/

/**
 * 按 **Unicode 码点**数长度。
 *
 * `String.length` 数的是 UTF-16 码元，而后端 pydantic 的 `min_length`/`max_length`
 * 数的是码点，两边对不上时**两个方向都会错判**：`'🔑🔑🔑'` 前端算 6 通过、后端算 3
 * 拒绝（且返回未翻译的 pydantic 英文原文）；16 个 emoji 的用户名前端算 32 拒绝、
 * 后端算 16 本该放行。
 */
export function codePointLength(value: string): number {
  return [...value].length
}

/** UTF-8 字节数。与码点计数是**两条独立规则**：bcrypt 限的是字节，pydantic 限的是码点 */
export function utf8ByteLength(value: string): number {
  return new TextEncoder().encode(value).length
}

/**
 * 是否含尖括号。
 *
 * 后端 `@Xss` 的正则对任何一对尖括号都命中（`action_vo.py:489-495`），且它的报错
 * 是中文硬编码。英文用户在 Institution 里填 `Dept. <Neurology>` 这种再正常不过的
 * 输入就会踩到，所以前端先拦、给本地化提示，不让用户白跑一趟。
 */
export function hasAngleBrackets(value: string): boolean {
  return value.includes('<') || value.includes('>')
}

/**
 * Header 值是否安全。
 *
 * cookie 里的 token 一旦被篡改成含非 Latin-1 字符，`new Headers()` 会在 `$fetch`
 * 真正发出请求**之前**抛 `TypeError`，落进 catch 后既拿不到 status 也拿不到响应体，
 * 于是「网络异常 + 不清登录态」——用户改去登录，登录请求同样带这个 header、同样抛，
 * 被永久锁在站外。JWT 只可能是 base64url + `.`，这里直接按可打印 ASCII 卡。
 */
export function isHeaderSafeToken(value: string): boolean {
  return /^[!-~]+$/.test(value)
}

/** 鉴权页自身不能作为登录后的跳转目标 */
const AUTH_PAGE_PATHS = ['/login', '/register']

/**
 * 校验并归一化登录后的跳转目标。
 *
 * 只接受站内相对路径：必须以 `/` 开头，且不能以 `//` 或 `/\` 开头（浏览器会把
 * `/\evil.com` 当协议相对 URL 解析）——否则就是一个开放重定向。
 *
 * 另外排除 `/login` 与 `/register` 自身：`?redirect=%2Flogin` 会让登录成功后的
 * `router.push('/login')` 变成同址导航（路由不动，用户停在原地），`redirect=/register`
 * 更糟——把刚登录成功的人送进注册表单。
 *
 * @param raw 来自 `?redirect=` 的原始值（数组型 query 一律视为非法）
 * @returns 可安全跳转的站内路径，非法时回落首页
 */
export function resolveRedirect(raw: unknown): string {
  const path = typeof raw === 'string' ? raw.trim() : ''
  if (!path.startsWith('/') || path.startsWith('//') || path.startsWith('/\\')) return '/'
  const pathname = (path.split(/[?#]/)[0] ?? '').replace(/\/+$/, '') || '/'
  if (AUTH_PAGE_PATHS.includes(pathname)) return '/'

  return path
}

/**
 * 后端对外中文文案 → i18n key。
 *
 * 输入侧有两层：
 *  - service 层：`action-backend/module_action/service/guest_auth_service.py:45-57`
 *    的模块级常量，加三处内联文案；
 *  - **VO 层**：`action-backend/module_action/entity/vo/action_vo.py:488-495` 的
 *    `@Xss` / `@NotBlank` / `@Size` 文案 —— 这一层靠正常输入就能踩到（英文用户填
 *    `Dept. <Neurology>` 即命中 `@Xss`），漏掉就是英文界面直冒中文；
 *  - 限流：`utils/response_util.py:252` 的 `请求过于频繁，请稍后再试`，走的是**真
 *    HTTP 429**（不是 200 信封），必须让用户知道是限流而不是网络问题，否则他会立刻
 *    重试、把滑动窗口继续顶满。
 *
 * 按**完整字符串**匹配而不是子串匹配：子串匹配在文案互为前缀时会误命中。
 */
export const BACKEND_MESSAGE_KEYS: Readonly<Record<string, string>> = {
  // --- service 层 ---
  '邮箱或密码错误': 'auth.err.loginFailed',
  '账号已停用': 'auth.err.accountDisabled',
  '该邮箱已注册': 'auth.err.emailRegistered',
  '验证码错误或已过期': 'auth.err.codeInvalid',
  '注册失败，请稍后重试': 'auth.err.registerFailed',
  '注册未完成，请联系管理员': 'auth.err.registerCompensateFailed',
  '验证码发送失败，请稍后重试': 'auth.err.mailSendFailed',
  '服务暂时不可用，请稍后重试': 'auth.err.serviceUnavailable',
  '发送过于频繁，请稍后再试': 'auth.err.tooFrequent',
  '两次输入的密码不一致': 'auth.err.passwordMismatch',
  '请提供验证码或密码其中一项': 'auth.err.credentialRequired',
  // --- VO 层（action_vo.py:488-495）---
  '用户名不能包含脚本字符': 'auth.err.usernameXss',
  '所属机构不能包含脚本字符': 'auth.err.institutionXss',
  '职位不能包含脚本字符': 'auth.err.positionXss',
  '用户名不能为空': 'auth.err.usernameBlank',
  '用户名长度不能超过30个字符': 'auth.err.usernameTooLong',
  '所属机构长度不能超过300个字符': 'auth.err.institutionTooLong',
  '职位长度不能超过100个字符': 'auth.err.positionTooLong',
  // --- 限流（真 HTTP 429）---
  '请求过于频繁，请稍后再试': 'auth.err.rateLimited',
}

/**
 * 后缀匹配规则。
 *
 * 「密码长度不能超过72个字节」里的字段名是变量（`action_vo.py` 的
 * `f'{field_label}长度不能超过{BCRYPT_MAX_PASSWORD_BYTES}个字节'`，实参有「密码」
 * 与「确认密码」两种），完整字符串匹配不住，只能按后缀匹配这一条。
 */
export const BACKEND_MESSAGE_SUFFIXES: ReadonlyArray<readonly [string, string]> = [
  ['长度不能超过72个字节', 'auth.err.passwordTooLong'],
]

/**
 * 后端 msg → i18n key
 *
 * @param msg 后端返回的中文 msg
 * @returns 命中的 i18n key；未命中返回 `null`（调用方负责原样显示 + warn）
 */
export function backendMessageKey(msg?: string | null): string | null {
  const raw = (msg ?? '').trim()
  if (!raw) return null
  const exact = BACKEND_MESSAGE_KEYS[raw]
  if (exact) return exact
  const suffix = BACKEND_MESSAGE_SUFFIXES.find(([tail]) => raw.endsWith(tail))

  return suffix ? suffix[1] : null
}

/**
 * 倒计时余量（秒）。
 *
 * 按**截止时间戳**算而不是按 tick 自减：用户点完「获取验证码」切到邮箱 App，标签页
 * 会被浏览器后台节流（移动端可能直接冻结），回来时服务端 60 秒冷却早已结束、按钮却
 * 还显示「38 秒后重发」并保持禁用。
 *
 * @param deadline 冷却结束的时间戳（`Date.now()` 口径）；`0` 表示无冷却
 * @param now 当前时间戳
 * @returns 剩余秒数，已结束返回 0
 */
export function countdownRemaining(deadline: number, now: number = Date.now()): number {
  if (!deadline) return 0

  return Math.max(0, Math.ceil((deadline - now) / 1000))
}

/**
 * 邮箱校验
 *
 * @param email 原始输入（内部 trim）
 * @returns i18n key 或 null。长度上限必须在**提交时**再查一次：模板上的
 *   `maxlength=50` 只约束键盘输入，密码管理器自动填充能直接绕过去。
 */
export function validateEmail(email: string): string | null {
  const value = email.trim()
  if (!value) return 'auth.v.emailRequired'
  if (!EMAIL_PATTERN.test(value)) return 'auth.v.emailInvalid'
  if (codePointLength(value) > AUTH_LIMITS.email) return 'auth.v.emailTooLong'

  return null
}

/**
 * 邮箱验证码校验（6 位数字）
 *
 * @param code 原始输入
 * @returns i18n key 或 null
 */
export function validateVerifyCode(code: string): string | null {
  return CODE_PATTERN.test(code.trim()) ? null : 'auth.v.codeRequired'
}

/**
 * 注册密码校验：码点长度 + UTF-8 字节数两条独立规则
 *
 * @param password 原始密码（不 trim，空格是合法密码字符）
 * @returns i18n key 或 null
 */
export function validateNewPassword(password: string): string | null {
  const length = codePointLength(password)
  if (length < AUTH_LIMITS.passwordMin || length > AUTH_LIMITS.passwordMax) return 'auth.v.passwordLength'
  if (utf8ByteLength(password) > AUTH_LIMITS.passwordMaxBytes) return 'auth.v.passwordBytes'

  return null
}

/**
 * 自由文本字段（尖括号 + 码点长度）
 *
 * @param value 已 trim 的值
 * @param max 码点上限
 * @param tooLongKey 超长时的 i18n key
 * @param angleKey 含尖括号时的 i18n key
 * @returns i18n key 或 null
 */
function validateFreeText(value: string, max: number, tooLongKey: string, angleKey: string): string | null {
  if (hasAngleBrackets(value)) return angleKey
  if (codePointLength(value) > max) return tooLongKey

  return null
}

/** 注册表单原始输入（全部为字符串，与 `form` ref 的形状一致） */
export interface RegisterFormInput {
  email: string
  code: string
  username: string
  institution: string
  position: string
  password: string
  confirm: string
}

/**
 * 注册表单整表校验，顺序与页面字段顺序一致
 *
 * @param form 表单原始输入
 * @returns 第一条不通过规则的 i18n key；全部通过返回 null
 */
export function validateRegisterForm(form: RegisterFormInput): string | null {
  const emailError = validateEmail(form.email)
  if (emailError) return emailError
  const codeError = validateVerifyCode(form.code)
  if (codeError) return codeError

  const username = form.username.trim()
  if (!username) return 'auth.v.usernameRequired'
  const usernameError = validateFreeText(
    username, AUTH_LIMITS.username, 'auth.v.usernameTooLong', 'auth.v.usernameNoAngle',
  )
  if (usernameError) return usernameError

  const institutionError = validateFreeText(
    form.institution.trim(), AUTH_LIMITS.institution, 'auth.v.institutionTooLong', 'auth.v.institutionNoAngle',
  )
  if (institutionError) return institutionError

  const positionError = validateFreeText(
    form.position.trim(), AUTH_LIMITS.position, 'auth.v.positionTooLong', 'auth.v.positionNoAngle',
  )
  if (positionError) return positionError

  const passwordError = validateNewPassword(form.password)
  if (passwordError) return passwordError
  if (form.password !== form.confirm) return 'auth.v.passwordMismatch'

  return null
}

export type LoginMode = 'password' | 'code'

/** 登录表单原始输入 */
export interface LoginFormInput {
  email: string
  code: string
  password: string
}

/**
 * 登录表单校验。
 *
 * 登录侧**不查密码的 6–50 位规则**：老账号的密码规则可能变过，把人挡在门外没有意义；
 * 但 72 字节那条必须查——超限的密码在后端是 601 而不是「邮箱或密码错误」。
 *
 * @param mode 当前登录方式
 * @param form 表单原始输入
 * @returns 第一条不通过规则的 i18n key；全部通过返回 null
 */
export function validateLoginForm(mode: LoginMode, form: LoginFormInput): string | null {
  const emailError = validateEmail(form.email)
  if (emailError) return emailError
  if (mode === 'code') return validateVerifyCode(form.code)
  if (!form.password) return 'auth.v.passwordRequired'
  if (utf8ByteLength(form.password) > AUTH_LIMITS.passwordMaxBytes) return 'auth.v.passwordBytes'

  return null
}
