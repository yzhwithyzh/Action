/**
 * 稿件行号的编法 —— 与 checklist worker 的 `engine/audit.py::number_lines` 逐字对齐。
 *
 * ## 为什么这必须是一份独立的、被测试钉住的实现
 *
 * 第三步的判定里，「报告于第 12 行」这个行号是模型定位证据的唯一锚点，也是用户人工复核时
 * 唯一能顺着回到原文的线索。而 worker 那边的编号规则有一条**极容易被漏掉的特例**：
 *
 *     空行原样输出，但**不占行号**。
 *
 * 也就是说模型看到的、返回的「第 8 行」，是第 8 个**非空**行，不是第 8 个物理行。
 * 前端若照着 `text.split('\n')` 顺序编号，从稿件里第一个空行之后就全线错位 ——
 * 而错位的表现极其温和：行号仍然落在合法范围内、面板照常滚过去、高亮照常亮起，
 * 只是**指着一段不相干的话**。实测一份 2193 字的稿件：物理 77 行 / 有效 39 行，
 * 判定说的第 8 行在物理编号下是一个空行。
 *
 * 所以这份实现要跟着引擎走，且两边任何一边改了编号规则都得同步 ——
 * `test/manuscriptLines.spec.ts` 用引擎的行为反过来钉住这里。
 *
 * ## 与 Python 的两处对齐细节
 *
 * ① **换行符集合**照 `str.splitlines()` 来，不是只认 `\n`。Python 会在 `\v` `\f` `\x1c`
 *    `\x85` ` ` 等处断行，而从 PDF / Word 粘出来的稿件里 `\f`（分页符）相当常见 ——
 *    只认 `\n` 的话，遇上一个分页符后面所有行号就整体偏移。
 * ② **`rstrip()` 后再判空**，与引擎一致：只含空格的行算空行、不占号。
 */

/** 一个显示行。`no` 为 null 表示空行 —— 它占一行位置，但不占行号 */
export interface SourceLine {
  no: number | null
  text: string
}

/**
 * Python `str.splitlines()` 的断行字符集。
 *
 * `\r\n` 放在最前先匹配，避免被拆成两次断行多出一个空行（多出来的是空行、不占号，
 * 所以不影响行号，但会让面板凭空多出一堆空行）。
 *
 * **分隔符一律写成 `\uXXXX` 转义，别贴字面量** —— U+2028 / U+2029 本身就是 JS 源码里的
 * 行终止符，直接贴进正则字面量会当场把它截断（踩过：整个模块编译不过，报
 * "Unterminated regular expression"）。
 */
const LINE_BREAK = /\r\n|[\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029]/

/**
 * 按 worker 的规则给稿件编行号
 *
 * @param text 稿件全文
 * @returns 显示行列表，空行的 `no` 为 null
 */
export function numberManuscriptLines(text: string): SourceLine[] {
  if (!text) return []
  const out: SourceLine[] = []
  let no = 0
  for (const raw of text.split(LINE_BREAK)) {
    // 与引擎的 `line = raw.rstrip()` 对齐
    const line = raw.replace(/\s+$/u, '')
    if (!line.trim()) {
      out.push({ no: null, text: '' })
      continue
    }
    no += 1
    out.push({ no, text: line })
  }

  return out
}

/**
 * 有效行数（即引擎返回的 `lineCount`）
 *
 * @param lines 已编号的显示行
 * @returns 非空行的条数
 */
export function countNumberedLines(lines: SourceLine[]): number {
  return lines.reduce((n, l) => (l.no === null ? n : n + 1), 0)
}
