import { describe, expect, it } from 'vitest'

import { countNumberedLines, numberManuscriptLines } from '../composables/manuscriptLines'

/**
 * 这组测试钉的是**前端与 checklist worker 对「第 N 行」的理解一致**。
 *
 * 不一致的后果不是报错，是**静默指错地方**：判定说「报告于第 8 行」，面板照常滚过去、
 * 照常高亮，只是那一行讲的是别的事。用户拿它去核稿，核到的是错的。
 *
 * 对照实现：`action-backend/tools/checklist_worker_tool/engine/audit.py::number_lines`
 */
describe('numberManuscriptLines', () => {
  it('空行占位置但不占行号', () => {
    // 引擎：空行 append('') 且 no 不递增
    const lines = numberManuscriptLines('第一行\n\n第三行')

    expect(lines.map((l) => l.no)).toEqual([1, null, 2])
    expect(countNumberedLines(lines)).toBe(2)
  })

  it('只含空白的行也算空行', () => {
    // 引擎先 rstrip 再判 strip()，所以「   」是空行
    const lines = numberManuscriptLines('甲\n   \n乙')

    expect(lines.map((l) => l.no)).toEqual([1, null, 2])
  })

  it('行尾空白被裁掉', () => {
    expect(numberManuscriptLines('结论。   ')[0]?.text).toBe('结论。')
  })

  it('CRLF 只断一次行，不多出空行', () => {
    // 拆成 \r + \n 会凭空多出一堆空行，行号虽不受影响，但面板会被撑开一倍
    const lines = numberManuscriptLines('甲\r\n乙\r\n丙')

    expect(lines).toHaveLength(3)
    expect(lines.map((l) => l.no)).toEqual([1, 2, 3])
  })

  it('认 Python splitlines 的其余断行符', () => {
    // 从 PDF / Word 粘出来的稿件里 \f（分页符）很常见；只认 \n 的话
    // 引擎在这里断了行而前端没断，后面所有行号整体偏移
    const lines = numberManuscriptLines('甲\f乙\v丙')

    expect(lines.map((l) => l.text)).toEqual(['甲', '乙', '丙'])
    expect(lines.map((l) => l.no)).toEqual([1, 2, 3])
  })

  it('行号是「第几个非空行」，不是「第几个物理行」', () => {
    // 这条是整份文件存在的理由。四个空行之后，物理第 6 行 = 有效第 2 行
    const lines = numberManuscriptLines('标题\n\n\n\n\n正文')
    const numbered = lines.find((l) => l.text === '正文')

    expect(numbered?.no).toBe(2)
    expect(lines).toHaveLength(6)
  })

  it('空稿件返回空列表', () => {
    expect(numberManuscriptLines('')).toEqual([])
  })

  it('countNumberedLines 与引擎的 lineCount 同义', () => {
    // 引擎返回的 line_count 就是最后那个 no
    const text = '一\n\n二\n   \n三\n'
    const lines = numberManuscriptLines(text)
    const last = [...lines].reverse().find((l) => l.no !== null)

    expect(countNumberedLines(lines)).toBe(last?.no)
    expect(countNumberedLines(lines)).toBe(3)
  })
})
