import { describe, expect, it } from 'vitest'

import { groupKeyOf, groupRows, stepItem, type NavRowInput } from '../composables/checklistNav'

/**
 * 钉住第二步条目导航的分组口径：**按相邻的表 + 维度切组，不按名字去重**。
 * RCT 的 CONSORT 主表与 STRICTA 表都有「干预措施」这个维度，按名字合并会把两张表的
 * 条目混进一组、丢掉出处 —— 与 `checklistRows` 的 `showPart/showDomain` 规则必须一致。
 */
const row = (itemId: number, partTitle: string, domain: string, no = String(itemId), partNo?: number): NavRowInput => ({
  itemId,
  seq: itemId,
  no,
  text: `条目 ${no}`,
  partNo: partNo ?? (partTitle === 'STRICTA 表' ? 2 : 1),
  partTitle,
  domain,
  required: true,
})

const ROWS: NavRowInput[] = [
  row(1, 'CONSORT 主表', '题目与摘要', '1a'),
  row(2, 'CONSORT 主表', '题目与摘要', '1b'),
  row(3, 'CONSORT 主表', '干预措施', '5'),
  row(4, 'STRICTA 表', '干预措施', '2a'),
  row(5, 'STRICTA 表', '干预措施', '2b'),
]

describe('groupRows', () => {
  it('换维度才断组，同名维度跨表不合并', () => {
    const groups = groupRows(ROWS, {}, 100)

    expect(groups.map((g) => [g.partTitle, g.domain, g.items.length])).toEqual([
      ['CONSORT 主表', '题目与摘要', 2],
      ['CONSORT 主表', '干预措施', 1],
      ['STRICTA 表', '干预措施', 2],
    ])
  })

  it('只有每张表的第一组带表标题', () => {
    expect(groupRows(ROWS, {}, 100).map((g) => g.showPart)).toEqual([true, false, true])
  })

  it('换表看 partNo 不看表标题：同名表（修订版）不合并', () => {
    const rows = [row(1, '主表', '题目', '1', 1), row(2, '主表', '题目', '1', 2)]
    const groups = groupRows(rows, {}, 100)

    expect(groups).toHaveLength(2)
    expect(groups.map((g) => g.showPart)).toEqual([true, true])
  })

  it('组 key 取组内首条 itemId，跨表同名维度也不撞', () => {
    const keys = groupRows(ROWS, {}, 100).map((g) => g.key)

    expect(keys).toEqual(['1', '3', '4'])
    expect(new Set(keys).size).toBe(keys.length)
  })

  it('已填计数只算非空白正文；超长单独标 over', () => {
    const groups = groupRows(ROWS, { 1: '写了', 2: '   ', 3: 'x'.repeat(101) }, 100)

    expect(groups[0]!.filled).toBe(1)
    expect(groups[0]!.total).toBe(2)
    expect(groups[0]!.items.map((it) => it.filled)).toEqual([true, false])
    expect(groups[1]!.items[0]!.over).toBe(true)
    expect(groups[1]!.items[0]!.filled).toBe(true)
  })

  it('空清单返回空数组', () => {
    expect(groupRows([], {}, 100)).toEqual([])
  })
})

describe('groupKeyOf', () => {
  it('找到条目所在组', () => {
    const groups = groupRows(ROWS, {}, 100)

    expect(groupKeyOf(groups, 5)).toBe('4')
    expect(groupKeyOf(groups, 99)).toBeNull()
    expect(groupKeyOf(groups, null)).toBeNull()
  })
})

describe('stepItem', () => {
  it('按流水顺序前进/后退', () => {
    expect(stepItem(ROWS, 3, 1)).toBe(4)
    expect(stepItem(ROWS, 3, -1)).toBe(2)
  })

  it('撞到首/末条返回 null，不绕回另一头', () => {
    expect(stepItem(ROWS, 1, -1)).toBeNull()
    expect(stepItem(ROWS, 5, 1)).toBeNull()
  })

  it('当前条目不在清单里时向前取首条、向后取末条', () => {
    expect(stepItem(ROWS, null, 1)).toBe(1)
    expect(stepItem(ROWS, 99, -1)).toBe(5)
  })

  it('空清单返回 null', () => {
    expect(stepItem([], 1, 1)).toBeNull()
  })
})
