<script setup lang="ts">
/**
 * ④ AI 优化：两个页签 —— 逐条优化 · 整篇成文。
 *
 * **逐条优化**：左边队列只是选择器（一行一条、一个「处理」），右边是**唯一**的工作区：
 * 当前正文 → 诊断 → 补充事实 → 生成 → 建议与原文并排 → 采用 / 追加 / 放弃。
 * 顶上一条「一键优化」把队列里的条目一次跑完（分钟级，走 worker），产出的是**待审阅的建议**，
 * 逐条看或「全部采用」才写回；生成之后又手改过的条目判「已过时」，不让采用。
 *
 * **整篇成文**：按章节把条目写成连贯正文，只读预览。每段标着取材于哪几条，点过去改条目、
 * 再「重新生成本章」。每章写完由代码核对（数字、占位、条目覆盖、穴位代码），不通过的标出原因。
 */
import { useAssistantCtx } from '~/composables/assistant/assistantContext'
import { MAX_ITEM_CHARS, REFINE_NOTE_MAX } from '~/composables/assistant/useReportWorkspace'

const ctx = useAssistantCtx()
const { t } = ctx

const tab = ref<'items' | 'render'>('items')
const KIND_CLASS: Record<string, string> = { cross: 'miss', missing: 'miss', vague: 'warn', blank: 'na', ok: 'ok' }

const id = computed(() => ctx.refineId)
const current = computed(() => (id.value != null ? ctx.body[id.value] ?? '' : ''))
const suggestion = computed(() => (id.value != null ? ctx.suggestionOf(id.value) : null))
const stale = computed(() => Boolean(suggestion.value && ctx.isStale(suggestion.value)))
const versions = computed(() => (id.value != null ? ctx.suggestionsOf(id.value) : []))
const verIndex = computed(() => versions.value.findIndex((s) => s.suggestionId === suggestion.value?.suggestionId) + 1)
/** 空条目又没写补充事实：按钮置灰并说明原因 */
const needNote = computed(() => id.value != null && !current.value.trim() && !(ctx.refineNotes[id.value] ?? '').trim())
const findings = computed(() => (id.value != null ? ctx.findingsByItem.get(id.value) ?? [] : []))
const verdict = computed(() => (id.value != null ? ctx.verdictById.get(id.value) ?? null : null))

/** 一键优化的范围：检查过就默认「有问题的条目」，没检查过只能「全部已填」 */
const batchRange = ref<'issues' | 'filled'>('issues')
const range = computed(() => (ctx.checkResult ? batchRange.value : 'filled'))
const live = computed(() => ctx.aiLive)
const liveKind = computed(() => (ctx.aiRunning ? ctx.aiLive?.kind ?? '' : ''))
</script>

<template>
  <div class="panel" :class="{ 'is-hidden': ctx.step !== 4 }" data-panel="4">
    <div class="p-head">
      <span class="p-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3l1.9 4.6L18.5 9.5 13.9 11.4 12 16l-1.9-4.6L5.5 9.5l4.6-1.9z" /><path d="M19 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z" /></svg></span>
      <div><span class="p-num">{{ t('assistant.rfNum') }}</span><h2>{{ t('assistant.rfH2') }}</h2></div>
    </div>
    <p class="p-desc" v-html="t('assistant.rfP')"></p>

    <p v-if="!ctx.isLoggedIn" class="wk-empty">
      {{ t('assistant.dfNeedLogin') }}
      <NuxtLink class="btn btn-primary btn-sm" :to="ctx.loginLink">{{ t('assistant.dfLogin') }}</NuxtLink>
    </p>
    <p v-else-if="!ctx.checklistRows.length" class="wk-empty">{{ t('assistant.tplEmpty') }}</p>
    <template v-else>
      <div class="rf-tabs" role="tablist">
        <button type="button" role="tab" :aria-selected="tab === 'items'" :class="{ on: tab === 'items' }" @click="tab = 'items'">
          {{ t('assistant.rfTabItems') }}
          <small v-if="ctx.adoptable.length">{{ t('assistant.rfPendingN', { n: ctx.adoptable.length }) }}</small>
        </button>
        <button type="button" role="tab" :aria-selected="tab === 'render'" :class="{ on: tab === 'render' }" @click="tab = 'render'">
          {{ t('assistant.rfTabRender') }}
          <small v-if="ctx.render && ctx.renderStaleN">{{ t('assistant.rdStaleN', { n: ctx.renderStaleN }) }}</small>
        </button>
      </div>

      <!-- 分钟级任务的进度条：两个页签共用（同一时间只跑一个） -->
      <div v-if="ctx.aiRunning && live" class="ck-bar">
        <span class="meter ck-meter" aria-hidden="true"><i :style="{ width: live.progress + '%' }"></i></span>
        <span class="ck-status">
          {{ t(liveKind === 'render' ? 'assistant.rdRunning' : 'assistant.bgRunning', { p: live.progress, phase: live.phase }) }}
        </span>
        <button type="button" class="btn btn-ghost btn-sm" @click="ctx.stopAi">{{ t('assistant.rvStop') }}</button>
      </div>
      <p v-if="ctx.aiErr" class="rv-err wb-hint">{{ ctx.aiErr }}</p>
      <p v-if="ctx.aiDone && ctx.aiDone.kind === 'refine'" class="df-imp-ok">
        {{ t(ctx.aiDone.stopped ? 'assistant.bgStopped' : 'assistant.bgDone', { n: ctx.aiDone.done, failed: ctx.aiDone.failed, skipped: ctx.aiDone.skipped }) }}
        <template v-if="ctx.aiDone.tooLong">{{ t('assistant.bgTooLong', { n: ctx.aiDone.tooLong }) }}</template>
        <template v-if="ctx.aiDone.ignored">{{ t('assistant.bgIgnored', { n: ctx.aiDone.ignored }) }}</template>
        <template v-if="ctx.aiDone.unchanged">{{ t('assistant.bgUnchanged', { n: ctx.aiDone.unchanged }) }}</template>
      </p>

      <!-- ================================================================ 逐条优化 -->
      <div v-show="tab === 'items'">
        <p v-if="!ctx.checkResult" class="route-note"><span>{{ t('assistant.rfNoCheck') }}</span></p>

        <!-- 一键优化：把一批条目一次跑完，产出待审阅的建议 -->
        <div class="rf-batch">
          <span class="rf-batch-t">{{ t('assistant.bgTitle') }}</span>
          <template v-if="ctx.checkResult">
            <label><input v-model="batchRange" type="radio" value="issues" /> {{ t('assistant.bgIssues', { n: ctx.issueRows.length }) }}</label>
            <label><input v-model="batchRange" type="radio" value="filled" /> {{ t('assistant.bgFilled') }}</label>
          </template>
          <span v-else class="rf-batch-note">{{ t('assistant.bgFilled') }}</span>
          <button class="btn btn-primary btn-sm" :disabled="ctx.aiRunning || !ctx.canEdit" @click="ctx.runBatch(range)">{{ t('assistant.bgRun') }}</button>
          <span class="rf-batch-sep" aria-hidden="true"></span>
          <button class="btn btn-ink btn-sm" :disabled="!ctx.adoptable.length || ctx.adoptBusy" @click="ctx.adoptAll">
            {{ t('assistant.sgAdoptAll', { n: ctx.adoptable.length }) }}
          </button>
          <small v-if="ctx.staleSuggestionN" class="rf-batch-note">{{ t('assistant.sgStaleN', { n: ctx.staleSuggestionN }) }}</small>
        </div>
        <p class="rf-batch-hint">{{ t('assistant.bgHint') }}</p>
        <p v-if="ctx.adoptAllMsg" class="df-imp-ok">{{ ctx.adoptAllMsg }}</p>

        <div class="rf-grid">
          <aside class="rf-queue">
            <div class="rf-src" role="group">
              <button
                type="button"
                :class="{ on: ctx.queueSource === 'check' && ctx.checkResult }"
                :disabled="!ctx.checkResult"
                @click="ctx.queueSource = 'check'"
              >{{ t('assistant.rfSrcCheck', { n: ctx.issueRows.length }) }}</button>
              <button
                type="button"
                :class="{ on: ctx.queueSource === 'all' || !ctx.checkResult }"
                @click="ctx.queueSource = 'all'"
              >{{ t('assistant.rfSrcAll') }}</button>
            </div>
            <p v-if="!ctx.queueRows.length" class="rf-qempty">{{ t('assistant.rfQueueEmpty') }}</p>
            <ul v-else class="rf-list">
              <li v-for="r in ctx.queueRows" :key="r.itemId">
                <button
                  type="button"
                  class="rf-item"
                  :class="{ on: r.itemId === ctx.refineId }"
                  :aria-current="r.itemId === ctx.refineId ? 'true' : undefined"
                  @click="ctx.pickRefine(r.itemId)"
                >
                  <span class="tnav-no">{{ ctx.rowById.get(r.itemId)?.no || r.itemId }}</span>
                  <span class="tnav-tx">{{ ctx.rowById.get(r.itemId)?.text }}</span>
                  <span class="rf-badges">
                    <span class="rf-kind" :class="KIND_CLASS[r.kind]">{{ t(`assistant.isKind.${r.kind}`) }}</span>
                    <span v-if="ctx.suggestionState(r.itemId)" class="rf-kind" :class="ctx.suggestionState(r.itemId) === 'stale' ? 'na' : 'sg'">
                      {{ t(`assistant.sgState.${ctx.suggestionState(r.itemId)}`) }}
                    </span>
                  </span>
                </button>
              </li>
            </ul>
          </aside>

          <section v-if="ctx.refineRow && id != null" class="tpane rf-pane">
            <header class="tp-head">
              <span class="tp-crumb">
                {{ ctx.refineRow.partTitle }}<template v-if="ctx.refineRow.partTitle && ctx.refineRow.domain"> · </template>{{ ctx.refineRow.domain }}
              </span>
              <div class="tp-title">
                <span class="tp-no">{{ ctx.refineRow.no || ctx.refineRow.seq }}</span>
                <span class="req" :class="ctx.refineRow.required ? 'must' : 'opt'">
                  {{ t(ctx.refineRow.required ? 'assistant.tplRequired' : 'assistant.tplOptional') }}
                </span>
              </div>
            </header>
            <div class="tp-req">
              <div class="subh">{{ t('assistant.tplRequirement') }}</div>
              <p class="tp-req-text">{{ ctx.refineRow.text }}</p>
            </div>

            <div v-if="findings.length || verdict" class="tp-issues">
              <div class="subh" style="margin:0">{{ t('assistant.rfDiag') }}</div>
              <p v-for="(x, i) in findings" :key="'c' + i" class="tp-issue" :class="x.finding.severity">
                <b>{{ ctx.ruleTitle(x.check.key) }}</b>
                {{ x.finding.detail }}
                <span v-if="x.finding.suggestion">{{ t('assistant.ckSuggest') }}{{ x.finding.suggestion }}</span>
              </p>
              <p v-if="verdict" class="tp-issue warn">
                <b>{{ t(`assistant.isKind.${verdict.status === 'vague' ? 'vague' : 'missing'}`) }}</b>
                {{ verdict.reason }}
              </p>
            </div>

            <div class="rf-cols" :class="{ two: suggestion }">
              <div>
                <label class="subh" :for="'rf-ta-' + id">{{ t('assistant.rfCurrent') }}</label>
                <textarea
                  :id="'rf-ta-' + id"
                  :key="'rf-' + id"
                  v-model="ctx.body[id]"
                  class="df-ta tp-ta"
                  :class="{ filled: current.trim() }"
                  :placeholder="t('assistant.rfEmpty')"
                  :maxlength="MAX_ITEM_CHARS"
                  :readonly="ctx.draftBusy || ctx.adoptBusy"
                  rows="8"
                  @input="ctx.touchDraft"
                ></textarea>
              </div>
              <div v-if="suggestion" class="tp-ai-out rf-out">
                <div class="rf-out-head">
                  <span class="subh" style="margin:0">{{ t('assistant.rfSuggest') }}</span>
                  <span v-if="versions.length > 1" class="rf-ver">
                    <button type="button" :disabled="verIndex <= 1" :aria-label="t('assistant.rfPrev')" @click="ctx.pickSuggestion(id, -1)">‹</button>
                    {{ t('assistant.rfVer', { i: verIndex, n: versions.length }) }}
                    <button type="button" :disabled="verIndex >= versions.length" :aria-label="t('assistant.rfNext')" @click="ctx.pickSuggestion(id, 1)">›</button>
                  </span>
                </div>
                <p class="tp-ai-text">{{ suggestion.content }}</p>
                <p v-if="stale" class="tp-ai-warn">{{ t('assistant.sgStale') }}</p>
                <p v-else class="tp-ai-warn">{{ t('assistant.aiVerify') }}</p>
                <div class="tp-ai-bar">
                  <button class="btn btn-primary btn-sm" :disabled="ctx.adoptBusy || stale" @click="ctx.adoptRefine(id, 'replace')">{{ t('assistant.aiReplace') }}</button>
                  <button v-if="current.trim()" class="btn btn-ghost btn-sm" :disabled="ctx.adoptBusy || stale" @click="ctx.adoptRefine(id, 'append')">{{ t('assistant.aiAppend') }}</button>
                  <button class="btn btn-ghost btn-sm" @click="ctx.discardSuggestion(id)">{{ t('assistant.aiDiscard') }}</button>
                  <small v-if="suggestion.modelLabel" class="tp-ai-model">{{ suggestion.modelLabel }}</small>
                </div>
              </div>
            </div>

            <div class="tp-ai">
              <label class="subh" :for="'rf-note-' + id">{{ t('assistant.rfNoteLabel') }}</label>
              <textarea
                :id="'rf-note-' + id"
                :key="'rfn-' + id"
                v-model="ctx.refineNotes[id]"
                class="df-ta tp-ai-note"
                :placeholder="t('assistant.aiNotePh')"
                :maxlength="REFINE_NOTE_MAX"
                rows="2"
              ></textarea>
              <div class="tp-ai-bar">
                <button class="btn btn-primary btn-sm" :disabled="!ctx.canRefine(id)" @click="ctx.runRefine(id)">
                  {{ ctx.refineBusy ? t('assistant.aiRunning') : suggestion ? t('assistant.rfRerun') : t('assistant.rfRun') }}
                </button>
                <span class="tp-ai-hint">{{ needNote ? t('assistant.rfNeedNote') : t('assistant.aiHint') }}</span>
              </div>
              <p v-if="ctx.refineErr" class="rv-err">{{ ctx.refineErr }}</p>
            </div>
          </section>
        </div>
      </div>

      <!-- ================================================================ 整篇成文 -->
      <div v-show="tab === 'render'" class="rd">
        <div class="rd-bar">
          <button class="btn btn-primary btn-sm" :disabled="ctx.aiRunning || !ctx.canEdit" @click="ctx.runRender()">
            {{ ctx.render ? t('assistant.rdRerun') : t('assistant.rdRun') }}
          </button>
          <span v-if="ctx.render" class="ck-status">
            {{ t('assistant.rdLast', { at: ctx.checkStamp(ctx.render.createTime), n: ctx.render.sections.length }) }}
            <b v-if="ctx.renderBadN" class="ck-n miss">{{ t('assistant.rdBadN', { n: ctx.renderBadN }) }}</b>
            <b v-if="ctx.renderStaleN" class="ck-n warn">{{ t('assistant.rdStaleN', { n: ctx.renderStaleN }) }}</b>
          </span>
        </div>
        <p class="rf-batch-hint">{{ ctx.hasSource ? t('assistant.rdHintImported') : t('assistant.rdHint') }}</p>

        <p v-if="!ctx.render" class="wk-empty">{{ t('assistant.rdEmpty') }}</p>
        <article v-else class="rd-doc" :lang="ctx.render.lang === 'en' ? 'en' : 'zh-CN'">
          <h2 v-if="ctx.render.title" class="rd-title">{{ ctx.render.title }}</h2>
          <section v-for="(s, k) in ctx.render.sections" :key="s.domain" class="rd-sec" :class="{ bad: !s.ok, stale: s.stale }">
            <!-- 一级部分（如「2 方法」）只在第一次出现时出标题，下面的小节各出二级标题 -->
            <h3 v-if="s.part && s.part !== ctx.render.sections[k - 1]?.part" class="rd-part">{{ s.part }}</h3>
            <header class="rd-sec-h">
              <h4 v-if="!s.part || s.domain !== s.part">{{ s.domain }}</h4>
              <span v-else></span>
              <span v-if="s.stale" class="ck-n warn">{{ t('assistant.rdStale') }}</span>
              <button type="button" class="btn btn-ghost btn-sm" :disabled="ctx.aiRunning" @click="ctx.runRender(s.domain)">{{ t('assistant.rdRedoSection') }}</button>
            </header>
            <p v-if="s.error" class="rv-err">{{ t('assistant.rdSectionFailed') }}</p>
            <ul v-if="s.issues.length" class="rd-issues">
              <li v-for="(x, i) in s.issues" :key="i">{{ ctx.renderIssueText(x) }}</li>
            </ul>
            <div v-for="(p, i) in s.paragraphs" :key="i" class="rd-p">
              <p>{{ p.text }}</p>
              <span v-if="p.itemIds.length" class="rd-src">
                {{ t('assistant.rdFrom') }}
                <button
                  v-for="iid in p.itemIds"
                  :key="iid"
                  type="button"
                  class="src-jump"
                  @click="ctx.editItem(iid)"
                >{{ ctx.rowById.get(iid)?.no || iid }}</button>
              </span>
            </div>
          </section>
        </article>
      </div>
    </template>

    <div class="step-foot">
      <button class="btn btn-ghost btn-sm" @click="ctx.go(3)">
        <span class="arrow" aria-hidden="true">←</span> {{ t('assistant.goRecheck') }}
      </button>
      <button class="btn btn-primary btn-sm" @click="ctx.go(5)">
        {{ t('assistant.goDeliver') }} <span class="arrow" aria-hidden="true">→</span>
      </button>
    </div>
  </div>
</template>
