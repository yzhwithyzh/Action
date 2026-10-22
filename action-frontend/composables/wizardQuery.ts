/**
 * 报告助手向导状态 ↔ URL query 的互转（纯函数，可单测）。
 *
 * 与 `authValidation.ts` 同一种分层：**输入是普通值，输出是普通值，不碰 route、
 * 不碰 ref**，页面负责把状态喂进来、把结果写回去（见 `pages/assistant.vue`）。
 *
 * 为什么要把它挪出 SFC：`parseWizardQuery` 是一层输入校验，值会一路流到取 checklist
 * 的接口参数上；`buildWizardQuery` 的「只带非默认值」有好几个分支。这两件事写在
 * `<script setup>` 里就只能靠手点浏览器验，同 `resolveRedirect` 当初挪出来的理由。
 */

import { findPathToType, MAX_DEPTH, OPT_KEY_RE, walkWizard, type WizardQuestion } from './studyWizard'

/**
 * 研究类型的**兜底**词表（与 sql/041 的 12 个判定结果一一对应）。
 *
 * **正常情况下第一步是一棵分支问卷**（`GET /action/site/study-wizard`），这里这份只在
 * 问卷与研究类型两个接口都取不到数据时垫底：平铺成一道题（`flatWizard`），文案回落
 * i18n 的 `assistant.typeOpt.<key>`，免得第一步变成一排空白让人没法往下走。
 */
export const FALLBACK_TYPE_OPTS = [
  'rct', 'nrct', 'case', 'sr', 'sr_narrative', 'cohort', 'case_control',
  'cross_sectional', 'protocol', 'protocol_obs', 'animal', 'guideline',
] as const

/**
 * 老链接兼容：`trial` 曾是页面上的一个按钮（rct + nrct 合成的），配合 `?rand=y|n`
 * 才能定位到具体类型。不映射的话老链接会被判非法、悄悄回落成默认。
 */
const LEGACY_TYPE_ALIASES: Record<string, (query: Record<string, unknown>) => string> = {
  trial: (query) => (query.rand === 'n' ? 'nrct' : 'rct'),
}

/**
 * 向导总步数：① 类型匹配 → ② 报告撰写 → ③ 合规与一致性检查 → ④ AI 优化 → ⑤ 成果交付。
 *
 * 2026-09 曾收成三步（匹配 → 撰写 → 导出），2026-10 又拆回五步：「写」「查」「改」三件事
 * 挤在第二步一屏里，用户分不清现在该干哪一件。这一版每一步只回答一个问题，③ 只诊断不改稿，
 * ③ 的问题清单就是 ④ 的工作队列。
 *
 * 五步时代的老链接（`step=4` 深度优化、`step=5` 导出）与现在的含义一致，原样生效；
 * 三步时代的 `step=3`（导出）会落在 ③ 检查 —— 就在导出前一步，不另做改道
 */
export const WIZARD_STEP_COUNT = 5

/**
 * 第一步末尾的「路线」选择。
 *
 * `draft` = 还没开始写,走第 2 步的逐条模板;`manuscript` = 已经有稿件了,第 2 步用不上、
 * 直奔第 3 步校验。空串 = 还没选,此时一切照旧(不标注、不提示)——**默认不替用户选**,
 * 猜错一次就是把人推到用不到的那一步。
 */
export const STAGE_OPTS = ['draft', 'manuscript'] as const

/**
 * 第一步的答案。
 *
 * `path` 是分支问卷里每一层选中的选项标识（如 `['A', 'y', 'n']`）。研究类型不单独存 ——
 * 它由路径走出来（`walkWizard`），单独存一份就会出现「路径说是 RCT、类型字段说是队列研究」
 * 这种两份真相对不上的状态。空数组 = 全取默认（每层第一个选项）。
 */
export interface WizardAnswers {
  path: string[]
  stage: string
}

/** 默认答案。与页面初值一致 */
export const WIZARD_DEFAULTS: WizardAnswers = { path: [], stage: '' }

/**
 * 向导状态 → query。
 *
 * **只带非默认值**：默认那份地址就是干净的 `/assistant`，也不会把 `step=1` 这种
 * 没信息量的参数写进地址栏。路径与默认路径相同时同样不写。
 *
 * @param step 当前步数
 * @param ans 第一步的答案（`path` 应是 `walkWizard` 规范化过的）
 * @param defaultPath 全取默认时走出来的路径
 * @param part 第二步正在看的清单表；0 = 未指定（不写进地址栏）
 * @param gl 第二步选的规范 id（不是重点推荐那份时才传）；0 = 未指定
 * @returns 可直接交给 `router.replace({ query })` 的对象
 */
export function buildWizardQuery(
  step: number,
  ans: WizardAnswers,
  defaultPath: readonly string[] = [],
  part = 0,
  gl = 0,
): Record<string, string> {
  const q: Record<string, string> = {}
  if (step !== 1) q.step = String(step)
  if (ans.path.length && ans.path.join('.') !== defaultPath.join('.')) q.path = ans.path.join('.')
  if (ans.stage) q.stage = ans.stage
  if (gl > 0) q.gl = String(gl)
  if (part > 0) q.part = String(part)

  return q
}

/**
 * query → 向导状态。
 *
 * **逐个走白名单**：这几个值会一路流到取 checklist 的接口参数上，手改地址栏就能塞进
 * 任意字符串。非法值一律忽略、回落默认且不报错 —— 用户看到的是一份正常的第一步，
 * 而不是一屏「参数错误」。数组型 query（`?path=a&path=b`）同样按非法处理。
 *
 * 路径要拿**当前的问卷**去走一遍才算数（问卷是后台维护的）：走不通的那一层及其之后
 * 全部回落默认。问卷改版前的老链接只有 `?type=<key>`，按类型反查一条路径。
 *
 * @param query 来自 `route.query` 的原始对象
 * @param questions 当前的分支问卷；传空时路径只做字符集校验、不规范化
 * @returns 校验后的步数与答案，可直接赋给页面状态
 */
export function parseWizardQuery(
  query: Record<string, unknown>,
  questions: readonly WizardQuestion[] = [],
): { step: number; ans: WizardAnswers } {
  const one = (v: unknown) => (typeof v === 'string' ? v : '')
  const ans: WizardAnswers = { ...WIZARD_DEFAULTS, path: [] }

  const raw = one(query.path)
  const segs = raw ? raw.split('.') : []
  if (segs.length <= MAX_DEPTH && segs.every((s) => OPT_KEY_RE.test(s))) ans.path = segs

  if (!ans.path.length) {
    const type = one(query.type)
    const resolved = LEGACY_TYPE_ALIASES[type]?.(query) ?? type
    ans.path = findPathToType(questions, resolved) ?? []
  }
  if (questions.length) {
    const walk = walkWizard(questions, ans.path)
    // 与默认路径相同就存成空数组，保持「没选过」与「选的正是默认」在状态上一致
    ans.path = walk.path.join('.') === walkWizard(questions).path.join('.') ? [] : walk.path
  }

  const stage = one(query.stage)
  if ((STAGE_OPTS as readonly string[]).includes(stage)) ans.stage = stage

  // Number('') === 0、Number('2x') === NaN，两者都进不了下面这道闸
  const n = Number(one(query.step))
  const step = Number.isInteger(n) && n >= 1 && n <= WIZARD_STEP_COUNT ? n : 1

  return { step, ans }
}

/** 清单表序号的合法上限。一份规范眼下最多 3 张表，99 是留足余量的硬闸 */
const MAX_PART = 99

/**
 * 第二步正在看的清单表（`?part=`，`action_guideline_item.part_no`）。
 *
 * 进 URL 是为了登录往返：第二步切到 STRICTA 那张表 → 撞登录墙 → 回来还停在 STRICTA。
 * 非法值回落 0（= 未指定，页面取第一张表）；指定的表在当前规范里不存在时由页面自己回落。
 *
 * @param query 来自 `route.query` 的原始对象
 * @returns 1..MAX_PART 的整数，或 0
 */
export function parsePartQuery(query: Record<string, unknown>): number {
  const raw = typeof query.part === 'string' ? query.part : ''
  const n = Number(raw)

  return Number.isInteger(n) && n >= 1 && n <= MAX_PART ? n : 0
}

/**
 * 第二步选的规范（`?gl=`，`action_guideline.guideline_id`，sql/056）。
 *
 * 进 URL 的理由同 `?part=`：第二步切到 TIDieR-A → 撞登录墙 → 回来还停在 TIDieR-A。
 * 存 id 不存代号：代号在后台可改、还带空格。非法值回落 0；指定的规范不在当前研究类型的
 * 可选范围里时由页面自己忽略（`chooseGuideline` 返回 false）。
 *
 * @param query 来自 `route.query` 的原始对象
 * @returns 正整数规范 id，或 0
 */
export function parseGuidelineQuery(query: Record<string, unknown>): number {
  const raw = typeof query.gl === 'string' ? query.gl : ''
  const n = Number(raw)

  return Number.isInteger(n) && n >= 1 && n <= 2 ** 31 - 1 ? n : 0
}
