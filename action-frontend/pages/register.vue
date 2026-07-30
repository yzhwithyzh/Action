<script setup lang="ts">
/**
 * 访客注册页。
 *
 * 表单范式、手写校验、`.fmsg` 提示条与 422 解析一律照 `pages/collaborate.vue`；
 * 样式复制到 `.page-register` 命名空间下（含每页必带的 `.btn` 基础块 —— 本仓没有
 * 全局 `.btn` 基础规则，见 `assets/css/base.css`）。
 */
const { t, locale } = useI18n()

// 必须是函数式：对象形式只在 setup 期求值一次，切语言后 <title> 与 description
// 还停在旧语言上
useHead(() => ({
  title: t('auth.register._title'),
  meta: [{ name: 'description', content: t('auth.register._desc') }],
}))

const route = useRoute()
const router = useRouter()
const { guest, isLoggedIn, sendCode, register } = useAuth()

/**
 * 模板上的 `maxlength` 用。它只约束键盘输入 —— 密码管理器自动填充能直接绕过去，
 * 所以真正的长度校验在 `composables/authValidation.ts` 的提交前校验里。
 */
const MAXLEN = {
  email: AUTH_LIMITS.email,
  code: AUTH_LIMITS.code,
  username: AUTH_LIMITS.username,
  institution: AUTH_LIMITS.institution,
  position: AUTH_LIMITS.position,
  password: AUTH_LIMITS.passwordMax,
}
const RESEND_SECONDS = AUTH_RESEND_SECONDS

const form = ref({ email: '', code: '', username: '', institution: '', position: '', password: '', confirm: '' })
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

/** 跳转目标只接受站内相对路径，防开放重定向 */
const redirectTarget = computed(() => resolveRedirect(route.query.redirect))
const loginLink = computed(() => {
  const target = redirectTarget.value

  return target === '/' ? '/login' : `/login?redirect=${encodeURIComponent(target)}`
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
    const res = await sendCode(form.value.email.trim(), 'register', locale.value)
    if (!res.ok) {
      fail(res.message)

      return
    }
    msgOk.value = true
    msg.value = t('auth.codeSent')
    // 只有真的发出去了才开始倒计时，否则用户被自己的倒计时锁住却什么都没收到
    startCountdown()
  } finally {
    codeSending.value = false
  }
}

const submit = async () => {
  msg.value = ''
  // 整表校验（邮箱格式与长度、验证码、尖括号、码点长度、密码字节数、两次一致）
  // 全在 `composables/authValidation.ts` 里，登录页共用同一套规则
  const error = validateRegisterForm(form.value)
  if (error) {
    failKey(error)

    return
  }
  const email = form.value.email.trim()
  const username = form.value.username.trim()
  const institution = form.value.institution.trim()
  const position = form.value.position.trim()
  const { password, confirm } = form.value

  submitting.value = true
  try {
    const res = await register({
      email,
      code: form.value.code.trim(),
      username,
      institution: institution || null,
      position: position || null,
      password,
      confirmPassword: confirm,
    })
    if (!res.ok) {
      fail(res.message)

      return
    }
    msgOk.value = true
    msg.value = t('auth.registerOk')
    await router.push(redirectTarget.value)
  } finally {
    submitting.value = false
  }
}

useReveal()
</script>

<template>
  <div class="page-register">
    <section class="sec">
      <div class="wrap auth-wrap">
        <span class="kicker reveal">{{ t('auth.register.kicker') }}</span>
        <h2 class="title reveal">{{ t('auth.register.heading') }}</h2>
        <p class="lead reveal">{{ t('auth.register.lead') }}</p>

        <!--
          `.reveal` 只能挂在这个常驻容器上：`useReveal()` 在 onMounted 时一次性收集
          元素，水合后才出现的节点不会被观察，挂在 v-if 分支上会永远停在 opacity:0。
        -->
        <div class="reveal auth-body">
          <!--
            已登录时不渲染注册表单（与 login.vue 同款守卫）。缺这条时，已登录用户从
            书签进来看到的是一张空表，用另一个邮箱注册成功后 `applyAuth` 会静默覆盖
            原 token —— 原账号在本浏览器里无声消失，且旧会话从未走过 logout。
          -->
          <div v-if="isLoggedIn" class="cform signed-in">
            <div class="subh">{{ t('auth.formTitle') }}</div>
            <p class="signed-name">{{ t('auth.loggedInAs', { name: guest?.username ?? '' }) }}</p>
            <p class="signed-hint">{{ t('auth.registeredHint') }}</p>
            <NuxtLink class="btn btn-primary" to="/">{{ t('auth.backHome') }}</NuxtLink>
          </div>

          <form v-else class="cform" novalidate @submit.prevent="submit">
            <div class="subh">{{ t('auth.formTitle') }}</div>

            <div class="frow">
              <label for="rg-email" v-html="t('auth.lblEmail')"></label>
              <input
                id="rg-email" v-model="form.email" class="inp" type="email" autocomplete="email"
                :placeholder="t('auth.phEmail')" :maxlength="MAXLEN.email" required
              />
            </div>

            <div class="frow">
              <label for="rg-code" v-html="t('auth.lblCode')"></label>
              <div class="code-row">
                <input
                  id="rg-code" v-model="form.code" class="inp" inputmode="numeric" autocomplete="one-time-code"
                  :placeholder="t('auth.phCode')" :maxlength="MAXLEN.code" required
                />
                <button
                  type="button" class="btn btn-ghost" :disabled="codeSending || countdown > 0"
                  @click="requestCode"
                >{{ countdown > 0 ? t('auth.resendIn', { n: countdown }) : (codeSending ? t('auth.sendingCode') : t('auth.sendCode')) }}</button>
              </div>
            </div>

            <div class="frow two-col">
              <div>
                <label for="rg-username" v-html="t('auth.lblUsername')"></label>
                <input
                  id="rg-username" v-model="form.username" class="inp" autocomplete="nickname"
                  :placeholder="t('auth.phUsername')" :maxlength="MAXLEN.username" required
                />
              </div>
              <div>
                <label for="rg-institution">{{ t('auth.lblInstitution') }}</label>
                <input
                  id="rg-institution" v-model="form.institution" class="inp" autocomplete="organization"
                  :placeholder="t('auth.phInstitution')" :maxlength="MAXLEN.institution"
                />
              </div>
            </div>

            <div class="frow">
              <label for="rg-position">{{ t('auth.lblPosition') }}</label>
              <input
                id="rg-position" v-model="form.position" class="inp" autocomplete="organization-title"
                :placeholder="t('auth.phPosition')" :maxlength="MAXLEN.position"
              />
            </div>

            <div class="frow two-col" style="margin-bottom:14px">
              <div>
                <label for="rg-password" v-html="t('auth.lblPassword')"></label>
                <input
                  id="rg-password" v-model="form.password" class="inp" type="password" autocomplete="new-password"
                  :placeholder="t('auth.phPassword')" :maxlength="MAXLEN.password" required
                />
              </div>
              <div>
                <label for="rg-confirm" v-html="t('auth.lblConfirmPassword')"></label>
                <input
                  id="rg-confirm" v-model="form.confirm" class="inp" type="password" autocomplete="new-password"
                  :placeholder="t('auth.phConfirmPassword')" :maxlength="MAXLEN.password" required
                />
              </div>
            </div>

            <div class="cform-foot">
              <span class="fn">{{ t('auth.note') }}</span>
              <button type="submit" class="btn btn-primary" :disabled="submitting">
                {{ submitting ? t('auth.submitting') : t('auth.submitRegister') }}
              </button>
            </div>
          </form>

          <!--
            提示条必须在 v-if/v-else **之外**：注册成功那一刻 `isLoggedIn` 变 true，
            整个 <form> 被替换掉，写在表单里的「注册成功，正在返回…」一帧都不会出现。
            `role="alert"` 让屏幕阅读器读出结果——这条提示原本对读屏用户完全静默。
          -->
          <div
            class="fmsg" :class="{ show: !!msg }" role="alert"
            :style="msgOk ? undefined : { color: 'var(--cinnabar)', background: 'rgba(192,54,44,.08)', borderColor: '#e7b0aa' }"
          >
            <span>{{ msg }}</span>
          </div>

          <p v-if="!isLoggedIn" class="auth-alt">
            <NuxtLink :to="loginLink"><span class="rich" v-html="t('auth.toLogin')"></span></NuxtLink>
          </p>
        </div>
      </div>
    </section>
  </div>
</template>

<style>
.page-register .sec{padding:clamp(44px,6vw,80px) 0;scroll-margin-top:130px}
.page-register .auth-wrap{max-width:760px}
.page-register h2.title{font-size:clamp(1.65rem,3.2vw,2.35rem);color:var(--indigo-900);letter-spacing:-.02em;text-wrap:balance;max-width:26ch}
.page-register .lead{color:var(--muted);font-size:clamp(1rem,1.4vw,1.14rem);max-width:68ch;margin-top:16px;text-wrap:pretty}
.page-register .btn{display:inline-flex;align-items:center;justify-content:center;gap:9px;padding:13px 24px;border-radius:999px;font-weight:600;font-size:15px;border:1.5px solid transparent;cursor:pointer;white-space:nowrap;transition:transform .25s var(--ease),background-color .25s var(--ease),box-shadow .25s var(--ease),border-color .25s var(--ease)}
.page-register .btn:disabled{opacity:.55;cursor:not-allowed;transform:none;box-shadow:none}
.page-register .auth-body{margin-top:clamp(26px,3.5vw,38px)}
.page-register .cform{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-lg);padding:clamp(20px,3vw,30px)}
.page-register .subh{font-size:12.5px;font-weight:700;color:var(--indigo-900);text-transform:uppercase;letter-spacing:.03em;margin-bottom:14px;font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-register .frow{margin-bottom:16px}
.page-register .frow.two-col{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.page-register .frow label{display:block;font-size:12.5px;font-weight:700;color:var(--indigo-800);margin-bottom:7px}
.page-register .frow label .rq{color:var(--cinnabar)}
.page-register .inp{width:100%;border:1.5px solid var(--line);border-radius:10px;padding:11px 13px;font-family:inherit;font-size:14px;color:var(--ink);background:var(--paper)}
.page-register .inp:focus{outline:none;border-color:var(--indigo-500);box-shadow:0 0 0 4px var(--indigo-100);background:var(--surface)}
.page-register .inp::placeholder{color:#8895a8}
.page-register .code-row{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center}
.page-register .code-row .btn{padding:11px 18px;font-size:14px;min-width:9.5em}
.page-register .cform-foot{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;margin-top:6px}
.page-register .cform-foot .fn{font-size:12px;color:var(--muted);max-width:42ch;line-height:1.5}
.page-register .fmsg{display:none;align-items:center;gap:9px;font-size:13px;font-weight:600;color:var(--info);background:var(--info-bg);border:1px solid #bcd4f0;border-radius:10px;padding:10px 14px;margin-top:14px}
.page-register .fmsg.show{display:flex}
.page-register .signed-in .signed-name{font-family:"Spectral","Noto Serif SC",serif;font-size:1.24rem;font-weight:600;color:var(--indigo-900)}
.page-register .signed-in .signed-hint{font-size:13px;color:var(--muted);margin:6px 0 18px}
.page-register .auth-alt{margin-top:18px;text-align:center;font-size:13.5px;color:var(--muted)}
.page-register .auth-alt b{color:var(--indigo-700);font-weight:700}
.page-register .auth-alt a:hover b{color:var(--cinnabar)}
@media(max-width:640px){
.page-register .frow.two-col{grid-template-columns:1fr}
.page-register .code-row{grid-template-columns:1fr}
.page-register .code-row .btn{width:100%}
}
</style>
