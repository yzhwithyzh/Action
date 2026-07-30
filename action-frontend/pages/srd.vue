<script setup lang="ts">
/**
 * srd.html 迁移而来。
 * 模板与样式保持原状；样式已加 .page-srd 命名空间，避免 SPA 路由切换时跨页污染。
 */
const { t } = useI18n()

interface SrdItem {
  itemId: number
  code: string | null
  questionZh: string | null
  questionEn: string | null
  level: string | null
  pct: number | null
  basisZh: string | null
  basisEn: string | null
  citeAZh: string | null
  citeAEn: string | null
  citeBZh: string | null
  citeBEn: string | null
}
interface SrdGroup {
  groupId: number
  code: string | null
  nameZh: string | null
  nameEn: string | null
  items: SrdItem[]
}
interface SrdDomain {
  domainId: number
  seq: number
  nameZh: string | null
  nameEn: string | null
  isKey: '0' | '1' | null
  level: string | null
  pct: number | null
  groups: SrdGroup[]
}
interface SrdAssessment {
  assessmentId: number
  reviewATitleZh: string | null
  reviewATitleEn: string | null
  reviewBTitleZh: string | null
  reviewBTitleEn: string | null
  overallLevel: string | null
  overallPct: number | null
  overallReasonZh: string | null
  overallReasonEn: string | null
  domains: SrdDomain[]
}

useHead({
  title: t('srd._title'),
  meta: [{ name: 'description', content: t('srd._desc') }],
})

const { pick } = useBilingual()
const api = useSiteRequest()

/** 判定等级 → CSS 类 / 文案键 / 环与条的配色，取值与原 srd.html 的 LV / BARC 常量一致 */
const LV_CLASS: Record<string, string> = { none: 'lvl-none', low: 'lvl-low', mod: 'lvl-mod', high: 'lvl-high' }
const LV_LABEL: Record<string, string> = {
  none: 'srd.lvlNone',
  low: 'srd.lvlLow',
  mod: 'srd.lvlMod',
  high: 'srd.lvlHigh',
}
const RING_COLOR: Record<string, string> = { none: '#63c3ba', low: '#9fb3d4', mod: '#e6a93c', high: '#ff8f86' }
const BAR_COLOR: Record<string, string> = {
  none: 'var(--info)',
  low: 'var(--indigo-500)',
  mod: 'var(--amber)',
  high: 'var(--cinnabar)',
}
const lvClass = (l: string | null) => LV_CLASS[l ?? 'mod'] ?? 'lvl-mod'
const lvLabel = (l: string | null) => t(LV_LABEL[l ?? 'mod'] ?? 'srd.lvlMod')

/** 示例文件名（原页面 DEMOF 常量的等价物；真实标题来自接口） */
const demoLoaded = ref(false)
const running = ref(false)
const runError = ref('')
const result = ref<SrdAssessment | null>(null)
/** 载入示例时先取一次接口，以便用真实的 A/B 标题填来源卡 */
const sample = ref<SrdAssessment | null>(null)

const loadDemo = async () => {
  runError.value = ''
  try {
    if (!sample.value) sample.value = await api.get<SrdAssessment>('/srd/sample')
  } catch {
    sample.value = null
  }
  demoLoaded.value = Boolean(sample.value)
  // 没有 try/catch 的话，后端 5xx 会让异常逃逸出去：demoLoaded 保持 false、
  // runError 也永远赋不上（赋值在 await 之后），按钮看起来像完全没反应。
  if (!sample.value) runError.value = t('srd.runFailed')
}

const runAssess = async () => {
  running.value = true
  runError.value = ''
  try {
    result.value = sample.value ?? (await api.get<SrdAssessment>('/srd/sample'))
    if (!result.value) runError.value = t('srd.runFailed')
  } catch {
    runError.value = t('srd.runFailed')
  } finally {
    running.value = false
  }
}

/** 环周长：r=56 → 2πr */
const CIRC = 2 * Math.PI * 56
const ringDash = computed(() => {
  const pct = result.value?.overallPct ?? 0

  return `${((pct / 100) * CIRC).toFixed(1)} ${CIRC.toFixed(1)}`
})

useReveal()
</script>

<template>
  <div class="page-srd">
    <!-- ===================== 工具工作区 ===================== -->
    <section class="tool" id="tool">
      <div class="wrap">
        <span class="kicker reveal">{{ t('srd.s001') }}</span>
        <h2 class="title reveal">{{ t('srd.s002') }}</h2>
        <p class="lead reveal">{{ t('srd.s003') }}</p>

        <div class="io-grid" style="margin-top:clamp(24px,3vw,32px)">
          <!-- 综述 A -->
          <div class="src-card a reveal" data-slot="a">
            <div class="src-head">
              <span class="src-tag" aria-hidden="true">A</span>
              <div><h3>{{ t('srd.s004') }}</h3><p>{{ t('srd.s005') }}</p></div>
            </div>
            <label class="pdf-drop" :class="{ 'is-hidden': demoLoaded }">
              <input type="file" accept="application/pdf,.pdf" class="pdf-input" hidden aria-label="上传系统综述 A 的 PDF 文件" />
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M12 16V4m0 0 4 4m-4-4-4 4" /><path d="M5 20h14" /></svg>
              <span class="pd-title">{{ t('srd.s006') }}</span>
              <span class="pd-sub">{{ t('srd.s007') }}</span>
            </label>
            <div class="pdf-file" :class="{ 'is-hidden': !demoLoaded }">
              <span class="pf-ic" aria-hidden="true">PDF</span>
              <div class="pf-meta"><b class="pf-name">{{ demoLoaded ? pick(sample, 'reviewATitle') : '' }}</b><span class="pf-size"></span></div>
              <button type="button" class="pf-rm" aria-label="移除文件">{{ t('srd.s008') }}</button>
            </div>
          </div>
          <!-- 综述 B -->
          <div class="src-card b reveal" data-slot="b">
            <div class="src-head">
              <span class="src-tag" aria-hidden="true">B</span>
              <div><h3>{{ t('srd.s009') }}</h3><p>{{ t('srd.s010') }}</p></div>
            </div>
            <label class="pdf-drop" :class="{ 'is-hidden': demoLoaded }">
              <input type="file" accept="application/pdf,.pdf" class="pdf-input" hidden aria-label="上传系统综述 B 的 PDF 文件" />
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M12 16V4m0 0 4 4m-4-4-4 4" /><path d="M5 20h14" /></svg>
              <span class="pd-title">{{ t('srd.s011') }}</span>
              <span class="pd-sub">{{ t('srd.s012') }}</span>
            </label>
            <div class="pdf-file" :class="{ 'is-hidden': !demoLoaded }">
              <span class="pf-ic" aria-hidden="true">PDF</span>
              <div class="pf-meta"><b class="pf-name">{{ demoLoaded ? pick(sample, 'reviewBTitle') : '' }}</b><span class="pf-size"></span></div>
              <button type="button" class="pf-rm" aria-label="移除文件">{{ t('srd.s013') }}</button>
            </div>
          </div>
        </div>

        <div class="run-bar reveal">
          <button type="button" class="btn btn-primary btn-lg" id="runBtn" :disabled="!demoLoaded || running" @click="runAssess">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" aria-hidden="true"><path d="M5 3l14 9-14 9V3Z" /></svg>
            <span>{{ t('srd.s014') }}</span>
          </button>
          <span class="run-note"><svg class="spark" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" /></svg><span id="runHint">{{ t('srd.s015') }}</span></span>
          <button type="button" class="demo-link" id="demoBtn" @click="loadDemo">{{ t('srd.s016') }}</button>
        </div>

        <!-- 方法说明 -->
        <details class="method reveal" id="method">
          <summary>
            <span class="mi" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 3l8 4v6c0 4.5-3.2 7-8 8-4.8-1-8-3.5-8-8V7z" /><path d="M12 8v5M12 16h.01" /></svg></span>
            <span>{{ t('srd.s017') }}</span>
            <small>{{ t('srd.s018') }}</small>
            <svg class="mcaret" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
          </summary>
          <div class="method-body">
            <div class="method-cols">
              <div>
                <div class="mh">{{ t('srd.s019') }}</div>
                <ul class="scale">
                  <li><span class="lv"><span class="lvl lvl-none">{{ t('srd.s020') }}</span></span><span class="rng">0–25%</span><span class="ds">{{ t('srd.s021') }}</span></li>
                  <li><span class="lv"><span class="lvl lvl-low">{{ t('srd.s022') }}</span></span><span class="rng">26–50%</span><span class="ds">{{ t('srd.s023') }}</span></li>
                  <li><span class="lv"><span class="lvl lvl-mod">{{ t('srd.s024') }}</span></span><span class="rng">51–75%</span><span class="ds">{{ t('srd.s025') }}</span></li>
                  <li><span class="lv"><span class="lvl lvl-high">{{ t('srd.s026') }}</span></span><span class="rng">76–100%</span><span class="ds">{{ t('srd.s027') }}</span></li>
                </ul>
              </div>
              <div>
                <div class="mh">{{ t('srd.s028') }}</div>
                <div class="dom-legend">
                  <p v-html="t('srd.s029')"></p>
                  <p>{{ t('srd.s030') }}</p>
                  <p>{{ t('srd.s031') }}</p>
                </div>
              </div>
            </div>
          </div>
        </details>
      </div>
    </section>

    <!-- ===================== 结果区（JS 渲染） ===================== -->
    <section class="sec results" id="results">
      <div class="wrap">
        <span class="res-flag" :class="{ 'is-hidden': !result }" id="resFlag"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 9v4M12 17h.01" /><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" /></svg><span>{{ t('srd.s032') }}</span></span>
        <div v-if="!result && !runError" id="resEmpty" class="res-empty">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="2" /><path d="M8 10h8M8 14h5" /></svg>
          <b>{{ t('srd.s033') }}</b>
          <p>{{ t('srd.s034') }}</p>
        </div>
        <p v-if="runError" class="res-empty" style="color:var(--cinnabar)">{{ runError }}</p>
        <div v-if="result" id="resContent">
          <div class="verdict">
            <div class="gauge">
              <div class="ring">
                <svg width="132" height="132" viewBox="0 0 132 132" aria-hidden="true">
                  <circle cx="66" cy="66" r="56" fill="none" stroke="rgba(255,255,255,.14)" stroke-width="12" />
                  <circle
                    cx="66" cy="66" r="56" fill="none"
                    :stroke="RING_COLOR[result.overallLevel ?? 'mod']"
                    stroke-width="12" stroke-linecap="round" :stroke-dasharray="ringDash"
                  />
                </svg>
                <div class="pctn"><b>{{ result.overallPct }}%</b><span>{{ t('srd.overallOverlap') }}</span></div>
              </div>
              <span class="lvl" :class="lvClass(result.overallLevel)" style="font-size:13px">{{ lvLabel(result.overallLevel) }}</span>
            </div>
            <div class="verdict-main">
              <h2>{{ t('srd.overallVerdict') }}<span class="em">{{ lvLabel(result.overallLevel) }}</span></h2>
              <p class="vpair">
                <b>{{ t('srd.reviewA') }}</b>《{{ pick(result, 'reviewATitle') }}》
                &nbsp;·&nbsp;
                <b>{{ t('srd.reviewB') }}</b>《{{ pick(result, 'reviewBTitle') }}》
              </p>
              <p class="verdict-rec">{{ pick(result, 'overallReason') }}</p>
            </div>
          </div>

          <div class="dom-tiles">
            <div v-for="d in result.domains" :key="d.domainId" class="dtile">
              <div class="dt-top">
                <span class="dt-name">{{ t('srd.lblDomain') }} {{ d.seq }}<small>{{ pick(d, 'name') }}{{ d.isKey === '1' ? ' · ' + t('srd.keyShort') : '' }}</small></span>
                <span class="lvl" :class="lvClass(d.level)">{{ lvLabel(d.level) }}</span>
              </div>
              <div class="bar"><i :style="{ width: d.pct + '%', background: BAR_COLOR[d.level ?? 'mod'] }"></i></div>
              <div class="dt-pct"><b>{{ d.pct }}%</b> <span>{{ t('srd.lblOverlap') }}</span></div>
            </div>
          </div>

          <div class="res-tools"><h3>{{ t('srd.itemTitle') }}</h3></div>
          <details v-for="d in result.domains" :key="'rd-' + d.domainId" class="rd" :open="d.isKey === '1'">
            <summary>
              <span class="rd-badge">{{ d.seq }}</span>
              <span class="rd-dn">
                <b>{{ t('srd.lblDomain') }} {{ d.seq }} · {{ pick(d, 'name') }}</b>
                <span>{{ d.isKey === '1' ? t('srd.keyDomain') : t('srd.nonKeyDomain') }} · {{ t('srd.domainOverlap') }} {{ d.pct }}%</span>
              </span>
              <span v-if="d.isKey === '1'" class="keych" style="margin-right:6px">{{ t('srd.keyShort') }}</span>
              <span class="lvl" :class="lvClass(d.level)">{{ lvLabel(d.level) }}</span>
              <svg class="rd-caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
            </summary>
            <div class="rd-body">
              <table class="srd">
                <thead>
                  <tr>
                    <th>{{ t('srd.thNo') }}</th>
                    <th>{{ t('srd.thQuestion') }}</th>
                    <th>{{ t('srd.thLevel') }}</th>
                    <th>{{ t('srd.thBasis') }}</th>
                    <th>{{ t('srd.thCite') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <template v-for="g in d.groups" :key="g.groupId">
                    <tr class="grp">
                      <td colspan="5" style="background:var(--indigo-100);font-weight:700;color:var(--indigo-800);font-size:12px">
                        <span>{{ t('srd.lblGroup') }} {{ g.code }} · {{ pick(g, 'name') }}</span>
                      </td>
                    </tr>
                    <tr v-for="it in g.items" :key="it.itemId">
                      <td class="c-id">{{ it.code }}</td>
                      <td class="c-q">{{ pick(it, 'question') }}</td>
                      <td class="c-v">
                        <span class="lvl" :class="lvClass(it.level)">{{ lvLabel(it.level) }}</span>
                        <div style="font-size:11.5px;color:var(--muted);margin-top:5px;font-variant-numeric:tabular-nums">{{ it.pct }}%</div>
                      </td>
                      <td class="c-basis">{{ pick(it, 'basis') }}</td>
                      <td>
                        <span class="cite a"><em>A</em>{{ pick(it, 'citeA') }}</span>
                        <span class="cite b"><em>B</em>{{ pick(it, 'citeB') }}</span>
                      </td>
                    </tr>
                  </template>
                </tbody>
              </table>
            </div>
          </details>
        </div>
      </div>
    </section>

    <!-- ===================== 评估历史 ===================== -->
    <section class="sec history" id="history" style="background:var(--surface)">
      <div class="wrap">
        <div class="sec-head" style="display:flex;align-items:flex-end;justify-content:space-between;gap:20px;flex-wrap:wrap">
          <div>
            <span class="kicker reveal">{{ t('srd.s035') }}</span>
            <h2 class="title reveal">{{ t('srd.s036') }}</h2>
          </div>
          <button type="button" class="btn btn-ghost btn-sm" id="clearHist">{{ t('srd.s037') }}</button>
        </div>
        <div id="histList" class="hist-list">
          <div class="hist-empty">{{ t('srd.histEmpty') }}</div>
        </div>
      </div>
    </section>
  </div>
</template>

<style>
.page-srd .skip-link{position:absolute;left:12px;top:-60px;z-index:var(--z-toast);background:var(--indigo-700);color:#fff;
    font-weight:600;font-size:15px;padding:12px 20px;border-radius:10px;transition:top .2s var(--ease)}
.page-srd .sec{padding:clamp(40px,5.5vw,72px) 0;scroll-margin-top:88px}
.page-srd .kicker.on-dark{color:var(--indigo-200)}
.page-srd h2.title{font-size:clamp(1.6rem,3vw,2.2rem);color:var(--indigo-900);letter-spacing:-.02em;text-wrap:balance;max-width:26ch}
.page-srd .lead{color:var(--muted);font-size:clamp(1rem,1.4vw,1.12rem);max-width:68ch;margin-top:16px;text-wrap:pretty}
.page-srd .btn{display:inline-flex;align-items:center;justify-content:center;gap:9px;padding:13px 24px;border-radius:999px;font-weight:600;font-size:15px;
    border:1.5px solid transparent;cursor:pointer;white-space:nowrap;
    transition:transform .25s var(--ease),background-color .25s var(--ease),box-shadow .25s var(--ease),border-color .25s var(--ease)}
.page-srd .btn-primary:disabled{background:var(--indigo-300);box-shadow:none;cursor:not-allowed;transform:none}
.page-srd .btn-lg{padding:15px 30px;font-size:16px}
.page-srd .phero{position:relative;overflow:hidden;background:var(--indigo-900);color:#fff;isolation:isolate}
.page-srd .phero::before{content:"";position:absolute;inset:0;z-index:-1;
    background:radial-gradient(1000px 560px at 90% 0%,rgba(44,127,114,.5),transparent 60%),
    radial-gradient(680px 460px at 2% 100%,rgba(15,111,106,.28),transparent 65%),
    linear-gradient(160deg,#0d1a17 0%,#12211d 44%,#183029 100%)}
.page-srd .phero .wrap{padding:clamp(28px,3.6vw,40px) clamp(20px,4vw,44px) clamp(40px,5vw,56px)}
.page-srd .crumb{display:flex;align-items:center;gap:9px;font-size:13.5px;color:rgba(233,238,247,.66);margin-bottom:24px;flex-wrap:wrap}
.page-srd .phero-tag{display:inline-flex;align-items:center;gap:10px;font-size:13px;font-weight:600;letter-spacing:.02em;color:var(--indigo-200);
    background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.16);padding:8px 16px;border-radius:999px;backdrop-filter:blur(4px)}
.page-srd .phero h1{font-size:clamp(1.9rem,3.8vw,3rem);font-weight:700;letter-spacing:-.025em;margin:18px 0 0;text-wrap:balance;line-height:1.14}
.page-srd .phero .psub{margin-top:18px;font-size:clamp(1rem,1.4vw,1.14rem);color:rgba(233,238,247,.9);max-width:66ch;line-height:1.7;text-wrap:pretty}
.page-srd .phero-steps{display:flex;flex-wrap:wrap;gap:10px;margin-top:28px}
.page-srd .phero-steps span{display:inline-flex;align-items:center;gap:9px;font-size:13.5px;font-weight:600;color:rgba(233,238,247,.86);
    background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.14);padding:9px 15px;border-radius:999px}
.page-srd .phero-steps span i{width:20px;height:20px;border-radius:6px;background:var(--indigo-600);color:#fff;display:inline-flex;align-items:center;justify-content:center;
    font-family:"Spectral",serif;font-weight:700;font-size:11.5px;font-style:normal}
.page-srd .phero-steps .sep2{background:none;border:none;padding:0;color:rgba(233,238,247,.4)}
.page-srd .tool{padding:clamp(36px,5vw,64px) 0}
.page-srd .io-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.page-srd .src-card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-lg);padding:22px 22px 20px;display:flex;flex-direction:column;gap:14px;
    transition:border-color .25s var(--ease),box-shadow .25s var(--ease)}
.page-srd .src-card:focus-within{border-color:var(--indigo-300);box-shadow:var(--shadow-sm)}
.page-srd .src-head{display:flex;align-items:center;gap:12px}
.page-srd .src-tag{width:38px;height:38px;flex-shrink:0;border-radius:11px;background:var(--indigo-700);color:#fff;display:flex;align-items:center;justify-content:center;
    font-family:"Spectral",serif;font-weight:700;font-size:17px}
.page-srd .src-card.b .src-tag{background:var(--info)}
.page-srd .src-head h3{font-size:1.1rem;color:var(--indigo-900)}
.page-srd .src-head p{font-size:12.5px;color:var(--muted);margin-top:1px}
.page-srd .seg{display:inline-flex;background:var(--paper-2);border:1px solid var(--line);border-radius:10px;padding:3px;gap:2px}
.page-srd .seg button{border:none;background:transparent;font-family:inherit;font-size:12.5px;font-weight:600;color:var(--muted);padding:7px 12px;border-radius:7px;cursor:pointer;transition:.2s}
.page-srd .seg button.on{background:var(--surface);color:var(--indigo-800);box-shadow:var(--shadow-sm)}
.page-srd .src-in{position:relative}
.page-srd .src-ta{width:100%;min-height:150px;resize:vertical;border:1.5px solid var(--line);border-radius:12px;padding:13px 14px;font-family:inherit;font-size:14px;color:var(--ink);line-height:1.6;background:var(--paper)}
.page-srd .src-ta:focus{outline:none;border-color:var(--indigo-500);box-shadow:0 0 0 4px var(--indigo-100)}
.page-srd .src-ta::placeholder{color:#8895a8}
.page-srd .src-title{width:100%;border:1.5px solid var(--line);border-radius:10px;padding:10px 13px;font-family:inherit;font-size:13.5px;color:var(--ink);background:var(--surface)}
.page-srd .src-title:focus{outline:none;border-color:var(--indigo-500);box-shadow:0 0 0 4px var(--indigo-100)}
.page-srd .src-lab{font-size:12px;font-weight:700;color:var(--indigo-700);letter-spacing:.02em;margin-bottom:6px;display:block}
.page-srd .drop{display:none;border:1.6px dashed var(--indigo-200);border-radius:12px;padding:28px 16px;text-align:center;background:var(--paper);color:var(--muted);font-size:13.5px}
.page-srd .drop svg{width:26px;height:26px;color:var(--indigo-400,#7d90ad);margin:0 auto 8px}
.page-srd .src-in[data-mode="upload"] .src-ta{display:none}
.page-srd .src-in[data-mode="upload"] .drop{display:block}
.page-srd .src-fill{margin-top:2px;font-size:12px;color:var(--indigo-600);font-weight:600;background:none;border:none;cursor:pointer;padding:0;text-decoration:underline;text-underline-offset:2px}
.page-srd .pdf-drop{display:flex;flex-direction:column;align-items:center;gap:5px;text-align:center;cursor:pointer;
    border:1.6px dashed var(--indigo-200);border-radius:14px;padding:30px 18px;background:var(--paper);transition:.2s var(--ease)}
.page-srd .pdf-drop:hover,.page-srd .pdf-drop:focus-within{border-color:var(--indigo-500);background:var(--indigo-100)}
.page-srd .pdf-drop.drag{border-color:var(--cinnabar);background:var(--indigo-100)}
.page-srd .pdf-drop svg{width:30px;height:30px;color:var(--indigo-500);margin-bottom:4px}
.page-srd .pdf-drop .pd-title{font-weight:700;color:var(--indigo-800);font-size:14px}
.page-srd .pdf-drop .pd-sub{font-size:12px;color:var(--muted)}
.page-srd .pdf-file{display:flex;align-items:center;gap:12px;border:1.5px solid var(--line);border-radius:12px;padding:13px 14px;background:var(--surface)}
.page-srd .pf-ic{width:38px;height:38px;flex-shrink:0;border-radius:9px;background:rgba(192,54,44,.09);color:var(--cinnabar-d);display:flex;align-items:center;justify-content:center;
    font-family:"Spectral",serif;font-weight:700;font-size:11px}
.page-srd .pf-meta{flex:1;min-width:0}
.page-srd .pf-name{display:block;font-size:13.5px;font-weight:600;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.page-srd .pf-size{font-size:12px;color:var(--muted)}
.page-srd .pf-rm{flex-shrink:0;font-family:inherit;font-size:12.5px;font-weight:600;color:var(--muted);background:var(--paper-2);border:1px solid var(--line);border-radius:999px;padding:5px 12px;cursor:pointer;transition:.2s}
.page-srd .pf-rm:hover{color:var(--cinnabar-d);border-color:var(--cinnabar)}
.page-srd .demo-link{font-family:inherit;font-size:13px;font-weight:600;color:var(--indigo-600);background:none;border:none;cursor:pointer;text-decoration:underline;text-underline-offset:3px;padding:2px}
.page-srd .demo-link:hover{color:var(--cinnabar-d)}
.page-srd .res-empty{text-align:center;padding:clamp(36px,5vw,60px) 20px;background:var(--surface);border:1.5px dashed var(--line);border-radius:var(--radius-lg)}
.page-srd .res-empty svg{width:42px;height:42px;color:var(--indigo-300);margin:0 auto 14px}
.page-srd .res-empty b{display:block;font-family:"Spectral","Noto Serif SC",serif;font-size:1.3rem;color:var(--indigo-900);margin-bottom:8px}
.page-srd .res-empty p{font-size:14px;color:var(--muted);max-width:52ch;margin:0 auto;line-height:1.6}
.page-srd .history{border-top:1px solid var(--line)}
.page-srd .hist-list{margin-top:clamp(22px,3vw,30px);display:flex;flex-direction:column;gap:10px}
.page-srd .hist-row{display:grid;grid-template-columns:120px 1fr auto auto;gap:18px;align-items:center;
    background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:16px 18px;transition:.2s var(--ease)}
.page-srd .hist-row:hover{border-color:var(--indigo-200);box-shadow:var(--shadow-sm);background:var(--surface)}
.page-srd .h-when b{display:block;font-family:"Spectral",serif;font-weight:700;color:var(--indigo-900);font-size:14px;font-variant-numeric:tabular-nums}
.page-srd .h-when span{font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums}
.page-srd .h-titles{min-width:0;font-size:13px;color:var(--ink);line-height:1.5}
.page-srd .h-titles .ht{display:flex;gap:7px;align-items:baseline}
.page-srd .h-titles em{font-style:normal;font-weight:700;font-size:11px;color:#fff;background:var(--indigo-600);border-radius:5px;padding:0 6px;flex-shrink:0}
.page-srd .h-titles .ht.b em{background:var(--info)}
.page-srd .h-titles .ht span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.page-srd .h-acts{display:flex;align-items:center;gap:8px}
.page-srd .h-del{width:34px;height:34px;flex-shrink:0;border-radius:9px;border:1px solid var(--line);background:var(--surface);color:var(--muted);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:.2s}
.page-srd .h-del:hover{color:var(--cinnabar-d);border-color:var(--cinnabar);background:rgba(192,54,44,.06)}
.page-srd .h-del svg{width:16px;height:16px}
.page-srd .hist-empty{text-align:center;padding:40px 20px;color:var(--muted);font-size:14px;background:var(--paper);border:1.5px dashed var(--line);border-radius:var(--radius-lg);margin-top:22px}
@media(max-width:720px){
.page-srd .hist-row{grid-template-columns:1fr;gap:10px}
.page-srd .h-acts{justify-content:flex-start}
}
.page-srd .run-bar{display:flex;flex-direction:column;align-items:center;gap:12px;margin-top:26px}
.page-srd .run-note{font-size:13px;color:var(--muted);display:inline-flex;align-items:center;gap:8px}
.page-srd .run-note .spark{color:var(--cinnabar)}
.page-srd .run-bar .btn-lg svg{width:19px;height:19px}
.page-srd .method{margin-top:clamp(30px,4vw,44px);background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-lg);overflow:hidden}
.page-srd .method>summary{display:flex;align-items:center;gap:12px;padding:18px 22px;cursor:pointer;list-style:none;font-weight:600;color:var(--indigo-900);font-size:1.02rem}
.page-srd .method>summary::-webkit-details-marker{display:none}
.page-srd .method>summary .mi{width:34px;height:34px;border-radius:10px;background:var(--indigo-100);color:var(--indigo-600);display:flex;align-items:center;justify-content:center;flex-shrink:0}
.page-srd .method>summary .mi svg{width:19px;height:19px}
.page-srd .method>summary small{margin-left:auto;font-family:"Source Sans 3","Noto Sans SC",sans-serif;font-weight:600;font-size:12.5px;color:var(--muted)}
.page-srd .method .mcaret{width:20px;height:20px;color:#7d90ad;transition:transform .3s var(--ease)}
.page-srd .method[open] .mcaret{transform:rotate(180deg)}
.page-srd .method-body{padding:4px 22px 24px;border-top:1px solid var(--line)}
.page-srd .method-cols{display:grid;grid-template-columns:1fr 1.25fr;gap:24px;padding-top:20px}
.page-srd .mh{font-size:12.5px;font-weight:700;color:var(--indigo-900);text-transform:uppercase;letter-spacing:.03em;margin-bottom:12px;font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-srd .scale{display:flex;flex-direction:column;gap:8px}
.page-srd .scale li{list-style:none;display:flex;align-items:center;gap:12px;font-size:13.5px;color:var(--ink)}
.page-srd .scale .lv{flex-shrink:0;width:88px;font-weight:700}
.page-srd .scale .rng{flex-shrink:0;font-variant-numeric:tabular-nums;color:var(--muted);font-size:12.5px;width:72px}
.page-srd .scale .ds{color:var(--muted);font-size:12.5px}
.page-srd .dom-legend{display:flex;flex-direction:column;gap:9px;font-size:13px;color:var(--muted);line-height:1.55}
.page-srd .dom-legend b{color:var(--indigo-800)}
.page-srd .keych{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:700;color:var(--cinnabar-d);background:rgba(192,54,44,.09);padding:2px 8px;border-radius:999px}
.page-srd .lvl{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:700;padding:4px 11px;border-radius:999px;white-space:nowrap}
.page-srd .lvl::before{content:"";width:7px;height:7px;border-radius:50%}
.page-srd .lvl-none{color:var(--info);background:var(--info-bg)}
.page-srd .lvl-none::before{background:var(--info)}
.page-srd .lvl-low{color:var(--indigo-600);background:var(--indigo-100)}
.page-srd .lvl-low::before{background:var(--indigo-500)}
.page-srd .lvl-mod{color:var(--amber);background:var(--amber-bg)}
.page-srd .lvl-mod::before{background:var(--amber)}
.page-srd .lvl-high{color:var(--cinnabar-d);background:rgba(192,54,44,.09)}
.page-srd .lvl-high::before{background:var(--cinnabar)}
.page-srd .results{background:var(--paper-2)}
.page-srd .res-flag{display:inline-flex;align-items:center;gap:9px;font-size:12.5px;font-weight:700;color:var(--amber);background:var(--amber-bg);
    border:1px solid #e7d39a;padding:7px 14px;border-radius:999px;margin-bottom:20px}
.page-srd .verdict{display:grid;grid-template-columns:auto 1fr;gap:clamp(20px,3vw,36px);align-items:center;
    background:var(--indigo-900);color:#fff;border-radius:var(--radius-lg);padding:clamp(24px,3vw,34px);position:relative;overflow:hidden;isolation:isolate}
.page-srd .verdict::before{content:"";position:absolute;inset:0;z-index:-1;background:radial-gradient(600px 300px at 100% 0,rgba(44,127,114,.4),transparent 60%)}
.page-srd .gauge{display:flex;flex-direction:column;align-items:center;gap:8px;min-width:150px}
.page-srd .gauge .ring{position:relative;width:132px;height:132px}
.page-srd .gauge svg{transform:rotate(-90deg)}
.page-srd .gauge .pctn{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
.page-srd .gauge .pctn b{font-family:"Spectral","Noto Serif SC",serif;font-weight:700;font-size:2rem;line-height:1;color:#fff}
.page-srd .gauge .pctn span{font-size:11px;color:rgba(233,238,247,.7);margin-top:3px;letter-spacing:.03em}
.page-srd .verdict-main h2{font-family:"Spectral","Noto Serif SC",serif;font-size:clamp(1.5rem,2.6vw,2rem);color:#fff;letter-spacing:-.01em;line-height:1.16}
.page-srd .verdict-main h2 .em{color:#ffb4ad}
.page-srd .verdict-main .vpair{font-size:13.5px;color:rgba(233,238,247,.8);margin-top:12px;line-height:1.6}
.page-srd .verdict-main .vpair b{color:#fff}
.page-srd .verdict-rec{margin-top:14px;font-size:14.5px;color:rgba(233,238,247,.94);line-height:1.6;max-width:60ch}
.page-srd .dom-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin-top:18px}
.page-srd .dtile{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px 18px 16px}
.page-srd .dtile .dt-top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px}
.page-srd .dtile .dt-name{font-weight:700;color:var(--indigo-900);font-size:14.5px}
.page-srd .dtile .dt-name small{display:block;font-family:"Source Sans 3","Noto Sans SC",sans-serif;font-weight:600;font-size:11px;color:var(--muted);margin-top:2px}
.page-srd .dtile .bar{height:7px;border-radius:999px;background:var(--paper-2);overflow:hidden;margin-bottom:8px}
.page-srd .dtile .bar i{display:block;height:100%;border-radius:999px}
.page-srd .dtile .dt-pct{font-size:12.5px;color:var(--muted);font-variant-numeric:tabular-nums}
.page-srd .dtile .dt-pct b{color:var(--indigo-800)}
.page-srd .res-tools{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;margin:26px 0 14px}
.page-srd .res-tools h3{font-size:1.2rem;color:var(--indigo-900)}
.page-srd .res-tools .rt-btns{display:flex;gap:10px;flex-wrap:wrap}
.page-srd .rd{background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden;margin-bottom:12px}
.page-srd .rd>summary{display:flex;align-items:center;gap:14px;padding:16px 20px;cursor:pointer;list-style:none}
.page-srd .rd>summary::-webkit-details-marker{display:none}
.page-srd .rd-badge{width:30px;height:30px;flex-shrink:0;border-radius:9px;background:var(--indigo-100);color:var(--indigo-700);display:flex;align-items:center;justify-content:center;
    font-family:"Spectral",serif;font-weight:700;font-size:14px}
.page-srd .rd-dn{flex:1;min-width:0}
.page-srd .rd-dn b{font-size:1.02rem;color:var(--indigo-900);font-family:"Spectral","Noto Serif SC",serif;font-weight:600}
.page-srd .rd-dn span{display:block;font-size:12px;color:var(--muted);margin-top:1px}
.page-srd .rd-caret{width:19px;height:19px;color:#7d90ad;transition:transform .3s var(--ease);flex-shrink:0}
.page-srd .rd[open] .rd-caret{transform:rotate(180deg)}
.page-srd .rd-body{border-top:1px solid var(--line);overflow-x:auto}
.page-srd table.srd{width:100%;border-collapse:collapse;min-width:760px;font-size:13.5px}
.page-srd table.srd th{background:var(--paper-2);text-align:left;font-family:"Source Sans 3","Noto Sans SC",sans-serif;font-weight:700;font-size:12px;
    color:var(--indigo-800);letter-spacing:.02em;padding:11px 14px;border-bottom:1px solid var(--line);white-space:nowrap}
.page-srd table.srd td{padding:13px 14px;border-bottom:1px solid var(--line);vertical-align:top;line-height:1.55;color:var(--ink)}
.page-srd table.srd tr:last-child td{border-bottom:none}
.page-srd table.srd tr:hover td{background:var(--paper)}
.page-srd .c-id{font-family:"Spectral",serif;font-weight:700;color:var(--indigo-600);white-space:nowrap;width:44px}
.page-srd .c-q{min-width:200px;max-width:320px}
.page-srd .c-v{width:104px}
.page-srd .c-basis{color:var(--muted);min-width:180px}
.page-srd .cite{display:block;font-size:12px;color:var(--muted);line-height:1.5;padding-left:12px;position:relative;margin-top:4px}
.page-srd .cite:first-of-type{margin-top:0}
.page-srd .cite::before{content:"";position:absolute;left:0;top:6px;bottom:6px;width:2px;border-radius:2px}
.page-srd .cite.a::before{background:var(--indigo-500)}
.page-srd .cite.b::before{background:var(--info)}
.page-srd .cite em{font-style:normal;font-weight:700;color:var(--indigo-700);margin-right:5px}
.page-srd .cite.b em{color:var(--info)}
@media(max-width:900px){
.page-srd .io-grid{grid-template-columns:1fr}
.page-srd .method-cols{grid-template-columns:1fr;gap:20px}
.page-srd .verdict{grid-template-columns:1fr;text-align:center;justify-items:center}
.page-srd .gauge{min-width:0}
}
@media print{
.page-srd .phero,.page-srd .tool,.page-srd .method,.page-srd .res-tools .rt-btns{display:none !important}
.page-srd body{background:#fff}
.page-srd .results{background:#fff;padding:0}
.page-srd .rd,.page-srd .rd-body{break-inside:avoid}
.page-srd .rd[open] .rd-caret{display:none}
.page-srd table.srd{min-width:0;font-size:11px}
}
</style>
