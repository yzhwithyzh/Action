<script setup lang="ts">
/**
 * 报告助手：① 立项匹配 → ② 报告撰写 → ③ 合规与一致性检查 → ④ AI 优化 → ⑤ 成果交付。
 *
 * 这个文件只是骨架：步骤条、五个面板、底部的上一步 / 下一步。
 * 状态在 `composables/assistant/`（问卷 · 清单 · 工作区三块），经 `provide` 交给
 * `components/assistant/Step*.vue` —— ③ 的判定要挂回 ② 的导航、④ 写回的正文 ② 要看得见、
 * ⑤ 的核对要读前面每一步的结果，它们本来就是一份状态。
 *
 * **两次 await 的顺序不能换**：第二步取哪份 checklist 由第一步的问卷判定决定，预渲染时
 * 先取 checklist 的话那次请求带的是空代号，烤进 HTML 的就是一份空清单。工作区必须在两次
 * await 之后同步创建 —— 它注册的生命周期钩子要挂在当前组件实例上。
 */
import { ASSISTANT_CTX } from '~/composables/assistant/assistantContext'
import { useAssistantWizard } from '~/composables/assistant/useAssistantWizard'
import { useChecklist } from '~/composables/assistant/useChecklist'
import { useReportWorkspace } from '~/composables/assistant/useReportWorkspace'
import { WIZARD_STEP_COUNT } from '~/composables/wizardQuery'
import StepCheck from '~/components/assistant/StepCheck.vue'
import StepDeliver from '~/components/assistant/StepDeliver.vue'
import StepMatch from '~/components/assistant/StepMatch.vue'
import StepRefine from '~/components/assistant/StepRefine.vue'
import StepWrite from '~/components/assistant/StepWrite.vue'

const { t } = useI18n()

// 用 getter：切换语言后标签页标题与 description 跟着换，不停在进入页面时的语言
useHead({
  title: () => t('assistant._title'),
  meta: [{ name: 'description', content: () => t('assistant._desc') }],
})

const { ready: wizardReady, ...wizard } = useAssistantWizard()
await wizardReady
const { ready: checklistReady, ...checklist } = useChecklist(wizard.checklistCode)
await checklistReady
const ws = useReportWorkspace(wizard, checklist)

provide(ASSISTANT_CTX, reactive({ ...wizard, ...checklist, ...ws }))

const { step, go, wizardEl, draftErr } = ws

/** 步骤条：标题与副标题的 i18n 键。① ② ⑤ 沿用原有键（后台改过的文案照样生效） */
const STEPS = [
  { n: 1, b: 'assistant.s002', s: 'assistant.s003' },
  { n: 2, b: 'assistant.s004', s: 'assistant.s005' },
  { n: 3, b: 'assistant.stepCheck', s: 'assistant.stepCheckSub' },
  { n: 4, b: 'assistant.stepRefine', s: 'assistant.stepRefineSub' },
  { n: 5, b: 'assistant.s010', s: 'assistant.s011' },
] as const

useReveal()
</script>

<template>
  <div class="page-assistant">
    <section class="wz" id="wizard">
      <div class="wrap">
        <span class="kicker reveal">{{ t('assistant.s001') }}</span>

        <!-- 步骤条：每一步都点得进去，不强制按顺序走 -->
        <div id="stepper" ref="wizardEl" class="stepper" role="tablist" :aria-label="t('assistant.wizardAria')">
          <button
            v-for="s in STEPS"
            :key="s.n"
            class="step"
            :class="{ on: step === s.n, done: step > s.n }"
            :data-step="s.n"
            role="tab"
            :aria-selected="step === s.n"
            @click="go(s.n)"
          >
            <span class="sn">{{ s.n }}</span>
            <span class="stx"><b>{{ t(s.b) }}</b><span>{{ t(s.s) }}</span></span>
          </button>
        </div>

        <!-- 保存 / 合成失败的报错原先只在第二步面板里显示，在 ③④⑤ 点按钮时它会先存一次，
             存失败就静默返回 —— 表现是「点了没反应」。在别的步骤里也把它摆出来 -->
        <p v-if="draftErr && step !== 2" class="rv-err" role="alert">{{ draftErr }}</p>

        <StepMatch />
        <StepWrite />
        <StepCheck />
        <StepRefine />
        <StepDeliver />

        <!-- 向导底部导航 -->
        <div class="wz-nav">
          <span class="wz-prog"><span>{{ t('assistant.s120') }}</span> <b id="curStep">{{ step }}</b> / {{ WIZARD_STEP_COUNT }} <span>{{ t('assistant.s121') }}</span></span>
          <div class="wz-btns">
            <button id="prevBtn" class="btn btn-ghost" :disabled="step === 1" @click="go(step - 1)">{{ t('assistant.s122') }}</button>
            <button id="nextBtn" class="btn btn-primary" :disabled="step === WIZARD_STEP_COUNT" @click="go(step + 1)">{{ t('assistant.nextStep') }} <span class="arrow" aria-hidden="true">→</span></button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style>
.page-assistant .btn{display:inline-flex;align-items:center;justify-content:center;gap:9px;padding:13px 24px;border-radius:999px;font-weight:600;font-size:15px;border:1.5px solid transparent;cursor:pointer;white-space:nowrap;transition:transform .25s var(--ease),background-color .25s var(--ease),box-shadow .25s var(--ease),border-color .25s var(--ease)}
.page-assistant .btn-primary:disabled{background:var(--indigo-300);box-shadow:none;cursor:not-allowed;transform:none}
.page-assistant .btn-ghost:disabled{opacity:.45;cursor:not-allowed}
.page-assistant .wz{padding:clamp(34px,5vw,60px) 0}
.page-assistant .stepper{display:flex;gap:6px;background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:10px;overflow-x:auto;scrollbar-width:none}
.page-assistant .stepper::-webkit-scrollbar{display:none}
.page-assistant .step{flex:1;min-width:150px;display:flex;align-items:center;gap:11px;padding:12px 14px;border-radius:12px;cursor:pointer;background:transparent;border:none;font-family:inherit;text-align:left;transition:background .2s}
.page-assistant .step:hover{background:var(--paper-2)}
.page-assistant .step.on{background:var(--indigo-100)}
.page-assistant .step .sn{width:30px;height:30px;flex-shrink:0;border-radius:var(--radius-sm);background:var(--paper-2);color:var(--muted);display:flex;align-items:center;justify-content:center;font-family:"Spectral",serif;font-weight:700;font-size:15px;transition:.2s}
.page-assistant .step.on .sn{background:var(--cinnabar);color:#fff}
.page-assistant .step.done .sn{background:var(--indigo-600);color:#fff}
.page-assistant .step .stx{min-width:0}
.page-assistant .step .stx b{display:block;font-size:13.5px;font-weight:700;color:var(--indigo-900);font-family:"Source Sans 3","Noto Sans SC",sans-serif;line-height:1.2}
.page-assistant .step .stx span{display:block;font-size:11px;color:var(--muted);margin-top:1px}
.page-assistant .step.on .stx b{color:var(--cinnabar-d)}
/* 路线角标：告诉用户这一步对他适不适用，但步骤本身照样点得进去 */

/* 4pt 基准的间距档位。第二步原先在 10/12/14/16 之间混用四个几乎相同的值，
   既分不出组也排不出节奏 —— 值必须来自一个定好的集合，而不是随手写 */
.page-assistant{--s1:4px;--s2:8px;--s3:12px;--s4:16px;--s6:24px;--s8:32px;--radius-sm:9px}
.page-assistant .panel{margin-top:20px;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-lg);padding:clamp(22px,3.2vw,38px)}
.page-assistant .panel.is-hidden{display:none}
.page-assistant .p-head{display:flex;align-items:flex-start;gap:15px;margin-bottom:6px}
.page-assistant .p-ic{width:48px;height:48px;flex-shrink:0;border-radius:13px;background:var(--indigo-700);color:#fff;display:flex;align-items:center;justify-content:center}
.page-assistant .p-ic svg{width:26px;height:26px}
.page-assistant .p-num{font-size:12px;font-weight:700;color:var(--indigo-500);letter-spacing:.03em}
.page-assistant .panel h2{font-size:clamp(1.4rem,2.5vw,1.9rem);color:var(--indigo-900);letter-spacing:-.01em;line-height:1.2}
.page-assistant .p-desc{font-size:14.5px;color:var(--muted);line-height:1.65;max-width:74ch;margin:14px 0 22px}
.page-assistant .p-desc b{color:var(--indigo-700)}
.page-assistant .two{display:grid;grid-template-columns:1fr 1fr;gap:clamp(20px,3vw,32px)}
.page-assistant .subh{font-size:12.5px;font-weight:700;color:var(--indigo-900);text-transform:uppercase;letter-spacing:.03em;margin-bottom:12px;font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-assistant .q-group{margin-bottom:18px}
.page-assistant .q-group>label{display:block;font-size:14px;font-weight:600;color:var(--ink);margin-bottom:9px}
.page-assistant .opts{display:flex;flex-wrap:wrap;gap:9px}
.page-assistant .opt{font-family:inherit;font-size:13.5px;font-weight:600;color:var(--indigo-700);background:var(--surface);border:1.5px solid var(--line);border-radius:10px;padding:10px 16px;cursor:pointer;transition:.18s}
.page-assistant .opt:hover{border-color:var(--indigo-300);background:var(--indigo-100)}
.page-assistant .opt.on{background:var(--indigo-700);border-color:var(--indigo-700);color:#fff}
.page-assistant .sub-q.is-hidden{display:none}
.page-assistant .match{background:var(--indigo-900);color:#fff;border-radius:16px;padding:24px;position:relative;overflow:hidden;isolation:isolate}
.page-assistant .match::before{content:"";position:absolute;inset:0;z-index:-1;background:radial-gradient(500px 240px at 100% 0,rgba(44,127,114,.4),transparent 60%)}
.page-assistant .match .ml{font-size:12px;font-weight:700;color:var(--indigo-200);letter-spacing:.03em}
.page-assistant .match .mt{font-family:"Spectral","Noto Serif SC",serif;font-weight:700;font-size:1.5rem;margin:5px 0 16px;color:#fff}
.page-assistant .match .mrow{margin-bottom:15px}
.page-assistant .match .mrow>span{font-size:12px;color:rgba(233,238,247,.7);display:block;margin-bottom:7px}
.page-assistant .gchips{display:flex;flex-wrap:wrap;gap:7px}
.page-assistant .gchips b{font-size:12.5px;font-weight:700;padding:5px 12px;border-radius:999px;background:rgba(255,255,255,.1);color:#fff}
.page-assistant .gchips b.hot{background:var(--cinnabar);color:#fff}
.page-assistant .statlist{list-style:none;display:flex;flex-direction:column;gap:7px}
.page-assistant .statlist li{display:flex;align-items:flex-start;gap:9px;font-size:13px;color:rgba(233,238,247,.92);line-height:1.45}
.page-assistant .statlist li svg{width:16px;height:16px;flex-shrink:0;margin-top:2px;color:var(--indigo-200)}
.page-assistant .sham-note{display:flex;align-items:flex-start;gap:9px;margin-top:16px;padding-top:15px;border-top:1px solid rgba(255,255,255,.14);font-size:12.5px;line-height:1.55;color:rgba(233,238,247,.82)}
.page-assistant .sham-note+.sham-note{margin-top:10px;padding-top:0;border-top:0}
.page-assistant .sham-note svg{width:15px;height:15px;flex-shrink:0;margin-top:2px;color:var(--indigo-200)}
/* 路线岔口。两张卡片并排，窄屏落成上下两张 */
.page-assistant .stage{margin-top:24px}
.page-assistant .stage .subh{margin-bottom:8px}
.page-assistant .stage-q{font-size:14px;font-weight:600;color:var(--ink);margin-bottom:11px}
.page-assistant .stage-opts{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}
.page-assistant .stage-opt{font-family:inherit;text-align:left;background:var(--surface);border:1.5px solid var(--line);border-radius:12px;padding:13px 15px;cursor:pointer;transition:.18s}
.page-assistant .stage-opt:hover{border-color:var(--indigo-300);background:var(--indigo-100)}
.page-assistant .stage-opt b{display:block;font-size:13.5px;font-weight:700;color:var(--indigo-800);margin-bottom:4px}
.page-assistant .stage-opt span{display:block;font-size:12px;line-height:1.5;color:var(--muted)}
.page-assistant .stage-opt.on{border-color:var(--indigo-700);background:var(--indigo-100)}
.page-assistant .stage-opt.on b{color:var(--cinnabar-d)}
.page-assistant .stage-go{margin-top:12px}
/* ---- 第四步工作清单 ----
   一条待办 = 第三步判为模糊/未报告的一个条目。不用卡片阵：每条的内容长短差很多，
   等大卡片会把「这条只缺一句」和「这条整段没写」画成同一个重量 */
.page-assistant .wk-empty,.page-assistant .wk-done{display:flex;align-items:center;gap:var(--s3);flex-wrap:wrap;margin:0;padding:var(--s6);border:1px dashed var(--line);border-radius:var(--radius);font-size:13.5px;line-height:1.65;color:var(--muted)}
/* 全部改完是个好消息，不该用灰色「暂无数据」的语气 */

/* 待办清单是选择器：一行一条，只有一个动作。行高压到能一眼扫完几十条 */

/* 建议区与当前正文明确分开：一个是你写的，一个是模型给的，混在一起最要命 */

/* 工作清单降级成快捷入口之后，「还没有草稿 / 还没跑过校验」不再是拦路的空状态，
   而是这一步下半段的一句说明 —— 所以比 .wk-empty 轻，不占一整块 */

/* ---- 第四步独立面板 ----
   这一步的主体：不需要草稿、不需要跑过校验，输入全由用户直接给（文档第 4 节的字面形态） */
/* ── 第四步工作台 ──────────────────────────────────────────────────────
   三层：工作区（白面，内容层）→ 工具条（paper-2，第二层中性面，比内容面稍冷）
   → 结果区。product register 的做法：工具栏与内容面用不同的中性层区分职责。
   朱砂只留给「运行」这一个主行动；覆盖度不足、年份存疑那些警示走琥珀 ——
   朱砂是行动色不是警示色，混用会把它的稀缺性稀释掉。 */

/* 分钟级任务的阶段条。四段是真实流水线，不是装饰性假进度 */

@keyframes bgPulse{0%,100%{opacity:1}50%{opacity:.35}}
/* 写回草稿。挂在生成结果框内部，与「复制」同处一区：它们是同一件事的两种去处 */

/* 第 2/3 步面板顶部的路线提示，与 .p-desc 区分开但不喧宾夺主 */
.page-assistant .route-note{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:18px;padding:12px 16px;border:1px solid var(--line);border-radius:12px;background:var(--paper-2);font-size:12.5px;line-height:1.6;color:var(--muted)}
.page-assistant .route-note>span{flex:1;min-width:220px}
.page-assistant .route-note b{color:var(--indigo-700)}
.page-assistant .type-tips{margin-bottom:18px;padding:12px 16px;border:1px solid var(--line);border-radius:12px;background:var(--paper-2);font-size:13px;line-height:1.65;color:var(--ink)}
.page-assistant .type-tips .tt-type{display:block;margin-bottom:4px;font-size:12px;font-weight:700;color:var(--cinnabar-d)}
.page-assistant .type-tips p{margin:0}
.page-assistant .type-tips p+p{margin-top:4px}
/* 导入已有稿件。label 包 input：原生可键盘聚焦 */
.page-assistant .df-import{position:relative;overflow:hidden;cursor:pointer}
.page-assistant .df-import input{position:absolute;inset:0;opacity:0;cursor:pointer;font-size:0}
.page-assistant .df-import.busy{opacity:.6;pointer-events:none}
.page-assistant .df-imp-bar{margin:calc(var(--s6) * -1 + var(--s2)) 0 var(--s4)}
.page-assistant .df-imp-ok{margin:calc(var(--s6) * -1 + var(--s2)) 0 var(--s6);padding:var(--s3) var(--s4);
  background:var(--indigo-100);border-radius:var(--radius-sm);font-size:12.5px;line-height:1.65;color:var(--indigo-800)}
/* 全稿一致性检查：一条状态栏 + 可收起的汇总。结果的主要落点在条目上，这里不抢清单的地方 */
.page-assistant .ck-bar{display:flex;align-items:center;flex-wrap:wrap;gap:var(--s2) var(--s3);margin:var(--s6) 0 var(--s3);padding:var(--s2) var(--s4);border:1px dashed var(--line);border-radius:var(--radius-sm);background:var(--paper-2)}
.page-assistant .ck-meter{flex:0 1 160px}
.page-assistant .ck-status{font-size:12.5px;color:var(--muted);line-height:1.6;display:inline-flex;flex-wrap:wrap;align-items:center;gap:6px}
.page-assistant .ck-n{font-size:12px;font-weight:700;padding:1px 8px;border-radius:999px}
.page-assistant .ck-n.miss{background:#fbe4df;color:var(--cinnabar-d)}
.page-assistant .ck-n.warn{background:#fdf1d8;color:#8a5a00}
.page-assistant .ck-n.ok{background:var(--indigo-100);color:var(--indigo-800)}
.page-assistant .ck-tog{margin-left:auto;background:none;border:none;font:inherit;font-size:12.5px;font-weight:600;color:var(--indigo-700);cursor:pointer}
.page-assistant .ck-stale{margin:0 0 var(--s3);font-size:12.5px;color:#8a5a00}
.page-assistant .ck-panel{margin:0 0 var(--s6)}
.page-assistant .ck-goto{display:inline-flex;flex-wrap:wrap;gap:6px 14px;margin-left:4px}
.page-assistant .chk .ctext .ck-goto-item{display:inline-flex;align-items:baseline;gap:8px;font-size:12px;color:var(--muted)}
/* 导航上的检查标记 */
.page-assistant .tnav-flag{flex-shrink:0;width:16px;height:16px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;line-height:1;color:#fff}
.page-assistant .tnav-flag.cross{background:var(--cinnabar)}
.page-assistant .tnav-flag.vague{background:#d49a1f}
/* 右侧面板里这一条的检查意见 */
.page-assistant .tp-issues{margin-top:var(--s3);display:grid;gap:6px}
.page-assistant .tp-issue{margin:0;padding:8px 12px;border-radius:var(--radius-sm);font-size:12.5px;line-height:1.65;border:1px solid #f0dcaa;background:#fdf6e6;color:var(--ink)}
.page-assistant .tp-issue.issue{border-color:#f2c9bf;background:#fcece8}
.page-assistant .tp-issue b{margin-right:6px}
/* AI 完善 */
.page-assistant .tp-ai{margin-top:var(--s4);padding-top:var(--s4);border-top:1px solid var(--line)}
.page-assistant .tp-ai-note{min-height:0}
.page-assistant .tp-ai-bar{display:flex;align-items:center;flex-wrap:wrap;gap:var(--s2);margin-top:var(--s2)}
.page-assistant .tp-ai-hint{font-size:12px;color:var(--muted)}
.page-assistant .tp-ai-out{margin-top:var(--s3);padding:var(--s3) var(--s4);border:1px solid var(--indigo-200);border-radius:var(--radius-sm);background:var(--indigo-100)}
.page-assistant .tp-ai-text{margin:6px 0 0;white-space:pre-wrap;font-size:14px;line-height:1.75;color:var(--ink)}
.page-assistant .tp-ai-warn{margin:8px 0 0;font-size:12px;color:#8a5a00}
.page-assistant .tp-ai-model{margin-left:auto;font-size:11px;color:var(--muted)}
.page-assistant details.audit>summary{cursor:pointer;list-style:revert}
/* ---- 第二步工作台条 ----
   一条横条装下「依据哪份规范 · 共几条 | 哪份草稿 · 叫什么 | 填到哪儿了 | 存/删」，
   替代原先五个纵向堆叠的块。间距一律走上面那套 4pt 档位，不再出现 10/12/14/16 混排 */
.page-assistant .wb{display:flex;align-items:center;flex-wrap:wrap;gap:var(--s3) var(--s4);padding:var(--s3) var(--s4);margin-bottom:var(--s6);background:var(--paper);border:1px solid var(--line);border-radius:var(--radius)}
.page-assistant .wb-src{display:flex;align-items:center;gap:var(--s2);flex-wrap:wrap;min-width:0}
.page-assistant .wb-src .gchips b{background:var(--indigo-100);color:var(--indigo-800)}
.page-assistant .wb-src .gchips b.hot{background:var(--cinnabar);color:#fff}
.page-assistant .wb-count{font-size:12px;color:var(--muted)}
/* 分隔线而不是又一个盒子：把「这份清单是什么」与「我的这份草稿」两组分开 */
.page-assistant .wb-sep{width:1px;align-self:stretch;min-height:24px;background:var(--line);flex:none}
.page-assistant .wb-name{flex:1 1 200px;min-width:0;font-family:inherit;font-size:13.5px;color:var(--ink);background:var(--surface);border:1.5px solid var(--line);border-radius:var(--radius-sm);padding:7px 12px}
.page-assistant .wb-name:focus{outline:none;border-color:var(--indigo-300)}
.page-assistant .wb-name::placeholder{color:var(--muted)}
.page-assistant .wb-prog{display:flex;align-items:center;gap:var(--s2);flex:none}
.page-assistant .wb-prog .meter{flex:none;width:56px;height:6px}
.page-assistant .wb-prog b{font-size:13px;font-weight:700;color:var(--indigo-700);font-variant-numeric:tabular-nums}
.page-assistant .wb-prog b em{font-style:normal;font-weight:600;color:var(--muted)}
.page-assistant .wb-act{display:flex;align-items:center;gap:var(--s2);flex:none;margin-left:auto}
.page-assistant .wb-hint{margin:calc(var(--s6) * -1 + var(--s2)) 0 var(--s6);font-size:12.5px;line-height:1.55;color:var(--muted)}
/* 第二步：左导航 + 右面板。导航定宽、面板吃剩余；导航自己滚，面板随页面走 */
.page-assistant .tpl-grid{display:grid;grid-template-columns:minmax(220px,300px) minmax(0,1fr);gap:clamp(16px,2.5vw,28px);align-items:start}
.page-assistant .tnav{position:sticky;top:var(--s6);max-height:calc(100vh - var(--s8) * 2);overflow-y:auto;border:1px solid var(--line);border-radius:var(--radius);background:var(--surface)}
.page-assistant .tnav-part{position:sticky;top:0;z-index:1;padding:9px 14px;background:var(--indigo-900);color:#fff;font-size:11.5px;font-weight:700;letter-spacing:.02em}
.page-assistant .tnav-dom{border-top:1px solid var(--line)}
.page-assistant .tnav-part+.tnav-dom{border-top:none}
.page-assistant .tnav-dh{display:flex;align-items:center;gap:8px;width:100%;padding:10px 14px;background:var(--paper-2);border:none;font-family:inherit;font-size:12.5px;font-weight:700;color:var(--indigo-800);text-align:left;cursor:pointer}
.page-assistant .tnav-dh:hover{background:var(--indigo-100)}
.page-assistant .tnav-dt{flex:1;min-width:0}
.page-assistant .tnav-dc{font-size:11px;font-weight:600;color:var(--muted);font-variant-numeric:tabular-nums}
.page-assistant .tnav-dh svg{width:14px;height:14px;flex-shrink:0;color:var(--muted);transition:transform .2s}
.page-assistant .tnav-dom.open .tnav-dh svg{transform:rotate(180deg)}
.page-assistant .tnav-list{list-style:none;margin:0;padding:4px 0}
.page-assistant .tnav-item{display:flex;align-items:flex-start;gap:8px;width:100%;padding:7px 14px 7px 11px;border:none;border-left:3px solid transparent;background:transparent;font-family:inherit;font-size:13px;line-height:1.45;color:var(--ink);text-align:left;cursor:pointer}
.page-assistant .tnav-item:hover{background:var(--paper)}
.page-assistant .tnav-item.on{background:var(--indigo-100);border-left-color:var(--cinnabar);color:var(--indigo-900);font-weight:600}
.page-assistant .tnav-no{font-family:"Spectral",serif;font-weight:700;color:var(--indigo-500);min-width:26px;flex-shrink:0;font-variant-numeric:tabular-nums}
/* 导航里只留一句要求的前两行；全文在右面板 */
.page-assistant .tnav-tx{flex:1;min-width:0;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.page-assistant .tnav-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;margin-top:6px;border:1.5px solid var(--line);background:transparent}
.page-assistant .tnav-item.filled .tnav-dot{background:var(--indigo-500);border-color:var(--indigo-500)}
.page-assistant .tnav-item.over .tnav-dot{background:var(--cinnabar);border-color:var(--cinnabar)}
/* scroll-margin 给 sticky 页头让位：`revealSelection` 滚到面板顶时标题不被压在页头下面 */
.page-assistant .tpane{border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);padding:var(--s6);scroll-margin-top:88px}
.page-assistant .tpl-empty-box{border:1px dashed var(--line);border-radius:var(--radius)}
.page-assistant .tp-crumb{display:block;font-size:11.5px;color:var(--muted);margin-bottom:6px}
.page-assistant .tp-title{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:var(--s4)}
.page-assistant .tp-no{font-family:"Spectral",serif;font-weight:700;font-size:24px;line-height:1;color:var(--indigo-600)}
.page-assistant .tp-req-text{margin:0;font-size:15px;font-weight:600;line-height:1.6;color:var(--ink)}
.page-assistant .tp-req .tmpl-ext{margin-top:8px}
.page-assistant .tp-ex{margin-top:var(--s6);padding:var(--s4);background:var(--paper);border-left:3px solid var(--indigo-300);border-radius:var(--radius-sm)}
.page-assistant .tp-ex .subh{margin-bottom:6px}
.page-assistant .tp-ex-text{margin:0;font-size:13.5px;line-height:1.7;color:var(--ink);white-space:pre-wrap;word-break:break-word}
.page-assistant .tp-ex-empty{margin:0;font-size:12.5px;line-height:1.6;color:var(--muted)}
.page-assistant .tp-write{margin-top:var(--s6)}
.page-assistant .tp-write .subh{display:block}
.page-assistant .tp-ta{margin-top:0;min-height:180px}
.page-assistant .tp-foot{display:flex;align-items:center;gap:var(--s3);flex-wrap:wrap;margin-top:var(--s3)}
.page-assistant .tp-chars{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
.page-assistant .tp-chars.over{color:var(--cinnabar-d);font-weight:700}
.page-assistant .tp-btns{display:flex;gap:8px;margin-left:auto}
.page-assistant .df-preview-wrap{margin-top:var(--s6)}
.page-assistant .tmpl-ext{display:block;margin-top:6px;font-weight:400;font-size:12.5px;color:var(--muted);line-height:1.5}
.page-assistant .tmpl-ext b{display:block;font-size:11px;font-weight:700;color:var(--indigo-500);margin-bottom:2px}
.page-assistant .tmpl-empty{padding:22px 16px;font-size:13px;color:var(--muted);text-align:center}
.page-assistant .req{font-size:11px;font-weight:700;padding:2px 9px;border-radius:999px;flex-shrink:0}
.page-assistant .req.must{color:var(--cinnabar-d);background:rgba(192,54,44,.09)}
.page-assistant .req.opt{color:var(--muted);background:var(--paper-2)}
.page-assistant .req.ext{color:var(--cinnabar-d);background:rgba(192,54,44,.09)}
.page-assistant .df-sel{flex:none;max-width:180px;font-family:inherit;font-size:13px;color:var(--ink);background:var(--surface);border:1.5px solid var(--line);border-radius:var(--radius-sm);padding:7px 10px}
.page-assistant .df-state{font-size:12px;color:var(--muted)}
.page-assistant .df-state.dirty{color:var(--cinnabar-d)}
.page-assistant .df-del{font-family:inherit;font-size:12.5px;color:var(--muted);background:none;border:none;cursor:pointer;padding:6px 2px;text-decoration:underline;text-underline-offset:3px}
.page-assistant .df-del:hover{color:var(--cinnabar-d)}
.page-assistant .df-del:disabled{opacity:.45;cursor:not-allowed}
.page-assistant .df-ta{display:block;width:100%;margin-top:8px;font-family:inherit;font-size:13.5px;font-weight:400;line-height:1.6;color:var(--ink);background:var(--surface);border:1.5px solid var(--line);border-radius:var(--radius-sm);padding:9px 12px;resize:vertical}
.page-assistant .df-ta:focus{outline:none;border-color:var(--indigo-300)}
.page-assistant .df-ta.filled{background:var(--paper)}
.page-assistant .df-compose{display:flex;align-items:center;gap:var(--s2);flex-wrap:wrap;margin-top:var(--s4)}
.page-assistant .df-miss{font-size:12.5px;color:var(--cinnabar-d)}
.page-assistant .df-preview{border:1px solid var(--line);border-radius:var(--radius);padding:var(--s4);background:var(--paper)}
.page-assistant .df-preview pre{margin:0;max-height:520px;overflow:auto;white-space:pre-wrap;word-break:break-word;font-family:inherit;font-size:13px;line-height:1.7;color:var(--ink)}
.page-assistant .df-rebuild{margin:0 0 var(--s3);padding:var(--s3) var(--s4);border:1px solid var(--line);border-radius:var(--radius-sm);background:var(--paper-2);font-size:12.5px;line-height:1.65;color:var(--ink)}
.page-assistant .df-rebuild p{margin:0}
.page-assistant .df-rebuild-warn{margin-top:6px !important;color:#8a5a00}
.page-assistant .df-preview-empty{margin:0;border:1px dashed var(--line);border-radius:var(--radius);padding:var(--s6) var(--s4);font-size:12.5px;line-height:1.65;color:var(--muted)}
.page-assistant .tmpl-note{margin-top:var(--s6);font-size:12.5px;color:var(--muted);line-height:1.55}
.page-assistant .tmpl-note b{color:var(--indigo-700)}
.page-assistant .meter-box{display:flex;align-items:center;gap:16px;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:16px 20px;margin-bottom:20px}
.page-assistant .meter{flex:1;height:10px;border-radius:999px;background:var(--paper-2);overflow:hidden}
.page-assistant .meter i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,var(--indigo-500),var(--indigo-600));width:82%}
.page-assistant .meter-box b{font-family:"Spectral",serif;font-weight:700;font-size:1.3rem;color:var(--indigo-700)}
.page-assistant .chk{list-style:none;display:flex;flex-direction:column;gap:8px}
.page-assistant .chk li{display:flex;align-items:flex-start;gap:11px;font-size:14px;padding:11px 14px;border:1px solid var(--line);border-radius:11px;background:var(--surface);line-height:1.5}
.page-assistant .chk .ci{width:22px;height:22px;flex-shrink:0;border-radius:50%;display:flex;align-items:center;justify-content:center;margin-top:1px}
.page-assistant .chk .ci svg{width:14px;height:14px}
.page-assistant .chk .ok .ci{background:var(--info-bg);color:var(--info)}
.page-assistant .chk .warn .ci{background:var(--amber-bg);color:var(--amber)}
.page-assistant .chk .miss .ci{background:rgba(192,54,44,.09);color:var(--cinnabar-d)}
.page-assistant .chk .ctext b{color:var(--indigo-900)}
.page-assistant .chk .ctext span{display:block;font-size:12.5px;color:var(--muted);margin-top:2px}
.page-assistant .chk .cstat{margin-left:auto;flex-shrink:0;font-size:11.5px;font-weight:700;padding:3px 10px;border-radius:999px;white-space:nowrap}
.page-assistant .chk .ok .cstat{color:var(--info);background:var(--info-bg)}
.page-assistant .chk .warn .cstat{color:var(--amber);background:var(--amber-bg)}
.page-assistant .chk .miss .cstat{color:var(--cinnabar-d);background:rgba(192,54,44,.09)}
.page-assistant .rv-err{margin-top:12px;font-size:13px;color:var(--cinnabar-d);background:rgba(192,54,44,.07);border-radius:10px;padding:10px 14px}
.page-assistant .chk .na .ci{background:var(--paper-2);color:var(--muted)}
.page-assistant .chk .na .cstat{color:var(--muted);background:var(--paper-2)}
.page-assistant .ck-list li{align-items:flex-start}
.page-assistant .ck-list .ctext b em{font-style:normal;font-size:11px;font-weight:700;color:var(--indigo-500);background:var(--indigo-100);border-radius:999px;padding:2px 9px;margin-right:8px;white-space:nowrap}
.page-assistant .ck-list .ckf{padding-left:11px;border-left:2px solid var(--line);margin-top:7px}
.page-assistant .ck-list .ckf.issue{border-left-color:var(--cinnabar)}
.page-assistant .ck-list .ckf.warn{border-left-color:var(--amber)}
.page-assistant .ck-list .ckf i{font-style:normal;font-weight:700;color:var(--indigo-700);margin-right:6px}
.page-assistant .ck-list .ckf u{text-decoration:none;color:var(--ink)}
.page-assistant .ck-list .ckf b{display:block;margin-top:3px;font-weight:600;color:var(--indigo-700)}
/* 结果区里的稿件原文（默认折叠，带行号）。等宽字体是必须的 ——
   行号要对齐才读得出「第 12 行」，比例字体下数字列会歪 */

/* 判定里的行号引用：看着像正文的一部分，点得动 */
.page-assistant .src-jump{background:none;border:0;padding:0;cursor:pointer;font:inherit;color:var(--indigo-700);
  font-weight:700;text-underline-offset:3px}
.page-assistant .src-jump:hover{text-decoration:underline}
/* 引文在原文里没找到：只是提醒去核，不是判错 —— 用琥珀色而不是朱砂，别和「未报告」撞色 */
.page-assistant .ev-unlocated{display:inline-block;margin-left:4px;font-size:12px;color:var(--amber)}

/* 校验历史。与 .audit 同一套卡片语言：两者都是「这一步发生过什么」的回看区 */

.page-assistant .audit{margin-top:22px;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:18px}
.page-assistant .audit-list{list-style:none;display:flex;flex-direction:column;gap:8px}
.page-assistant .audit-list li{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;font-size:13px;padding:11px 14px;border:1px solid var(--line);border-radius:11px;background:var(--surface);line-height:1.5}
.page-assistant .audit-list .at{font-family:"Spectral",serif;font-weight:700;color:var(--indigo-500);font-variant-numeric:tabular-nums;flex-shrink:0}
.page-assistant .audit-list .aa{font-weight:700;color:var(--indigo-900);flex-shrink:0}
.page-assistant .audit-list .ad{flex:1;min-width:200px;color:var(--muted)}
.page-assistant .exp-btns{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.page-assistant .exp{display:flex;align-items:center;gap:13px;padding:16px 18px;border:1.5px solid var(--line);border-radius:14px;background:var(--surface);cursor:pointer;text-align:left;font-family:inherit;transition:.2s var(--ease)}
.page-assistant .exp:hover{border-color:var(--indigo-300);background:var(--indigo-100);transform:translateY(-2px)}
.page-assistant .exp.on{border-color:var(--indigo-700);background:var(--indigo-100)}
.page-assistant .exp.on .ei{background:var(--indigo-700);color:#fff}
.page-assistant .exp .ei{width:40px;height:40px;flex-shrink:0;border-radius:11px;background:var(--indigo-100);color:var(--indigo-700);display:flex;align-items:center;justify-content:center}
.page-assistant .exp .ei svg{width:21px;height:21px}
.page-assistant .exp b{display:block;font-size:14px;color:var(--indigo-900)}
.page-assistant .exp span{font-size:12px;color:var(--muted)}
.page-assistant .share{margin-top:20px;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:18px}
.page-assistant .share-row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.page-assistant .share-link{flex:1;min-width:200px;display:flex;align-items:center;gap:10px;background:var(--surface);border:1.5px solid var(--line);border-radius:10px;padding:10px 14px;font-size:13px;color:var(--muted);font-family:"Spectral",monospace}
.page-assistant .share-perm{display:inline-flex;background:var(--paper-2);border:1px solid var(--line);border-radius:var(--radius-sm);padding:3px;gap:2px}
.page-assistant .share-perm button{border:none;background:transparent;font-family:inherit;font-size:12.5px;font-weight:600;color:var(--muted);padding:6px 12px;border-radius:7px;cursor:pointer}
.page-assistant .share-perm button.on{background:var(--surface);color:var(--indigo-800);box-shadow:var(--shadow-sm)}
.page-assistant .ver-list{list-style:none;margin-top:18px;display:flex;flex-direction:column;gap:8px}
.page-assistant .ver-list li{display:flex;align-items:center;gap:12px;font-size:13px;padding:11px 14px;border:1px solid var(--line);border-radius:11px;background:var(--surface)}
.page-assistant .ver-list .vt{font-family:"Spectral",serif;font-weight:700;color:var(--indigo-700);font-variant-numeric:tabular-nums}
.page-assistant .ver-list .vn{flex:1;color:var(--ink)}
.page-assistant .ver-list .vtag{font-size:11px;font-weight:700;color:var(--muted);background:var(--paper-2);border-radius:999px;padding:3px 10px}
.page-assistant .ver-list .vdiff{font-family:inherit;font-size:12px;font-weight:700;color:var(--indigo-700);background:var(--surface);border:1.5px solid var(--line);border-radius:8px;padding:4px 12px;cursor:pointer;transition:.18s}
.page-assistant .ver-list .vdiff:hover{border-color:var(--indigo-300);background:var(--indigo-100)}
.page-assistant .ver-list .vdiff.on{background:var(--indigo-700);border-color:var(--indigo-700);color:#fff}
.page-assistant .ver-list li.diffbox{flex-direction:column;gap:6px;align-items:stretch;background:var(--paper);border-style:dashed;margin:-2px 0 2px 10px}
.page-assistant .diffbox .dh{font-size:11.5px;font-weight:700;color:var(--indigo-500);letter-spacing:.02em}
.page-assistant .diffbox .dl{display:flex;gap:9px;font-size:13px;line-height:1.5;color:var(--ink)}
.page-assistant .diffbox .dl em{font-style:normal;font-weight:700;flex-shrink:0;width:12px;text-align:center}
.page-assistant .diffbox .add em{color:var(--info)}
.page-assistant .diffbox .del em{color:var(--cinnabar-d)}
.page-assistant .diffbox .del{color:var(--muted);text-decoration:line-through;text-decoration-color:rgba(122,132,148,.45)}
.page-assistant .wz-nav{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-top:22px;flex-wrap:wrap}
.page-assistant .wz-nav .wz-prog{font-size:13px;color:var(--muted)}
.page-assistant .wz-nav .wz-prog b{color:var(--indigo-700)}
.page-assistant .wz-nav .wz-btns{display:flex;gap:10px}
.page-assistant .beta-note{display:inline-flex;align-items:center;gap:9px;font-size:12.5px;font-weight:600;color:var(--amber);background:var(--amber-bg);border:1px solid #e7d39a;padding:7px 14px;border-radius:999px;margin-top:20px}
/* ---- 五步拆回来之后新增的版面（2026-10） ---- */
/* 每一步底部的「下一步该去哪」：主行动靠右，与面板底边留出节奏 */
.page-assistant .step-foot{display:flex;align-items:center;justify-content:flex-end;flex-wrap:wrap;gap:var(--s3);margin-top:var(--s6);padding-top:var(--s4);border-top:1px solid var(--line)}
.page-assistant .step-foot .df-miss{margin-right:auto}
/* ① 继续上次的草稿：一条横幅，不抢问卷的地方 */
.page-assistant .resume{display:flex;align-items:center;gap:var(--s4);flex-wrap:wrap;margin:0 0 var(--s6);padding:var(--s3) var(--s4);border:1px solid var(--indigo-200);border-radius:var(--radius);background:var(--indigo-100)}
.page-assistant .resume-tx{flex:1;min-width:220px;display:flex;flex-wrap:wrap;align-items:baseline;gap:4px var(--s3)}
.page-assistant .resume-tx b{font-size:12px;font-weight:700;color:var(--cinnabar-d)}
.page-assistant .resume-tx span{font-size:14px;font-weight:600;color:var(--indigo-900)}
.page-assistant .resume-tx small{font-size:12px;color:var(--muted)}
/* ② 清单表页签。没纳入的那张降灰、标题划线 —— 还点得进去（正文照存），只是不参与后面几步 */
.page-assistant .ptabs{display:flex;gap:var(--s2);flex-wrap:wrap;margin:0 0 var(--s4)}
.page-assistant .ptab{display:flex;align-items:stretch;border:1.5px solid var(--line);border-radius:var(--radius-sm);background:var(--surface);overflow:hidden;max-width:100%}
.page-assistant .ptab.on{border-color:var(--indigo-700);background:var(--indigo-100)}
.page-assistant .ptab-main{display:flex;flex-direction:column;align-items:flex-start;gap:2px;padding:8px 12px;border:none;background:none;font-family:inherit;text-align:left;cursor:pointer;min-width:0}
.page-assistant .ptab-main b{font-size:13px;font-weight:700;color:var(--indigo-800);max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.page-assistant .ptab-main small{font-size:11.5px;color:var(--muted);font-variant-numeric:tabular-nums}
.page-assistant .ptab.on .ptab-main b{color:var(--cinnabar-d)}
.page-assistant .ptab.off .ptab-main b{color:var(--muted);text-decoration:line-through;text-decoration-color:rgba(122,132,148,.5)}
.page-assistant .ptab-inc{display:flex;align-items:center;gap:6px;padding:0 12px;border-left:1px solid var(--line);font-size:11.5px;color:var(--muted);cursor:pointer;white-space:nowrap}
.page-assistant .ptab-inc input{accent-color:var(--indigo-700);margin:0}
/* 第二步的规范切换（sql/056）：借清单表页签的外形，但它切的是「整份草稿用哪份规范」，比页签高一级，单独一行加标题 */
.page-assistant .glsw{margin:0 0 var(--s6);padding:var(--s3) var(--s4);background:var(--paper);border:1px solid var(--line);border-radius:var(--radius)}
.page-assistant .glsw-label{display:block;font-size:12.5px;font-weight:700;color:var(--indigo-900);margin-bottom:var(--s2)}
.page-assistant .glsw-tabs{margin:0}
.page-assistant .glsw-opt{border:1.5px solid var(--line);border-radius:var(--radius-sm);background:var(--surface)}
.page-assistant .glsw-opt.on{border-color:var(--indigo-700);background:var(--indigo-100)}
.page-assistant .glsw-opt:disabled{cursor:wait;opacity:.6}
.page-assistant .glsw-opt.on b{color:var(--cinnabar-d)}
.page-assistant .glsw-opt b em{font-style:normal;font-size:10.5px;font-weight:700;color:#fff;background:var(--cinnabar);border-radius:999px;padding:1px 7px;margin-left:6px;vertical-align:1px}
.page-assistant .glsw-opt small.warn{color:#8a5a00}
.page-assistant .glsw-hint{margin:var(--s2) 0 0;font-size:12px;color:var(--muted);line-height:1.55}
.page-assistant .part-off-note{margin:0 0 var(--s4);font-size:12.5px;line-height:1.6;color:#8a5a00}
/* ③ 问题清单的概览与筛选 */
.page-assistant .ck-sum,.page-assistant .ck-parts{display:flex;flex-wrap:wrap;gap:var(--s2);margin:var(--s4) 0 0}
.page-assistant .ck-chip{font-family:inherit;font-size:12.5px;font-weight:600;color:var(--indigo-800);background:var(--surface);border:1.5px solid var(--line);border-radius:999px;padding:4px 12px;cursor:pointer}
.page-assistant .ck-chip.miss{color:var(--cinnabar-d)}
.page-assistant .ck-chip.warn{color:#8a5a00}
.page-assistant .ck-chip.on{border-color:var(--indigo-700);background:var(--indigo-100)}
.page-assistant .ck-sec{margin:var(--s6) 0 var(--s3)}
.page-assistant .is-list .is-no{font-family:"Spectral",serif;font-weight:700;color:var(--indigo-500);min-width:30px;flex-shrink:0;font-variant-numeric:tabular-nums;margin-top:1px}
.page-assistant .is-list .ctext{flex:1;min-width:0}
.page-assistant .is-list .ctext b{font-weight:600}
.page-assistant .chk .ctext .is-act{display:flex;gap:var(--s2);flex-wrap:wrap;margin-top:var(--s2)}
/* ④ 队列 + 唯一的工作区 */
.page-assistant .rf-grid{display:grid;grid-template-columns:minmax(220px,300px) minmax(0,1fr);gap:clamp(16px,2.5vw,28px);align-items:start}
.page-assistant .rf-queue{position:sticky;top:var(--s6);max-height:calc(100vh - var(--s8) * 2);display:flex;flex-direction:column;border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);overflow:hidden}
.page-assistant .rf-src{display:flex;gap:2px;padding:4px;margin:var(--s2);background:var(--paper-2);border-radius:var(--radius-sm)}
.page-assistant .rf-src button{flex:1;border:none;background:transparent;font-family:inherit;font-size:12px;font-weight:600;color:var(--muted);padding:6px 8px;border-radius:7px;cursor:pointer}
.page-assistant .rf-src button.on{background:var(--surface);color:var(--indigo-800);box-shadow:var(--shadow-sm)}
.page-assistant .rf-src button:disabled{opacity:.45;cursor:not-allowed}
.page-assistant .rf-qempty{margin:0;padding:var(--s4);font-size:12.5px;line-height:1.6;color:var(--muted)}
.page-assistant .rf-list{list-style:none;margin:0;padding:0 0 4px;overflow-y:auto}
.page-assistant .rf-item{display:flex;align-items:flex-start;gap:8px;width:100%;padding:7px 12px 7px 9px;border:none;border-left:3px solid transparent;background:transparent;font-family:inherit;font-size:13px;line-height:1.45;color:var(--ink);text-align:left;cursor:pointer}
.page-assistant .rf-item:hover{background:var(--paper)}
.page-assistant .rf-item.on{background:var(--indigo-100);border-left-color:var(--cinnabar);font-weight:600}
.page-assistant .rf-kind{flex-shrink:0;font-size:10.5px;font-weight:700;padding:1px 7px;border-radius:999px;margin-top:1px;white-space:nowrap}
.page-assistant .rf-kind.miss{background:#fbe4df;color:var(--cinnabar-d)}
.page-assistant .rf-kind.warn{background:#fdf1d8;color:#8a5a00}
.page-assistant .rf-kind.na{background:var(--paper-2);color:var(--muted)}
.page-assistant .rf-kind.ok{background:var(--indigo-100);color:var(--indigo-800)}
.page-assistant .rf-cols{display:grid;gap:var(--s4);margin-top:var(--s6)}
.page-assistant .rf-cols.two{grid-template-columns:1fr 1fr}
.page-assistant .rf-cols .subh{display:block}
.page-assistant .rf-out{margin-top:0}
.page-assistant .rf-out-head{display:flex;align-items:center;gap:var(--s3)}
.page-assistant .rf-ver{margin-left:auto;display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
.page-assistant .rf-ver button{border:1px solid var(--line);background:var(--surface);border-radius:6px;width:22px;height:22px;line-height:1;cursor:pointer;font:inherit;color:var(--indigo-700)}
.page-assistant .rf-ver button:disabled{opacity:.4;cursor:not-allowed}
/* ⑤ 交付前核对 · AI 使用说明 */
.page-assistant .dl-box{margin-top:var(--s6);padding:var(--s4) var(--s6);border:1px solid var(--line);border-radius:var(--radius);background:var(--paper)}
.page-assistant .p-desc+.dl-box{margin-top:0}
.page-assistant .dl-list{list-style:none;margin:0;padding:0;display:grid;gap:6px}
.page-assistant .dl-list li{display:flex;align-items:baseline;gap:var(--s3);flex-wrap:wrap;font-size:13.5px;line-height:1.6;color:var(--ink);padding-left:14px;position:relative}
.page-assistant .dl-list li::before{content:"";position:absolute;left:0;top:.62em;width:6px;height:6px;border-radius:50%;background:#d49a1f}
.page-assistant .dl-ok{margin:0;font-size:13.5px;color:var(--indigo-800)}
.page-assistant .dl-note{margin:var(--s3) 0 0;font-size:12px;line-height:1.6;color:var(--muted)}
.page-assistant .dl-ai{margin:var(--s3) 0;padding:var(--s3) var(--s4);background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-sm);font-size:13.5px;line-height:1.75;color:var(--ink)}
.page-assistant .dl-pv-head{display:flex;align-items:center;gap:var(--s3);flex-wrap:wrap;margin-bottom:var(--s3)}
/* ④ 两个页签：逐条优化 · 整篇成文 */
.page-assistant .rf-tabs{display:flex;gap:var(--s2);margin:0 0 var(--s4);border-bottom:1px solid var(--line)}
.page-assistant .rf-tabs button{display:inline-flex;align-items:center;gap:8px;padding:10px 4px;margin-bottom:-1px;border:none;border-bottom:2px solid transparent;background:none;font-family:inherit;font-size:14px;font-weight:700;color:var(--muted);cursor:pointer}
.page-assistant .rf-tabs button+button{margin-left:var(--s4)}
.page-assistant .rf-tabs button.on{color:var(--indigo-900);border-bottom-color:var(--cinnabar)}
.page-assistant .rf-tabs small{font-size:11px;font-weight:700;padding:1px 8px;border-radius:999px;background:var(--indigo-100);color:var(--indigo-800)}
/* 一键优化条：范围 · 运行 | 全部采用。与 ck-bar 同一种「工具条」语言 */
.page-assistant .rf-batch{display:flex;align-items:center;flex-wrap:wrap;gap:var(--s2) var(--s3);padding:var(--s2) var(--s4);border:1px solid var(--line);border-radius:var(--radius-sm);background:var(--paper-2);font-size:13px}
.page-assistant .rf-batch-t{font-weight:700;color:var(--indigo-900)}
.page-assistant .rf-batch label{display:inline-flex;align-items:center;gap:5px;color:var(--ink);cursor:pointer}
.page-assistant .rf-batch input{accent-color:var(--indigo-700);margin:0}
.page-assistant .rf-batch-sep{width:1px;align-self:stretch;min-height:22px;background:var(--line)}
.page-assistant .rf-batch-note{font-size:12px;color:var(--muted)}
.page-assistant .rf-batch-hint{margin:var(--s2) 0 var(--s4);font-size:12px;line-height:1.6;color:var(--muted)}
.page-assistant .rf-badges{display:flex;flex-direction:column;align-items:flex-end;gap:3px;flex-shrink:0}
.page-assistant .rf-kind.sg{background:var(--cinnabar);color:#fff}
/* ④ 整篇成文：只读预览，像一篇稿子而不是一张表 */
.page-assistant .rd-bar{display:flex;align-items:center;flex-wrap:wrap;gap:var(--s2) var(--s3)}
.page-assistant .rd-doc{border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);padding:var(--s6) clamp(18px,4vw,48px)}
.page-assistant .rd-sec+.rd-sec{margin-top:var(--s8)}
.page-assistant .rd-sec-h{display:flex;align-items:center;gap:var(--s3);flex-wrap:wrap;margin-bottom:var(--s3)}
.page-assistant .rd-sec-h h3{font-size:1.1rem;color:var(--indigo-900);margin:0}
/* 2026-10 起成文按论文结构：题目 → 一级部分（2 方法）→ 小节（2.1 随机化与分配隐藏） */
.page-assistant .rd-title{font-size:1.35rem;line-height:1.4;color:var(--indigo-900);text-align:center;margin:0 0 var(--s6)}
.page-assistant .rd-part{font-size:1.15rem;color:var(--indigo-900);margin:var(--s6) 0 var(--s3);padding-bottom:6px;border-bottom:1px solid var(--line)}
.page-assistant .rd-sec-h h4{font-size:1rem;color:var(--indigo-800);margin:0}
.page-assistant .rd-sec-h .btn{margin-left:auto}
.page-assistant .rd-issues{margin:0 0 var(--s3);padding:var(--s2) var(--s4) var(--s2) calc(var(--s4) + 14px);border:1px solid #f2c9bf;border-radius:var(--radius-sm);background:#fcece8;font-size:12.5px;line-height:1.7;color:var(--ink)}
.page-assistant .rd-sec.stale .rd-p p{color:var(--muted)}
.page-assistant .rd-p{margin-bottom:var(--s3)}
.page-assistant .rd-p p{margin:0;font-family:"Noto Serif SC","Spectral",serif;font-size:15px;line-height:1.9;color:var(--ink);text-align:justify}
.page-assistant .rd-src{display:inline-flex;flex-wrap:wrap;gap:6px;margin-top:2px;font-size:11.5px;color:var(--muted);opacity:.7}
.page-assistant .rd-p:hover .rd-src{opacity:1}
/* ⑤ 正文来源 */
.page-assistant .dl-src{margin-top:var(--s6);display:grid;gap:var(--s2)}
.page-assistant .dl-src label{display:flex;align-items:baseline;gap:var(--s2);flex-wrap:wrap;padding:var(--s2) var(--s4);border:1.5px solid var(--line);border-radius:var(--radius-sm);cursor:pointer}
.page-assistant .dl-src label:has(input:checked){border-color:var(--indigo-700);background:var(--indigo-100)}
.page-assistant .dl-src input{accent-color:var(--indigo-700)}
.page-assistant .dl-src b{font-size:13.5px;color:var(--indigo-900)}
.page-assistant .dl-src small{flex-basis:100%;padding-left:22px;font-size:12px;color:var(--muted)}
@media(max-width:900px){
.page-assistant .two,.page-assistant .tpl-grid,.page-assistant .rf-grid,.page-assistant .rf-cols.two{grid-template-columns:1fr}
.page-assistant .rf-queue{position:static;max-height:300px}
/* 窄屏导航在上、面板在下；导航限高，否则 282 条把面板顶出首屏 */
.page-assistant .tnav{position:static;max-height:260px}
/* 工作台条在窄屏会折成两三行，两组之间的竖分隔线此时没有分隔任何东西 */
.page-assistant .wb-sep{display:none}
.page-assistant .wb-act{margin-left:0}
}
</style>
