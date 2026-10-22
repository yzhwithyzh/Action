import { describe, expect, it } from 'vitest'

import {
  countPlaceholders,
  deliverChecks,
  isIncluded,
  listParts,
  scopeIds,
  toggleIncluded,
  type ScopeRow,
} from '../composables/reportScope'

const ROWS: ScopeRow[] = [
  { itemId: 1, partNo: 1, partTitle: 'CONSORT', required: true },
  { itemId: 2, partNo: 1, partTitle: 'CONSORT', required: false },
  { itemId: 3, partNo: 2, partTitle: '摘要', required: true },
  { itemId: 4, partNo: 3, partTitle: 'STRICTA', required: true },
]

describe('listParts', () => {
  it('按 partNo 分表，保持首次出现的顺序', () => {
    expect(listParts(ROWS)).toEqual([
      { partNo: 1, title: 'CONSORT', total: 2, required: 1 },
      { partNo: 2, title: '摘要', total: 1, required: 1 },
      { partNo: 3, title: 'STRICTA', total: 1, required: 1 },
    ])
  })

  it('partNo 为空按 1 算', () => {
    expect(listParts([{ itemId: 9, partNo: null, partTitle: '', required: true }])[0]!.partNo).toBe(1)
  })
})

describe('scopeIds —— 与后端 ReportDraftService.scope_ids 同一口径', () => {
  it('空 = 全部纳入', () => {
    expect(scopeIds(ROWS, [])).toEqual(new Set([1, 2, 3, 4]))
  })

  it('只留纳入的表', () => {
    expect(scopeIds(ROWS, [1, 3])).toEqual(new Set([1, 2, 4]))
  })

  it('选中的表一张都不在了：按全部算，不让草稿整份变空', () => {
    expect(scopeIds(ROWS, [9])).toEqual(new Set([1, 2, 3, 4]))
  })
})

describe('toggleIncluded', () => {
  const ALL = [1, 2, 3]

  it('从「全部」里取消一张', () => {
    expect(toggleIncluded([], ALL, 2)).toEqual([1, 3])
  })

  it('重新勾满时存空（= 全部，后台日后加的表也自动纳入）', () => {
    expect(toggleIncluded([1, 3], ALL, 2)).toEqual([])
  })

  it('最后一张取消不掉', () => {
    expect(toggleIncluded([2], ALL, 2)).toBeNull()
  })

  it('isIncluded 与之一致', () => {
    expect(isIncluded([], ALL, 2)).toBe(true)
    expect(isIncluded([1, 3], ALL, 2)).toBe(false)
    expect(isIncluded([9], ALL, 2)).toBe(true)
  })
})

describe('countPlaceholders', () => {
  it('中英两种占位都认', () => {
    expect(countPlaceholders('随访【待补充：随访时长】，样本量【待补充】')).toBe(2)
    expect(countPlaceholders('Follow-up [to be completed: duration].')).toBe(1)
    expect(countPlaceholders('没有占位。')).toBe(0)
  })
})

describe('deliverChecks', () => {
  const base = { rows: ROWS, included: [] as number[], verdicts: [], checked: true, stale: false }

  it('占位、必填空着、已填却判未报告，各报各的', () => {
    const out = deliverChecks({
      ...base,
      body: { 1: '已写，但【待补充：剂量】', 3: '摘要已写' },
      verdicts: [{ itemId: 3, status: 'missing' }, { itemId: 4, status: 'missing' }],
    })
    expect(out).toEqual([
      { key: 'placeholder', count: 1, itemIds: [1] },
      // 4 号必填空着；它的「未报告」判定不再重复算进下一项
      { key: 'requiredBlank', count: 1, itemIds: [4] },
      { key: 'unreported', count: 1, itemIds: [3] },
    ])
  })

  it('没纳入的表不核对', () => {
    const out = deliverChecks({ ...base, included: [1], body: { 1: '已写' } })
    expect(out).toEqual([])
  })

  it('没检查过 / 检查已过时', () => {
    const body = { 1: 'a', 3: 'b', 4: 'c' }
    expect(deliverChecks({ ...base, body, checked: false }).map((c) => c.key)).toEqual(['notChecked'])
    expect(deliverChecks({ ...base, body, stale: true }).map((c) => c.key)).toEqual(['stale'])
  })
})
