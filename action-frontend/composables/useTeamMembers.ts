/**
 * 团队成员（国际顾问委员会 / 核心执行团队）的取数与类型。
 *
 * 数据源是后端 `action_team_member` 表，后台「团队成员管理」页可增删改，
 * 因此两个取数口都开 `swr` —— 不开就要等下一次 `npm run generate` 才看得见改动。
 *
 * 简介分三层，各用各的：
 *  - `summary*`      名单卡片上的一句话
 *  - `bio*`          详情页履历
 *  - `contribution*` 详情页「对 ACTION 的贡献」单独成块
 */

export interface TeamMemberRow {
  memberId: number
  /** board 国际顾问委员会 · core 核心执行团队 */
  groupKey: 'board' | 'core'
  nameZh: string | null
  nameEn: string | null
  /** 称谓（Prof./Dr.），与姓名分开存，便于排版 */
  honorific: string | null
  titleZh: string | null
  titleEn: string | null
  affiliationZh: string | null
  affiliationEn: string | null
  roleZh: string | null
  roleEn: string | null
  /** 研究方向标签：中文以顿号分隔，英文以分号分隔 */
  expertiseZh: string | null
  expertiseEn: string | null
  summaryZh: string | null
  summaryEn: string | null
  bioZh: string | null
  bioEn: string | null
  contributionZh: string | null
  contributionEn: string | null
  avatarUrl: string | null
  homepageUrl: string | null
  email: string | null
}

/**
 * 拼展示用的姓名。
 *
 * `Prof.` / `Dr.` 这类称谓是英文排版习惯，接在中文名前面（「Prof. 刘存志」）不合中文行文；
 * 中文里该由职称字段（教授 / 研究员，显示在姓名下一行）承担。
 * 但韩国籍成员在中文界面下仍显示罗马字姓名，那时称谓照旧要带上 ——
 * 所以判据是「这个名字是不是中日韩汉字」，而不是「当前是不是中文界面」。
 */
export function displayName(honorific: string | null, name: string): string {
  if (!name) return ''
  if (/[一-龥]/.test(name)) return name

  return honorific ? `${honorific} ${name}` : name
}

/**
 * 把 `expertise*` 拆成标签数组。
 *
 * 中英文分隔符不同（中文顿号 / 英文分号），且两边都可能夹杂逗号，这里一起吃掉；
 * 拆完去空、去重，避免录入时多打一个分隔符就多出一个空标签。
 */
export function splitExpertise(text: string): string[] {
  const parts = text
    .split(/[、;；,，]/)
    .map((s) => s.trim())
    .filter(Boolean)

  return [...new Set(parts)]
}
