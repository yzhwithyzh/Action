<script setup lang="ts">
/**
 * 找回密码：邮箱验证码 + 新密码，成功后直接登录（后端签发新令牌）。
 *
 * 版式与 `pages/login.vue` 同一套（表单卡片、`.fmsg` 提示条、验证码倒计时），
 * 样式复制到 `.page-forgot` 命名空间下 —— 本仓没有全局 `.btn` 基础规则，每页自带。
 *
 * 防枚举在后端：没注册过的邮箱「获取验证码」也报已发送，只是收不到信。
 * 所以这页的提示语要把这种情况说出来（`auth.forgot.codeHint`），
 * 不然用户会以为是邮件延迟，守着一封永远不来的信。
 */
const { t, locale } = useI18n()

useHead(() => ({
  title: t('auth.forgot._title'),
  meta: [{ name: 'description', content: t('auth.forgot._desc') }],
}))

const route = useRoute()
const router = useRouter()
const { sendCode, resetPassword } = useAuth()

const MAXLEN = {
  email: AUTH_LIMITS.email,
  code: AUTH_LIMITS.code,
  password: AUTH_LIMITS.passwordMax,
}

const form = ref({ email: '', code: '', password: '', confirm: '' })
const submitting = ref(false)
const codeSending = ref(false)
const countdown = ref(0)
const msg = ref('')
const msgOk = ref(true)
/** 重设成功后锁住表单：此时已经登录、正在跳走，再点一次只会撞「验证码已失效」 */
const done = ref(false)

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
  deadline = Date.now() + AUTH_RESEND_SECONDS * 1000
  syncCountdown()
  timer = setInterval(syncCountdown, 1000)
}

onMounted(() => {
  document.addEventListener('visibilitychange', syncCountdown)
})
onBeforeUnmount(() => {
  stopCountdown()
  if (import.meta.client) document.removeEventListener('visibilitychange', syncCountdown)
})

const redirectTarget = computed(() => resolveRedirect(route.query.redirect))
const loginLink = computed(() => {
  const target = redirectTarget.value

  return target === '/' ? '/login' : `/login?redirect=${encodeURIComponent(target)}`
})

const fail = (text: string) => {
  msgOk.value = false
  msg.value = text
}
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
    const res = await sendCode(form.value.email.trim(), 'reset', locale.value)
    if (!res.ok) {
      fail(res.message)

      return
    }
    msgOk.value = true
    msg.value = t('auth.forgot.codeHint')
    startCountdown()
  } finally {
    codeSending.value = false
  }
}

const submit = async () => {
  msg.value = ''
  const error = validateResetForm(form.value)
  if (error) {
    failKey(error)

    return
  }

  submitting.value = true
  try {
    const res = await resetPassword({
      email: form.value.email.trim(),
      code: form.value.code.trim(),
      password: form.value.password,
      confirmPassword: form.value.confirm,
    })
    if (!res.ok) {
      fail(res.message)

      return
    }
    done.value = true
    msgOk.value = true
    msg.value = t('auth.forgot.ok')
    await router.push(redirectTarget.value)
  } finally {
    submitting.value = false
  }
}

useReveal()
</script>

<template>
  <div class="page-forgot">
    <section class="sec">
      <div class="wrap auth-wrap">
        <span class="kicker reveal">{{ t('auth.login.kicker') }}</span>
        <h2 class="title reveal">{{ t('auth.forgot.heading') }}</h2>
        <p class="lead reveal">{{ t('auth.forgot.lead') }}</p>

        <!-- `.reveal` 只挂常驻容器：useReveal 在挂载时收集，v-if 分支上的会停在 opacity:0 -->
        <div class="reveal auth-body">
          <form class="cform" novalidate @submit.prevent="submit">
            <div class="subh">{{ t('auth.forgot.formTitle') }}</div>

            <div class="frow">
              <label for="fp-email" v-html="t('auth.lblEmail')"></label>
              <input
                id="fp-email" v-model="form.email" class="inp" type="email" autocomplete="email"
                :placeholder="t('auth.phEmail')" :maxlength="MAXLEN.email" :disabled="done" required
              />
            </div>

            <div class="frow">
              <label for="fp-code" v-html="t('auth.lblCode')"></label>
              <div class="code-row">
                <input
                  id="fp-code" v-model="form.code" class="inp" inputmode="numeric" autocomplete="one-time-code"
                  :placeholder="t('auth.phCode')" :maxlength="MAXLEN.code" :disabled="done" required
                />
                <button
                  type="button" class="btn btn-ghost" :disabled="done || codeSending || countdown > 0"
                  @click="requestCode"
                >{{ countdown > 0 ? t('auth.resendIn', { n: countdown }) : (codeSending ? t('auth.sendingCode') : t('auth.sendCode')) }}</button>
              </div>
            </div>

            <div class="frow">
              <label for="fp-password" v-html="t('auth.forgot.lblNewPassword')"></label>
              <input
                id="fp-password" v-model="form.password" class="inp" type="password" autocomplete="new-password"
                :placeholder="t('auth.phPassword')" :maxlength="MAXLEN.password" :disabled="done" required
              />
            </div>

            <div class="frow" style="margin-bottom:14px">
              <label for="fp-confirm" v-html="t('auth.lblConfirmPassword')"></label>
              <input
                id="fp-confirm" v-model="form.confirm" class="inp" type="password" autocomplete="new-password"
                :placeholder="t('auth.phConfirmPassword')" :maxlength="MAXLEN.password" :disabled="done" required
              />
            </div>

            <div class="cform-foot">
              <span class="fn">{{ t('auth.forgot.note') }}</span>
              <button type="submit" class="btn btn-primary" :disabled="submitting || done">
                {{ submitting ? t('auth.submitting') : t('auth.forgot.submit') }}
              </button>
            </div>
          </form>

          <div
            class="fmsg" :class="{ show: !!msg }" role="alert"
            :style="msgOk ? undefined : { color: 'var(--cinnabar)', background: 'rgba(192,54,44,.08)', borderColor: '#e7b0aa' }"
          >
            <span>{{ msg }}</span>
          </div>

          <p class="auth-alt">
            <NuxtLink :to="loginLink"><span class="rich" v-html="t('auth.forgot.toLogin')"></span></NuxtLink>
          </p>
        </div>
      </div>
    </section>
  </div>
</template>

<style>
.page-forgot .sec{padding:clamp(44px,6vw,80px) 0;scroll-margin-top:130px}
.page-forgot .auth-wrap{max-width:640px}
.page-forgot h2.title{font-size:clamp(1.65rem,3.2vw,2.35rem);color:var(--indigo-900);letter-spacing:-.02em;text-wrap:balance;max-width:26ch}
.page-forgot .lead{color:var(--muted);font-size:clamp(1rem,1.4vw,1.14rem);max-width:68ch;margin-top:16px;text-wrap:pretty}
.page-forgot .btn{display:inline-flex;align-items:center;justify-content:center;gap:9px;padding:13px 24px;border-radius:999px;font-weight:600;font-size:15px;border:1.5px solid transparent;cursor:pointer;white-space:nowrap;transition:transform .25s var(--ease),background-color .25s var(--ease),box-shadow .25s var(--ease),border-color .25s var(--ease)}
.page-forgot .btn:disabled{opacity:.55;cursor:not-allowed;transform:none;box-shadow:none}
.page-forgot .auth-body{margin-top:clamp(26px,3.5vw,38px)}
.page-forgot .cform{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-lg);padding:clamp(20px,3vw,30px)}
.page-forgot .subh{font-size:12.5px;font-weight:700;color:var(--indigo-900);text-transform:uppercase;letter-spacing:.03em;margin-bottom:14px;font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-forgot .frow{margin-bottom:16px}
.page-forgot .frow label{display:block;font-size:12.5px;font-weight:700;color:var(--indigo-800);margin-bottom:7px}
.page-forgot .frow label .rq{color:var(--cinnabar)}
.page-forgot .inp{width:100%;border:1.5px solid var(--line);border-radius:10px;padding:11px 13px;font-family:inherit;font-size:14px;color:var(--ink);background:var(--paper)}
.page-forgot .inp:focus{outline:none;border-color:var(--indigo-500);box-shadow:0 0 0 4px var(--indigo-100);background:var(--surface)}
.page-forgot .inp::placeholder{color:#8895a8}
.page-forgot .inp:disabled{opacity:.6}
.page-forgot .code-row{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center}
.page-forgot .code-row .btn{padding:11px 18px;font-size:14px;min-width:9.5em}
.page-forgot .cform-foot{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;margin-top:6px}
.page-forgot .cform-foot .fn{font-size:12px;color:var(--muted);max-width:42ch;line-height:1.5}
.page-forgot .fmsg{display:none;align-items:center;gap:9px;font-size:13px;font-weight:600;color:var(--info);background:var(--info-bg);border:1px solid #bcd4f0;border-radius:10px;padding:10px 14px;margin-top:14px}
.page-forgot .fmsg.show{display:flex}
.page-forgot .auth-alt{margin-top:18px;text-align:center;font-size:13.5px;color:var(--muted)}
.page-forgot .auth-alt b{color:var(--indigo-700);font-weight:700}
.page-forgot .auth-alt a:hover b{color:var(--cinnabar)}
@media(max-width:640px){
.page-forgot .code-row{grid-template-columns:1fr}
.page-forgot .code-row .btn{width:100%}
}
</style>
