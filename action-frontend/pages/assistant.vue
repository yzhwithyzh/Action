<script setup lang="ts">
/**
 * assistant.html 迁移而来。
 * 模板与样式保持原状；样式已加 .page-assistant 命名空间，避免 SPA 路由切换时跨页污染。
 */
const { t, te } = useI18n()

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

/**
 * 问题 1 的选项（`TYPE_OPTS`）与默认答案（`WIZARD_DEFAULTS`）都在
 * `composables/wizardQuery.ts` —— 那边同时负责 query 的构造与校验，
 * 词表跟着校验走才不会出现「页面上能选、从 URL 进来却被判非法」。
 *
 * 前四个是研究者最常自认的类型；后三个（试验方案 / 动物实验 / 临床实践指南）是补进来的
 * —— 库里 SPIRIT 79 条、RIGHT 42 条、ARRIVE 21 条 checklist 原先在助手里没有任何路径
 * 能走到，第二步展不开、第三步也就校验不了，而这三类在规范目录页里一直陈列着。
 *
 * 值与 `action_study_type.type_key` 一一对应，只有 `trial` 是例外：它还要靠问题 2
 * 才能落到 rct / nrct 上。
 */

/** 三个问题的当前答案 */
const ans = ref<WizardAnswers>({ ...WIZARD_DEFAULTS })

/** 是否显示「随机化 / 假针」两个子问题 —— 仅试验类才问 */
const showSubQ = computed(() => ans.value.type === 'trial')

/**
 * 第一步末尾选的路线（`draft` 从零开始写 / `manuscript` 已有稿件 / `''` 还没选）。
 *
 * 这个向导实际服务两类人:从零开始写的人第 2 步是主菜、第 3 步的完整性判定几乎必然全绿;
 * 已经写好稿子的人第 2 步整个用不上、第 3 步才是主菜。五步线性排布在暗示「都要走一遍」,
 * 于是两类人各自都会撞上一屏与自己无关的东西。这里**只标注不强制**:两条路的步骤都点得进去,
 * 只是把「哪几步对你适用」说出来。
 */
const stage = computed({
  get: () => ans.value.stage,
  set: (v: string) => { ans.value.stage = v },
})

/** 把答案解析成 action_study_type.type_key */
const resolvedKey = computed(() => {
  const a = ans.value
  if (a.type !== 'trial') return a.type

  return a.rand === 'y' ? 'rct' : 'nrct'
})

const matched = computed<StudyTypeRow | null>(
  () => types.value.find((x) => x.typeKey === resolvedKey.value) ?? null,
)

/** 假针 / 安慰针问题的报告提示 —— 仅试验类才有对照措施可谈 */
const shamNote = computed(() =>
  showSubQ.value ? t(ans.value.sham === 'y' ? 'assistant.shamNoteY' : 'assistant.shamNoteN') : '',
)

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
  /** 填写要求：'0' 必填 / '1' 条件填写。库里由 sql/007 的关键词启发式回填，后台可逐条改 */
  requireLevel: string | null
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
      itemId: it.itemId,
      required: (it.requireLevel ?? '0') === '0',
    }
  }),
)

/** 清单表张数，用于「共 N 条 · M 张清单表」 */
const checklistPartCount = computed(() => new Set(checklist.value.map((i) => i.partNo)).size)

const { guest, isLoggedIn, authedCall, authedBlob } = useAuth()
const route = useRoute()
const router = useRouter()
/** 登录后跳回本页 —— 连同 query 里的向导位置与第一步答案一起带回来，见下一段 */
const loginLink = computed(() => `/login?redirect=${encodeURIComponent(route.fullPath)}`)

/**
 * 五步向导的位置与第一步的三个答案，同步进 URL query。
 *
 * **动机是登录往返。** `loginLink` 用的是 `route.fullPath`，而 step 与 ans 原先都是普通
 * ref、不进 URL，于是「第一步选完 → 翻到第二步撞上登录墙 → 去登录 → 回来落在第一步、
 * 答案清空」，用户得从头再走一遍。位置进了 URL，`?redirect=` 就天然把它带回来了
 * （`resolveRedirect` 保留 query 与 hash，见 `test/authValidation.spec.ts`）。
 * 顺带白拿一个能力：第二步的链接可以直接分享或收藏。
 *
 * **这一段刻意放在草稿逻辑上面**：还原必须早于下面那次 `loadDrafts()` 的 onMounted
 * （onMounted 按注册顺序跑），否则挂载瞬间会先按默认规范取一遍草稿、还原后再取一遍，
 * 中间还会闪一下别的规范的草稿。
 *
 * **还原只能在挂载之后做。** 全站是预渲染静态站，构建期烤进 HTML 的永远是 step=1 那一版；
 * 若在 setup 阶段就按 query 算出 step=2，客户端首帧与静态 HTML 不一致，而面板显隐是
 * `:class="{ 'is-hidden': ... }"` —— **Vue 的 hydration 不修 class**（同 `SiteHeader.vue`
 * 的 `menuIsEn` 那个坑），表现会是「步骤条停在第 2 步、内容却还是第 1 步」，且只在直接
 * 打开带 query 的地址时出现。挂载后再赋值是普通的响应式更新，class 会正常 patch。
 */
const step = ref(1)
const wizardEl = ref<HTMLElement | null>(null)

/** 跳到第 n 步；越界钳位。滚回向导顶部，避免长面板切换后停在半空 */
function go(n: number) {
  const next = Math.min(WIZARD_STEP_COUNT, Math.max(1, n))
  if (next === step.value) return
  step.value = next
  // 第四步的输入是第三步对当前草稿的判定 —— 用户可能是上次跑完校验、这次直接回来的，
  // 所以进这一步时按需拉一次，而不是只依赖第三步跑完那一下
  if (next === 3) void loadTrail()
  if (next === 4) void loadReview()
  wizardEl.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(() => {
  const restored = parseWizardQuery(route.query)
  ans.value = restored.ans
  step.value = restored.step
  // 写回的监听要在还原**之后**才挂：先挂的话，挂载瞬间那一次 replace 会拿默认值
  // 把 URL 上刚带进来的答案冲掉，等于这个功能自己把自己废了。
  // 用 replace 不用 push —— 每点一个选项压一条历史，返回键就成了「逐个撤销我的选择」。
  // ans 是对象 ref，模板里是 `ans.type = k` 这种就地改，必须 deep 才监听得到
  watch(
    [step, ans],
    () => void router.replace({ query: buildWizardQuery(step.value, ans.value) }),
    { deep: true },
  )
})

/**
 * 第二步：报告草稿 —— 把只读的条目清单变成可编辑、可保存、可生成初稿的编辑页。
 *
 * 文档 2 要的三件事在这里各有落点：
 *  · 必填 / 条件填写   → 条目的 `requireLevel`，角标 + 完成度分母
 *  · 一键生成初稿       → `composeDraft()`，合成在后端（第五步导出将来要复用同一份逻辑）
 *  · 关键参数一次定义、全文联动 → 针灸四字段存在草稿主表，合成时注入到相关条目下
 *
 * **未登录访客一个草稿接口都不发**：这一段整体挂在 `isLoggedIn` 后面。
 * 条目清单本身照常展示（那是公开数据），只是不可编辑。
 */
interface DraftItem { itemId: number; content: string }
interface DraftRow {
  draftId: number
  guidelineId: number
  guidelineCode: string
  studyTypeKey: string
  title: string
  items: DraftItem[]
  itemTotal: number
  filledCount: number
  requiredTotal: number
  requiredFilled: number
  updateTime: string | null
}

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
 * 连同「还没存」这个事实一起抹掉：界面显示「已保存」、保存按钮变灰，内容却没落库。
 */
let editSeq = 0
/** 保存串行化队列。并发两次 PUT 会在 (draft_id,item_id) 唯一索引上撞车 */
let savePromise: Promise<boolean> = Promise.resolve(true)

/** 只列当前规范的草稿：第二步展开的是第一步匹配到的那份规范，混列别的规范只会选错 */
const myDrafts = computed(() => drafts.value.filter((d) => d.guidelineCode === checklistCode.value))
/**
 * 能否编辑。**刻意不要求 `draftId` 非空** —— 登录用户第一次进第二步时就该看到一份
 * 可写的空骨架，而不是先点一次「新建草稿」；草稿在第一次保存时才真的建出来
 * （`ensureDraft`），这样只是路过看看的人也不会在库里留下空壳。
 * 条目还在载入时不给编辑：那会儿渲染的还是上一份规范的条目，写进去的 itemId 是旧的。
 */
const canEdit = computed(
  () => isLoggedIn.value && Boolean(checklistCode.value) && !ckLoading.value && checklist.value.length > 0,
)

/** 完成度：分母是必填条目数 —— 选填项本就可能不适用于这份研究，算进去会让进度永远到不了头 */
const requiredIds = computed(
  () => new Set(checklist.value.filter((it) => (it.requireLevel ?? '0') === '0').map((it) => it.itemId)),
)
const filledIds = computed(
  () => new Set(checklist.value.map((it) => it.itemId).filter((id) => (body.value[id] ?? '').trim())),
)
const requiredFilled = computed(() => [...filledIds.value].filter((id) => requiredIds.value.has(id)).length)
const donePct = computed(() =>
  requiredIds.value.size ? Math.round((requiredFilled.value / requiredIds.value.size) * 100) : 0,
)

/** 单条正文的字符上限，与后端 `MAX_DRAFT_ITEM_CHARS` 对齐 */
const MAX_ITEM_CHARS = 20000
/** 超长的那一条 —— 后端只会回一句字段级 422，不指明是几十条里的哪一条 */
const overLongRow = computed(() =>
  checklistRows.value.find((r) => (body.value[r.itemId] ?? '').length > MAX_ITEM_CHARS) ?? null,
)

function stopAutoSave() {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = null
}

/** 有改动就标脏并排一次自动保存。4 秒是「停下来想一句话」的时长，比逐字保存省得多 */
function touchDraft() {
  if (!canEdit.value) return
  editSeq += 1
  dirty.value = true
  stopAutoSave()
  saveTimer = setTimeout(() => void saveDraft(), 4000)
}

/** 把接口回来的草稿灌进编辑态 */
function applyDraft(row: DraftRow) {
  draftId.value = row.draftId
  draftTitle.value = row.title
  body.value = Object.fromEntries(row.items.map((it) => [it.itemId, it.content]))
  // 换了一份草稿，第四步要跟着换成这一份的判定
  resetWork()
  if (step.value === 4) void loadReview()
  dirty.value = false
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
  // 已经打开的那份还在列表里就别动它，否则每次回到第二步都会跳回最近改的那份
  if (draftId.value && mine.some((d) => d.draftId === draftId.value)) return
  if (mine.length) await openDraft(mine[0]!.draftId)
  else resetDraft()
}

function resetDraft() {
  stopAutoSave()
  draftId.value = null
  draftTitle.value = ''
  body.value = {}
  // 判定与建议都是「上一份草稿」的，留着会拿旧判定去改新稿子
  resetWork()
  dirty.value = false
  composed.value = ''
}

/**
 * 离开当前草稿之前先把改动落盘。
 *
 * 切草稿 / 改研究类型 / 离开页面这几条路都会整体覆盖或清空 `body`，
 * 而自动保存是 4 秒防抖 —— 不先存一次，最后这几秒的输入就无声无息地没了。
 */
async function leaveDraft() {
  stopAutoSave()
  if (dirty.value && canEdit.value) await saveDraft()
}

async function openDraft(id: number) {
  if (!isLoggedIn.value || id === draftId.value) return
  await leaveDraft()
  const prev = draftId.value
  draftBusy.value = true
  draftErr.value = ''
  composed.value = ''
  const res = await authedCall(`/report-drafts/${id}`, 'GET')
  draftBusy.value = false
  if (!res.ok) {
    draftErr.value = res.message
    // 下拉的 DOM 值已经跟着用户的选择变了，而 draftId 没变 —— 绑同一个值不会触发重渲染，
    // 于是「显示的是 B、编辑的是 A」。先置空再放回去，强制把 select 拨回真实状态
    draftId.value = null
    await nextTick()
    draftId.value = prev
    return
  }
  applyDraft(res.envelope?.data as DraftRow)
}

/**
 * 确保有一份草稿可写。空骨架在第一次保存时才真的建出来，所以这里**不能** applyDraft
 * —— 那会把用户刚敲进去的内容清空。
 */
async function ensureDraft(): Promise<boolean> {
  if (draftId.value) return true
  if (!isLoggedIn.value || !checklistCode.value) return false
  const res = await authedCall('/report-drafts', 'POST', {
    guidelineCode: checklistCode.value,
    studyTypeKey: resolvedKey.value,
    title: draftTitle.value,
  })
  if (!res.ok) {
    draftErr.value = res.message
    return false
  }
  const row = res.envelope?.data as DraftRow
  draftId.value = row.draftId
  if (!draftTitle.value) draftTitle.value = row.title
  drafts.value = [{ ...row, items: [] }, ...drafts.value]

  return true
}

/** 「新建草稿」按钮：先把当前这份落盘，再开一份空的 */
async function newDraft() {
  if (!isLoggedIn.value || !checklistCode.value) return
  await leaveDraft()
  draftBusy.value = true
  draftErr.value = ''
  resetDraft()
  const ok = await ensureDraft()
  draftBusy.value = false
  if (ok) await loadDrafts(false)
}

/**
 * 第二步的第二条路：导入已有稿件。
 *
 * ## 为什么导入口在这里，不在第三步
 *
 * 第三步只产出**只读**判定：导进去之后第四步没有草稿条目可写回、第五步的数据源是草稿
 * 于是整个导不出、下次再来还得重新粘一遍。而「哪些条目没覆盖」第三步其实已经算出来了
 * —— 缺的只是把它落成一份可继续加工的草稿。导入挪到这里，下游三步一次性全接通。
 *
 * ## 原稿不会被拆碎
 *
 * 后端把整篇原稿单独存着（`source_text`），**第五步导出正文以它为准**；条目框只装
 * 「从原稿里摘出来的对应段落」，是对照与改写的工作面。不这么分的话，导出拼回来的
 * 就不是用户写的那篇了 —— 一句话常同时答好几条，而讨论、致谢、参考文献不对应任何条目。
 *
 * ## 映射是异步的
 *
 * 建草稿同步完成（立刻有 draftId），条目映射是几分钟级的 worker 任务，
 * 走第三步那个轮询口。跑完再打开草稿 —— 早开一步看到的是一片空框，很像导入失败了。
 */
const IMPORT_ACCEPT = '.docx,.pdf,.txt,.md'
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

async function pickImport(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  // 清掉 value，否则连着选同一个文件不会再触发 change
  input.value = ''
  if (!file || !isLoggedIn.value || !checklistCode.value || importBusy.value) return

  await leaveDraft()
  stopImportPoll()
  importBusy.value = true
  importErr.value = ''
  importDone.value = null
  importPct.value = 0
  importMsg.value = t('assistant.dfImportParsing')

  const form = new FormData()
  form.append('file', file)
  form.append('guidelineCode', checklistCode.value)
  form.append('studyTypeKey', resolvedKey.value ?? '')
  form.append('title', '')

  const res = await authedCall(`/report-drafts/import?lang=${isEn.value ? 'en' : 'zh'}`, 'POST', form)
  if (!res.ok) {
    importBusy.value = false
    importErr.value = res.message

    return
  }
  const data = (res.envelope?.data ?? {}) as {
    draftId: number
    sessionId: string
    sourceName: string
    sourceLines: number
  }
  importMsg.value = t('assistant.dfImportMatching')
  await pollImport(data.sessionId, data.draftId, data.sourceName, data.sourceLines)
}

async function pollImport(sid: string, newDraftId: number, name: string, lines: number) {
  const tick = async () => {
    const res = await authedCall(`/checklist-review/${sid}`, 'GET')
    if (!res.ok) {
      importBusy.value = false
      importErr.value = res.message

      return
    }
    const st = (res.envelope?.data ?? {}) as Record<string, unknown>
    const cur = Number(st.progressCurrent ?? 0)
    const total = Number(st.progressTotal ?? 100) || 100
    importPct.value = Math.min(100, Math.round((cur / total) * 100))
    if (st.message) importMsg.value = String(st.message)

    const status = String(st.status ?? '')
    if (status === 'completed') {
      importBusy.value = false
      // 回填是后端在这次轮询里做完的，所以现在才打开草稿 —— 早开一步是一片空框
      await loadDrafts(false)
      await openDraft(newDraftId)
      const filled = filledIds.value.size
      importDone.value = { filled, total: checklist.value.length, lines, name }

      return
    }
    if (status === 'failed' || status === 'stopped') {
      importBusy.value = false
      // **草稿已经建好了**：映射失败不等于白导，原稿还在，用户可以自己逐条填或去第三步跑
      importErr.value = String(st.error || '') || t('assistant.dfImportFailed')
      await loadDrafts(false)
      await openDraft(newDraftId)

      return
    }
    importTimer = setTimeout(tick, 2500)
  }
  await tick()
}

onBeforeUnmount(stopImportPoll)

/**
 * 保存。**串行化**：已有一次在途时排队等它结束再存 ——
 * 并发两次 PUT 会撞 (draft_id,item_id) 唯一索引，而直接丢弃这次调用
 * （原先的 `if (saving) return`）会让在途期间敲的字永远存不进去。
 */
function saveDraft(): Promise<boolean> {
  savePromise = savePromise.catch(() => false).then(() => doSave())

  return savePromise
}

async function doSave(): Promise<boolean> {
  if (!canEdit.value) return false
  const over = overLongRow.value
  if (over) {
    draftErr.value = t('assistant.dfTooLong', { no: over.no || over.seq, max: MAX_ITEM_CHARS })
    return false
  }
  if (!(await ensureDraft())) return false

  const seq = editSeq
  stopAutoSave()
  saving.value = true
  draftErr.value = ''
  const res = await authedCall(`/report-drafts/${draftId.value}`, 'PUT', {
    title: draftTitle.value,
    // 整体覆盖语义：空内容也要带上，否则「用户清空了这条」会被当成「这次没带这条」
    items: Object.entries(body.value).map(([id, content]) => ({ itemId: Number(id), content })),
  })
  saving.value = false
  if (!res.ok) {
    draftErr.value = res.message
    return false
  }
  savedAt.value = new Date().toLocaleTimeString(isEn.value ? 'en-GB' : 'zh-CN', { hour12: false })
  const row = res.envelope?.data as DraftRow
  // 标题可能被后端规范化（清空时保留旧名），不回写的话输入框与下拉里的名字会长期对不上
  draftTitle.value = row.title
  const idx = drafts.value.findIndex((d) => d.draftId === row.draftId)
  if (idx >= 0) drafts.value[idx] = { ...row, items: [] }
  // 请求这一两秒里又改过 —— 别把 dirty 清掉，另排一次
  if (editSeq === seq) dirty.value = false
  else touchDraft()

  return true
}

async function removeDraft() {
  if (!draftId.value) return
  // 主表是逻辑删，但条目正文是**物理删**，几十条已写好的内容不可恢复，值得挡一下
  if (!window.confirm(t('assistant.dfDeleteConfirm'))) return
  stopAutoSave()
  draftBusy.value = true
  const res = await authedCall(`/report-drafts/${draftId.value}`, 'DELETE')
  draftBusy.value = false
  if (!res.ok) {
    draftErr.value = res.message
    return
  }
  const removed = draftId.value
  drafts.value = drafts.value.filter((d) => d.draftId !== removed)
  resetDraft()
  const mine = myDrafts.value
  if (mine.length) await openDraft(mine[0]!.draftId)
}

/** 一键生成初稿 —— 合成在后端（第五步导出将来复用同一份逻辑，不在前端各写一遍） */
const composed = ref('')
const composeMissing = ref(0)
const composing = ref(false)

async function composeDraft() {
  if (!canEdit.value) return
  // 先落盘再合成：合成读的是库里的草稿，没存成功就会拿到上一版内容，
  // 而用户看不出差别 —— 所以保存失败必须就地停住，不能把错误抹掉继续走
  if (dirty.value || !draftId.value) {
    const ok = await saveDraft()
    if (!ok) return
  }
  composing.value = true
  draftErr.value = ''
  const res = await authedCall(`/report-drafts/${draftId.value}/compose?lang=${isEn.value ? 'en' : 'zh'}`, 'POST')
  composing.value = false
  if (!res.ok) {
    draftErr.value = res.message
    return
  }
  const data = res.envelope?.data as { text: string; missingRequired: number }
  composed.value = data.text
  composeMissing.value = data.missingRequired
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
})

// 登录态与所选规范都可能在页面存活期间变化（水合后 fetchMe 回来、第一步换研究类型），
// 两者任一变化都要重新取草稿；未登录时清空，避免上一个账号的草稿留在界面上
watch([isLoggedIn, checklistCode], async ([loggedIn], [wasLoggedIn]) => {
  // 还登录着就先把改动落盘再切；掉登录态时存不进去，别白发一次 401
  if (wasLoggedIn && loggedIn) await leaveDraft()
  resetDraft()
  drafts.value = []
  if (loggedIn && checklistCode.value) await loadDrafts()
})
onMounted(() => {
  if (isLoggedIn.value && checklistCode.value) void loadDrafts()
})

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

/**
 * 第二类判定：全稿逻辑一致性与术语标准化（`engine/consistency.py`）。
 *
 * 与逐条判定的区别在于「问题不属于某一条 checklist 条目」，而是各处对不上，
 * 所以自成一段，不混进上面那份逐条清单里。
 */
interface CrossFinding {
  severity: 'warn' | 'issue'
  lines: number[]
  evidence: string
  detail: string
  suggestion: string
}
type CrossStatus = 'ok' | 'warn' | 'issue' | 'na' | 'unchecked'
interface CrossCheck {
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

interface ReviewResult {
  summary: ReviewSummary
  verdicts: Verdict[]
  /** worker 未更新到带全稿校验的版本时没有这一段，按「没跑过」处理 */
  consistency?: CrossResult
  lineCount: number
  truncated: boolean
  models?: string[]
}

const manuscript = ref('')

/**
 * 待校验的稿件是不是第二步合成出来的那一份。
 *
 * 用比对而不是挂个标志位：用户送过来之后又在文本框里改了几笔，标志位就成了谎话，
 * 而这个值决定的是要不要跟用户说「完整性多半是满的」——说错了比不说更糟。
 */
const reviewFromDraft = computed(
  () => Boolean(composed.value.trim()) && manuscript.value.trim() === composed.value.trim(),
)

/**
 * 把生成的初稿送进第三步。
 *
 * 这一步之前是断的：第二步只读，用户得自己把稿件贴进第三步。接上之后
 * 「模板 → 初稿 → 校验」才是一条路，而不是三个互不相干的演示面板。
 */
function sendToReview() {
  if (!composed.value) return
  // 第三步有 200 字符的下限，光把人送过去会看到一个点不动的按钮而不知道为什么
  if (composed.value.trim().length < MIN_CHARS) {
    draftErr.value = t('assistant.dfTooShort', { min: MIN_CHARS })
    return
  }
  manuscript.value = composed.value
  resetReview()
  go(3)
}
/**
 * 第三步 → 第四步的管道。
 *
 * **落库已经不在前端做了**：提交那一刻后端就落了台账，判定由轮询接口在终态时写进去。
 * 原先是这里在拿到结果后另调一个写入口，那条路径有两个洞 —— 用户中途刷新就没人来落库，
 * 而且外部粘贴的稿件永远进不了库。这里只负责在跑完之后把第四步的工作清单重新拉一遍。
 */
async function refreshWorkList() {
  if (!draftId.value) return
  await loadReview()
}

/**
 * 一条落库后的判定。
 *
 * `lines` 是逗号分隔的字符串（库里就这么存），与 worker 直接吐回来的 `Verdict.lines`
 * 那个数字数组**不是同一种东西** —— 回看历史时要先切开再渲染。
 */
interface ReviewVerdictRow {
  itemId: number
  status: 'reported' | 'vague' | 'missing'
  reason: string
  evidence: string
  lines: string
}
interface ReviewRow {
  reviewId: number | null
  draftId: number | null
  reported: number
  vague: number
  missing: number
  completeness: number
  itemTotal: number
  lineCount: number
  verdicts: ReviewVerdictRow[]
  createTime: string | null
}

/**
 * 第四步：工作清单。
 *
 * 这一步原先是一屏静态演示，对前三步状态的引用次数是 0 —— 既没有输入也没有输出。
 * 现在输入是第三步对**这份草稿**的判定，输出写回第二步的条目正文，
 * 链路闭合成 2（填）→ 3（判）→ 4（改）→ 2（回写）。
 */
const review = ref<ReviewRow | null>(null)
const workErr = ref('')
/** 正在改写的条目id；同时只允许一条在跑，避免用户连点把模型池打满 */
const assistBusy = ref<number | null>(null)
/** 条目id -> 模型给的改写结果。**不自动写回**，等用户点「采用」 */
const suggestions = ref<Record<number, { text: string; action: string; model: string }>>({})
/** 条目id -> 续写关键词输入 */
const kw = ref<Record<number, string>>({})
/** 当前润色风格 */
const polishStyle = ref<'rigorous' | 'concise' | 'critical'>('rigorous')

function applyReview(row: ReviewRow | null) {
  review.value = row && row.reviewId ? row : null
}

/** 切草稿/退出登录时，第四步的一切都得跟着清掉 —— 否则会拿上一份草稿的判定去改这一份 */
function resetWork() {
  review.value = null
  suggestions.value = {}
  kw.value = {}
  workErr.value = ''
  assistBusy.value = null
}

/** 进第四步时按需拉一次工作清单：用户可能是上次跑完校验、这次直接回来的 */
async function loadReview() {
  if (!isLoggedIn.value || !draftId.value) return
  workErr.value = ''
  const res = await authedCall(`/report-drafts/${draftId.value}/review`, 'GET')
  if (!res.ok) {
    workErr.value = res.message
    return
  }
  applyReview(res.envelope?.data as ReviewRow)
}

/**
 * 待办条目：第三步判为「描述模糊 / 未报告」的那些，配上条目文案与当前正文。
 *
 * 已报告的不列 —— 那些不需要改，列出来只会把真正要干的活淹掉。
 */
const workRows = computed(() => {
  const verdicts = review.value?.verdicts ?? []

  return verdicts
    .filter((v) => v.status === 'vague' || v.status === 'missing')
    .map((v) => {
      // computed ref，脚本里要 .value（模板里才自动解包）
      const it = itemById.value.get(v.itemId)

      return {
        ...v,
        no: pick(it, 'itemNo') || String(v.itemId),
        text: pick(it, 'content') || pick(it, 'extension') || '',
        current: (body.value[v.itemId] ?? '').trim(),
      }
    })
})

/** 跑一次改写。结果只进 suggestions，等用户看过再决定采不采用 */
async function runAssist(itemId: number, action: 'continue' | 'polish' | 'translate') {
  if (assistBusy.value !== null || !draftId.value) return
  assistBusy.value = itemId
  workErr.value = ''
  const res = await authedCall(`/report-assist?lang=${isEn.value ? 'en' : 'zh'}`, 'POST', {
    draftId: draftId.value,
    itemId,
    action,
    style: action === 'polish' ? polishStyle.value : '',
    keywords: action === 'continue' ? (kw.value[itemId] ?? '') : '',
  })
  assistBusy.value = null
  if (!res.ok) {
    workErr.value = res.message
    return
  }
  const data = res.envelope?.data as { text: string; action: string; modelLabel: string }
  suggestions.value = { ...suggestions.value, [itemId]: { text: data.text, action: data.action, model: data.modelLabel } }
}

/**
 * 采用某条建议 —— 写回第二步的草稿条目，这一步让整个环闭合。
 *
 * 写回成功后同步更新第二步的编辑态 `body`，否则用户切回第二步看到的还是旧正文，
 * 再一保存就把刚采用的改写覆盖掉了。
 */
async function applySuggestion(itemId: number) {
  const sug = suggestions.value[itemId]
  if (!sug || !draftId.value) return
  assistBusy.value = itemId
  workErr.value = ''
  const res = await authedCall('/report-assist/apply', 'PUT', {
    draftId: draftId.value,
    itemId,
    content: sug.text,
  })
  assistBusy.value = null
  if (!res.ok) {
    workErr.value = res.message
    return
  }
  body.value = { ...body.value, [itemId]: sug.text }
  // **这里原先置 `dirty = false`，那会丢用户的字。** 写回是后端「整份读回来、只换这一条、
  // 再写回去」，读的是**库里**那份 —— 客户端待保存的其他条目改动根本不在其中。而 dirty
  // 一旦置假，`saveDraft` 开头那句 `if (!dirty) return` 就把 `touchDraft` 排好的那次
  // 自动保存整个吞掉：用户在第二步敲了几句、4 秒内切到第四步点了「采用」，那几句就没了
  const rest = { ...suggestions.value }
  delete rest[itemId]
  suggestions.value = rest
}

/**
 * 第四步的独立模式 —— 不需要草稿，也不需要跑过第三步。
 *
 * ## 为什么它是主体，工作清单反而是快捷方式
 *
 * 《智能报告辅助工具.docx》第 4 节四项功能（续写 / 背景生成 / 润色 / 翻译）的输入
 * **全是用户直接给的**：关键词、研究方向、要润色的那段话、要翻译的摘要。没有一项依赖
 * 第二步的草稿或第三步的判定。这里一度只有「按草稿条目改写」一条路，理由是文档那句
 * 「遵循 STRICTA 条目规范」得先站在某一条上 —— 那个推理是错的：这句话要的是「按哪份
 * 规范写」，第一步就给了。
 *
 * 代价是实打实的：已经写好稿、直接来第三步的用户（文档意义上最主要的一类），
 * 跑完校验拿到几十条待办，第四步却一个字都出不来 —— 因为他没有第二步的草稿。
 *
 * 所以现在：这块面板任何时候都能用；有草稿有判定时，下面那张工作清单作为快捷入口出现。
 */
const SOLO_ACTIONS = ['continue', 'polish', 'translate'] as const
type SoloAction = (typeof SOLO_ACTIONS)[number]

/** 与后端 `MAX_ASSIST_INPUT_CHARS` 对齐；超了后端也会拒，前端先拦一道省一次往返 */
const SOLO_MAX = 5000

const soloAction = ref<SoloAction>('continue')
const soloKeywords = ref('')
const soloText = ref('')
const soloBusy = ref(false)
const soloErr = ref('')
const soloResult = ref<{ text: string; action: string; model: string } | null>(null)
const soloCopied = ref(false)

/** 润色与翻译是改写已有内容，没有输入就没有输出；续写只要关键词 */
const soloNeedsText = computed(() => soloAction.value !== 'continue')
const soloCanRun = computed(() => {
  if (soloBusy.value || soloText.value.length > SOLO_MAX) return false

  return soloNeedsText.value ? Boolean(soloText.value.trim()) : Boolean(soloKeywords.value.trim())
})

async function runSolo() {
  if (!soloCanRun.value) return
  soloBusy.value = true
  soloErr.value = ''
  soloResult.value = null
  soloCopied.value = false
  const res = await authedCall(`/report-assist?lang=${isEn.value ? 'en' : 'zh'}`, 'POST', {
    // 不传 draftId/itemId 就是独立模式；规范代号来自第一步，只用来告诉模型「按哪份规范写」
    guidelineCode: checklistCode.value,
    action: soloAction.value,
    style: soloAction.value === 'polish' ? polishStyle.value : '',
    keywords: soloAction.value === 'continue' ? soloKeywords.value : '',
    text: soloText.value,
  })
  soloBusy.value = false
  if (!res.ok) {
    soloErr.value = res.message

    return
  }
  const data = res.envelope?.data as { text: string; action: string; modelLabel: string }
  soloResult.value = { text: data.text, action: data.action, model: data.modelLabel }
}

/**
 * 独立模式的生成结果写回草稿。
 *
 * 「复制」永远可用（没有草稿时那是唯一出路），但**有草稿时不该逼用户手工粘回去** ——
 * 这一步与工作清单那条路写的是同一个地方（`action_report_draft_item`），只是
 * 「写进哪一条」由用户当场指定，而不是由第三步的判定指定。
 *
 * 后端复用 `PUT /report-assist/apply`，一个字都不用改：它本来就验草稿归属、验条目属于
 * 该规范，并在服务端自己记 `applied` 留痕（投稿时被问起「AI 参与了多少」，那张表是答案）。
 *
 * **写进的永远是当前打开的那份草稿**（选草稿走 `openDraft`，与第二步同一个入口）：
 * 这样 `body` 里就是该条目的现有正文，既能在覆盖前把它摆给用户看，
 * 写回之后同步 `body` 也一定同步对了草稿。若允许写进「没打开的那一份」，
 * 这两件事都得另发请求，而且极易把第二步的编辑态更新到另一份草稿上去。
 */
const saveItemId = ref<number | null>(null)
const saveBusy = ref(false)
const saveDone = ref(false)

/** 选中条目在当前草稿里已有的正文 —— 覆盖前要让用户看见，别盲覆盖 */
const saveTargetText = computed(() => (saveItemId.value ? (body.value[saveItemId.value] ?? '').trim() : ''))
const canSaveSolo = computed(
  () => Boolean(soloResult.value && draftId.value && saveItemId.value) && !saveBusy.value,
)

async function saveSoloTo(mode: 'replace' | 'append') {
  const text = soloResult.value?.text
  const itemId = saveItemId.value
  if (!text || !itemId || !draftId.value || saveBusy.value) return
  const existing = saveTargetText.value
  const content = mode === 'append' && existing ? `${existing}\n${text}` : text

  saveBusy.value = true
  soloErr.value = ''
  const res = await authedCall('/report-assist/apply', 'PUT', {
    draftId: draftId.value,
    itemId,
    content,
  })
  saveBusy.value = false
  if (!res.ok) {
    soloErr.value = res.message

    return
  }
  // 同步第二步的编辑态，否则切回去看到的还是旧正文，再一保存就把刚写回的覆盖掉
  body.value = { ...body.value, [itemId]: content }
  // **不动 `dirty`**：写回是后端「整份读回来、只换这一条、再写回去」，读的是**库里**那份，
  // 客户端尚未保存的其他条目改动并不在其中。把 dirty 置 false 会让 saveDraft 的
  // `if (!dirty) return` 把待发的自动保存直接吞掉 —— 用户刚敲的字就这么没了
  saveDone.value = true
  setTimeout(() => { saveDone.value = false }, 2500)
}

/**
 * 复制。没有草稿时这是唯一出路，有草稿时也留着 —— 用户可能要粘到别处去。
 */
async function copySolo() {
  const text = soloResult.value?.text
  if (!text || !import.meta.client) return
  try {
    await navigator.clipboard.writeText(text)
    soloCopied.value = true
    setTimeout(() => { soloCopied.value = false }, 2000)
  } catch {
    // 剪贴板 API 在非 https / 无权限时会拒绝。不弹错：文字就在上面，用户手动选中即可
    soloErr.value = t('assistant.wkCopyFailed')
  }
}

const reviewState = ref<'idle' | 'running' | 'done' | 'error'>('idle')
const reviewSid = ref('')
/**
 * 本次校验在库里的记录 id。
 *
 * 提交那一刻后端就落了台账并把它一并回来。**它是「刷新之后还找得回来」的锚点**：
 * 此前提交只回一个 session_id，而它只活在这个组件的内存里 —— 刷一下页面，
 * Redis 里明明还躺着结果，前端却再也没有任何线索去取它。
 */
const reviewId = ref<number | null>(null)
/**
 * 这次校验是不是本客户端提交的 —— 决定跑完时要不要记一条留痕。
 *
 * 留痕是**只追加**的审计记录。刷新后 `resumeReview` 会接回还在跑的任务并继续轮询，
 * 若不分辨，同一次校验在「提交的那个页面」和「刷新后的这个页面」各记一条 judged，
 * 看起来就成了判定跑过两遍。落库那边不会重复（`_sync_run` 见到 completed 直接跳过），
 * 唯独留痕这条得前端自己认。
 */
const reviewSubmittedHere = ref(false)
const reviewMsg = ref('')
const reviewError = ref('')
const reviewPct = ref(0)
const reviewResult = ref<ReviewResult | null>(null)
let pollTimer: ReturnType<typeof setTimeout> | null = null

const MIN_CHARS = 200

/**
 * 匹配到的规范一条 checklist 条目都没有（眼下只有 STROBE 这一份——仓库里没有它的中英素材）。
 *
 * 这种情况后端提交接口本来就会回绝，但那是「点了才知道」；条目数是第二步就摆在眼前的，
 * 没理由让人写完整篇稿件再吃一个报错。载入期间不算 —— 那会儿 length 也是 0。
 */
const noItems = computed(() => Boolean(checklistCode.value) && !ckLoading.value && checklist.value.length === 0)

const canRun = computed(
  () =>
    manuscript.value.trim().length >= MIN_CHARS &&
    Boolean(checklistCode.value) &&
    !noItems.value &&
    reviewState.value !== 'running',
)

/** 判定结果按条目 id 索引，渲染时和第二步已经取到的条目正文拼在一起 */
const itemById = computed(() => new Map(checklist.value.map((it) => [it.itemId, it])))

/**
 * 全稿校验的状态 → `.chk` 的配色档位。
 *
 * `na`（不适用）与 `unchecked`（没跑完）一律中性灰：它们都不是判定结论，不该占用
 * 三档里任何一档的颜色 —— 尤其 unchecked，长得像「未见问题」就等于把没跑过的检查
 * 当成了合格，这正是这一层最容易骗人的地方。
 */
const CROSS_CLASS: Record<CrossStatus, string> = {
  ok: 'ok',
  warn: 'warn',
  issue: 'miss',
  na: 'na',
  unchecked: 'na',
}
const crossChecks = computed<CrossCheck[]>(() => reviewResult.value?.consistency?.checks ?? [])
const crossTruncated = computed(() => Boolean(reviewResult.value?.consistency?.truncated))

/**
 * 结果区里的稿件原文。
 *
 * **判定的两样证据都指向原文**：「报告于第 12 行」这个行号，和那段 evidence 引文。
 * 结果一出来输入框整块就被藏起来（`v-if="reviewState !== 'done'"`），于是这两样
 * 都没法核 —— 从历史点开一条旧记录时尤其荒唐：稿件明明取回来了，却只能看见判定。
 *
 * 所以原文在结果区单独有一块，默认折叠（多数时候用户只看判定），**带行号** ——
 * 不带行号的话这块就只是一堵墙，行号引用照样落空。
 */
const showSource = ref(false)
/** 当前高亮的行号集合，由点击某条判定的行号引用触发 */
const srcHit = ref<Set<number>>(new Set())

/**
 * 编好行号的稿件。
 *
 * **编号规则必须与 worker 的 `engine/audit.py::number_lines` 一致，细节见
 * `composables/manuscriptLines.ts`** —— 那边空行不占行号，照着物理行号编的话，
 * 稿件里出现第一个空行之后，所有「报告于第 N 行」就指向不相干的内容，
 * 而且不会报任何错。实测一份 2193 字的稿件：物理 77 行、有效 39 行。
 */
const srcLines = computed(() => numberManuscriptLines(manuscript.value))
/** 有效行数，与引擎返回的 lineCount 同义 */
const srcCount = computed(() => countNumberedLines(srcLines.value))

/**
 * 从一条判定跳到它引用的原文行。
 *
 * 展开面板 → 高亮这条判定引用的所有行 → 滚到第一行。折叠状态下要等 DOM 出来才滚得动，
 * 所以走 `nextTick`。
 */
async function jumpToLine(lines: number[]) {
  if (!lines.length || !srcLines.value.length) return
  showSource.value = true
  srcHit.value = new Set(lines)
  await nextTick()
  if (!import.meta.client) return
  document.getElementById(`srcline-${lines[0]}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
}

/** 规则名走 i18n；引擎新加了规则而前端还没配词条时，退回显示 key，不显示成空白 */
const ruleTitle = (key: string) => (te(`assistant.ckRule.${key}`) ? t(`assistant.ckRule.${key}`) : key)

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
    // 落库由后端在这次轮询里做完了（见 refreshWorkList 的注释）。这里只把第四步的
    // 工作清单重新拉一遍，顺带刷新历史列表让这次校验立刻出现在里面
    void refreshWorkList()
    void loadReviewHistory()

    // 留痕只由提交它的那个页面记（见 reviewSubmittedHere）
    if (!reviewSubmittedHere.value) return
    reviewSubmittedHere.value = false

    const who = (done.models ?? []).join(' / ') || t('assistant.auditSystem')
    pushTrail({
      event: 'judged',
      actor: who,
      total: done.summary.total,
      reported: done.summary.reported,
      vague: done.summary.vague,
      missing: done.summary.missing,
      completeness: done.summary.completeness,
    })
    // 全稿校验是另一次判定，留痕也另记一条：它可能整体没跑成，而逐条判定照常完成
    const cross = done.consistency
    if (cross?.checks?.length) {
      // 全稿一致性复用同三个计数列：issue→missing、warn→vague、ok→reported，
      // 免得为一个事件另开三列。渲染时按 event 分支取回去
      pushTrail({
        event: 'cross',
        actor: who,
        missing: cross.summary?.issue ?? 0,
        vague: cross.summary?.warn ?? 0,
        reported: cross.summary?.ok ?? 0,
      })
    }
    return
  }
  if (status === 'failed' || status === 'stopped') {
    reviewState.value = 'error'
    reviewError.value = String(state.error || '') || t(status === 'stopped' ? 'assistant.rvStopped' : 'assistant.rvFailed', { msg: '' })
    pushTrail({ event: 'failed', actor: t('assistant.auditSystem'), note: reviewError.value })
    // 失败的那条也要在历史里现出来 —— 「昨天那次为什么挂了」正是要查的那批
    void loadReviewHistory()
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
    // 稿件就是第二步那份初稿时才认领草稿，第四步的工作清单据此接上。
    // 外部粘贴的稿件不带 draftId，但**照样进历史** —— 它只是没有草稿可挂
    draftId: reviewFromDraft.value ? draftId.value : null,
  })
  if (!res.ok) {
    reviewState.value = 'error'
    reviewError.value = res.message
    return
  }
  const ticket = (res.envelope?.data ?? {}) as { sessionId?: string; reviewId?: number }
  reviewSid.value = String(ticket.sessionId ?? '')
  reviewId.value = Number(ticket.reviewId ?? 0) || null
  reviewSubmittedHere.value = true
  if (!reviewSid.value) {
    reviewState.value = 'error'
    reviewError.value = t('assistant.rvFailed', { msg: '' })
    return
  }
  // 任务一进队就让它出现在历史里：用户此刻刷新页面，凭这条记录才找得回来
  void loadReviewHistory()
  pushTrail({
    event: 'submitted',
    actor: guest.value?.username || t('assistant.auditYou'),
    guidelineCode: checklistCode.value,
    charCount: manuscript.value.trim().length,
  })
  pollTimer = setTimeout(poll, 1500)
}

async function stopReview() {
  if (!reviewSid.value) return
  stopPolling()
  await authedCall(`/checklist-review/${reviewSid.value}/stop`, 'POST')
  reviewState.value = 'idle'
  void loadReviewHistory()
}

function resetReview() {
  stopPolling()
  reviewState.value = 'idle'
  reviewResult.value = null
  reviewError.value = ''
  reviewId.value = null
  reviewSid.value = ''
  showSource.value = false
  srcHit.value = new Set()
}

onBeforeUnmount(stopPolling)

// ---------------------------------------------------------------- 第三步：校验历史
//
// 这一段回答的是「关掉页面之后，刚才那次校验还在不在」。在 014 之前答案是不在：
// 判定只在前端轮到 completed 那一刻才落库，而 session_id 只活在内存里，
// 刷新一下就等于把一次几十次模型调用的结果扔了。现在提交即落台账，这里把它列出来。

interface ReviewHistoryRow {
  reviewId: number
  sessionId: string
  draftId: number | null
  guidelineCode: string
  runStatus: 'pending' | 'running' | 'completed' | 'failed' | 'stopped'
  errorMsg: string
  progress: number
  charCount: number
  itemTotal: number
  completeness: number
  reported: number
  vague: number
  missing: number
  createTime: string | null
  finishTime: string | null
}

const reviewHistory = ref<ReviewHistoryRow[]>([])
const historyLoading = ref(false)
/** 正在回看的那条历史；用来给列表行加选中态，也用来判断删掉的是不是当前这条 */
const viewingReviewId = ref<number | null>(null)

/**
 * 拉一次历史。
 *
 * 后端在这个口里顺带对账（未终结的记录补查一次 worker 状态并补落库），
 * 所以「关掉页面、任务在后台跑完」这种情况，下次打开页面就是靠这一下补上的。
 */
async function loadReviewHistory() {
  if (!isLoggedIn.value) {
    reviewHistory.value = []

    return
  }
  historyLoading.value = true
  const res = await authedCall('/checklist-reviews', 'GET')
  historyLoading.value = false
  reviewHistory.value = res.ok ? ((res.envelope?.data ?? []) as ReviewHistoryRow[]) : []
}

/**
 * 把一条历史还原成第三步那整屏结果。
 *
 * 库里的 `lines` 是逗号分隔字符串，而渲染层认的是 worker 那种数字数组，这里补上转换
 * —— 不转的话行号会渲染成一整串 "3,7,12" 挤在一个「报告于第几行」里。
 */
async function viewReviewHistory(row: ReviewHistoryRow) {
  if (row.runStatus !== 'completed') return
  stopPolling()
  reviewError.value = ''
  const res = await authedCall(`/checklist-reviews/${row.reviewId}`, 'GET')
  if (!res.ok) {
    reviewState.value = 'error'
    reviewError.value = res.message

    return
  }
  const d = (res.envelope?.data ?? {}) as {
    manuscript?: string
    reported?: number
    vague?: number
    missing?: number
    itemTotal?: number
    completeness?: number
    lineCount?: number
    truncated?: boolean
    models?: string
    consistency?: CrossResult | null
    verdicts?: ReviewVerdictRow[]
  }
  manuscript.value = d.manuscript ?? ''
  reviewResult.value = {
    summary: {
      total: d.itemTotal ?? 0,
      reported: d.reported ?? 0,
      vague: d.vague ?? 0,
      missing: d.missing ?? 0,
      completeness: d.completeness ?? 0,
    },
    verdicts: (d.verdicts ?? []).map((v) => ({
      itemId: v.itemId,
      status: v.status,
      reason: v.reason ?? '',
      evidence: v.evidence ?? '',
      lines: (v.lines ?? '')
        .split(',')
        .map((n) => Number(n))
        .filter((n) => Number.isFinite(n) && n > 0),
    })),
    consistency: d.consistency ?? undefined,
    lineCount: d.lineCount ?? 0,
    truncated: Boolean(d.truncated),
    models: d.models ? d.models.split(' / ') : [],
  }
  reviewId.value = row.reviewId
  reviewSid.value = row.sessionId
  viewingReviewId.value = row.reviewId
  // 换了一份稿件，上一条记录留下的高亮与展开状态都得清掉
  showSource.value = false
  srcHit.value = new Set()
  reviewState.value = 'done'
}

async function removeReviewHistory(row: ReviewHistoryRow) {
  // 删除会连稿件正文一起真删，不是「列表里看不见了」—— 值得问一句
  if (import.meta.client && !window.confirm(t('assistant.rvHistConfirmDelete'))) return
  const res = await authedCall(`/checklist-reviews/${row.reviewId}`, 'DELETE')
  if (!res.ok) return
  reviewHistory.value = reviewHistory.value.filter((r) => r.reviewId !== row.reviewId)
  if (viewingReviewId.value === row.reviewId) {
    viewingReviewId.value = null
    resetReview()
  }
}

/**
 * 挂载后拉历史，并**接回还在跑的那次校验**。
 *
 * 这才是「刷新之后不丢」的完整闭环：任务在 worker 那边照跑不误，页面回来以后
 * 认领回 session_id 继续轮询，进度条从中途接上，而不是留一个空白的第三步。
 * 登录态是水合后才知道的（全站预渲染），所以只能在客户端挂载后做。
 */
async function resumeReview() {
  await loadReviewHistory()
  if (reviewState.value !== 'idle') return
  const live = reviewHistory.value.find((r) => r.runStatus === 'pending' || r.runStatus === 'running')
  if (!live?.sessionId) return
  reviewSid.value = live.sessionId
  reviewId.value = live.reviewId
  // 不是这个页面提交的，跑完不补记留痕（提交它的那个页面已经记过 submitted）
  reviewSubmittedHere.value = false
  reviewState.value = 'running'
  reviewPct.value = live.progress ?? 0
  stopPolling()
  pollTimer = setTimeout(poll, 500)
}

onMounted(() => {
  void resumeReview()
})
watch(isLoggedIn, () => {
  void loadReviewHistory()
})

const reviewStamp = (iso: string | null) => {
  if (!iso) return ''
  const d = new Date(iso.replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return iso
  const locale = isEn.value ? 'en-GB' : 'zh-CN'

  return `${d.toLocaleDateString(locale)} ${d.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', hour12: false })}`
}

const RV_HIST_STATUS_KEY: Record<string, string> = {
  pending: 'assistant.rvHistQueued',
  running: 'assistant.rvHistRunning',
  failed: 'assistant.rvHistFailed',
  stopped: 'assistant.rvHistStopped',
  completed: 'assistant.rvHistDone',
}

/**
 * 第三步：数据留痕与追溯。
 *
 * 记的是本次校验真实发生过的事（提交了什么、哪些模型判的、判成什么样），
 * 没跑过校验就不显示 —— 留痕不能是摆设。
 */
/**
 * 操作留痕（文档 3.4）。原先只是前端内存里的 8 条，刷新即失、实际不可追溯，现在落库。
 *
 * **存的是结构化事件，不是渲染好的句子。** 句子里迟早会混进稿件正文片段
 * （「已提交稿件：本研究纳入 120 例……」），第三步「稿件只在校验期间流转，不会入库」
 * 那条承诺就绕过去了。所以库里只有事件键与几个数字，人读的那句话由这里按 i18n 拼。
 */
interface TrailRow {
  trailId?: number | null
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
  if (r.event === 'applied') return t('assistant.auditApplied', { no: r.itemId ?? '', chars: r.charCount ?? 0 })

  return r.note || t('assistant.auditFailed')
}

const auditTrail = computed(() =>
  trail.value.map((r) => ({
    id: r.trailId ?? -(r.localId ?? 0),
    at: stamp(r.createTime),
    who: r.actor || t('assistant.auditSystem'),
    what: trailText(r),
  })),
)

/**
 * 记一条留痕：先本地插入让用户立刻看到，再异步落库。
 *
 * 落库失败不打断任何事 —— 留痕是旁路。第四步写回草稿那条留痕由**服务端**自己记
 * （`ReportReviewService.apply_services`），不走这里：前端不调，那条最重要的记录就没了。
 */
function pushTrail(row: Omit<TrailRow, 'localId'>) {
  trail.value = [{ ...row, localId: ++trailSeq }, ...trail.value].slice(0, 20)
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

/** 拉回历史留痕。进第三步时调一次，让「刷新即失」变成「查得到」 */
async function loadTrail() {
  if (!isLoggedIn.value) return
  const res = await authedCall('/report-trails', 'GET')
  if (!res.ok) return
  trail.value = ((res.envelope?.data ?? []) as TrailRow[]).slice(0, 20)
}

/**
 * 第四步：润色风格。值与后端 `report_assist_prompt._STYLE_RULES` 的键一一对应，
 * 改档位时两边一起改 —— 后端拿不认识的键会兜到 rigorous，表现是「选了没反应」
 */
const POLISH_STYLES = ['rigorous', 'concise', 'critical'] as const

/**
 * 第五步：导出格式。
 *
 * 三种各答一个问题：docx 稿件本身 · xlsx 投稿随附的 checklist 对照表 · json 结构化留档。
 * **没有 PDF** —— 服务端生成中文 PDF 要在服务器装中文字体，字体缺失时的表现是整篇方块字
 * 而不是报错，这种失败方式在导出场景代价太高；docx 自己另存更可靠。
 */
const EXPORT_FMTS = ['docx', 'xlsx', 'json'] as const
const exporting = ref('')
const exportErr = ref('')

/**
 * 下载一份导出文件。
 *
 * 走 `authedBlob` 而不是普通 `authedCall`：本站错误是「HTTP 200 + code≠200」的 JSON 信封，
 * 与文件走同一条通道，靠 Content-Type 区分（后端因此必须显式给 media type）。
 */
async function downloadExport(fmt: string) {
  if (!draftId.value || exporting.value) return
  exporting.value = fmt
  exportErr.value = ''
  const res = await authedBlob(
    `/report-drafts/${draftId.value}/export?fmt=${fmt}&lang=${isEn.value ? 'en' : 'zh'}`,
  )
  exporting.value = ''
  if (!res.ok || !res.blob) {
    exportErr.value = res.message
    return
  }
  const url = URL.createObjectURL(res.blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${(draftTitle.value || 'report').slice(0, 60)}.${fmt}`
  a.click()
  // 不撤销的话每导一次泄漏一个 blob，一个长会话里能攒出几十兆
  URL.revokeObjectURL(url)
}
/**
 * 第五步的「加密分享链接」与「版本快照对比」两段还是写死的演示，先关掉。
 *
 * **不是排期问题，是两个未定的设计。**
 * 分享链接一旦真发，就是一个**匿名可读的未发表稿件外链** —— 要先定清楚有效期、能不能撤销、
 * 「可评论」的评论存哪、被转发出去怎么办。这不是加个随机串了事，是个独立的权限模型。
 * 版本对比要先有快照模型：什么时候存一版（每次保存？手动打点？）、对比的粒度是条目还是全文。
 *
 * 关掉而不是留着：留着一个会复制出真链接的按钮，用户会以为它真的分享了什么。
 * 模板与样式都还在，两段定稿后把这里改成 true 即恢复 —— 与 `guidelines.vue`
 * 的 `SHOW_WIP_TABS` 是同一个处理。
 */
const SHOW_WIP_SHARE = false

/** 第五步：分享权限 */
const perm = ref<'view' | 'comment'>('view')

/** 第五步：分享链接与复制反馈 */
const SHARE_URL = 'https://action-acu.cn/r/9f3a…c7'
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

// 五步向导的状态（step / go / wizardEl）在上面的「URL 同步」一段，
// 那里说明了为什么必须放在草稿逻辑之前。

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
          <button class="step" :class="{ on: step === 2, done: step > 2 }" data-step="2" role="tab" :aria-selected="step === 2" @click="go(2)"><span class="sn">2</span><span class="stx"><b>{{ t('assistant.s004') }}</b><span>{{ t('assistant.s005') }}</span></span><span v-if="stage === 'manuscript'" class="sbadge">{{ t('assistant.stepSkippable') }}</span></button>
          <button class="step" :class="{ on: step === 3, done: step > 3 }" data-step="3" role="tab" :aria-selected="step === 3" @click="go(3)"><span class="sn">3</span><span class="stx"><b>{{ t('assistant.s006') }}</b><span>{{ t('assistant.s007') }}</span></span><span v-if="stage === 'draft'" class="sbadge">{{ t('assistant.stepLater') }}</span></button>
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
                  <button
                    v-for="k in TYPE_OPTS"
                    :key="k"
                    class="opt"
                    :class="{ on: ans.type === k }"
                    :data-v="k"
                    @click="ans.type = k"
                  >{{ t(`assistant.typeOpt.${k}`) }}</button>
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

              <!-- 路线岔口。「从零开始写」与「已经有稿件」是两条不同的路,
                   压进一条线性向导里,两类人各自都会撞上一屏与自己无关的东西 -->
              <div class="stage">
                <div class="subh">{{ t('assistant.stageTitle') }}</div>
                <p class="stage-q">{{ t('assistant.stageQ') }}</p>
                <div class="stage-opts">
                  <button
                    v-for="o in STAGE_OPTS"
                    :key="o"
                    type="button"
                    class="stage-opt"
                    :class="{ on: stage === o }"
                    :aria-pressed="stage === o"
                    @click="stage = stage === o ? '' : o"
                  >
                    <b>{{ t(`assistant.stageOpt.${o}`) }}</b>
                    <span>{{ t(`assistant.stageDesc.${o}`) }}</span>
                  </button>
                </div>
                <button v-if="stage" class="btn btn-primary btn-sm stage-go" @click="go(stage === 'manuscript' ? 3 : 2)">
                  {{ t(stage === 'manuscript' ? 'assistant.stageGoReview' : 'assistant.stageGoDraft') }}
                  <span class="arrow" aria-hidden="true">→</span>
                </button>
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
          <!-- 只提示不拦截：这一步照样点得进来、填得动，已有稿件的人未必不想看看清单长什么样 -->
          <p v-if="stage === 'manuscript'" class="route-note">
            <span>{{ t('assistant.skipHint') }}</span>
            <button class="btn btn-ghost btn-sm" @click="go(3)">{{ t('assistant.skipToReview') }}</button>
          </p>

          <!--
            工作台条。

            原先「规范来源 / 条目数 / 草稿工具条 / 完成度 / 草稿名称」是五个纵向堆叠的块，各带各的
            margin（10/12/12/14/16px —— 六个几乎相等又都不相等的值），既排不出分组也排不出节奏，
            还把真正要干活的清单挤到了首屏之外。它们回答的其实是同一个问题——「我在编辑哪份草稿、
            依据哪份规范、填到哪儿了」——压成一条横条之后，这个面板里就只剩一个主体：清单本身。
          -->
          <div v-if="checklistRows.length" class="wb">
            <!-- chips 不再配一行「依据所匹配的规范生成」的可见标签：紧跟其后的条目数
                 已经把这组东西说清楚了。那句话降级成 aria-label，读屏用户不丢上下文 -->
            <div class="wb-src" :aria-label="t('assistant.tplFrom')">
              <div v-if="matched" class="gchips">
                <b v-for="g in matched.guidelines" :key="g" :class="{ hot: g === matched.hotGuideline }">{{ g }}</b>
              </div>
              <span class="wb-count">
                {{ t('assistant.tplCount', { n: checklistRows.length, m: checklistPartCount }) }}
              </span>
            </div>
            <template v-if="isLoggedIn">
              <span class="wb-sep" aria-hidden="true"></span>
              <select
                v-if="myDrafts.length"
                class="df-sel"
                :value="draftId ?? ''"
                :aria-label="t('assistant.dfSwitch')"
                @change="openDraft(Number(($event.target as HTMLSelectElement).value))"
              >
                <option v-for="d in myDrafts" :key="d.draftId" :value="d.draftId">{{ d.title }}</option>
              </select>
              <!-- 草稿名称原先是「独占一行的 label + 输入框」，它其实就是个文档标题，
                   与草稿下拉挨着才说得通；label 降级成 placeholder + aria-label -->
              <input
                v-if="canEdit"
                id="dfTitle"
                v-model="draftTitle"
                class="wb-name"
                :placeholder="t('assistant.dfTitlePh')"
                :aria-label="t('assistant.dfTitleLabel')"
                maxlength="300"
                @input="touchDraft"
              />
              <!-- 完成度原先是个带边框的大盒子 + 1.3rem 衬线数字，是整个左栏最大的字 ——
                   页面上最抢眼的东西成了一个进度数字，而不是用户要填的清单。
                   它是状态指示，降级成一条细线 + 小号分数 -->
              <div v-if="canEdit" class="wb-prog">
                <span class="meter" aria-hidden="true"><i :style="{ width: donePct + '%' }"></i></span>
                <b :aria-label="t('assistant.dfProgress')">{{ requiredFilled }}<em>/{{ requiredIds.size }}</em></b>
              </div>
              <div class="wb-act">
                <span class="df-state" :class="{ dirty }">
                  {{ dirty ? t('assistant.dfUnsaved') : savedAt ? t('assistant.dfSavedAt', { at: savedAt }) : '' }}
                </span>
                <button class="btn btn-ghost btn-sm" :disabled="draftBusy" @click="newDraft">
                  {{ t('assistant.dfNew') }}
                </button>
                <!-- 导入已有稿件：第二步的第二条路。已经写好稿的人用不上逐条填，
                     但也不该被挡在草稿之外 —— 没有草稿，第四五步都走不了 -->
                <label class="btn btn-ghost btn-sm df-import" :class="{ busy: importBusy }">
                  <input type="file" :accept="IMPORT_ACCEPT" :disabled="importBusy || draftBusy" @change="pickImport" />
                  <span>{{ importBusy ? t('assistant.dfImporting') : t('assistant.dfImport') }}</span>
                </label>
                <button class="btn btn-primary btn-sm" :disabled="saving || !dirty" @click="saveDraft">
                  {{ saving ? t('assistant.dfSaving') : t('assistant.dfSave') }}
                </button>
                <button v-if="draftId" class="df-del" type="button" :disabled="draftBusy" @click="removeDraft">
                  {{ t('assistant.dfDelete') }}
                </button>
              </div>
            </template>
            <NuxtLink v-else class="btn btn-primary btn-sm wb-act" :to="loginLink">{{ t('assistant.dfLogin') }}</NuxtLink>
          </div>
          <p v-if="checklistRows.length && !isLoggedIn" class="wb-hint">{{ t('assistant.dfNeedLogin') }}</p>
          <p v-if="draftErr" class="rv-err wb-hint">{{ draftErr }}</p>

          <!-- 导入进度与结果。解析是秒级的，条目映射是几分钟级的 worker 任务 -->
          <div v-if="importBusy" class="meter-box df-imp-bar">
            <span class="subh" style="margin:0;white-space:nowrap">{{ importMsg }}</span>
            <span class="meter" aria-hidden="true"><i :style="{ width: importPct + '%' }"></i></span>
            <b>{{ importPct }}%</b>
          </div>
          <p v-if="importErr" class="rv-err wb-hint">{{ importErr }}</p>
          <p v-else-if="importDone" class="df-imp-ok">
            {{ t('assistant.dfImportDone', {
              name: importDone.name, lines: importDone.lines,
              filled: importDone.filled, blank: Math.max(0, importDone.total - importDone.filled),
            }) }}
          </p>

          <!-- 清单是主体、预览是副产物，所以不再对半分：1fr 1fr 会让首次进入这一步时
               右半屏整片空着，而左半屏挤满东西 -->
          <div class="two two-tpl">
            <div>
              <div class="tmpl tmpl-scroll">
                <template v-for="row in checklistRows" :key="row.key">
                  <div v-if="row.showPart && row.partTitle" class="tmpl-part">{{ row.partTitle }}</div>
                  <div v-if="row.showDomain && row.domain" class="tmpl-dom">{{ row.domain }}</div>
                  <div class="tmpl-row">
                    <span class="tnum">{{ row.no || row.seq }}</span>
                    <span class="tnm">
                      {{ row.text }}
                      <span v-if="row.ext" class="tmpl-ext"><b>{{ row.extLabel }}</b>{{ row.ext }}</span>
                      <textarea
                        v-if="canEdit"
                        v-model="body[row.itemId]"
                        class="df-ta"
                        :class="{ filled: (body[row.itemId] ?? '').trim() }"
                        :placeholder="t('assistant.dfItemPh')"
                        :aria-label="row.no + ' ' + row.text"
                        :maxlength="MAX_ITEM_CHARS"
                        rows="2"
                        @input="touchDraft"
                      ></textarea>
                    </span>
                    <span class="req" :class="row.required ? 'must' : 'opt'">
                      {{ t(row.required ? 'assistant.tplRequired' : 'assistant.tplOptional') }}
                    </span>
                    <span v-if="row.isExt" class="req ext">{{ t('assistant.tplExtTag') }}</span>
                  </div>
                </template>
                <p v-if="!checklistRows.length" class="tmpl-empty">
                  {{ ckLoading ? t('assistant.tplLoading') : t('assistant.tplEmpty') }}
                </p>
              </div>

              <!-- 一键生成初稿 → 直接送第三步，把「模板 → 校验」那个断点接上 -->
              <div v-if="canEdit" class="df-compose">
                <button class="btn btn-ink btn-sm" :disabled="composing" @click="composeDraft">
                  {{ composing ? t('assistant.dfComposing') : t('assistant.dfCompose') }}
                </button>
                <button v-if="composed" class="btn btn-primary btn-sm" @click="sendToReview">
                  {{ t('assistant.dfSendReview') }}
                </button>
                <span v-if="composed && composeMissing" class="df-miss">
                  {{ t('assistant.dfMissing', { n: composeMissing }) }}
                </span>
                <span v-if="overLongRow" class="df-miss">
                  {{ t('assistant.dfTooLong', { no: overLongRow.no || overLongRow.seq, max: MAX_ITEM_CHARS }) }}
                </span>
              </div>
            </div>

            <!-- 右栏：初稿预览，随页面滚动吸顶。左边逐条填、右边看它长出来 -->
            <aside class="tpl-side">
              <div class="subh">{{ t('assistant.dfPreview') }}</div>
              <div v-if="composed" class="df-preview">
                <pre>{{ composed }}</pre>
              </div>
              <p v-else class="df-preview-empty">{{ t('assistant.dfPreviewEmpty') }}</p>
            </aside>
          </div>
          <p class="tmpl-note" v-html="t('assistant.s048')"></p>
        </div>

        <!-- 面板 3：报告内容智能校验 -->
        <div class="panel" :class="{ 'is-hidden': step !== 3 }" data-panel="3">
          <div class="p-head">
            <span class="p-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M9 12l2 2 4-4" /><path d="M12 3l7 3v6c0 4.5-3 7-7 8-4-1-7-3.5-7-8V6z" /></svg></span>
            <div><span class="p-num">{{ t('assistant.s058') }}</span><h2>{{ t('assistant.s059') }}</h2></div>
          </div>
          <p class="p-desc" v-html="t('assistant.s060')"></p>
          <!-- 逐条填出来的稿子,再逐条判一遍完整性近乎循环论证。与其让用户看着满屏绿勾
               以为这一步没产出,不如直说真正值得看的是哪两栏 -->
          <p v-if="reviewFromDraft" class="route-note" v-html="t('assistant.rvFromDraft')"></p>
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
              <span v-if="checklistCode && !noItems" class="rv-target">
                {{ t('assistant.rvTarget', { code: checklistCode, n: checklist.length }) }}
              </span>
              <span v-else-if="noItems" class="rv-target warn">
                {{ t('assistant.rvNoItems', { code: checklistCode }) }}
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

            <!-- 被校验的稿件原文。默认折叠：多数时候只看判定；但判定引用的行号与 evidence
                 只有对着原文才核得动，从历史点开旧记录时尤其需要 -->
            <div v-if="srcLines.length" class="src">
              <button class="src-tog" :aria-expanded="showSource" @click="showSource = !showSource">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true" :class="{ open: showSource }"><path d="m9 6 6 6-6 6" /></svg>
                <span>{{ showSource ? t('assistant.rvSrcHide') : t('assistant.rvSrcShow') }}</span>
                <em>{{ t('assistant.rvSrcMeta', { n: srcCount, c: manuscript.length }) }}</em>
              </button>
              <!-- 行号只挂在非空行上（空行不占号，同 worker）。id 用行号而非数组下标，
                   否则跳转会差出所有空行的数量 -->
              <ol v-if="showSource" class="src-body">
                <li
                  v-for="(ln, i) in srcLines"
                  :id="ln.no === null ? undefined : `srcline-${ln.no}`"
                  :key="i"
                  :class="{ hit: ln.no !== null && srcHit.has(ln.no) }"
                >
                  <span class="src-n">{{ ln.no ?? '' }}</span>
                  <span class="src-t">{{ ln.text }}</span>
                </li>
              </ol>
            </div>

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
                  <!-- 行号引用做成可点：点一下展开原文、高亮这几行并滚过去。
                       这是「存了稿件」真正兑现价值的地方 —— 否则「第 12 行」只是个数字 -->
                  <span v-if="v.lines.length">
                    <button type="button" class="src-jump" :title="t('assistant.rvSrcJump')" @click="jumpToLine(v.lines)">
                      {{ t('assistant.rvLines', { lines: v.lines.join('、') }) }}
                    </button><i v-if="v.evidence">「{{ v.evidence }}」</i>
                  </span>
                  <span v-if="v.reason">{{ v.reason }}</span>
                </span>
                <span class="cstat">
                  {{ t(v.status === 'reported' ? 'assistant.rvStatReported' : v.status === 'vague' ? 'assistant.rvStatVague' : 'assistant.rvStatMissing') }}
                </span>
              </li>
            </ul>

            <!-- 全稿逻辑一致性与术语标准化：问题不落在某一条 checklist 条目上，故自成一段 -->
            <template v-if="crossChecks.length">
              <div class="subh" style="margin-top:24px">{{ t('assistant.ckTitle') }}</div>
              <p class="tmpl-note" style="margin:0 0 12px">{{ t('assistant.ckDesc') }}</p>
              <p v-if="crossTruncated" class="rv-err">{{ t('assistant.ckTruncated') }}</p>
              <ul class="chk ck-list">
                <li v-for="c in crossChecks" :key="c.key" :class="CROSS_CLASS[c.status]">
                  <span class="ci">
                    <svg v-if="c.status === 'ok'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><path d="M20 6 9 17l-5-5" /></svg>
                    <svg v-else-if="c.status === 'warn'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M12 8v5M12 16h.01" /></svg>
                    <svg v-else-if="c.status === 'issue'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><path d="M18 6 6 18M6 6l12 12" /></svg>
                    <svg v-else-if="c.status === 'na'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="8" /><path d="m7 17 10-10" /></svg>
                    <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M5 12h14" /></svg>
                  </span>
                  <span class="ctext">
                    <b><em>{{ t(`assistant.ckKind.${c.kind}`) }}</em>{{ ruleTitle(c.key) }}</b>
                    <span v-if="!c.findings.length">{{ t(`assistant.ckEmpty.${c.status}`) }}</span>
                    <span v-for="(f, i) in c.findings" :key="i" class="ckf" :class="f.severity">
                      <button v-if="f.lines.length" type="button" class="src-jump" :title="t('assistant.rvSrcJump')" @click="jumpToLine(f.lines)">
                        {{ t('assistant.rvLines', { lines: f.lines.join('、') }) }}
                      </button>
                      <u v-if="f.evidence">「{{ f.evidence }}」</u>
                      {{ f.detail }}
                      <b v-if="f.suggestion">{{ t('assistant.ckSuggest') }}{{ f.suggestion }}</b>
                    </span>
                    <span v-if="c.capped">{{ t('assistant.ckCapped', { n: c.findings.length }) }}</span>
                  </span>
                  <span class="cstat">{{ t(`assistant.ckStatus.${c.status}`) }}</span>
                </li>
              </ul>
            </template>
          </template>
          <!-- 校验历史：关掉页面之后还找得回来的那一份。
               任务一提交就有记录，跑挂了的也在，点开即还原整屏结果 -->
          <div v-if="isLoggedIn" class="rvh">
            <div class="rvh-head">
              <div>
                <div class="subh" style="margin:0">{{ t('assistant.rvHistTitle') }}</div>
                <p class="tmpl-note" style="margin:6px 0 0">{{ t('assistant.rvHistDesc') }}</p>
              </div>
              <button class="btn btn-ghost btn-sm" :disabled="historyLoading" @click="loadReviewHistory">
                {{ t('assistant.rvHistRefresh') }}
              </button>
            </div>
            <p v-if="!reviewHistory.length" class="rvh-empty">{{ t('assistant.rvHistEmpty') }}</p>
            <ul v-else class="rvh-list">
              <li
                v-for="row in reviewHistory"
                :key="row.reviewId"
                :class="{ on: viewingReviewId === row.reviewId }"
              >
                <span class="rvh-when">{{ reviewStamp(row.createTime) }}</span>
                <span class="rvh-meta">
                  <b>{{ row.guidelineCode }}</b>
                  <span>{{ t('assistant.rvHistChars', { n: row.charCount }) }}</span>
                </span>
                <span class="rvh-stat">
                  <template v-if="row.runStatus === 'completed'">
                    <span class="rv-tally ok">{{ row.reported }}</span>
                    <span class="rv-tally warn">{{ row.vague }}</span>
                    <span class="rv-tally miss">{{ row.missing }}</span>
                    <em>{{ row.completeness }}%</em>
                  </template>
                  <template v-else>
                    <span class="rvh-state" :class="{ bad: row.runStatus === 'failed' }">
                      {{ t(RV_HIST_STATUS_KEY[row.runStatus] ?? 'assistant.rvHistQueued') }}
                      <template v-if="row.runStatus === 'running'">{{ row.progress }}%</template>
                    </span>
                    <em v-if="row.errorMsg" class="rvh-err">{{ row.errorMsg }}</em>
                  </template>
                </span>
                <span class="rvh-acts">
                  <button
                    class="btn btn-ghost btn-sm"
                    :disabled="row.runStatus !== 'completed'"
                    @click="viewReviewHistory(row)"
                  >
                    {{ t('assistant.rvHistView') }}
                  </button>
                  <button class="rvh-del" :aria-label="t('assistant.rvHistDelete')" @click="removeReviewHistory(row)">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" /></svg>
                  </button>
                </span>
              </li>
            </ul>
          </div>

          <div v-if="auditTrail.length" class="audit">
            <div class="subh" style="margin-bottom:6px">{{ t('assistant.auditTitle') }}</div>
            <p class="tmpl-note" style="margin:0 0 12px">{{ t('assistant.auditDesc') }}</p>
            <ul class="audit-list">
              <li v-for="l in auditTrail" :key="l.id">
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

          <p v-if="workErr" class="rv-err">{{ workErr }}</p>

          <!-- 登录是唯一的硬前置（这一步要调模型，匿名放开等于把账单交给公网）。
               **没有草稿、没跑过校验都不再拦路** —— 文档第 4 节四项功能的输入全是用户
               直接给的，把它们锁在第二三步之后，等于把「已经写好稿、直接来校验」
               那类用户整个挡在这一步之外 -->
          <p v-if="!isLoggedIn" class="wk-empty">
            {{ t('assistant.wkNeedLogin') }}
            <NuxtLink class="btn btn-primary btn-sm" :to="loginLink">{{ t('assistant.dfLogin') }}</NuxtLink>
          </p>

          <template v-else>
            <!-- ① 独立面板：这一步的主体，任何时候都能用 -->
            <div class="solo">
              <div class="solo-tabs" role="tablist">
                <button
                  v-for="a in SOLO_ACTIONS" :key="a" class="solo-tab" role="tab"
                  :class="{ on: soloAction === a }" :aria-selected="soloAction === a"
                  @click="soloAction = a; soloResult = null; soloErr = ''"
                >
                  {{ t(`assistant.wkSoloTab.${a}`) }}
                </button>
                <span v-if="checklistCode" class="solo-gl">{{ t('assistant.wkSoloGuideline', { code: checklistCode }) }}</span>
              </div>

              <p class="tmpl-note solo-lead">{{ t(`assistant.wkSoloLead.${soloAction}`) }}</p>

              <input
                v-if="soloAction === 'continue'"
                v-model="soloKeywords" class="solo-kw" type="text"
                :placeholder="t('assistant.wkSoloKwPh')" :aria-label="t('assistant.wkSoloKwLabel')"
              />
              <textarea
                v-model="soloText" class="solo-ta"
                :placeholder="t(soloAction === 'continue' ? 'assistant.wkSoloTextOptPh' : 'assistant.wkSoloTextPh')"
                :aria-label="t('assistant.wkSoloTextLabel')"
              ></textarea>

              <div class="solo-bar">
                <span class="solo-chars" :class="{ over: soloText.length > SOLO_MAX }">
                  {{ t('assistant.wkSoloChars', { n: soloText.length, max: SOLO_MAX }) }}
                </span>
                <div v-if="soloAction === 'polish'" class="style-chips" role="group" :aria-label="t('assistant.styleAria')">
                  <button
                    v-for="o in POLISH_STYLES" :key="o" type="button"
                    :class="{ on: polishStyle === o }" :aria-pressed="polishStyle === o"
                    @click="polishStyle = o"
                  >{{ t(`assistant.wkStyleOpt.${o}`) }}</button>
                </div>
                <button class="btn btn-primary btn-sm" :disabled="!soloCanRun" @click="runSolo">
                  {{ soloBusy ? t('assistant.wkRunning') : t('assistant.wkSoloRun') }}
                </button>
              </div>

              <p v-if="soloErr" class="rv-err">{{ soloErr }}</p>

              <div v-if="soloResult" class="wk-sug">
                <div class="wk-sug-h">
                  <span>{{ t(`assistant.wkAct.${soloResult.action}`) }}</span>
                  <em>{{ soloResult.model }}</em>
                </div>
                <p class="wk-sug-t">{{ soloResult.text }}</p>
                <div class="wk-sug-a">
                  <button class="btn btn-ghost btn-sm" @click="copySolo">
                    {{ soloCopied ? t('assistant.wkCopied') : t('assistant.wkCopy') }}
                  </button>
                  <button class="btn btn-ghost btn-sm" :disabled="soloBusy" @click="runSolo">{{ t('assistant.wkRetry') }}</button>
                </div>

                <!-- 写回草稿：选一份草稿 + 选一条条目。没有草稿时整块不出现，
                     「复制」就是那种情况下的唯一出路 -->
                <div v-if="myDrafts.length" class="solo-save">
                  <div class="solo-save-row">
                    <span class="solo-save-l">{{ t('assistant.wkSaveTo') }}</span>
                    <select
                      class="df-sel" :value="draftId ?? ''" :aria-label="t('assistant.dfSwitch')"
                      @change="openDraft(Number(($event.target as HTMLSelectElement).value))"
                    >
                      <option v-for="d in myDrafts" :key="d.draftId" :value="d.draftId">{{ d.title }}</option>
                    </select>
                    <select v-model.number="saveItemId" class="df-sel solo-save-item" :aria-label="t('assistant.wkSaveItem')">
                      <option :value="null">{{ t('assistant.wkSavePickItem') }}</option>
                      <option v-for="r in checklistRows" :key="r.itemId" :value="r.itemId">
                        {{ r.no || r.seq }} · {{ r.text.slice(0, 40) }}
                      </option>
                    </select>
                  </div>

                  <!-- 覆盖前把该条目现有的正文摆出来。盲覆盖用户自己写的字是不能接受的 -->
                  <p v-if="saveTargetText" class="solo-save-cur">
                    <em>{{ t('assistant.wkSaveHasText') }}</em>{{ saveTargetText }}
                  </p>

                  <div v-if="saveItemId" class="solo-save-acts">
                    <button class="btn btn-primary btn-sm" :disabled="!canSaveSolo" @click="saveSoloTo('replace')">
                      {{ saveBusy ? t('assistant.wkRunning') : t(saveTargetText ? 'assistant.wkSaveReplace' : 'assistant.wkSaveWrite') }}
                    </button>
                    <button
                      v-if="saveTargetText" class="btn btn-ghost btn-sm"
                      :disabled="!canSaveSolo" @click="saveSoloTo('append')"
                    >
                      {{ t('assistant.wkSaveAppend') }}
                    </button>
                    <span v-if="saveDone" class="solo-save-ok">{{ t('assistant.wkSaveDone') }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- ② 工作清单：有草稿且跑过校验时才出现的快捷入口。**不是这一步的前提** -->
            <p v-if="!draftId" class="wk-hint">
              {{ t('assistant.wkNeedDraft') }}
              <button class="btn btn-ghost btn-sm" @click="go(2)">{{ t('assistant.wkGoStep2') }}</button>
            </p>
            <p v-else-if="!review" class="wk-hint">
              {{ t('assistant.wkNeedReview') }}
              <button class="btn btn-ghost btn-sm" @click="go(3)">{{ t('assistant.wkGoStep3') }}</button>
            </p>
          </template>

          <template v-if="isLoggedIn && draftId && review">
            <!-- 工作台条，与第二步同一套视觉语言：这一步改的就是那份草稿 -->
            <div class="wb">
              <div class="wb-src">
                <span class="wb-count">{{ t('assistant.wkFrom', { title: draftTitle || t('assistant.dfTitleLabel') }) }}</span>
              </div>
              <span class="wb-sep" aria-hidden="true"></span>
              <div class="wk-tally">
                <span class="rv-tally warn">{{ t('assistant.rvStatVague') }} {{ review.vague }}</span>
                <span class="rv-tally miss">{{ t('assistant.rvStatMissing') }} {{ review.missing }}</span>
                <span class="rv-tally ok">{{ t('assistant.rvStatReported') }} {{ review.reported }}</span>
              </div>
              <div class="wb-act">
                <button class="btn btn-ghost btn-sm" @click="go(3)">{{ t('assistant.wkRerun') }}</button>
              </div>
            </div>

            <!-- 全部改完了。这是个好消息，不是空状态，所以不用灰色「暂无数据」的语气 -->
            <p v-if="!workRows.length" class="wk-done">{{ t('assistant.wkAllClear') }}</p>

            <div v-else class="wk-list">
              <p class="tmpl-note wk-lead">{{ t('assistant.wkLead', { n: workRows.length }) }}</p>
              <article v-for="row in workRows" :key="row.itemId" class="wk-item">
                <header class="wk-head">
                  <span class="tnum">{{ row.no }}</span>
                  <b>{{ row.text }}</b>
                  <span class="req" :class="row.status === 'vague' ? 'opt' : 'must'">
                    {{ t(row.status === 'vague' ? 'assistant.rvStatVague' : 'assistant.rvStatMissing') }}
                  </span>
                </header>
                <p v-if="row.reason" class="wk-reason">{{ row.reason }}</p>

                <!-- 当前正文。未报告的条目这里是空的，正好说明为什么要「续写」而不是「润色」 -->
                <p v-if="row.current" class="wk-cur">{{ row.current }}</p>
                <p v-else class="wk-cur is-empty">{{ t('assistant.wkNoText') }}</p>

                <div class="wk-act">
                  <input
                    v-model="kw[row.itemId]"
                    class="wb-name wk-kw"
                    :placeholder="t('assistant.wkKwPh')"
                    :aria-label="t('assistant.wkKw')"
                    maxlength="500"
                  />
                  <button
                    class="btn btn-ink btn-sm"
                    :disabled="assistBusy !== null"
                    @click="runAssist(row.itemId, 'continue')"
                  >
                    {{ assistBusy === row.itemId ? t('assistant.wkRunning') : t('assistant.wkContinue') }}
                  </button>
                  <!-- 润色与翻译都是改写已有内容，没有正文就没有输入，按钮直接禁掉 -->
                  <button
                    class="btn btn-ghost btn-sm"
                    :disabled="assistBusy !== null || !row.current"
                    :title="row.current ? '' : t('assistant.wkNeedTextTip')"
                    @click="runAssist(row.itemId, 'polish')"
                  >
                    {{ t('assistant.wkPolish') }}
                  </button>
                  <button
                    class="btn btn-ghost btn-sm"
                    :disabled="assistBusy !== null || !row.current"
                    :title="row.current ? '' : t('assistant.wkNeedTextTip')"
                    @click="runAssist(row.itemId, 'translate')"
                  >
                    {{ t('assistant.wkTranslate') }}
                  </button>
                </div>

                <!-- 建议**不自动写回**：让模型直接改用户的稿子而不问一声是不能接受的 -->
                <div v-if="suggestions[row.itemId]" class="wk-sug">
                  <div class="wk-sug-h">
                    <span>{{ t(`assistant.wkAct.${suggestions[row.itemId]!.action}`) }}</span>
                    <em>{{ suggestions[row.itemId]!.model }}</em>
                  </div>
                  <p class="wk-sug-t">{{ suggestions[row.itemId]!.text }}</p>
                  <div class="wk-sug-a">
                    <button
                      class="btn btn-primary btn-sm"
                      :disabled="assistBusy !== null"
                      @click="applySuggestion(row.itemId)"
                    >
                      {{ t('assistant.wkApply') }}
                    </button>
                    <button class="btn btn-ghost btn-sm" @click="runAssist(row.itemId, suggestions[row.itemId]!.action as 'continue' | 'polish' | 'translate')">
                      {{ t('assistant.wkRetry') }}
                    </button>
                  </div>
                </div>
              </article>
            </div>

            <!-- 润色风格。放在列表末尾而不是每条重复一遍：它是这一屏的全局设置 -->
            <div class="style-chips" role="group" :aria-label="t('assistant.styleAria')">
              <span class="wk-style-l">{{ t('assistant.wkStyle') }}</span>
              <button
                v-for="o in POLISH_STYLES"
                :key="o"
                type="button"
                :class="{ on: polishStyle === o }"
                :aria-pressed="polishStyle === o"
                @click="polishStyle = o"
              >{{ t(`assistant.wkStyleOpt.${o}`) }}</button>
            </div>

            <p class="tmpl-note" v-html="t('assistant.wkNote')"></p>
          </template>
        </div>


        <!-- 面板 5：报告导出与分享 -->
        <div class="panel" :class="{ 'is-hidden': step !== 5 }" data-panel="5">
          <div class="p-head">
            <span class="p-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3v12m0 0 4-4m-4 4-4-4" /><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" /></svg></span>
            <div><span class="p-num">{{ t('assistant.s102') }}</span><h2>{{ t('assistant.s103') }}</h2></div>
          </div>
          <p class="p-desc">{{ t('assistant.s104') }}</p>
          <div class="subh">{{ t('assistant.s105') }}</div>
          <!-- 导出的是**库里那份草稿**，不是第二步那份合成文本 —— 后者是瞬时产物，
               用户可能压根没点过「生成初稿」 -->
          <p v-if="!isLoggedIn" class="wk-empty">
            {{ t('assistant.wkNeedLogin') }}
            <NuxtLink class="btn btn-primary btn-sm" :to="loginLink">{{ t('assistant.dfLogin') }}</NuxtLink>
          </p>
          <p v-else-if="!draftId" class="wk-empty">
            {{ t('assistant.wkNeedDraft') }}
            <button class="btn btn-ghost btn-sm" @click="go(2)">{{ t('assistant.wkGoStep2') }}</button>
          </p>
          <template v-else>
            <div class="exp-btns">
              <button
                v-for="f in EXPORT_FMTS"
                :key="f"
                class="exp"
                :disabled="Boolean(exporting)"
                @click="downloadExport(f)"
              >
                <span class="ei" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4" /><path d="M9 13h6M9 16h4" /></svg></span>
                <span>
                  <b>{{ t(`assistant.expFmt.${f}`) }}</b>
                  <span>{{ exporting === f ? t('assistant.expRunning') : t(`assistant.expDesc.${f}`) }}</span>
                </span>
              </button>
            </div>
            <p v-if="exportErr" class="rv-err">{{ exportErr }}</p>
            <p class="tmpl-note" v-html="t('assistant.expNote')"></p>
          </template>
          <div v-if="SHOW_WIP_SHARE" class="share">
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
          <template v-if="SHOW_WIP_SHARE">
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
          </template>
        </div>

        <!-- 向导底部导航 -->
        <div class="wz-nav">
          <span class="wz-prog"><span>{{ t('assistant.s120') }}</span> <b id="curStep">{{ step }}</b> / {{ WIZARD_STEP_COUNT }} <span>{{ t('assistant.s121') }}</span></span>
          <div class="wz-btns">
            <button class="btn btn-ghost" id="prevBtn" :disabled="step === 1" @click="go(step - 1)">{{ t('assistant.s122') }}</button>
            <button class="btn btn-primary" id="nextBtn" :disabled="step === WIZARD_STEP_COUNT" @click="go(step + 1)">{{ t('assistant.nextStep') }} <span class="arrow" aria-hidden="true">→</span></button>
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
.page-assistant .step .sn{width:30px;height:30px;flex-shrink:0;border-radius:var(--radius-sm);background:var(--paper-2);color:var(--muted);display:flex;align-items:center;justify-content:center;font-family:"Spectral",serif;font-weight:700;font-size:15px;transition:.2s}
.page-assistant .step.on .sn{background:var(--cinnabar);color:#fff}
.page-assistant .step.done .sn{background:var(--indigo-600);color:#fff}
.page-assistant .step .stx{min-width:0}
.page-assistant .step .stx b{display:block;font-size:13.5px;font-weight:700;color:var(--indigo-900);font-family:"Source Sans 3","Noto Sans SC",sans-serif;line-height:1.2}
.page-assistant .step .stx span{display:block;font-size:11px;color:var(--muted);margin-top:1px}
.page-assistant .step.on .stx b{color:var(--cinnabar-d)}
/* 路线角标：告诉用户这一步对他适不适用，但步骤本身照样点得进去 */
.page-assistant .step .sbadge{margin-left:auto;flex-shrink:0;font-size:10.5px;font-weight:700;color:var(--indigo-700);background:var(--indigo-100);border-radius:999px;padding:3px 9px;white-space:nowrap}
/* 4pt 基准的间距档位。第二步原先在 10/12/14/16 之间混用四个几乎相同的值，
   既分不出组也排不出节奏 —— 值必须来自一个定好的集合，而不是随手写 */
.page-assistant{--s1:4px;--s2:8px;--s3:12px;--s4:16px;--s6:24px;--s8:32px;--radius-sm:9px}
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
/* 第二步不对半分：清单是主体，预览是副产物。1fr 1fr 会让首次进入时右半屏整片空着 */
.page-assistant .two-tpl{grid-template-columns:minmax(0,1.45fr) minmax(0,1fr);align-items:start}
/* 预览跟着清单滚。清单内部自带 520px 滚动区，两栏因此不会互相拉长 */
.page-assistant .tpl-side{position:sticky;top:var(--s6)}
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
/* 路线岔口。两张卡片并排，窄屏落成上下两张 */
.page-assistant .stage{margin-top:24px}
.page-assistant .stage .subh{margin-bottom:8px}
.page-assistant .stage-q{font-size:14px;font-weight:600;color:var(--ink);margin-bottom:11px}
.page-assistant .stage-opts{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}
.page-assistant .stage-opt{font-family:inherit;text-align:left;background:var(--surface);border:1.5px solid var(--line);border-radius:12px;padding:13px 15px;cursor:pointer;transition:.18s}
.page-assistant .stage-opt:hover{border-color:var(--indigo-300);background:var(--indigo-100)}
.page-assistant .stage-opt b{display:block;font-size:13.5px;font-weight:700;color:var(--indigo-800);margin-bottom:4px}
.page-assistant .stage-opt span{display:block;font-size:12px;line-height:1.5;color:var(--muted)}
.page-assistant .stage-opt.on{border-color:var(--indigo-700);background:var(--indigo-100)}
.page-assistant .stage-opt.on b{color:var(--cinnabar-d)}
.page-assistant .stage-go{margin-top:12px}
/* ---- 第四步工作清单 ----
   一条待办 = 第三步判为模糊/未报告的一个条目。不用卡片阵：每条的内容长短差很多，
   等大卡片会把「这条只缺一句」和「这条整段没写」画成同一个重量 */
.page-assistant .wk-empty,.page-assistant .wk-done{display:flex;align-items:center;gap:var(--s3);flex-wrap:wrap;margin:0;padding:var(--s6);border:1px dashed var(--line);border-radius:var(--radius);font-size:13.5px;line-height:1.65;color:var(--muted)}
/* 全部改完是个好消息，不该用灰色「暂无数据」的语气 */
.page-assistant .wk-done{border-style:solid;border-color:var(--indigo-200);background:var(--indigo-100);color:var(--indigo-800);font-weight:600}
.page-assistant .wk-tally{display:flex;align-items:center;gap:var(--s2);flex-wrap:wrap}
.page-assistant .wk-lead{margin:0 0 var(--s4)}
.page-assistant .wk-list{display:flex;flex-direction:column;gap:var(--s4)}
.page-assistant .wk-item{border:1px solid var(--line);border-radius:var(--radius);padding:var(--s4)}
.page-assistant .wk-head{display:flex;align-items:flex-start;gap:var(--s3);margin-bottom:var(--s2)}
.page-assistant .wk-head b{flex:1;font-size:14px;font-weight:600;color:var(--ink);line-height:1.55}
.page-assistant .wk-reason{margin:0 0 var(--s2);font-size:12.5px;line-height:1.6;color:var(--amber)}
.page-assistant .wk-cur{margin:0 0 var(--s3);padding:var(--s3);background:var(--paper);border-radius:var(--radius-sm);font-size:13px;line-height:1.7;color:var(--ink);white-space:pre-wrap}
.page-assistant .wk-cur.is-empty{color:var(--muted);font-style:normal;background:none;border:1px dashed var(--line)}
.page-assistant .wk-act{display:flex;align-items:center;gap:var(--s2);flex-wrap:wrap}
.page-assistant .wk-kw{flex:1 1 220px}
/* 建议区与当前正文明确分开：一个是你写的，一个是模型给的，混在一起最要命 */
.page-assistant .wk-sug{margin-top:var(--s3);border:1px solid var(--indigo-200);border-radius:var(--radius-sm);background:var(--indigo-100)}
.page-assistant .wk-sug-h{display:flex;align-items:center;gap:var(--s2);padding:var(--s2) var(--s3);border-bottom:1px solid var(--indigo-200);font-size:11.5px;font-weight:700;color:var(--indigo-800)}
.page-assistant .wk-sug-h em{font-style:normal;font-weight:600;color:var(--muted);margin-left:auto}
.page-assistant .wk-sug-t{margin:0;padding:var(--s3);font-size:13px;line-height:1.75;color:var(--ink);white-space:pre-wrap}
.page-assistant .wk-sug-a{display:flex;gap:var(--s2);flex-wrap:wrap;padding:0 var(--s3) var(--s3)}
.page-assistant .wk-style-l{font-size:12.5px;font-weight:700;color:var(--indigo-700);margin-right:var(--s2)}
/* 工作清单降级成快捷入口之后，「还没有草稿 / 还没跑过校验」不再是拦路的空状态，
   而是这一步下半段的一句说明 —— 所以比 .wk-empty 轻，不占一整块 */
.page-assistant .wk-hint{display:flex;align-items:center;gap:var(--s3);flex-wrap:wrap;margin:var(--s6) 0 0;padding:var(--s4);
  border-top:1px solid var(--line);font-size:12.5px;line-height:1.65;color:var(--muted)}
/* ---- 第四步独立面板 ----
   这一步的主体：不需要草稿、不需要跑过校验，输入全由用户直接给（文档第 4 节的字面形态） */
.page-assistant .solo{border:1px solid var(--line);border-radius:var(--radius);padding:var(--s4);margin-bottom:var(--s6)}
.page-assistant .solo-tabs{display:flex;align-items:center;gap:var(--s2);flex-wrap:wrap;margin-bottom:var(--s3)}
.page-assistant .solo-tab{padding:6px 14px;border:1.5px solid var(--line);border-radius:999px;background:var(--surface);
  cursor:pointer;font-family:inherit;font-size:13px;font-weight:600;color:var(--muted);transition:color .18s,border-color .18s,background .18s}
.page-assistant .solo-tab:hover{color:var(--indigo-700);border-color:var(--indigo-300)}
.page-assistant .solo-tab.on{border-color:var(--indigo-700);background:var(--indigo-100);color:var(--indigo-800)}
.page-assistant .solo-gl{margin-left:auto;font-size:12px;color:var(--muted)}
.page-assistant .solo-lead{margin:0 0 var(--s3)}
.page-assistant .solo-kw{width:100%;margin-bottom:var(--s2);font-family:inherit;font-size:13.5px;color:var(--ink);
  background:var(--surface);border:1.5px solid var(--line);border-radius:var(--radius-sm);padding:8px 12px}
.page-assistant .solo-kw:focus{outline:none;border-color:var(--indigo-300)}
.page-assistant .solo-ta{width:100%;min-height:130px;resize:vertical;font-family:inherit;font-size:13.5px;line-height:1.75;
  color:var(--ink);background:var(--surface);border:1.5px solid var(--line);border-radius:var(--radius-sm);padding:10px 12px}
.page-assistant .solo-ta:focus{outline:none;border-color:var(--indigo-300)}
.page-assistant .solo-kw::placeholder,.page-assistant .solo-ta::placeholder{color:var(--muted)}
.page-assistant .solo-bar{display:flex;align-items:center;gap:var(--s3);flex-wrap:wrap;margin-top:var(--s3)}
.page-assistant .solo-chars{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums;margin-right:auto}
.page-assistant .solo-chars.over{color:var(--cinnabar-d);font-weight:700}
/* 写回草稿。挂在生成结果框内部，与「复制」同处一区：它们是同一件事的两种去处 */
.page-assistant .solo-save{margin:0 var(--s3) var(--s3);padding-top:var(--s3);border-top:1px solid var(--indigo-200)}
.page-assistant .solo-save-row{display:flex;align-items:center;gap:var(--s2);flex-wrap:wrap}
.page-assistant .solo-save-l{font-size:12.5px;font-weight:700;color:var(--indigo-800)}
.page-assistant .solo-save-item{flex:1 1 260px;min-width:0}
.page-assistant .solo-save-cur{margin:var(--s2) 0 0;padding:var(--s2) var(--s3);background:var(--surface);border:1px dashed var(--line);
  border-radius:var(--radius-sm);font-size:12.5px;line-height:1.65;color:var(--muted);white-space:pre-wrap}
.page-assistant .solo-save-cur em{font-style:normal;font-weight:700;color:var(--amber);margin-right:var(--s2)}
.page-assistant .solo-save-acts{display:flex;align-items:center;gap:var(--s2);flex-wrap:wrap;margin-top:var(--s2)}
.page-assistant .solo-save-ok{font-size:12.5px;font-weight:700;color:var(--indigo-700)}
/* 第 2/3 步面板顶部的路线提示，与 .p-desc 区分开但不喧宾夺主 */
.page-assistant .route-note{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:18px;padding:12px 16px;border:1px solid var(--line);border-radius:12px;background:var(--paper-2);font-size:12.5px;line-height:1.6;color:var(--muted)}
.page-assistant .route-note>span{flex:1;min-width:220px}
.page-assistant .route-note b{color:var(--indigo-700)}
/* ---- 第二步工作台条 ----
   一条横条装下「依据哪份规范 · 共几条 | 哪份草稿 · 叫什么 | 填到哪儿了 | 存/删」，
   替代原先五个纵向堆叠的块。间距一律走上面那套 4pt 档位，不再出现 10/12/14/16 混排 */
.page-assistant .wb{display:flex;align-items:center;flex-wrap:wrap;gap:var(--s3) var(--s4);padding:var(--s3) var(--s4);margin-bottom:var(--s6);background:var(--paper);border:1px solid var(--line);border-radius:var(--radius)}
.page-assistant .wb-src{display:flex;align-items:center;gap:var(--s2);flex-wrap:wrap;min-width:0}
.page-assistant .wb-src .gchips b{background:var(--indigo-100);color:var(--indigo-800)}
.page-assistant .wb-src .gchips b.hot{background:var(--cinnabar);color:#fff}
.page-assistant .wb-count{font-size:12px;color:var(--muted)}
/* 分隔线而不是又一个盒子：把「这份清单是什么」与「我的这份草稿」两组分开 */
.page-assistant .wb-sep{width:1px;align-self:stretch;min-height:24px;background:var(--line);flex:none}
.page-assistant .wb-name{flex:1 1 200px;min-width:0;font-family:inherit;font-size:13.5px;color:var(--ink);background:var(--surface);border:1.5px solid var(--line);border-radius:var(--radius-sm);padding:7px 12px}
.page-assistant .wb-name:focus{outline:none;border-color:var(--indigo-300)}
.page-assistant .wb-name::placeholder{color:var(--muted)}
.page-assistant .wb-prog{display:flex;align-items:center;gap:var(--s2);flex:none}
.page-assistant .wb-prog .meter{flex:none;width:56px;height:6px}
.page-assistant .wb-prog b{font-size:13px;font-weight:700;color:var(--indigo-700);font-variant-numeric:tabular-nums}
.page-assistant .wb-prog b em{font-style:normal;font-weight:600;color:var(--muted)}
.page-assistant .wb-act{display:flex;align-items:center;gap:var(--s2);flex:none;margin-left:auto}
.page-assistant .wb-hint{margin:calc(var(--s6) * -1 + var(--s2)) 0 var(--s6);font-size:12.5px;line-height:1.55;color:var(--muted)}
/* 导入已有稿件。用 label 包 input 而不是自己 click() 一个隐藏 input：
   前者原生可键盘聚焦，后者要额外补一堆 a11y */
.page-assistant .df-import{position:relative;overflow:hidden;cursor:pointer}
.page-assistant .df-import input{position:absolute;inset:0;opacity:0;cursor:pointer;font-size:0}
.page-assistant .df-import.busy{opacity:.6;pointer-events:none}
.page-assistant .df-imp-bar{margin:calc(var(--s6) * -1 + var(--s2)) 0 var(--s4)}
.page-assistant .df-imp-ok{margin:calc(var(--s6) * -1 + var(--s2)) 0 var(--s6);padding:var(--s3) var(--s4);
  background:var(--indigo-100);border-radius:var(--radius-sm);font-size:12.5px;line-height:1.65;color:var(--indigo-800)}
.page-assistant .tmpl{border:1px solid var(--line);border-radius:var(--radius);overflow:hidden}
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
.page-assistant .df-sel{flex:none;max-width:180px;font-family:inherit;font-size:13px;color:var(--ink);background:var(--surface);border:1.5px solid var(--line);border-radius:var(--radius-sm);padding:7px 10px}
.page-assistant .df-state{font-size:12px;color:var(--muted)}
.page-assistant .df-state.dirty{color:var(--cinnabar-d)}
.page-assistant .df-del{font-family:inherit;font-size:12.5px;color:var(--muted);background:none;border:none;cursor:pointer;padding:6px 2px;text-decoration:underline;text-underline-offset:3px}
.page-assistant .df-del:hover{color:var(--cinnabar-d)}
.page-assistant .df-del:disabled{opacity:.45;cursor:not-allowed}
.page-assistant .df-ta{display:block;width:100%;margin-top:8px;font-family:inherit;font-size:13.5px;font-weight:400;line-height:1.6;color:var(--ink);background:var(--surface);border:1.5px solid var(--line);border-radius:var(--radius-sm);padding:9px 12px;resize:vertical}
.page-assistant .df-ta:focus{outline:none;border-color:var(--indigo-300)}
.page-assistant .df-ta.filled{background:var(--paper)}
.page-assistant .df-compose{display:flex;align-items:center;gap:var(--s2);flex-wrap:wrap;margin-top:var(--s4)}
.page-assistant .df-miss{font-size:12.5px;color:var(--cinnabar-d)}
.page-assistant .df-preview{border:1px solid var(--line);border-radius:var(--radius);padding:var(--s4);background:var(--paper)}
/* 跟着左栏清单一起滚：两栏等高时，右栏比左栏矮一大截会显得整段悬空 */
.page-assistant .df-preview pre{margin:0;max-height:520px;overflow:auto;white-space:pre-wrap;word-break:break-word;font-family:inherit;font-size:13px;line-height:1.7;color:var(--ink)}
.page-assistant .df-preview-empty{margin:0;border:1px dashed var(--line);border-radius:var(--radius);padding:var(--s6) var(--s4);font-size:12.5px;line-height:1.65;color:var(--muted)}
.page-assistant .afield .inp:disabled{background:var(--paper-2);color:var(--muted);cursor:not-allowed}
.page-assistant .afield{margin-bottom:14px}
.page-assistant .afield>label{display:block;font-size:12.5px;font-weight:700;color:var(--indigo-700);margin-bottom:6px}
.page-assistant .afield .inp{width:100%;border:1.5px solid var(--line);border-radius:var(--radius-sm);padding:9px 12px;font-family:inherit;font-size:13.5px;color:var(--ink);background:var(--surface)}
.page-assistant .tmpl-note{margin-top:var(--s6);font-size:12.5px;color:var(--muted);line-height:1.55}
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
.page-assistant .rv-file{position:relative;overflow:hidden;display:inline-flex;align-items:center;font-size:13px;font-weight:600;color:var(--indigo-700);background:var(--surface);border:1.5px solid var(--line);border-radius:var(--radius-sm);padding:8px 14px;cursor:pointer;transition:.18s}
.page-assistant .rv-file:hover{border-color:var(--indigo-300);background:var(--indigo-100)}
.page-assistant .rv-file input{position:absolute;inset:0;opacity:0;cursor:pointer}
.page-assistant .rv-chars{font-size:12.5px;color:var(--muted);font-variant-numeric:tabular-nums}
.page-assistant .rv-chars.short{color:var(--amber)}
.page-assistant .rv-target{font-size:12.5px;color:var(--indigo-700);font-weight:600;margin-right:auto}
.page-assistant .rv-target.warn{color:var(--amber)}
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
.page-assistant .chk .na .ci{background:var(--paper-2);color:var(--muted)}
.page-assistant .chk .na .cstat{color:var(--muted);background:var(--paper-2)}
.page-assistant .ck-list li{align-items:flex-start}
.page-assistant .ck-list .ctext b em{font-style:normal;font-size:11px;font-weight:700;color:var(--indigo-500);background:var(--indigo-100);border-radius:999px;padding:2px 9px;margin-right:8px;white-space:nowrap}
.page-assistant .ck-list .ckf{padding-left:11px;border-left:2px solid var(--line);margin-top:7px}
.page-assistant .ck-list .ckf.issue{border-left-color:var(--cinnabar)}
.page-assistant .ck-list .ckf.warn{border-left-color:var(--amber)}
.page-assistant .ck-list .ckf i{font-style:normal;font-weight:700;color:var(--indigo-700);margin-right:6px}
.page-assistant .ck-list .ckf u{text-decoration:none;color:var(--ink)}
.page-assistant .ck-list .ckf b{display:block;margin-top:3px;font-weight:600;color:var(--indigo-700)}
/* 结果区里的稿件原文（默认折叠，带行号）。等宽字体是必须的 ——
   行号要对齐才读得出「第 12 行」，比例字体下数字列会歪 */
.page-assistant .src{margin-bottom:16px;border:1px solid var(--line);border-radius:12px;background:var(--paper);overflow:hidden}
.page-assistant .src-tog{width:100%;display:flex;align-items:center;gap:9px;padding:11px 14px;background:none;border:0;
  cursor:pointer;font-size:13px;font-weight:700;color:var(--indigo-800);text-align:left}
.page-assistant .src-tog:hover{background:var(--paper-2)}
.page-assistant .src-tog svg{width:14px;height:14px;flex-shrink:0;transition:transform .18s}
.page-assistant .src-tog svg.open{transform:rotate(90deg)}
.page-assistant .src-tog em{margin-left:auto;font-style:normal;font-weight:400;color:var(--muted);font-size:12.5px}
.page-assistant .src-body{list-style:none;margin:0;padding:8px 0;max-height:420px;overflow-y:auto;
  border-top:1px solid var(--line);background:var(--surface);
  font-family:ui-monospace,"SFMono-Regular",Menlo,Consolas,monospace;font-size:12.5px;line-height:1.75}
.page-assistant .src-body li{display:flex;gap:12px;padding:1px 14px;scroll-margin:80px}
.page-assistant .src-body li.hit{background:var(--amber-bg)}
.page-assistant .src-n{flex-shrink:0;width:38px;text-align:right;color:var(--muted);user-select:none;font-variant-numeric:tabular-nums}
.page-assistant .src-t{white-space:pre-wrap;word-break:break-word;color:var(--ink)}
/* 判定里的行号引用：看着像正文的一部分，点得动 */
.page-assistant .src-jump{background:none;border:0;padding:0;cursor:pointer;font:inherit;color:var(--indigo-700);
  font-weight:700;text-underline-offset:3px}
.page-assistant .src-jump:hover{text-decoration:underline}

/* 校验历史。与 .audit 同一套卡片语言：两者都是「这一步发生过什么」的回看区 */
.page-assistant .rvh{margin-top:22px;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:18px}
.page-assistant .rvh-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:14px}
.page-assistant .rvh-empty{font-size:13px;color:var(--muted);text-align:center;padding:22px 12px;border:1.5px dashed var(--line);border-radius:11px}
.page-assistant .rvh-list{list-style:none;display:flex;flex-direction:column;gap:8px;max-height:340px;overflow-y:auto;padding-right:4px}
.page-assistant .rvh-list li{display:grid;grid-template-columns:150px minmax(0,1fr) auto auto;gap:14px;align-items:center;
  padding:11px 14px;border:1px solid var(--line);border-radius:11px;background:var(--surface);font-size:13px}
.page-assistant .rvh-list li.on{border-color:var(--indigo-300);background:var(--indigo-100)}
.page-assistant .rvh-when{font-family:"Spectral",serif;font-weight:700;color:var(--indigo-500);font-variant-numeric:tabular-nums}
.page-assistant .rvh-meta{display:flex;align-items:baseline;gap:10px;min-width:0}
.page-assistant .rvh-meta b{color:var(--indigo-900);font-weight:700}
.page-assistant .rvh-meta span{color:var(--muted);font-size:12.5px;white-space:nowrap}
.page-assistant .rvh-stat{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.page-assistant .rvh-stat em{font-style:normal;font-weight:700;color:var(--indigo-700);font-variant-numeric:tabular-nums}
.page-assistant .rvh-state{font-size:12.5px;font-weight:700;color:var(--indigo-700)}
.page-assistant .rvh-state.bad{color:var(--cinnabar-d)}
.page-assistant .rvh-err{font-weight:400;color:var(--muted);font-size:12px;max-width:280px}
.page-assistant .rvh-acts{display:flex;align-items:center;gap:6px}
.page-assistant .rvh-del{width:30px;height:30px;display:grid;place-items:center;border:1px solid var(--line);border-radius:9px;
  background:var(--surface);color:var(--muted);cursor:pointer;transition:color .18s,border-color .18s}
.page-assistant .rvh-del:hover{color:var(--cinnabar-d);border-color:var(--cinnabar)}
.page-assistant .rvh-del svg{width:15px;height:15px}
@media (max-width:860px){
  .page-assistant .rvh-list li{grid-template-columns:1fr;gap:8px}
}
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
.page-assistant .style-chips{display:flex;align-items:center;flex-wrap:wrap;gap:var(--s2);margin:var(--s6) 0 var(--s4)}
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
.page-assistant .share-perm{display:inline-flex;background:var(--paper-2);border:1px solid var(--line);border-radius:var(--radius-sm);padding:3px;gap:2px}
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
.page-assistant .two,.page-assistant .two-tpl{grid-template-columns:1fr}
.page-assistant .tpl-side{position:static}
/* 工作台条在窄屏会折成两三行，两组之间的竖分隔线此时没有分隔任何东西 */
.page-assistant .wb-sep{display:none}
.page-assistant .wb-act{margin-left:0}
}
</style>
