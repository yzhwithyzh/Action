import { describe, expect, it } from 'vitest'

import {
  buildWizardQuery,
  parseWizardQuery,
  STAGE_OPTS,
  TYPE_OPTS,
  WIZARD_DEFAULTS,
  WIZARD_STEP_COUNT,
  type WizardAnswers,
} from '../composables/wizardQuery'

/** 一份默认答案，各用例只覆盖自己关心的那一项 */
const ans = (patch: Partial<WizardAnswers> = {}): WizardAnswers => ({ ...WIZARD_DEFAULTS, ...patch })

describe('buildWizardQuery', () => {
  it('全默认时不写任何参数 —— 地址栏保持干净的 /assistant', () => {
    expect(buildWizardQuery(1, ans())).toEqual({})
  })

  it('带上非默认的步数与类型', () => {
    expect(buildWizardQuery(3, ans({ type: 'case' }))).toEqual({ step: '3', type: 'case' })
  })

  it('试验类才带随机化/假针', () => {
    expect(buildWizardQuery(1, ans({ rand: 'n', sham: 'n' }))).toEqual({ rand: 'n', sham: 'n' })
  })

  it('非试验类不带随机化/假针 —— 那两个问题它根本没问过', () => {
    expect(buildWizardQuery(2, ans({ type: 'animal', rand: 'n', sham: 'n' }))).toEqual({
      step: '2',
      type: 'animal',
    })
  })

  it('选了路线才带 stage —— 没选是有意义的第三态，不能当成选了 draft', () => {
    expect(buildWizardQuery(1, ans())).toEqual({})
    expect(buildWizardQuery(1, ans({ stage: 'draft' }))).toEqual({ stage: 'draft' })
    expect(buildWizardQuery(3, ans({ stage: 'manuscript' }))).toEqual({ step: '3', stage: 'manuscript' })
  })
})

describe('parseWizardQuery', () => {
  it('原样还原一份合法 query', () => {
    expect(parseWizardQuery({ step: '2', type: 'sr' })).toEqual({ step: 2, ans: ans({ type: 'sr' }) })
    expect(parseWizardQuery({ rand: 'n', sham: 'n' })).toEqual({ step: 1, ans: ans({ rand: 'n', sham: 'n' }) })
  })

  it('空 query 回落默认', () => {
    expect(parseWizardQuery({})).toEqual({ step: 1, ans: ans() })
  })

  it('词表外的研究类型一律忽略 —— 这个值会流到取 checklist 的接口参数上', () => {
    expect(parseWizardQuery({ type: 'rct' }).ans.type).toBe(WIZARD_DEFAULTS.type)
    expect(parseWizardQuery({ type: '<script>' }).ans.type).toBe(WIZARD_DEFAULTS.type)
    expect(parseWizardQuery({ type: '' }).ans.type).toBe(WIZARD_DEFAULTS.type)
  })

  it('rand / sham 只认 y 与 n', () => {
    expect(parseWizardQuery({ rand: 'yes', sham: '1' }).ans).toEqual(ans())
  })

  it('stage 只认 draft 与 manuscript，其余回落「还没选」', () => {
    for (const stage of STAGE_OPTS) {
      expect(parseWizardQuery({ stage }).ans.stage).toBe(stage)
    }
    for (const stage of ['review', 'DRAFT', '1', ' ']) {
      expect(parseWizardQuery({ stage }).ans.stage, `stage=${stage}`).toBe('')
    }
  })

  it('越界、非整数、非数字的步数一律回落第一步', () => {
    for (const step of ['0', '6', '-1', '2.5', '2x', 'NaN', 'Infinity', '', ' ']) {
      expect(parseWizardQuery({ step }).step, `step=${step}`).toBe(1)
    }
  })

  it('数组型 query（?type=a&type=b）按非法处理', () => {
    expect(parseWizardQuery({ type: ['case', 'sr'], step: ['2'] })).toEqual({ step: 1, ans: ans() })
  })

  it('每个合法步数都进得来', () => {
    for (let n = 1; n <= WIZARD_STEP_COUNT; n += 1) {
      expect(parseWizardQuery({ step: String(n) }).step).toBe(n)
    }
  })

  it('每个词表内的类型都进得来', () => {
    for (const type of TYPE_OPTS) {
      expect(parseWizardQuery({ type }).ans.type).toBe(type)
    }
  })
})

describe('build 与 parse 互为逆运算', () => {
  it('任一状态 build 再 parse 回得来（非试验类的子问题除外，它们本就不该被记住）', () => {
    const states: Array<[number, WizardAnswers]> = [
      [1, ans()],
      [2, ans({ type: 'case' })],
      [5, ans({ rand: 'n' })],
      [3, ans({ rand: 'n', sham: 'n' })],
      [4, ans({ type: 'guideline' })],
      [2, ans({ stage: 'draft' })],
      [3, ans({ type: 'sr', stage: 'manuscript' })],
    ]
    for (const [step, a] of states) {
      expect(parseWizardQuery(buildWizardQuery(step, a))).toEqual({ step, ans: a })
    }
  })
})
