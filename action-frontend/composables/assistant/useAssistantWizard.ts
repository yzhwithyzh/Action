/**
 * 报告助手第一步：分支问卷 → 研究类型 → 用哪份规范。
 *
 * 问卷来自 `GET /action/site/study-wizard`（`action_wizard_question/option`，后台「研究类型管理 →
 * 分支问卷」维护）：第一题 7 选 1，按答案动态弹出下一题，叶子选项判定出一类研究。
 * **问什么、每个选项去哪都在库里，改分支不用改代码。** 判定出的那一类挂什么规范、
 * 推荐什么统计方法、带什么专属提示，仍由 `/study-types`（`action_study_type`）管。
 *
 * 两个请求**不在这里 await**，由页面在 `<script setup>` 顶层 await `ready`：Nuxt 只在
 * setup 顶层的 await 之后恢复组件实例，写在这个函数里的话，后面注册的生命周期钩子会挂空。
 * 第二步的 checklist 要按这里判定出的规范代号去取，所以页面必须先等它再往下走 ——
 * 否则预渲染时那次请求带的是空代号，烤进 HTML 的是一份空清单。
 */

import { findPathToType, flatWizard, walkWizard, type WizardQuestion } from '~/composables/studyWizard'
import { FALLBACK_TYPE_OPTS, WIZARD_DEFAULTS, type WizardAnswers } from '~/composables/wizardQuery'

interface StudyTypeStat { textZh: string | null; textEn: string | null }
/** 第二步「用哪份规范写」的一个选项（sql/056）。`itemCount` 为 0 的照样列出，标「条目待录入」 */
export interface ChecklistOption {
  guidelineId: number
  code: string
  nameZh: string | null
  nameEn: string | null
  itemCount: number
}
export interface StudyTypeRow {
  typeId: number
  typeKey: string
  nameZh: string | null
  nameEn: string | null
  /** 平铺兜底时的排列顺序（正常情况下第一步是分支问卷，顺序由问卷定） */
  sortNum: number | null
  hotGuideline: string | null
  /** 专属提示，显示在匹配结果卡片底部 */
  tipZh: string | null
  tipEn: string | null
  /** 重点推荐那份在前，其后是后台「可切换规范」；老接口没有这个字段时按 `hotGuideline` 一份算 */
  checklistOptions?: ChecklistOption[]
  /** 匹配卡上的展示标签（自由文本，不是规范代号，不能拿来切换） */
  guidelines: string[]
  stats: StudyTypeStat[]
}

export function useAssistantWizard() {
  const { t } = useI18n()
  const { pick } = useBilingual()

  const typesReq = useSiteObject<StudyTypeRow[]>('/study-types', 'assistant-types')
  const wizardReq = useSiteObject<WizardQuestion[]>('/study-wizard', 'assistant-wizard')

  const types = computed<StudyTypeRow[]>(() => typesReq.data.value?.data ?? [])

  /**
   * 问卷取不到时退成一道平铺题（`flatWizard`）：研究类型接口有数据就用它，再没有就用
   * `FALLBACK_TYPE_OPTS` + i18n 文案 —— 免得第一步变成一排空白，整个向导没法往下走。
   */
  const wizard = computed<WizardQuestion[]>(() => {
    const tree = wizardReq.data.value?.data ?? []
    if (tree.some((q) => q.isRoot === '1')) return tree

    const rows = [...types.value].sort((a, b) => (a.sortNum ?? 0) - (b.sortNum ?? 0))
    if (rows.length) {
      return flatWizard(rows.map((r) => ({
        key: r.typeKey,
        labelZh: r.nameZh || t(`assistant.typeOpt.${r.typeKey}`),
        labelEn: r.nameEn || '',
      })))
    }

    return flatWizard(FALLBACK_TYPE_OPTS.map((k) => ({ key: k, labelZh: t(`assistant.typeOpt.${k}`), labelEn: '' })))
  })

  /** 第一步的答案：问卷路径 + 路线 */
  const ans = ref<WizardAnswers>({ ...WIZARD_DEFAULTS, path: [] })
  /** 用户在第二步选的规范代号；空串或不在当前选项里 = 用重点推荐那份（见下面 `checklistCode`） */
  const chosenCode = ref('')

  /**
   * 按当前路径走一遍问卷：页面上显示哪几道题、各选中哪一项、判定为哪一类，全由它现算。
   * 上层换了答案，下层旧答案属于别的分支，自然作废 —— 不需要手动清。
   */
  const walk = computed(() => walkWizard(wizard.value, ans.value.path))
  const defaultPath = computed(() => walkWizard(wizard.value).path)

  /** 在第 depth 层（0 起）选了 optKey：保留上面几层，截掉下面的 */
  function answer(depth: number, optKey: string) {
    // 点的就是已选中的那一项：什么都不做 —— 否则路径在这一层被截断，下面几层的选择全回落默认
    if (walk.value.path[depth] === optKey) return
    ans.value.path = [...walk.value.path.slice(0, depth), optKey]
    // 换了研究类型就回到它的重点推荐规范。不放在 watch(resolvedKey) 里：挂载时从 URL 还原
    // 路径也会让类型变一次，那会把同时还原的 ?gl= 冲掉
    chosenCode.value = ''
  }

  /**
   * 跳到能判定出某类研究的那条路径（「继续上次的草稿」用：那份草稿是按某个研究类型建的）。
   *
   * @returns 问卷里找不到这一类（后台停用了它）时为 false，调用方不该再往下走
   */
  function answerType(typeKey: string): boolean {
    const path = findPathToType(wizard.value, typeKey)
    if (!path) return false
    ans.value.path = path
    chosenCode.value = ''

    return true
  }

  /**
   * 第一步末尾选的路线（`draft` 从零开始写 / `manuscript` 已有稿件 / `''` 还没选）。
   * **只标注不强制**：两条路的步骤都点得进去，只是把「哪几步对你适用」说出来。
   */
  const stage = computed({
    get: () => ans.value.stage,
    set: (v: string) => { ans.value.stage = v },
  })

  /** 问卷判定出的研究类型（`action_study_type.type_key`），第二步取哪份 checklist 由它定 */
  const resolvedKey = computed(() => walk.value.resultKey)

  const matched = computed<StudyTypeRow | null>(
    () => types.value.find((x) => x.typeKey === resolvedKey.value) ?? null,
  )

  /**
   * 专属提示 = 路径上各选项自带的提示 + 判定结果自身的提示。
   *
   * 选项也能带提示，是因为文档里有条件提示：RCT 那句「若设置假针 / 安慰剂对照，请重点报告
   * TIDieR-A 干预细节……」只对问题 3 答「是」的人成立，它挂在那个选项上而不是 RCT 这个结果上。
   */
  const matchTips = computed(() => [
    ...walk.value.steps.map((s) => pick(s.option as unknown as Record<string, unknown>, 'tip')),
    pick(matched.value as unknown as Record<string, unknown>, 'tip'),
  ].filter(Boolean))

  /**
   * 第二步可选的规范：重点推荐那份在前（sql/056）。**一份草稿只对应一份规范**，切换规范就是换一份草稿 ——
   * 草稿本来就按规范代号分开列（`myDrafts`），换代号时工作区会先存当前这份、再取那份规范下的草稿。
   */
  const checklistOptions = computed<ChecklistOption[]>(() => {
    const m = matched.value
    if (!m) return []
    if (m.checklistOptions?.length) return m.checklistOptions
    return m.hotGuideline ? [{ guidelineId: 0, code: m.hotGuideline, nameZh: null, nameEn: null, itemCount: 0 }] : []
  })

  /** 第二步展开哪份规范的 checklist（代号是按 id 现取的当前代号，sql/048） */
  const checklistCode = computed(() => {
    const opts = checklistOptions.value
    return opts.find((o) => o.code === chosenCode.value)?.code ?? opts[0]?.code ?? ''
  })

  /** @returns 这份规范不在当前研究类型的可选范围里时为 false（什么都不改） */
  function chooseGuideline(code: string): boolean {
    if (!checklistOptions.value.some((o) => o.code === code)) return false
    chosenCode.value = code === checklistOptions.value[0]?.code ? '' : code

    return true
  }

  return {
    ready: Promise.all([typesReq, wizardReq]),
    types,
    wizard,
    ans,
    walk,
    defaultPath,
    answer,
    answerType,
    stage,
    resolvedKey,
    matched,
    matchTips,
    checklistOptions,
    checklistCode,
    chooseGuideline,
  }
}
