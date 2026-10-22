<script setup lang="ts">
/**
 * ③ 合规与一致性检查：把纳入的清单表过一遍，产出问题清单。**这一步只诊断，不改稿。**
 *
 * 两类判定都在这里：逐条完整性（已报告 / 描述模糊 / 未报告）与全稿一致性（前后矛盾、术语写法）。
 * 每个问题两个出口 —— 「交给 AI 优化」带着它去第四步，「自己改」回第二步那一条。
 * 问题清单本身就是第四步的工作队列。
 */
import { useAssistantCtx } from '~/composables/assistant/assistantContext'
import { MIN_CHARS, type IssueKind } from '~/composables/assistant/useReportWorkspace'

const ctx = useAssistantCtx()
const { t } = ctx

const KINDS: IssueKind[] = ['cross', 'missing', 'vague', 'blank']
/** 问题清单的筛选：类别 + 清单表（0 = 全部） */
const kindFilter = ref<IssueKind | ''>('')
const partFilter = ref(0)

/**
 * 筛选指向的东西没了就自动回到「全部」：换了草稿、或回第二步取消纳入了别的表只剩一张时，
 * 那一排筛选按钮整个不显示，而 partFilter 还指着旧表 —— 问题清单变空、又没有地方能取消筛选
 */
watch(
  () => [ctx.issueByPart.map((p) => p.partNo).join(','), ctx.issueCount] as const,
  () => {
    if (partFilter.value && (ctx.issueByPart.length <= 1 || !ctx.issueByPart.some((p) => p.partNo === partFilter.value))) {
      partFilter.value = 0
    }
    if (kindFilter.value && !ctx.issueCount[kindFilter.value]) kindFilter.value = ''
  },
  { deep: true },
)

const shownIssues = computed(() =>
  ctx.issueRows.filter((r) =>
    (!kindFilter.value || r.kind === kindFilter.value)
    && (!partFilter.value || ctx.rowById.get(r.itemId)?.partNo === partFilter.value)),
)
const hasProblems = computed(() => ctx.issueRows.length > 0 || ctx.crossCount.issue > 0 || ctx.crossCount.warn > 0)
const KIND_CLASS: Record<string, string> = { cross: 'miss', missing: 'miss', vague: 'warn', blank: 'na' }
</script>

<template>
  <div class="panel" :class="{ 'is-hidden': ctx.step !== 3 }" data-panel="3">
    <div class="p-head">
      <span class="p-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M9 11l3 3 8-8" /><path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9" /></svg></span>
      <div><span class="p-num">{{ t('assistant.ckNum') }}</span><h2>{{ t('assistant.ckH2') }}</h2></div>
    </div>
    <p class="p-desc" v-html="t('assistant.ckP')"></p>

    <p v-if="!ctx.isLoggedIn" class="wk-empty">
      {{ t('assistant.dfNeedLogin') }}
      <NuxtLink class="btn btn-primary btn-sm" :to="ctx.loginLink">{{ t('assistant.dfLogin') }}</NuxtLink>
    </p>
    <template v-else>
      <!-- 运行条：开始 / 停止 · 进度 · 上次检查时间 -->
      <div class="ck-bar">
        <button v-if="ctx.checkState !== 'running'" class="btn btn-ink btn-sm" :disabled="!ctx.canCheck" @click="ctx.runCheck">
          {{ ctx.checkResult ? t('assistant.ckRerun') : t('assistant.ckRun') }}
        </button>
        <button v-else class="btn btn-ghost btn-sm" @click="ctx.stopCheck">{{ t('assistant.rvStop') }}</button>
        <template v-if="ctx.checkState === 'running'">
          <span class="meter ck-meter" aria-hidden="true"><i :style="{ width: ctx.checkPct + '%' }"></i></span>
          <span class="ck-status">{{ ctx.checkMsg || t('assistant.ckRunning') }} · {{ ctx.checkPct }}%</span>
        </template>
        <span v-else-if="ctx.checkResult" class="ck-status">{{ t('assistant.ckLast', { at: ctx.checkStamp(ctx.checkResult.at) }) }}</span>
        <span v-else class="ck-status">
          {{ ctx.noItems ? t('assistant.ckNoItems')
            : ctx.writtenChars < MIN_CHARS ? t('assistant.ckTooShort', { min: MIN_CHARS })
              : t('assistant.ckIntro') }}
        </span>
      </div>
      <p v-if="ctx.checkErr" class="rv-err wb-hint">{{ ctx.checkErr }}</p>
      <p v-if="ctx.checkResult && ctx.checkStale && ctx.checkState !== 'running'" class="ck-stale">{{ t('assistant.ckStale') }}</p>

      <p v-if="!ctx.checkResult && ctx.checkState !== 'running'" class="wk-empty">{{ t('assistant.ckNone') }}</p>

      <template v-if="ctx.checkResult && ctx.checkState !== 'running'">
        <p v-if="ctx.checkResult.truncated" class="rv-err">{{ t('assistant.ckTruncated') }}</p>
        <p v-if="ctx.checkResult.partial" class="rv-err">{{ t('assistant.rvPartial') }}</p>

        <!-- 概览：按类别，再按清单表（投稿时 CONSORT 与 STRICTA 是分开交的，缺口也要分开看） -->
        <div class="ck-sum">
          <span v-if="!hasProblems" class="ck-n ok">{{ t('assistant.ckAllClear') }}</span>
          <template v-else>
            <button
              type="button"
              class="ck-chip"
              :class="{ on: !kindFilter }"
              @click="kindFilter = ''"
            >{{ t('assistant.isAll', { n: ctx.issueRows.length }) }}</button>
            <button
              v-for="k in KINDS.filter((x) => ctx.issueCount[x])"
              :key="k"
              type="button"
              class="ck-chip"
              :class="[KIND_CLASS[k], { on: kindFilter === k }]"
              @click="kindFilter = kindFilter === k ? '' : k"
            >{{ t(`assistant.isKind.${k}`) }} {{ ctx.issueCount[k] }}</button>
          </template>
        </div>
        <div v-if="ctx.issueByPart.length > 1 && ctx.issueRows.length" class="ck-parts">
          <button
            v-for="p in ctx.issueByPart"
            :key="p.partNo"
            type="button"
            class="ck-chip"
            :class="{ on: partFilter === p.partNo }"
            @click="partFilter = partFilter === p.partNo ? 0 : p.partNo"
          >{{ t('assistant.isByPart', { title: p.title || p.partNo, n: p.n }) }}</button>
        </div>

        <!-- 逐条问题清单：一行一条，两个出口 -->
        <div v-if="ctx.issueRows.length" class="subh ck-sec">{{ t('assistant.ckItemsTitle') }}</div>
        <ul v-if="shownIssues.length" class="chk ck-list is-list">
          <li v-for="r in shownIssues" :key="r.itemId" :class="KIND_CLASS[r.kind]">
            <span class="is-no">{{ ctx.rowById.get(r.itemId)?.no || r.itemId }}</span>
            <span class="ctext">
              <b>{{ ctx.rowById.get(r.itemId)?.text }}</b>
              <span v-if="r.reason">{{ r.reason }}</span>
              <span class="is-act">
                <button type="button" class="btn btn-primary btn-sm" @click="ctx.optimizeItem(r.itemId)">{{ t('assistant.toOptimize') }}</button>
                <button type="button" class="btn btn-ghost btn-sm" @click="ctx.editItem(r.itemId)">{{ t('assistant.toEdit') }}</button>
              </span>
            </span>
            <span class="cstat">{{ t(`assistant.isKind.${r.kind}`) }}</span>
          </li>
        </ul>

        <!-- 全稿一致性：按规则列，引文可点回条目 -->
        <div v-if="ctx.crossChecks.length" class="subh ck-sec">{{ t('assistant.ckCrossTitle') }}</div>
        <ul v-if="ctx.crossChecks.length" class="chk ck-list">
          <li v-for="c in ctx.crossChecks" :key="c.key" :class="ctx.CROSS_CLASS[c.status]">
            <span class="ci">
              <svg v-if="c.status === 'ok'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><path d="M20 6 9 17l-5-5" /></svg>
              <svg v-else-if="c.status === 'warn'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M12 8v5M12 16h.01" /></svg>
              <svg v-else-if="c.status === 'issue'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><path d="M18 6 6 18M6 6l12 12" /></svg>
              <svg v-else-if="c.status === 'na'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="8" /><path d="m7 17 10-10" /></svg>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M5 12h14" /></svg>
            </span>
            <span class="ctext">
              <b><em>{{ t(`assistant.ckKind.${c.kind}`) }}</em>{{ ctx.ruleTitle(c.key) }}</b>
              <span v-if="!c.findings.length">{{ t(`assistant.ckEmpty.${c.status}`) }}</span>
              <span v-for="(f, i) in c.findings" :key="i" class="ckf" :class="f.severity">
                <u v-if="f.evidence">「{{ f.evidence }}」</u>
                <small v-if="f.evidence && f.located === 'no'" class="ev-unlocated">{{ t('assistant.evUnlocated') }}</small>
                {{ f.detail }}
                <b v-if="f.suggestion">{{ t('assistant.ckSuggest') }}{{ f.suggestion }}</b>
                <!-- 每条引文对应的条目，两个出口：交给 AI 优化 / 回第二步自己改 -->
                <span v-if="ctx.itemsOfQuote(f.evidence).length" class="ck-goto">
                  <span v-for="id in ctx.itemsOfQuote(f.evidence)" :key="id" class="ck-goto-item">
                    {{ t('assistant.ckItemNo', { no: ctx.rowById.get(id)?.no || id }) }}
                    <button type="button" class="src-jump" @click="ctx.optimizeItem(id)">{{ t('assistant.toOptimize') }}</button>
                    <button type="button" class="src-jump" @click="ctx.editItem(id)">{{ t('assistant.toEdit') }}</button>
                  </span>
                </span>
              </span>
              <span v-if="c.capped">{{ t('assistant.ckCapped', { n: c.findings.length }) }}</span>
            </span>
            <span class="cstat">{{ t(`assistant.ckStatus.${c.status}`) }}</span>
          </li>
        </ul>
        <p class="tmpl-note" style="margin:10px 0 0">{{ t('assistant.ckDesc') }}</p>
      </template>
    </template>

    <div class="step-foot">
      <button class="btn btn-ghost btn-sm" @click="ctx.go(2)">
        <span class="arrow" aria-hidden="true">←</span> {{ t('assistant.backWrite') }}
      </button>
      <button class="btn btn-primary btn-sm" @click="ctx.go(4)">
        {{ t('assistant.goRefine') }} <span class="arrow" aria-hidden="true">→</span>
      </button>
    </div>
  </div>
</template>
