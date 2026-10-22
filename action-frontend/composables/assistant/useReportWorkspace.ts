/**
 * 报告助手的工作区状态：向导位置 · 草稿 · 清单表纳入 · 导入 · AI 完善 · 检查 · 留痕 · 交付。
 *
 * ## 五步各管一件事（2026-10 定稿）
 *
 * ① 类型匹配 → ② 报告撰写（人写事实；AI 只在**空条目**上起个草）→ ③ 合规与一致性检查
 * （只诊断不改稿）→ ④ AI 优化（③ 的问题清单就是这里的工作队列；AI 起草、人点「采用」才写回）
 * → ⑤ 成果交付（核对单只提醒不拦截 · 初稿预览 · 导出 · AI 使用说明）。
 *
 * 五个步骤组件（`components/assistant/Step*.vue`）共用这一份状态，经 `provide/inject`
 * 拿到（`assistantContext.ts`）。状态集中在这里而不是散在组件里，是因为它们本来就是一份：
 * ③ 的判定挂回 ② 的导航、④ 写回的正文 ② 要看得见、⑤ 的核对要读前面每一步的结果。
 *
 * **调用时机**：必须在页面 `<script setup>` 顶层、两次 await 之后**同步**调用 ——
 * 里面注册了 onMounted / onBeforeUnmount，挂在当前组件实例上。
 */

import { groupKeyOf, groupRows, stepItem } from '~/composables/checklistNav'
import { deliverChecks, isIncluded, scopeIds, toggleIncluded } from '~/composables/reportScope'
import { findPathToType } from '~/composables/studyWizard'
import { buildWizardQuery, parseGuidelineQuery, parsePartQuery, parseWizardQuery, WIZARD_STEP_COUNT } from '~/composables/wizardQuery'
import type { useAssistantWizard } from './useAssistantWizard'
import type { useChecklist } from './useChecklist'

type Wizard = Omit<ReturnType<typeof useAssistantWizard>, 'ready'>
type Checklist = Omit<ReturnType<typeof useChecklist>, 'ready'>

interface DraftItem { itemId: number; content: string }
export interface DraftRow {
  draftId: number
  guidelineId: number
  guidelineCode: string
  studyTypeKey: string
  title: string
  /** 导入的草稿（带原稿）：整篇成文前要先确认，第五步默认导出原稿写回 */
  hasSource: boolean
  /** 纳入的清单表（空 = 全部，sql/051） */
  parts: number[]
  items: DraftItem[]
  itemTotal: number
  filledCount: number
  requiredTotal: number
  requiredFilled: number
  updateTime: string | null
}

export interface Verdict {
  itemId: number
  status: 'reported' | 'vague' | 'missing'
  evidence: string
  reason: string
}
export interface CrossFinding {
  severity: 'warn' | 'issue'
  evidence: string
  detail: string
  suggestion: string
  /** 'no' = 模型给的引文在稿件里一段都没找到（`engine/grounding.py`），只挂提示不改判定 */
  located?: string
}
export type CrossStatus = 'ok' | 'warn' | 'issue' | 'na' | 'unchecked'
export interface CrossCheck {
  key: string
  kind: 'logic' | 'term'
  status: CrossStatus
  findings: CrossFinding[]
  capped: boolean
}
interface CrossResult {
  summary: { ok: number; warn: number; issue: number; na: number; unchecked: number }
  checks: CrossCheck[]
  truncated: boolean
}
interface CheckResult {
  verdicts: Verdict[]
  consistency: CrossResult | null
  truncated: boolean
  /** 有一部分没判成（批次失败 / 某条规则没跑成）。非空时顶部提示，不然和「查过没问题」长得一样 */
  partial: boolean
  models: string[]
  /** 这次检查的时间，展示「上次检查于」用 */
  at: string | null
}

/**
 * 一条要处理的问题（③ 的问题清单 / ④ 的工作队列）。
 *
 * `kind` 的先后就是严重程度：跨条目矛盾 > 已填却未报告 > 描述模糊 > 还没写。
 * 「还没写」也列出来，但它在 ④ 里需要作者先补事实 —— 模型手里只有条目要求时写不出东西。
 */
export type IssueKind = 'cross' | 'missing' | 'vague' | 'blank'
export interface IssueRow {
  itemId: number
  /** `ok` 只出现在 ④「全部条目」队列里：这条已填、检查也没挑出问题 */
  kind: IssueKind | 'ok'
  reason: string
}
const ISSUE_ORDER: Record<IssueKind, number> = { cross: 0, missing: 1, vague: 2, blank: 3 }

/**
 * 导入的草稿，初稿是从原稿出发、把改过的条目写回原处生成的（后端 `manuscript_rebuild`）。
 * 这组数告诉用户这次动了什么 —— 尤其 `appended`：与没改的条目共用一段、或位于表格里的，
 * 原文留着、新文字追加在后面，可能出现重复，需要人看一眼
 */
interface RebuildInfo {
  fromSource: boolean
  keepsLayout: boolean
  replaced: number
  inserted: number
  appended: number
  removed: number
  images: number
  tables: number
}

/**
 * 操作留痕（文档 3.4）。**存的是结构化事件，不是渲染好的句子** —— 句子里迟早会混进稿件正文片段，
 * 而留痕表没有删除入口。人读的那句话由 `trailText()` 按 i18n 拼。
 */
interface TrailRow {
  trailId?: number | null
  draftId?: number | null
  event: string
  actor: string
  itemId?: number | null
  total?: number | null
  reported?: number | null
  vague?: number | null
  missing?: number | null
  completeness?: number | null
  charCount?: number | null
  note?: string
  guidelineCode?: string
  createTime?: string | null
  /** 未落库前的本地临时 id —— 时间戳只到秒，同一秒连写两条会撞 v-for key */
  localId?: number
}
/** 与后端 `MAX_TRAIL_ROWS` 对齐：取回的条数撞到它，说明更早的留痕没取回来 */
const MAX_TRAIL_ROWS = 50

/** 单条正文的字符上限，与后端 `MAX_DRAFT_ITEM_CHARS` 对齐 */
export const MAX_ITEM_CHARS = 20000
/** 「AI 完善」补充意见的上限，与后端 `MAX_INSTRUCTION_CHARS` 对齐 */
export const REFINE_NOTE_MAX = 1000
/** 合成出的全文太短时模型判不出东西，与后端同一道下限 */
export const MIN_CHARS = 200
export const IMPORT_ACCEPT = '.docx,.pdf,.txt,.md'
export const EXPORT_FMTS = ['docx', 'xlsx', 'json'] as const
/** 预览里段落之间的分隔 */
const PARA_BREAK = String.fromCharCode(10, 10)

export function useReportWorkspace(wz: Wizard, ck: Checklist) {
  const { t, te } = useI18n()
  const { pick, isEn } = useBilingual()
  const { guest, isLoggedIn, authedCall, authedBlob } = useAuth()
  const route = useRoute()
  const router = useRouter()
  const { checklist, checklistRows, checklistParts, partNos, rowById, ckLoading, noItems } = ck
  const { checklistCode, resolvedKey } = wz

  /** 登录后跳回本页 —— 连同 query 里的向导位置与第一步答案一起带回来 */
  const loginLink = computed(() => `/login?redirect=${encodeURIComponent(route.fullPath)}`)
  const lang = () => (isEn.value ? 'en' : 'zh')
  /** 后端时间串 → 毫秒；解析不了按 0 */
  const toTime = (iso: string) => new Date(iso.replace(' ', 'T')).getTime() || 0

  // ================================================================ 向导位置 ↔ URL
  //
  // **动机是登录往返。** `loginLink` 用的是 `route.fullPath`：位置进了 URL，`?redirect=` 就天然
  // 把它带回来了。**还原只能在挂载之后做** —— 全站是预渲染静态站，烤进 HTML 的永远是 step=1、
  // 第一张表那一版；setup 阶段就按 query 算的话，面板显隐那个 `:class` 对不上，而 Vue 的
  // hydration 不修 class（见 CLAUDE.md「按 locale 变化的 class」那条）。
  //
  // **这一段刻意放在草稿逻辑上面**：还原必须早于下面那次 `loadDrafts()` 的 onMounted
  // （onMounted 按注册顺序跑），否则挂载瞬间会先按默认规范取一遍草稿、还原后再取一遍。

  const step = ref(1)
  const wizardEl = ref<HTMLElement | null>(null)
  /** 第二步正在看的清单表；0 = 还没选过（取第一张） */
  const activePart = ref(0)

  /** 跳到第 n 步；越界钳位。滚回向导顶部，避免长面板切换后停在半空 */
  function go(n: number) {
    const next = Math.min(WIZARD_STEP_COUNT, Math.max(1, n))
    if (next === step.value) return
    step.value = next
    wizardEl.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  /**
   * 落地时 URL 指名要打开的草稿（`?draft=`，来自「我的账号」页，或第一步的「继续上次的草稿」）。
   *
   * 不在 `loadDrafts` 里一取到就清掉，而是等**某一份草稿真的灌进编辑态**（`applyDraft`）时才清：
   * 挂载时 `loadDrafts` 可能被 onMounted 与「规范变了」那个 watch 各调一次、两个请求并发，
   * 先回来的那次把它消费掉的话，后回来的那次会按老规矩打开「最近改的那份」把它盖掉。
   */
  let wantDraftId: number | null = null

  /**
   * 草稿代际：每换一份草稿（打开 / 新建 / 清空）加一。在途的异步回调都先比一下代际，对不上就丢弃 ——
   * 否则 A 稿的检查结果、AI 轮询、合成全文会在用户换到 B 稿之后写进 B 稿，B 稿的按钮还会被
   * A 稿的「进行中」锁住。挂载时 `loadDrafts` 可能并发两次、同一份草稿 apply 两遍，
   * 代际也让先发的那一轮作废，不会出现两条并行的轮询链。
   */
  let draftGen = 0
  /** 页面已卸载：在途请求回来后不许再挂新的轮询 */
  let disposed = false

  onMounted(() => {
    const restored = parseWizardQuery(route.query, wz.wizard.value)
    wz.ans.value = restored.ans
    step.value = restored.step
    // 规范选项由刚还原的研究类型决定（computed 同步就算好了），所以要在 ans 之后还原
    const gl = parseGuidelineQuery(route.query)
    const glOpt = gl ? wz.checklistOptions.value.find((o) => o.guidelineId === gl) : undefined
    if (glOpt) wz.chooseGuideline(glOpt.code)
    activePart.value = parsePartQuery(route.query)
    // 必须在下面那个 watch 之前读 —— 它一挂上就用向导状态整个替换 query，draft 会被抹掉
    const wanted = Number(typeof route.query.draft === 'string' ? route.query.draft : '')
    if (Number.isInteger(wanted) && wanted > 0) wantDraftId = wanted
    // 写回的监听要在还原**之后**才挂：先挂的话，挂载瞬间那一次 replace 会拿默认值
    // 把 URL 上刚带进来的答案冲掉。用 replace 不用 push —— 每点一个选项压一条历史，
    // 返回键就成了「逐个撤销我的选择」
    watch(
      () => buildWizardQuery(
        step.value,
        { path: wz.walk.value.path, stage: wz.ans.value.stage },
        wz.defaultPath.value,
        // 第一张表是默认值，不写进地址栏
        currentPart.value !== partNos.value[0] ? currentPart.value : 0,
        // 重点推荐那份规范同理
        checklistCode.value !== wz.checklistOptions.value[0]?.code
          ? (wz.checklistOptions.value.find((o) => o.code === checklistCode.value)?.guidelineId ?? 0)
          : 0,
      ),
      (query) => void router.replace({ query }),
      { deep: true },
    )
  })

  // ================================================================ 草稿
  //
  // **未登录访客一个草稿接口都不发**。条目清单本身照常展示（那是公开数据），只是不可编辑。

  const drafts = ref<DraftRow[]>([])
  const draftId = ref<number | null>(null)
  /** 编辑态：条目id -> 正文。与 draft 分开放，避免每敲一个字就重建整个草稿对象 */
  const body = ref<Record<number, string>>({})
  const draftTitle = ref('')
  const draftErr = ref('')
  const draftBusy = ref(false)
  const dirty = ref(false)
  const savedAt = ref('')
  /** 正在保存中；与 draftBusy 分开，保存不该禁用输入框 */
  const saving = ref(false)
  let saveTimer: ReturnType<typeof setTimeout> | null = null
  /**
   * 编辑序号。每次改动自增，保存成功时**只有序号没变**才敢把 dirty 清掉 ——
   * 请求在途的这一两秒里用户往往还在打字，凭 `dirty=false` 一刀切会把这段输入
   * 连同「还没存」这个事实一起抹掉。
   */
  let editSeq = 0
  /** 保存串行化队列。并发两次 PUT 会在 (draft_id,item_id) 唯一索引上撞车 */
  let savePromise: Promise<boolean> = Promise.resolve(true)

  /** 只列当前规范的草稿：第二步展开的是第一步匹配到的那份规范，混列别的规范只会选错 */
  const myDrafts = computed(() => drafts.value.filter((d) => d.guidelineCode === checklistCode.value))
  /**
   * 能否编辑。**刻意不要求 `draftId` 非空** —— 登录用户第一次进第二步时就该看到一份
   * 可写的空骨架；草稿在第一次保存时才真的建出来（`ensureDraft`），只是路过看看的人
   * 不会在库里留下空壳。条目还在载入时不给编辑：那会儿渲染的还是上一份规范的条目。
   */
  const canEdit = computed(
    () => isLoggedIn.value && Boolean(checklistCode.value) && !ckLoading.value && checklist.value.length > 0,
  )

  // ---------------------------------------------------------------- 纳入的清单表（sql/051）
  //
  // 一份规范可能含多张清单表。第二步按表切换，用户可以取消纳入某张（例如不打算交摘要清单）：
  // 不计完成度、不进检查与优化、不进导出，**但正文照存**，重新勾上时都还在。

  /** 纳入的清单表；空 = 全部 */
  const includedParts = ref<number[]>([])
  /** 纳入范围改过、还没存 —— 保存时才带 `parts`（不带 = 后端不改，自动保存不会冲掉它） */
  let partsDirty = false
  /**
   * 纳入范围的改动序号。保存成功时只有序号没变才清 `partsDirty` —— 连着勾两张表时，第一次保存
   * 在途、第二次排队，第一次回来把标志清掉的话，第二次就不带 `parts` 了，服务端停在第一次的选择上
   */
  let partsSeq = 0

  const scope = computed(() => scopeIds(checklistRows.value, includedParts.value))
  const scopedRows = computed(() => checklistRows.value.filter((r) => scope.value.has(r.itemId)))
  const partIncluded = (partNo: number) => isIncluded(includedParts.value, partNos.value, partNo)
  const partErr = ref('')

  /** 勾选 / 取消纳入某张表，立刻存（它不是正文，没有「停下来想一句话」的必要） */
  function togglePart(partNo: number) {
    if (!canEdit.value) return
    const next = toggleIncluded(includedParts.value, partNos.value, partNo)
    if (!next) {
      partErr.value = t('assistant.partKeepOne')
      return
    }
    partErr.value = ''
    includedParts.value = next
    partsDirty = true
    partsSeq += 1
    editSeq += 1
    dirty.value = true
    markCheckStale()
    void saveDraft()
  }

  /** 当前看的那张表：URL / 用户选过的那张不在这份规范里时回落第一张 */
  const currentPart = computed(() =>
    partNos.value.includes(activePart.value) ? activePart.value : (partNos.value[0] ?? 0),
  )
  const currentPartInfo = computed(() => checklistParts.value.find((p) => p.partNo === currentPart.value) ?? null)
  /** 当前那张表的条目 —— 导航、上一条 / 下一条都只在表内走 */
  const partRows = computed(() => checklistRows.value.filter((r) => r.partNo === currentPart.value))

  /** 完成度：分母是**纳入范围内**的必填条目 —— 选填项本就可能不适用于这份研究 */
  const requiredIds = computed(() => new Set(scopedRows.value.filter((r) => r.required).map((r) => r.itemId)))
  const filledIds = computed(
    () => new Set(scopedRows.value.map((r) => r.itemId).filter((id) => (body.value[id] ?? '').trim())),
  )
  const requiredFilled = computed(() => [...filledIds.value].filter((id) => requiredIds.value.has(id)).length)
  const donePct = computed(() =>
    requiredIds.value.size ? Math.round((requiredFilled.value / requiredIds.value.size) * 100) : 0,
  )
  /** 每张表各自的完成度（表页签上显示） */
  function partProgress(partNo: number) {
    const rows = checklistRows.value.filter((r) => r.partNo === partNo && r.required)

    return { filled: rows.filter((r) => (body.value[r.itemId] ?? '').trim()).length, total: rows.length }
  }

  /** 超长的那一条 —— 后端只会回一句字段级 422，不指明是几十条里的哪一条 */
  const overLongRow = computed(() =>
    checklistRows.value.find((r) => (body.value[r.itemId] ?? '').length > MAX_ITEM_CHARS) ?? null,
  )

  // ---------------------------------------------------------------- 条目导航
  //
  // 左边按 维度 折叠（一次只列当前这张表），右边一次只展开当前这一条。分组与步进是纯函数
  // （`checklistNav.ts`）。**首帧必须与预渲染一致**：当前条目默认取当前表首条、展开的维度默认
  // 只含首条所在组，两者都只从 `checklist` 推出，不看登录态。

  const navGroups = computed(() => groupRows(partRows.value, body.value, MAX_ITEM_CHARS))
  const activeItemId = ref<number | null>(null)
  const currentId = computed<number | null>(() => {
    const id = activeItemId.value
    if (id != null && partRows.value.some((r) => r.itemId === id)) return id

    return partRows.value[0]?.itemId ?? null
  })
  const activeRow = computed(() => (currentId.value != null ? rowById.value.get(currentId.value) ?? null : null))
  const activeGroupKey = computed(() => groupKeyOf(navGroups.value, currentId.value))
  const prevId = computed(() => stepItem(partRows.value, currentId.value, -1))
  const nextId = computed(() => stepItem(partRows.value, currentId.value, 1))
  /** 当前正文长度；超过上限时面板计数与导航上那条一起标红 */
  const activeLen = computed(() => (activeRow.value ? (body.value[activeRow.value.itemId] ?? '').length : 0))

  /** 展开的维度 —— **唯一**一份状态（曾经给「当前组」单开过一个收起开关，结果是两份真相） */
  const openDomains = ref<Set<string>>(new Set())
  const isDomainOpen = (key: string) => openDomains.value.has(key)
  function setDomainOpen(key: string, open: boolean) {
    if (openDomains.value.has(key) === open) return
    const next = new Set(openDomains.value)
    if (open) next.add(key)
    else next.delete(key)
    openDomains.value = next
  }
  function toggleDomain(key: string) {
    setDomainOpen(key, !isDomainOpen(key))
  }
  // immediate：首帧就把首条所在组展开，构建期与客户端算出的是同一个 key
  watch(activeGroupKey, (key) => {
    if (key != null) setDomainOpen(key, true)
  }, { immediate: true })
  // 换规范：展开过的组的 key 全是旧清单的 itemId，留着无害但会越积越多。
  // activePart 不重置 —— 挂载时从 URL 还原的路径会让规范变一次，重置就把同时带回来的 ?part= 冲掉了；
  // 它在新规范里不存在时 currentPart 自己会回落第一张
  watch(checklistCode, () => {
    openDomains.value = new Set()
    activeItemId.value = null
  })

  /** 下面三个由 `StepWrite.vue` 用函数式 ref 填进来 */
  const navEl = ref<HTMLElement | null>(null)
  const paneEl = ref<HTMLElement | null>(null)
  const paneTa = ref<HTMLTextAreaElement | null>(null)
  /** 页头是 sticky 的，滚到面板顶时要给它让出位置（见 `.tpane` 的 scroll-margin-top） */
  const PANE_VISIBLE_RATIO = 0.7

  /**
   * 换条目之后把两边都带到眼前：导航里高亮那条滚进自己的滚动区；面板顶部若在视口外就滚到面板顶。
   * 输入框的焦点只在鼠标点导航时给；「上一条 / 下一条」按钮保留焦点，键盘用户连按回车才走得动
   */
  function revealSelection(focus: boolean) {
    void nextTick(() => {
      navEl.value?.querySelector('.tnav-item.on')?.scrollIntoView({ block: 'nearest' })
      const pane = paneEl.value
      if (pane) {
        const top = pane.getBoundingClientRect().top
        if (top < 0 || top > window.innerHeight * PANE_VISIBLE_RATIO) pane.scrollIntoView({ block: 'start' })
      }
      if (focus) paneTa.value?.focus({ preventScroll: true })
    })
  }

  /**
   * 选中一条：切到它所在的表、展开它所在的维度。
   *
   * @param reveal 只有在第二步里点的才滚动与聚焦 —— 从 ③ ④ 选中时第二步的面板是隐藏的
   */
  function selectItem(id: number, focus = true, reveal = true) {
    const row = rowById.value.get(id)
    if (row) activePart.value = row.partNo
    activeItemId.value = id
    void nextTick(() => setDomainOpen(groupKeyOf(navGroups.value, id) ?? '', true))
    if (reveal) revealSelection(focus)
  }
  function goItem(delta: 1 | -1) {
    const id = delta > 0 ? nextId.value : prevId.value
    if (id != null) selectItem(id, false)
  }
  function selectPart(partNo: number) {
    activePart.value = partNo
  }
  /** 从 ③ ④ 跳回第二步改这一条 */
  function editItem(id: number) {
    go(2)
    selectItem(id, true)
  }

  function stopAutoSave() {
    if (saveTimer) clearTimeout(saveTimer)
    saveTimer = null
  }

  /** 有改动就标脏并排一次自动保存。4 秒是「停下来想一句话」的时长，比逐字保存省得多 */
  function touchDraft() {
    if (!canEdit.value) return
    editSeq += 1
    dirty.value = true
    markCheckStale()
    stopAutoSave()
    saveTimer = setTimeout(() => void saveDraft(), 4000)
  }

  /**
   * 清掉「属于上一份草稿」的一切：检查结果、补充事实、建议、成文、正文来源选择、各种回执。
   *
   * 打开另一份草稿（`applyDraft`）与清空（`resetDraft`）都要走这里。**补充事实尤其不能带过去**：
   * 条目 id 在同一份规范的两份草稿里是同一套，A 稿第 12 条写的「样本量 n=60」会被一键优化当成
   * 作者提供的事实发给模型，写进 B 稿的论文。接口失败时也不会留着上一份的东西当这一份的
   */
  function resetPerDraft() {
    draftGen += 1
    stopAutoSave()
    resetCheck()
    refineNotes.value = {}
    refineErr.value = ''
    // 上一份草稿在途的单条优化 / 采用：它回来时代际对不上会自己丢弃，按钮不该被它锁着
    refineBusy.value = false
    adoptBusy.value = false
    suggestions.value = []
    refinePick.value = {}
    refineItemId.value = null
    stopAiPoll()
    aiPollFails = 0
    checkPollFails = 0
    aiLive.value = null
    aiDone.value = null
    aiErr.value = ''
    aiBusy.value = false
    adoptAllMsg.value = ''
    render.value = null
    bodyPick.value = ''
    composed.value = ''
    composeMissing.value = 0
    composedAt = -1
    rebuildInfo.value = null
    trail.value = []
    partErr.value = ''
    importDone.value = null
    importErr.value = ''
    exporting.value = ''
    exportErr.value = ''
  }

  /** 把接口回来的草稿灌进编辑态 */
  function applyDraft(row: DraftRow) {
    // 指名的那份在别的规范下时，这里打开的只是过渡用的当前规范的草稿 —— 不能把指名冲掉
    const consumed = wantDraftId === row.draftId
    if (consumed) wantDraftId = null
    resetPerDraft()
    draftId.value = row.draftId
    draftTitle.value = row.title
    body.value = Object.fromEntries(row.items.map((it) => [it.itemId, it.content]))
    includedParts.value = [...(row.parts ?? [])]
    partsDirty = false
    dirty.value = false
    // `?draft=` 用过就从地址栏摘掉：留着的话用户在下拉里换了别的草稿再刷新，又会跳回这一份。
    // 等一拍再读 query：向导的 query 同步也在 replace，读旧快照会把它刚写的 step / path 冲回去
    if (consumed) dropDraftQuery()
    // 换了一份草稿，检查结果、留痕、建议与成文也要换成这一份的
    void loadCheck()
    void loadTrail()
    void loadAi()
  }

  /** 把 `?draft=` 从地址栏摘掉（读最新的 query，只动这一个键） */
  function dropDraftQuery() {
    void nextTick(() => {
      if (route.query.draft == null) return
      const { draft: _drop, ...rest } = route.query
      void router.replace({ query: rest })
    })
  }

  async function loadDrafts(openFirst = true) {
    if (!isLoggedIn.value) return
    const res = await authedCall('/report-drafts', 'GET')
    if (!res.ok) {
      draftErr.value = res.message
      return
    }
    drafts.value = (res.envelope?.data ?? []) as DraftRow[]
    if (!openFirst) return
    const mine = myDrafts.value
    // URL / 「继续上次的草稿」指名的那份优先
    if (wantDraftId != null) {
      const target = drafts.value.find((d) => d.draftId === wantDraftId)
      if (target && target.guidelineCode === checklistCode.value) {
        if (draftId.value !== wantDraftId) await openDraft(wantDraftId)
        return
      }
      // 指名的草稿属于本研究类型的另一份可选规范（如 TIDieR-A）：切过去，规范一变下面那个 watch 会再取一次并打开它
      if (target && wz.chooseGuideline(target.guidelineCode)) return
      // 已经删了：不再惦记它。属于别的规范的留着 —— 「继续上次的草稿」正在把问卷拨过去，规范一变还会再取一次
      if (!target) {
        wantDraftId = null
        dropDraftQuery()
      }
    }
    // 已经打开的那份还在列表里就别动它，否则每次回到第二步都会跳回最近改的那份
    if (draftId.value && mine.some((d) => d.draftId === draftId.value)) return
    if (mine.length) await openDraft(mine[0]!.draftId)
    else resetDraft()
  }

  function resetDraft() {
    draftId.value = null
    draftTitle.value = ''
    body.value = {}
    includedParts.value = []
    partsDirty = false
    dirty.value = false
    // 检查结果与完善稿都是「上一份草稿」的，留着会拿旧结果去改新稿子
    resetPerDraft()
  }

  /**
   * 离开当前草稿之前先把改动落盘。切草稿 / 改研究类型 / 离开页面这几条路都会整体覆盖或清空
   * `body`，而自动保存是 4 秒防抖 —— 不先存一次，最后这几秒的输入就无声无息地没了。
   *
   * **改研究类型时 `canEdit` 已经是假的**（新规范的清单正在载入），所以这里不看它：
   * 只要是一份已经建出来的草稿，就按它自己的条目存回去（`force`）。
   */
  async function leaveDraft(): Promise<boolean> {
    stopAutoSave()
    if (!dirty.value || !isLoggedIn.value) return true
    // 还没建出来的空骨架、清单又已在按新规范重取：没有草稿可存，也不能按新规范建（条目对不上）。
    // 原因要说对 —— 报「请检查网络」会让人以为重试一下就能存上
    if (!canEdit.value && !draftId.value) {
      draftErr.value = t('assistant.leaveTypeChanged')
      return false
    }

    return saveDraft(true)
  }

  /** 正在打开的那份：挂载时两路 `loadDrafts` 会对同一份草稿各 openDraft 一次，第二次会冲掉其间的输入 */
  let openingId: number | null = null
  /**
   * 打开请求的序号：快速连选 A、B 时两次 GET 并发，**只认最后一次选择**。不看序号的话谁后返回就打开谁，
   * 用户最后选的是 B，落下来的却可能是 A
   */
  let openSeq = 0

  async function openDraft(id: number) {
    if (!isLoggedIn.value || id === draftId.value || id === openingId) return
    const prev = draftId.value
    const my = ++openSeq
    openingId = id
    // 从这一刻起正文框只读（StepWrite 看 draftBusy）：取详情这一两秒里敲的字会被新草稿整个覆盖
    draftBusy.value = true
    try {
      // 当前这份没存上就不走：打开别的草稿会整个覆盖 body，没存的字连同报错一起没了
      if (!(await leaveDraft())) {
        if (my !== openSeq) return
        draftErr.value = draftErr.value || t('assistant.leaveSaveFailed')
        await snapSelect(prev)
        return
      }
      if (my !== openSeq) return
      await loadOne(id, prev, my)
    } finally {
      if (my === openSeq) {
        openingId = null
        draftBusy.value = false
      }
    }
  }

  /** 下拉的 DOM 值已经跟着用户的选择变了而 draftId 没变：先置空再放回去，强制把 select 拨回真实状态 */
  async function snapSelect(prev: number | null) {
    draftId.value = null
    await nextTick()
    draftId.value = prev
  }

  async function loadOne(id: number, prev: number | null, my: number) {
    const res = await authedCall(`/report-drafts/${id}`, 'GET')
    // 其间又选了别的草稿：这次的结果作废
    if (my !== openSeq) return
    composed.value = ''
    rebuildInfo.value = null
    if (!res.ok) {
      draftErr.value = res.message
      await snapSelect(prev)
      return
    }
    // 成功打开才清上一份的报错（换研究类型时「没存上」的提示由调用方在这之后补回去）
    draftErr.value = ''
    applyDraft(res.envelope?.data as unknown as DraftRow)
  }

  /**
   * 确保有一份草稿可写。空骨架在第一次保存时才真的建出来，所以这里**不能** applyDraft
   * —— 那会把用户刚敲进去的内容清空。
   */
  async function ensureDraft(): Promise<boolean> {
    if (draftId.value) return true
    if (!isLoggedIn.value || !checklistCode.value) return false
    const gen = draftGen
    const code = checklistCode.value
    const res = await authedCall('/report-drafts', 'POST', {
      guidelineCode: code,
      studyTypeKey: resolvedKey.value,
      title: draftTitle.value,
    })
    // 建草稿在途时换了研究类型（或换了草稿）：不能把旧规范的草稿 id 挂到新规范的清单上。
    // 建出来的那份已在服务端，会出现在原规范的草稿列表里
    if (gen !== draftGen || code !== checklistCode.value) return false
    if (!res.ok) {
      draftErr.value = res.message
      return false
    }
    const row = res.envelope?.data as unknown as DraftRow
    draftId.value = row.draftId
    if (!draftTitle.value) draftTitle.value = row.title
    drafts.value = [{ ...row, items: [] }, ...drafts.value]

    return true
  }

  /** 「新建草稿」按钮：先把当前这份落盘，再开一份空的 */
  async function newDraft() {
    if (!isLoggedIn.value || !checklistCode.value) return
    if (!(await leaveDraft())) {
      draftErr.value = draftErr.value || t('assistant.leaveSaveFailed')
      return
    }
    draftBusy.value = true
    draftErr.value = ''
    resetDraft()
    const ok = await ensureDraft()
    draftBusy.value = false
    if (ok) await loadDrafts(false)
  }

  /**
   * 保存。**串行化**：已有一次在途时排队等它结束再存 —— 并发两次 PUT 会撞唯一索引，
   * 而直接丢弃这次调用会让在途期间敲的字永远存不进去。
   */
  function saveDraft(force = false): Promise<boolean> {
    savePromise = savePromise.catch(() => false).then(() => doSave(force))

    return savePromise
  }

  /**
   * @param force 离开草稿时用：清单可能正在按新规范重取（`canEdit` 为假），但这份草稿已经建好、
   *   条目是它自己那一套，照样能存。不建新草稿（新规范下建出来的会装着旧规范的条目）
   */
  async function doSave(force = false): Promise<boolean> {
    if (!canEdit.value && !(force && isLoggedIn.value && draftId.value)) return false
    // 超长判断按 body 自己来：force 时清单已经换成新规范的了，按清单行找会漏掉旧条目
    const overId = Object.entries(body.value).find(([, v]) => (v ?? '').length > MAX_ITEM_CHARS)?.[0]
    if (overId != null) {
      const row = rowById.value.get(Number(overId))
      draftErr.value = t('assistant.dfTooLong', { no: row?.no || row?.seq || overId, max: MAX_ITEM_CHARS })
      return false
    }
    // 还没建出来的空骨架（第一次保存时才建）：能编辑时照样先建，离开草稿时也不例外 ——
    // 不然在新骨架里敲的字，一换草稿就无声无息地没了
    if (!draftId.value && !(canEdit.value && (await ensureDraft()))) return false

    const seq = editSeq
    const gen = draftGen
    // 纳入范围只在改过时带；空列表 = 全部纳入（后端认），所以 force 时清单已换、表号不可信也能如实表达
    const sendParts = partsDirty
    const sentPartsSeq = partsSeq
    stopAutoSave()
    saving.value = true
    draftErr.value = ''
    const res = await authedCall(`/report-drafts/${draftId.value}`, 'PUT', {
      title: draftTitle.value,
      // 整体覆盖语义：空内容也要带上，否则「用户清空了这条」会被当成「这次没带这条」。
      // 没纳入的表的正文也在 body 里，照样带上 —— 不带就被清空了
      items: Object.entries(body.value).map(([id, content]) => ({ itemId: Number(id), content })),
      ...(sendParts ? { parts: includedParts.value } : {}),
    })
    saving.value = false
    if (!res.ok) {
      if (gen !== draftGen) return false
      draftErr.value = res.message
      // **只在后端拒的就是纳入范围时**才退回（例如后台刚删了那张表）：不退的话之后每次自动保存都带着它、
      // 每次都被拒，正文也跟着存不进去。网络抖动、超时这类失败不碰用户刚做的选择，下次保存照样带上
      if (sendParts && /清单表|checklist table/i.test(res.message)) {
        partsDirty = false
        includedParts.value = [...(drafts.value.find((d) => d.draftId === draftId.value)?.parts ?? [])]
        partErr.value = res.message
      }
      return false
    }
    if (sendParts && partsSeq === sentPartsSeq) partsDirty = false
    savedAt.value = new Date().toLocaleTimeString(isEn.value ? 'en-GB' : 'zh-CN', { hour12: false })
    const row = res.envelope?.data as unknown as DraftRow
    const idx = drafts.value.findIndex((d) => d.draftId === row.draftId)
    if (idx >= 0) drafts.value[idx] = { ...row, items: [] }
    // 保存在途时换了 / 删了草稿：这份回执属于上一份，别把它的标题写进现在这份的输入框
    if (gen !== draftGen) return true
    // 请求这一两秒里又改过 —— 别把 dirty 清掉，另排一次；**标题也别回写**，回写会把在途期间敲的字打回去。
    // 没改过时才回写：标题可能被后端规范化（清空时保留旧名），不回写的话输入框与下拉里的名字会长期对不上
    if (editSeq === seq) {
      draftTitle.value = row.title
      dirty.value = false
    } else touchDraft()

    return true
  }

  async function removeDraft() {
    if (!draftId.value) return
    // 主表是逻辑删，但条目正文是**物理删**，几十条已写好的内容不可恢复，值得挡一下
    if (!window.confirm(t('assistant.dfDeleteConfirm'))) return
    stopAutoSave()
    const removed = draftId.value
    draftBusy.value = true
    // 等在途 / 排队的保存走完再删：它晚于删除返回的话，会把这份的标题写进接下来打开的那份
    await savePromise.catch(() => false)
    if (removed !== draftId.value) {
      draftBusy.value = false
      return
    }
    const res = await authedCall(`/report-drafts/${removed}`, 'DELETE')
    draftBusy.value = false
    if (!res.ok) {
      draftErr.value = res.message
      return
    }
    drafts.value = drafts.value.filter((d) => d.draftId !== removed)
    if (removed !== draftId.value) return
    resetDraft()
    const mine = myDrafts.value
    if (mine.length) await openDraft(mine[0]!.draftId)
  }

  /**
   * 第一步顶部的「继续上次的草稿」：最近改过的那份，任何规范都算。
   *
   * 那份草稿是按某个研究类型建的，所以要先把问卷拨到能判定出那一类的路径上 ——
   * 规范一变，下面那个 watch 会重取草稿并打开 `wantDraftId` 指名的那份。
   * 问卷里已经走不到那一类（后台停用了它）时不给这个入口。
   */
  const resumeDraft = computed(() => {
    // 列表顺序不可靠（保存是原位替换、新建是插到最前），按更新时间挑
    const d = [...drafts.value].sort((a, b) => toTime(b.updateTime ?? '') - toTime(a.updateTime ?? ''))[0]
    if (!d) return null
    if (d.guidelineCode === checklistCode.value) return d

    return d.studyTypeKey && findPathToType(wz.wizard.value, d.studyTypeKey) ? d : null
  })

  /** 要挺过「换规范 → 重取并打开草稿」那一轮的提示（打开草稿会清报错） */
  let carryErr = ''

  async function continueDraft(d: DraftRow) {
    if (d.guidelineCode === checklistCode.value) {
      go(2)
      await openDraft(d.draftId)
      return
    }
    wantDraftId = d.draftId
    if (!wz.answerType(d.studyTypeKey)) {
      wantDraftId = null
      return
    }
    // 那份草稿可能是按这一类研究的另一份可选规范写的（sql/056）
    wz.chooseGuideline(d.guidelineCode)
    // 后台把这个研究类型改挂到了别的规范（sql/048）：拨过去也打不开那份草稿。说出来，且别把指名留着
    // —— 留着的话日后切到那份规范时会突然把它打开
    if (checklistCode.value !== d.guidelineCode) {
      wantDraftId = null
      draftErr.value = t('assistant.dfResumeMoved', { code: d.guidelineCode })
      // 规范变了的话下面那个 watch 会取草稿、打开一份，那会清掉报错 —— 交给它在最后补回去
      carryErr = draftErr.value
    }
    go(2)
  }

  /** 关标签页 / 刷新时的最后一道闸：浏览器自己弹确认，文案由浏览器决定 */
  function guardUnload(e: BeforeUnloadEvent) {
    if (!dirty.value) return
    e.preventDefault()
    e.returnValue = ''
  }
  onMounted(() => window.addEventListener('beforeunload', guardUnload))
  onBeforeUnmount(() => {
    window.removeEventListener('beforeunload', guardUnload)
    // 路由离开无法 await，尽力存一次（SPA 内跳转时请求照样发得出去）
    if (dirty.value && canEdit.value) void saveDraft()
    stopAutoSave()
    disposed = true
  })

  // 登录态与所选规范都可能在页面存活期间变化（水合后 fetchMe 回来、第一步换研究类型），
  // 两者任一变化都要重新取草稿；未登录时清空，避免上一个账号的草稿留在界面上
  watch([isLoggedIn, checklistCode], async ([loggedIn], [wasLoggedIn]) => {
    // 还登录着就先把改动落盘再切；掉登录态时存不进去，别白发一次 401
    const saved = wasLoggedIn && loggedIn ? await leaveDraft() : true
    // 研究类型已经换了、清单也换了，没法停在原地 —— 至少把「最后几句没存上」说出来
    const lost = saved ? '' : draftErr.value || t('assistant.leaveSaveFailed')
    resetDraft()
    drafts.value = []
    if (loggedIn && checklistCode.value) await loadDrafts()
    // 放在取完草稿之后：打开新规范下的草稿会清掉报错，提示得留住
    const msg = lost || carryErr
    carryErr = ''
    if (msg) draftErr.value = msg
  })
  onMounted(() => {
    if (isLoggedIn.value && checklistCode.value) void loadDrafts()
  })

  // ================================================================ 导入已有稿件
  //
  // 已有稿件的人从这里进：上传 → 后端解析、建草稿、整篇原稿另存 → 跑一次条目映射，
  // 把稿件里对应的段落回填进各条目框（空着的就是没覆盖到的条目）。
  // **原稿不会被拆碎**：导出正文以原稿为准、把改过的条目写回原处，条目框只是对照与完善的工作面。

  const importInput = ref<HTMLInputElement | null>(null)
  const importBusy = ref(false)
  const importErr = ref('')
  const importPct = ref(0)
  const importMsg = ref('')
  /** 导入完成后的小结：填了几条、还剩几条空着 */
  const importDone = ref<{ filled: number; total: number; lines: number; name: string } | null>(null)
  let importTimer: ReturnType<typeof setTimeout> | null = null

  function stopImportPoll() {
    if (importTimer) clearTimeout(importTimer)
    importTimer = null
  }

  /**
   * 第一步路线岔口的「开始」。两条路都进第二步：从零写的直接逐条填；已有稿件的顺手弹出选文件
   * —— 在点击手势里同步调用 `click()` 浏览器才放行，挪到 watch 里就会被拦掉
   */
  function startStage() {
    go(2)
    if (wz.stage.value === 'manuscript' && canEdit.value && !importBusy.value) importInput.value?.click()
  }

  async function pickImport(e: Event) {
    const input = e.target as HTMLInputElement
    const file = input.files?.[0]
    // 清掉 value，否则连着选同一个文件不会再触发 change
    input.value = ''
    if (!file || !isLoggedIn.value || !checklistCode.value || importBusy.value) return

    if (!(await leaveDraft())) {
      importErr.value = t('assistant.leaveSaveFailed')
      return
    }
    stopImportPoll()
    importBusy.value = true
    importErr.value = ''
    importDone.value = null
    importPct.value = 0
    importMsg.value = t('assistant.dfImportParsing')
    // 映射要跑几分钟，期间第一步仍可操作：记下导入时的规范，完成时规范变了就别把草稿灌进来
    importCode = checklistCode.value

    const form = new FormData()
    form.append('file', file)
    form.append('guidelineCode', checklistCode.value)
    form.append('studyTypeKey', resolvedKey.value ?? '')
    form.append('title', '')

    const res = await authedCall(`/report-drafts/import?lang=${lang()}`, 'POST', form)
    if (!res.ok) {
      importBusy.value = false
      importErr.value = res.message

      return
    }
    const data = (res.envelope?.data ?? {}) as { draftId: number; sessionId: string; sourceName: string; sourceLines: number }
    importMsg.value = t('assistant.dfImportMatching')
    await pollImport(data.sessionId, data.draftId, data.sourceName, data.sourceLines)
  }

  /** 导入时的规范代号（完成时比对用） */
  let importCode = ''
  /** 轮询连续失败几次才放弃（导入 / 检查 / AI 任务同一口径） */
  const POLL_MAX_FAILS = 5

  async function pollImport(sid: string, newDraftId: number, name: string, lines: number) {
    /** 映射跑完（或失败）之后：规范没变才打开新草稿；变了只刷新列表并说明 */
    const land = async (err: string) => {
      importBusy.value = false
      await loadDrafts(false)
      if (checklistCode.value !== importCode) {
        importErr.value = t('assistant.dfImportElsewhere', { name })
        return
      }
      await openDraft(newDraftId)
      // 要在 openDraft 之后写：打开草稿会清掉上一份的回执。没打开（接口失败）就只报错，
      // 不然回执里的条数算的是当前那份旧草稿
      if (draftId.value !== newDraftId) {
        // 导入本身成功了、只是没切过去（当前草稿没存上）：别报「导入失败」—— 那会让人再导一次，
        // 生成一份重复的草稿。新草稿已在下拉里
        const landed = !err && drafts.value.some((d) => d.draftId === newDraftId)
        importErr.value = landed
          ? t('assistant.dfImportNotOpened', { name })
          : importErr.value || err || t('assistant.dfImportFailed')
        return
      }
      if (err) importErr.value = err
      else importDone.value = { filled: filledIds.value.size, total: scopedRows.value.length, lines, name }
    }
    let fails = 0
    const tick = async () => {
      if (disposed) return
      const res = await authedCall(`/checklist-review/${sid}`, 'GET')
      if (disposed) return
      if (!res.ok) {
        // 偶发一次失败重试：映射还在跑，这时就打开草稿的话是一片空框，之后回填进库的内容还会被
        // 整体覆盖式的自动保存冲掉。连续失败才放弃 —— 草稿已经建好了，照样放进列表
        fails += 1
        if (fails < POLL_MAX_FAILS) {
          importTimer = setTimeout(tick, 2500 * fails)
          return
        }
        await land(res.message || t('assistant.dfImportFailed'))

        return
      }
      fails = 0
      const st = (res.envelope?.data ?? {}) as Record<string, unknown>
      const cur = Number(st.progressCurrent ?? 0)
      const total = Number(st.progressTotal ?? 100) || 100
      importPct.value = Math.min(100, Math.round((cur / total) * 100))
      if (st.message) importMsg.value = String(st.message)

      const status = String(st.status ?? '')
      if (status === 'completed') {
        // 回填是后端在这次轮询里做完的，所以现在才打开草稿 —— 早开一步是一片空框。
        // 这次映射本身就是一次完整校验，打开草稿时 loadCheck 会把它的结果一并带出来
        await land('')

        return
      }
      if (status === 'failed' || status === 'stopped') {
        // **草稿已经建好了**：映射失败不等于白导，原稿还在，用户可以逐条填，或再点一次检查
        await land(String(st.error || '') || t('assistant.dfImportFailed'))

        return
      }
      if (!disposed) importTimer = setTimeout(tick, 2500)
    }
    await tick()
  }

  onBeforeUnmount(stopImportPoll)

  // ================================================================ AI 优化（② 空条目起草 · ④ 逐条 / 一键优化 · ④ 整篇成文）
  //
  // 单条走 `/report-assist` 的草稿模式（action='refine'），秒级同步；一键优化与整篇成文是分钟级，
  // 走 `report_ai` worker：提交 → 轮询 → 终态时后端落库。**两条来路的建议都入库**（sql/053），
  // 打开草稿时 `loadAi()` 一次取回：在跑的任务（接回轮询）、逐条建议、最近的整篇成文。
  //
  // **结果不自动写回**：看过点「采用」才走 `/suggestions/apply`，服务端逐条核「建议生成之后这一条
  // 又改过没有」（base_text），改过的跳过并如实返回，每条写回记 applied 留痕。
  //
  // ② 只在**空条目**上露出（「让 AI 起个草」，要点必填）；④ 对任何条目都能用。

  interface Suggestion {
    suggestionId: number
    itemId: number
    runId: number | null
    content: string
    baseText: string
    instruction: string
    modelLabel: string
    status: string
  }
  interface AiRunState {
    runId: number
    sessionId: string
    kind: 'refine' | 'render'
    runStatus: 'pending' | 'running' | 'completed' | 'failed' | 'stopped'
    progress: number
    phase: string
    errorMsg: string
    itemTotal: number
    doneCount: number
    failedCount: number
    skippedCount: number
    tooLongCount: number
    ignoredCount: number
    /** 模型判定已满足要求、原样返回的条数（这些不出建议） */
    unchangedCount?: number
  }
  interface RenderParagraph { text: string; itemIds: number[] }
  interface RenderSection {
    /** 小节标题（不分小节的部分就是部分名），也是单节重写的键 */
    domain: string
    /** 所属一级部分（如「2 方法」）；改版前的成文为空 */
    part?: string
    paragraphs: RenderParagraph[]
    ok: boolean
    issues: { kind: string; values: string[] }[]
    error: string
    stale: boolean
  }
  interface RenderState {
    runId: number
    lang: string
    /** 论文题目（照录作者写的题目条目）；没有就空 */
    title?: string
    sections: RenderSection[]
    modelLabel: string
    createTime: string | null
  }

  /** 每条各自的补充意见 / 要点。按条目存：切到别的条目再回来，刚写的还在 */
  const refineNotes = ref<Record<number, string>>({})
  const refineBusy = ref(false)
  const refineErr = ref('')
  const adoptBusy = ref(false)
  /** 这份草稿的待审阅建议（库里的，旧的在前） */
  const suggestions = ref<Suggestion[]>([])
  /** 条目id → 正在看的那一版建议id；没选过取最新的 */
  const refinePick = ref<Record<number, number>>({})

  /** 某条的待审阅建议，旧的在前 */
  const suggestionsOf = (id: number) => suggestions.value.filter((s) => s.itemId === id && s.status === 'pending')

  /** 某条当前展示的那一版 */
  function suggestionOf(id: number): Suggestion | null {
    const list = suggestionsOf(id)
    if (!list.length) return null
    const picked = refinePick.value[id]

    return list.find((s) => s.suggestionId === picked) ?? list[list.length - 1]!
  }

  /**
   * 建议已过时：生成之后这一条又改过（拿编辑态比，未保存的手改也算）。
   * 过时的建议不让采用 —— 整条覆盖会冲掉手改的字；要么放弃，要么对着新正文重新优化
   */
  const isStale = (s: Suggestion) => (body.value[s.itemId] ?? '').trim() !== s.baseText.trim()

  /** 条目在队列里的建议状态：待审阅 / 已过时 / 无 */
  function suggestionState(id: number): '' | 'pending' | 'stale' {
    const s = suggestionOf(id)
    if (!s) return ''

    return isStale(s) ? 'stale' : 'pending'
  }

  /** 空条目又没有补充意见，模型手里只有条目要求 —— 后端会拦，这里先把按钮置灰 */
  function canRefine(id: number | null) {
    if (!id || !canEdit.value || refineBusy.value) return false

    return Boolean((body.value[id] ?? '').trim() || (refineNotes.value[id] ?? '').trim())
  }

  async function runRefine(id: number | null) {
    if (!id || !canRefine(id)) return
    refineErr.value = ''
    // busy 先置上再 await：保存要一两秒，这期间按钮还可点的话双击会发两次
    refineBusy.value = true
    // 代际在保存之前取：保存在途时草稿被删 / 换了，后面的请求不能带着新 draftId 发出去
    const gen = draftGen
    // 规范代号在保存之前抄下：保存在途时换了研究类型，请求不能带着旧草稿 id + 新规范代号发出去
    const code = checklistCode.value
    if (dirty.value || !draftId.value) {
      if (!(await saveDraft())) {
        if (gen !== draftGen) return
        refineBusy.value = false
        refineErr.value = draftErr.value || t('assistant.saveFirstFailed')
        return
      }
    }
    if (gen !== draftGen || code !== checklistCode.value) {
      if (gen === draftGen) refineBusy.value = false
      return
    }
    // 建议是对着「发请求那一刻」的正文生成的：等结果回来再取的话，生成期间又改过的字会被当成基准，
    // 本地判「未过时」、服务端判「已过时」，采用按钮点了只会一直报错
    const base = body.value[id] ?? ''
    const note = refineNotes.value[id] ?? ''
    const res = await authedCall(`/report-assist?lang=${lang()}`, 'POST', {
      draftId: draftId.value,
      itemId: id,
      guidelineCode: code,
      action: 'refine',
      instruction: note.slice(0, REFINE_NOTE_MAX),
    })
    if (gen !== draftGen) return
    refineBusy.value = false
    if (!res.ok) {
      refineErr.value = res.message

      return
    }
    const data = res.envelope?.data as unknown as { text: string; modelLabel: string; suggestionId: number | null }
    if (data.suggestionId == null) {
      // 建议没入库就没法采用（采用走的是按建议 id 写回）—— 如实说，不造一个假 id 让按钮点了没反应
      refineErr.value = t('assistant.sgNotSaved')
      return
    }
    const s: Suggestion = {
      suggestionId: data.suggestionId,
      itemId: id,
      runId: null,
      content: data.text,
      baseText: base,
      instruction: note,
      modelLabel: data.modelLabel,
      status: 'pending',
    }
    suggestions.value = [...suggestions.value, s]
    refinePick.value = { ...refinePick.value, [id]: s.suggestionId }
  }

  /** 在历次建议之间切换 */
  function pickSuggestion(id: number, delta: 1 | -1) {
    const list = suggestionsOf(id)
    const cur = list.findIndex((s) => s.suggestionId === suggestionOf(id)?.suggestionId)
    const next = list[Math.min(Math.max(cur + delta, 0), list.length - 1)]
    if (next) refinePick.value = { ...refinePick.value, [id]: next.suggestionId }
  }

  /** 放弃这一条当前那一版建议 */
  async function discardSuggestion(id: number) {
    const s = suggestionOf(id)
    if (!s || !draftId.value) return
    suggestions.value = suggestions.value.filter((x) => x.suggestionId !== s.suggestionId)
    await authedCall(`/report-drafts/${draftId.value}/suggestions/discard`, 'POST', { ids: [s.suggestionId] })
  }

  /**
   * 写回之后同步编辑态。**不许把 `dirty` 置 false**：写回是后端整份读回来、只换这几条、再写回去，
   * 客户端还没存的其他条目改动不在其中 —— 置假会让排好的那次自动保存被吞掉。
   * 编辑序号要加一：第五步的预览靠它判「合成之后改过没有」，不加的话采用之后预览还是旧的
   */
  function absorbApplied(applied: Record<string, string>, appliedIds: number[], sent: Record<number, string>) {
    const next = { ...body.value }
    let kept = false
    for (const [id, text] of Object.entries(applied)) {
      // 请求在途时这一条又被改过（另一步的输入框没锁）：留用户的字，并排一次保存把它写回去 ——
      // 拿服务端那份盖上去，在途期间敲的字就无声地没了
      if ((next[Number(id)] ?? '') !== (sent[Number(id)] ?? '')) kept = true
      else next[Number(id)] = text
    }
    body.value = next
    if (Object.keys(applied).length) editSeq += 1
    if (kept) touchDraft()
    suggestions.value = suggestions.value.filter((s) => !appliedIds.includes(s.suggestionId))
    markCheckStale()
    // applied 留痕是服务端在写回时自己记的，拉一次让它出现在留痕与 AI 使用说明里
    void loadTrail()
  }

  /**
   * 采用一条建议。先把未保存的手改落盘 —— 服务端拿库里的正文核「已过时」，不先存的话
   * 用户刚敲的字它看不见，就会把建议直接盖上去
   */
  async function adoptRefine(id: number, mode: 'replace' | 'append') {
    const s = suggestionOf(id)
    if (!s || !draftId.value || adoptBusy.value) return
    refineErr.value = ''
    if (isStale(s)) {
      refineErr.value = t('assistant.sgStale')
      return
    }
    adoptBusy.value = true
    const gen = draftGen
    if (dirty.value && !(await saveDraft())) {
      if (gen !== draftGen) return
      adoptBusy.value = false
      refineErr.value = draftErr.value || t('assistant.saveFirstFailed')
      return
    }
    if (gen !== draftGen) return
    const sent = { ...body.value }
    const res = await authedCall(`/report-drafts/${draftId.value}/suggestions/apply`, 'POST', { ids: [s.suggestionId], mode })
    if (gen !== draftGen) return
    adoptBusy.value = false
    if (!res.ok) {
      refineErr.value = res.message

      return
    }
    const data = res.envelope?.data as unknown as { applied: Record<string, string>; stale: number[] }
    if (data.stale.length) refineErr.value = t('assistant.sgStale')
    absorbApplied(data.applied, Object.keys(data.applied).length ? [s.suggestionId] : [], sent)
  }

  /** 某条最新的那一版待审阅建议 */
  const latestOf = (id: number) => {
    const list = suggestionsOf(id)

    return list.length ? list[list.length - 1]! : null
  }

  /**
   * 「全部采用」能采用的：每条**最新**那一版、且没过时的。
   * 不看用户在工作区里翻到了哪一版 —— 翻回旧版本看一眼，不该让「全部采用」写回旧版本
   */
  const adoptable = computed(() => {
    const out: Suggestion[] = []
    for (const id of new Set(suggestions.value.filter((s) => s.status === 'pending').map((s) => s.itemId))) {
      const s = latestOf(id)
      if (s && !isStale(s) && scope.value.has(id)) out.push(s)
    }

    return out
  })
  /** 已过时的条数，与「全部采用」同一个范围（只算纳入的清单表），两个数才对得上 */
  const staleSuggestionN = computed(() => {
    let n = 0
    for (const id of new Set(suggestions.value.filter((s) => s.status === 'pending').map((s) => s.itemId))) {
      const s = latestOf(id)
      if (s && isStale(s) && scope.value.has(id)) n += 1
    }

    return n
  })
  const adoptAllMsg = ref('')

  async function adoptAll() {
    const list = adoptable.value
    if (!list.length || !draftId.value || adoptBusy.value) return
    if (!window.confirm(t('assistant.sgAdoptAllConfirm', { n: list.length }))) return
    adoptBusy.value = true
    adoptAllMsg.value = ''
    const gen = draftGen
    if (dirty.value && !(await saveDraft())) {
      if (gen !== draftGen) return
      adoptBusy.value = false
      adoptAllMsg.value = draftErr.value || t('assistant.saveFirstFailed')
      return
    }
    if (gen !== draftGen) return
    const sent = { ...body.value }
    const res = await authedCall(`/report-drafts/${draftId.value}/suggestions/apply`, 'POST', {
      ids: list.map((s) => s.suggestionId),
      mode: 'replace',
    })
    if (gen !== draftGen) return
    adoptBusy.value = false
    if (!res.ok) {
      adoptAllMsg.value = res.message

      return
    }
    const data = res.envelope?.data as unknown as { applied: Record<string, string>; stale: number[] }
    const appliedIds = list.filter((s) => !data.stale.includes(s.suggestionId)).map((s) => s.suggestionId)
    absorbApplied(data.applied, appliedIds, sent)
    adoptAllMsg.value = t('assistant.sgAdoptAllDone', { n: Object.keys(data.applied).length, stale: data.stale.length })
  }

  // ---------------------------------------------------------------- 分钟级任务：一键优化 / 整篇成文

  const aiLive = ref<AiRunState | null>(null)
  const aiErr = ref('')
  /** 最近一次跑完的任务回执（一键优化：生成几条、失败几条、跳过几条、超长几条） */
  const aiDone = ref<{
    kind: string; done: number; failed: number; skipped: number; tooLong: number; ignored: number; unchanged: number; stopped: boolean
  } | null>(null)
  const render = ref<RenderState | null>(null)
  /** 提交中（还没拿到任务回执）：与「在跑」合起来锁按钮，双击不会提交两个分钟级任务 */
  const aiBusy = ref(false)
  let aiTimer: ReturnType<typeof setTimeout> | null = null
  /** 轮询连续失败的次数：偶发一次网络抖动重试，连续失败才放弃并解锁按钮 */
  let aiPollFails = 0
  const AI_POLL_MAX_FAILS = 5

  function stopAiPoll() {
    if (aiTimer) clearTimeout(aiTimer)
    aiTimer = null
  }

  const aiRunning = computed(() =>
    aiBusy.value || (aiLive.value != null && ['pending', 'running'].includes(aiLive.value.runStatus)),
  )

  /** 挂一次轮询；页面卸载了或草稿已经换了就不挂 */
  function scheduleAiPoll(gen: number, ms: number) {
    stopAiPoll()
    if (disposed || gen !== draftGen) return
    aiTimer = setTimeout(() => void pollAi(gen), ms)
  }

  /** 打开草稿时取回第四步的整份状态：在跑的任务（接回轮询）· 建议 · 最近的整篇成文 */
  async function loadAi() {
    stopAiPoll()
    const id = draftId.value
    const gen = draftGen
    if (!isLoggedIn.value || !id) return
    const res = await authedCall(`/report-drafts/${id}/ai`, 'GET')
    // 接口失败时不留任何东西：上一份草稿的建议与成文已经在 resetPerDraft 里清掉了
    if (!res.ok || gen !== draftGen || id !== draftId.value) return
    const data = res.envelope?.data as unknown as { live: AiRunState | null; render: RenderState | null; suggestions: Suggestion[] }
    suggestions.value = data.suggestions ?? []
    render.value = data.render
    if (data.live) {
      aiLive.value = data.live
      aiPollFails = 0
    }
    if (aiLive.value && ['pending', 'running'].includes(aiLive.value.runStatus)) scheduleAiPoll(gen, 800)
  }

  async function pollAi(gen: number) {
    const live = aiLive.value
    if (!live || gen !== draftGen || disposed) return
    const res = await authedCall(`/report-ai/${live.sessionId}`, 'GET')
    if (gen !== draftGen || disposed) return
    if (!res.ok) {
      aiPollFails += 1
      if (aiPollFails < AI_POLL_MAX_FAILS) {
        scheduleAiPoll(gen, 2000 * aiPollFails)
        return
      }
      // 连续失败：放弃这一轮轮询、解锁按钮。任务在 worker 那边照跑，刷新页面会接回来
      aiPollFails = 0
      aiLive.value = null
      aiErr.value = t('assistant.aiPollLost', { msg: res.message })
      return
    }
    aiPollFails = 0
    const st = res.envelope?.data as unknown as AiRunState
    aiLive.value = st
    if (['pending', 'running'].includes(st.runStatus)) {
      scheduleAiPoll(gen, 2000)

      return
    }
    if (st.runStatus === 'failed') aiErr.value = st.errorMsg || t('assistant.aiTaskFailed')
    aiDone.value = {
      kind: st.kind,
      done: st.doneCount,
      failed: st.failedCount,
      skipped: st.skippedCount ?? 0,
      tooLong: st.tooLongCount ?? 0,
      ignored: st.ignoredCount ?? 0,
      unchanged: st.unchangedCount ?? 0,
      stopped: st.runStatus === 'stopped',
    }
    // 落库是后端在这次轮询里做完的，重取一次把新建议 / 新成文拿回来
    await loadAi()
    if (gen !== draftGen) return
    // loadAi 可能接回了另一个正在跑的任务（另一个标签页刚提交的）：那时别拿已终结的这条把它盖掉
    const now = aiLive.value
    if (!now || now.sessionId === st.sessionId || !['pending', 'running'].includes(now.runStatus)) aiLive.value = st
    if (st.runStatus === 'completed') void loadTrail()
  }

  async function stopAi() {
    const live = aiLive.value
    if (!live) return
    const res = await authedCall(`/report-ai/${live.sessionId}/stop`, 'POST')
    if (!res.ok) aiErr.value = res.message
  }

  /** 提交一个分钟级任务的公共部分：锁按钮 → 先存 → 提交 → 接上轮询 */
  async function submitAi(kind: 'refine' | 'render', send: () => Promise<Awaited<ReturnType<typeof authedCall>>>) {
    aiBusy.value = true
    const gen = draftGen
    try {
      if (dirty.value || !draftId.value) {
        if (!(await saveDraft())) {
          if (gen === draftGen) aiErr.value = draftErr.value || t('assistant.saveFirstFailed')
          return
        }
      }
      if (gen !== draftGen) return
      const res = await send()
      if (gen !== draftGen) return
      if (!res.ok) {
        aiErr.value = res.message

        return
      }
      const data = res.envelope?.data as unknown as { runId: number; sessionId: string; itemTotal: number }
      aiPollFails = 0
      aiLive.value = {
        runId: data.runId, sessionId: data.sessionId, kind, runStatus: 'pending', progress: 0, phase: '',
        errorMsg: '', itemTotal: data.itemTotal, doneCount: 0, failedCount: 0, skippedCount: 0, tooLongCount: 0, ignoredCount: 0,
      }
      scheduleAiPoll(gen, 1500)
    } finally {
      // 只解锁自己这份草稿的按钮：提交在途时换了草稿，新草稿可能正在提交它自己的任务
      if (gen === draftGen) aiBusy.value = false
    }
  }

  /**
   * 一键优化。范围 `issues` = 第三步查出问题的条目；`filled` = 纳入范围内全部已填条目。
   * 空着又没写要点、或正文超长的由后端跳过并报回来；各条的补充事实一并带上
   */
  async function runBatch(range: 'issues' | 'filled') {
    if (!canEdit.value || aiRunning.value) return
    aiErr.value = ''
    aiDone.value = null
    const ids = range === 'issues'
      ? issueRows.value.map((r) => r.itemId)
      : scopedRows.value.filter((r) => (body.value[r.itemId] ?? '').trim()).map((r) => r.itemId)
    if (!ids.length) {
      aiErr.value = t('assistant.bgNothing')
      return
    }
    const instructions: Record<number, string> = {}
    for (const id of ids) {
      const note = (refineNotes.value[id] ?? '').trim()
      if (note) instructions[id] = note.slice(0, REFINE_NOTE_MAX)
    }
    await submitAi('refine', () =>
      authedCall(`/report-drafts/${draftId.value}/refine-batch?lang=${lang()}`, 'POST', { itemIds: ids, instructions }),
    )
  }

  /** 导入的草稿会被整篇重写；还有没审阅的建议时成文只用已采用的内容 —— 两件事都要先问一声 */
  async function runRender(domain = '') {
    if (!canEdit.value || aiRunning.value) return
    aiErr.value = ''
    aiDone.value = null
    if (!domain) {
      if (hasSource.value && !window.confirm(t('assistant.rdConfirmImported'))) return
      const pending = adoptable.value.length
      if (pending && !window.confirm(t('assistant.rdConfirmPending', { n: pending }))) return
    }
    await submitAi('render', () => authedCall(`/report-drafts/${draftId.value}/render`, 'POST', { domain }))
  }

  onBeforeUnmount(stopAiPoll)

  /** 这份草稿是不是导入的（带原稿） */
  const hasSource = computed(() => Boolean(drafts.value.find((d) => d.draftId === draftId.value)?.hasSource))
  /** 成文里过时的章节数 / 核对不通过的章节数 */
  const renderStaleN = computed(() => render.value?.sections.filter((s) => s.stale).length ?? 0)
  const renderBadN = computed(() => render.value?.sections.filter((s) => !s.ok).length ?? 0)

  /** 核对问题 → 一句人话 */
  function renderIssueText(issue: { kind: string; values: string[] }): string {
    const key = `assistant.rdIssue.${issue.kind}`
    const values = issue.values.join(isEn.value ? ', ' : '、')

    return te(key) ? t(key, { v: values }) : `${issue.kind}: ${values}`
  }

  // ================================================================ 合规与一致性检查（③）
  //
  // 真正干活的是 `tools/checklist_worker_tool` 常驻 worker：一次跑两类判定 —— 逐条完整性与
  // 全稿一致性。这里把草稿合成全文交过去（只含纳入的清单表），落库在后端：提交即落一行台账，
  // 轮询到终态时由后端写判定。这里只负责提交、轮询、渲染；打开草稿时取它最近一次跑完的结果。

  const checkState = ref<'idle' | 'running' | 'done' | 'error'>('idle')
  const checkSid = ref('')
  const checkPct = ref(0)
  const checkMsg = ref('')
  const checkErr = ref('')
  const checkResult = ref<CheckResult | null>(null)
  /** 检查之后又改过稿子 —— 结果只对检查那一刻的正文成立，得说出来 */
  const checkStale = ref(false)
  /** 这次检查是不是本页提交的：留痕只由提交它的那个页面记，刷新后接回的不重复记 */
  let checkOwn = false
  let checkTimer: ReturnType<typeof setTimeout> | null = null

  /**
   * 用户实际写下的字数（纳入范围内）。**不能拿合成全文的长度来判**：合成时每条空着的必填条目
   * 都会补一行「【待补充：条目 x】」，只写了两个字的草稿合成出来也有几千字
   */
  const writtenChars = computed(() =>
    scopedRows.value.reduce((n, r) => n + (body.value[r.itemId] ?? '').trim().length, 0),
  )

  const canCheck = computed(
    () =>
      canEdit.value &&
      !noItems.value &&
      checkState.value !== 'running' &&
      !importBusy.value &&
      writtenChars.value >= MIN_CHARS,
  )

  /**
   * 全稿校验的状态 → `.chk` 的配色档位。`na`（不适用）与 `unchecked`（没跑完）一律中性灰：
   * unchecked 若长得像「未见问题」，就等于把没跑过的检查当成了合格。
   */
  const CROSS_CLASS: Record<CrossStatus, string> = { ok: 'ok', warn: 'warn', issue: 'miss', na: 'na', unchecked: 'na' }
  const crossChecks = computed<CrossCheck[]>(() => checkResult.value?.consistency?.checks ?? [])

  /** 规则名走 i18n；引擎新加了规则而前端还没配词条时，退回显示 key，不显示成空白 */
  const ruleTitle = (key: string) => (te(`assistant.ckRule.${key}`) ? t(`assistant.ckRule.${key}`) : key)

  /**
   * 检查提交那一刻的编辑序号，以及提交前那份旧结果是否已过时。检查在跑时改稿不会立刻标过时
   * （那时页面上没有结果），要等结果回来再比；停止 / 失败时旧结果留着，也要按这两个值还原 ——
   * 提交时一并清掉的话，旧判定会以「不过时」的身份继续驱动问题清单与交付核对
   */
  let checkBaseSeq = 0
  let checkPrevStale = false

  function markCheckStale() {
    if (checkState.value === 'done' || checkState.value === 'error') checkStale.value = true
  }

  /** 结果没换（停止 / 失败）时：提交前就过时，或检查期间又改过，都算过时 */
  function restoreCheckStale() {
    checkStale.value = checkPrevStale || editSeq !== checkBaseSeq
  }

  /** 去掉所有空白再比 —— 合成全文时会插标题与换行，引文与条目正文的空白未必一致 */
  const squash = (s: string) => s.replace(/\s+/g, '')

  /**
   * 一致性发现 → 它引用的原文出自哪几条。
   *
   * 模型只照抄引文，不报条目号（报了也不可信）。引文取自合成全文，而全文由各条目正文拼成，
   * 所以拿引文回各条目正文里找就能定位；找不到（引文跨了两条、或检查后又改过）就只在
   * 结果区列出来，不硬挂到某一条上。短于 6 个字的引文不找 —— 太短会到处命中。
   */
  function itemsOfQuote(quote: string): number[] {
    const q = squash(quote)
    if (q.length < 6) return []
    const inScope = Object.entries(body.value).filter(([id]) => scope.value.has(Number(id)))
    const hits: number[] = []
    for (const [id, text] of inScope) {
      if (squash(text ?? '').includes(q)) hits.push(Number(id))
    }
    if (hits.length) return hits
    // 引文可能跨了条目边界：退一步用前 16 个字再找一次
    const head = q.slice(0, 16)
    if (head.length < 16) return []
    for (const [id, text] of inScope) {
      if (squash(text ?? '').includes(head)) hits.push(Number(id))
    }

    return hits
  }

  interface ItemFinding { check: CrossCheck; finding: CrossFinding }

  /** 条目 id → 挂在它上面的一致性发现 */
  const findingsByItem = computed(() => {
    const map = new Map<number, ItemFinding[]>()
    for (const check of crossChecks.value) {
      for (const finding of check.findings) {
        for (const id of itemsOfQuote(finding.evidence)) {
          const list = map.get(id) ?? []
          list.push({ check, finding })
          map.set(id, list)
        }
      }
    }

    return map
  })

  /** 条目 id → 非「已报告」的逐条判定（纳入范围内） */
  const verdictById = computed(() => {
    const map = new Map<number, Verdict>()
    for (const v of checkResult.value?.verdicts ?? []) {
      if (v.status !== 'reported' && scope.value.has(v.itemId)) map.set(v.itemId, v)
    }

    return map
  })

  /**
   * 条目 id → 需要在第二步导航上提醒的判定。
   *
   * 只挂**已填**条目上的 vague / missing：空条目本来就在导航里显示为空，再挂一个「未报告」
   * 只是重复；已填却被判未报告，说明写的内容没答到点子上，这才是要提醒的。
   */
  const verdictByItem = computed(() => {
    const map = new Map<number, Verdict>()
    for (const [id, v] of verdictById.value) {
      if ((body.value[id] ?? '').trim()) map.set(id, v)
    }

    return map
  })

  /** 导航上的标记：一致性问题优先（跨条目的矛盾比单条模糊更要紧） */
  function flagOf(itemId: number): '' | 'cross' | 'vague' {
    if (findingsByItem.value.has(itemId)) return 'cross'
    if (verdictByItem.value.has(itemId)) return 'vague'

    return ''
  }

  /**
   * ③ 的问题清单 = ④ 的默认工作队列。一条条目只出现一次，取最严重的那一类。
   * 没检查过时为空。
   */
  const issueRows = computed<IssueRow[]>(() => {
    if (!checkResult.value) return []
    const out: IssueRow[] = []
    for (const r of scopedRows.value) {
      const filled = Boolean((body.value[r.itemId] ?? '').trim())
      const cross = findingsByItem.value.get(r.itemId)
      const v = verdictById.value.get(r.itemId)
      if (cross?.length) out.push({ itemId: r.itemId, kind: 'cross', reason: cross[0]!.finding.detail })
      else if (v && filled) out.push({ itemId: r.itemId, kind: v.status === 'vague' ? 'vague' : 'missing', reason: v.reason })
      else if (v && !filled && r.required) out.push({ itemId: r.itemId, kind: 'blank', reason: v.reason })
    }

    return out.sort((a, b) => ISSUE_ORDER[a.kind as IssueKind] - ISSUE_ORDER[b.kind as IssueKind])
  })

  /** 各类问题的条数 */
  const issueCount = computed(() => {
    const n: Record<IssueKind, number> = { cross: 0, missing: 0, vague: 0, blank: 0 }
    for (const r of issueRows.value) if (r.kind !== 'ok') n[r.kind] += 1

    return n
  })

  /** 按清单表分的问题条数（③ 的概览：「CONSORT 未报告 3 · STRICTA 未报告 4」） */
  const issueByPart = computed(() =>
    checklistParts.value
      .filter((p) => partIncluded(p.partNo))
      .map((p) => ({
        ...p,
        n: issueRows.value.filter((r) => rowById.value.get(r.itemId)?.partNo === p.partNo).length,
      })),
  )

  const crossCount = computed(() => {
    const s = checkResult.value?.consistency?.summary

    return { issue: s?.issue ?? 0, warn: s?.warn ?? 0 }
  })

  function stopCheckPoll() {
    if (checkTimer) clearTimeout(checkTimer)
    checkTimer = null
  }

  function resetCheck() {
    stopCheckPoll()
    checkState.value = 'idle'
    checkSid.value = ''
    checkPct.value = 0
    checkMsg.value = ''
    checkErr.value = ''
    checkResult.value = null
    checkStale.value = false
    checkOwn = false
    checkPollFails = 0
    refineErr.value = ''
  }

  /** worker 吐回来的结果与库里读回来的详情形状略有不同，统一成一种 */
  function toCheckResult(raw: Record<string, unknown>, at: string | null): CheckResult {
    const verdicts = ((raw.verdicts ?? []) as Record<string, unknown>[]).map((v) => ({
      itemId: Number(v.itemId),
      status: v.status as Verdict['status'],
      evidence: String(v.evidence ?? ''),
      reason: String(v.reason ?? ''),
    }))
    const cross = (raw.consistency ?? null) as CrossResult | null
    const models = raw.models
    const errors = (raw.errors ?? []) as string[]

    return {
      verdicts,
      consistency: cross && Array.isArray(cross.checks) ? cross : null,
      truncated: Boolean(raw.truncated),
      partial: errors.length > 0,
      models: Array.isArray(models) ? (models as string[]) : String(models ?? '').split(' / ').filter(Boolean),
      at,
    }
  }

  /**
   * 挂一次检查轮询。带上「这是哪份草稿、哪个任务的轮询」：在途那次请求回来时草稿换了、任务停了，
   * 结果就丢掉、也不再挂下一次 —— 否则 A 稿的判定会写进 B 稿，组件卸载后还会一直轮询
   */
  /** 检查轮询连续失败的次数 */
  let checkPollFails = 0

  function scheduleCheck(gen: number, sid: string, ms: number) {
    stopCheckPoll()
    if (disposed || gen !== draftGen || sid !== checkSid.value) return
    checkTimer = setTimeout(() => void pollCheck(gen, sid), ms)
  }

  async function pollCheck(gen: number, sid: string) {
    if (disposed || gen !== draftGen || sid !== checkSid.value) return
    const res = await authedCall(`/checklist-review/${sid}`, 'GET')
    if (disposed || gen !== draftGen || sid !== checkSid.value) return
    if (!res.ok && checkPollFails + 1 < POLL_MAX_FAILS) {
      // 偶发一次失败重试：检查在 worker 那边照跑，一次网络抖动就判失败的话用户只会再提交一次
      checkPollFails += 1
      scheduleCheck(gen, sid, 2000 * checkPollFails)
      return
    }
    checkPollFails = 0
    if (!res.ok) {
      checkState.value = 'error'
      checkErr.value = res.message
      restoreCheckStale()

      return
    }
    const st = (res.envelope?.data ?? {}) as Record<string, unknown>
    checkMsg.value = String(st.message ?? '')
    const cur = Number(st.progressCurrent ?? 0)
    const total = Number(st.progressTotal ?? 100) || 100
    checkPct.value = Math.min(100, Math.round((cur / total) * 100))

    const status = String(st.status ?? '')
    if (status === 'completed') {
      const raw = (st.result ?? null) as Record<string, unknown> | null
      if (!raw) {
        checkState.value = 'error'
        checkErr.value = t('assistant.rvFailed', { msg: '' })
        restoreCheckStale()

        return
      }
      checkResult.value = toCheckResult(raw, new Date().toISOString())
      checkState.value = 'done'
      // 结果对应的是提交那一刻的正文：检查在跑时改过稿 / 采用过建议，一回来就是过时的
      checkStale.value = editSeq !== checkBaseSeq
      if (checkOwn) {
        checkOwn = false
        const done = checkResult.value
        const who = done.models.join(' / ') || t('assistant.auditSystem')
        const cross = done.consistency
        if (cross?.checks?.length) {
          // 全稿一致性复用同三个计数列：issue→missing、warn→vague、ok→reported
          pushTrail({
            event: 'cross',
            actor: who,
            missing: cross.summary?.issue ?? 0,
            vague: cross.summary?.warn ?? 0,
            reported: cross.summary?.ok ?? 0,
          })
        }
      }

      return
    }
    if (status === 'failed' || status === 'stopped') {
      checkState.value = 'error'
      checkErr.value = String(st.error || '') || t(status === 'stopped' ? 'assistant.rvStopped' : 'assistant.rvFailed', { msg: '' })
      restoreCheckStale()
      if (checkOwn) pushTrail({ event: 'failed', actor: t('assistant.auditSystem'), note: checkErr.value })
      checkOwn = false

      return
    }
    scheduleCheck(gen, sid, 2000)
  }

  /** 先落盘 → 合成全文 → 提交。合成读的是库里那份，没存成功就会查到上一版，所以保存失败就停 */
  async function runCheck() {
    if (!canCheck.value) return
    checkErr.value = ''
    // 先置「进行中」再 await：保存要一两秒，这期间按钮还可点的话双击会提交两次检查
    const before = checkState.value
    stopCheckPoll()
    checkPrevStale = checkStale.value
    checkBaseSeq = editSeq
    checkPollFails = 0
    checkState.value = 'running'
    checkPct.value = 0
    checkMsg.value = ''
    const gen = draftGen
    // 规范代号在保存之前抄下（理由同 runRefine）
    const code = checklistCode.value
    const fail = (msg: string) => {
      checkState.value = 'error'
      checkErr.value = msg
      restoreCheckStale()
    }
    if (dirty.value || !draftId.value) {
      if (!(await saveDraft())) {
        if (gen !== draftGen) return
        checkState.value = before
        restoreCheckStale()
        checkErr.value = draftErr.value || t('assistant.saveFirstFailed')
        return
      }
    }
    if (gen !== draftGen) return
    if (code !== checklistCode.value) {
      checkState.value = before
      restoreCheckStale()
      return
    }
    const comp = await authedCall(`/report-drafts/${draftId.value}/compose?lang=${lang()}`, 'POST')
    if (gen !== draftGen) return
    if (!comp.ok) {
      fail(comp.message)

      return
    }
    const text = String((comp.envelope?.data as { text?: string } | undefined)?.text ?? '').trim()
    const res = await authedCall('/checklist-review', 'POST', {
      guidelineCode: code,
      manuscript: text,
      locale: lang(),
      draftId: draftId.value,
    })
    if (gen !== draftGen) return
    if (!res.ok) {
      fail(res.message)

      return
    }
    const ticket = (res.envelope?.data ?? {}) as { sessionId?: string }
    checkSid.value = String(ticket.sessionId ?? '')
    if (!checkSid.value) {
      fail(t('assistant.rvFailed', { msg: '' }))

      return
    }
    checkOwn = true
    pushTrail({
      event: 'submitted',
      actor: guest.value?.username || t('assistant.auditYou'),
      guidelineCode: code,
      charCount: text.length,
    })
    scheduleCheck(gen, checkSid.value, 1500)
  }

  async function stopCheck() {
    const sid = checkSid.value
    if (!sid) return
    stopCheckPoll()
    checkOwn = false
    // 先把 sid 摘掉：在途那次轮询回来时对不上号，就不会把状态翻回「进行中」
    checkSid.value = ''
    const gen = draftGen
    await authedCall(`/checklist-review/${sid}/stop`, 'POST')
    if (gen !== draftGen) return
    checkState.value = checkResult.value ? 'done' : 'idle'
    restoreCheckStale()
  }

  interface ReviewHistoryRow {
    reviewId: number
    sessionId: string
    draftId: number | null
    runStatus: 'pending' | 'running' | 'completed' | 'failed' | 'stopped'
    progress: number
  }

  /**
   * 打开一份草稿时，把它的检查状态接回来。
   *
   * 1. 这份草稿有在跑的检查（刷新页面 / 从别处回来）→ 接回 session 继续轮询，进度从中途接上
   * 2. 否则取它最近一次跑完的检查结果（导入时那次映射也算）。检查之后草稿又被保存过，
   *    就标「结果可能已过时」—— 判据是草稿的更新时间晚于检查时间
   */
  async function loadCheck() {
    resetCheck()
    const id = draftId.value
    const gen = draftGen
    if (!isLoggedIn.value || !id) return

    const hist = await authedCall('/checklist-reviews', 'GET')
    if (id !== draftId.value || gen !== draftGen) return
    const rows = hist.ok ? ((hist.envelope?.data ?? []) as ReviewHistoryRow[]) : []
    const live = rows.find((r) => r.draftId === id && (r.runStatus === 'pending' || r.runStatus === 'running'))
    if (live?.sessionId) {
      checkBaseSeq = editSeq
      checkPrevStale = false
      checkSid.value = live.sessionId
      checkState.value = 'running'
      checkPct.value = live.progress ?? 0
      scheduleCheck(gen, live.sessionId, 500)

      return
    }

    const latest = await authedCall(`/report-drafts/${id}/review`, 'GET')
    const reviewId = latest.ok ? Number((latest.envelope?.data as { reviewId?: number } | undefined)?.reviewId ?? 0) : 0
    if (!reviewId || id !== draftId.value) return
    const detail = await authedCall(`/checklist-reviews/${reviewId}`, 'GET')
    if (!detail.ok || id !== draftId.value || gen !== draftGen) return
    const d = (detail.envelope?.data ?? {}) as Record<string, unknown>
    const at = (d.finishTime ?? d.createTime ?? null) as string | null
    checkResult.value = toCheckResult(d, at)
    checkState.value = 'done'
    const upd = drafts.value.find((x) => x.draftId === id)?.updateTime
    checkStale.value = Boolean(upd && at && toTime(upd) > toTime(at) + 60_000)
  }

  const checkStamp = (iso: string | null) => {
    if (!iso) return ''
    const d = new Date(iso.replace(' ', 'T'))
    if (Number.isNaN(d.getTime())) return iso
    const locale = isEn.value ? 'en-GB' : 'zh-CN'

    return `${d.toLocaleDateString(locale)} ${d.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', hour12: false })}`
  }

  onBeforeUnmount(stopCheckPoll)

  // ================================================================ AI 优化的工作队列（④）
  //
  // 队列只是选择器：一行一条、只有一个「处理」，点了就把这条送进右边那个**唯一**的工作区。
  // 曾经每条待办各挂一套工具，64 条待办就是 64 份重复版面 —— 甲方的原话是「非常乱」。

  /** `check` = ③ 查出来的问题；`all` = 纳入范围内的全部条目（没检查过也能用这一步） */
  const queueSource = ref<'check' | 'all'>('check')
  const queueRows = computed<IssueRow[]>(() => {
    if (queueSource.value === 'check' && checkResult.value) return issueRows.value
    const byId = new Map(issueRows.value.map((r) => [r.itemId, r]))

    return scopedRows.value.map((r): IssueRow => byId.get(r.itemId)
      ?? { itemId: r.itemId, kind: (body.value[r.itemId] ?? '').trim() ? 'ok' : 'blank', reason: '' })
  })
  /** ④ 当前处理的条目：队列里选过的那条；没选过取队列首条 */
  const refineItemId = ref<number | null>(null)
  const refineId = computed<number | null>(() => {
    const id = refineItemId.value
    if (id != null && scope.value.has(id)) return id

    return queueRows.value[0]?.itemId ?? null
  })
  const refineRow = computed(() => (refineId.value != null ? rowById.value.get(refineId.value) ?? null : null))
  /** 这一条的诊断：一致性发现 + 逐条判定 */
  const refineIssue = computed(() => issueRows.value.find((r) => r.itemId === refineId.value) ?? null)

  function pickRefine(id: number) {
    refineItemId.value = id
    // 第二步的当前条目跟着走：回到第二步时正停在这一条上
    selectItem(id, false, false)
  }
  /** 从 ③ 把一条交给 ④ */
  function optimizeItem(id: number) {
    queueSource.value = 'check'
    pickRefine(id)
    go(4)
  }

  // ================================================================ 留痕
  //
  // 记的是真实发生过的事（提交了什么、哪些模型判的、判成什么样、哪几条采用了 AI 的文字）。
  // 第五步的「AI 使用说明」也从这里算。

  const trail = ref<TrailRow[]>([])
  let trailSeq = 0

  const stamp = (iso?: string | null) =>
    (iso ? new Date(iso.replace(' ', 'T')) : new Date()).toLocaleTimeString(isEn.value ? 'en-GB' : 'zh-CN', {
      hour12: false,
    })

  /** 把一条结构化留痕渲染成人读的一句话。库里没有这句话，只有拼它用的那几个数 */
  function trailText(r: TrailRow): string {
    if (r.event === 'submitted') return t('assistant.auditSubmitted', { code: r.guidelineCode ?? '', chars: r.charCount ?? 0 })
    if (r.event === 'judged') {
      return t('assistant.auditJudged', {
        n: r.total ?? 0,
        ok: r.reported ?? 0,
        vague: r.vague ?? 0,
        miss: r.missing ?? 0,
        pct: r.completeness ?? 0,
      })
    }
    if (r.event === 'cross') {
      return t('assistant.auditCross', { issue: r.missing ?? 0, warn: r.vague ?? 0, ok: r.reported ?? 0 })
    }
    if (r.event === 'rendered') return t('assistant.auditRendered', { n: r.total ?? 0, ok: r.reported ?? 0 })
    if (r.event === 'applied') {
      const no = (r.itemId != null && rowById.value.get(r.itemId)?.no) || r.itemId || ''

      return t('assistant.auditApplied', { no, chars: r.charCount ?? 0 })
    }

    return r.note || t('assistant.auditFailed')
  }

  const auditTrail = computed(() =>
    trail.value.slice(0, 20).map((r) => ({
      id: r.trailId ?? -(r.localId ?? 0),
      at: stamp(r.createTime),
      who: r.actor || t('assistant.auditSystem'),
      what: trailText(r),
    })),
  )

  /**
   * 记一条留痕：先本地插入让用户立刻看到，再异步落库。
   * 落库失败不打断任何事 —— 留痕是旁路。AI 写回草稿那条由**服务端**自己记，不走这里。
   */
  function pushTrail(row: Omit<TrailRow, 'localId'>) {
    trail.value = [{ ...row, draftId: draftId.value, localId: ++trailSeq }, ...trail.value]
    if (!isLoggedIn.value) return
    void authedCall('/report-trails', 'POST', {
      event: row.event,
      draftId: draftId.value ?? undefined,
      guidelineCode: row.guidelineCode ?? checklistCode.value,
      actor: row.actor,
      itemId: row.itemId ?? undefined,
      total: row.total ?? undefined,
      reported: row.reported ?? undefined,
      vague: row.vague ?? undefined,
      missing: row.missing ?? undefined,
      completeness: row.completeness ?? undefined,
      charCount: row.charCount ?? undefined,
      note: (row.note ?? '').slice(0, 300),
    })
  }

  /** 拉回这份草稿的留痕。登录态水合后才知道，所以由 applyDraft 与登录态变化触发 */
  async function loadTrail() {
    const id = draftId.value
    if (!isLoggedIn.value || !id) {
      trail.value = []

      return
    }
    const gen = draftGen
    const res = await authedCall(`/report-trails?draftId=${id}`, 'GET')
    if (!res.ok || id !== draftId.value || gen !== draftGen) return
    trail.value = (res.envelope?.data ?? []) as TrailRow[]
  }

  /**
   * AI 使用说明（⑤）：哪几条、几次采用了 AI 生成的文字。现在很多期刊投稿要声明 AI 的使用，
   * 这段话由留痕里的 `applied` 事件算出来，用户复制即可。
   *
   * 取回的留痕撞到上限时说「至少」—— 更早的记录没取回来，报一个确数就是少报。
   */
  const aiUse = computed(() => {
    const applied = trail.value.filter((r) => r.event === 'applied' && r.itemId != null)
    const items = [...new Set(applied.map((r) => r.itemId!))]
    const nos = items.map((id) => rowById.value.get(id)?.no || String(id))

    return { times: applied.length, items: nos, capped: trail.value.length >= MAX_TRAIL_ROWS }
  })
  const aiUseText = computed(() => {
    const u = aiUse.value
    const items = u.times
      ? t(u.capped ? 'assistant.dlAiTextMin' : 'assistant.dlAiText', {
        n: u.items.length,
        times: u.times,
        items: u.items.join(isEn.value ? ', ' : '、'),
      })
      : ''
    // 正文用的是整篇成文：全文由 AI 组织成文，这一点必须写进声明，不能只报「采用了几条」
    if (bodySource.value === 'render') return [t('assistant.dlAiRender'), items].filter(Boolean).join(' ')

    return items || t('assistant.dlAiNone')
  })
  const aiCopied = ref(false)
  async function copyAiUse() {
    try {
      await navigator.clipboard?.writeText(aiUseText.value)
      aiCopied.value = true
      setTimeout(() => (aiCopied.value = false), 2000)
    } catch { /* 浏览器拒绝时文字就在框里，用户可以手选 */ }
  }

  // ================================================================ 成果交付（⑤）

  /** 初稿预览 —— 合成在后端（导出复用同一份逻辑，不在前端各写一遍） */
  const composed = ref('')
  const composeMissing = ref(0)
  const composing = ref(false)
  const rebuildInfo = ref<RebuildInfo | null>(null)
  /** 上次合成时的编辑序号：没改过就不重合成 */
  let composedAt = 0

  async function composeDraft() {
    if (!canEdit.value || composing.value) return
    // 先落盘再合成：合成读的是库里的草稿，没存成功就会拿到上一版内容，
    // 而用户看不出差别 —— 所以保存失败必须就地停住，不能把错误抹掉继续走
    composing.value = true
    const gen = draftGen
    if (dirty.value || !draftId.value) {
      if (!(await saveDraft())) {
        composing.value = false
        return
      }
    }
    if (gen !== draftGen) {
      composing.value = false
      return
    }
    draftErr.value = ''
    const seq = editSeq
    const res = await authedCall(`/report-drafts/${draftId.value}/compose?lang=${lang()}`, 'POST')
    composing.value = false
    if (gen !== draftGen) return
    if (!res.ok) {
      draftErr.value = res.message
      return
    }
    const data = res.envelope?.data as unknown as { text: string; missingRequired: number } & Partial<RebuildInfo>
    composed.value = data.text
    composeMissing.value = data.missingRequired
    rebuildInfo.value = data.fromSource ? (data as RebuildInfo) : null
    composedAt = seq
  }

  // 进第五步就把预览备好：核对单里「共用段落追加」那一项要靠它算。没改过就不重算。
  // 不只看 step：直接带 `?step=5` 落地（登录往返）时 step 在挂载时就变成了 5，那一刻草稿还没载入，
  // 之后草稿到了 step 却不再变 —— 所以草稿与可编辑状态变了也要再判一次
  let autoComposeKey = ''
  watch([step, draftId, canEdit, composing], ([n]) => {
    if (n !== 5 || !draftId.value || !canEdit.value || composing.value) return
    if (composed.value && composedAt === editSeq) return
    // 合成在途时换了草稿：那次结果被代际丢掉，composing 落下时这里会再判一次。
    // 同一份草稿、同一版正文只自动试一次 —— 合成失败时不至于来回重试
    const key = `${draftGen}:${editSeq}`
    if (key === autoComposeKey) return
    autoComposeKey = key
    void composeDraft()
  })

  /**
   * 第五步导出的正文用哪一份：`render` = 第四步的整篇成文；`auto` = 原稿写回（导入的草稿）/ 条目合成。
   * 默认：有成文、且不是导入的草稿 → 成文；导入的草稿默认原稿写回（保留用户自己论文的格式）。
   * 用户选过就听用户的
   */
  const bodyPick = ref<'' | 'render' | 'auto'>('')
  const bodySource = computed<'render' | 'auto'>(() => {
    if (!render.value?.sections.length) return 'auto'
    if (bodyPick.value) return bodyPick.value

    return hasSource.value ? 'auto' : 'render'
  })
  /** 成文的纯文本（第五步预览用） */
  const renderText = computed(() =>
    (render.value?.sections ?? [])
      .map((s) => [s.domain, ...s.paragraphs.map((p) => p.text)].join(PARA_BREAK))
      .join(PARA_BREAK),
  )

  /** 交付前核对（只提醒，不拦导出） */
  const deliverList = computed(() => {
    const list: { key: string; count: number; itemIds: number[] }[] = deliverChecks({
      rows: checklistRows.value,
      included: includedParts.value,
      body: body.value,
      verdicts: checkResult.value?.verdicts ?? [],
      checked: Boolean(checkResult.value),
      stale: checkStale.value,
    })
    if (bodySource.value === 'render') {
      if (renderStaleN.value) list.push({ key: 'renderStale', count: renderStaleN.value, itemIds: [] })
      if (renderBadN.value) list.push({ key: 'renderIssues', count: renderBadN.value, itemIds: [] })
    } else if (rebuildInfo.value?.appended) {
      list.push({ key: 'appended', count: rebuildInfo.value.appended, itemIds: [] })
    }

    return list
  })

  const exporting = ref('')
  const exportErr = ref('')

  /**
   * 下载一份导出文件。走 `authedBlob` 而不是普通 `authedCall`：本站错误是「HTTP 200 + code≠200」
   * 的 JSON 信封，与文件走同一条通道，靠 Content-Type 区分（后端因此必须显式给 media type）。
   */
  async function downloadExport(fmt: string) {
    if (!draftId.value || exporting.value) return
    const gen = draftGen
    exporting.value = fmt
    exportErr.value = ''
    if (dirty.value && !(await saveDraft())) {
      if (gen === draftGen) exporting.value = ''
      return
    }
    if (gen !== draftGen) return
    // 文件名按发请求这一刻的草稿取：下载回来时可能已经换了草稿
    const title = draftTitle.value
    const body = fmt === 'docx' && bodySource.value === 'render' ? '&body=render' : ''
    const res = await authedBlob(`/report-drafts/${draftId.value}/export?fmt=${fmt}&lang=${lang()}${body}`)
    if (gen !== draftGen) return
    exporting.value = ''
    if (!res.ok || !res.blob) {
      exportErr.value = res.message
      return
    }
    const url = URL.createObjectURL(res.blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${(title || 'report').slice(0, 60)}.${fmt}`
    // 挂进 DOM 再点、过一会儿再撤销：同步撤销的话部分浏览器（Firefox / Safari）会取消下载或下到空文件。
    // 不撤销的话每导一次泄漏一个 blob，一个长会话里能攒出几十兆
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 10_000)
  }

  return {
    // 依赖与小工具
    t, te, pick, isEn, isLoggedIn, loginLink,
    // 向导
    step, wizardEl, go,
    // 草稿
    drafts, myDrafts, draftId, body, draftTitle, draftErr, draftBusy, dirty, savedAt, saving, canEdit,
    touchDraft, openDraft, newDraft, saveDraft, removeDraft, resumeDraft, continueDraft,
    // 清单表
    includedParts, partIncluded, togglePart, partErr, currentPart, currentPartInfo, selectPart, partProgress,
    scope, scopedRows, requiredIds, filledIds, requiredFilled, donePct, overLongRow,
    // 导航
    navGroups, currentId, activeRow, prevId, nextId, activeLen, isDomainOpen, toggleDomain,
    navEl, paneEl, paneTa, selectItem, goItem, editItem,
    // 导入
    importInput, importBusy, importErr, importPct, importMsg, importDone, pickImport, startStage,
    // AI 完善
    refineNotes, refineBusy, refineErr, adoptBusy, suggestions, refinePick,
    suggestionsOf, suggestionOf, suggestionState, isStale, canRefine, runRefine, pickSuggestion, discardSuggestion,
    adoptRefine, adoptable, staleSuggestionN, adoptAll, adoptAllMsg,
    // 一键优化 · 整篇成文
    aiLive, aiErr, aiDone, aiRunning, runBatch, runRender, stopAi, render, hasSource, renderStaleN, renderBadN,
    renderIssueText,
    // 检查
    checkState, checkPct, checkMsg, checkErr, checkResult, checkStale, writtenChars, canCheck,
    CROSS_CLASS, crossChecks, ruleTitle, itemsOfQuote, findingsByItem, verdictById, verdictByItem, flagOf,
    issueRows, issueCount, issueByPart, crossCount, runCheck, stopCheck, checkStamp,
    // 优化队列
    queueSource, queueRows, refineId, refineRow, refineIssue, pickRefine, optimizeItem,
    // 留痕与交付
    auditTrail, aiUse, aiUseText, aiCopied, copyAiUse,
    composed, composeMissing, composing, rebuildInfo, composeDraft, deliverList, bodyPick, bodySource, renderText,
    exporting, exportErr, downloadExport,
  }
}

export type ReportWorkspace = ReturnType<typeof useReportWorkspace>
