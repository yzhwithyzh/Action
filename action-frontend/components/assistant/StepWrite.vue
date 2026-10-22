<script setup lang="ts">
/**
 * ② 报告撰写：人写事实的地方。
 *
 * 工作台条（草稿 · 名称 · 完成度 · 导入 / 保存）→ 清单表页签（可取消纳入）→ 左导航 + 右面板。
 * AI 在这一步**只在空条目上**露面（「让 AI 起个草」，要点必填）；已填条目的完善、润色都在第四步 ——
 * 「写」和「改」挤在一屏里，是五步拆回来的直接原因。
 */
import { useAssistantCtx } from '~/composables/assistant/assistantContext'
import { IMPORT_ACCEPT, MAX_ITEM_CHARS, REFINE_NOTE_MAX } from '~/composables/assistant/useReportWorkspace'

const ctx = useAssistantCtx()
const { t, pick } = ctx

/** 当前条目是空的 —— 只有这时才露出「AI 起草」 */
const activeEmpty = computed(() => Boolean(ctx.activeRow) && !(ctx.body[ctx.activeRow!.itemId] ?? '').trim())
const activeSuggestion = computed(() => (ctx.activeRow ? ctx.suggestionOf(ctx.activeRow.itemId) : null))
const hasNote = computed(() => Boolean(ctx.activeRow && (ctx.refineNotes[ctx.activeRow.itemId] ?? '').trim()))

/** 函数式 ref：把 DOM 节点交回工作区（换条目时要滚动、聚焦它们） */
const setNav = (el: unknown) => { ctx.navEl = el as HTMLElement | null }
const setPane = (el: unknown) => { ctx.paneEl = el as HTMLElement | null }
const setTa = (el: unknown) => { ctx.paneTa = el as HTMLTextAreaElement | null }
const setImport = (el: unknown) => { ctx.importInput = el as HTMLInputElement | null }

/**
 * 勾选 / 取消纳入。取消的是最后一张时工作区会拒绝（至少留一张），而状态没变、绑定的值也没变，
 * Vue 不会去动 DOM —— 复选框就停在「已取消」上与状态对不上。所以事后按状态拨回去
 */
function onToggle(e: Event, partNo: number) {
  ctx.togglePart(partNo)
  ;(e.target as HTMLInputElement).checked = ctx.partIncluded(partNo)
}
</script>

<template>
  <div class="panel" :class="{ 'is-hidden': ctx.step !== 2 }" data-panel="2">
    <div class="p-head">
      <span class="p-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M8 8h8M8 12h8M8 16h5" /></svg></span>
      <div><span class="p-num">{{ t('assistant.s028') }}</span><h2>{{ t('assistant.s029') }}</h2></div>
    </div>
    <p class="p-desc" v-html="t('assistant.s030')"></p>
    <!-- 第一步选了「已经有稿件」、而当前草稿还是空的：把导入口直接摆到眼前 -->
    <p v-if="ctx.stage === 'manuscript' && ctx.canEdit && !ctx.filledIds.size && !ctx.importBusy" class="route-note">
      <span>{{ t('assistant.importHint') }}</span>
      <button class="btn btn-primary btn-sm" @click="ctx.importInput?.click()">{{ t('assistant.dfImport') }}</button>
    </p>
    <!-- 同一份规范服务好几类研究，离开第一步后只剩规范 chip 就分不出来了。专属提示是这几类之间唯一的差别 -->
    <div v-if="ctx.matched && ctx.matchTips.length" class="type-tips">
      <span class="tt-type">{{ t('assistant.tipFor', { type: pick(ctx.matched, 'name') }) }}</span>
      <p v-for="(tip, k) in ctx.matchTips" :key="k">{{ tip }}</p>
    </div>

    <!--
      先选「用哪份规范写」（sql/056：如 RCT = CONSORT-A / TIDieR-A）。一份草稿只对应一份规范，
      切换就是换一份草稿：工作区会先存当前这份，再列出那份规范下的草稿。
      放在工作台条外面 —— 选到一份还没录条目的规范时工作台条不显示，切换口不能跟着消失
    -->
    <div v-if="ctx.checklistOptions.length > 1" class="glsw">
      <span class="glsw-label">{{ t('assistant.glSwitch') }}</span>
      <div class="ptabs glsw-tabs" role="radiogroup" :aria-label="t('assistant.glSwitch')">
        <button
          v-for="(o, k) in ctx.checklistOptions"
          :key="o.code"
          type="button"
          class="ptab ptab-main glsw-opt"
          :class="{ on: o.code === ctx.checklistCode }"
          role="radio"
          :aria-checked="o.code === ctx.checklistCode"
          :disabled="ctx.draftBusy || ctx.saving"
          @click="ctx.chooseGuideline(o.code)"
        >
          <b>{{ o.code }}<em v-if="k === 0">{{ t('assistant.glHot') }}</em></b>
          <small :class="{ warn: !o.itemCount }">
            {{ o.itemCount ? t('assistant.glCount', { n: o.itemCount }) : t('assistant.glNoItems') }}
          </small>
        </button>
      </div>
      <p class="glsw-hint">{{ t('assistant.glHint') }}</p>
    </div>

    <!-- 工作台条：「我在编辑哪份草稿、依据哪份规范、填到哪儿了」压成一条，面板里只剩一个主体：清单本身 -->
    <div v-if="ctx.checklistRows.length" class="wb">
      <div class="wb-src" :aria-label="t('assistant.tplFrom')">
        <!-- 只摆当前这份规范：匹配卡上那排是展示标签（含「针灸专属条目」这类非规范），在这里会被当成「在用哪几份」 -->
        <div v-if="ctx.checklistCode" class="gchips">
          <b class="hot">{{ ctx.checklistCode }}</b>
        </div>
        <span class="wb-count">
          {{ t('assistant.tplCount', { n: ctx.checklistRows.length, m: ctx.checklistParts.length }) }}
        </span>
      </div>
      <template v-if="ctx.isLoggedIn">
        <span class="wb-sep" aria-hidden="true"></span>
        <select
          v-if="ctx.myDrafts.length"
          class="df-sel"
          :value="ctx.draftId ?? ''"
          :aria-label="t('assistant.dfSwitch')"
          :disabled="ctx.draftBusy"
          @change="ctx.openDraft(Number(($event.target as HTMLSelectElement).value))"
        >
          <option v-for="d in ctx.myDrafts" :key="d.draftId" :value="d.draftId">{{ d.title }}</option>
        </select>
        <input
          v-if="ctx.canEdit"
          id="dfTitle"
          v-model="ctx.draftTitle"
          class="wb-name"
          :placeholder="t('assistant.dfTitlePh')"
          :aria-label="t('assistant.dfTitleLabel')"
          maxlength="300"
          :readonly="ctx.draftBusy"
          @input="ctx.touchDraft"
        />
        <div v-if="ctx.canEdit" class="wb-prog">
          <span class="meter" aria-hidden="true"><i :style="{ width: ctx.donePct + '%' }"></i></span>
          <b :aria-label="t('assistant.dfProgress')">{{ ctx.requiredFilled }}<em>/{{ ctx.requiredIds.size }}</em></b>
        </div>
        <div class="wb-act">
          <span class="df-state" :class="{ dirty: ctx.dirty }">
            {{ ctx.dirty ? t('assistant.dfUnsaved') : ctx.savedAt ? t('assistant.dfSavedAt', { at: ctx.savedAt }) : '' }}
          </span>
          <button class="btn btn-ghost btn-sm" :disabled="ctx.draftBusy" @click="ctx.newDraft">
            {{ t('assistant.dfNew') }}
          </button>
          <!-- 导入已有稿件：用 label 包 input 而不是自己 click() 一个隐藏 input，前者原生可键盘聚焦 -->
          <label class="btn btn-ghost btn-sm df-import" :class="{ busy: ctx.importBusy }">
            <input :ref="setImport" type="file" :accept="IMPORT_ACCEPT" :disabled="ctx.importBusy || ctx.draftBusy" @change="ctx.pickImport" />
            <span>{{ ctx.importBusy ? t('assistant.dfImporting') : t('assistant.dfImport') }}</span>
          </label>
          <button class="btn btn-primary btn-sm" :disabled="ctx.saving || !ctx.dirty" @click="ctx.saveDraft">
            {{ ctx.saving ? t('assistant.dfSaving') : t('assistant.dfSave') }}
          </button>
          <button v-if="ctx.draftId" class="df-del" type="button" :disabled="ctx.draftBusy" @click="ctx.removeDraft">
            {{ t('assistant.dfDelete') }}
          </button>
        </div>
      </template>
      <NuxtLink v-else class="btn btn-primary btn-sm wb-act" :to="ctx.loginLink">{{ t('assistant.dfLogin') }}</NuxtLink>
    </div>
    <p v-if="ctx.checklistRows.length && !ctx.isLoggedIn" class="wb-hint">{{ t('assistant.dfNeedLogin') }}</p>
    <p v-if="ctx.draftErr" class="rv-err wb-hint">{{ ctx.draftErr }}</p>

    <!-- 导入进度与结果。解析是秒级的，条目映射是几分钟级的 worker 任务 -->
    <div v-if="ctx.importBusy" class="meter-box df-imp-bar">
      <span class="subh" style="margin:0;white-space:nowrap">{{ ctx.importMsg }}</span>
      <span class="meter" aria-hidden="true"><i :style="{ width: ctx.importPct + '%' }"></i></span>
      <b>{{ ctx.importPct }}%</b>
    </div>
    <p v-if="ctx.importErr" class="rv-err wb-hint">{{ ctx.importErr }}</p>
    <p v-else-if="ctx.importDone" class="df-imp-ok">
      {{ t('assistant.dfImportDone', {
        name: ctx.importDone.name, lines: ctx.importDone.lines,
        filled: ctx.importDone.filled, blank: Math.max(0, ctx.importDone.total - ctx.importDone.filled),
      }) }}
    </p>

    <!--
      清单表页签。一份规范可能含多张表（RCT：CONSORT 主表 / 摘要表 / STRICTA 表），
      投稿时它们是分开交的几张表，所以分开写、分开看，不再拼成一条长流水。
      每张表可以取消纳入：不计完成度、不参与检查与优化、不进导出，已写的内容保留。
      只有一张表时不画这一排，界面与原来一样。
    -->
    <div v-if="ctx.checklistParts.length > 1" class="ptabs" role="tablist" :aria-label="t('assistant.partTabsAria')">
      <div
        v-for="p in ctx.checklistParts"
        :key="p.partNo"
        class="ptab"
        :class="{ on: p.partNo === ctx.currentPart, off: !ctx.partIncluded(p.partNo) }"
      >
        <button
          type="button"
          role="tab"
          class="ptab-main"
          :aria-selected="p.partNo === ctx.currentPart"
          @click="ctx.selectPart(p.partNo)"
        >
          <b>{{ p.title || t('assistant.partUntitled', { n: p.partNo }) }}</b>
          <small v-if="ctx.canEdit">
            {{ t('assistant.partProgress', { a: ctx.partProgress(p.partNo).filled, b: ctx.partProgress(p.partNo).total }) }}
          </small>
          <small v-else>{{ t('assistant.partCount', { n: p.total }) }}</small>
        </button>
        <label v-if="ctx.canEdit" class="ptab-inc" :title="t('assistant.partInclude')">
          <input type="checkbox" :checked="ctx.partIncluded(p.partNo)" @change="onToggle($event, p.partNo)" />
          <span>{{ t('assistant.partInclude') }}</span>
        </label>
      </div>
    </div>
    <p v-if="ctx.partErr" class="rv-err wb-hint">{{ ctx.partErr }}</p>
    <p v-if="ctx.canEdit && ctx.checklistParts.length > 1 && !ctx.partIncluded(ctx.currentPart)" class="part-off-note">
      {{ t('assistant.partExcluded') }}
    </p>

    <!--
      左导航 + 右面板：左边按维度折叠（只列当前这张表）、只列条目号与一句要求；
      右边一次只展开当前这一条：要求 → 示例 → 撰写框。
    -->
    <p v-if="!ctx.checklistRows.length" class="tmpl-empty tpl-empty-box">
      {{ ctx.ckLoading ? t('assistant.tplLoading') : t('assistant.tplEmpty') }}
    </p>
    <div v-else class="tpl-grid">
      <nav :ref="setNav" class="tnav" :aria-label="t('assistant.tplNavAria')">
        <div v-if="ctx.checklistParts.length === 1 && ctx.currentPartInfo?.title" class="tnav-part">{{ ctx.currentPartInfo.title }}</div>
        <div v-for="g in ctx.navGroups" :key="g.key" class="tnav-dom" :class="{ open: ctx.isDomainOpen(g.key) }">
          <button
            type="button"
            class="tnav-dh"
            :aria-expanded="ctx.isDomainOpen(g.key)"
            :aria-controls="'tnav-g-' + g.key"
            @click="ctx.toggleDomain(g.key)"
          >
            <span class="tnav-dt">{{ g.domain || t('assistant.tplNavOther') }}</span>
            <!-- 已填/总数只对能编辑的人有意义；匿名访客看到 0/12 只会以为数据没了 -->
            <span v-if="ctx.canEdit" class="tnav-dc">{{ t('assistant.tplDomainCount', { a: g.filled, b: g.total }) }}</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
          </button>
          <ul v-show="ctx.isDomainOpen(g.key)" :id="'tnav-g-' + g.key" class="tnav-list">
            <li v-for="it in g.items" :key="it.itemId">
              <button
                type="button"
                class="tnav-item"
                :class="{ on: it.itemId === ctx.currentId, filled: it.filled, over: it.over }"
                :aria-current="it.itemId === ctx.currentId ? 'true' : undefined"
                @click="ctx.selectItem(it.itemId)"
              >
                <span class="tnav-no">{{ it.no || it.seq }}</span>
                <span class="tnav-tx">{{ it.text }}</span>
                <!-- 第三步检查挂过来的标记：红 = 与别处矛盾，黄 = 描述模糊 / 没答到点子上 -->
                <span
                  v-if="ctx.canEdit && ctx.flagOf(it.itemId)"
                  class="tnav-flag"
                  :class="ctx.flagOf(it.itemId)"
                  :title="t(ctx.flagOf(it.itemId) === 'cross' ? 'assistant.ckFlagCross' : 'assistant.ckFlagVague')"
                >!</span>
                <span v-if="ctx.canEdit" class="tnav-dot" aria-hidden="true"></span>
              </button>
            </li>
          </ul>
        </div>
      </nav>

      <section v-if="ctx.activeRow" :ref="setPane" class="tpane" :aria-label="t('assistant.tplRequirement') + ' ' + (ctx.activeRow.no || ctx.activeRow.seq)">
        <header class="tp-head">
          <span class="tp-crumb">
            {{ ctx.activeRow.partTitle }}<template v-if="ctx.activeRow.partTitle && ctx.activeRow.domain"> · </template>{{ ctx.activeRow.domain }}
          </span>
          <div class="tp-title">
            <span class="tp-no">{{ ctx.activeRow.no || ctx.activeRow.seq }}</span>
            <span class="req" :class="ctx.activeRow.required ? 'must' : 'opt'">
              {{ t(ctx.activeRow.required ? 'assistant.tplRequired' : 'assistant.tplOptional') }}
            </span>
            <span v-if="ctx.activeRow.isExt" class="req ext">{{ t('assistant.tplExtTag') }}</span>
          </div>
        </header>

        <div class="tp-req">
          <div class="subh">{{ t('assistant.tplRequirement') }}</div>
          <p class="tp-req-text">{{ ctx.activeRow.text }}</p>
          <p v-if="ctx.activeRow.ext" class="tmpl-ext"><b>{{ ctx.activeRow.extLabel }}</b>{{ ctx.activeRow.ext }}</p>
        </div>

        <!-- 示例由后台逐条录入，为空就说「暂无」——不摆占位假文，那段字会被照着抄进论文 -->
        <div class="tp-ex">
          <div class="subh">{{ t('assistant.tplExample') }}</div>
          <p v-if="ctx.activeRow.example" class="tp-ex-text">{{ ctx.activeRow.example }}</p>
          <p v-else class="tp-ex-empty">{{ t('assistant.tplExampleEmpty') }}</p>
        </div>

        <!-- 只渲染当前这一条的输入框。`:key` 让换条目时重建，撤销栈与滚动位置不串到下一条 -->
        <div v-if="ctx.canEdit" class="tp-write">
          <label class="subh" :for="'tp-ta-' + ctx.activeRow.itemId">{{ t('assistant.tplWrite') }}</label>
          <textarea
            :id="'tp-ta-' + ctx.activeRow.itemId"
            :key="ctx.activeRow.itemId"
            :ref="setTa"
            v-model="ctx.body[ctx.activeRow.itemId]"
            class="df-ta tp-ta"
            :class="{ filled: (ctx.body[ctx.activeRow.itemId] ?? '').trim() }"
            :aria-label="(ctx.activeRow.no || ctx.activeRow.seq) + ' ' + ctx.activeRow.text"
            :placeholder="t('assistant.dfItemPh')"
            :maxlength="MAX_ITEM_CHARS"
            :readonly="ctx.draftBusy"
            rows="8"
            @input="ctx.touchDraft"
          ></textarea>
        </div>

        <!-- 第三步检查对这一条的意见：只摆出来、指个路，改在第四步 -->
        <div
          v-if="ctx.canEdit && (ctx.findingsByItem.get(ctx.activeRow.itemId)?.length || ctx.verdictByItem.get(ctx.activeRow.itemId))"
          class="tp-issues"
        >
          <p v-for="(x, i) in ctx.findingsByItem.get(ctx.activeRow.itemId) ?? []" :key="'c' + i" class="tp-issue" :class="x.finding.severity">
            <b>{{ ctx.ruleTitle(x.check.key) }}</b>
            {{ x.finding.detail }}
            <span v-if="x.finding.suggestion">{{ t('assistant.ckSuggest') }}{{ x.finding.suggestion }}</span>
          </p>
          <p v-if="ctx.verdictByItem.get(ctx.activeRow.itemId)" class="tp-issue warn">
            <b>{{ t(ctx.verdictByItem.get(ctx.activeRow.itemId)!.status === 'vague' ? 'assistant.rvStatVague' : 'assistant.ckOffPoint') }}</b>
            {{ ctx.verdictByItem.get(ctx.activeRow.itemId)!.reason }}
          </p>
          <button type="button" class="src-jump" @click="ctx.optimizeItem(ctx.activeRow.itemId)">{{ t('assistant.goOptimize') }}</button>
        </div>

        <!--
          让 AI 起个草：**只对空条目**。要点必填 —— 只凭条目要求，模型写出来的是一段满屏【待补充】的空壳；
          要点是作者给的事实（会被写进正文），不是聊天框。已填条目的完善在第四步
        -->
        <div v-if="ctx.canEdit && activeEmpty" class="tp-ai">
          <template v-if="!activeSuggestion">
            <label class="subh" :for="'tp-ai-' + ctx.activeRow.itemId">{{ t('assistant.draftAiTitle') }}</label>
            <textarea
              :id="'tp-ai-' + ctx.activeRow.itemId"
              :key="'ai-' + ctx.activeRow.itemId"
              v-model="ctx.refineNotes[ctx.activeRow.itemId]"
              class="df-ta tp-ai-note"
              :placeholder="t('assistant.draftAiPh')"
              :maxlength="REFINE_NOTE_MAX"
              rows="3"
            ></textarea>
            <div class="tp-ai-bar">
              <button class="btn btn-primary btn-sm" :disabled="!ctx.canRefine(ctx.activeRow.itemId)" @click="ctx.runRefine(ctx.activeRow.itemId)">
                {{ ctx.refineBusy ? t('assistant.aiRunning') : t('assistant.draftAiRun') }}
              </button>
              <span class="tp-ai-hint">{{ hasNote ? t('assistant.aiHint') : t('assistant.draftAiNeedNote') }}</span>
            </div>
          </template>
          <p v-if="ctx.refineErr" class="rv-err">{{ ctx.refineErr }}</p>
          <div v-if="activeSuggestion" class="tp-ai-out">
            <div class="subh">{{ t('assistant.aiResult') }}</div>
            <p class="tp-ai-text">{{ activeSuggestion.content }}</p>
            <p class="tp-ai-warn">{{ t('assistant.aiVerify') }}</p>
            <div class="tp-ai-bar">
              <button class="btn btn-primary btn-sm" :disabled="ctx.adoptBusy" @click="ctx.adoptRefine(ctx.activeRow.itemId, 'replace')">{{ t('assistant.aiReplace') }}</button>
              <button
                v-if="(ctx.body[ctx.activeRow.itemId] ?? '').trim()"
                class="btn btn-ghost btn-sm"
                :disabled="ctx.adoptBusy"
                @click="ctx.adoptRefine(ctx.activeRow.itemId, 'append')"
              >{{ t('assistant.aiAppend') }}</button>
              <button class="btn btn-ghost btn-sm" @click="ctx.discardSuggestion(ctx.activeRow.itemId)">{{ t('assistant.aiDiscard') }}</button>
              <small v-if="activeSuggestion.modelLabel" class="tp-ai-model">{{ activeSuggestion.modelLabel }}</small>
            </div>
          </div>
        </div>

        <div class="tp-foot">
          <span v-if="ctx.canEdit" class="tp-chars" :class="{ over: ctx.activeLen > MAX_ITEM_CHARS }">
            {{ t('assistant.tplChars', { n: ctx.activeLen, max: MAX_ITEM_CHARS }) }}
          </span>
          <span class="tp-btns">
            <button type="button" class="btn btn-ghost btn-sm" :disabled="ctx.prevId == null" @click="ctx.goItem(-1)">
              <span class="arrow" aria-hidden="true">←</span> {{ t('assistant.tplPrev') }}
            </button>
            <button type="button" class="btn btn-ghost btn-sm" :disabled="ctx.nextId == null" @click="ctx.goItem(1)">
              {{ t('assistant.tplNext') }} <span class="arrow" aria-hidden="true">→</span>
            </button>
          </span>
        </div>
      </section>
    </div>

    <div v-if="ctx.canEdit && ctx.checklistRows.length" class="step-foot">
      <span v-if="ctx.overLongRow" class="df-miss">
        {{ t('assistant.dfTooLong', { no: ctx.overLongRow.no || ctx.overLongRow.seq, max: MAX_ITEM_CHARS }) }}
      </span>
      <button class="btn btn-primary btn-sm" @click="ctx.go(3)">
        {{ t('assistant.goCheck') }} <span class="arrow" aria-hidden="true">→</span>
      </button>
    </div>
  </div>
</template>
