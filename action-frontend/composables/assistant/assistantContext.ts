/**
 * 报告助手五个步骤组件共用的那一份状态（`provide` 在 `pages/assistant.vue`，`inject` 在各 Step 组件）。
 *
 * 包成 `reactive` 再往下传：里面的 ref / computed 自动解包，组件模板里直接写 `ctx.body[id]`、
 * `ctx.step`，`v-model` 也照常工作。函数原样透传。
 */

import type { InjectionKey, UnwrapNestedRefs } from 'vue'
import type { useAssistantWizard } from './useAssistantWizard'
import type { useChecklist } from './useChecklist'
import type { ReportWorkspace } from './useReportWorkspace'

type Wizard = Omit<ReturnType<typeof useAssistantWizard>, 'ready'>
type Checklist = Omit<ReturnType<typeof useChecklist>, 'ready'>

export type AssistantCtx = UnwrapNestedRefs<Wizard & Checklist & ReportWorkspace>

export const ASSISTANT_CTX: InjectionKey<AssistantCtx> = Symbol('assistant-ctx')

/** 组件里取上下文。拿不到说明组件被用在了报告助手页之外，直接报错比静默空白好查 */
export function useAssistantCtx(): AssistantCtx {
  const ctx = inject(ASSISTANT_CTX)
  if (!ctx) throw new Error('useAssistantCtx() 只能在报告助手页的步骤组件里调用')

  return ctx
}
