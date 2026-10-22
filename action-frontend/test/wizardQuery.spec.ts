import { describe, expect, it } from 'vitest'

import { walkWizard } from '../composables/studyWizard'
import {
  buildWizardQuery,
  parseGuidelineQuery,
  parsePartQuery,
  parseWizardQuery,
  STAGE_OPTS,
  WIZARD_DEFAULTS,
  WIZARD_STEP_COUNT,
  type WizardAnswers,
} from '../composables/wizardQuery'
import { DOC_TREE } from './wizardFixture'

/** 一份默认答案，各用例只覆盖自己关心的那一项 */
const ans = (patch: Partial<WizardAnswers> = {}): WizardAnswers => ({ ...WIZARD_DEFAULTS, path: [], ...patch })
const DEFAULT_PATH = walkWizard(DOC_TREE).path

describe('buildWizardQuery', () => {
  it('全默认时不写任何参数 —— 地址栏保持干净的 /assistant', () => {
    expect(buildWizardQuery(1, ans())).toEqual({})
    expect(buildWizardQuery(1, ans({ path: DEFAULT_PATH }), DEFAULT_PATH)).toEqual({})
  })

  it('带上非默认的步数与路径', () => {
    expect(buildWizardQuery(3, ans({ path: ['D', 'cohort'] }), DEFAULT_PATH)).toEqual({ step: '3', path: 'D.cohort' })
    expect(buildWizardQuery(1, ans({ path: ['A', 'y', 'n'] }), DEFAULT_PATH)).toEqual({ path: 'A.y.n' })
  })

  it('选了路线才带 stage —— 没选是有意义的第三态，不能当成选了 draft', () => {
    expect(buildWizardQuery(1, ans({ stage: 'draft' }))).toEqual({ stage: 'draft' })
    expect(buildWizardQuery(3, ans({ stage: 'manuscript' }))).toEqual({ step: '3', stage: 'manuscript' })
  })
})

describe('parseWizardQuery', () => {
  it('原样还原一份合法 query', () => {
    expect(parseWizardQuery({ step: '2', path: 'C.n' }, DOC_TREE)).toEqual({ step: 2, ans: ans({ path: ['C', 'n'] }) })
  })

  it('空 query 回落默认', () => {
    expect(parseWizardQuery({}, DOC_TREE)).toEqual({ step: 1, ans: ans() })
  })

  it('路径等于默认路径时存成空 —— 与「没选过」同一个状态', () => {
    expect(parseWizardQuery({ path: 'A.y.y' }, DOC_TREE).ans.path).toEqual([])
  })

  it('路径按当前问卷规范化：走不通的那层之后回落默认', () => {
    expect(parseWizardQuery({ path: 'D.nope' }, DOC_TREE).ans.path).toEqual(['D', 'cohort'])
    expect(parseWizardQuery({ path: 'E' }, DOC_TREE).ans.path).toEqual(['E', 'trial'])
  })

  it('字符集不对的路径整段忽略 —— 这个值会流到取 checklist 的接口参数上', () => {
    for (const path of ['<script>', 'A..y', 'A.y.', 'A/y', 'A.y.y.y.y.y.y.y.y']) {
      expect(parseWizardQuery({ path }, DOC_TREE).ans.path, `path=${path}`).toEqual([])
    }
  })

  // 问卷改版前一个类型就是一个按钮，分享出去的链接是 ?type=<key>
  it('老链接的 ?type= 反查成路径', () => {
    expect(parseWizardQuery({ type: 'nrct' }, DOC_TREE).ans.path).toEqual(['A', 'n'])
    expect(parseWizardQuery({ type: 'sr' }, DOC_TREE).ans.path).toEqual(['C', 'y'])
    expect(parseWizardQuery({ type: 'protocol' }, DOC_TREE).ans.path).toEqual(['E', 'trial'])
  })

  it('更老的 ?type=trial&rand= 先翻成 rct / nrct', () => {
    expect(parseWizardQuery({ type: 'trial', rand: 'n' }, DOC_TREE).ans.path).toEqual(['A', 'n'])
    expect(parseWizardQuery({ type: 'trial' }, DOC_TREE).ans.path).toEqual([])
  })

  it('问卷里走不到的老类型（已停用的 obs）回落默认', () => {
    expect(parseWizardQuery({ type: 'obs' }, DOC_TREE).ans.path).toEqual([])
    expect(parseWizardQuery({ type: '<script>' }, DOC_TREE).ans.path).toEqual([])
  })

  it('path 与 type 同时给时以 path 为准', () => {
    expect(parseWizardQuery({ path: 'F', type: 'rct' }, DOC_TREE).ans.path).toEqual(['F'])
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

  // 2026-10 拆回五步：五步时代的老链接（step=4 优化、step=5 导出）含义与现在一致，原样生效
  it('五步：step=4 是 AI 优化、step=5 是成果交付，不再改道', () => {
    expect(WIZARD_STEP_COUNT).toBe(5)
    expect(parseWizardQuery({ step: '4' }).step).toBe(4)
    expect(parseWizardQuery({ step: '5' }).step).toBe(5)
  })

  it('数组型 query（?path=a&path=b）按非法处理', () => {
    expect(parseWizardQuery({ path: ['B', 'C'], step: ['2'] }, DOC_TREE)).toEqual({ step: 1, ans: ans() })
  })

  it('每个合法步数都进得来', () => {
    for (let n = 1; n <= WIZARD_STEP_COUNT; n += 1) {
      expect(parseWizardQuery({ step: String(n) }).step).toBe(n)
    }
  })
})

describe('清单表 ?part=', () => {
  it('只在指定了表时写进地址栏', () => {
    expect(buildWizardQuery(2, ans(), DEFAULT_PATH)).toEqual({ step: '2' })
    expect(buildWizardQuery(2, ans(), DEFAULT_PATH, 3)).toEqual({ step: '2', part: '3' })
  })

  it('非法值回落 0（= 由页面取第一张表）', () => {
    expect(parsePartQuery({ part: '3' })).toBe(3)
    for (const part of ['0', '-1', '1.5', 'x', '', '100', undefined]) {
      expect(parsePartQuery({ part }), `part=${part}`).toBe(0)
    }
    expect(parsePartQuery({ part: ['2'] })).toBe(0)
  })
})

describe('规范 ?gl=（sql/056）', () => {
  it('只在选了非推荐规范时写进地址栏', () => {
    expect(buildWizardQuery(2, ans(), DEFAULT_PATH, 0, 0)).toEqual({ step: '2' })
    expect(buildWizardQuery(2, ans(), DEFAULT_PATH, 0, 8)).toEqual({ step: '2', gl: '8' })
    expect(parseGuidelineQuery(buildWizardQuery(2, ans(), DEFAULT_PATH, 2, 8))).toBe(8)
  })

  it('非法值回落 0（= 用重点推荐那份）', () => {
    expect(parseGuidelineQuery({ gl: '8' })).toBe(8)
    for (const gl of ['0', '-1', '1.5', 'x', '', 'CONSORT', undefined]) {
      expect(parseGuidelineQuery({ gl }), `gl=${gl}`).toBe(0)
    }
    expect(parseGuidelineQuery({ gl: ['8'] })).toBe(0)
  })
})

describe('build 与 parse 互为逆运算', () => {
  it('任一状态 build 再 parse 回得来', () => {
    const states: Array<[number, WizardAnswers]> = [
      [1, ans()],
      [2, ans({ path: ['B'] })],
      [3, ans({ path: ['A', 'n'] })],
      [3, ans({ path: ['A', 'y', 'n'] })],
      [2, ans({ path: ['G'] })],
      [2, ans({ stage: 'draft' })],
      [3, ans({ path: ['D', 'cross_sectional'], stage: 'manuscript' })],
    ]
    for (const [step, a] of states) {
      expect(parseWizardQuery(buildWizardQuery(step, a, DEFAULT_PATH), DOC_TREE)).toEqual({ step, ans: a })
    }
  })
})
