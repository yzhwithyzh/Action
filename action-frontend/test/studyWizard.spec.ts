import { describe, expect, it } from 'vitest'

import { findPathToType, flatWizard, walkWizard } from '../composables/studyWizard'
import { DOC_TREE, o, q } from './wizardFixture'

const keys = (path: string[]) => walkWizard(DOC_TREE, path).steps.map((s) => s.question.qKey)

describe('walkWizard', () => {
  it('不带路径时每层取第一个选项：干预性试验 → 随机 → 设假针 → RCT', () => {
    const w = walkWizard(DOC_TREE)
    expect(w.path).toEqual(['A', 'y', 'y'])
    expect(w.resultKey).toBe('rct')
  })

  // 文档的分支逻辑逐条过一遍：弹出哪几题、最后判成什么
  it.each([
    [['A', 'y', 'n'], ['type', 'randomized', 'sham'], 'rct'],
    [['A', 'n'], ['type', 'randomized'], 'nrct'],
    [['B'], ['type'], 'case'],
    [['C', 'y'], ['type', 'meta'], 'sr'],
    [['C', 'n'], ['type', 'meta'], 'sr_narrative'],
    [['D', 'cohort'], ['type', 'obs_design'], 'cohort'],
    [['D', 'case_control'], ['type', 'obs_design'], 'case_control'],
    [['D', 'cross_sectional'], ['type', 'obs_design'], 'cross_sectional'],
    [['E', 'trial'], ['type', 'protocol_main'], 'protocol'],
    [['E', 'obs'], ['type', 'protocol_main'], 'protocol_obs'],
    [['F'], ['type'], 'animal'],
    [['G'], ['type'], 'guideline'],
  ])('路径 %j 弹出 %j，判定 %s', (path, qs, result) => {
    const w = walkWizard(DOC_TREE, path)
    expect(w.steps.map((s) => s.question.qKey)).toEqual(qs)
    expect(w.path).toEqual(path)
    expect(w.resultKey).toBe(result)
  })

  it('随机分组答「否」就不再问假针', () => {
    expect(keys(['A', 'n'])).not.toContain('sham')
  })

  it('换了上层的答案，属于别的分支的下层旧答案作废', () => {
    // 原来在 A 分支答过 y/y，改选 D 后「y」在观察性研究那题里不存在 → 回落第一个选项
    expect(walkWizard(DOC_TREE, ['D', 'y', 'y']).path).toEqual(['D', 'cohort'])
  })

  it('路径里走不通的一层之后全部回落默认，不会「跳」到后面某个同名选项', () => {
    expect(walkWizard(DOC_TREE, ['A', 'zzz', 'n']).path).toEqual(['A', 'y', 'y'])
  })

  it('路径比树长时多余的段被丢掉', () => {
    expect(walkWizard(DOC_TREE, ['B', 'x', 'y']).path).toEqual(['B'])
  })

  it('空问卷 / 没有第一题：什么都不渲染，也没有判定', () => {
    expect(walkWizard([])).toEqual({ steps: [], path: [], resultKey: '' })
    expect(walkWizard(DOC_TREE.map((x) => ({ ...x, isRoot: '0' }))).resultKey).toBe('')
  })

  it('后台拼出了环也不会死循环', () => {
    const loop = [q(1, 'a', [o('x', 2)], true), q(2, 'b', [o('x', 1)])]
    const w = walkWizard(loop)
    expect(w.steps.map((s) => s.question.qKey)).toEqual(['a', 'b'])
    expect(w.resultKey).toBe('')
  })
})

describe('findPathToType', () => {
  it('老链接的 ?type= 反查到一条路径', () => {
    expect(findPathToType(DOC_TREE, 'rct')).toEqual(['A', 'y', 'y'])
    expect(findPathToType(DOC_TREE, 'nrct')).toEqual(['A', 'n'])
    expect(findPathToType(DOC_TREE, 'protocol_obs')).toEqual(['E', 'obs'])
    expect(findPathToType(DOC_TREE, 'guideline')).toEqual(['G'])
  })

  it('树里没有的类型（如已停用的 obs）返回 null', () => {
    expect(findPathToType(DOC_TREE, 'obs')).toBeNull()
    expect(findPathToType(DOC_TREE, '')).toBeNull()
    expect(findPathToType([], 'rct')).toBeNull()
  })
})

describe('flatWizard', () => {
  it('把研究类型平铺成一道题，每个选项直接判定为自己', () => {
    const tree = flatWizard([{ key: 'rct', labelZh: 'RCT', labelEn: 'RCT' }, { key: 'case', labelZh: '病例', labelEn: 'Case' }])
    expect(walkWizard(tree, ['case']).resultKey).toBe('case')
    expect(walkWizard(tree).resultKey).toBe('rct')
    expect(flatWizard([])).toEqual([])
  })
})
