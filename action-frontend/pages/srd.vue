<script setup lang="ts">
/**
 * SRD 系统综述重复性评估。
 *
 * 页面接的是 `tools/srd_worker_tool` 常驻 worker（Redis 队列驱动）：
 * 上传两篇 PDF → 后端入队并落一行任务记录 → 这里每 3 秒轮询一次状态 →
 * 跑完由后端把引擎结果写进 `action_srd_*` 四张表，本页按 assessmentId 取详情渲染。
 * 一次评估是几十次模型调用、常需数分钟，所以**必须登录**，且历史按账号存。
 *
 * 「载入示例」不走这条链路 —— 它直接取库里那份 `is_sample='1'` 的演示数据，
 * 让没有账号的访客也能看清输出形态，且不烧 token。
 *
 * 评分口径（引擎 0.8.0 起）：每个条目 0–3 分，**分越高越重复**
 * （3 完全相同 / 0 完全不同 / unclear 证据不足，不计分也不进分母）。
 * 领域与整体的「重复百分比」由这些分数算出（得分 ÷ 满分），与分数同向。
 *
 * **甲方的 Excel 表 1 表头写的是相反的「完全相同 0 分 … 完全不同 3 分」**，
 * 拿那张表来核这一页会读反 —— 0.8.0 按甲方后来的定稿把方向翻了过来，
 * 口径的唯一真源是引擎的 `srd_engine/schemas.py`（RATING_LABEL_*），不是那份 xlsx。
 */
const { t } = useI18n()

interface SrdItem {
  itemId: number
  code: string | null
  questionZh: string | null
  questionEn: string | null
  rating: '0' | '1' | '2' | '3' | 'unclear' | null
  score: number | null
  confidence: string | null
  needsReview: '0' | '1' | null
  reviewNote: string | null
  evidenceCard: string | null
  basisZh: string | null
  basisEn: string | null
  citeAZh: string | null
  citeAEn: string | null
  citeBZh: string | null
  citeBEn: string | null
}
interface SrdGroup {
  groupId: number
  code: string | null
  nameZh: string | null
  nameEn: string | null
  items: SrdItem[]
}
interface SrdDomain {
  domainId: number
  seq: number
  nameZh: string | null
  nameEn: string | null
  isKey: '0' | '1' | null
  level: string | null
  pct: number | null
  scoreSum: number | null
  scoreMax: number | null
  scoreMaxFull: number | null
  unclearCount: number | null
  evidenceSufficient: '0' | '1' | null
  nearBoundary: '0' | '1' | null
  groups: SrdGroup[]
}
interface SrdAssessment {
  assessmentId: number
  reviewATitleZh: string | null
  reviewATitleEn: string | null
  reviewBTitleZh: string | null
  reviewBTitleEn: string | null
  overallLevel: string | null
  overallPct: number | null
  overallScoreSum: number | null
  overallScoreMax: number | null
  overallScoreMaxFull: number | null
  overallReasonZh: string | null
  overallReasonEn: string | null
  provisional: '0' | '1' | null
  unclearCount: number | null
  reviewCount: number | null
  modelName: string | null
  engineVersion: string | null
  llmCalls: number | null
  seconds: number | null
  isSample: '0' | '1' | null
  domains: SrdDomain[]
}
interface SrdHistoryRow {
  assessmentId: number
  sessionId: string | null
  runStatus: 'pending' | 'running' | 'completed' | 'failed' | 'stopped' | null
  progress: number | null
  errorMsg: string | null
  reviewATitleZh: string | null
  reviewATitleEn: string | null
  reviewBTitleZh: string | null
  reviewBTitleEn: string | null
  overallLevel: string | null
  overallPct: number | null
  overallScoreSum: number | null
  overallScoreMax: number | null
  provisional: '0' | '1' | null
  createTime: string | null
  finishTime: string | null
}

useHead({
  title: t('srd._title'),
  meta: [{ name: 'description', content: t('srd._desc') }],
})

const { pick, isEn } = useBilingual()
const api = useSiteRequest()
const { isLoggedIn, authedCall, authedBlob } = useAuth()
const route = useRoute()
/** 登录后跳回本页 */
const loginLink = computed(() => `/login?redirect=${encodeURIComponent(route.fullPath)}`)

/**
 * 判定等级 → CSS 类 / 文案键 / 环与条的配色，取值与原 srd.html 的 LV / BARC 常量一致。
 *
 * **`level` 为 null 不是「中度」**：一个领域的条目全都证据不足时，引擎给不出档位，
 * 聚合层如实留空。兜成任何一档都是在编造结论，所以它有自己的一档「无法判定」（中性灰）。
 */
const LV_CLASS: Record<string, string> = { none: 'lvl-none', low: 'lvl-low', mod: 'lvl-mod', high: 'lvl-high' }
const LV_LABEL: Record<string, string> = {
  none: 'srd.lvlNone',
  low: 'srd.lvlLow',
  mod: 'srd.lvlMod',
  high: 'srd.lvlHigh',
}
const RING_COLOR: Record<string, string> = { none: '#63c3ba', low: '#9fb3d4', mod: '#e6a93c', high: '#ff8f86' }
const BAR_COLOR: Record<string, string> = {
  none: 'var(--info)',
  low: 'var(--indigo-500)',
  mod: 'var(--amber)',
  high: 'var(--cinnabar)',
}
const UNKNOWN_COLOR = '#9aa7b8'
const lvClass = (l: string | null) => (l && LV_CLASS[l]) || 'lvl-unknown'
const lvLabel = (l: string | null) => t((l && LV_LABEL[l]) || 'srd.lvlUnknown')
const ringColor = (l: string | null) => (l && RING_COLOR[l]) || UNKNOWN_COLOR
const barColor = (l: string | null) => (l && BAR_COLOR[l]) || UNKNOWN_COLOR

/**
 * 条目评分 → 样式与文案。**键就是分数**，与引擎 `RATING_LABEL_*` 一一对应。
 *
 * 色阶跟着**重复程度**走，不跟着分数大小走：3 分是「完全相同」（最重复）用朱砂，
 * 0 分是「完全不同」用青。色值写在 `.sc-3` … `.sc-0` 里，所以那几条 CSS 看起来
 * 是「大数字偏红」—— 别按数字大小去顺手改回来。
 * 证据不足不是第五档程度，是「没得判」，所以用中性灰而不是色阶两端任何一色。
 */
const RT_CLASS: Record<string, string> = { '0': 'sc-0', '1': 'sc-1', '2': 'sc-2', '3': 'sc-3', unclear: 'sc-u' }
const RT_LABEL: Record<string, string> = {
  '0': 'srd.rt0',
  '1': 'srd.rt1',
  '2': 'srd.rt2',
  '3': 'srd.rt3',
  unclear: 'srd.rtUnclear',
}
/** 图例的展示顺序：按重复程度从高到低，与领域/整体的色阶读起来同向（不是按分数升序） */
const RT_ORDER = ['3', '2', '1', '0', 'unclear'] as const
const rtClass = (r: string | null) => RT_CLASS[r ?? 'unclear'] ?? 'sc-u'
const rtLabel = (r: string | null) => t(RT_LABEL[r ?? 'unclear'] ?? 'srd.rtUnclear')

// ---------------------------------------------------------------- 输入

/** 上传上限，与后端 `SrdService.MAX_PDF_BYTES` 对齐 */
const MAX_PDF_BYTES = 30 * 1024 * 1024

interface Slot {
  /** 真实文件；示例槽为 null */
  file: File | null
  name: string
  size: number
  /** 示例槽：不上传，运行时直接渲染库里的示例评估 */
  sample: boolean
}
const slotA = ref<Slot | null>(null)
const slotB = ref<Slot | null>(null)
const dragging = ref<'a' | 'b' | ''>('')
const inputError = ref('')

const slotOf = (which: 'a' | 'b') => (which === 'a' ? slotA : slotB)

const fmtSize = (bytes: number) => (bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`)

/**
 * 收下一个文件。
 *
 * 类型与大小在这里就拦掉：等后端回绝要多花一次上传，而 30MB 的往返在会场 Wi-Fi 上
 * 是十几秒的沉默。扩展名不可信，但浏览器侧只有它可用；真正的把关在后端读文件头。
 */
function acceptFile(which: 'a' | 'b', file: File | undefined | null) {
  if (!file) return
  inputError.value = ''
  if (!/\.pdf$/i.test(file.name) && file.type !== 'application/pdf') {
    inputError.value = t('srd.errNotPdf')

    return
  }
  if (file.size > MAX_PDF_BYTES) {
    inputError.value = t('srd.errTooBig', { mb: MAX_PDF_BYTES / 1024 / 1024 })

    return
  }
  slotOf(which).value = { file, name: file.name, size: file.size, sample: false }

  // 示例是全有或全无：另一边还挂着示例槽的话就腾空它。
  // 不腾的话会出现「一真一示例」的半吊子状态 —— 那一边根本没有 File 可传。
  const other = slotOf(which === 'a' ? 'b' : 'a')
  if (other.value?.sample) other.value = null
  if (isSampleResult.value) result.value = null
}

function onPick(which: 'a' | 'b', e: Event) {
  const input = e.target as HTMLInputElement
  acceptFile(which, input.files?.[0])
  // 清空原生 input：不清的话「移除后再选同一个文件」不会触发 change
  input.value = ''
}

function onDrop(which: 'a' | 'b', e: DragEvent) {
  dragging.value = ''
  acceptFile(which, e.dataTransfer?.files?.[0])
}

function removeFile(which: 'a' | 'b') {
  slotOf(which).value = null
  inputError.value = ''
  if (isSampleResult.value) result.value = null
}

// ---------------------------------------------------------------- 运行

type RunState = 'idle' | 'uploading' | 'running' | 'done' | 'error'

const runState = ref<RunState>('idle')
const runError = ref('')
const runMsg = ref('')
const runPct = ref(0)
const sessionId = ref('')
const result = ref<SrdAssessment | null>(null)
const isSampleResult = computed(() => result.value?.isSample === '1')
let pollTimer: ReturnType<typeof setTimeout> | null = null

const sampleMode = computed(() => Boolean(slotA.value?.sample && slotB.value?.sample))
const bothReal = computed(() => Boolean(slotA.value?.file && slotB.value?.file))
const busy = computed(() => runState.value === 'uploading' || runState.value === 'running')
/**
 * 真跑要登录、且两边都得是真文件；跑示例不用登录。
 *
 * 看的是 `bothReal` 而不是「两个槽都非空」：一真一示例的话示例那边根本没有 File，
 * `FormData.append` 会拿到 null。`acceptFile` 已经会腾空示例槽，这里是第二道闸。
 */
const canRun = computed(
  () => !busy.value && (sampleMode.value || (bothReal.value && isLoggedIn.value)),
)

/**
 * 载入示例：把两个槽填成示例综述的标题，运行时直接取库里的示例评估。
 *
 * **入口按钮（原 `srd.s016`「没有文件？载入两篇示例 PDF 试用」）已按要求撤除**，
 * 这条路径眼下没有触发点，`sampleMode` 恒为 false。示例数据、`/srd/sample` 与
 * `/srd/sample/export` 三处都还在，重新挂个按钮调 `loadDemo()` 即可恢复 ——
 * 所以刻意不删这段，删了再要就得连服务端一起重接。
 */
const sample = ref<SrdAssessment | null>(null)

async function loadDemo() {
  inputError.value = ''
  runError.value = ''
  try {
    if (!sample.value) sample.value = await api.get<SrdAssessment>('/srd/sample')
  } catch {
    sample.value = null
  }
  if (!sample.value) {
    // 没有 try/catch 的话，后端 5xx 会让异常逃逸出去：两个槽保持空、错误也永远赋不上
    // （赋值在 await 之后），按钮看起来像完全没反应。
    inputError.value = t('srd.runFailed')

    return
  }
  slotA.value = { file: null, name: pick(sample.value, 'reviewATitle'), size: 0, sample: true }
  slotB.value = { file: null, name: pick(sample.value, 'reviewBTitle'), size: 0, sample: true }
}

function stopPolling() {
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = null
}

function failRun(msg: string) {
  stopPolling()
  runState.value = 'error'
  runError.value = msg
}

/** 轮询任务状态直到终态。3 秒一次 —— 一次评估通常几分钟，打得再密也只是白问 */
async function poll() {
  const res = await authedCall(`/srd/assessments/${sessionId.value}/state`, 'GET')
  if (!res.ok) return failRun(res.message)

  const state = (res.envelope?.data ?? {}) as Record<string, unknown>
  runMsg.value = String(state.message ?? '')
  runPct.value = Math.min(100, Number(state.progress ?? 0))

  const status = String(state.runStatus ?? '')
  if (status === 'completed') {
    stopPolling()
    await openAssessment(Number(state.assessmentId ?? 0))
    void loadHistory()

    return
  }
  if (status === 'failed' || status === 'stopped') {
    void loadHistory()

    return failRun(String(state.errorMsg || '') || t(status === 'stopped' ? 'srd.runStopped' : 'srd.runFailed'))
  }
  pollTimer = setTimeout(poll, 3000)
}

async function runAssess() {
  if (!canRun.value) return
  stopPolling()
  runError.value = ''
  runMsg.value = ''
  runPct.value = 0

  if (sampleMode.value) {
    result.value = sample.value
    runState.value = sample.value ? 'done' : 'error'
    if (!sample.value) runError.value = t('srd.runFailed')

    return
  }

  runState.value = 'uploading'
  result.value = null
  const form = new FormData()
  form.append('fileA', slotA.value!.file as File, slotA.value!.name)
  form.append('fileB', slotB.value!.file as File, slotB.value!.name)

  const res = await authedCall('/srd/assessments', 'POST', form)
  if (!res.ok) return failRun(res.message)
  sessionId.value = String(res.envelope?.data ?? '')
  if (!sessionId.value) return failRun(t('srd.runFailed'))

  runState.value = 'running'
  runMsg.value = t('srd.stQueued')
  void loadHistory()
  pollTimer = setTimeout(poll, 2000)
}

async function stopRun() {
  if (!sessionId.value) return
  stopPolling()
  await authedCall(`/srd/assessments/${sessionId.value}/stop`, 'POST')
  runState.value = 'idle'
  runMsg.value = ''
  void loadHistory()
}

/** 取一次评估的完整结果（真跑跑完、或从历史里点开，走的是同一条路） */
async function openAssessment(assessmentId: number) {
  if (!assessmentId) return failRun(t('srd.runFailed'))
  const res = await authedCall(`/srd/assessments/${assessmentId}`, 'GET')
  if (!res.ok) return failRun(res.message)
  result.value = (res.envelope?.data ?? null) as SrdAssessment | null
  runState.value = result.value ? 'done' : 'error'
  if (!result.value) runError.value = t('srd.runFailed')
}

onBeforeUnmount(stopPolling)

// ---------------------------------------------------------------- 历史

const history = ref<SrdHistoryRow[]>([])
const historyLoading = ref(false)

async function loadHistory() {
  if (!isLoggedIn.value) {
    history.value = []

    return
  }
  historyLoading.value = true
  const res = await authedCall('/srd/assessments', 'GET')
  historyLoading.value = false
  history.value = res.ok ? ((res.envelope?.data ?? []) as SrdHistoryRow[]) : []
}

async function viewHistory(row: SrdHistoryRow) {
  if (row.runStatus !== 'completed') return
  stopPolling()
  runError.value = ''
  await openAssessment(row.assessmentId)
  if (import.meta.client) document.getElementById('results')?.scrollIntoView({ behavior: 'smooth' })
}

async function removeHistory(row: SrdHistoryRow) {
  if (import.meta.client && !window.confirm(t('srd.histConfirmDelete'))) return
  const res = await authedCall(`/srd/assessments/${row.assessmentId}`, 'DELETE')
  if (!res.ok) return
  history.value = history.value.filter((r) => r.assessmentId !== row.assessmentId)
  if (result.value?.assessmentId === row.assessmentId) {
    result.value = null
    runState.value = 'idle'
  }
}

/**
 * 落地时 URL 指名要打开的评估（`?assessment=`，来自「我的账号」页的「查看结果」）。
 * 要登录才取得到，而登录态水合后才知道，所以挂载时与登录态变化时各试一次，打开过就清掉
 */
let wantAssessmentId: number | null = null

async function openWanted() {
  if (!wantAssessmentId || !isLoggedIn.value) return
  const id = wantAssessmentId
  wantAssessmentId = null
  stopPolling()
  runError.value = ''
  await openAssessment(id)
  if (import.meta.client) document.getElementById('results')?.scrollIntoView({ behavior: 'smooth' })
}

/** 登录态是水合后才知道的（全站预渲染），所以历史只能在客户端挂载后取 */
onMounted(() => {
  const wanted = Number(typeof route.query.assessment === 'string' ? route.query.assessment : '')
  if (Number.isInteger(wanted) && wanted > 0) wantAssessmentId = wanted
  void loadHistory()
  void openWanted()
})
watch(isLoggedIn, () => {
  void loadHistory()
  void openWanted()
})

const stamp = (iso: string | null) => {
  if (!iso) return { date: '', time: '' }
  const d = new Date(iso.replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return { date: iso, time: '' }
  const locale = isEn.value ? 'en-GB' : 'zh-CN'

  return {
    date: d.toLocaleDateString(locale),
    time: d.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', hour12: false }),
  }
}

const HIST_STATUS_KEY: Record<string, string> = {
  pending: 'srd.stQueued',
  running: 'srd.stRunning',
  failed: 'srd.stFailed',
  stopped: 'srd.stStopped',
}

// ---------------------------------------------------------------- 结果展示

/** 环周长：r=56 → 2πr */
const CIRC = 2 * Math.PI * 56
const ringDash = computed(() => {
  const pct = result.value?.overallPct ?? 0

  return `${((pct / 100) * CIRC).toFixed(1)} ${CIRC.toFixed(1)}`
})

/** 「得分 55/102」——满分用可评分满分，与名义满分不等时说明有条目证据不足被剔出了分母 */
const overallScoreText = computed(() => {
  const r = result.value
  if (!r || r.overallScoreMax == null) return ''

  return `${r.overallScoreSum ?? 0}/${r.overallScoreMax}`
})
const scoreDenominatorNote = computed(() => {
  const r = result.value
  if (!r || !r.overallScoreMaxFull || r.overallScoreMax === r.overallScoreMaxFull) return ''

  return t('srd.scoreDropped', { full: r.overallScoreMaxFull, n: r.unclearCount ?? 0 })
})

/**
 * 条目的两条原文引用。
 *
 * 引擎产出的是「原文逐字 `cite_a` + 中文翻译 `cite_a_zh`」，落库时逐字原文进了
 * `citeAEn` 那一格 —— 那一格装的是**原语言**，不一定是英文（中文文献就是中文）。
 *
 * 所以这里**不能用 `pick()`**：pick 在中文界面一律取 `citeAZh`，于是上传英文文献、
 * 「原文引用」一栏却全是中文译文。逐字引用是人工复核时唯一能回到原文去核的依据，
 * 一经翻译就核不动了 —— 主行永远是原文，译文只在中文界面、且确实与原文不同时
 * （中文文献两栏同值）作为附注跟在后面，还得由上面那个开关点开。
 */
const showTrans = ref(false)

const oneCite = (raw: string | null, zh: string | null) => {
  const text = (raw || '').trim() || (zh || '').trim()
  const tr = (zh || '').trim()

  return { text, tr: !isEn.value && tr && tr !== text ? tr : '' }
}
const cites = (it: SrdItem) => [
  { tag: 'A', ...oneCite(it.citeAEn, it.citeAZh) },
  { tag: 'B', ...oneCite(it.citeBEn, it.citeBZh) },
]

/** 有译文可看才给开关 —— 中文文献的译文与原文同值，开关点开也不会有任何变化 */
const hasTrans = computed(() =>
  Boolean(
    result.value?.domains.some((d) =>
      d.groups.some((g) => g.items.some((it) => cites(it).some((c) => c.tr))),
    ),
  ),
)

// ---------------------------------------------------------------- 导出 xlsx

/**
 * 导出当前这份结果。
 *
 * 排版在后端（`srd_export_service`），前端只负责把字节存成文件：xlsx 的写库
 * （SheetJS / exceljs）压进这个静态站要几百 KB，而后端本来就装着 openpyxl。
 *
 * 示例走公开口、真实评估走要登录的那条 —— 与「看」的可见性规则一一对应。
 * 文件名在这里拼：后端回的是裸字节流，中文文件名进 `Content-Disposition`
 * 还要 RFC 5987 编码，不如交给浏览器侧。
 */
const exporting = ref(false)
const exportError = ref('')

/** yyyyMMdd，给文件名用。同一份结果导两次不会互相覆盖靠的是这个 + 评估 id */
const today = () => {
  const d = new Date()

  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  // 立刻 revoke 会在部分浏览器里赶在下载真正开始之前把 URL 撤掉，下载直接失败
  setTimeout(() => URL.revokeObjectURL(url), 10000)
}

async function exportXlsx() {
  const r = result.value
  if (!r || exporting.value) return
  exporting.value = true
  exportError.value = ''

  const lang = isEn.value ? 'en' : 'zh'
  const path = isSampleResult.value
    ? `/srd/sample/export?lang=${lang}`
    : `/srd/assessments/${r.assessmentId}/export?lang=${lang}`
  const res = await authedBlob(path)
  exporting.value = false

  if (!res.ok || !res.blob) {
    exportError.value = res.message || t('srd.runFailed')

    return
  }
  // 文件名的前缀是站点文案（后台可改），剔掉文件名非法字符再用：
  // 一个 `/` 就能让 `a.download` 被浏览器整个忽略、存成 "download"
  const base = t('srd.exportFilename').replace(/[\\/:*?"<>|]/g, '').trim() || 'SRD'
  saveBlob(res.blob, `${base}-${r.assessmentId}-${today()}.xlsx`)
}

useReveal()
</script>

<template>
  <div class="page-srd">
    <!-- ===================== 工具工作区 ===================== -->
    <section class="tool" id="tool">
      <div class="wrap">
        <span class="kicker reveal">{{ t('srd.s001') }}</span>
        <h2 class="title reveal">{{ t('srd.s002') }}</h2>
        <p class="lead reveal">{{ t('srd.s003') }}</p>

        <div class="io-grid" style="margin-top:clamp(24px,3vw,32px)">
          <!-- 综述 A / B：两张卡除了标签与文案完全同构 -->
          <div
            v-for="s in ([
              { key: 'a', tag: 'A', slot: slotA, head: 'srd.s004', sub: 'srd.s005', drop: 'srd.s006', hint: 'srd.s007', rm: 'srd.s008' },
              { key: 'b', tag: 'B', slot: slotB, head: 'srd.s009', sub: 'srd.s010', drop: 'srd.s011', hint: 'srd.s012', rm: 'srd.s013' },
            ] as const)"
            :key="s.key"
            class="src-card reveal"
            :class="s.key"
          >
            <div class="src-head">
              <span class="src-tag" aria-hidden="true">{{ s.tag }}</span>
              <div><h3>{{ t(s.head) }}</h3><p>{{ t(s.sub) }}</p></div>
            </div>
            <label
              v-if="!s.slot"
              class="pdf-drop"
              :class="{ drag: dragging === s.key }"
              @dragover.prevent="dragging = s.key"
              @dragleave="dragging = ''"
              @drop.prevent="onDrop(s.key, $event)"
            >
              <input
                type="file" accept="application/pdf,.pdf" class="pdf-input" hidden
                :aria-label="t(s.drop)" @change="onPick(s.key, $event)"
              />
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M12 16V4m0 0 4 4m-4-4-4 4" /><path d="M5 20h14" /></svg>
              <span class="pd-title">{{ t(s.drop) }}</span>
              <span class="pd-sub">{{ t(s.hint) }}</span>
            </label>
            <div v-else class="pdf-file">
              <span class="pf-ic" aria-hidden="true">PDF</span>
              <div class="pf-meta">
                <b class="pf-name">{{ s.slot.name }}</b>
                <span class="pf-size">{{ s.slot.sample ? t('srd.sampleFile') : fmtSize(s.slot.size) }}</span>
              </div>
              <button type="button" class="pf-rm" :aria-label="t(s.rm)" @click="removeFile(s.key)">{{ t(s.rm) }}</button>
            </div>
          </div>
        </div>

        <p v-if="inputError" class="io-err">{{ inputError }}</p>

        <div class="run-bar reveal">
          <button
            type="button" class="btn btn-primary btn-lg" id="runBtn"
            :disabled="!canRun" @click="runAssess"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" aria-hidden="true"><path d="M5 3l14 9-14 9V3Z" /></svg>
            <span>{{ t('srd.s014') }}</span>
          </button>

          <!-- 未登录时把「为什么按钮点不动」说清楚，而不是让它默默灰着 -->
          <p v-if="bothReal && !isLoggedIn" class="login-gate">
            {{ t('srd.needLogin') }}
            <NuxtLink :to="loginLink">{{ t('srd.needLoginCta') }}</NuxtLink>
          </p>

          <div v-if="busy" class="run-prog">
            <div class="rp-bar"><i :style="{ width: (runState === 'uploading' ? 3 : Math.max(3, runPct)) + '%' }"></i></div>
            <div class="rp-foot">
              <span class="rp-msg">{{ runState === 'uploading' ? t('srd.stUploading') : (runMsg || t('srd.stRunning')) }}</span>
              <span class="rp-pct">{{ runState === 'uploading' ? '' : runPct + '%' }}</span>
              <button v-if="runState === 'running'" type="button" class="btn btn-ghost btn-sm" @click="stopRun">
                {{ t('srd.btnStop') }}
              </button>
            </div>
            <p class="rp-note">{{ t('srd.runLongHint') }}</p>
          </div>

          <span v-else class="run-note"><svg class="spark" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" /></svg><span id="runHint">{{ t('srd.s015') }}</span></span>
        </div>

        <!-- 方法说明 -->
        <details class="method reveal" id="method">
          <summary>
            <span class="mi" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 3l8 4v6c0 4.5-3.2 7-8 8-4.8-1-8-3.5-8-8V7z" /><path d="M12 8v5M12 16h.01" /></svg></span>
            <span>{{ t('srd.s017') }}</span>
            <small>{{ t('srd.s018') }}</small>
            <svg class="mcaret" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
          </summary>
          <div class="method-body">
            <!-- ① 条目评分：这是最容易读反的一层，放在最前面 -->
            <div class="mh" style="margin-top:20px">{{ t('srd.scoreTitle') }}</div>
            <!-- role 是显式补的：li 用了 display:contents（见样式），加上 list-style:none，
                 部分读屏器会把列表语义整个丢掉 -->
            <ul class="scale sc-scale" role="list">
              <li v-for="r in RT_ORDER" :key="r" role="listitem">
                <span class="lv"><span class="sc" :class="rtClass(r)">{{ rtLabel(r) }}</span></span>
                <span class="rng">{{ r === 'unclear' ? t('srd.scoreNone') : t('srd.scorePoints', { n: r }) }}</span>
                <span class="ds">{{ t(`srd.rt${r === 'unclear' ? 'Unclear' : r}Desc`) }}</span>
              </li>
            </ul>
            <p class="sc-formula">{{ t('srd.scoreFormula') }}</p>

            <div class="method-cols">
              <div>
                <div class="mh">{{ t('srd.s019') }}</div>
                <ul class="scale" role="list">
                  <li role="listitem"><span class="lv"><span class="lvl lvl-none">{{ t('srd.s020') }}</span></span><span class="rng">0–25%</span><span class="ds">{{ t('srd.s021') }}</span></li>
                  <li role="listitem"><span class="lv"><span class="lvl lvl-low">{{ t('srd.s022') }}</span></span><span class="rng">26–50%</span><span class="ds">{{ t('srd.s023') }}</span></li>
                  <li role="listitem"><span class="lv"><span class="lvl lvl-mod">{{ t('srd.s024') }}</span></span><span class="rng">51–75%</span><span class="ds">{{ t('srd.s025') }}</span></li>
                  <li role="listitem"><span class="lv"><span class="lvl lvl-high">{{ t('srd.s026') }}</span></span><span class="rng">76–100%</span><span class="ds">{{ t('srd.s027') }}</span></li>
                </ul>
              </div>
              <div>
                <div class="mh">{{ t('srd.s028') }}</div>
                <div class="dom-legend">
                  <p v-html="t('srd.s029')"></p>
                  <p>{{ t('srd.s030') }}</p>
                  <p>{{ t('srd.s031') }}</p>
                </div>
              </div>
            </div>
          </div>
        </details>
      </div>
    </section>

    <!-- ===================== 结果区 ===================== -->
    <section class="sec results" id="results">
      <div class="wrap">
        <span v-if="isSampleResult" class="res-flag"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 9v4M12 17h.01" /><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" /></svg><span>{{ t('srd.s032') }}</span></span>

        <div v-if="!result && !runError" id="resEmpty" class="res-empty">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="2" /><path d="M8 10h8M8 14h5" /></svg>
          <b>{{ t('srd.s033') }}</b>
          <p>{{ t('srd.s034') }}</p>
        </div>
        <p v-if="runError" class="res-empty" style="color:var(--cinnabar)">{{ runError }}</p>

        <div v-if="result" id="resContent">
          <div class="verdict">
            <div class="gauge">
              <div class="ring">
                <svg width="132" height="132" viewBox="0 0 132 132" aria-hidden="true">
                  <circle cx="66" cy="66" r="56" fill="none" stroke="rgba(255,255,255,.14)" stroke-width="12" />
                  <circle
                    cx="66" cy="66" r="56" fill="none"
                    :stroke="ringColor(result.overallLevel)"
                    stroke-width="12" stroke-linecap="round" :stroke-dasharray="ringDash"
                  />
                </svg>
                <div class="pctn"><b>{{ result.overallPct }}%</b><span>{{ t('srd.overallOverlap') }}</span></div>
              </div>
              <span class="lvl" :class="lvClass(result.overallLevel)" style="font-size:13px">{{ lvLabel(result.overallLevel) }}</span>
              <span v-if="overallScoreText" class="gauge-score">{{ t('srd.scoreLabel') }} {{ overallScoreText }}</span>
            </div>
            <div class="verdict-main">
              <h2>{{ t('srd.overallVerdict') }}<span class="em">{{ lvLabel(result.overallLevel) }}</span></h2>
              <!-- 两篇标题各占一行、标签对齐：挤在一行里靠「·」分隔的写法，
                   在两个英文长标题下会折成一团分不清哪句是哪篇 -->
              <div class="vpair">
                <p><b>{{ t('srd.reviewA') }}</b><span>{{ pick(result, 'reviewATitle') }}</span></p>
                <p><b>{{ t('srd.reviewB') }}</b><span>{{ pick(result, 'reviewBTitle') }}</span></p>
              </div>
              <p class="verdict-rec">{{ pick(result, 'overallReason') }}</p>
              <p v-if="result.provisional === '1'" class="prov-note">{{ t('srd.provisional') }}</p>
              <p v-if="scoreDenominatorNote" class="prov-note soft">{{ scoreDenominatorNote }}</p>
            </div>
          </div>

          <div class="dom-tiles">
            <div v-for="d in result.domains" :key="d.domainId" class="dtile">
              <div class="dt-top">
                <span class="dt-name">{{ t('srd.lblDomain') }} {{ d.seq }}<small>{{ pick(d, 'name') }}{{ d.isKey === '1' ? ' · ' + t('srd.keyShort') : '' }}</small></span>
                <span class="lvl" :class="lvClass(d.level)">{{ lvLabel(d.level) }}</span>
              </div>
              <div class="bar"><i :style="{ width: (d.level ? (d.pct ?? 0) : 0) + '%', background: barColor(d.level) }"></i></div>
              <!-- level 为空＝一条都没判出来。这时 pct 是 0，照直显示「0% 重叠」等于替模型下了
                   「两篇毫无重叠」这个结论，所以只画一条横杠 -->
              <div class="dt-pct">
                <b>{{ d.level ? d.pct + '%' : '—' }}</b> <span>{{ t('srd.lblOverlap') }}</span>
                <span v-if="d.scoreMax" class="dt-score">{{ t('srd.scoreLabel') }} {{ d.scoreSum }}/{{ d.scoreMax }}</span>
              </div>
              <div v-if="d.evidenceSufficient === '0' || d.nearBoundary === '1'" class="dt-flags">
                <span v-if="d.evidenceSufficient === '0'">{{ t('srd.flagEvidence', { n: d.unclearCount ?? 0 }) }}</span>
                <span v-if="d.nearBoundary === '1'">{{ t('srd.flagBoundary') }}</span>
              </div>
            </div>
          </div>

          <div class="res-tools">
            <h3>{{ t('srd.itemTitle') }}</h3>
            <div class="rt-btns">
              <label v-if="hasTrans" class="tr-toggle">
                <input v-model="showTrans" type="checkbox" />
                <span>{{ t('srd.showTrans') }}</span>
              </label>
              <button type="button" class="btn btn-ghost btn-sm" :disabled="exporting" @click="exportXlsx">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M12 4v11m0 0 4-4m-4 4-4-4" /><path d="M5 19h14" /></svg>
                <span>{{ exporting ? t('srd.exporting') : t('srd.exportXlsx') }}</span>
              </button>
            </div>
          </div>
          <p v-if="exportError" class="io-err" style="margin-bottom:12px">{{ exportError }}</p>
          <details v-for="d in result.domains" :key="'rd-' + d.domainId" class="rd" :open="d.isKey === '1'">
            <summary>
              <span class="rd-badge">{{ d.seq }}</span>
              <span class="rd-dn">
                <b>{{ t('srd.lblDomain') }} {{ d.seq }} · {{ pick(d, 'name') }}</b>
                <span>
                  {{ d.isKey === '1' ? t('srd.keyDomain') : t('srd.nonKeyDomain') }} ·
                  {{ t('srd.domainOverlap') }} {{ d.level ? d.pct + '%' : '—' }} ·
                  {{ t('srd.scoreLabel') }} {{ d.scoreSum }}/{{ d.scoreMax }}
                </span>
              </span>
              <span v-if="d.isKey === '1'" class="keych" style="margin-right:6px">{{ t('srd.keyShort') }}</span>
              <span class="lvl" :class="lvClass(d.level)">{{ lvLabel(d.level) }}</span>
              <svg class="rd-caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
            </summary>
            <div class="rd-body">
              <table class="srd">
                <thead>
                  <tr>
                    <th>{{ t('srd.thNo') }}</th>
                    <th>{{ t('srd.thQuestion') }}</th>
                    <th>{{ t('srd.thScore') }}</th>
                    <th>{{ t('srd.thBasis') }}</th>
                    <th>{{ t('srd.thCite') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <template v-for="g in d.groups" :key="g.groupId">
                    <tr class="grp">
                      <td colspan="5" style="background:var(--indigo-100);font-weight:700;color:var(--indigo-800);font-size:12px">
                        <span>{{ t('srd.lblGroup') }} {{ g.code }} · {{ pick(g, 'name') }}</span>
                      </td>
                    </tr>
                    <tr v-for="it in g.items" :key="it.itemId">
                      <td class="c-id">{{ it.code }}</td>
                      <td class="c-q">
                        {{ pick(it, 'question') }}
                        <span v-if="it.needsReview === '1'" class="rvch" :title="it.reviewNote || ''">{{ t('srd.needsReview') }}</span>
                      </td>
                      <td class="c-v">
                        <span class="sc" :class="rtClass(it.rating)">{{ rtLabel(it.rating) }}</span>
                        <div class="c-pts">{{ it.score == null ? '—' : t('srd.scorePoints', { n: it.score }) }}</div>
                      </td>
                      <td class="c-basis">
                        {{ pick(it, 'basis') }}
                        <div v-if="it.evidenceCard" class="evcard">{{ it.evidenceCard }}</div>
                      </td>
                      <td class="c-cite">
                        <span
                          v-for="c in cites(it)" :key="c.tag"
                          class="cite" :class="c.tag.toLowerCase()"
                        >
                          <em>{{ c.tag }}</em>
                          <span class="cq" :class="{ none: !c.text }">{{ c.text || t('srd.citeEmpty') }}</span>
                          <span v-if="showTrans && c.tr" class="ctr">{{ c.tr }}</span>
                        </span>
                      </td>
                    </tr>
                  </template>
                </tbody>
              </table>
            </div>
          </details>
        </div>
      </div>
    </section>

    <!-- ===================== 评估历史 ===================== -->
    <section class="sec history" id="history" style="background:var(--surface)">
      <div class="wrap">
        <div class="sec-head" style="display:flex;align-items:flex-end;justify-content:space-between;gap:20px;flex-wrap:wrap">
          <div>
            <span class="kicker reveal">{{ t('srd.s035') }}</span>
            <h2 class="title reveal">{{ t('srd.s036') }}</h2>
          </div>
          <button
            v-if="isLoggedIn" type="button" class="btn btn-ghost btn-sm"
            :disabled="historyLoading" @click="loadHistory"
          >
            {{ t('srd.histRefresh') }}
          </button>
        </div>

        <div v-if="!isLoggedIn" class="hist-empty">
          {{ t('srd.histNeedLogin') }}
          <NuxtLink :to="loginLink">{{ t('srd.needLoginCta') }}</NuxtLink>
        </div>
        <div v-else-if="!history.length" class="hist-empty">{{ t('srd.histEmpty') }}</div>
        <div v-else class="hist-list">
          <div v-for="row in history" :key="row.assessmentId" class="hist-row">
            <div class="h-when">
              <b>{{ stamp(row.createTime).date }}</b>
              <span>{{ stamp(row.createTime).time }}</span>
            </div>
            <div class="h-titles">
              <div class="ht"><em>A</em><span>{{ pick(row, 'reviewATitle') }}</span></div>
              <div class="ht b"><em>B</em><span>{{ pick(row, 'reviewBTitle') }}</span></div>
            </div>
            <div class="h-verdict">
              <template v-if="row.runStatus === 'completed'">
                <span class="lvl" :class="lvClass(row.overallLevel)">{{ lvLabel(row.overallLevel) }}</span>
                <span class="h-num">{{ row.overallPct }}% · {{ row.overallScoreSum }}/{{ row.overallScoreMax }}</span>
              </template>
              <template v-else>
                <span class="h-state" :class="{ bad: row.runStatus === 'failed' }">
                  {{ t(HIST_STATUS_KEY[row.runStatus ?? 'pending'] ?? 'srd.stQueued') }}
                  <template v-if="row.runStatus === 'running'">{{ row.progress }}%</template>
                </span>
                <span v-if="row.errorMsg" class="h-num">{{ row.errorMsg }}</span>
              </template>
            </div>
            <div class="h-acts">
              <button
                type="button" class="btn btn-ghost btn-sm"
                :disabled="row.runStatus !== 'completed'" @click="viewHistory(row)"
              >
                {{ t('srd.histView') }}
              </button>
              <button type="button" class="h-del" :aria-label="t('srd.histDelete')" @click="removeHistory(row)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" /></svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style>
.page-srd .skip-link{position:absolute;left:12px;top:-60px;z-index:var(--z-toast);background:var(--indigo-700);color:#fff;
    font-weight:600;font-size:15px;padding:12px 20px;border-radius:10px;transition:top .2s var(--ease)}
.page-srd .sec{padding:clamp(40px,5.5vw,72px) 0;scroll-margin-top:88px}
.page-srd .kicker.on-dark{color:var(--indigo-200)}
.page-srd h2.title{font-size:clamp(1.6rem,3vw,2.2rem);color:var(--indigo-900);letter-spacing:-.02em;text-wrap:balance;max-width:26ch}
.page-srd .lead{color:var(--muted);font-size:clamp(1rem,1.4vw,1.12rem);max-width:68ch;margin-top:16px;text-wrap:pretty}
.page-srd .btn{display:inline-flex;align-items:center;justify-content:center;gap:9px;padding:13px 24px;border-radius:999px;font-weight:600;font-size:15px;
    border:1.5px solid transparent;cursor:pointer;white-space:nowrap;
    transition:transform .25s var(--ease),background-color .25s var(--ease),box-shadow .25s var(--ease),border-color .25s var(--ease)}
.page-srd .btn-primary:disabled{background:var(--indigo-300);box-shadow:none;cursor:not-allowed;transform:none}
.page-srd .btn-ghost:disabled{opacity:.45;cursor:not-allowed}
.page-srd .btn-lg{padding:15px 30px;font-size:16px}
.page-srd .phero{position:relative;overflow:hidden;background:var(--indigo-900);color:#fff;isolation:isolate}
.page-srd .phero::before{content:"";position:absolute;inset:0;z-index:-1;
    background:radial-gradient(1000px 560px at 90% 0%,rgba(44,127,114,.5),transparent 60%),
    radial-gradient(680px 460px at 2% 100%,rgba(15,111,106,.28),transparent 65%),
    linear-gradient(160deg,#0d1a17 0%,#12211d 44%,#183029 100%)}
.page-srd .phero .wrap{padding:clamp(28px,3.6vw,40px) clamp(20px,4vw,44px) clamp(40px,5vw,56px)}
.page-srd .crumb{display:flex;align-items:center;gap:9px;font-size:13.5px;color:rgba(233,238,247,.66);margin-bottom:24px;flex-wrap:wrap}
.page-srd .phero-tag{display:inline-flex;align-items:center;gap:10px;font-size:13px;font-weight:600;letter-spacing:.02em;color:var(--indigo-200);
    background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.16);padding:8px 16px;border-radius:999px;backdrop-filter:blur(4px)}
.page-srd .phero h1{font-size:clamp(1.9rem,3.8vw,3rem);font-weight:700;letter-spacing:-.025em;margin:18px 0 0;text-wrap:balance;line-height:1.14}
.page-srd .phero .psub{margin-top:18px;font-size:clamp(1rem,1.4vw,1.14rem);color:rgba(233,238,247,.9);max-width:66ch;line-height:1.7;text-wrap:pretty}
.page-srd .phero-steps{display:flex;flex-wrap:wrap;gap:10px;margin-top:28px}
.page-srd .phero-steps span{display:inline-flex;align-items:center;gap:9px;font-size:13.5px;font-weight:600;color:rgba(233,238,247,.86);
    background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.14);padding:9px 15px;border-radius:999px}
.page-srd .phero-steps span i{width:20px;height:20px;border-radius:6px;background:var(--indigo-600);color:#fff;display:inline-flex;align-items:center;justify-content:center;
    font-family:"Spectral",serif;font-weight:700;font-size:11.5px;font-style:normal}
.page-srd .phero-steps .sep2{background:none;border:none;padding:0;color:rgba(233,238,247,.4)}
.page-srd .tool{padding:clamp(36px,5vw,64px) 0}
/* minmax(0,·) 而不是 1fr：1fr 的最小轨道是 min-content，
   选中的 PDF 文件名是一串不换行的长文本，会把整列顶宽、两张卡跟着不等宽 */
.page-srd .io-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px}
.page-srd .src-card{min-width:0;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-lg);padding:22px 22px 20px;display:flex;flex-direction:column;gap:14px;
    transition:border-color .25s var(--ease),box-shadow .25s var(--ease)}
.page-srd .src-card:focus-within{border-color:var(--indigo-300);box-shadow:var(--shadow-sm)}
.page-srd .src-head{display:flex;align-items:center;gap:12px}
.page-srd .src-tag{width:38px;height:38px;flex-shrink:0;border-radius:11px;background:var(--indigo-700);color:#fff;display:flex;align-items:center;justify-content:center;
    font-family:"Spectral",serif;font-weight:700;font-size:17px}
.page-srd .src-card.b .src-tag{background:var(--info)}
.page-srd .src-head h3{font-size:1.1rem;color:var(--indigo-900)}
.page-srd .src-head p{font-size:12.5px;color:var(--muted);margin-top:1px}
.page-srd .io-err{margin-top:12px;font-size:13.5px;font-weight:600;color:var(--cinnabar-d)}
.page-srd .pdf-drop{display:flex;flex-direction:column;align-items:center;gap:5px;text-align:center;cursor:pointer;
    border:1.6px dashed var(--indigo-200);border-radius:14px;padding:30px 18px;background:var(--paper);transition:.2s var(--ease)}
.page-srd .pdf-drop:hover,.page-srd .pdf-drop:focus-within{border-color:var(--indigo-500);background:var(--indigo-100)}
.page-srd .pdf-drop.drag{border-color:var(--cinnabar);background:var(--indigo-100)}
.page-srd .pdf-drop svg{width:30px;height:30px;color:var(--indigo-500);margin-bottom:4px}
.page-srd .pdf-drop .pd-title{font-weight:700;color:var(--indigo-800);font-size:14px}
.page-srd .pdf-drop .pd-sub{font-size:12px;color:var(--muted)}
.page-srd .pdf-file{display:flex;align-items:center;gap:12px;border:1.5px solid var(--line);border-radius:12px;padding:13px 14px;background:var(--surface)}
.page-srd .pf-ic{width:38px;height:38px;flex-shrink:0;border-radius:9px;background:rgba(192,54,44,.09);color:var(--cinnabar-d);display:flex;align-items:center;justify-content:center;
    font-family:"Spectral",serif;font-weight:700;font-size:11px}
.page-srd .pf-meta{flex:1;min-width:0}
.page-srd .pf-name{display:block;font-size:13.5px;font-weight:600;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.page-srd .pf-size{font-size:12px;color:var(--muted)}
.page-srd .pf-rm{flex-shrink:0;font-family:inherit;font-size:12.5px;font-weight:600;color:var(--muted);background:var(--paper-2);border:1px solid var(--line);border-radius:999px;padding:5px 12px;cursor:pointer;transition:.2s}
.page-srd .pf-rm:hover{color:var(--cinnabar-d);border-color:var(--cinnabar)}
.page-srd .res-empty{text-align:center;padding:clamp(36px,5vw,60px) 20px;background:var(--surface);border:1.5px dashed var(--line);border-radius:var(--radius-lg)}
.page-srd .res-empty svg{width:42px;height:42px;color:var(--indigo-300);margin:0 auto 14px}
.page-srd .res-empty b{display:block;font-family:"Spectral","Noto Serif SC",serif;font-size:1.3rem;color:var(--indigo-900);margin-bottom:8px}
.page-srd .res-empty p{font-size:14px;color:var(--muted);max-width:52ch;margin:0 auto;line-height:1.6}
.page-srd .history{border-top:1px solid var(--line)}
.page-srd .hist-list{margin-top:clamp(22px,3vw,30px);display:flex;flex-direction:column;gap:10px}
.page-srd .hist-row{display:grid;grid-template-columns:110px minmax(0,1fr) 190px auto;gap:18px;align-items:center;
    background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:16px 18px;transition:.2s var(--ease)}
.page-srd .hist-row:hover{border-color:var(--indigo-200);box-shadow:var(--shadow-sm);background:var(--surface)}
.page-srd .h-when b{display:block;font-family:"Spectral",serif;font-weight:700;color:var(--indigo-900);font-size:14px;font-variant-numeric:tabular-nums}
.page-srd .h-when span{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
.page-srd .h-titles{min-width:0;font-size:13px;color:var(--ink);line-height:1.5}
.page-srd .h-titles .ht{display:flex;gap:7px;align-items:baseline}
.page-srd .h-titles em{font-style:normal;font-weight:700;font-size:11px;color:#fff;background:var(--indigo-600);border-radius:5px;padding:0 6px;flex-shrink:0}
.page-srd .h-titles .ht.b em{background:var(--info)}
.page-srd .h-titles .ht span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.page-srd .h-verdict{display:flex;flex-direction:column;align-items:flex-start;gap:5px;min-width:0}
.page-srd .h-num{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums;
    display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.page-srd .h-state{font-size:12.5px;font-weight:700;color:var(--indigo-600);font-variant-numeric:tabular-nums}
.page-srd .h-state.bad{color:var(--cinnabar-d)}
.page-srd .h-acts{display:flex;align-items:center;gap:8px}
.page-srd .h-del{width:34px;height:34px;flex-shrink:0;border-radius:9px;border:1px solid var(--line);background:var(--surface);color:var(--muted);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:.2s}
.page-srd .h-del:hover{color:var(--cinnabar-d);border-color:var(--cinnabar);background:rgba(192,54,44,.06)}
.page-srd .h-del svg{width:16px;height:16px}
.page-srd .hist-empty{text-align:center;padding:40px 20px;color:var(--muted);font-size:14px;background:var(--paper);border:1.5px dashed var(--line);border-radius:var(--radius-lg);margin-top:22px}
.page-srd .hist-empty a{color:var(--indigo-600);font-weight:600;text-decoration:underline;text-underline-offset:3px;margin-left:4px}
@media(max-width:820px){
.page-srd .hist-row{grid-template-columns:1fr;gap:10px}
.page-srd .h-acts{justify-content:flex-start}
}
.page-srd .run-bar{display:flex;flex-direction:column;align-items:center;gap:12px;margin-top:26px}
.page-srd .run-note{font-size:13px;color:var(--muted);display:inline-flex;align-items:center;gap:8px}
.page-srd .run-note .spark{color:var(--cinnabar)}
.page-srd .run-bar .btn-lg svg{width:19px;height:19px}
.page-srd .login-gate{font-size:13.5px;color:var(--cinnabar-d);font-weight:600}
.page-srd .login-gate a{color:var(--indigo-600);text-decoration:underline;text-underline-offset:3px;margin-left:6px}
.page-srd .run-prog{width:min(560px,100%);display:flex;flex-direction:column;gap:9px}
.page-srd .rp-bar{height:8px;border-radius:999px;background:var(--paper-2);border:1px solid var(--line);overflow:hidden}
.page-srd .rp-bar i{display:block;height:100%;border-radius:999px;background:var(--indigo-600);transition:width .5s var(--ease)}
.page-srd .rp-foot{display:flex;align-items:center;gap:12px}
.page-srd .rp-msg{flex:1;min-width:0;font-size:13px;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.page-srd .rp-pct{font-size:13px;font-weight:700;color:var(--indigo-700);font-variant-numeric:tabular-nums}
.page-srd .rp-note{font-size:12px;color:var(--muted);text-align:center}
.page-srd .method{margin-top:clamp(30px,4vw,44px);background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-lg);overflow:hidden}
.page-srd .method>summary{display:flex;align-items:center;gap:12px;padding:18px 22px;cursor:pointer;list-style:none;font-weight:600;color:var(--indigo-900);font-size:1.02rem}
.page-srd .method>summary::-webkit-details-marker{display:none}
.page-srd .method>summary .mi{width:34px;height:34px;border-radius:10px;background:var(--indigo-100);color:var(--indigo-600);display:flex;align-items:center;justify-content:center;flex-shrink:0}
.page-srd .method>summary .mi svg{width:19px;height:19px}
.page-srd .method>summary small{margin-left:auto;font-family:"Source Sans 3","Noto Sans SC",sans-serif;font-weight:600;font-size:12.5px;color:var(--muted)}
.page-srd .method .mcaret{width:20px;height:20px;color:#7d90ad;transition:transform .3s var(--ease)}
.page-srd .method[open] .mcaret{transform:rotate(180deg)}
.page-srd .method-body{padding:4px 22px 24px;border-top:1px solid var(--line)}
.page-srd .method-cols{display:grid;grid-template-columns:1fr 1.25fr;gap:24px;padding-top:20px}
.page-srd .mh{font-size:12.5px;font-weight:700;color:var(--indigo-900);text-transform:uppercase;letter-spacing:.03em;margin-bottom:12px;font-family:"Source Sans 3","Noto Sans SC",sans-serif}
/* 档位表：三列（色块标签 / 分值区间 / 说明）。
   前两列宽度**由内容决定**，不能写死 px —— 里头的 .lvl / .sc 是 white-space:nowrap 的胶囊，
   写死宽度时中文刚好塞得下、英文（"Completely different" / "Insufficient evidence"）会
   溢出色块并压在分值那列上，表现就是两段字重叠。max-content 让整列取最宽那格，
   各行仍然对齐。li 用 display:contents 把三个 span 直接交给 ul 的网格 —— 逐行各自
   grid 是对不齐的（没有 subgrid 时列宽不共享）。语义靠 role 显式补回来。 */
.page-srd .scale{display:grid;grid-template-columns:max-content max-content minmax(0,1fr);gap:8px 12px;align-items:center;font-size:13.5px;color:var(--ink)}
.page-srd .scale li{display:contents}
.page-srd .scale .lv{font-weight:700}
.page-srd .scale .rng{font-variant-numeric:tabular-nums;color:var(--muted);font-size:12.5px}
.page-srd .scale .ds{color:var(--muted);font-size:12.5px}
.page-srd .sc-formula{margin-top:12px;padding:11px 14px;border-radius:10px;background:var(--paper-2);border:1px solid var(--line);
    font-size:12.5px;color:var(--muted);line-height:1.6}
.page-srd .dom-legend{display:flex;flex-direction:column;gap:9px;font-size:13px;color:var(--muted);line-height:1.55}
.page-srd .dom-legend b{color:var(--indigo-800)}
.page-srd .keych{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:700;color:var(--cinnabar-d);background:rgba(192,54,44,.09);padding:2px 8px;border-radius:999px}
.page-srd .rvch{display:inline-block;margin-left:6px;font-size:10.5px;font-weight:700;color:var(--amber);background:var(--amber-bg);
    border:1px solid #e7d39a;padding:1px 7px;border-radius:999px;vertical-align:middle;cursor:help}
.page-srd .lvl{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:700;padding:4px 11px;border-radius:999px;white-space:nowrap}
.page-srd .lvl::before{content:"";width:7px;height:7px;border-radius:50%}
.page-srd .lvl-none{color:var(--info);background:var(--info-bg)}
.page-srd .lvl-none::before{background:var(--info)}
.page-srd .lvl-low{color:var(--indigo-600);background:var(--indigo-100)}
.page-srd .lvl-low::before{background:var(--indigo-500)}
.page-srd .lvl-mod{color:var(--amber);background:var(--amber-bg)}
.page-srd .lvl-mod::before{background:var(--amber)}
.page-srd .lvl-high{color:var(--cinnabar-d);background:rgba(192,54,44,.09)}
.page-srd .lvl-high::before{background:var(--cinnabar)}
/* level 为 null：不是第五档程度，是「没得判」，所以用中性灰而不是色阶两端任何一色 */
.page-srd .lvl-unknown{color:var(--muted);background:var(--paper-2)}
.page-srd .lvl-unknown::before{background:#9aa7b8}
/* 条目评分：0 分最重复→朱砂，3 分最不同→青。与上面的重复度色阶方向相反，刻意的 */
.page-srd .sc{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:700;padding:4px 11px;border-radius:8px;white-space:nowrap}
.page-srd .sc::before{content:"";width:7px;height:7px;border-radius:2px}
/* 色阶按重复程度排，不按分数大小排：3 分（完全相同）最重复 → 朱砂，0 分（完全不同）→ 青。
   看着像是反的，是因为分数与颜色本来就不同向，见 RT_CLASS 的注释。 */
.page-srd .sc-3{color:var(--cinnabar-d);background:rgba(192,54,44,.09)}
.page-srd .sc-3::before{background:var(--cinnabar)}
.page-srd .sc-2{color:var(--amber);background:var(--amber-bg)}
.page-srd .sc-2::before{background:var(--amber)}
.page-srd .sc-1{color:var(--indigo-600);background:var(--indigo-100)}
.page-srd .sc-1::before{background:var(--indigo-500)}
.page-srd .sc-0{color:var(--info);background:var(--info-bg)}
.page-srd .sc-0::before{background:var(--info)}
.page-srd .sc-u{color:var(--muted);background:var(--paper-2)}
.page-srd .sc-u::before{background:#9aa7b8}
.page-srd .results{background:var(--paper-2)}
.page-srd .res-flag{display:inline-flex;align-items:center;gap:9px;font-size:12.5px;font-weight:700;color:var(--amber);background:var(--amber-bg);
    border:1px solid #e7d39a;padding:7px 14px;border-radius:999px;margin-bottom:20px}
.page-srd .verdict{display:grid;grid-template-columns:auto 1fr;gap:clamp(20px,3vw,36px);align-items:center;
    background:var(--indigo-900);color:#fff;border-radius:var(--radius-lg);padding:clamp(24px,3vw,34px);position:relative;overflow:hidden;isolation:isolate}
.page-srd .verdict::before{content:"";position:absolute;inset:0;z-index:-1;background:radial-gradient(600px 300px at 100% 0,rgba(44,127,114,.4),transparent 60%)}
.page-srd .gauge{display:flex;flex-direction:column;align-items:center;gap:8px;min-width:150px}
.page-srd .gauge .ring{position:relative;width:132px;height:132px}
.page-srd .gauge svg{transform:rotate(-90deg)}
.page-srd .gauge .pctn{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
.page-srd .gauge .pctn b{font-family:"Spectral","Noto Serif SC",serif;font-weight:700;font-size:2rem;line-height:1;color:#fff}
.page-srd .gauge .pctn span{font-size:11px;color:rgba(233,238,247,.7);margin-top:3px;letter-spacing:.03em}
.page-srd .gauge-score{font-size:12px;color:rgba(233,238,247,.72);font-variant-numeric:tabular-nums}
.page-srd .verdict-main h2{font-family:"Spectral","Noto Serif SC",serif;font-size:clamp(1.5rem,2.6vw,2rem);color:#fff;letter-spacing:-.01em;line-height:1.16}
.page-srd .verdict-main h2 .em{color:#ffb4ad}
.page-srd .verdict-main .vpair{display:flex;flex-direction:column;gap:4px;margin-top:14px}
.page-srd .verdict-main .vpair p{display:flex;gap:10px;font-size:13.5px;color:rgba(233,238,247,.82);line-height:1.55}
/* min-width 而不是 width：英文的 "Review A" 比「综述 A」宽，写死宽度会让它在标签里换行。
   两行的标签内容等长，min-width 撑开后自然对齐 */
.page-srd .verdict-main .vpair b{flex-shrink:0;min-width:4.8em;white-space:nowrap;color:rgba(233,238,247,.6);
    font-weight:600;font-size:12px;letter-spacing:.02em;padding-top:1px}
.page-srd .verdict-main .vpair span{min-width:0}
.page-srd .verdict-rec{margin-top:14px;font-size:14.5px;color:rgba(233,238,247,.94);line-height:1.6;max-width:60ch}
/* 竖线用 .cite 那套 2px 圆角伪元素，与页面里已有的引用条同一个语汇 */
.page-srd .prov-note{position:relative;margin-top:12px;padding-left:12px;font-size:13px;line-height:1.6;color:#ffd9a3;max-width:60ch}
.page-srd .prov-note::before{content:"";position:absolute;left:0;top:4px;bottom:4px;width:2px;border-radius:2px;background:#e6a93c}
.page-srd .prov-note.soft{color:rgba(233,238,247,.72)}
.page-srd .prov-note.soft::before{background:rgba(233,238,247,.3)}
.page-srd .dom-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin-top:18px}
.page-srd .dtile{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px 18px 16px}
.page-srd .dtile .dt-top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px}
.page-srd .dtile .dt-name{font-weight:700;color:var(--indigo-900);font-size:14.5px}
.page-srd .dtile .dt-name small{display:block;font-family:"Source Sans 3","Noto Sans SC",sans-serif;font-weight:600;font-size:11px;color:var(--muted);margin-top:2px}
.page-srd .dtile .bar{height:7px;border-radius:999px;background:var(--paper-2);overflow:hidden;margin-bottom:8px}
.page-srd .dtile .bar i{display:block;height:100%;border-radius:999px}
.page-srd .dtile .dt-pct{font-size:12.5px;color:var(--muted);font-variant-numeric:tabular-nums}
.page-srd .dtile .dt-pct b{color:var(--indigo-800)}
.page-srd .dtile .dt-score{margin-left:8px;padding-left:8px;border-left:1px solid var(--line)}
.page-srd .dtile .dt-flags{margin-top:9px;display:flex;flex-wrap:wrap;gap:6px}
.page-srd .dtile .dt-flags span{font-size:11px;font-weight:600;color:var(--amber);background:var(--amber-bg);border:1px solid #e7d39a;padding:2px 8px;border-radius:999px}
.page-srd .res-tools{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;margin:26px 0 14px}
.page-srd .res-tools h3{font-size:1.2rem;color:var(--indigo-900)}
.page-srd .res-tools .rt-btns{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.page-srd .res-tools .rt-btns .btn svg{width:16px;height:16px}
.page-srd .rd{background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden;margin-bottom:12px}
.page-srd .rd>summary{display:flex;align-items:center;gap:14px;padding:16px 20px;cursor:pointer;list-style:none}
.page-srd .rd>summary::-webkit-details-marker{display:none}
.page-srd .rd-badge{width:30px;height:30px;flex-shrink:0;border-radius:9px;background:var(--indigo-100);color:var(--indigo-700);display:flex;align-items:center;justify-content:center;
    font-family:"Spectral",serif;font-weight:700;font-size:14px}
.page-srd .rd-dn{flex:1;min-width:0}
.page-srd .rd-dn b{font-size:1.02rem;color:var(--indigo-900);font-family:"Spectral","Noto Serif SC",serif;font-weight:600}
.page-srd .rd-dn span{display:block;font-size:12px;color:var(--muted);margin-top:1px}
.page-srd .rd-caret{width:19px;height:19px;color:#7d90ad;transition:transform .3s var(--ease);flex-shrink:0}
.page-srd .rd[open] .rd-caret{transform:rotate(180deg)}
.page-srd .rd-body{border-top:1px solid var(--line);overflow-x:auto}
.page-srd table.srd{width:100%;border-collapse:collapse;min-width:760px;font-size:13.5px}
.page-srd table.srd th{background:var(--paper-2);text-align:left;font-family:"Source Sans 3","Noto Sans SC",sans-serif;font-weight:700;font-size:12px;
    color:var(--indigo-800);letter-spacing:.02em;padding:11px 14px;border-bottom:1px solid var(--line);white-space:nowrap}
.page-srd table.srd td{padding:13px 14px;border-bottom:1px solid var(--line);vertical-align:top;line-height:1.55;color:var(--ink)}
.page-srd table.srd tr:last-child td{border-bottom:none}
.page-srd table.srd tr:hover td{background:var(--paper)}
.page-srd .c-id{font-family:"Spectral",serif;font-weight:700;color:var(--indigo-600);white-space:nowrap;width:44px}
.page-srd .c-q{min-width:200px;max-width:320px}
.page-srd .c-v{width:112px}
.page-srd .c-pts{font-size:11.5px;color:var(--muted);margin-top:5px;font-variant-numeric:tabular-nums}
.page-srd .c-basis{color:var(--muted);min-width:180px}
.page-srd .evcard{margin-top:7px;padding:7px 9px;border-radius:8px;background:var(--paper-2);border:1px solid var(--line);
    font-size:11.5px;line-height:1.5;color:var(--ink);white-space:pre-wrap}
.page-srd .c-cite{min-width:220px}
.page-srd .cite{display:block;font-size:12px;color:var(--muted);line-height:1.5;padding-left:12px;position:relative;margin-top:8px}
.page-srd .cite:first-of-type{margin-top:0}
.page-srd .cite::before{content:"";position:absolute;left:0;top:6px;bottom:6px;width:2px;border-radius:2px}
.page-srd .cite.a::before{background:var(--indigo-500)}
.page-srd .cite.b::before{background:var(--info)}
.page-srd .cite em{font-style:normal;font-weight:700;color:var(--indigo-700);margin-right:5px}
.page-srd .cite.b em{color:var(--info)}
/* 原文引用比判定依据更该被读到（它是能回原文核对的那一句），所以用正文色，
   不跟着 .cite 的 muted 走 */
.page-srd .cite .cq{color:var(--ink)}
.page-srd .cite .cq.none{color:var(--muted);font-style:italic}
.page-srd .cite .ctr{display:block;margin-top:3px;padding-left:1px;color:var(--muted);font-size:11.5px;line-height:1.5}
.page-srd .tr-toggle{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;font-weight:600;color:var(--muted);cursor:pointer;
    border:1px solid var(--line);background:var(--surface);border-radius:999px;padding:6px 14px 6px 11px;transition:.2s var(--ease)}
.page-srd .tr-toggle:hover{border-color:var(--indigo-300);color:var(--indigo-700)}
.page-srd .tr-toggle input{width:14px;height:14px;accent-color:var(--indigo-600);cursor:pointer}
@media(max-width:900px){
.page-srd .io-grid{grid-template-columns:minmax(0,1fr)}
.page-srd .method-cols{grid-template-columns:1fr;gap:20px}
.page-srd .verdict{grid-template-columns:1fr;text-align:center;justify-items:center}
.page-srd .gauge{min-width:0}
/* 窄屏整块居中，标签就不能再当左侧对齐列用了：一列左对齐的标签配一段居中的正文
   会看着像没对齐的错位。改回行内前缀，跟着正文一起居中 */
.page-srd .verdict-main .vpair p{display:block}
.page-srd .verdict-main .vpair b{display:inline;margin-right:8px}
}
@media print{
.page-srd .phero,.page-srd .tool,.page-srd .method,.page-srd .history,.page-srd .res-tools .rt-btns{display:none !important}
.page-srd body{background:#fff}
.page-srd .results{background:#fff;padding:0}
.page-srd .rd,.page-srd .rd-body{break-inside:avoid}
.page-srd .rd[open] .rd-caret{display:none}
.page-srd table.srd{min-width:0;font-size:11px}
}
</style>
