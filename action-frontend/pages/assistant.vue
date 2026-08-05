<script setup lang="ts">
/**
 * assistant.html 迁移而来。
 * 模板与样式保持原状；样式已加 .page-assistant 命名空间，避免 SPA 路由切换时跨页污染。
 */
const { t } = useI18n()

interface StudyTypeStat { textZh: string | null; textEn: string | null }
interface StudyTypeRow {
  typeId: number
  typeKey: string
  nameZh: string | null
  nameEn: string | null
  hotGuideline: string | null
  guidelines: string[]
  stats: StudyTypeStat[]
}

useHead({
  title: t('assistant._title'),
  meta: [{ name: 'description', content: t('assistant._desc') }],
})

const { pick, isEn } = useBilingual()

const { data: stRes } = await useSiteObject<StudyTypeRow[]>('/study-types', 'assistant-types')
const types = computed<StudyTypeRow[]>(() => stRes.value?.data ?? [])

/** 三个问题的当前答案，默认值与原页面一致（type=trial / rand=y / sham=y） */
const ans = ref<{ type: string; rand: string; sham: string }>({ type: 'trial', rand: 'y', sham: 'y' })

/** 是否显示「随机化 / 假针」两个子问题 —— 仅试验类才问 */
const showSubQ = computed(() => ans.value.type === 'trial')

/** 把答案解析成 action_study_type.type_key */
const resolvedKey = computed(() => {
  const a = ans.value
  if (a.type === 'case' || a.type === 'sr' || a.type === 'obs') return a.type

  return a.rand === 'y' ? 'rct' : 'nrct'
})

const matched = computed<StudyTypeRow | null>(
  () => types.value.find((x) => x.typeKey === resolvedKey.value) ?? null,
)

/** 假针 / 安慰针问题的报告提示 —— 仅试验类才有对照措施可谈 */
const shamNote = computed(() =>
  showSubQ.value ? t(ans.value.sham === 'y' ? 'assistant.shamNoteY' : 'assistant.shamNoteN') : '',
)

/** 第二步模板里的「对照 / 对照措施设置」示例值随第一步的假针答案联动 */
const ctrlSample = computed(() =>
  t(showSubQ.value && ans.value.sham === 'n' ? 'assistant.acuCtrlNoSham' : 'assistant.acuCtrlSham'),
)

/** 只有试验类才谈得上对照措施设置 */
const isTrialKey = computed(() => resolvedKey.value === 'rct' || resolvedKey.value === 'nrct')

/**
 * 第二步的结构化模板 = 第一步匹配到的那份规范的真实 checklist 条目。
 *
 * 条目存在 action_guideline_item，由 tools/extract_checklists.py 从各规范的中英文版
 * docx 抽取入库，后台「规范条目管理」页面可增删改。挂在哪份规范由 action_study_type
 * 的 hot_guideline 决定（rct/nrct→STRICTA，case→CARE，sr→PRISMA，obs→STROBE）。
 */
interface ChecklistItem {
  itemId: number
  partNo: number | null
  partZh: string | null
  partEn: string | null
  domainZh: string | null
  domainEn: string | null
  itemNoZh: string | null
  itemNoEn: string | null
  contentZh: string | null
  contentEn: string | null
  extLabelZh: string | null
  extLabelEn: string | null
  extensionZh: string | null
  extensionEn: string | null
}

const checklistCode = computed(() => matched.value?.hotGuideline ?? '')

const { data: ckRes, status: ckStatus } = await useSiteObject<ChecklistItem[]>(
  '/guideline-items',
  'assistant-checklist',
  { query: () => ({ guidelineCode: checklistCode.value }) },
)
const checklist = computed<ChecklistItem[]>(() => ckRes.value?.data ?? [])
const ckLoading = computed(() => ckStatus.value === 'pending')

/** 原表用「—」表示该条无对应内容（如 CONSORT 无此条、只有针刺扩展有） */
const DASH = /^[—–-]+$/
const hasText = (s: string) => Boolean(s) && !DASH.test(s.trim())

/**
 * 多张清单表合并成一条流水清单：整体按 sortNum 顺序排开，
 * 只在「换表」「换领域」时插一条标题行，保留条目出处。
 */
const checklistRows = computed(() =>
  checklist.value.map((it, i) => {
    const prev = checklist.value[i - 1]
    const content = pick(it, 'content')
    const ext = pick(it, 'extension')
    // 正文是「—」而扩展有内容时，扩展就是这条的正文（CONSORT 非药物扩展里的新增条目）
    const extOnly = !hasText(content) && hasText(ext)

    return {
      key: it.itemId,
      seq: i + 1,
      showPart: !prev || prev.partNo !== it.partNo,
      partTitle: pick(it, 'part'),
      showDomain: !prev || prev.partNo !== it.partNo || pick(prev, 'domain') !== pick(it, 'domain'),
      domain: pick(it, 'domain'),
      no: pick(it, 'itemNo'),
      text: extOnly ? ext : content,
      extLabel: pick(it, 'extLabel'),
      ext: extOnly ? '' : (hasText(ext) ? ext : ''),
      isExt: extOnly,
    }
  }),
)

/** 清单表张数，用于「共 N 条 · M 张清单表」 */
const checklistPartCount = computed(() => new Set(checklist.value.map((i) => i.partNo)).size)

/** 第二步：穴位选取依据（辨证 / 对症 / 经验） */
const basisIdx = ref(0)

/**
 * 第三步：把稿件交给后端逐条核对 checklist。
 *
 * 真正干活的是 `tools/checklist_worker_tool` 常驻 worker（Redis 队列驱动），
 * 这里只负责提交、轮询状态、渲染判定。接口要登录访客账号 —— 一次校验是几十次模型调用。
 */
interface Verdict {
  itemId: number
  status: 'reported' | 'vague' | 'missing'
  lines: number[]
  evidence: string
  reason: string
}
interface ReviewSummary {
  total: number
  reported: number
  vague: number
  missing: number
  completeness: number
}
interface ReviewResult {
  summary: ReviewSummary
  verdicts: Verdict[]
  lineCount: number
  truncated: boolean
  models?: string[]
}

const { guest, isLoggedIn, authedCall } = useAuth()
const route = useRoute()
/** 登录后跳回本页，直接落回第三步 */
const loginLink = computed(() => `/login?redirect=${encodeURIComponent(route.fullPath)}`)

const manuscript = ref('')
const reviewState = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const reviewSid = ref('')
const reviewMsg = ref('')
const reviewError = ref('')
const reviewPct = ref(0)
const reviewResult = ref<ReviewResult | null>(null)
let pollTimer: ReturnType<typeof setTimeout> | null = null

const MIN_CHARS = 200
const canRun = computed(
  () => manuscript.value.trim().length >= MIN_CHARS && Boolean(checklistCode.value) && reviewState.value !== 'running',
)

/** 判定结果按条目 id 索引，渲染时和第二步已经取到的条目正文拼在一起 */
const itemById = computed(() => new Map(checklist.value.map((it) => [it.itemId, it])))

/** 只读一个纯文本文件填进文本框；docx/pdf 需要后端解析，暂不支持 */
async function pickFile(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  manuscript.value = await file.text()
}

function stopPolling() {
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = null
}

/** 轮询任务状态直到终态。间隔 2 秒 —— 一次校验通常几十秒到几分钟 */
async function poll() {
  const res = await authedCall(`/checklist-review/${reviewSid.value}`, 'GET')
  if (!res.ok) {
    reviewState.value = 'error'
    reviewError.value = res.message
    return
  }
  const state = (res.envelope?.data ?? {}) as Record<string, unknown>
  reviewMsg.value = String(state.message ?? '')
  const cur = Number(state.progressCurrent ?? 0)
  const total = Number(state.progressTotal ?? 100) || 100
  reviewPct.value = Math.min(100, Math.round((cur / total) * 100))

  const status = String(state.status ?? '')
  if (status === 'completed') {
    const done = (state.result ?? null) as ReviewResult | null
    reviewResult.value = done
    reviewState.value = done ? 'done' : 'error'
    if (!done) {
      reviewError.value = t('assistant.rvFailed', { msg: '' })
      return
    }
    pushTrail(
      (done.models ?? []).join(' / ') || t('assistant.auditSystem'),
      t('assistant.auditJudged', {
        n: done.summary.total,
        ok: done.summary.reported,
        vague: done.summary.vague,
        miss: done.summary.missing,
        pct: done.summary.completeness,
      }),
    )
    return
  }
  if (status === 'failed' || status === 'stopped') {
    reviewState.value = 'error'
    reviewError.value = String(state.error || '') || t(status === 'stopped' ? 'assistant.rvStopped' : 'assistant.rvFailed', { msg: '' })
    pushTrail(t('assistant.auditSystem'), reviewError.value)
    return
  }
  pollTimer = setTimeout(poll, 2000)
}

async function runReview() {
  if (!canRun.value) return
  stopPolling()
  reviewState.value = 'running'
  reviewError.value = ''
  reviewResult.value = null
  reviewPct.value = 0
  reviewMsg.value = ''

  const res = await authedCall('/checklist-review', 'POST', {
    guidelineCode: checklistCode.value,
    manuscript: manuscript.value.trim(),
    locale: isEn.value ? 'en' : 'zh',
  })
  if (!res.ok) {
    reviewState.value = 'error'
    reviewError.value = res.message
    return
  }
  reviewSid.value = String(res.envelope?.data ?? '')
  if (!reviewSid.value) {
    reviewState.value = 'error'
    reviewError.value = t('assistant.rvFailed', { msg: '' })
    return
  }
  pushTrail(
    guest.value?.username || t('assistant.auditYou'),
    t('assistant.auditSubmitted', { code: checklistCode.value, chars: manuscript.value.trim().length }),
  )
  pollTimer = setTimeout(poll, 1500)
}

async function stopReview() {
  if (!reviewSid.value) return
  stopPolling()
  await authedCall(`/checklist-review/${reviewSid.value}/stop`, 'POST')
  reviewState.value = 'idle'
}

function resetReview() {
  stopPolling()
  reviewState.value = 'idle'
  reviewResult.value = null
  reviewError.value = ''
}

onBeforeUnmount(stopPolling)

/**
 * 第三步：数据留痕与追溯。
 *
 * 记的是本次校验真实发生过的事（提交了什么、哪些模型判的、判成什么样），
 * 没跑过校验就不显示 —— 留痕不能是摆设。
 */
const trail = ref<{ at: string; who: string; what: string }[]>([])
const auditTrail = computed(() => trail.value)

const stamp = () => new Date().toLocaleTimeString(isEn.value ? 'en-GB' : 'zh-CN', { hour12: false })

function pushTrail(who: string, what: string) {
  trail.value = [{ at: stamp(), who, what }, ...trail.value].slice(0, 8)
}

/** 第四步：润色风格 —— 切换时输出段落同步换成对应风格的示例 */
const STYLES = [
  { label: 's092', out: 's091' },
  { label: 's093', out: 'aiOut2' },
  { label: 's094', out: 'aiOut3' },
  { label: 's095', out: 'aiOut4' },
]
const styleIdx = ref(0)
const aiOut = computed(() => t(`assistant.${STYLES[styleIdx.value]!.out}`))

/** 第五步：导出格式（演示不产出真实文件） */
const EXPORT_FMTS = ['docx', 'pdf', 'xml'] as const
const exportFmt = ref<string | null>(null)

/** 第五步：分享权限 */
const perm = ref<'view' | 'comment'>('view')

/** 第五步：分享链接与复制反馈 */
const SHARE_URL = 'https://action.gztcm.cn/r/9f3a…c7'
const copied = ref(false)
let copyTimer: ReturnType<typeof setTimeout> | null = null

async function copyLink() {
  // 非安全上下文 / 浏览器拒绝时也给出反馈，演示页不必区分失败原因
  try {
    await navigator.clipboard?.writeText(SHARE_URL)
  } catch { /* ignore */ }
  copied.value = true
  if (copyTimer) clearTimeout(copyTimer)
  copyTimer = setTimeout(() => (copied.value = false), 2000)
}

onBeforeUnmount(() => {
  if (copyTimer) clearTimeout(copyTimer)
})

/** 第五步：版本历史快照与版本间差异对比 */
interface DiffRow { kind: 'add' | 'del'; key: string }
const versions: { v: number; name: string; tag?: string; tagKey?: string; diff?: DiffRow[] }[] = [
  {
    v: 3,
    name: 's115',
    tagKey: 's116',
    diff: [
      { kind: 'add', key: 'diffV3_1' },
      { kind: 'add', key: 'diffV3_2' },
      { kind: 'del', key: 'diffV3_3' },
    ],
  },
  {
    v: 2,
    name: 's117',
    tag: '2026-07-20',
    diff: [
      { kind: 'add', key: 'diffV2_1' },
      { kind: 'add', key: 'diffV2_2' },
      { kind: 'del', key: 'diffV2_3' },
    ],
  },
  { v: 1, name: 's118', tag: '2026-07-18' },
]
/** 当前展开对比的版本号；再次点击收起 */
const diffVer = ref<number | null>(null)

/** 五步向导 */
const STEP_COUNT = 5
const step = ref(1)
const wizardEl = ref<HTMLElement | null>(null)

/** 跳到第 n 步；越界钳位。滚回向导顶部，避免长面板切换后停在半空 */
function go(n: number) {
  const next = Math.min(STEP_COUNT, Math.max(1, n))
  if (next === step.value) return
  step.value = next
  wizardEl.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

useReveal()
</script>

<template>
  <div class="page-assistant">
    <section class="wz" id="wizard">
      <div class="wrap">
        <span class="kicker reveal">{{ t('assistant.s001') }}</span>

        <!-- 步骤条 -->
        <div class="stepper" id="stepper" ref="wizardEl" role="tablist" :aria-label="t('assistant.wizardAria')">
          <button class="step" :class="{ on: step === 1, done: step > 1 }" data-step="1" role="tab" :aria-selected="step === 1" @click="go(1)"><span class="sn">1</span><span class="stx"><b>{{ t('assistant.s002') }}</b><span>{{ t('assistant.s003') }}</span></span></button>
          <button class="step" :class="{ on: step === 2, done: step > 2 }" data-step="2" role="tab" :aria-selected="step === 2" @click="go(2)"><span class="sn">2</span><span class="stx"><b>{{ t('assistant.s004') }}</b><span>{{ t('assistant.s005') }}</span></span></button>
          <button class="step" :class="{ on: step === 3, done: step > 3 }" data-step="3" role="tab" :aria-selected="step === 3" @click="go(3)"><span class="sn">3</span><span class="stx"><b>{{ t('assistant.s006') }}</b><span>{{ t('assistant.s007') }}</span></span></button>
          <button class="step" :class="{ on: step === 4, done: step > 4 }" data-step="4" role="tab" :aria-selected="step === 4" @click="go(4)"><span class="sn">4</span><span class="stx"><b>{{ t('assistant.s008') }}</b><span>{{ t('assistant.s009') }}</span></span></button>
          <button class="step" :class="{ on: step === 5, done: step > 5 }" data-step="5" role="tab" :aria-selected="step === 5" @click="go(5)"><span class="sn">5</span><span class="stx"><b>{{ t('assistant.s010') }}</b><span>{{ t('assistant.s011') }}</span></span></button>
        </div>

        <!-- 面板 1：研究类型智能匹配 -->
        <div class="panel" :class="{ 'is-hidden': step !== 1 }" data-panel="1">
          <div class="p-head">
            <span class="p-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /><path d="M8 11h6M11 8v6" /></svg></span>
            <div><span class="p-num">{{ t('assistant.s012') }}</span><h2>{{ t('assistant.s013') }}</h2></div>
          </div>
          <p class="p-desc" v-html="t('assistant.s014')"></p>
          <div class="two">
            <div>
              <div class="subh">{{ t('assistant.s015') }}</div>
              <div class="q-group">
                <label>{{ t('assistant.s016') }}</label>
                <div class="opts" data-q="type">
                  <button class="opt" :class="{ on: ans.type === 'trial' }" data-v="trial" @click="ans.type = 'trial'">{{ t('assistant.s017') }}</button>
                  <button class="opt" :class="{ on: ans.type === 'case' }" data-v="case" @click="ans.type = 'case'">{{ t('assistant.s018') }}</button>
                  <button class="opt" :class="{ on: ans.type === 'sr' }" data-v="sr" @click="ans.type = 'sr'">{{ t('assistant.s019') }}</button>
                  <button class="opt" :class="{ on: ans.type === 'obs' }" data-v="obs" @click="ans.type = 'obs'">{{ t('assistant.s020') }}</button>
                </div>
              </div>
              <div class="q-group sub-q" :class="{ 'is-hidden': !showSubQ }" data-subq="trial">
                <label>{{ t('assistant.s021') }}</label>
                <div class="opts" data-q="rand">
                  <button class="opt" :class="{ on: ans.rand === 'y' }" data-v="y" @click="ans.rand = 'y'">{{ t('assistant.s022') }}</button>
                  <button class="opt" :class="{ on: ans.rand === 'n' }" data-v="n" @click="ans.rand = 'n'">{{ t('assistant.s023') }}</button>
                </div>
              </div>
              <div class="q-group sub-q" :class="{ 'is-hidden': !showSubQ }" data-subq="trial">
                <label>{{ t('assistant.s024') }}</label>
                <div class="opts" data-q="sham">
                  <button class="opt" :class="{ on: ans.sham === 'y' }" data-v="y" @click="ans.sham = 'y'">{{ t('assistant.s025') }}</button>
                  <button class="opt" :class="{ on: ans.sham === 'n' }" data-v="n" @click="ans.sham = 'n'">{{ t('assistant.s026') }}</button>
                </div>
              </div>
            </div>
            <div>
              <div class="subh">{{ t('assistant.s027') }}</div>
              <div class="match" id="matchBox">
                <template v-if="matched">
                  <span class="ml">{{ t('assistant.mlLabel') }}</span>
                  <div class="mt">{{ pick(matched, 'name') }}</div>
                  <div class="mrow">
                    <span>{{ t('assistant.mountGuidelines') }}</span>
                    <div class="gchips">
                      <b v-for="g in matched.guidelines" :key="g" :class="{ hot: g === matched.hotGuideline }">{{ g }}</b>
                    </div>
                  </div>
                  <div class="mrow" :style="shamNote ? undefined : 'margin-bottom:0'">
                    <span>{{ t('assistant.recStats') }}</span>
                    <ul class="statlist">
                      <li v-for="(st, k) in matched.stats" :key="k">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M20 6 9 17l-5-5" /></svg>
                        <span>{{ pick(st, 'text') }}</span>
                      </li>
                    </ul>
                  </div>
                  <p v-if="shamNote" class="sham-note">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></svg>
                    <span>{{ shamNote }}</span>
                  </p>
                </template>
              </div>
            </div>
          </div>
        </div>

        <!-- 面板 2：在线报告模板 -->
        <div class="panel" :class="{ 'is-hidden': step !== 2 }" data-panel="2">
          <div class="p-head">
            <span class="p-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M8 8h8M8 12h8M8 16h5" /></svg></span>
            <div><span class="p-num">{{ t('assistant.s028') }}</span><h2>{{ t('assistant.s029') }}</h2></div>
          </div>
          <p class="p-desc" v-html="t('assistant.s030')"></p>
          <div class="two">
            <div>
              <div class="subh">{{ t('assistant.s031') }}</div>
              <div v-if="matched" class="tmpl-from">
                <span>{{ t('assistant.tplFrom') }}</span>
                <div class="gchips">
                  <b v-for="g in matched.guidelines" :key="g" :class="{ hot: g === matched.hotGuideline }">{{ g }}</b>
                </div>
              </div>
              <p v-if="checklistRows.length" class="tmpl-count">
                {{ t('assistant.tplCount', { n: checklistRows.length, m: checklistPartCount }) }}
              </p>
              <div class="tmpl tmpl-scroll">
                <template v-for="row in checklistRows" :key="row.key">
                  <div v-if="row.showPart && row.partTitle" class="tmpl-part">{{ row.partTitle }}</div>
                  <div v-if="row.showDomain && row.domain" class="tmpl-dom">{{ row.domain }}</div>
                  <div class="tmpl-row">
                    <span class="tnum">{{ row.no || row.seq }}</span>
                    <span class="tnm">
                      {{ row.text }}
                      <span v-if="row.ext" class="tmpl-ext"><b>{{ row.extLabel }}</b>{{ row.ext }}</span>
                    </span>
                    <span v-if="row.isExt" class="req ext">{{ t('assistant.tplExtTag') }}</span>
                  </div>
                </template>
                <p v-if="!checklistRows.length" class="tmpl-empty">
                  {{ ckLoading ? t('assistant.tplLoading') : t('assistant.tplEmpty') }}
                </p>
              </div>
              <p class="tmpl-note" v-html="t('assistant.s048')"></p>
            </div>
            <div>
              <div class="subh">{{ t('assistant.s049') }}</div>
              <div class="acu">
                <div class="ah"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2v20M12 2l3 3M12 2 9 5" /></svg><span>{{ t('assistant.s050') }}</span></div>
                <div class="afield">
                  <label>{{ t('assistant.s051') }}</label>
                  <div class="segp">
                    <button v-for="(k, i) in ['s052', 's053', 's054']" :key="k" type="button" :class="{ on: basisIdx === i }" :aria-pressed="basisIdx === i" @click="basisIdx = i">{{ t(`assistant.${k}`) }}</button>
                  </div>
                </div>
                <div class="afield">
                  <label>{{ t('assistant.s055') }}</label>
                  <input class="inp" :value="t('assistant.acuNeedle')" readonly :aria-label="t('assistant.s055')" />
                </div>
                <div class="afield">
                  <label>{{ t('assistant.s056') }}</label>
                  <input class="inp" :value="t('assistant.acuDeqi')" readonly :aria-label="t('assistant.s056')" />
                </div>
                <div v-if="isTrialKey" class="afield" style="margin-bottom:0">
                  <label>{{ t('assistant.s057') }}</label>
                  <input class="inp" :value="ctrlSample" readonly :aria-label="t('assistant.s057')" />
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 面板 3：报告内容智能校验 -->
        <div class="panel" :class="{ 'is-hidden': step !== 3 }" data-panel="3">
          <div class="p-head">
            <span class="p-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M9 12l2 2 4-4" /><path d="M12 3l7 3v6c0 4.5-3 7-7 8-4-1-7-3.5-7-8V6z" /></svg></span>
            <div><span class="p-num">{{ t('assistant.s058') }}</span><h2>{{ t('assistant.s059') }}</h2></div>
          </div>
          <p class="p-desc" v-html="t('assistant.s060')"></p>
          <!-- 稿件录入 -->
          <div v-if="reviewState !== 'done'" class="rv-input">
            <div class="subh">{{ t('assistant.rvTitle') }}</div>
            <textarea
              v-model="manuscript"
              class="rv-ta"
              :placeholder="t('assistant.rvHint')"
              :disabled="reviewState === 'running'"
              :aria-label="t('assistant.rvTitle')"
            ></textarea>
            <div class="rv-bar">
              <label class="rv-file">
                <input type="file" accept=".txt,.md,text/plain" @change="pickFile" />
                <span>{{ t('assistant.rvPickFile') }}</span>
              </label>
              <span class="rv-chars" :class="{ short: manuscript.trim().length < MIN_CHARS }">
                {{ t('assistant.rvChars', { n: manuscript.trim().length, min: MIN_CHARS }) }}
              </span>
              <span v-if="checklistCode" class="rv-target">
                {{ t('assistant.rvTarget', { code: checklistCode, n: checklist.length }) }}
              </span>
              <template v-if="isLoggedIn">
                <button v-if="reviewState !== 'running'" class="btn btn-primary btn-sm" :disabled="!canRun" @click="runReview">
                  {{ t('assistant.rvRun') }}
                </button>
                <button v-else class="btn btn-ghost btn-sm" @click="stopReview">{{ t('assistant.rvStop') }}</button>
              </template>
              <NuxtLink v-else class="btn btn-primary btn-sm" :to="loginLink">{{ t('assistant.rvLogin') }}</NuxtLink>
            </div>
            <p v-if="!isLoggedIn" class="tmpl-note">{{ t('assistant.rvNeedLogin') }}</p>
            <div v-if="reviewState === 'running'" class="meter-box" style="margin-top:16px">
              <span class="subh" style="margin:0;white-space:nowrap">{{ t('assistant.rvRunning') }}</span>
              <span class="meter" aria-hidden="true"><i :style="{ width: reviewPct + '%' }"></i></span>
              <b>{{ reviewPct }}%</b>
            </div>
            <p v-if="reviewState === 'running' && reviewMsg" class="tmpl-note">{{ reviewMsg }}</p>
            <p v-if="reviewState === 'error'" class="rv-err">{{ reviewError }}</p>
          </div>

          <!-- 判定结果 -->
          <template v-if="reviewState === 'done' && reviewResult">
            <div class="meter-box">
              <span class="subh" style="margin:0;white-space:nowrap">{{ t('assistant.s061') }}</span>
              <span class="meter" aria-hidden="true"><i :style="{ width: reviewResult.summary.completeness + '%' }"></i></span>
              <b>{{ reviewResult.summary.completeness }}%</b>
            </div>
            <div class="rv-head">
              <span class="rv-tally ok">{{ t('assistant.rvStatReported') }} {{ reviewResult.summary.reported }}</span>
              <span class="rv-tally warn">{{ t('assistant.rvStatVague') }} {{ reviewResult.summary.vague }}</span>
              <span class="rv-tally miss">{{ t('assistant.rvStatMissing') }} {{ reviewResult.summary.missing }}</span>
              <span class="rv-lines">{{ t('assistant.rvLineCount', { n: reviewResult.lineCount }) }}</span>
              <button class="btn btn-ghost btn-sm" @click="resetReview">{{ t('assistant.rvAgain') }}</button>
            </div>
            <p v-if="reviewResult.truncated" class="rv-err">{{ t('assistant.rvTruncated') }}</p>
            <ul class="chk rv-list">
              <li
                v-for="v in reviewResult.verdicts"
                :key="v.itemId"
                :class="v.status === 'reported' ? 'ok' : v.status === 'vague' ? 'warn' : 'miss'"
              >
                <span class="ci">
                  <svg v-if="v.status === 'reported'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><path d="M20 6 9 17l-5-5" /></svg>
                  <svg v-else-if="v.status === 'vague'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M12 8v5M12 16h.01" /></svg>
                  <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><path d="M18 6 6 18M6 6l12 12" /></svg>
                </span>
                <span class="ctext">
                  <b>
                    <em v-if="pick(itemById.get(v.itemId), 'itemNo')">{{ pick(itemById.get(v.itemId), 'itemNo') }}</em>
                    {{ pick(itemById.get(v.itemId), 'content') || pick(itemById.get(v.itemId), 'extension') }}
                  </b>
                  <span v-if="v.lines.length">{{ t('assistant.rvLines', { lines: v.lines.join('、') }) }}<i v-if="v.evidence">「{{ v.evidence }}」</i></span>
                  <span v-if="v.reason">{{ v.reason }}</span>
                </span>
                <span class="cstat">
                  {{ t(v.status === 'reported' ? 'assistant.rvStatReported' : v.status === 'vague' ? 'assistant.rvStatVague' : 'assistant.rvStatMissing') }}
                </span>
              </li>
            </ul>
          </template>
          <div v-if="auditTrail.length" class="audit">
            <div class="subh" style="margin-bottom:6px">{{ t('assistant.auditTitle') }}</div>
            <p class="tmpl-note" style="margin:0 0 12px">{{ t('assistant.auditDesc') }}</p>
            <ul class="audit-list">
              <li v-for="l in auditTrail" :key="l.at">
                <span class="at">{{ l.at }}</span>
                <span class="aa">{{ l.who }}</span>
                <span class="ad">{{ l.what }}</span>
              </li>
            </ul>
          </div>
        </div>

        <!-- 面板 4：AI 辅助撰写建议 -->
        <div class="panel" :class="{ 'is-hidden': step !== 4 }" data-panel="4">
          <div class="p-head">
            <span class="p-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3v3M12 18v3M3 12h3M18 12h3M6 6l2 2M16 16l2 2M18 6l-2 2M8 16l-2 2" /><circle cx="12" cy="12" r="3.5" /></svg></span>
            <div><span class="p-num">{{ t('assistant.s085') }}</span><h2>{{ t('assistant.s086') }}</h2></div>
          </div>
          <p class="p-desc">{{ t('assistant.s087') }}</p>
          <div class="two">
            <div>
              <div class="subh">{{ t('assistant.s088') }}</div>
              <div class="ai-box">
                <div class="ai-top"><span class="dot"></span><span>{{ t('assistant.s089') }}</span></div>
                <div class="ai-inp" v-html="t('assistant.s090')"></div>
                <div class="ai-out" v-html="aiOut"></div>
              </div>
              <div class="style-chips" role="group" :aria-label="t('assistant.styleAria')">
                <button v-for="(s, i) in STYLES" :key="s.label" type="button" :class="{ on: styleIdx === i }" :aria-pressed="styleIdx === i" @click="styleIdx = i">{{ t(`assistant.${s.label}`) }}</button>
              </div>
            </div>
            <div>
              <div class="subh">{{ t('assistant.s096') }}</div>
              <div class="ai-box" style="margin-bottom:16px">
                <div class="ai-top"><span class="dot"></span><span>{{ t('assistant.bgTitle') }}</span></div>
                <div class="ai-inp" v-html="t('assistant.bgIn')"></div>
                <div class="ai-out" v-html="t('assistant.bgOut')"></div>
              </div>
              <div class="subh">{{ t('assistant.refTitle') }}</div>
              <ul class="ref-list">
                <li><em>1</em><span v-html="t('assistant.s097')"></span></li>
                <li><em>2</em><span v-html="t('assistant.s098')"></span></li>
                <li><em>3</em><span v-html="t('assistant.s099')"></span></li>
                <li><em>4</em><span v-html="t('assistant.s100')"></span></li>
              </ul>
              <p class="tmpl-note">{{ t('assistant.s101') }}</p>
            </div>
          </div>
        </div>

        <!-- 面板 5：报告导出与分享 -->
        <div class="panel" :class="{ 'is-hidden': step !== 5 }" data-panel="5">
          <div class="p-head">
            <span class="p-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3v12m0 0 4-4m-4 4-4-4" /><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" /></svg></span>
            <div><span class="p-num">{{ t('assistant.s102') }}</span><h2>{{ t('assistant.s103') }}</h2></div>
          </div>
          <p class="p-desc">{{ t('assistant.s104') }}</p>
          <div class="subh">{{ t('assistant.s105') }}</div>
          <div class="exp-btns">
            <button class="exp" :class="{ on: exportFmt === 'docx' }" data-fmt="docx" :aria-pressed="exportFmt === 'docx'" @click="exportFmt = 'docx'"><span class="ei" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4" /><path d="M9 13h6M9 16h4" /></svg></span><span><b>Word (.docx)</b><span>{{ t('assistant.s106') }}</span></span></button>
            <button class="exp" :class="{ on: exportFmt === 'pdf' }" data-fmt="pdf" :aria-pressed="exportFmt === 'pdf'" @click="exportFmt = 'pdf'"><span class="ei" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4" /><path d="M9 14h1.5a1.5 1.5 0 0 0 0-3H9v6" /></svg></span><span><b>{{ t('assistant.s107') }}</b><span>{{ t('assistant.s108') }}</span></span></button>
            <button class="exp" :class="{ on: exportFmt === 'xml' }" data-fmt="xml" :aria-pressed="exportFmt === 'xml'" @click="exportFmt = 'xml'"><span class="ei" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M9 8l-4 4 4 4M15 8l4 4-4 4" /></svg></span><span><b>XML / JSON</b><span>{{ t('assistant.s109') }}</span></span></button>
          </div>
          <p v-if="exportFmt" class="tmpl-note" aria-live="polite">{{ t('assistant.exportNote') }}</p>
          <div class="share">
            <div class="subh">{{ t('assistant.s110') }}</div>
            <div class="share-row">
              <span class="share-link"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M9 15l6-6M8 13l-2 2a3 3 0 0 0 4 4l2-2M16 11l2-2a3 3 0 0 0-4-4l-2 2" /></svg><span id="shareUrl">{{ SHARE_URL }}</span></span>
              <span class="share-perm" role="group" :aria-label="t('assistant.permAria')">
                <button type="button" :class="{ on: perm === 'view' }" :aria-pressed="perm === 'view'" @click="perm = 'view'">{{ t('assistant.s111') }}</button>
                <button type="button" :class="{ on: perm === 'comment' }" :aria-pressed="perm === 'comment'" @click="perm = 'comment'">{{ t('assistant.s112') }}</button>
              </span>
              <button class="btn btn-ink btn-sm" id="copyLink" @click="copyLink">{{ copied ? t('assistant.copied') : t('assistant.s113') }}</button>
            </div>
          </div>
          <div class="subh" style="margin-top:22px">{{ t('assistant.s114') }}</div>
          <ul class="ver-list">
            <template v-for="ver in versions" :key="ver.v">
              <li>
                <span class="vt">v{{ ver.v }}</span>
                <span class="vn">{{ t(`assistant.${ver.name}`) }}</span>
                <span class="vtag">{{ ver.tagKey ? t(`assistant.${ver.tagKey}`) : ver.tag }}</span>
                <button
                  v-if="ver.diff"
                  class="vdiff"
                  type="button"
                  :class="{ on: diffVer === ver.v }"
                  :aria-expanded="diffVer === ver.v"
                  @click="diffVer = diffVer === ver.v ? null : ver.v"
                >{{ t('assistant.verCompare') }}</button>
              </li>
              <li v-if="ver.diff && diffVer === ver.v" class="diffbox">
                <span class="dh">{{ t('assistant.diffTitle', { a: ver.v - 1, b: ver.v }) }}</span>
                <span v-for="d in ver.diff" :key="d.key" class="dl" :class="d.kind">
                  <em aria-hidden="true">{{ d.kind === 'add' ? '+' : '−' }}</em>{{ t(`assistant.${d.key}`) }}
                </span>
              </li>
            </template>
          </ul>
          <div class="beta-note"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 9v4M12 17h.01" /><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" /></svg><span>{{ t('assistant.s119') }}</span></div>
        </div>

        <!-- 向导底部导航 -->
        <div class="wz-nav">
          <span class="wz-prog"><span>{{ t('assistant.s120') }}</span> <b id="curStep">{{ step }}</b> / {{ STEP_COUNT }} <span>{{ t('assistant.s121') }}</span></span>
          <div class="wz-btns">
            <button class="btn btn-ghost" id="prevBtn" :disabled="step === 1" @click="go(step - 1)">{{ t('assistant.s122') }}</button>
            <button class="btn btn-primary" id="nextBtn" :disabled="step === STEP_COUNT" @click="go(step + 1)">{{ t('assistant.nextStep') }} <span class="arrow" aria-hidden="true">→</span></button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style>
.page-assistant .skip-link{position:absolute;left:12px;top:-60px;z-index:var(--z-toast);background:var(--indigo-700);color:#fff;font-weight:600;font-size:15px;padding:12px 20px;border-radius:10px;transition:top .2s var(--ease)}
.page-assistant .btn{display:inline-flex;align-items:center;justify-content:center;gap:9px;padding:13px 24px;border-radius:999px;font-weight:600;font-size:15px;border:1.5px solid transparent;cursor:pointer;white-space:nowrap;transition:transform .25s var(--ease),background-color .25s var(--ease),box-shadow .25s var(--ease),border-color .25s var(--ease)}
.page-assistant .btn-primary:disabled{background:var(--indigo-300);box-shadow:none;cursor:not-allowed;transform:none}
.page-assistant .btn-ghost:disabled{opacity:.45;cursor:not-allowed}
.page-assistant .btn-lg{padding:15px 30px;font-size:16px}
.page-assistant .phero{position:relative;overflow:hidden;background:var(--indigo-900);color:#fff;isolation:isolate}
.page-assistant .phero::before{content:"";position:absolute;inset:0;z-index:-1;background:radial-gradient(1000px 560px at 88% 0%,rgba(44,127,114,.5),transparent 60%),radial-gradient(680px 460px at 2% 100%,rgba(24,48,41,.7),transparent 65%),linear-gradient(160deg,#0d1a17 0%,#12211d 44%,#183029 100%)}
.page-assistant .phero .wrap{padding:clamp(28px,3.6vw,42px) clamp(20px,4vw,44px) clamp(40px,5.5vw,58px)}
.page-assistant .crumb{display:flex;align-items:center;gap:9px;font-size:13.5px;color:rgba(233,238,247,.66);margin-bottom:22px;flex-wrap:wrap}
.page-assistant .phero-tag{display:inline-flex;align-items:center;gap:10px;font-size:13px;font-weight:600;letter-spacing:.02em;color:var(--indigo-200);background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.16);padding:8px 16px;border-radius:999px;backdrop-filter:blur(4px)}
.page-assistant .phero h1{font-size:clamp(1.9rem,3.9vw,3rem);font-weight:700;letter-spacing:-.025em;margin:18px 0 0;text-wrap:balance;line-height:1.14}
.page-assistant .phero .psub{margin-top:18px;font-size:clamp(1rem,1.4vw,1.16rem);color:rgba(233,238,247,.9);max-width:64ch;line-height:1.7;text-wrap:pretty}
.page-assistant .phero-cta{display:flex;gap:14px;flex-wrap:wrap;margin-top:28px}
.page-assistant .wz{padding:clamp(34px,5vw,60px) 0}
.page-assistant .stepper{display:flex;gap:6px;background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:10px;overflow-x:auto;scrollbar-width:none}
.page-assistant .stepper::-webkit-scrollbar{display:none}
.page-assistant .step{flex:1;min-width:150px;display:flex;align-items:center;gap:11px;padding:12px 14px;border-radius:12px;cursor:pointer;background:transparent;border:none;font-family:inherit;text-align:left;transition:background .2s}
.page-assistant .step:hover{background:var(--paper-2)}
.page-assistant .step.on{background:var(--indigo-100)}
.page-assistant .step .sn{width:30px;height:30px;flex-shrink:0;border-radius:9px;background:var(--paper-2);color:var(--muted);display:flex;align-items:center;justify-content:center;font-family:"Spectral",serif;font-weight:700;font-size:15px;transition:.2s}
.page-assistant .step.on .sn{background:var(--cinnabar);color:#fff}
.page-assistant .step.done .sn{background:var(--indigo-600);color:#fff}
.page-assistant .step .stx{min-width:0}
.page-assistant .step .stx b{display:block;font-size:13.5px;font-weight:700;color:var(--indigo-900);font-family:"Source Sans 3","Noto Sans SC",sans-serif;line-height:1.2}
.page-assistant .step .stx span{display:block;font-size:11px;color:var(--muted);margin-top:1px}
.page-assistant .step.on .stx b{color:var(--cinnabar-d)}
.page-assistant .panel{margin-top:20px;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-lg);padding:clamp(22px,3.2vw,38px)}
.page-assistant .panel.is-hidden{display:none}
.page-assistant .p-head{display:flex;align-items:flex-start;gap:15px;margin-bottom:6px}
.page-assistant .p-ic{width:48px;height:48px;flex-shrink:0;border-radius:13px;background:var(--indigo-700);color:#fff;display:flex;align-items:center;justify-content:center}
.page-assistant .p-ic svg{width:26px;height:26px}
.page-assistant .p-num{font-size:12px;font-weight:700;color:var(--indigo-500);letter-spacing:.03em}
.page-assistant .panel h2{font-size:clamp(1.4rem,2.5vw,1.9rem);color:var(--indigo-900);letter-spacing:-.01em;line-height:1.2}
.page-assistant .p-desc{font-size:14.5px;color:var(--muted);line-height:1.65;max-width:74ch;margin:14px 0 22px}
.page-assistant .p-desc b{color:var(--indigo-700)}
.page-assistant .two{display:grid;grid-template-columns:1fr 1fr;gap:clamp(20px,3vw,32px)}
.page-assistant .subh{font-size:12.5px;font-weight:700;color:var(--indigo-900);text-transform:uppercase;letter-spacing:.03em;margin-bottom:12px;font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-assistant .q-group{margin-bottom:18px}
.page-assistant .q-group>label{display:block;font-size:14px;font-weight:600;color:var(--ink);margin-bottom:9px}
.page-assistant .opts{display:flex;flex-wrap:wrap;gap:9px}
.page-assistant .opt{font-family:inherit;font-size:13.5px;font-weight:600;color:var(--indigo-700);background:var(--surface);border:1.5px solid var(--line);border-radius:10px;padding:10px 16px;cursor:pointer;transition:.18s}
.page-assistant .opt:hover{border-color:var(--indigo-300);background:var(--indigo-100)}
.page-assistant .opt.on{background:var(--indigo-700);border-color:var(--indigo-700);color:#fff}
.page-assistant .sub-q.is-hidden{display:none}
.page-assistant .match{background:var(--indigo-900);color:#fff;border-radius:16px;padding:24px;position:relative;overflow:hidden;isolation:isolate}
.page-assistant .match::before{content:"";position:absolute;inset:0;z-index:-1;background:radial-gradient(500px 240px at 100% 0,rgba(44,127,114,.4),transparent 60%)}
.page-assistant .match .ml{font-size:12px;font-weight:700;color:var(--indigo-200);letter-spacing:.03em}
.page-assistant .match .mt{font-family:"Spectral","Noto Serif SC",serif;font-weight:700;font-size:1.5rem;margin:5px 0 16px;color:#fff}
.page-assistant .match .mrow{margin-bottom:15px}
.page-assistant .match .mrow>span{font-size:12px;color:rgba(233,238,247,.7);display:block;margin-bottom:7px}
.page-assistant .gchips{display:flex;flex-wrap:wrap;gap:7px}
.page-assistant .gchips b{font-size:12.5px;font-weight:700;padding:5px 12px;border-radius:999px;background:rgba(255,255,255,.1);color:#fff}
.page-assistant .gchips b.hot{background:var(--cinnabar);color:#fff}
.page-assistant .statlist{list-style:none;display:flex;flex-direction:column;gap:7px}
.page-assistant .statlist li{display:flex;align-items:flex-start;gap:9px;font-size:13px;color:rgba(233,238,247,.92);line-height:1.45}
.page-assistant .statlist li svg{width:16px;height:16px;flex-shrink:0;margin-top:2px;color:var(--indigo-200)}
.page-assistant .sham-note{display:flex;align-items:flex-start;gap:9px;margin-top:16px;padding-top:15px;border-top:1px solid rgba(255,255,255,.14);font-size:12.5px;line-height:1.55;color:rgba(233,238,247,.82)}
.page-assistant .sham-note svg{width:15px;height:15px;flex-shrink:0;margin-top:2px;color:var(--indigo-200)}
.page-assistant .tmpl-from{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.page-assistant .tmpl-from>span{font-size:12px;color:var(--muted)}
.page-assistant .tmpl-from .gchips b{background:var(--indigo-100);color:var(--indigo-800)}
.page-assistant .tmpl-from .gchips b.hot{background:var(--cinnabar);color:#fff}
.page-assistant .tmpl-count{font-size:12px;color:var(--muted);margin-bottom:10px}
.page-assistant .tmpl{border:1px solid var(--line);border-radius:14px;overflow:hidden}
.page-assistant .tmpl-scroll{max-height:520px;overflow-y:auto}
.page-assistant .tmpl-part{position:sticky;top:0;z-index:1;padding:10px 16px;background:var(--indigo-900);color:#fff;font-size:12px;font-weight:700;letter-spacing:.02em}
.page-assistant .tmpl-dom{padding:9px 16px;background:var(--paper-2);border-top:1px solid var(--line);font-size:12px;font-weight:700;color:var(--indigo-800)}
.page-assistant .tmpl-row{display:flex;align-items:flex-start;gap:12px;padding:12px 16px;border-top:1px solid var(--line);font-size:14px}
.page-assistant .tmpl-part+.tmpl-row,.page-assistant .tmpl-dom+.tmpl-row{border-top:none}
.page-assistant .tmpl-row .tnum{font-family:"Spectral",serif;font-weight:700;color:var(--indigo-500);min-width:28px;flex-shrink:0;font-variant-numeric:tabular-nums}
.page-assistant .tmpl-row .tnm{flex:1;color:var(--ink);font-weight:600;line-height:1.55}
.page-assistant .tmpl-ext{display:block;margin-top:6px;font-weight:400;font-size:12.5px;color:var(--muted);line-height:1.5}
.page-assistant .tmpl-ext b{display:block;font-size:11px;font-weight:700;color:var(--indigo-500);margin-bottom:2px}
.page-assistant .tmpl-empty{padding:22px 16px;font-size:13px;color:var(--muted);text-align:center}
.page-assistant .req{font-size:11px;font-weight:700;padding:2px 9px;border-radius:999px;flex-shrink:0}
.page-assistant .req.must{color:var(--cinnabar-d);background:rgba(192,54,44,.09)}
.page-assistant .req.opt{color:var(--muted);background:var(--paper-2)}
.page-assistant .req.ext{color:var(--cinnabar-d);background:rgba(192,54,44,.09)}
.page-assistant .acu{background:linear-gradient(180deg,#fff,var(--indigo-100));border:1px solid var(--indigo-200);border-radius:14px;padding:18px}
.page-assistant .acu .ah{display:flex;align-items:center;gap:8px;font-weight:700;color:var(--indigo-800);margin-bottom:14px}
.page-assistant .acu .ah svg{width:18px;height:18px;color:var(--cinnabar)}
.page-assistant .afield{margin-bottom:14px}
.page-assistant .afield>label{display:block;font-size:12.5px;font-weight:700;color:var(--indigo-700);margin-bottom:6px}
.page-assistant .afield .inp{width:100%;border:1.5px solid var(--line);border-radius:9px;padding:9px 12px;font-family:inherit;font-size:13.5px;color:var(--ink);background:var(--surface)}
.page-assistant .afield .segp{display:flex;flex-wrap:wrap;gap:6px}
.page-assistant .afield .segp button{font-family:inherit;font-size:12.5px;font-weight:600;color:var(--indigo-700);background:var(--surface);border:1.5px solid var(--line);border-radius:8px;padding:6px 12px;cursor:pointer;transition:.18s}
.page-assistant .afield .segp button:hover{border-color:var(--indigo-300);background:var(--indigo-100)}
.page-assistant .afield .segp button.on{background:var(--cinnabar);border-color:var(--cinnabar);color:#fff}
.page-assistant .tmpl-note{margin-top:14px;font-size:12.5px;color:var(--muted);line-height:1.55}
.page-assistant .tmpl-note b{color:var(--indigo-700)}
.page-assistant .meter-box{display:flex;align-items:center;gap:16px;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:16px 20px;margin-bottom:20px}
.page-assistant .meter{flex:1;height:10px;border-radius:999px;background:var(--paper-2);overflow:hidden}
.page-assistant .meter i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,var(--indigo-500),var(--indigo-600));width:82%}
.page-assistant .meter-box b{font-family:"Spectral",serif;font-weight:700;font-size:1.3rem;color:var(--indigo-700)}
.page-assistant .chk{list-style:none;display:flex;flex-direction:column;gap:8px}
.page-assistant .chk li{display:flex;align-items:flex-start;gap:11px;font-size:14px;padding:11px 14px;border:1px solid var(--line);border-radius:11px;background:var(--surface);line-height:1.5}
.page-assistant .chk .ci{width:22px;height:22px;flex-shrink:0;border-radius:50%;display:flex;align-items:center;justify-content:center;margin-top:1px}
.page-assistant .chk .ci svg{width:14px;height:14px}
.page-assistant .chk .ok .ci{background:var(--info-bg);color:var(--info)}
.page-assistant .chk .warn .ci{background:var(--amber-bg);color:var(--amber)}
.page-assistant .chk .miss .ci{background:rgba(192,54,44,.09);color:var(--cinnabar-d)}
.page-assistant .chk .ctext b{color:var(--indigo-900)}
.page-assistant .chk .ctext span{display:block;font-size:12.5px;color:var(--muted);margin-top:2px}
.page-assistant .chk .cstat{margin-left:auto;flex-shrink:0;font-size:11.5px;font-weight:700;padding:3px 10px;border-radius:999px;white-space:nowrap}
.page-assistant .chk .ok .cstat{color:var(--info);background:var(--info-bg)}
.page-assistant .chk .warn .cstat{color:var(--amber);background:var(--amber-bg)}
.page-assistant .chk .miss .cstat{color:var(--cinnabar-d);background:rgba(192,54,44,.09)}
.page-assistant .rv-input{margin-bottom:6px}
.page-assistant .rv-ta{width:100%;min-height:200px;resize:vertical;border:1.5px solid var(--line);border-radius:12px;padding:14px 16px;font-family:inherit;font-size:13.5px;line-height:1.7;color:var(--ink);background:var(--surface)}
.page-assistant .rv-ta:focus{outline:none;border-color:var(--indigo-500)}
.page-assistant .rv-ta:disabled{background:var(--paper-2);color:var(--muted)}
.page-assistant .rv-bar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:12px}
.page-assistant .rv-file{position:relative;overflow:hidden;display:inline-flex;align-items:center;font-size:13px;font-weight:600;color:var(--indigo-700);background:var(--surface);border:1.5px solid var(--line);border-radius:9px;padding:8px 14px;cursor:pointer;transition:.18s}
.page-assistant .rv-file:hover{border-color:var(--indigo-300);background:var(--indigo-100)}
.page-assistant .rv-file input{position:absolute;inset:0;opacity:0;cursor:pointer}
.page-assistant .rv-chars{font-size:12.5px;color:var(--muted);font-variant-numeric:tabular-nums}
.page-assistant .rv-chars.short{color:var(--amber)}
.page-assistant .rv-target{font-size:12.5px;color:var(--indigo-700);font-weight:600;margin-right:auto}
.page-assistant .rv-err{margin-top:12px;font-size:13px;color:var(--cinnabar-d);background:rgba(192,54,44,.07);border-radius:10px;padding:10px 14px}
.page-assistant .rv-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.page-assistant .rv-tally{font-size:12.5px;font-weight:700;padding:5px 12px;border-radius:999px}
.page-assistant .rv-tally.ok{color:var(--info);background:var(--info-bg)}
.page-assistant .rv-tally.warn{color:var(--amber);background:var(--amber-bg)}
.page-assistant .rv-tally.miss{color:var(--cinnabar-d);background:rgba(192,54,44,.09)}
.page-assistant .rv-head .rv-lines{font-size:12.5px;color:var(--muted);margin-right:auto}
.page-assistant .rv-list{max-height:560px;overflow-y:auto;padding-right:4px}
.page-assistant .rv-list .ctext b em{font-style:normal;font-family:"Spectral",serif;color:var(--indigo-500);margin-right:7px}
.page-assistant .rv-list .ctext span i{font-style:normal;color:var(--indigo-700)}
.page-assistant .audit{margin-top:22px;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:18px}
.page-assistant .audit-list{list-style:none;display:flex;flex-direction:column;gap:8px}
.page-assistant .audit-list li{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;font-size:13px;padding:11px 14px;border:1px solid var(--line);border-radius:11px;background:var(--surface);line-height:1.5}
.page-assistant .audit-list .at{font-family:"Spectral",serif;font-weight:700;color:var(--indigo-500);font-variant-numeric:tabular-nums;flex-shrink:0}
.page-assistant .audit-list .aa{font-weight:700;color:var(--indigo-900);flex-shrink:0}
.page-assistant .audit-list .ad{flex:1;min-width:200px;color:var(--muted)}
.page-assistant .ai-box{border:1px solid var(--line);border-radius:14px;overflow:hidden}
.page-assistant .ai-top{display:flex;align-items:center;gap:8px;padding:12px 16px;background:var(--paper-2);border-bottom:1px solid var(--line);font-size:13px;font-weight:700;color:var(--indigo-800)}
.page-assistant .ai-top .dot{width:8px;height:8px;border-radius:50%;background:var(--cinnabar)}
.page-assistant .ai-inp{padding:14px 16px;border-bottom:1px dashed var(--line);font-size:13.5px;color:var(--muted)}
.page-assistant .ai-inp b{color:var(--indigo-700)}
.page-assistant .ai-out{padding:16px;font-size:14px;color:var(--ink);line-height:1.7}
.page-assistant .ai-out .hl{background:var(--indigo-100);border-radius:3px;padding:0 2px}
.page-assistant .style-chips{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}
.page-assistant .style-chips button{font-family:inherit;font-size:13px;font-weight:600;color:var(--indigo-700);background:var(--surface);border:1.5px solid var(--line);border-radius:999px;padding:7px 15px;cursor:pointer;transition:.18s}
.page-assistant .style-chips button:hover{border-color:var(--indigo-300);background:var(--indigo-100)}
.page-assistant .style-chips button.on{background:var(--info);border-color:var(--info);color:#fff}
.page-assistant .ref-list{list-style:none;display:flex;flex-direction:column;gap:9px}
.page-assistant .ref-list li{display:flex;gap:11px;font-size:13px;color:var(--muted);line-height:1.5;padding:11px 14px;border:1px solid var(--line);border-radius:11px;background:var(--paper)}
.page-assistant .ref-list li em{font-style:normal;font-family:"Spectral",serif;font-weight:700;color:var(--indigo-500);flex-shrink:0}
.page-assistant .exp-btns{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.page-assistant .exp{display:flex;align-items:center;gap:13px;padding:16px 18px;border:1.5px solid var(--line);border-radius:14px;background:var(--surface);cursor:pointer;text-align:left;font-family:inherit;transition:.2s var(--ease)}
.page-assistant .exp:hover{border-color:var(--indigo-300);background:var(--indigo-100);transform:translateY(-2px)}
.page-assistant .exp.on{border-color:var(--indigo-700);background:var(--indigo-100)}
.page-assistant .exp.on .ei{background:var(--indigo-700);color:#fff}
.page-assistant .exp .ei{width:40px;height:40px;flex-shrink:0;border-radius:11px;background:var(--indigo-100);color:var(--indigo-700);display:flex;align-items:center;justify-content:center}
.page-assistant .exp .ei svg{width:21px;height:21px}
.page-assistant .exp b{display:block;font-size:14px;color:var(--indigo-900)}
.page-assistant .exp span{font-size:12px;color:var(--muted)}
.page-assistant .share{margin-top:20px;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:18px}
.page-assistant .share-row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.page-assistant .share-link{flex:1;min-width:200px;display:flex;align-items:center;gap:10px;background:var(--surface);border:1.5px solid var(--line);border-radius:10px;padding:10px 14px;font-size:13px;color:var(--muted);font-family:"Spectral",monospace}
.page-assistant .share-perm{display:inline-flex;background:var(--paper-2);border:1px solid var(--line);border-radius:9px;padding:3px;gap:2px}
.page-assistant .share-perm button{border:none;background:transparent;font-family:inherit;font-size:12.5px;font-weight:600;color:var(--muted);padding:6px 12px;border-radius:7px;cursor:pointer}
.page-assistant .share-perm button.on{background:var(--surface);color:var(--indigo-800);box-shadow:var(--shadow-sm)}
.page-assistant .ver-list{list-style:none;margin-top:18px;display:flex;flex-direction:column;gap:8px}
.page-assistant .ver-list li{display:flex;align-items:center;gap:12px;font-size:13px;padding:11px 14px;border:1px solid var(--line);border-radius:11px;background:var(--surface)}
.page-assistant .ver-list .vt{font-family:"Spectral",serif;font-weight:700;color:var(--indigo-700);font-variant-numeric:tabular-nums}
.page-assistant .ver-list .vn{flex:1;color:var(--ink)}
.page-assistant .ver-list .vtag{font-size:11px;font-weight:700;color:var(--muted);background:var(--paper-2);border-radius:999px;padding:3px 10px}
.page-assistant .ver-list .vdiff{font-family:inherit;font-size:12px;font-weight:700;color:var(--indigo-700);background:var(--surface);border:1.5px solid var(--line);border-radius:8px;padding:4px 12px;cursor:pointer;transition:.18s}
.page-assistant .ver-list .vdiff:hover{border-color:var(--indigo-300);background:var(--indigo-100)}
.page-assistant .ver-list .vdiff.on{background:var(--indigo-700);border-color:var(--indigo-700);color:#fff}
.page-assistant .ver-list li.diffbox{flex-direction:column;gap:6px;align-items:stretch;background:var(--paper);border-style:dashed;margin:-2px 0 2px 10px}
.page-assistant .diffbox .dh{font-size:11.5px;font-weight:700;color:var(--indigo-500);letter-spacing:.02em}
.page-assistant .diffbox .dl{display:flex;gap:9px;font-size:13px;line-height:1.5;color:var(--ink)}
.page-assistant .diffbox .dl em{font-style:normal;font-weight:700;flex-shrink:0;width:12px;text-align:center}
.page-assistant .diffbox .add em{color:var(--info)}
.page-assistant .diffbox .del em{color:var(--cinnabar-d)}
.page-assistant .diffbox .del{color:var(--muted);text-decoration:line-through;text-decoration-color:rgba(122,132,148,.45)}
.page-assistant .wz-nav{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-top:22px;flex-wrap:wrap}
.page-assistant .wz-nav .wz-prog{font-size:13px;color:var(--muted)}
.page-assistant .wz-nav .wz-prog b{color:var(--indigo-700)}
.page-assistant .wz-nav .wz-btns{display:flex;gap:10px}
.page-assistant .beta-note{display:inline-flex;align-items:center;gap:9px;font-size:12.5px;font-weight:600;color:var(--amber);background:var(--amber-bg);border:1px solid #e7d39a;padding:7px 14px;border-radius:999px;margin-top:20px}
@media(max-width:900px){
.page-assistant .two{grid-template-columns:1fr}
}
</style>
