/**
 * 报告规范目录的类型与共用小工具。
 *
 * 目录页 `pages/guidelines.vue`（分类导航）与原文阅读页 `pages/guideline/[id].vue`
 * 用的是同一张 `action_guideline` 表，字段定义只放这一份 ——
 * 两处各抄一份 interface，后台加一个字段就会有一边悄悄漏掉。
 */

export interface GuidelineRow {
  guidelineId: number
  code: string
  nameZh: string | null
  nameEn: string | null
  /** 研究设计标识，取值域是 action_guideline_category.catKey */
  studyType: string | null
  summaryZh: string | null
  summaryEn: string | null
  /** 展示用版本号（「2010 修订 · 6 领域 / 17 条目」），取值走 pick()，en 为空回落 zh */
  versionZh: string | null
  versionEn: string | null
  /** 中英文原文 PDF 的 OSS 公网直链 */
  fileUrlZh: string | null
  fileUrlEn: string | null
  /** 原文出处（期刊 / 官网），外链 */
  externalUrl: string | null
  logoUrl: string | null
  releaseState: 'open' | 'beta' | 'soon' | null
}

/** 研究设计分类（筛选条一格一条），来自 action_guideline_category */
export interface GuidelineCategoryRow {
  catId: number
  catKey: string
  nameZh: string | null
  nameEn: string | null
  iconPaths: string | null
}

/**
 * 分类图标：`icon_paths` 是一行一条 SVG path 的 d 属性，留空则不画。
 *
 * @param cat 分类，可为空（规范未归类或分类已停用）
 * @return path 的 d 值数组
 */
export function categoryIconPaths(cat: GuidelineCategoryRow | undefined | null): string[] {
  return (cat?.iconPaths ?? '').split('\n').map((d) => d.trim()).filter(Boolean)
}
