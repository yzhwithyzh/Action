/**
 * 报告助手向导状态 ↔ URL query 的互转（纯函数，可单测）。
 *
 * 与 `authValidation.ts` 同一种分层：**输入是普通值，输出是普通值，不碰 route、
 * 不碰 ref**，页面负责把状态喂进来、把结果写回去（见 `pages/assistant.vue`）。
 *
 * 为什么要把它挪出 SFC：`parseWizardQuery` 是一层输入校验，值会一路流到取 checklist
 * 的接口参数上；`buildWizardQuery` 的「只带非默认值」有四个分支。这两件事写在
 * `<script setup>` 里就只能靠手点浏览器验，同 `resolveRedirect` 当初挪出来的理由。
 */

/** 第一步「研究类型」的选项，顺序即页面上的排列顺序 */
export const TYPE_OPTS = ['trial', 'case', 'sr', 'obs', 'protocol', 'animal', 'guideline'] as const

/** 向导总步数 */
export const WIZARD_STEP_COUNT = 5

/**
 * 第一步末尾的「路线」选择。
 *
 * `draft` = 还没开始写,走第 2 步的逐条模板;`manuscript` = 已经有稿件了,第 2 步用不上、
 * 直奔第 3 步校验。空串 = 还没选,此时一切照旧(不标注、不提示)——**默认不替用户选**,
 * 猜错一次就是把人推到用不到的那一步。
 */
export const STAGE_OPTS = ['draft', 'manuscript'] as const

/** 第一步的答案 */
export interface WizardAnswers {
  type: string
  rand: string
  sham: string
  stage: string
}

/** 默认答案。与页面初值一致，也是「哪些值不必写进 URL」的判据 */
export const WIZARD_DEFAULTS: WizardAnswers = { type: 'trial', rand: 'y', sham: 'y', stage: '' }

/** 是/否两个档位 */
const YES_NO = ['y', 'n']

/** 随机化 / 假针两个子问题只有试验类才问 */
function asksSubQuestions(ans: WizardAnswers): boolean {
  return ans.type === 'trial'
}

/**
 * 向导状态 → query。
 *
 * **只带非默认值**：默认那份地址就是干净的 `/assistant`，也不会把 `step=1` 这种
 * 没信息量的参数写进地址栏。非试验类不带 rand/sham —— 那两个问题它根本没问，
 * 带上会让分享出去的链接看起来像是选过。
 *
 * @param step 当前步数
 * @param ans 第一步的三个答案
 * @returns 可直接交给 `router.replace({ query })` 的对象
 */
export function buildWizardQuery(step: number, ans: WizardAnswers): Record<string, string> {
  const q: Record<string, string> = {}
  if (step !== 1) q.step = String(step)
  if (ans.type !== WIZARD_DEFAULTS.type) q.type = ans.type
  if (asksSubQuestions(ans)) {
    if (ans.rand !== WIZARD_DEFAULTS.rand) q.rand = ans.rand
    if (ans.sham !== WIZARD_DEFAULTS.sham) q.sham = ans.sham
  }
  if (ans.stage) q.stage = ans.stage

  return q
}

/**
 * query → 向导状态。
 *
 * **逐个走白名单**：这几个值会一路流到取 checklist 的接口参数上，手改地址栏就能塞进
 * 任意字符串。非法值一律忽略、回落默认且不报错 —— 用户看到的是一份正常的第一步，
 * 而不是一屏「参数错误」。数组型 query（`?type=a&type=b`）同样按非法处理。
 *
 * @param query 来自 `route.query` 的原始对象
 * @returns 校验后的步数与答案，可直接赋给页面状态
 */
export function parseWizardQuery(query: Record<string, unknown>): { step: number; ans: WizardAnswers } {
  const one = (v: unknown) => (typeof v === 'string' ? v : '')
  const ans: WizardAnswers = { ...WIZARD_DEFAULTS }

  const type = one(query.type)
  if ((TYPE_OPTS as readonly string[]).includes(type)) ans.type = type
  const rand = one(query.rand)
  if (YES_NO.includes(rand)) ans.rand = rand
  const sham = one(query.sham)
  if (YES_NO.includes(sham)) ans.sham = sham
  const stage = one(query.stage)
  if ((STAGE_OPTS as readonly string[]).includes(stage)) ans.stage = stage

  // Number('') === 0、Number('2x') === NaN，两者都进不了下面这道闸
  const n = Number(one(query.step))
  const step = Number.isInteger(n) && n >= 1 && n <= WIZARD_STEP_COUNT ? n : 1

  return { step, ans }
}
