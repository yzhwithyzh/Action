<script setup lang="ts">
/**
 * ① 立项匹配：分支问卷 → 研究类型 → 用哪份规范；末尾是路线岔口（从零写 / 已有稿件）。
 * 状态全在 `useReportWorkspace` / `useAssistantWizard`，这里只画。
 */
import { useAssistantCtx } from '~/composables/assistant/assistantContext'
import { STAGE_OPTS } from '~/composables/wizardQuery'

const ctx = useAssistantCtx()
const { t, pick } = ctx

const resumeAt = computed(() => {
  const iso = ctx.resumeDraft?.updateTime
  if (!iso) return ''
  const d = new Date(iso.replace(' ', 'T'))

  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString(ctx.isEn ? 'en-GB' : 'zh-CN')
})
</script>

<template>
  <div class="panel" :class="{ 'is-hidden': ctx.step !== 1 }" data-panel="1">
    <div class="p-head">
      <span class="p-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /><path d="M8 11h6M11 8v6" /></svg></span>
      <div><span class="p-num">{{ t('assistant.s012') }}</span><h2>{{ t('assistant.s013') }}</h2></div>
    </div>
    <p class="p-desc" v-html="t('assistant.s014')"></p>

    <!-- 账号下有草稿时，最近改过的那份放在最前面：回来接着写的人不必把问卷再答一遍 -->
    <div v-if="ctx.resumeDraft" class="resume">
      <span class="resume-tx">
        <b>{{ t('assistant.resumeTitle') }}</b>
        <span>{{ ctx.resumeDraft.title }}</span>
        <small>{{ t('assistant.resumeMeta', {
          code: ctx.resumeDraft.guidelineCode,
          a: ctx.resumeDraft.requiredFilled,
          b: ctx.resumeDraft.requiredTotal,
          at: resumeAt,
        }) }}</small>
      </span>
      <button class="btn btn-primary btn-sm" @click="ctx.continueDraft(ctx.resumeDraft)">
        {{ t('assistant.resumeGo') }} <span class="arrow" aria-hidden="true">→</span>
      </button>
    </div>

    <div class="two">
      <div>
        <div class="subh">{{ t('assistant.s015') }}</div>
        <!-- 分支问卷：按上一题的答案逐层弹出下一题（《ACTION智能匹配研究类型.docx》）。
             题与选项都来自后台，页面只负责按 walk 的结果逐层渲染 -->
        <div
          v-for="(s, depth) in ctx.walk.steps"
          :key="s.question.qKey"
          class="q-group"
          :class="{ 'sub-q': depth > 0 }"
          :data-q="s.question.qKey"
        >
          <label :id="`wzq-${s.question.qKey}`">
            {{ t('assistant.qNo', { n: depth + 1 }) }}{{ pick(s.question, 'text') ? ` · ${pick(s.question, 'text')}` : '' }}
          </label>
          <div class="opts" role="radiogroup" :aria-labelledby="`wzq-${s.question.qKey}`">
            <button
              v-for="o in s.question.options"
              :key="o.optKey"
              type="button"
              role="radio"
              class="opt"
              :class="{ on: o.optKey === s.option.optKey }"
              :aria-checked="o.optKey === s.option.optKey"
              :data-v="o.optKey"
              @click="ctx.answer(depth, o.optKey)"
            >{{ pick(o, 'label') || o.optKey }}</button>
          </div>
        </div>
      </div>
      <div>
        <div class="subh">{{ t('assistant.s027') }}</div>
        <div class="match" id="matchBox">
          <template v-if="ctx.matched">
            <span class="ml">{{ t('assistant.mlLabel') }}</span>
            <div class="mt">{{ pick(ctx.matched, 'name') }}</div>
            <div class="mrow">
              <span>{{ t('assistant.mountGuidelines') }}</span>
              <div class="gchips">
                <b v-for="g in ctx.matched.guidelines" :key="g" :class="{ hot: g === ctx.matched.hotGuideline }">{{ g }}</b>
              </div>
            </div>
            <div class="mrow" :style="ctx.matchTips.length ? undefined : 'margin-bottom:0'">
              <span>{{ t('assistant.recStats') }}</span>
              <ul class="statlist">
                <li v-for="(st, k) in ctx.matched.stats" :key="k">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M20 6 9 17l-5-5" /></svg>
                  <span>{{ pick(st, 'text') }}</span>
                </li>
              </ul>
            </div>
            <p v-for="(tip, k) in ctx.matchTips" :key="k" class="sham-note">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></svg>
              <span>{{ tip }}</span>
            </p>
          </template>
          <!-- 问卷判定的类型在研究类型表里查不到（后台停用了它）时，别让卡片整块消失 -->
          <p v-else class="ml">{{ t('assistant.matchNone') }}</p>
        </div>
        <!-- 规范有了、条目一条没有（眼下 STROBE）：在这一步就说，别等用户到第二步看见一片空白 -->
        <p v-if="ctx.noItems" class="rv-err">{{ t('assistant.tplEmpty') }}</p>

        <!-- 路线岔口。「从零开始写」与「已经有稿件」是两条不同的路，不替用户默认选一个 -->
        <div class="stage">
          <div class="subh">{{ t('assistant.stageTitle') }}</div>
          <p class="stage-q">{{ t('assistant.stageQ') }}</p>
          <div class="stage-opts">
            <button
              v-for="o in STAGE_OPTS"
              :key="o"
              type="button"
              class="stage-opt"
              :class="{ on: ctx.stage === o }"
              :aria-pressed="ctx.stage === o"
              @click="ctx.stage = ctx.stage === o ? '' : o"
            >
              <b>{{ t(`assistant.stageOpt.${o}`) }}</b>
              <span>{{ t(`assistant.stageDesc.${o}`) }}</span>
            </button>
          </div>
          <button v-if="ctx.stage" class="btn btn-primary btn-sm stage-go" @click="ctx.startStage">
            {{ t(ctx.stage === 'manuscript' ? 'assistant.stageGoReview' : 'assistant.stageGoDraft') }}
            <span class="arrow" aria-hidden="true">→</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
