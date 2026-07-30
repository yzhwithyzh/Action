<script setup lang="ts">
/**
 * 访客登录页（密码登录 / 验证码登录两个通道，后端两种都支持）。
 *
 * 表单范式、手写校验、`.fmsg` 提示条与 422 解析一律照 `pages/collaborate.vue`；
 * 样式复制到 `.page-login` 命名空间下（含每页必带的 `.btn` 基础块）。
 */
const { t, locale } = useI18n()

// 必须是函数式：对象形式只在 setup 期求值一次，切语言后 <title> 与 description
// 还停在旧语言上
useHead(() => ({
  title: t('auth.login._title'),
  meta: [{ name: 'description', content: t('auth.login._desc') }],
}))

const route = useRoute()
const router = useRouter()
const { guest, isLoggedIn, sendCode, login } = useAuth()

/**
 * 模板上的 `maxlength` 用。它只约束键盘输入 —— 密码管理器自动填充能直接绕过去，
 * 所以真正的长度校验在 `composables/authValidation.ts` 的提交前校验里。
 */
const MAXLEN = {
  email: AUTH_LIMITS.email,
  code: AUTH_LIMITS.code,
  password: AUTH_LIMITS.passwordMax,
}
const RESEND_SECONDS = AUTH_RESEND_SECONDS

/** 与 `authValidation` 的 `LoginMode` 一致；这里就地声明，不依赖类型的自动导入 */
type LoginMode = 'password' | 'code'

const mode = ref<LoginMode>('password')
const form = ref({ email: '', code: '', password: '' })
const submitting = ref(false)
const codeSending = ref(false)
const countdown = ref(0)
const msg = ref('')
const msgOk = ref(true)

/** 冷却截止时间戳（`Date.now()` 口径），0 表示无冷却 */
let deadline = 0
let timer: ReturnType<typeof setInterval> | null = null

const stopCountdown = () => {
  if (timer) clearInterval(timer)
  timer = null
}

/** 按时间差重算剩余秒数——标签页被后台节流时 tick 会漏跳，自减法会把用户白锁在那 */
const syncCountdown = () => {
  countdown.value = countdownRemaining(deadline)
  if (countdown.value <= 0) {
    deadline = 0
    stopCountdown()
  }
}

const startCountdown = () => {
  stopCountdown()
  deadline = Date.now() + RESEND_SECONDS * 1000
  syncCountdown()
  timer = setInterval(syncCountdown, 1000)
}

// 从邮箱 App 切回来的那一刻必须重算：移动端可能把整个标签页冻结，一个 tick 都不给
onMounted(() => {
  document.addEventListener('visibilitychange', syncCountdown)
})
onBeforeUnmount(() => {
  stopCountdown()
  if (import.meta.client) document.removeEventListener('visibilitychange', syncCountdown)
})

/** 切换登录方式：邮箱保留，错误提示与另一方式的输入清空 */
const switchMode = (next: LoginMode) => {
  if (mode.value === next) return
  mode.value = next
  msg.value = ''
  if (next === 'password') form.value.code = ''
  else form.value.password = ''
}

/** 跳转目标只接受站内相对路径，防开放重定向 */
const redirectTarget = computed(() => resolveRedirect(route.query.redirect))
const registerLink = computed(() => {
  const target = redirectTarget.value

  return target === '/' ? '/register' : `/register?redirect=${encodeURIComponent(target)}`
})

const fail = (text: string) => {
  msgOk.value = false
  msg.value = text
}
/** 校验函数返回的是 i18n key，翻译在这里做 */
const failKey = (key: string) => fail(t(key))

const requestCode = async () => {
  msg.value = ''
  const emailError = validateEmail(form.value.email)
  if (emailError) {
    failKey(emailError)

    return
  }

  codeSending.value = true
  try {
    const res = await sendCode(form.value.email.trim(), 'login', locale.value)
    if (!res.ok) {
      fail(res.message)

      return
    }
    msgOk.value = true
    msg.value = t('auth.codeSent')
    startCountdown()
  } finally {
    codeSending.value = false
  }
}

const submit = async () => {
  msg.value = ''
  const error = validateLoginForm(mode.value, form.value)
  if (error) {
    failKey(error)

    return
  }
  const email = form.value.email.trim()
  const code = form.value.code.trim()
  const password = form.value.password

  submitting.value = true
  try {
    // code 与 password 必须**恰好**给一个：两个都传会被后端的 model_validator 拒
    const res = await login(mode.value === 'code' ? { email, code } : { email, password })
    if (!res.ok) {
      fail(res.message)

      return
    }
    msgOk.value = true
    msg.value = t('auth.loginOk')
    await router.push(redirectTarget.value)
  } finally {
    submitting.value = false
  }
}

useReveal()
</script>

<template>
  <div class="page-login">
    <section class="sec">
      <div class="wrap auth-wrap">
        <span class="kicker reveal">{{ t('auth.login.kicker') }}</span>
        <h2 class="title reveal">{{ t('auth.login.heading') }}</h2>
        <p class="lead reveal">{{ t('auth.login.lead') }}</p>

        <!--
          `.reveal` 只能挂在这个常驻容器上：`useReveal()` 在 onMounted 时一次性收集
          元素，水合后才出现的节点不会被观察，挂在 v-if 分支上会永远停在 opacity:0。
        -->
        <div class="reveal auth-body">
          <!-- 已登录时不重复渲染表单。静态预渲染下这一分支只可能在水合之后出现 -->
          <div v-if="isLoggedIn" class="cform signed-in">
            <div class="subh">{{ t('auth.formTitle') }}</div>
            <p class="signed-name">{{ t('auth.loggedInAs', { name: guest?.username ?? '' }) }}</p>
            <p class="signed-hint">{{ t('auth.loggedInHint') }}</p>
            <NuxtLink class="btn btn-primary" to="/">{{ t('auth.backHome') }}</NuxtLink>
          </div>

          <form v-else class="cform" novalidate @submit.prevent="submit">
            <div class="subh">{{ t('auth.formTitle') }}</div>

            <div class="frow">
              <div class="catchips" role="group" :aria-label="t('auth.tabAria')">
                <button
                  type="button" :class="{ on: mode === 'password' }" :aria-pressed="mode === 'password'"
                  @click="switchMode('password')"
                >{{ t('auth.tabPassword') }}</button>
                <button
                  type="button" :class="{ on: mode === 'code' }" :aria-pressed="mode === 'code'"
                  @click="switchMode('code')"
                >{{ t('auth.tabCode') }}</button>
              </div>
            </div>

            <div class="frow">
              <label for="lg-email" v-html="t('auth.lblEmail')"></label>
              <input
                id="lg-email" v-model="form.email" class="inp" type="email" autocomplete="email"
                :placeholder="t('auth.phEmail')" :maxlength="MAXLEN.email" required
              />
            </div>

            <div v-if="mode === 'password'" class="frow" style="margin-bottom:14px">
              <label for="lg-password" v-html="t('auth.lblPassword')"></label>
              <input
                id="lg-password" v-model="form.password" class="inp" type="password" autocomplete="current-password"
                :placeholder="t('auth.phPassword')" :maxlength="MAXLEN.password" required
              />
            </div>

            <div v-else class="frow" style="margin-bottom:14px">
              <label for="lg-code" v-html="t('auth.lblCode')"></label>
              <div class="code-row">
                <input
                  id="lg-code" v-model="form.code" class="inp" inputmode="numeric" autocomplete="one-time-code"
                  :placeholder="t('auth.phCode')" :maxlength="MAXLEN.code" required
                />
                <button
                  type="button" class="btn btn-ghost" :disabled="codeSending || countdown > 0"
                  @click="requestCode"
                >{{ countdown > 0 ? t('auth.resendIn', { n: countdown }) : (codeSending ? t('auth.sendingCode') : t('auth.sendCode')) }}</button>
              </div>
            </div>

            <div class="cform-foot">
              <span class="fn">{{ t('auth.note') }}</span>
              <button type="submit" class="btn btn-primary" :disabled="submitting">
                {{ submitting ? t('auth.submitting') : t('auth.submitLogin') }}
              </button>
            </div>
          </form>

          <!--
            提示条必须在 v-if/v-else **之外**：登录成功那一刻 `isLoggedIn` 变 true，
            整个 <form> 被替换掉，写在表单里的「登录成功，正在返回…」一帧都不会出现。
            `role="alert"` 让屏幕阅读器读出结果——这条提示原本对读屏用户完全静默。
          -->
          <div
            class="fmsg" :class="{ show: !!msg }" role="alert"
            :style="msgOk ? undefined : { color: 'var(--cinnabar)', background: 'rgba(192,54,44,.08)', borderColor: '#e7b0aa' }"
          >
            <span>{{ msg }}</span>
          </div>

          <p v-if="!isLoggedIn" class="auth-alt">
            <NuxtLink :to="registerLink"><span class="rich" v-html="t('auth.toRegister')"></span></NuxtLink>
          </p>
        </div>
      </div>
    </section>
  </div>
</template>

<style>
.page-login .sec{padding:clamp(44px,6vw,80px) 0;scroll-margin-top:130px}
.page-login .auth-wrap{max-width:640px}
.page-login h2.title{font-size:clamp(1.65rem,3.2vw,2.35rem);color:var(--indigo-900);letter-spacing:-.02em;text-wrap:balance;max-width:26ch}
.page-login .lead{color:var(--muted);font-size:clamp(1rem,1.4vw,1.14rem);max-width:68ch;margin-top:16px;text-wrap:pretty}
.page-login .btn{display:inline-flex;align-items:center;justify-content:center;gap:9px;padding:13px 24px;border-radius:999px;font-weight:600;font-size:15px;border:1.5px solid transparent;cursor:pointer;white-space:nowrap;transition:transform .25s var(--ease),background-color .25s var(--ease),box-shadow .25s var(--ease),border-color .25s var(--ease)}
.page-login .btn:disabled{opacity:.55;cursor:not-allowed;transform:none;box-shadow:none}
.page-login .auth-body{margin-top:clamp(26px,3.5vw,38px)}
.page-login .cform{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-lg);padding:clamp(20px,3vw,30px)}
.page-login .subh{font-size:12.5px;font-weight:700;color:var(--indigo-900);text-transform:uppercase;letter-spacing:.03em;margin-bottom:14px;font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-login .frow{margin-bottom:16px}
.page-login .frow label{display:block;font-size:12.5px;font-weight:700;color:var(--indigo-800);margin-bottom:7px}
.page-login .frow label .rq{color:var(--cinnabar)}
.page-login .catchips{display:flex;flex-wrap:wrap;gap:8px}
.page-login .catchips button{font-family:inherit;font-size:13px;font-weight:600;color:var(--indigo-700);background:var(--surface);border:1.5px solid var(--line);border-radius:999px;padding:8px 14px;cursor:pointer;transition:.18s}
.page-login .catchips button:hover{border-color:var(--indigo-300);background:var(--indigo-100)}
.page-login .catchips button.on{background:var(--indigo-700);border-color:var(--indigo-700);color:#fff}
.page-login .inp{width:100%;border:1.5px solid var(--line);border-radius:10px;padding:11px 13px;font-family:inherit;font-size:14px;color:var(--ink);background:var(--paper)}
.page-login .inp:focus{outline:none;border-color:var(--indigo-500);box-shadow:0 0 0 4px var(--indigo-100);background:var(--surface)}
.page-login .inp::placeholder{color:#8895a8}
.page-login .code-row{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center}
.page-login .code-row .btn{padding:11px 18px;font-size:14px;min-width:9.5em}
.page-login .cform-foot{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;margin-top:6px}
.page-login .cform-foot .fn{font-size:12px;color:var(--muted);max-width:42ch;line-height:1.5}
.page-login .fmsg{display:none;align-items:center;gap:9px;font-size:13px;font-weight:600;color:var(--info);background:var(--info-bg);border:1px solid #bcd4f0;border-radius:10px;padding:10px 14px;margin-top:14px}
.page-login .fmsg.show{display:flex}
.page-login .signed-in .signed-name{font-family:"Spectral","Noto Serif SC",serif;font-size:1.24rem;font-weight:600;color:var(--indigo-900)}
.page-login .signed-in .signed-hint{font-size:13px;color:var(--muted);margin:6px 0 18px}
.page-login .auth-alt{margin-top:18px;text-align:center;font-size:13.5px;color:var(--muted)}
.page-login .auth-alt b{color:var(--indigo-700);font-weight:700}
.page-login .auth-alt a:hover b{color:var(--cinnabar)}
@media(max-width:640px){
.page-login .code-row{grid-template-columns:1fr}
.page-login .code-row .btn{width:100%}
}
</style>
