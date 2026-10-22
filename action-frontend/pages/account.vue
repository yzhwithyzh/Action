<script setup lang="ts">
/**
 * 我的账号：「我的工作」汇总 + 资料与密码。
 *
 * 访客登录是为了把东西存下来（报告草稿、SRD 评估），而这些原本分散在各自的工具页里，
 * 想找回上个月那份草稿得先记得它在哪个工具里。这页只做**汇总与跳转**，不做第二套编辑器：
 * 点「继续撰写」带着 `?draft=` 回报告助手、点「查看结果」带着 `?assessment=` 回 SRD 页，
 * 由那两页自己打开那一份。
 *
 * 全站预渲染：构建期永远是未登录那一版，登录态与数据只能挂载后取（`onNuxtReady`），
 * 所以页面主体都挂在 `isLoggedIn` 后面。表单与列表的样式照 `login.vue` 的 `.cform`
 * 与 `srd.vue` 的历史行，复制在 `.page-account` 命名空间下。
 */
const { t } = useI18n()
const { pick, isEn } = useBilingual()

useHead(() => ({
  title: t('account._title'),
  meta: [{ name: 'description', content: t('account._desc') }],
}))

const { guest, isLoggedIn, authedCall, updateProfile, changePassword, logout } = useAuth()
const router = useRouter()

const loginLink = '/login?redirect=%2Faccount'

// ---------------------------------------------------------------- 我的工作

interface DraftRow {
  draftId: number
  guidelineCode: string
  studyTypeKey: string
  title: string
  itemTotal: number
  filledCount: number
  requiredTotal: number
  requiredFilled: number
  updateTime: string | null
}

interface SrdRow {
  assessmentId: number
  runStatus: string | null
  progress: number | null
  errorMsg: string | null
  overallLevel: string | null
  overallPct: number | null
  overallScoreSum: number | null
  overallScoreMax: number | null
  createTime: string | null
  [key: string]: unknown
}

const drafts = ref<DraftRow[]>([])
const srdRuns = ref<SrdRow[]>([])
const workLoading = ref(false)
const workErr = ref('')

async function loadWork() {
  if (!isLoggedIn.value) {
    drafts.value = []
    srdRuns.value = []

    return
  }
  workLoading.value = true
  workErr.value = ''
  const [d, s] = await Promise.all([
    authedCall('/report-drafts', 'GET'),
    authedCall('/srd/assessments', 'GET'),
  ])
  workLoading.value = false
  drafts.value = d.ok ? ((d.envelope?.data ?? []) as DraftRow[]) : []
  srdRuns.value = s.ok ? ((s.envelope?.data ?? []) as SrdRow[]) : []
  // 一边失败另一边照常显示；只报第一条错误，免得同一句「网络异常」出现两遍
  if (!d.ok || !s.ok) workErr.value = (!d.ok ? d.message : s.message) || t('auth.err.unknown')
}

/** 报告助手按 `type` 反查问卷路径、`step=2` 直接进撰写、`draft` 打开这一份（见 assistant.vue） */
const draftLink = (row: DraftRow) => {
  const q = new URLSearchParams({ step: '2', draft: String(row.draftId) })
  if (row.studyTypeKey) q.set('type', row.studyTypeKey)

  return `/assistant?${q.toString()}`
}
const draftPct = (row: DraftRow) =>
  (row.requiredTotal ? Math.round((row.requiredFilled / row.requiredTotal) * 100) : 0)

/** 跑完的直接打开结果；没跑完的去 SRD 页的历史区看进度（那边会接回轮询） */
const srdLink = (row: SrdRow) =>
  (row.runStatus === 'completed' ? `/srd?assessment=${row.assessmentId}` : '/srd#history')

/** 与 srd.vue 同一套：`level` 为 null 是「无法判定」，不兜进四档里任何一档 */
const LV_CLASS: Record<string, string> = { none: 'lvl-none', low: 'lvl-low', mod: 'lvl-mod', high: 'lvl-high' }
const LV_LABEL: Record<string, string> = {
  none: 'srd.lvlNone',
  low: 'srd.lvlLow',
  mod: 'srd.lvlMod',
  high: 'srd.lvlHigh',
}
const lvClass = (l: string | null) => (l && LV_CLASS[l]) || 'lvl-unknown'
const lvLabel = (l: string | null) => t((l && LV_LABEL[l]) || 'srd.lvlUnknown')
const SRD_STATUS_KEY: Record<string, string> = {
  pending: 'srd.stQueued',
  running: 'srd.stRunning',
  failed: 'srd.stFailed',
  stopped: 'srd.stStopped',
}

const stamp = (iso: string | null) => {
  if (!iso) return { date: '', time: '' }
  const d = new Date(iso.replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return { date: iso, time: '' }
  const loc = isEn.value ? 'en-GB' : 'zh-CN'

  return {
    date: d.toLocaleDateString(loc),
    time: d.toLocaleTimeString(loc, { hour: '2-digit', minute: '2-digit', hour12: false }),
  }
}

// 登录态是水合之后才知道的：挂 onNuxtReady 取一次，登录态变化（顶栏 fetchMe 回来、退出）再取
onNuxtReady(() => void loadWork())
watch(isLoggedIn, () => void loadWork())

// ---------------------------------------------------------------- 资料

const MAXLEN = {
  username: AUTH_LIMITS.username,
  institution: AUTH_LIMITS.institution,
  position: AUTH_LIMITS.position,
  password: AUTH_LIMITS.passwordMax,
}

const profile = ref({ username: '', institution: '', position: '' })
const profileBusy = ref(false)
const profileMsg = ref('')
const profileOk = ref(true)

// 访客信息到了（或保存后被刷新）就灌进表单。保存前改了一半的不会被冲掉：
// guest 只在 fetchMe 与保存成功时变，前者发生在页面刚挂载、还没来得及输入的时候
watch(guest, (g) => {
  profile.value = { username: g?.username ?? '', institution: g?.institution ?? '', position: g?.position ?? '' }
}, { immediate: true })

const profileDirty = computed(() => {
  const g = guest.value
  if (!g) return false
  const p = profile.value

  return p.username.trim() !== (g.username ?? '')
    || p.institution.trim() !== (g.institution ?? '')
    || p.position.trim() !== (g.position ?? '')
})

async function saveProfile() {
  profileMsg.value = ''
  const error = validateProfileForm(profile.value)
  if (error) {
    profileOk.value = false
    profileMsg.value = t(error)

    return
  }
  profileBusy.value = true
  const res = await updateProfile({
    username: profile.value.username.trim(),
    institution: profile.value.institution.trim() || null,
    position: profile.value.position.trim() || null,
  })
  profileBusy.value = false
  profileOk.value = res.ok
  profileMsg.value = res.ok ? t('account.profileSaved') : res.message
}

// ---------------------------------------------------------------- 密码

const pwd = ref({ old: '', password: '', confirm: '' })
const pwdBusy = ref(false)
const pwdMsg = ref('')
const pwdOk = ref(true)

async function savePassword() {
  pwdMsg.value = ''
  const error = validatePasswordChangeForm(pwd.value)
  if (error) {
    pwdOk.value = false
    pwdMsg.value = t(error)

    return
  }
  pwdBusy.value = true
  const res = await changePassword({
    oldPassword: pwd.value.old,
    password: pwd.value.password,
    confirmPassword: pwd.value.confirm,
  })
  pwdBusy.value = false
  pwdOk.value = res.ok
  if (!res.ok) {
    pwdMsg.value = res.message

    return
  }
  pwd.value = { old: '', password: '', confirm: '' }
  pwdMsg.value = t('account.pwdSaved')
}

async function onLogout() {
  await logout()
  await router.push('/')
}

useReveal()
</script>

<template>
  <div class="page-account">
    <section class="sec">
      <div class="wrap">
        <div class="acc-head">
          <div>
            <span class="kicker reveal">{{ t('account.kicker') }}</span>
            <!--
              预渲染出来的永远是未登录那版标题；登录后换成用户名属于文本变化，
              hydration 会就地修文本，不存在 class 不匹配的问题
            -->
            <h2 class="title reveal">{{ isLoggedIn ? guest?.username : t('account.heading') }}</h2>
            <p class="lead reveal">
              <template v-if="isLoggedIn">
                {{ guest?.email }}<template v-if="guest?.institution"> · {{ guest.institution }}</template><template v-if="guest?.position"> · {{ guest.position }}</template>
              </template>
              <template v-else>{{ t('account.lead') }}</template>
            </p>
          </div>
          <ClientOnly>
            <button v-if="isLoggedIn" type="button" class="btn btn-ghost btn-sm" @click="onLogout">{{ t('nav.logout') }}</button>
          </ClientOnly>
        </div>

        <!-- `.reveal` 只挂常驻容器：v-if 分支上的会永远停在 opacity:0 -->
        <div class="reveal acc-body">
          <div v-if="!isLoggedIn" class="acc-empty">
            {{ t('account.needLogin') }}
            <NuxtLink :to="loginLink">{{ t('nav.login') }}</NuxtLink>
          </div>

          <template v-else>
            <!-- ===================== 我的工作 ===================== -->
            <div class="blk">
              <div class="blk-head">
                <h3>{{ t('account.draftsTitle') }} <span class="cnt">{{ drafts.length }}</span></h3>
                <NuxtLink class="blk-more" to="/assistant">{{ t('account.toAssistant') }}</NuxtLink>
              </div>
              <div v-if="!drafts.length" class="acc-empty sm">
                {{ workLoading ? t('account.loading') : t('account.draftsEmpty') }}
              </div>
              <div v-else class="w-list">
                <div v-for="row in drafts" :key="row.draftId" class="w-row">
                  <div class="w-when">
                    <b>{{ stamp(row.updateTime).date }}</b>
                    <span>{{ stamp(row.updateTime).time }}</span>
                  </div>
                  <div class="w-main">
                    <div class="w-title">{{ row.title || t('account.draftUntitled') }}</div>
                    <span class="w-tag">{{ row.guidelineCode }}</span>
                  </div>
                  <div class="w-prog">
                    <div class="w-bar"><i :style="{ width: draftPct(row) + '%' }" /></div>
                    <span>{{ t('account.draftProgress', { done: row.requiredFilled, total: row.requiredTotal }) }}</span>
                  </div>
                  <div class="w-acts">
                    <NuxtLink class="btn btn-ghost btn-sm" :to="draftLink(row)">{{ t('account.draftOpen') }}</NuxtLink>
                  </div>
                </div>
              </div>
            </div>

            <div class="blk">
              <div class="blk-head">
                <h3>{{ t('account.srdTitle') }} <span class="cnt">{{ srdRuns.length }}</span></h3>
                <NuxtLink class="blk-more" to="/srd">{{ t('account.toSrd') }}</NuxtLink>
              </div>
              <div v-if="!srdRuns.length" class="acc-empty sm">
                {{ workLoading ? t('account.loading') : t('account.srdEmpty') }}
              </div>
              <div v-else class="w-list">
                <div v-for="row in srdRuns" :key="row.assessmentId" class="w-row">
                  <div class="w-when">
                    <b>{{ stamp(row.createTime).date }}</b>
                    <span>{{ stamp(row.createTime).time }}</span>
                  </div>
                  <div class="w-main ab">
                    <div class="ht"><em>A</em><span>{{ pick(row, 'reviewATitle') }}</span></div>
                    <div class="ht b"><em>B</em><span>{{ pick(row, 'reviewBTitle') }}</span></div>
                  </div>
                  <div class="w-verdict">
                    <template v-if="row.runStatus === 'completed'">
                      <span class="lvl" :class="lvClass(row.overallLevel)">{{ lvLabel(row.overallLevel) }}</span>
                      <span class="w-num">{{ row.overallPct }}% · {{ row.overallScoreSum }}/{{ row.overallScoreMax }}</span>
                    </template>
                    <span v-else class="w-state" :class="{ bad: row.runStatus === 'failed' }">
                      {{ t(SRD_STATUS_KEY[row.runStatus ?? 'pending'] ?? 'srd.stQueued') }}
                      <template v-if="row.runStatus === 'running'">{{ row.progress }}%</template>
                    </span>
                  </div>
                  <div class="w-acts">
                    <NuxtLink class="btn btn-ghost btn-sm" :to="srdLink(row)">
                      {{ row.runStatus === 'completed' ? t('srd.histView') : t('account.srdProgress') }}
                    </NuxtLink>
                  </div>
                </div>
              </div>
            </div>

            <p v-if="workErr" class="w-err" role="alert">{{ workErr }}</p>

            <!-- ===================== 账号设置 ===================== -->
            <div class="blk">
              <div class="blk-head"><h3>{{ t('account.settingsTitle') }}</h3></div>
              <div class="set-grid">
                <form class="cform" novalidate @submit.prevent="saveProfile">
                  <div class="subh">{{ t('account.profileTitle') }}</div>
                  <div class="frow">
                    <label for="ac-email">{{ t('account.lblEmail') }}</label>
                    <input id="ac-email" class="inp" type="email" :value="guest?.email" readonly />
                    <span class="hint">{{ t('account.emailHint') }}</span>
                  </div>
                  <div class="frow">
                    <label for="ac-username" v-html="t('auth.lblUsername')"></label>
                    <input
                      id="ac-username" v-model="profile.username" class="inp" autocomplete="nickname"
                      :placeholder="t('auth.phUsername')" :maxlength="MAXLEN.username" required
                    />
                  </div>
                  <div class="frow">
                    <label for="ac-institution">{{ t('auth.lblInstitution') }}</label>
                    <input
                      id="ac-institution" v-model="profile.institution" class="inp" autocomplete="organization"
                      :placeholder="t('auth.phInstitution')" :maxlength="MAXLEN.institution"
                    />
                  </div>
                  <div class="frow">
                    <label for="ac-position">{{ t('auth.lblPosition') }}</label>
                    <input
                      id="ac-position" v-model="profile.position" class="inp" autocomplete="organization-title"
                      :placeholder="t('auth.phPosition')" :maxlength="MAXLEN.position"
                    />
                  </div>
                  <div class="cform-foot">
                    <button type="submit" class="btn btn-primary" :disabled="profileBusy || !profileDirty">
                      {{ profileBusy ? t('auth.submitting') : t('account.profileSave') }}
                    </button>
                  </div>
                  <div class="fmsg" :class="{ show: !!profileMsg, bad: !profileOk }" role="alert">
                    <span>{{ profileMsg }}</span>
                  </div>
                </form>

                <form class="cform" novalidate @submit.prevent="savePassword">
                  <div class="subh">{{ t('account.pwdTitle') }}</div>
                  <!-- 隐藏的用户名字段：让密码管理器知道这组密码属于哪个账号，否则它会存成一条无主密码 -->
                  <input type="email" class="vh" autocomplete="username" :value="guest?.email" readonly tabindex="-1" aria-hidden="true" />
                  <div class="frow">
                    <label for="ac-old" v-html="t('account.lblOldPassword')"></label>
                    <input
                      id="ac-old" v-model="pwd.old" class="inp" type="password" autocomplete="current-password"
                      :maxlength="MAXLEN.password" required
                    />
                    <NuxtLink class="forgot" to="/forgot-password?redirect=%2Faccount">{{ t('auth.forgot.link') }}</NuxtLink>
                  </div>
                  <div class="frow">
                    <label for="ac-new" v-html="t('auth.forgot.lblNewPassword')"></label>
                    <input
                      id="ac-new" v-model="pwd.password" class="inp" type="password" autocomplete="new-password"
                      :placeholder="t('auth.phPassword')" :maxlength="MAXLEN.password" required
                    />
                  </div>
                  <div class="frow">
                    <label for="ac-confirm" v-html="t('auth.lblConfirmPassword')"></label>
                    <input
                      id="ac-confirm" v-model="pwd.confirm" class="inp" type="password" autocomplete="new-password"
                      :placeholder="t('auth.phConfirmPassword')" :maxlength="MAXLEN.password" required
                    />
                  </div>
                  <div class="cform-foot">
                    <span class="fn">{{ t('account.pwdNote') }}</span>
                    <button type="submit" class="btn btn-primary" :disabled="pwdBusy">
                      {{ pwdBusy ? t('auth.submitting') : t('account.pwdSave') }}
                    </button>
                  </div>
                  <div class="fmsg" :class="{ show: !!pwdMsg, bad: !pwdOk }" role="alert">
                    <span>{{ pwdMsg }}</span>
                  </div>
                </form>
              </div>
            </div>
          </template>
        </div>
      </div>
    </section>
  </div>
</template>

<style>
.page-account .sec{padding:clamp(44px,6vw,80px) 0;scroll-margin-top:130px}
.page-account h2.title{font-size:clamp(1.65rem,3.2vw,2.35rem);color:var(--indigo-900);letter-spacing:-.02em;text-wrap:balance;max-width:26ch;overflow-wrap:anywhere}
.page-account .lead{color:var(--muted);font-size:clamp(1rem,1.4vw,1.14rem);max-width:68ch;margin-top:16px;text-wrap:pretty;overflow-wrap:anywhere}
.page-account .btn{display:inline-flex;align-items:center;justify-content:center;gap:9px;padding:13px 24px;border-radius:999px;font-weight:600;font-size:15px;border:1.5px solid transparent;cursor:pointer;white-space:nowrap;transition:transform .25s var(--ease),background-color .25s var(--ease),box-shadow .25s var(--ease),border-color .25s var(--ease)}
.page-account .btn:disabled{opacity:.55;cursor:not-allowed;transform:none;box-shadow:none}
.page-account .btn-sm{padding:9px 16px;font-size:13.5px}
.page-account .acc-head{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;flex-wrap:wrap}
.page-account .acc-body{margin-top:clamp(26px,3.5vw,38px)}
.page-account .acc-empty{text-align:center;padding:40px 20px;color:var(--muted);font-size:14px;background:var(--paper);border:1.5px dashed var(--line);border-radius:var(--radius-lg)}
.page-account .acc-empty.sm{padding:26px 20px}
.page-account .acc-empty a{color:var(--indigo-600);font-weight:600;text-decoration:underline;text-underline-offset:3px;margin-left:4px}

.page-account .blk + .blk{margin-top:clamp(30px,4vw,44px)}
.page-account .blk-head{display:flex;align-items:baseline;justify-content:space-between;gap:14px;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid var(--line)}
.page-account .blk-head h3{font-family:"Spectral","Noto Serif SC",serif;font-size:1.24rem;font-weight:600;color:var(--indigo-900)}
.page-account .blk-head .cnt{font-family:"Source Sans 3","Noto Sans SC",sans-serif;font-size:12px;font-weight:700;color:var(--indigo-600);background:var(--indigo-100);border-radius:999px;padding:2px 9px;margin-left:6px;vertical-align:middle;font-variant-numeric:tabular-nums}
.page-account .blk-more{font-size:13px;font-weight:600;color:var(--indigo-600);white-space:nowrap}
.page-account .blk-more:hover{color:var(--cinnabar)}

.page-account .w-list{display:flex;flex-direction:column;gap:10px}
.page-account .w-row{display:grid;grid-template-columns:110px minmax(0,1fr) 190px auto;gap:18px;align-items:center;
    background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:16px 18px;transition:.2s var(--ease)}
.page-account .w-row:hover{border-color:var(--indigo-200);box-shadow:var(--shadow-sm);background:var(--surface)}
.page-account .w-when b{display:block;font-family:"Spectral",serif;font-weight:700;color:var(--indigo-900);font-size:14px;font-variant-numeric:tabular-nums}
.page-account .w-when span{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
.page-account .w-main{min-width:0;display:flex;align-items:center;gap:10px}
.page-account .w-title{font-size:14px;font-weight:600;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.page-account .w-tag{flex-shrink:0;font-size:11.5px;font-weight:700;color:var(--indigo-700);background:var(--indigo-100);border:1px solid var(--indigo-200);border-radius:6px;padding:1px 7px}
.page-account .w-main.ab{flex-direction:column;align-items:stretch;gap:0;font-size:13px;color:var(--ink);line-height:1.5}
.page-account .w-main .ht{display:flex;gap:7px;align-items:baseline;min-width:0}
.page-account .w-main em{font-style:normal;font-weight:700;font-size:11px;color:#fff;background:var(--indigo-600);border-radius:5px;padding:0 6px;flex-shrink:0}
.page-account .w-main .ht.b em{background:var(--info)}
.page-account .w-main .ht span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.page-account .w-prog{display:flex;flex-direction:column;gap:6px;min-width:0}
.page-account .w-bar{height:6px;border-radius:999px;background:var(--paper-2);overflow:hidden}
.page-account .w-bar i{display:block;height:100%;background:var(--indigo-500);border-radius:inherit}
.page-account .w-prog span,.page-account .w-num{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
.page-account .w-verdict{display:flex;flex-direction:column;align-items:flex-start;gap:5px;min-width:0}
.page-account .w-state{font-size:12.5px;font-weight:700;color:var(--indigo-600);font-variant-numeric:tabular-nums}
.page-account .w-state.bad{color:var(--cinnabar-d)}
.page-account .w-acts{display:flex;align-items:center;gap:8px}
.page-account .w-err{margin-top:14px;font-size:13px;font-weight:600;color:var(--cinnabar)}
.page-account .lvl{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:700;padding:4px 11px;border-radius:999px;white-space:nowrap}
.page-account .lvl::before{content:"";width:7px;height:7px;border-radius:50%}
.page-account .lvl-none{color:var(--info);background:var(--info-bg)}
.page-account .lvl-none::before{background:var(--info)}
.page-account .lvl-low{color:var(--indigo-600);background:var(--indigo-100)}
.page-account .lvl-low::before{background:var(--indigo-500)}
.page-account .lvl-mod{color:var(--amber);background:var(--amber-bg)}
.page-account .lvl-mod::before{background:var(--amber)}
.page-account .lvl-high{color:var(--cinnabar-d);background:rgba(192,54,44,.09)}
.page-account .lvl-high::before{background:var(--cinnabar)}
.page-account .lvl-unknown{color:var(--muted);background:var(--paper-2)}
.page-account .lvl-unknown::before{background:#9aa7b8}

.page-account .set-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;align-items:start}
.page-account .cform{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-lg);padding:clamp(20px,3vw,30px)}
.page-account .subh{font-size:12.5px;font-weight:700;color:var(--indigo-900);text-transform:uppercase;letter-spacing:.03em;margin-bottom:14px;font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-account .frow{margin-bottom:16px}
.page-account .frow label{display:block;font-size:12.5px;font-weight:700;color:var(--indigo-800);margin-bottom:7px}
.page-account .frow label .rq{color:var(--cinnabar)}
.page-account .frow .hint{display:block;margin-top:6px;font-size:12px;color:var(--muted)}
.page-account .inp{width:100%;border:1.5px solid var(--line);border-radius:10px;padding:11px 13px;font-family:inherit;font-size:14px;color:var(--ink);background:var(--paper)}
.page-account .inp:focus{outline:none;border-color:var(--indigo-500);box-shadow:0 0 0 4px var(--indigo-100);background:var(--surface)}
.page-account .inp[readonly]{color:var(--muted);background:var(--paper-2);cursor:default}
.page-account .inp[readonly]:focus{box-shadow:none;border-color:var(--line)}
.page-account .inp::placeholder{color:#8895a8}
.page-account .forgot{display:inline-block;margin-top:8px;font-size:12.5px;font-weight:600;color:var(--indigo-600);text-decoration:underline;text-underline-offset:3px}
.page-account .forgot:hover{color:var(--cinnabar)}
.page-account .cform-foot{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;margin-top:6px}
.page-account .cform-foot .btn{margin-left:auto}
.page-account .cform-foot .fn{font-size:12px;color:var(--muted);max-width:32ch;line-height:1.5}
.page-account .fmsg{display:none;align-items:center;gap:9px;font-size:13px;font-weight:600;color:var(--info);background:var(--info-bg);border:1px solid #bcd4f0;border-radius:10px;padding:10px 14px;margin-top:14px}
.page-account .fmsg.show{display:flex}
.page-account .fmsg.bad{color:var(--cinnabar);background:rgba(192,54,44,.08);border-color:#e7b0aa}
.page-account .vh{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);border:0}
@media(max-width:860px){
.page-account .set-grid{grid-template-columns:1fr}
.page-account .w-row{grid-template-columns:1fr;gap:10px}
.page-account .w-acts{justify-content:flex-start}
}
</style>
