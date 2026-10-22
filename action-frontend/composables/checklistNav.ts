/**
 * 报告助手第二步「条目导航」的分组与步进 —— 纯函数，不认识 Vue，`test/checklistNav.spec.ts` 钉住。
 *
 * 第二步的清单区是「左导航 + 右面板」：左边按 清单表 → 维度 折叠，一次只展开右边那一条。
 * 分组口径**照抄** `checklistRows` 里 `showPart` / `showDomain` 那套「换表、换维度才断开」的规则：
 * 换表看 `partNo` 不看表标题 —— 后台新加一张同名的表（修订版）时标题会撞、序号不会；
 * 同一个维度名在两张清单表里各出现一次（CONSORT 主表与 STRICTA 表都有「干预措施」），
 * 按名字合并会把两张表的条目混进一组，条目出处就丢了。所以这里按**相邻**分组，不按名字去重。
 *
 * 导航上每条带两个状态点：`filled`（正文非空）与 `over`（超过单条上限）。后者要单独标出来 ——
 * 后端对超长只回一句字段级 422、不指明是几十条里的哪一条，导航上不标红的话用户得逐条翻。
 */

/** 分组只依赖这几个字段；`checklistRows` 的行是它的超集 */
export interface NavRowInput {
  itemId: number
  seq: number
  no: string
  text: string
  partNo: number | null
  partTitle: string
  domain: string
  required: boolean
}

export interface NavItem extends NavRowInput {
  filled: boolean
  over: boolean
}

export interface NavGroup {
  /** 组内首条的 itemId，稳定且唯一（同名维度跨表出现时也不会撞） */
  key: string
  /** 这一组是否是所属清单表的第一组 —— 导航上在它前面插一条表标题 */
  showPart: boolean
  partTitle: string
  domain: string
  items: NavItem[]
  filled: number
  total: number
}

/**
 * 把流水清单按「相邻的表 + 维度」切成折叠组
 *
 * @param rows 流水清单（已按 sortNum 排好）
 * @param body 编辑态正文，itemId → 文本
 * @param maxChars 单条上限，超过的条目标 `over`
 */
export function groupRows(
  rows: readonly NavRowInput[],
  body: Readonly<Record<number, string | undefined>>,
  maxChars: number,
): NavGroup[] {
  const groups: NavGroup[] = []
  let prev: NavRowInput | undefined

  for (const row of rows) {
    const partChanged = !prev || prev.partNo !== row.partNo
    const domainChanged = partChanged || prev!.domain !== row.domain
    if (domainChanged || !groups.length) {
      groups.push({
        key: String(row.itemId),
        showPart: partChanged,
        partTitle: row.partTitle,
        domain: row.domain,
        items: [],
        filled: 0,
        total: 0,
      })
    }
    const text = body[row.itemId] ?? ''
    const filled = text.trim().length > 0
    const group = groups[groups.length - 1]!
    group.items.push({ ...row, filled, over: text.length > maxChars })
    group.total += 1
    if (filled) group.filled += 1
    prev = row
  }

  return groups
}

/**
 * 当前条目所在组的 key；不在清单里返回 null
 */
export function groupKeyOf(groups: readonly NavGroup[], itemId: number | null): string | null {
  if (itemId == null) return null
  for (const g of groups) {
    if (g.items.some((it) => it.itemId === itemId)) return g.key
  }

  return null
}

/**
 * 按流水顺序前进/后退一条，撞到首/末条返回 null —— 调用方据此禁用按钮，而不是绕回另一头
 *
 * `currentId` 不在清单里（换了规范、条目被停用）时：向前取首条、向后取末条，让按钮总有出路。
 */
export function stepItem(rows: readonly NavRowInput[], currentId: number | null, delta: 1 | -1): number | null {
  if (!rows.length) return null
  const idx = currentId == null ? -1 : rows.findIndex((r) => r.itemId === currentId)
  if (idx < 0) return (delta > 0 ? rows[0] : rows[rows.length - 1])!.itemId
  const next = idx + delta
  if (next < 0 || next >= rows.length) return null

  return rows[next]!.itemId
}
