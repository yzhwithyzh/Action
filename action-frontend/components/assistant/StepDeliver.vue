<script setup lang="ts">
/**
 * ⑤ 成果交付：交付前核对（只提醒，不拦导出）→ 初稿预览 → 导出 → AI 使用说明 → 操作留痕。
 *
 * 导出的是**库里那份草稿**，不是预览那段文本 —— 后者是瞬时产物。三种格式各答一个问题：
 * docx 稿件本身（附录每张清单一张对照表）· xlsx 投稿随附的对照表（每张清单一个工作表）· json 留档。
 * **没有 PDF**：服务端生成中文 PDF 缺字体时是整篇方块字而不是报错，docx 自己另存更可靠。
 */
import { useAssistantCtx } from '~/composables/assistant/assistantContext'
import { EXPORT_FMTS } from '~/composables/assistant/useReportWorkspace'

const ctx = useAssistantCtx()
const { t } = ctx

/** 核对项的去处：有条目就定位到第一条，没检查过 / 过时就去第三步 */
function goCheck(c: { key: string; itemIds: number[] }) {
  if (c.itemIds.length) {
    ctx.editItem(c.itemIds[0]!)
    return
  }
  if (c.key === 'notChecked' || c.key === 'stale') ctx.go(3)
  if (c.key === 'renderStale' || c.key === 'renderIssues') ctx.go(4)
}

/**
 * 「加密分享链接」与「版本快照对比」两段还是写死的演示，先关掉。
 *
 * **不是排期问题，是两个未定的设计。** 分享链接一旦真发，就是一个**匿名可读的未发表稿件外链** ——
 * 有效期、撤销、评论存哪、被转发怎么办都要先定。版本对比要先有快照模型。
 * 留着一个会复制出真链接的按钮，用户会以为它真的分享了什么。模板与样式都还在，定稿后改成 true 即恢复
 */
const SHOW_WIP_SHARE = false
const perm = ref<'view' | 'comment'>('view')
const SHARE_URL = 'https://action-acu.cn/r/9f3a…c7'
const copied = ref(false)
async function copyLink() {
  try {
    await navigator.clipboard?.writeText(SHARE_URL)
  } catch { /* ignore */ }
  copied.value = true
  setTimeout(() => (copied.value = false), 2000)
}
interface DiffRow { kind: 'add' | 'del'; key: string }
const versions: { v: number; name: string; tag?: string; tagKey?: string; diff?: DiffRow[] }[] = [
  { v: 3, name: 's115', tagKey: 's116', diff: [{ kind: 'add', key: 'diffV3_1' }, { kind: 'add', key: 'diffV3_2' }, { kind: 'del', key: 'diffV3_3' }] },
  { v: 2, name: 's117', tag: '2026-07-20', diff: [{ kind: 'add', key: 'diffV2_1' }, { kind: 'add', key: 'diffV2_2' }, { kind: 'del', key: 'diffV2_3' }] },
  { v: 1, name: 's118', tag: '2026-07-18' },
]
const diffVer = ref<number | null>(null)
</script>

<template>
  <div class="panel" :class="{ 'is-hidden': ctx.step !== 5 }" data-panel="5">
    <div class="p-head">
      <span class="p-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3v12m0 0 4-4m-4 4-4-4" /><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" /></svg></span>
      <div><span class="p-num">{{ t('assistant.s102') }}</span><h2>{{ t('assistant.s103') }}</h2></div>
    </div>
    <p class="p-desc">{{ t('assistant.s104') }}</p>

    <p v-if="!ctx.isLoggedIn" class="wk-empty">
      {{ t('assistant.expNeedLogin') }}
      <NuxtLink class="btn btn-primary btn-sm" :to="ctx.loginLink">{{ t('assistant.dfLogin') }}</NuxtLink>
    </p>
    <p v-else-if="!ctx.draftId" class="wk-empty">
      {{ t('assistant.expNeedDraft') }}
      <button class="btn btn-ghost btn-sm" @click="ctx.go(2)">{{ t('assistant.wkGoStep2') }}</button>
    </p>
    <template v-else>
      <!-- 交付前核对：只提醒，不拦导出（甲方定稿）。每一项都能点过去处理 -->
      <div class="dl-box">
        <div class="subh">{{ t('assistant.dlCheckTitle') }}</div>
        <p v-if="!ctx.deliverList.length" class="dl-ok">{{ t('assistant.dlAllClear') }}</p>
        <ul v-else class="dl-list">
          <li v-for="c in ctx.deliverList" :key="c.key">
            <span>{{ t(`assistant.dlc.${c.key}`, { n: c.count }) }}</span>
            <button
              v-if="c.itemIds.length || ['notChecked', 'stale', 'renderStale', 'renderIssues'].includes(c.key)"
              type="button"
              class="src-jump"
              @click="goCheck(c)"
            >{{ c.itemIds.length ? t('assistant.dlGoItem') : c.key.startsWith('render') ? t('assistant.dlGoRender') : t('assistant.dlGoCheck') }}</button>
          </li>
        </ul>
        <p class="dl-note">{{ t('assistant.dlCheckNote') }}</p>
      </div>

      <!-- 正文来源：有整篇成文时才出现这道选择。只影响 docx 正文，对照表与 json 不变 -->
      <div v-if="ctx.render?.sections.length" class="dl-src">
        <div class="subh">{{ t('assistant.dlBodyTitle') }}</div>
        <label>
          <input type="radio" :checked="ctx.bodySource === 'render'" @change="ctx.bodyPick = 'render'" />
          <b>{{ t('assistant.dlBodyRender') }}</b>
          <small>{{ t('assistant.dlBodyRenderDesc') }}</small>
        </label>
        <label>
          <input type="radio" :checked="ctx.bodySource === 'auto'" @change="ctx.bodyPick = 'auto'" />
          <b>{{ ctx.hasSource ? t('assistant.dlBodySource') : t('assistant.dlBodyItems') }}</b>
          <small>{{ ctx.hasSource ? t('assistant.dlBodySourceDesc') : t('assistant.dlBodyItemsDesc') }}</small>
        </label>
      </div>

      <!-- 导出 -->
      <div class="subh" style="margin-top:22px">{{ t('assistant.s105') }}</div>
      <div class="exp-btns">
        <button
          v-for="f in EXPORT_FMTS"
          :key="f"
          class="exp"
          :disabled="Boolean(ctx.exporting)"
          @click="ctx.downloadExport(f)"
        >
          <span class="ei" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4" /><path d="M9 13h6M9 16h4" /></svg></span>
          <span>
            <b>{{ t(`assistant.expFmt.${f}`) }}</b>
            <span>{{ ctx.exporting === f ? t('assistant.expRunning') : t(`assistant.expDesc.${f}`) }}</span>
          </span>
        </button>
      </div>
      <p v-if="ctx.exportErr" class="rv-err">{{ ctx.exportErr }}</p>
      <p class="tmpl-note" v-html="t('assistant.expNote')"></p>

      <!-- AI 使用说明：由本稿的 applied 留痕算出来，复制即用 -->
      <div class="dl-box">
        <div class="subh">{{ t('assistant.dlAiTitle') }}</div>
        <p class="dl-note" style="margin-top:0">{{ t('assistant.dlAiDesc') }}</p>
        <p class="dl-ai">{{ ctx.aiUseText }}</p>
        <button v-if="ctx.aiUse.times || ctx.bodySource === 'render'" type="button" class="btn btn-ghost btn-sm" @click="ctx.copyAiUse">
          {{ ctx.aiCopied ? t('assistant.copied') : t('assistant.dlAiCopy') }}
        </button>
      </div>

      <!-- 初稿预览：导出 docx 的正文就是它（导入的稿件 = 原稿 + 改过的条目写回原处） -->
      <div class="df-preview-wrap">
        <div v-if="ctx.bodySource === 'render'" class="dl-pv-head">
          <span class="subh" style="margin:0">{{ t('assistant.dfPreview') }}</span>
          <button class="btn btn-ghost btn-sm" @click="ctx.go(4)">{{ t('assistant.dlEditRender') }}</button>
        </div>
        <div v-if="ctx.bodySource === 'render'" class="df-preview"><pre>{{ ctx.renderText }}</pre></div>
        <template v-else>
        <div class="dl-pv-head">
          <span class="subh" style="margin:0">{{ t('assistant.dfPreview') }}</span>
          <button class="btn btn-ghost btn-sm" :disabled="ctx.composing" @click="ctx.composeDraft">
            {{ ctx.composing ? t('assistant.dfComposing') : t('assistant.dlPreviewRefresh') }}
          </button>
          <span v-if="ctx.composed && ctx.composeMissing" class="df-miss">{{ t('assistant.dfMissing', { n: ctx.composeMissing }) }}</span>
        </div>
        <div v-if="ctx.composed && ctx.rebuildInfo" class="df-rebuild">
          <p>
            {{ t('assistant.rbSummary', {
              replaced: ctx.rebuildInfo.replaced, inserted: ctx.rebuildInfo.inserted, removed: ctx.rebuildInfo.removed,
            }) }}
            <template v-if="ctx.rebuildInfo.keepsLayout">
              {{ t('assistant.rbLayout', { images: ctx.rebuildInfo.images, tables: ctx.rebuildInfo.tables }) }}
            </template>
            <template v-else>{{ t('assistant.rbNoLayout') }}</template>
          </p>
        </div>
        <div v-if="ctx.composed" class="df-preview"><pre>{{ ctx.composed }}</pre></div>
        <p v-else class="df-preview-empty">{{ ctx.composing ? t('assistant.dfComposing') : t('assistant.dfPreviewEmpty') }}</p>
        </template>
      </div>

      <!-- 操作留痕（文档 3.4）：检查、AI 写回这类关键操作。默认收起 -->
      <details v-if="ctx.auditTrail.length" class="audit">
        <summary class="subh">{{ t('assistant.auditTitle') }}</summary>
        <p class="tmpl-note" style="margin:6px 0 12px">{{ t('assistant.auditDesc') }}</p>
        <ul class="audit-list">
          <li v-for="l in ctx.auditTrail" :key="l.id">
            <span class="at">{{ l.at }}</span>
            <span class="aa">{{ l.who }}</span>
            <span class="ad">{{ l.what }}</span>
          </li>
        </ul>
      </details>
    </template>

    <div v-if="SHOW_WIP_SHARE" class="share">
      <div class="subh">{{ t('assistant.s110') }}</div>
      <div class="share-row">
        <span class="share-link"><span id="shareUrl">{{ SHARE_URL }}</span></span>
        <span class="share-perm" role="group" :aria-label="t('assistant.permAria')">
          <button type="button" :class="{ on: perm === 'view' }" :aria-pressed="perm === 'view'" @click="perm = 'view'">{{ t('assistant.s111') }}</button>
          <button type="button" :class="{ on: perm === 'comment' }" :aria-pressed="perm === 'comment'" @click="perm = 'comment'">{{ t('assistant.s112') }}</button>
        </span>
        <button class="btn btn-ink btn-sm" @click="copyLink">{{ copied ? t('assistant.copied') : t('assistant.s113') }}</button>
      </div>
      <div class="subh" style="margin-top:22px">{{ t('assistant.s114') }}</div>
      <ul class="ver-list">
        <template v-for="ver in versions" :key="ver.v">
          <li>
            <span class="vt">v{{ ver.v }}</span>
            <span class="vn">{{ t(`assistant.${ver.name}`) }}</span>
            <span class="vtag">{{ ver.tagKey ? t(`assistant.${ver.tagKey}`) : ver.tag }}</span>
            <button v-if="ver.diff" class="vdiff" type="button" :class="{ on: diffVer === ver.v }" @click="diffVer = diffVer === ver.v ? null : ver.v">{{ t('assistant.verCompare') }}</button>
          </li>
          <li v-if="ver.diff && diffVer === ver.v" class="diffbox">
            <span class="dh">{{ t('assistant.diffTitle', { a: ver.v - 1, b: ver.v }) }}</span>
            <span v-for="d in ver.diff" :key="d.key" class="dl" :class="d.kind">
              <em aria-hidden="true">{{ d.kind === 'add' ? '+' : '−' }}</em>{{ t(`assistant.${d.key}`) }}
            </span>
          </li>
        </template>
      </ul>
      <div class="beta-note"><span>{{ t('assistant.s119') }}</span></div>
    </div>
  </div>
</template>
