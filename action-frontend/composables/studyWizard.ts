/**
 * 报告助手第一步「分支问卷」的走法（纯函数，可单测，见 `test/studyWizard.spec.ts`）。
 *
 * 问卷来自 `GET /action/site/study-wizard`（`action_wizard_question` + `action_wizard_option`，
 * 后台「研究类型管理 → 分支问卷」维护），照《ACTION智能匹配研究类型.docx》的分支逻辑：
 * 第一题 7 选 1，按答案动态弹出下一题（A 分支三层、B/F/G 一层就出结果），叶子选项
 * 判定出一类研究（`resultTypeKey` → `action_study_type.type_key`）。
 *
 * 页面只存「每一层选了哪个选项」这条路径（`opt_key` 数组），问卷当前长什么样、判定
 * 结果是什么，都由 `walkWizard` 从路径现算 —— 换了上层的答案，下层自然作废，不会留下
 * 一个指向别的分支的旧答案。
 */

export interface WizardOption {
  optionId?: number | null
  optKey: string
  labelZh: string | null
  labelEn: string | null
  nextQuestionId: number | null
  resultTypeKey: string | null
  tipZh: string | null
  tipEn: string | null
}

export interface WizardQuestion {
  questionId: number | null
  qKey: string
  textZh: string | null
  textEn: string | null
  isRoot: string
  options: WizardOption[]
}

/** 走过的一层：这一题，以及这一题上选中的那个选项 */
export interface WizardStep {
  question: WizardQuestion
  option: WizardOption
}

export interface WizardWalk {
  steps: WizardStep[]
  /** 规范化后的路径（每层实际选中的 optKey），可直接写回状态与 URL */
  path: string[]
  /** 判定的研究类型；树拼坏了走不到叶子时为空串 */
  resultKey: string
}

/** 选项标识的字符集（与后端 `WizardOptionModel.opt_key` 同一条正则）。点号是路径分隔符，不许出现 */
export const OPT_KEY_RE = /^[A-Za-z0-9_]{1,32}$/

/** 路径最多几层。真实问卷 3 层；这道闸只防手改地址栏塞进一长串 */
export const MAX_DEPTH = 8

/**
 * 从第一题出发，按路径逐层往下走。
 *
 * - 路径里这一层的 optKey 能在当前题里找到就用它，找不到（或路径已用完）就取**第一个选项**
 *   —— 与早先「默认选中 RCT」同一个口径：第一步永远有一个完整的匹配结果，第二步的
 *   checklist 才有得展开。一旦某层没对上，后面的路径段全部作废（它们属于别的分支）
 * - 防环：同一道题第二次出现就停。后台保存时已校验无环，这里只保证页面不死循环
 */
export function walkWizard(questions: readonly WizardQuestion[], path: readonly string[] = []): WizardWalk {
  const byId = new Map(questions.map((q) => [q.questionId, q]))
  const steps: WizardStep[] = []
  const seen = new Set<WizardQuestion>()
  let q = questions.find((x) => x.isRoot === '1')
  let onPath = true

  while (q && !seen.has(q) && q.options.length && steps.length < MAX_DEPTH) {
    seen.add(q)
    const want = onPath ? path[steps.length] : undefined
    let option = want !== undefined ? q.options.find((o) => o.optKey === want) : undefined
    if (!option) {
      onPath = false
      option = q.options[0]!
    }
    steps.push({ question: q, option })
    if (option.resultTypeKey) {
      return { steps, path: steps.map((s) => s.option.optKey), resultKey: option.resultTypeKey }
    }
    q = option.nextQuestionId != null ? byId.get(option.nextQuestionId) : undefined
  }

  return { steps, path: steps.map((s) => s.option.optKey), resultKey: '' }
}

/**
 * 找一条能走到这一类研究的路径（深度优先，按选项顺序取第一条）。
 *
 * 给老链接用：`?type=rct` 这种地址来自问卷改版之前，那时一个类型就是一个按钮。
 * 同一类研究可能有多条路径（RCT 在「是否设假针」答是/否都算），取第一条即可。
 */
export function findPathToType(questions: readonly WizardQuestion[], typeKey: string): string[] | null {
  const byId = new Map(questions.map((q) => [q.questionId, q]))
  const root = questions.find((x) => x.isRoot === '1')

  function dfs(q: WizardQuestion, trail: string[], seen: Set<WizardQuestion>): string[] | null {
    if (seen.has(q) || trail.length >= MAX_DEPTH) return null
    const nextSeen = new Set(seen).add(q)
    for (const o of q.options) {
      if (o.resultTypeKey) {
        if (o.resultTypeKey === typeKey) return [...trail, o.optKey]
        continue
      }
      const next = o.nextQuestionId != null ? byId.get(o.nextQuestionId) : undefined
      const hit = next ? dfs(next, [...trail, o.optKey], nextSeen) : null
      if (hit) return hit
    }

    return null
  }

  return root && typeKey ? dfs(root, [], new Set()) : null
}

/**
 * 接口没取到问卷时的兜底：把研究类型平铺成一道题。
 *
 * 构建期后端没起来、或线上接口挂了时，第一步不至于变成一片空白让人没法往下走。
 * 这时没有分支，但每一类研究都选得到，第二步照样展得开。
 */
export function flatWizard(types: readonly { key: string, labelZh: string, labelEn: string }[]): WizardQuestion[] {
  if (!types.length) return []

  return [{
    questionId: -1,
    qKey: 'type',
    textZh: null,
    textEn: null,
    isRoot: '1',
    options: types.map((t) => ({
      optKey: t.key,
      labelZh: t.labelZh,
      labelEn: t.labelEn,
      nextQuestionId: null,
      resultTypeKey: t.key,
      tipZh: null,
      tipEn: null,
    })),
  }]
}
