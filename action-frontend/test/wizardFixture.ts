/** 分支问卷测试夹具（不是 spec，被 studyWizard / wizardQuery 两份 spec 共用） */
import type { WizardOption, WizardQuestion } from '../composables/studyWizard'

export const o = (optKey: string, next: number | null = null, res = ''): WizardOption => ({
  optKey, labelZh: optKey, labelEn: optKey, nextQuestionId: next, resultTypeKey: res, tipZh: '', tipEn: '',
})
export const q = (questionId: number, qKey: string, options: WizardOption[], root = false): WizardQuestion => ({
  questionId, qKey, textZh: qKey, textEn: qKey, isRoot: root ? '1' : '0', options,
})

/** 与 sql/041 同构：《ACTION智能匹配研究类型.docx》的分支逻辑 */
export const DOC_TREE: WizardQuestion[] = [
  q(1, 'type', [
    o('A', 2), o('B', null, 'case'), o('C', 4), o('D', 5), o('E', 6),
    o('F', null, 'animal'), o('G', null, 'guideline'),
  ], true),
  q(2, 'randomized', [o('y', 3), o('n', null, 'nrct')]),
  q(3, 'sham', [o('y', null, 'rct'), o('n', null, 'rct')]),
  q(4, 'meta', [o('y', null, 'sr'), o('n', null, 'sr_narrative')]),
  q(5, 'obs_design', [o('cohort', null, 'cohort'), o('case_control', null, 'case_control'), o('cross_sectional', null, 'cross_sectional')]),
  q(6, 'protocol_main', [o('trial', null, 'protocol'), o('obs', null, 'protocol_obs')]),
]
