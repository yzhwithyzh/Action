import { describe, expect, it } from 'vitest'

import {
  AUTH_LIMITS,
  backendMessageKey,
  codePointLength,
  countdownRemaining,
  hasAngleBrackets,
  isHeaderSafeToken,
  resolveRedirect,
  utf8ByteLength,
  validateEmail,
  validateLoginForm,
  validateNewPassword,
  validateRegisterForm,
  validateVerifyCode,
  type RegisterFormInput,
} from '../composables/authValidation'

/** 一张合法的注册表单，各用例只覆盖自己关心的那个字段 */
const validRegisterForm = (patch: Partial<RegisterFormInput> = {}): RegisterFormInput => ({
  email: 'zhang@example.com',
  code: '123456',
  username: '张三',
  institution: '广州中医药大学',
  position: '研究员',
  password: 'secret123',
  confirm: 'secret123',
  ...patch,
})

describe('resolveRedirect', () => {
  it('放行普通站内路径', () => {
    expect(resolveRedirect('/guidelines')).toBe('/guidelines')
    expect(resolveRedirect('/news?page=2#top')).toBe('/news?page=2#top')
  })

  it('拒绝协议相对 URL —— 开放重定向', () => {
    expect(resolveRedirect('//evil.com')).toBe('/')
    expect(resolveRedirect('/\\evil.com')).toBe('/')
    expect(resolveRedirect('https://evil.com')).toBe('/')
    expect(resolveRedirect('evil.com')).toBe('/')
  })

  it('拒绝鉴权页自身 —— 同址导航会让用户停在原地，跳注册页更糟', () => {
    expect(resolveRedirect('/login')).toBe('/')
    expect(resolveRedirect('/register')).toBe('/')
    expect(resolveRedirect('/login?x=1')).toBe('/')
    expect(resolveRedirect('/register?redirect=%2Fnews')).toBe('/')
    expect(resolveRedirect('/login/')).toBe('/')
    expect(resolveRedirect('/login#top')).toBe('/')
  })

  it('不误伤只是以 /login 开头的真实路径', () => {
    expect(resolveRedirect('/login-help')).toBe('/login-help')
  })

  it('空值与数组型 query 一律回落首页', () => {
    expect(resolveRedirect(undefined)).toBe('/')
    expect(resolveRedirect(null)).toBe('/')
    expect(resolveRedirect('')).toBe('/')
    expect(resolveRedirect('   ')).toBe('/')
    expect(resolveRedirect(['/news', '/about'])).toBe('/')
    expect(resolveRedirect(42)).toBe('/')
  })

  it('两端空白先 trim', () => {
    expect(resolveRedirect('  /about  ')).toBe('/about')
  })
})

describe('backendMessageKey', () => {
  it('命中 service 层常量', () => {
    expect(backendMessageKey('邮箱或密码错误')).toBe('auth.err.loginFailed')
    expect(backendMessageKey('该邮箱已注册')).toBe('auth.err.emailRegistered')
    expect(backendMessageKey('服务暂时不可用，请稍后重试')).toBe('auth.err.serviceUnavailable')
    expect(backendMessageKey('请提供验证码或密码其中一项')).toBe('auth.err.credentialRequired')
  })

  it('命中 VO 层校验文案（action_vo.py:488-495）', () => {
    expect(backendMessageKey('用户名不能包含脚本字符')).toBe('auth.err.usernameXss')
    expect(backendMessageKey('所属机构不能包含脚本字符')).toBe('auth.err.institutionXss')
    expect(backendMessageKey('职位不能包含脚本字符')).toBe('auth.err.positionXss')
    expect(backendMessageKey('用户名不能为空')).toBe('auth.err.usernameBlank')
    expect(backendMessageKey('用户名长度不能超过30个字符')).toBe('auth.err.usernameTooLong')
    expect(backendMessageKey('所属机构长度不能超过300个字符')).toBe('auth.err.institutionTooLong')
    expect(backendMessageKey('职位长度不能超过100个字符')).toBe('auth.err.positionTooLong')
  })

  it('命中限流文案（真 HTTP 429，不能退化成「网络异常」）', () => {
    expect(backendMessageKey('请求过于频繁，请稍后再试')).toBe('auth.err.rateLimited')
  })

  it('按后缀命中 72 字节那条 —— 字段名是变量', () => {
    expect(backendMessageKey('密码长度不能超过72个字节')).toBe('auth.err.passwordTooLong')
    expect(backendMessageKey('确认密码长度不能超过72个字节')).toBe('auth.err.passwordTooLong')
  })

  it('两端空白不影响匹配', () => {
    expect(backendMessageKey('  邮箱或密码错误  ')).toBe('auth.err.loginFailed')
  })

  it('未命中返回 null，由调用方原样显示 + warn', () => {
    expect(backendMessageKey('后端新加的一句文案')).toBeNull()
    expect(backendMessageKey('')).toBeNull()
    expect(backendMessageKey(undefined)).toBeNull()
    expect(backendMessageKey(null)).toBeNull()
  })

  it('不做子串匹配 —— 前缀相同的文案不得误命中', () => {
    expect(backendMessageKey('邮箱或密码错误了')).toBeNull()
  })
})

describe('码点计数', () => {
  it('codePointLength 数码点而不是 UTF-16 码元', () => {
    expect('🔑🔑🔑'.length).toBe(6)
    expect(codePointLength('🔑🔑🔑')).toBe(3)
    expect(codePointLength('中文abc')).toBe(5)
  })

  it('utf8ByteLength 与码点是两条独立规则', () => {
    expect(utf8ByteLength('🔑🔑🔑')).toBe(12)
    expect(utf8ByteLength('中')).toBe(3)
    expect(utf8ByteLength('a')).toBe(1)
  })

  it('emoji 密码 🔑🔑🔑 只有 3 个码点 —— 应判为不足 6，不能放到后端才被 422 打回', () => {
    expect(validateNewPassword('🔑🔑🔑')).toBe('auth.v.passwordLength')
  })

  it('16 个 emoji 的用户名是 16 个码点 —— 后端算 16 会放行，前端不得按 32 拒绝', () => {
    const username = '🔑'.repeat(16)
    expect(username.length).toBe(32)
    expect(codePointLength(username)).toBe(AUTH_LIMITS.username - 14)
    expect(validateRegisterForm(validRegisterForm({ username }))).toBeNull()
  })

  it('31 个码点的用户名仍应拒绝', () => {
    expect(validateRegisterForm(validRegisterForm({ username: 'a'.repeat(31) }))).toBe('auth.v.usernameTooLong')
  })

  it('72 字节那条独立生效：25 个中文字符 = 75 字节', () => {
    const password = '密'.repeat(25)
    expect(codePointLength(password)).toBe(25)
    expect(utf8ByteLength(password)).toBe(75)
    expect(validateNewPassword(password)).toBe('auth.v.passwordBytes')
  })

  it('50 码点以内、72 字节以内的密码放行', () => {
    expect(validateNewPassword('secret123')).toBeNull()
    expect(validateNewPassword('密'.repeat(24))).toBeNull()
  })

  it('超 50 码点的密码按长度拒', () => {
    expect(validateNewPassword('a'.repeat(51))).toBe('auth.v.passwordLength')
  })
})

describe('validateEmail', () => {
  it('必填', () => {
    expect(validateEmail('')).toBe('auth.v.emailRequired')
    expect(validateEmail('   ')).toBe('auth.v.emailRequired')
  })

  it('格式', () => {
    expect(validateEmail('nope')).toBe('auth.v.emailInvalid')
    expect(validateEmail('a@b')).toBe('auth.v.emailInvalid')
    expect(validateEmail('a b@c.com')).toBe('auth.v.emailInvalid')
    expect(validateEmail('zhang@example.com')).toBeNull()
    expect(validateEmail('  zhang@example.com  ')).toBeNull()
  })

  it('长度上限在提交时也要查 —— maxlength=50 挡不住密码管理器自动填充', () => {
    const tooLong = `${'a'.repeat(45)}@example.com`
    expect(tooLong.length).toBeGreaterThan(AUTH_LIMITS.email)
    expect(validateEmail(tooLong)).toBe('auth.v.emailTooLong')
  })

  it('刚好 50 字符放行', () => {
    const exact = `${'a'.repeat(38)}@example.com`
    expect(exact.length).toBe(AUTH_LIMITS.email)
    expect(validateEmail(exact)).toBeNull()
  })
})

describe('validateVerifyCode', () => {
  it('必须是 6 位数字', () => {
    expect(validateVerifyCode('123456')).toBeNull()
    expect(validateVerifyCode(' 123456 ')).toBeNull()
    expect(validateVerifyCode('12345')).toBe('auth.v.codeRequired')
    expect(validateVerifyCode('1234567')).toBe('auth.v.codeRequired')
    expect(validateVerifyCode('12345a')).toBe('auth.v.codeRequired')
    expect(validateVerifyCode('')).toBe('auth.v.codeRequired')
  })
})

describe('尖括号拦截', () => {
  it('hasAngleBrackets 认单个尖括号', () => {
    expect(hasAngleBrackets('Dept. <Neurology>')).toBe(true)
    expect(hasAngleBrackets('a < b')).toBe(true)
    expect(hasAngleBrackets('a > b')).toBe(true)
    expect(hasAngleBrackets('Department of Neurology')).toBe(false)
  })

  it('英文用户填 Dept. <Neurology> 时前端就拦下，不让后端回一句中文', () => {
    expect(validateRegisterForm(validRegisterForm({ institution: 'Dept. <Neurology>' })))
      .toBe('auth.v.institutionNoAngle')
  })

  it('用户名与职位同样拦', () => {
    expect(validateRegisterForm(validRegisterForm({ username: '<script>' }))).toBe('auth.v.usernameNoAngle')
    expect(validateRegisterForm(validRegisterForm({ position: 'PI <acting>' }))).toBe('auth.v.positionNoAngle')
  })
})

describe('validateRegisterForm', () => {
  it('合法表单返回 null', () => {
    expect(validateRegisterForm(validRegisterForm())).toBeNull()
  })

  it('按页面字段顺序返回第一条错误', () => {
    expect(validateRegisterForm(validRegisterForm({ email: 'nope', code: 'x' }))).toBe('auth.v.emailInvalid')
    expect(validateRegisterForm(validRegisterForm({ code: 'x' }))).toBe('auth.v.codeRequired')
  })

  it('用户名纯空白视为未填', () => {
    expect(validateRegisterForm(validRegisterForm({ username: '   ' }))).toBe('auth.v.usernameRequired')
  })

  it('机构与职位是选填，空串放行', () => {
    expect(validateRegisterForm(validRegisterForm({ institution: '', position: '' }))).toBeNull()
  })

  it('两次密码不一致', () => {
    expect(validateRegisterForm(validRegisterForm({ confirm: 'other123' }))).toBe('auth.v.passwordMismatch')
  })
})

describe('validateLoginForm', () => {
  it('密码方式：邮箱 + 非空密码', () => {
    expect(validateLoginForm('password', { email: 'a@b.com', code: '', password: 'x' })).toBeNull()
    expect(validateLoginForm('password', { email: 'a@b.com', code: '', password: '' }))
      .toBe('auth.v.passwordRequired')
  })

  it('密码方式不查 6–50 位规则（老账号的密码规则可能变过），但查 72 字节', () => {
    expect(validateLoginForm('password', { email: 'a@b.com', code: '', password: 'abc' })).toBeNull()
    expect(validateLoginForm('password', { email: 'a@b.com', code: '', password: '密'.repeat(25) }))
      .toBe('auth.v.passwordBytes')
  })

  it('验证码方式只查验证码，不查密码', () => {
    expect(validateLoginForm('code', { email: 'a@b.com', code: '123456', password: '' })).toBeNull()
    expect(validateLoginForm('code', { email: 'a@b.com', code: '12', password: '' })).toBe('auth.v.codeRequired')
  })

  it('邮箱先于其余字段校验', () => {
    expect(validateLoginForm('code', { email: '', code: '123456', password: '' })).toBe('auth.v.emailRequired')
  })
})

describe('countdownRemaining', () => {
  const now = 1_700_000_000_000

  it('按时间差算，不按 tick 自减', () => {
    expect(countdownRemaining(now + 60_000, now)).toBe(60)
    expect(countdownRemaining(now + 38_400, now)).toBe(39)
  })

  it('标签页被冻结 90 秒后回来：冷却早已结束，不能还显示「38 秒后重发」', () => {
    const deadline = now + 60_000
    expect(countdownRemaining(deadline, now + 90_000)).toBe(0)
  })

  it('无冷却时返回 0', () => {
    expect(countdownRemaining(0, now)).toBe(0)
  })
})

describe('isHeaderSafeToken', () => {
  it('正常 JWT 放行', () => {
    expect(isHeaderSafeToken('eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc-_123')).toBe(true)
  })

  it('含非 Latin-1 / 空白 / 控制字符的 cookie 一律判不可用', () => {
    // 这些值会让 `new Headers()` 在 $fetch 发出请求前就抛 TypeError，
    // 若不提前识别，用户会被永久锁在站外（连登录都发不出去）
    expect(isHeaderSafeToken('中文token')).toBe(false)
    expect(isHeaderSafeToken('abc def')).toBe(false)
    expect(isHeaderSafeToken('abc\ndef')).toBe(false)
    expect(isHeaderSafeToken('')).toBe(false)
    expect(isHeaderSafeToken('tok🔑en')).toBe(false)
  })
})
