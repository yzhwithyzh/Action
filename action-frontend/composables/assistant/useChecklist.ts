/**
 * 第一步匹配到的那份规范的真实 checklist 条目 —— 第二步撰写、第三步检查、第四步优化的唯一数据源。
 *
 * 条目存在 action_guideline_item，由 tools/extract_checklists.py 从各规范的中英文版
 * docx 抽取入库，后台「规范条目管理」页面可增删改。
 *
 * 一份规范可能含多张清单表（RCT = CONSORT 主表 + 摘要表 + STRICTA 表），`partNo` 区分。
 * 2026-10 起第二步按表切换（`parts`），不再拼成一条流水清单 —— 投稿时它们本来就是分开交的几张表。
 *
 * 请求同样不在这里 await，理由见 `useAssistantWizard` 的文件头。
 */

import type { Ref } from 'vue'
import { listParts } from '~/composables/reportScope'

export interface ChecklistItem {
  itemId: number
  partNo: number | null
  partZh: string | null
  partEn: string | null
  domainZh: string | null
  domainEn: string | null
  itemNoZh: string | null
  itemNoEn: string | null
  contentZh: string | null
  contentEn: string | null
  extLabelZh: string | null
  extLabelEn: string | null
  extensionZh: string | null
  extensionEn: string | null
  /** 条目示例：后台「规范条目管理」逐条录入（sql/035），为空即「暂无示例」，不由模型生成 */
  exampleZh: string | null
  exampleEn: string | null
  /** 填写要求：'0' 必填 / '1' 条件填写。库里由 sql/007 的关键词启发式回填，后台可逐条改 */
  requireLevel: string | null
}

/** 原表用「—」表示该条无对应内容（如 CONSORT 无此条、只有针刺扩展有） */
const DASH = /^[—–-]+$/
const hasText = (s: string) => Boolean(s.trim()) && !DASH.test(s.trim())

export function useChecklist(code: Ref<string>) {
  const { pick } = useBilingual()

  const req = useSiteObject<ChecklistItem[]>(
    '/guideline-items',
    'assistant-checklist',
    { query: () => ({ guidelineCode: code.value }) },
  )
  const checklist = computed<ChecklistItem[]>(() => req.data.value?.data ?? [])
  const ckLoading = computed(() => req.status.value === 'pending')

  /**
   * 条目行：整体按 sortNum 顺序排开（DAO 已排好），每行带上所在清单表与维度。
   * `seq` 是全清单的流水号，只在条目没有编号时兜底显示。
   */
  const checklistRows = computed(() =>
    checklist.value.map((it, i) => {
      const r = it as unknown as Record<string, unknown>
      const content = pick(r, 'content')
      const ext = pick(r, 'extension')
      const example = pick(r, 'example')
      // 正文是「—」而扩展有内容时，扩展就是这条的正文（CONSORT 非药物扩展里的新增条目）
      const extOnly = !hasText(content) && hasText(ext)

      return {
        key: it.itemId,
        seq: i + 1,
        partNo: it.partNo || 1,
        partTitle: pick(r, 'part'),
        domain: pick(r, 'domain'),
        no: pick(r, 'itemNo'),
        text: extOnly ? ext : content,
        extLabel: pick(r, 'extLabel'),
        ext: extOnly ? '' : (hasText(ext) ? ext : ''),
        isExt: extOnly,
        // 「—」与 extension 同一套约定：后台可能照着旁边那栏的习惯填个横线表示无
        example: hasText(example) ? example : '',
        itemId: it.itemId,
        required: (it.requireLevel ?? '0') === '0',
      }
    }),
  )

  /** 清单表列表（标题、条目数、必填数），第二步的表页签由它画 */
  const checklistParts = computed(() => listParts(checklistRows.value))
  const partNos = computed(() => checklistParts.value.map((p) => p.partNo))

  /** 条目 id → 行 */
  const rowById = computed(() => new Map(checklistRows.value.map((r) => [r.itemId, r])))

  /**
   * 匹配到的规范一条 checklist 条目都没有（眼下 STROBE 是 0 条 —— 仓库里没有它的中英素材）。
   * 后端提交口本来就会回绝，但条目数第二步就摆在眼前，没理由让人点了才知道。
   */
  const noItems = computed(() => Boolean(code.value) && !ckLoading.value && checklist.value.length === 0)

  return {
    ready: req,
    checklist,
    ckLoading,
    checklistRows,
    checklistParts,
    partNos,
    rowById,
    noItems,
  }
}

export type ChecklistRow = ReturnType<typeof useChecklist>['checklistRows']['value'][number]
