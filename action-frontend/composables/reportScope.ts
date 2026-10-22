/**
 * 报告助手「纳入哪几张清单表」与「交付前核对」的纯函数 —— 不认识 Vue，`test/reportScope.spec.ts` 钉住。
 *
 * 一份规范可能含多张清单表（RCT = CONSORT 主表 + 摘要表 + STRICTA 表，`partNo` 区分）。
 * 第二步按表切换、可以取消纳入某张：没纳入的表不计完成度、不进检查与优化、不进导出，
 * **但正文照存**，重新勾上时都还在。
 *
 * 纳入范围的口径与后端 `ReportDraftService.scope_ids` 逐字一致：**空 = 全部纳入**；
 * 选中的表一张都不在了（后台删了表）也按全部算 —— 两边不一致的话，前端的完成度与
 * 后端检查的条目数会对不上，而用户看不出是哪边错了。
 */

/** 一张清单表 */
export interface PartInfo {
  partNo: number
  title: string
  /** 条目数 */
  total: number
  /** 必填条目数 */
  required: number
}

/** 分组只依赖这几个字段 */
export interface ScopeRow {
  itemId: number
  partNo: number | null
  partTitle: string
  required: boolean
}

/** part_no 为空按 1 算，与库里列的 server_default 一致 */
export const partOf = (row: { partNo: number | null }): number => row.partNo || 1

/**
 * 清单 → 清单表列表，表的先后取条目里首次出现的顺序（条目已按 sortNum 排好）
 *
 * 按 `partNo` 分，不按标题 —— 后台新加一张同名的表（修订版）时标题会撞、序号不会。
 */
export function listParts(rows: readonly ScopeRow[]): PartInfo[] {
  const map = new Map<number, PartInfo>()
  for (const row of rows) {
    const no = partOf(row)
    let part = map.get(no)
    if (!part) {
      part = { partNo: no, title: row.partTitle, total: 0, required: 0 }
      map.set(no, part)
    }
    part.total += 1
    if (row.required) part.required += 1
  }

  return [...map.values()]
}

/**
 * 纳入范围内的条目id
 *
 * @param rows 清单
 * @param included 纳入的 partNo；空 = 全部
 */
export function scopeIds(rows: readonly ScopeRow[], included: readonly number[]): Set<number> {
  if (included.length) {
    const wanted = new Set(included)
    const chosen = rows.filter((r) => wanted.has(partOf(r))).map((r) => r.itemId)
    if (chosen.length) return new Set(chosen)
  }

  return new Set(rows.map((r) => r.itemId))
}

/**
 * 勾选 / 取消某张表之后的纳入范围
 *
 * **选满了存空**（= 全部纳入），与后端 `_normalize_parts` 同一口径。至少留一张：
 * 最后一张取消不掉，返回 null 让调用方提示。
 *
 * @param included 当前纳入的 partNo（空 = 全部）
 * @param available 规范里全部的 partNo
 * @param partNo 这次点的那张
 * @returns 新的纳入范围；取消的是最后一张时为 null
 */
export function toggleIncluded(included: readonly number[], available: readonly number[], partNo: number): number[] | null {
  const current = new Set(included.length ? included.filter((p) => available.includes(p)) : available)
  if (!current.size) available.forEach((p) => current.add(p))
  if (current.has(partNo)) current.delete(partNo)
  else current.add(partNo)
  if (!current.size) return null
  if (available.every((p) => current.has(p))) return []

  return [...current].sort((a, b) => a - b)
}

/** 某张表是否纳入 */
export function isIncluded(included: readonly number[], available: readonly number[], partNo: number): boolean {
  if (!included.length) return true
  // 选中的表全都不在了 —— 与 scopeIds 一样按全部纳入算
  if (!included.some((p) => available.includes(p))) return true

  return included.includes(partNo)
}

/**
 * 正文里的待补充占位：AI 完善与合成初稿都用它标「条目要求需要、但作者没提供」的内容。
 * 中英两种写法都认（英文界面下模型写的是 `[to be completed: …]`）
 */
const PLACEHOLDER_RE = /【待补充[^】]*】|\[to be completed[^\]]*\]/gi

/** 一段正文里有几处待补充占位 */
export function countPlaceholders(text: string): number {
  return text.match(PLACEHOLDER_RE)?.length ?? 0
}

/** 第五步交付前核对里的一项。`itemIds` 非空时页面给「定位」，点了去对应条目 */
export interface DeliverCheck {
  key: 'placeholder' | 'requiredBlank' | 'notChecked' | 'stale' | 'unreported'
  count: number
  itemIds: number[]
}

/** 交付前核对的输入 */
export interface DeliverInput {
  rows: readonly ScopeRow[]
  included: readonly number[]
  body: Readonly<Record<number, string | undefined>>
  /** 最近一次检查的逐条判定（只有纳入范围内的条目） */
  verdicts: readonly { itemId: number; status: string }[]
  /** 跑过检查没有 */
  checked: boolean
  /** 检查之后又改过稿子 */
  stale: boolean
}

/**
 * 交付前核对：**只提醒，不拦导出**（甲方定稿）。
 *
 * 顺序就是严重程度：占位会原样进 Word、必填空着、判了「未报告」的已填条目、没检查过 / 检查已过时。
 * 「判了未报告」只算**已填**的那些 —— 空着的必填条目已经在上一项里了，再算一遍是重复。
 *
 * @returns 只含 count > 0 的项
 */
export function deliverChecks(input: DeliverInput): DeliverCheck[] {
  const scope = scopeIds(input.rows, input.included)
  const rows = input.rows.filter((r) => scope.has(r.itemId))
  const text = (id: number) => (input.body[id] ?? '').trim()

  const placeholderIds = rows.filter((r) => countPlaceholders(text(r.itemId)) > 0).map((r) => r.itemId)
  const placeholderN = rows.reduce((n, r) => n + countPlaceholders(text(r.itemId)), 0)
  const blankIds = rows.filter((r) => r.required && !text(r.itemId)).map((r) => r.itemId)
  const unreportedIds = input.verdicts
    .filter((v) => v.status === 'missing' && scope.has(v.itemId) && text(v.itemId))
    .map((v) => v.itemId)

  const out: DeliverCheck[] = [
    { key: 'placeholder', count: placeholderN, itemIds: placeholderIds },
    { key: 'requiredBlank', count: blankIds.length, itemIds: blankIds },
    { key: 'unreported', count: unreportedIds.length, itemIds: unreportedIds },
  ]
  if (!input.checked) out.push({ key: 'notChecked', count: 1, itemIds: [] })
  else if (input.stale) out.push({ key: 'stale', count: 1, itemIds: [] })

  return out.filter((c) => c.count > 0)
}
