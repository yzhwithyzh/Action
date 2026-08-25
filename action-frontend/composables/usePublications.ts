/**
 * 成果发表的类型与共用小工具。
 *
 * 列表页 `pages/publications.vue` 与详情页 `pages/publication/[id].vue` 用的是同一张
 * `action_publication` 表，字段定义只放这一份 —— 两处各抄一份 interface，
 * 后台加一个字段就会有一边悄悄漏掉（同 `useGuidelines.ts`）。
 *
 * **这些字段没有 `*Zh`/`*En` 双语版，所以不要拿 `pick()` 去取。** 标题、作者、期刊、
 * 摘要都是发表原文，同时也是引用信息，中英两种界面显示的都是它；
 * 页面上的栏目标题与按钮字才走 i18n（同 `pages/srd.vue` 的「原文引用」列）。
 */

export interface PublicationAuthor {
  name: string
  /** 所属机构在 affiliations 里的下标；未标注时为 null（不是 0，0 是第一家单位） */
  affiliationIndex: number | null
}

export interface PublicationRow {
  publicationId: number
  title: string
  authors: PublicationAuthor[] | null
  affiliations: string[] | null
  keywords: string[] | null
  journal: string | null
  volume: string | null
  issue: string | null
  pages: string | null
  publicationYear: number | null
  doi: string | null
  sourceUrl: string | null
  pdfUrl: string | null
  coverImageUrl: string | null
  /** 以下两项**只有详情接口才返回** —— 列表接口刻意不吐，见后端 PublicationService._LIST_OMIT */
  abstract?: string | null
  citationText?: string | null
}

/** 列表里作者一行最多列几位，超出写 et al. */
const AUTHOR_LIMIT = 8

export function usePublications() {
  /**
   * 作者一行：`Zhang San, Li Si, … et al.`
   *
   * 顺序即署名顺序，**不排序、不去重**。
   *
   * @param authors 作者列表
   * @param limit 最多列几位
   * @return 拼好的一行；没有作者时空串
   */
  const authorLine = (authors: PublicationAuthor[] | null | undefined, limit = AUTHOR_LIMIT): string => {
    const names = (authors ?? []).map((a) => a?.name).filter(Boolean)
    if (!names.length) return ''

    return names.slice(0, limit).join(', ') + (names.length > limit ? ', et al.' : '')
  }

  /**
   * 出处一行：`Journal, 80(3):145-152, 2024`
   *
   * 缺哪一截就不写哪一截 —— 预印本没有卷期页，会议摘要连期刊名都没有。
   *
   * @param row 一条成果
   * @return 拼好的一行；一个字段都没有时空串
   */
  const citeLine = (row: PublicationRow | null | undefined): string => {
    if (!row) return ''
    const parts: string[] = []
    if (row.journal) parts.push(row.journal)
    if (row.volume) parts.push(`${row.volume}${row.issue ? `(${row.issue})` : ''}${row.pages ? `:${row.pages}` : ''}`)
    else if (row.pages) parts.push(row.pages)
    if (row.publicationYear) parts.push(String(row.publicationYear))

    return parts.join(', ')
  }

  return { authorLine, citeLine }
}
