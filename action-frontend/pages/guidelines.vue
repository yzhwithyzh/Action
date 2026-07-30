<script setup lang="ts">
/**
 * guidelines.html 迁移而来。
 * 模板与样式保持原状；样式已加 .page-guidelines 命名空间，避免 SPA 路由切换时跨页污染。
 */
interface GuidelineRow {
  guidelineId: number
  code: string
  nameZh: string | null
  nameEn: string | null
  studyType: string | null
  summaryZh: string | null
  summaryEn: string | null
  version: string | null
  fileUrlZh: string | null
  fileUrlEn: string | null
  externalUrl: string | null
  logoUrl: string | null
  releaseState: 'open' | 'beta' | 'soon' | null
}

const { t } = useI18n()
const { pick } = useBilingual()

useHead({
  title: t('guidelines._title'),
  meta: [{ name: 'description', content: t('guidelines._desc') }],
})

const { data: glRes } = await useSiteList<GuidelineRow>(
  '/guidelines',
  { pageNum: 1, pageSize: 20 },
  'guidelines-page',
)
const rows = computed<GuidelineRow[]>(() => glRes.value?.rows ?? [])

/**
 * 接口的 studyType 用 action_study_type.type_key 那套术语，页面筛选条用另一套。
 * 见 deferred-work.md 的 W23：两套词表只在 rct/case 上同名。
 */
const CAT_OF: Record<string, string> = {
  rct: 'rct',
  protocol: 'protocol',
  sr: 'review',
  case: 'case',
  guideline: 'cpg',
  animal: 'animal',
}
const catOf = (r: GuidelineRow) => CAT_OF[r.studyType ?? ''] ?? 'all'

/** 研究设计标签：复用筛选条已有的 i18n 键，不另起一套文案 */
const CAT_LABEL: Record<string, string> = {
  rct: 'guidelines.s005',
  protocol: 'guidelines.s006',
  review: 'guidelines.s007',
  case: 'guidelines.s008',
  cpg: 'guidelines.s009',
  animal: 'guidelines.s010',
}
const catLabel = (r: GuidelineRow) => {
  const key = CAT_LABEL[catOf(r)]

  return key ? t(key) : ''
}

/** 卡片图标（纯装饰，接口不含图形数据），按研究设计取 */
const ICON: Record<string, string[]> = {
  rct: ['M4 5h16M4 5v14M4 19h16', 'M8 15l3-4 2 2 3-5'],
  protocol: ['M8 3h6l4 4v14H6V5', 'M8 3v4H4', 'M9 13h6M9 17h4'],
  review: ['M12 3v18', 'M5 8l7-5 7 5', 'M5 8v8l7 5 7-5V8'],
  case: ['M7 3h7l4 4v14H6V4', 'M14 3v4h4', 'M12 11v6M9 14h6'],
  cpg: ['M12 3l8 4v6c0 4.5-3.2 7-8 8-4.8-1-8-3.5-8-8V7z', 'M9 12l2 2 4-4'],
  animal: ['M4 20c0-3 2-5 4-5s4 2 4 5', 'M15 8c2 0 4 1.5 4 4s-2 4-4 4', 'M17 12h.01'],
}
const iconOf = (r: GuidelineRow) => ICON[catOf(r)] ?? []

/** 三个链接字段是否至少有一个可用 —— 全空时不渲染 .dl-side */
const hasAnyLink = (r: GuidelineRow) => Boolean(r.fileUrlZh || r.fileUrlEn || r.externalUrl)

/** 开放状态 → 文案键。原页面 CARE 用 `.st pub`（已发表）、其余 `.st cur`（现行）；
 *  接口只有 open/beta/soon 三态，无「已发表」语义，故统一按状态映射，不臆造 pub。 */
const ST_LABEL: Record<string, string> = {
  open: 'guidelines.stOpen',
  beta: 'guidelines.stBeta',
  soon: 'guidelines.stSoon',
}
const ST_CLASS: Record<string, string> = { open: 'cur', beta: 'beta', soon: 'soon' }
const stLabel = (r: GuidelineRow) => {
  const key = ST_LABEL[r.releaseState ?? 'open']

  return key ? t(key) : String(r.releaseState ?? '')
}

const activeCat = ref('all')
/** 筛选用 CSS 隐藏而不卸载节点，理由同 news.vue（原页面也是 toggle('hide')） */
const isHidden = (r: GuidelineRow) => activeCat.value !== 'all' && catOf(r) !== activeCat.value

useReveal()
</script>

<template>
  <div class="page-guidelines">
    <!-- ===================== ① 分类导航 ===================== -->
    <section class="sec" id="nav">
      <div class="wrap">
        <span class="kicker reveal">{{ t('guidelines.s001') }}</span>
        <h2 class="title reveal">{{ t('guidelines.s002') }}</h2>
        <p class="lead reveal">{{ t('guidelines.s003') }}</p>

        <div class="gl-filter reveal" role="group" aria-label="按研究类型筛选">
          <button
            v-for="c in ['all', 'rct', 'protocol', 'review', 'case', 'cpg', 'animal']"
            :key="c"
            class="gl-chip"
            :class="{ on: activeCat === c }"
            :aria-pressed="activeCat === c"
            :data-filter="c"
            @click="activeCat = c"
          >
            {{ t(c === 'all' ? 'guidelines.s004' : CAT_LABEL[c]) }}
          </button>
        </div>

        <div class="gl-grid">
          <a v-for="r in rows" :key="r.guidelineId" class="gl-card reveal" :class="{ hide: isHidden(r) }" href="#download" :data-cat="catOf(r)">
            <div class="gl-top">
              <span class="gl-ic" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                  <path v-for="(d, k) in iconOf(r)" :key="k" :d="d" />
                </svg>
              </span>
              <span><span class="gl-type">{{ catLabel(r) }}</span><span class="gl-abbr">{{ r.code }}</span></span>
            </div>
            <p class="gl-basis">{{ pick(r, 'summary') }}</p>
            <div class="gl-meta"><span v-if="r.version">{{ r.version }}</span></div>
            <span class="gl-go" v-html="t('guidelines.s015')"></span>
          </a>
        </div>
      </div>
    </section>
    <!-- ===================== ② 在线预览与下载 ===================== -->
    <section class="sec is-hidden" id="download" style="background:var(--paper-2)">
      <div class="wrap">
        <span class="kicker reveal">{{ t('guidelines.s039') }}</span>
        <h2 class="title reveal">{{ t('guidelines.s040') }}</h2>
        <p class="lead reveal">{{ t('guidelines.s041') }}</p>

        <div class="dl-list">
          <details v-for="r in rows" :key="r.guidelineId" class="dl-item reveal">
            <summary class="dl-sum">
              <span class="dl-badge" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                  <path v-for="(d, k) in iconOf(r)" :key="k" :d="d" />
                </svg>
                <span>{{ catLabel(r) }}</span>
              </span>
              <span class="dl-h">
                <span class="dl-abbr">{{ r.code }}</span>
                <p>{{ pick(r, 'name') }}</p>
              </span>
              <span v-if="r.version" class="dl-tag live">{{ r.version }}</span>
              <svg class="dl-caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
            </summary>
            <div class="dl-body">
              <div class="dl-body-in">
                <div class="dl-intro">
                  <p>{{ pick(r, 'summary') }}</p>
                </div>
                <div v-if="hasAnyLink(r)" class="dl-side">
                  <h4>{{ t('guidelines.s046') }}</h4>
                  <div class="dl-btns">
                    <a v-if="r.fileUrlZh" class="dl-btn" :href="r.fileUrlZh" download>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 3v12m0 0 4-4m-4 4-4-4M5 21h14" /></svg>
                      <span>{{ t('guidelines.s047') }}</span><span class="ext">DOCX</span>
                    </a>
                    <a v-if="r.fileUrlEn" class="dl-btn" :href="r.fileUrlEn" download>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 3v12m0 0 4-4m-4 4-4-4M5 21h14" /></svg>
                      <span>{{ t('guidelines.s048') }}</span><span class="ext">DOCX</span>
                    </a>
                    <a v-if="r.externalUrl" class="dl-btn prev" :href="r.externalUrl" target="_blank" rel="noopener noreferrer">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M7 17 17 7M8 7h9v9" /></svg>
                      <span>{{ t('guidelines.s049') }}</span><span class="ext">{{ t('guidelines.s050') }}</span>
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </details>
        </div>
      </div>
    </section>
    <!-- ===================== ③ 版本管理 ===================== -->
    <section class="sec is-hidden" id="versions">
      <div class="wrap">
        <span class="kicker reveal">{{ t('guidelines.s116') }}</span>
        <h2 class="title reveal">{{ t('guidelines.s117') }}</h2>
        <p class="lead reveal">{{ t('guidelines.s118') }}</p>

        <div class="tbl-wrap reveal">
          <div class="tbl-scroll">
            <table class="act">
              <thead>
                <tr>
                  <th>{{ t('guidelines.s119') }}</th>
                  <th>{{ t('guidelines.s120') }}</th>
                  <th>{{ t('guidelines.s121') }}</th>
                  <th>{{ t('guidelines.s122') }}</th>
                  <th>{{ t('guidelines.s123') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in rows" :key="r.guidelineId">
                  <td><span class="abbr">{{ r.code }}</span><span class="sub">{{ pick(r, 'name') }}</span></td>
                  <td>{{ catLabel(r) }}</td>
                  <td>{{ r.version }}</td>
                  <td><span class="st" :class="ST_CLASS[r.releaseState ?? 'open'] ?? 'cur'">{{ stLabel(r) }}</span></td>
                  <td>
                    <a v-if="r.externalUrl" :href="r.externalUrl" target="_blank" rel="noopener noreferrer">{{ r.externalUrl }}</a>
                    <span v-else>—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="tbl-note" v-html="t('guidelines.s154')"></p>
        </div>
      </div>
    </section>
    <!-- ===================== ④ 试点测试 ===================== -->
    <section class="sec is-hidden" id="pilot" style="background:var(--paper-2)">
      <div class="wrap">
        <span class="kicker reveal">{{ t('guidelines.s155') }}</span>
        <h2 class="title reveal">{{ t('guidelines.s156') }}</h2>
        <p class="lead reveal">{{ t('guidelines.s157') }}</p>

        <div class="pilot-grid">
          <div class="pilot-copy reveal">
            <p>{{ t('guidelines.s158') }}</p>
            <p v-html="t('guidelines.s159')"></p>

            <div class="mini-tbl reveal">
              <div class="tbl-wrap" style="margin-top:8px">
                <div class="tbl-scroll">
                  <table class="act">
                    <thead>
                      <tr>
                        <th>{{ t('guidelines.s160') }}</th>
                        <th>{{ t('guidelines.s161') }}</th>
                        <th>{{ t('guidelines.s162') }}</th>
                        <th>{{ t('guidelines.s163') }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr><td>{{ t('guidelines.s164') }}</td><td>2024.05–08</td><td>38</td><td>{{ t('guidelines.s165') }}</td></tr>
                      <tr><td>{{ t('guidelines.s166') }}</td><td>2024.09</td><td>30</td><td>{{ t('guidelines.s167') }}</td></tr>
                      <tr><td>{{ t('guidelines.s168') }}</td><td>2024.10</td><td>24</td><td>{{ t('guidelines.s169') }}</td></tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <div class="pilot-cta reveal">
              <a class="btn btn-primary" href="https://doi.org/10.1136/bmjebm-2025-113641" target="_blank" rel="noopener noreferrer" v-html="t('guidelines.s170')"></a>
              <a class="btn btn-ghost" href="#download">{{ t('guidelines.s171') }}</a>
            </div>
            <p class="src reveal" v-html="t('guidelines.s172')"></p>
          </div>

          <aside class="pilot-facts reveal" aria-label="试点测试关键数字">
            <div class="fact"><b>38</b><span>{{ t('guidelines.s173') }}</span></div>
            <div class="fact"><b>16</b><span>{{ t('guidelines.s174') }}</span></div>
            <div class="fact"><b>3</b><span>{{ t('guidelines.s175') }}</span></div>
            <div class="fact"><b>414</b><span>{{ t('guidelines.s176') }}</span></div>
            <div class="fact warm"><b>0.163<span class="u">W</span></b><span v-html="t('guidelines.s177')"></span></div>
            <div class="fact warm"><b>15.1<span class="u">%</span></b><span>{{ t('guidelines.s178') }}</span></div>
          </aside>
        </div>
      </div>
    </section>
  </div>
</template>

<style>
.page-guidelines .skip-link{position:absolute;left:12px;top:-60px;z-index:var(--z-toast);background:var(--indigo-700);color:#fff;
    font-weight:600;font-size:15px;padding:12px 20px;border-radius:10px;transition:top .2s var(--ease)}
.page-guidelines .sec{padding:clamp(52px,7vw,88px) 0;scroll-margin-top:128px}
.page-guidelines .kicker{display:inline-flex;align-items:center;gap:9px;font-size:13.5px;font-weight:600;letter-spacing:.02em;
    color:var(--indigo-500);margin-bottom:16px}
.page-guidelines .kicker.on-dark{color:var(--indigo-200)}
.page-guidelines h2.title{font-size:clamp(1.7rem,3.4vw,2.5rem);color:var(--indigo-900);letter-spacing:-.02em;text-wrap:balance;max-width:26ch}
.page-guidelines h2.title.on-dark{color:#fff}
.page-guidelines .lead{color:var(--muted);font-size:clamp(1.02rem,1.4vw,1.16rem);max-width:66ch;margin-top:18px;text-wrap:pretty}
.page-guidelines .lead.on-dark{color:rgba(233,238,247,.86)}
.page-guidelines .sec-head{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;flex-wrap:wrap}
.page-guidelines .btn{display:inline-flex;align-items:center;gap:9px;padding:13px 24px;border-radius:999px;font-weight:600;font-size:15px;
    border:1.5px solid transparent;cursor:pointer;white-space:nowrap;
    transition:transform .25s var(--ease),background-color .25s var(--ease),box-shadow .25s var(--ease),border-color .25s var(--ease)}
.page-guidelines .btn-lg{padding:15px 28px;font-size:15.5px}
.page-guidelines .phero{position:relative;overflow:hidden;background:var(--indigo-900);color:#fff;isolation:isolate}
.page-guidelines .phero::before{content:"";position:absolute;inset:0;z-index:-1;
    background:radial-gradient(1000px 560px at 90% 0%,rgba(44,127,114,.5),transparent 60%),
    radial-gradient(680px 460px at 2% 100%,rgba(24,48,41,.7),transparent 65%),
    linear-gradient(160deg,#0d1a17 0%,#12211d 44%,#183029 100%)}
.page-guidelines .phero .wrap{padding:clamp(30px,4vw,44px) clamp(20px,4vw,44px) clamp(46px,6vw,64px)}
.page-guidelines .crumb{display:flex;align-items:center;gap:9px;font-size:13.5px;color:rgba(233,238,247,.66);margin-bottom:26px;flex-wrap:wrap}
.page-guidelines .phero-tag{display:inline-flex;align-items:center;gap:10px;font-size:13px;font-weight:600;letter-spacing:.02em;
    color:var(--indigo-200);background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.16);
    padding:8px 16px;border-radius:999px;backdrop-filter:blur(4px)}
.page-guidelines .phero h1{font-size:clamp(2rem,4.2vw,3.3rem);font-weight:700;letter-spacing:-.025em;margin:20px 0 0;text-wrap:balance;line-height:1.14}
.page-guidelines .phero .psub{margin-top:20px;font-size:clamp(1.02rem,1.5vw,1.2rem);color:rgba(233,238,247,.9);max-width:60ch;line-height:1.72;text-wrap:pretty}
.page-guidelines .phero-stats{display:flex;flex-wrap:wrap;gap:14px;margin-top:34px}
.page-guidelines .pstat{display:flex;flex-direction:column;gap:4px;padding:15px 22px;background:rgba(255,255,255,.05);
    border:1px solid rgba(255,255,255,.14);border-radius:14px}
.page-guidelines .pstat b{font-family:"Spectral","Noto Serif SC",serif;font-weight:700;font-size:1.5rem;color:#fff;line-height:1.1}
.page-guidelines .pstat span{display:inline-flex;align-items:center;gap:8px;font-size:13px;color:rgba(233,238,247,.72)}
.page-guidelines .pstat span::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--cinnabar);flex-shrink:0}
.page-guidelines .subnav{position:sticky;top:72px;z-index:var(--z-subnav);background:rgba(242,246,244,.9);
    backdrop-filter:blur(12px) saturate(1.3);border-bottom:1px solid var(--line)}
.page-guidelines .subnav-in{display:flex;align-items:center;gap:4px;overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none}
.page-guidelines .subnav-in::-webkit-scrollbar{display:none}
.page-guidelines .subnav a{position:relative;flex-shrink:0;padding:16px 16px 14px;font-size:14.5px;font-weight:600;color:var(--muted);
    white-space:nowrap;transition:color .2s}
.page-guidelines .subnav a .n{display:inline-flex;align-items:center;justify-content:center;width:19px;height:19px;margin-right:7px;
    border-radius:6px;background:var(--indigo-100);color:var(--indigo-600);font-size:11.5px;font-weight:700;
    font-family:"Spectral",serif;transition:.2s}
.page-guidelines .subnav a::after{content:"";position:absolute;left:16px;right:16px;bottom:-1px;height:2px;background:var(--cinnabar);
    transform:scaleX(0);transform-origin:left;transition:transform .3s var(--ease)}
.page-guidelines .subnav a:hover{color:var(--indigo-900)}
.page-guidelines .subnav a.active{color:var(--indigo-900)}
.page-guidelines .subnav a.active .n{background:var(--cinnabar);color:#fff}
.page-guidelines .subnav a.active::after{transform:scaleX(1)}
.page-guidelines .gl-filter{display:flex;flex-wrap:wrap;gap:9px;margin-top:clamp(26px,3.5vw,36px)}
.page-guidelines .gl-chip{font-size:13.5px;font-weight:600;color:var(--indigo-700);background:var(--surface);border:1.5px solid var(--line);
    padding:8px 16px;border-radius:999px;cursor:pointer;transition:.2s var(--ease)}
.page-guidelines .gl-chip:hover{border-color:var(--indigo-300);background:var(--indigo-100)}
.page-guidelines .gl-chip.on{background:var(--indigo-700);border-color:var(--indigo-700);color:#fff}
.page-guidelines .gl-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;margin-top:22px}
.page-guidelines .gl-card{display:flex;flex-direction:column;gap:13px;background:var(--surface);border:1px solid var(--line);
    border-radius:var(--radius-lg);padding:26px 26px 22px;color:inherit;position:relative;
    transition:transform .25s var(--ease),box-shadow .25s var(--ease),border-color .25s var(--ease)}
.page-guidelines .gl-card:hover{transform:translateY(-3px);box-shadow:var(--shadow-md);border-color:var(--indigo-200)}
.page-guidelines .gl-card.hide{display:none}
.page-guidelines .gl-top{display:flex;align-items:center;gap:13px}
.page-guidelines .gl-ic{width:44px;height:44px;flex-shrink:0;border-radius:12px;background:var(--indigo-100);color:var(--indigo-600);
    display:flex;align-items:center;justify-content:center}
.page-guidelines .gl-ic svg{width:24px;height:24px}
.page-guidelines .gl-top>span:last-child{display:flex;flex-direction:column;gap:2px;min-width:0}
.page-guidelines .gl-type{display:block;font-size:12px;font-weight:700;color:var(--indigo-500);letter-spacing:.02em}
.page-guidelines .gl-abbr{display:block;font-family:"Spectral","Noto Serif SC",serif;font-weight:700;font-size:1.32rem;color:var(--indigo-900);line-height:1.1}
.page-guidelines .gl-card h3{font-size:1.02rem;color:var(--ink);font-family:"Source Sans 3","Noto Sans SC",sans-serif;font-weight:600}
.page-guidelines .gl-basis{font-size:13.5px;color:var(--muted);line-height:1.55}
.page-guidelines .gl-basis b{color:var(--indigo-700);font-family:inherit;font-weight:700}
.page-guidelines .gl-meta{display:flex;flex-wrap:wrap;gap:6px;margin-top:2px}
.page-guidelines .gl-meta span{font-size:12px;font-weight:600;color:var(--indigo-700);background:var(--indigo-100);padding:3px 10px;border-radius:999px}
.page-guidelines .gl-go{margin-top:auto;padding-top:6px;display:inline-flex;align-items:center;gap:7px;font-weight:600;font-size:14px;color:var(--cinnabar)}
.page-guidelines .gl-go .arrow{transition:transform .3s var(--ease)}
.page-guidelines .gl-card:hover .gl-go .arrow{transform:translateX(3px)}
.page-guidelines .dl-list{margin-top:clamp(28px,3.5vw,38px);display:flex;flex-direction:column;gap:12px}
.page-guidelines .dl-item{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-lg);overflow:hidden;
    transition:border-color .25s var(--ease),box-shadow .25s var(--ease)}
.page-guidelines .dl-item[open]{border-color:var(--indigo-200);box-shadow:var(--shadow-sm)}
.page-guidelines .dl-sum{display:flex;align-items:center;gap:16px;padding:20px 24px;cursor:pointer;list-style:none;user-select:none}
.page-guidelines .dl-sum::-webkit-details-marker{display:none}
.page-guidelines .dl-badge{flex-shrink:0;width:52px;height:52px;border-radius:13px;background:var(--indigo-100);color:var(--indigo-700);
    display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:"Spectral",serif;font-weight:700;
    font-size:11px;line-height:1;gap:2px}
.page-guidelines .dl-badge svg{width:23px;height:23px}
.page-guidelines .dl-h{flex:1;min-width:0}
.page-guidelines .dl-h .dl-abbr{font-family:"Spectral","Noto Serif SC",serif;font-weight:700;font-size:1.22rem;color:var(--indigo-900);line-height:1.15}
.page-guidelines .dl-h .dl-abbr .zh{font-family:"Noto Serif SC",serif}
.page-guidelines .dl-h p{font-size:13.5px;color:var(--muted);margin-top:3px;line-height:1.5}
.page-guidelines .dl-tag{flex-shrink:0;font-size:12px;font-weight:700;padding:5px 12px;border-radius:999px;white-space:nowrap}
.page-guidelines .dl-tag.live{color:var(--indigo-600);background:var(--indigo-100)}
.page-guidelines .dl-tag.pub{color:var(--cinnabar-d);background:rgba(192,54,44,.09)}
.page-guidelines .dl-caret{flex-shrink:0;width:22px;height:22px;color:var(--indigo-400,#7d90ad);transition:transform .3s var(--ease)}
.page-guidelines .dl-item[open] .dl-caret{transform:rotate(180deg)}
.page-guidelines .dl-body{padding:2px 24px 24px;border-top:1px solid var(--line)}
.page-guidelines .dl-body-in{padding-top:20px;display:grid;grid-template-columns:1.35fr 1fr;gap:clamp(20px,3vw,40px)}
.page-guidelines .dl-intro p{font-size:14.5px;color:var(--ink);line-height:1.66}
.page-guidelines .dl-intro p+p{margin-top:12px}
.page-guidelines .dl-intro .muted{color:var(--muted);font-size:13.5px}
.page-guidelines .dl-doms{margin-top:16px;display:flex;flex-wrap:wrap;gap:6px}
.page-guidelines .dl-doms li{list-style:none;font-size:12.5px;font-weight:600;color:var(--indigo-700);background:var(--paper-2);
    border:1px solid var(--line);padding:4px 10px;border-radius:8px}
.page-guidelines .dl-doms li b{color:var(--cinnabar-d);font-family:"Spectral",serif;margin-right:5px}
.page-guidelines .dl-side{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:20px}
.page-guidelines .dl-side h4{font-size:13px;font-weight:700;letter-spacing:.02em;color:var(--indigo-900);
    font-family:"Source Sans 3","Noto Sans SC",sans-serif;margin-bottom:14px;text-transform:uppercase}
.page-guidelines .dl-btns{display:flex;flex-direction:column;gap:9px}
.page-guidelines .dl-btn{display:flex;align-items:center;gap:11px;padding:11px 14px;border-radius:11px;border:1.5px solid var(--line);
    background:var(--surface);font-size:14px;font-weight:600;color:var(--indigo-800);transition:.2s var(--ease)}
.page-guidelines .dl-btn:hover{border-color:var(--indigo-300);background:var(--indigo-100);transform:translateX(2px)}
.page-guidelines .dl-btn svg{width:19px;height:19px;flex-shrink:0;color:var(--indigo-500)}
.page-guidelines .dl-btn .ext{margin-left:auto;font-size:11px;font-weight:700;color:var(--muted);letter-spacing:.04em}
.page-guidelines .dl-btn.prev{border-color:var(--indigo-200);background:var(--indigo-100)}
.page-guidelines .dl-btn.prev svg{color:var(--cinnabar)}
.page-guidelines .tbl-wrap{margin-top:clamp(26px,3vw,34px);border:1px solid var(--line);border-radius:var(--radius-lg);overflow:hidden;background:var(--surface)}
.page-guidelines .tbl-scroll{overflow-x:auto}
.page-guidelines table.act{width:100%;border-collapse:collapse;min-width:640px;font-size:14.5px}
.page-guidelines table.act thead th{background:var(--indigo-900);color:#fff;text-align:left;font-family:"Source Sans 3","Noto Sans SC",sans-serif;
    font-weight:600;font-size:13.5px;letter-spacing:.02em;padding:14px 18px;white-space:nowrap}
.page-guidelines table.act tbody td{padding:15px 18px;border-top:1px solid var(--line);color:var(--ink);line-height:1.55;vertical-align:top}
.page-guidelines table.act tbody tr:nth-child(even){background:var(--paper)}
.page-guidelines table.act tbody tr:hover{background:var(--indigo-100)}
.page-guidelines table.act .abbr{font-family:"Spectral","Noto Serif SC",serif;font-weight:700;color:var(--indigo-900);font-size:15px}
.page-guidelines table.act .sub{display:block;font-size:12.5px;color:var(--muted);margin-top:2px;font-weight:400}
.page-guidelines .st{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:700;padding:4px 11px;border-radius:999px;white-space:nowrap}
.page-guidelines .st::before{content:"";width:6px;height:6px;border-radius:50%}
.page-guidelines .st.pub{color:var(--cinnabar-d);background:rgba(192,54,44,.09)}
.page-guidelines .st.pub::before{background:var(--cinnabar)}
.page-guidelines .st.cur{color:var(--indigo-600);background:var(--indigo-100)}
.page-guidelines .st.cur::before{background:var(--indigo-500)}
.page-guidelines .tbl-note{padding:14px 18px;font-size:13px;color:var(--muted);background:var(--paper-2);border-top:1px solid var(--line);line-height:1.55}
.page-guidelines .tbl-note b{color:var(--indigo-700)}
.page-guidelines .pilot-grid{display:grid;grid-template-columns:1.15fr 1fr;gap:clamp(26px,4vw,52px);margin-top:clamp(30px,4vw,44px);align-items:start}
.page-guidelines .pilot-copy p{font-size:15px;color:var(--ink);line-height:1.72}
.page-guidelines .pilot-copy p+p{margin-top:14px}
.page-guidelines .pilot-copy .src{margin-top:22px;padding:16px 18px;background:var(--surface);border:1px solid var(--line);border-radius:14px;
    font-size:13.5px;color:var(--muted);line-height:1.6}
.page-guidelines .pilot-copy .src b{color:var(--indigo-800)}
.page-guidelines .pilot-cta{display:flex;flex-wrap:wrap;gap:12px;margin-top:22px}
.page-guidelines .pilot-facts{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.page-guidelines .fact{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:20px}
.page-guidelines .fact b{display:block;font-family:"Spectral","Noto Serif SC",serif;font-weight:700;font-size:1.85rem;color:var(--indigo-900);line-height:1}
.page-guidelines .fact b .u{font-size:.9rem;color:var(--indigo-500);margin-left:3px}
.page-guidelines .fact span{display:block;font-size:13px;color:var(--muted);margin-top:7px;line-height:1.45}
.page-guidelines .fact.warm{background:linear-gradient(180deg,#fff,var(--indigo-100));border-color:var(--indigo-200)}
.page-guidelines .mini-tbl{margin-top:16px}
.page-guidelines .mini-tbl table{min-width:0}
.page-guidelines .mini-tbl table.act tbody td{padding:11px 14px;font-size:13.5px}
.page-guidelines .mini-tbl table.act thead th{padding:11px 14px}
@media (prefers-reduced-motion:no-preference){
.page-guidelines html.js .reveal{opacity:0;transform:translateY(18px);transition:opacity .8s var(--ease),transform .8s var(--ease)}
.page-guidelines html.js .reveal.is-visible{opacity:1;transform:none}
}
@media(max-width:1000px){
.page-guidelines .dl-body-in{grid-template-columns:1fr;gap:22px}
.page-guidelines .pilot-grid{grid-template-columns:1fr;gap:30px}
}
@media(max-width:820px){
.page-guidelines .pilot-facts{grid-template-columns:1fr 1fr}
.page-guidelines .mobile-menu .btn{width:100%;justify-content:center;margin-top:24px}
}
@media(max-width:520px){
.page-guidelines .dl-sum{flex-wrap:wrap;gap:12px}
.page-guidelines .dl-tag{order:3}
}
</style>
