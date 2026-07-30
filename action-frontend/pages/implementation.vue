<script setup lang="ts">
/**
 * implementation.html 迁移而来。
 * 模板与样式保持原状；样式已加 .page-implementation 命名空间，避免 SPA 路由切换时跨页污染。
 */
const { t } = useI18n()

interface CfirStrategy {
  strategyId: number
  nameZh: string | null
  nameEn: string | null
  detailZh: string | null
  detailEn: string | null
  sourceZh: string | null
  sourceEn: string | null
}
interface CfirConstruct {
  constructId: number
  code: string
  nameZh: string | null
  nameEn: string | null
  hintZh: string | null
  hintEn: string | null
  severity: 'h' | 'm' | 'l' | null
  strategies: CfirStrategy[]
}
interface CfirDomain {
  domainId: number
  seq: number
  nameZh: string | null
  nameEn: string | null
  constructs: CfirConstruct[]
}
interface EricCategory { catKey: string; nameZh: string | null; nameEn: string | null }
interface EricStrategy {
  ericId: number
  category: string
  nameZh: string | null
  nameEn: string | null
  detailZh: string | null
  detailEn: string | null
  mapZh: string | null
  mapEn: string | null
}
interface ReaimDim {
  dimId: number
  letter: string
  nameZh: string | null
  nameEn: string | null
  subTitle: string | null
  definitionZh: string | null
  definitionEn: string | null
  measureZh: string | null
  measureEn: string | null
  scoreText: string | null
}

useHead({
  title: t('implementation._title'),
  meta: [{ name: 'description', content: t('implementation._desc') }],
})

const { pick } = useBilingual()

const { data: cfirRes } = await useSiteObject<CfirDomain[]>('/implementation/cfir', 'impl-cfir')
const { data: ericRes } = await useSiteObject<{ categories: EricCategory[]; strategies: EricStrategy[] }>(
  '/implementation/eric',
  'impl-eric',
)
const { data: reaimRes } = await useSiteObject<ReaimDim[]>('/implementation/reaim', 'impl-reaim')

const domains = computed<CfirDomain[]>(() => cfirRes.value?.data ?? [])
const ericCats = computed<EricCategory[]>(() => ericRes.value?.data?.categories ?? [])
const ericAll = computed<EricStrategy[]>(() => ericRes.value?.data?.strategies ?? [])
const reaimDims = computed<ReaimDim[]>(() => reaimRes.value?.data ?? [])

/* ---------- ERIC 分类筛选（分类条本身也由接口数据生成，渲染了就得能点） ---------- */
const ericCat = ref('all')
/** 同 news/guidelines：用 CSS 隐藏，与原 implementation.html 的 toggle('hide') 一致 */
const ericHidden = (e: EricStrategy) => ericCat.value !== 'all' && e.category !== ericCat.value
const catName = (key: string) => {
  const c = ericCats.value.find((x) => x.catKey === key)

  return c ? pick(c, 'name') : key
}

/* ---------- 障碍选择 ---------- */
const SEV_CLASS: Record<string, string> = { h: 'sev-h', m: 'sev-m', l: 'sev-l' }
const SEV_LABEL: Record<string, string> = {
  h: 'implementation.sevH',
  m: 'implementation.sevM',
  l: 'implementation.sevL',
}

const selected = ref<Set<number>>(new Set())
const selCount = computed(() => selected.value.size)

const toggle = (id: number, checked: boolean) => {
  const next = new Set(selected.value)
  checked ? next.add(id) : next.delete(id)
  selected.value = next
}
const clearSel = () => {
  selected.value = new Set()
  report.value = null
}

/* ---------- 报告 ---------- */
interface ReportRow { domain: CfirDomain; construct: CfirConstruct }
const report = ref<ReportRow[] | null>(null)

const buildReport = () => {
  const picked: ReportRow[] = []
  for (const d of domains.value) {
    for (const c of d.constructs) {
      if (selected.value.has(c.constructId)) picked.push({ domain: d, construct: c })
    }
  }
  report.value = picked
}

const repStats = computed(() => {
  const rows = report.value ?? []

  return {
    barriers: rows.length,
    strategies: rows.reduce((n, r) => n + (r.construct.strategies?.length ?? 0), 0),
    domains: new Set(rows.map((r) => r.domain.domainId)).size,
  }
})

/** 表格里同一领域只在首行前插一条分组行 */
const isNewGroup = (idx: number) => {
  const rows = report.value ?? []

  return idx === 0 || rows[idx].domain.domainId !== rows[idx - 1].domain.domainId
}

useReveal()
</script>

<template>
  <div class="page-implementation">
    <!-- ===================== CFIR ===================== -->
    <section class="sec" id="cfir">
      <div class="wrap">
        <div class="toolhead cfir">
          <span class="th-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 3v18h18" /><path d="M7 15l3-4 3 2 4-6" /><circle cx="7" cy="15" r="1.3" fill="currentColor" stroke="none" /><circle cx="10" cy="11" r="1.3" fill="currentColor" stroke="none" /><circle cx="13" cy="13" r="1.3" fill="currentColor" stroke="none" /><circle cx="17" cy="7" r="1.3" fill="currentColor" stroke="none" /></svg></span>
          <div>
            <span class="th-tag">{{ t('implementation.s001') }}</span>
            <h2 class="title reveal">{{ t('implementation.s002') }}</h2>
          </div>
        </div>
        <p class="lead reveal">{{ t('implementation.s003') }}</p>

        <div class="modes" role="tablist" aria-label="CFIR 使用模式">
          <button type="button" class="on" data-mode="lib" role="tab"><span class="mn">1</span><span>{{ t('implementation.s004') }}</span></button>
          <button type="button" data-mode="ai" role="tab"><span class="mn">2</span><span>{{ t('implementation.s005') }}</span></button>
        </div>

        <!-- 模式一：对照库匹配 -->
        <div class="mode-panel" id="mLib">
          <p class="mode-desc" v-html="t('implementation.s006')"></p>
          <div class="cfir-grid" id="cfirGrid">
            <div v-for="d in domains" :key="d.domainId" class="cfir-dom">
              <div class="cd-head">
                <span class="cd-n">{{ d.seq }}</span>
                <div>
                  <b>{{ pick(d, 'name') }}</b>
                  <small>{{ t('implementation.lblDomain') }} {{ d.seq }}</small>
                </div>
              </div>
              <div class="cons">
                <label v-for="c in d.constructs" :key="c.constructId" class="con" :class="{ sel: selected.has(c.constructId) }">
                  <input
                    type="checkbox"
                    :data-id="c.constructId"
                    :checked="selected.has(c.constructId)"
                    @change="toggle(c.constructId, ($event.target as HTMLInputElement).checked)"
                  />
                  <span class="ct"><b>{{ pick(c, 'name') }}</b><span>{{ pick(c, 'hint') }}</span></span>
                </label>
              </div>
            </div>
          </div>
          <div class="selbar">
            <span class="sb-n"><span>{{ t('implementation.s007') }}</span> <b id="selCount">{{ selCount }}</b> <span>{{ t('implementation.s008') }}</span></span>
            <div class="sb-btns">
              <button type="button" class="btn btn-onDark btn-sm" id="clearSel" @click="clearSel">{{ t('implementation.s009') }}</button>
              <button type="button" class="btn btn-primary" id="genLib" :disabled="selCount === 0" v-html="t('implementation.s010')" @click="buildReport"></button>
            </div>
          </div>
        </div>

        <!-- 模式二：AI 智能梳理 -->
        <div class="mode-panel is-hidden" id="mAi">
          <p class="mode-desc">{{ t('implementation.s011') }}</p>
          <div class="ai-in">
            <label class="src-lab vh" for="aiTa">情境描述</label>
            <textarea class="ai-ta" id="aiTa" placeholder="例如：我科室想在门诊常规开展针刺镇痛，但年轻医生操作不规范、缺乏标准化培训；西医科室转诊意愿低；医院对针刺项目没有绩效激励；患者对针具有顾虑、依从性差……"></textarea>
            <div class="ai-foot">
              <button type="button" class="ai-sample" id="aiSample">{{ t('implementation.s012') }}</button>
              <button type="button" class="btn btn-primary" id="genAi" v-html="t('implementation.s013')"></button>
            </div>
          </div>
        </div>

        <!-- 报告 -->
        <div class="rep" id="cfirRep">
          <div v-if="!report" class="rep-empty" id="repEmpty">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M9 11l3 3 8-8" /><path d="M20 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9" /></svg>
            <b>{{ t('implementation.s014') }}</b>
            <p>{{ t('implementation.s015') }}</p>
          </div>
          <div v-if="report" id="repContent">
            <span class="rep-flag">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 9v4M12 17h.01" /><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" /></svg>
              <span>{{ t('implementation.repFlag') }}</span>
            </span>
            <div class="rep-sum">
              <div class="rsum warm"><b>{{ repStats.barriers }}</b><span>{{ t('implementation.sumBarriers') }}</span></div>
              <div class="rsum"><b>{{ repStats.strategies }}</b><span>{{ t('implementation.sumStrategies') }}</span></div>
              <div class="rsum"><b>{{ repStats.domains }}</b><span>{{ t('implementation.sumDomains') }}</span></div>
            </div>
            <div class="res-tools"><h3>{{ t('implementation.repTitle') }}</h3></div>
            <div class="tbl-wrap">
              <div class="tbl-scroll">
                <table class="rep-tbl">
                  <thead>
                    <tr>
                      <th>{{ t('implementation.thConstruct') }}</th>
                      <th>{{ t('implementation.thAssess') }}</th>
                      <th>{{ t('implementation.thStrategies') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <template v-for="(row, idx) in report" :key="row.construct.constructId">
                      <tr v-if="isNewGroup(idx)" class="grp">
                        <td colspan="3"><span>{{ t('implementation.lblDomain') }} {{ row.domain.seq }} · {{ pick(row.domain, 'name') }}</span></td>
                      </tr>
                      <tr>
                        <td>
                          <span class="cst">{{ pick(row.construct, 'name') }}</span>
                          <small class="cst" style="font-weight:400">{{ t('implementation.lblDomain') }} {{ row.domain.seq }} · {{ pick(row.domain, 'name') }}</small>
                        </td>
                        <td>
                          <span class="sev" :class="SEV_CLASS[row.construct.severity ?? 'm']">
                            {{ t(SEV_LABEL[row.construct.severity ?? 'm']) }}
                          </span>
                          <div style="font-size:12px;color:var(--muted);margin-top:6px;line-height:1.5">{{ pick(row.construct, 'hint') }}</div>
                        </td>
                        <td>
                          <div class="strat">
                            <div v-for="st in row.construct.strategies" :key="st.strategyId" class="st1">
                              <b>{{ pick(st, 'name') }}</b>
                              <span>{{ pick(st, 'detail') }}</span>
                              <span v-if="pick(st, 'source')" class="src-chip">{{ pick(st, 'source') }}</span>
                            </div>
                          </div>
                        </td>
                      </tr>
                    </template>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
    <!-- ===================== ERIC ===================== -->
    <section class="sec is-hidden" id="eric" style="background:var(--paper-2)">
      <div class="wrap">
        <div class="toolhead eric">
          <span class="th-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="6" cy="6" r="2.5" /><circle cx="18" cy="6" r="2.5" /><circle cx="12" cy="18" r="2.5" /><path d="M8 7.5 16 7.5M7 8l4 8M17 8l-4 8" /></svg></span>
          <div>
            <span class="th-tag" style="color:var(--info);background:var(--info-bg)">{{ t('implementation.s016') }}</span>
            <h2 class="title reveal">{{ t('implementation.s017') }}</h2>
          </div>
        </div>
        <p class="lead reveal">{{ t('implementation.s018') }}</p>
        <div class="filt" id="ericFilt" role="group" aria-label="按类别筛选策略">
          <button
            v-for="c in ericCats"
            :key="c.catKey"
            type="button"
            class="fchip"
            :class="{ on: ericCat === c.catKey }"
            :aria-pressed="ericCat === c.catKey"
            :data-k="c.catKey"
            @click="ericCat = c.catKey"
          >
            {{ pick(c, 'name') }}
          </button>
        </div>
        <div class="eric-grid" id="ericGrid">
          <div v-for="e in ericAll" :key="e.ericId" class="ecard" :class="{ hide: ericHidden(e) }" :data-cat="e.category">
            <span class="ecat">{{ catName(e.category) }}</span>
            <h4>{{ pick(e, 'name') }}</h4>
            <p>{{ pick(e, 'detail') }}</p>
            <div class="emap"><b>{{ t('implementation.lblAddresses') }}</b> <span>{{ pick(e, 'map') }}</span></div>
          </div>
        </div>
      </div>
    </section>

    <!-- ===================== RE-AIM ===================== -->
    <section class="sec is-hidden" id="reaim">
      <div class="wrap">
        <div class="toolhead reaim">
          <span class="th-ic" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="4.5" /><circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none" /></svg></span>
          <div>
            <span class="th-tag" style="color:var(--cinnabar-d);background:rgba(192,54,44,.09)">{{ t('implementation.s019') }}</span>
            <h2 class="title reveal">{{ t('implementation.s020') }}</h2>
          </div>
        </div>
        <p class="lead reveal">{{ t('implementation.s021') }}</p>
        <div class="raim-grid" id="raimGrid">
          <div v-for="r in reaimDims" :key="r.dimId" class="rcard">
            <span class="rscore">{{ r.scoreText }}</span>
            <div class="rletter">{{ r.letter }}</div>
            <h4>{{ pick(r, 'name') }}<small v-if="r.subTitle && r.subTitle !== pick(r, 'name')">{{ r.subTitle }}</small></h4>
            <p>{{ pick(r, 'definition') }}</p>
            <div class="rmetric"><b>{{ t('implementation.lblMetrics') }}</b> <span>{{ pick(r, 'measure') }}</span></div>
          </div>
        </div>
        <p class="lead reveal" style="margin-top:22px;font-size:13.5px">{{ t('implementation.s022') }}</p>
      </div>
    </section>
  </div>
</template>

<style>
.page-implementation .skip-link{position:absolute;left:12px;top:-60px;z-index:var(--z-toast);background:var(--indigo-700);color:#fff;font-weight:600;font-size:15px;padding:12px 20px;border-radius:10px;transition:top .2s var(--ease)}
.page-implementation .sec{padding:clamp(44px,6vw,80px) 0;scroll-margin-top:130px}
.page-implementation .kicker.on-dark{color:var(--indigo-200)}
.page-implementation h2.title{font-size:clamp(1.65rem,3.2vw,2.35rem);color:var(--indigo-900);letter-spacing:-.02em;text-wrap:balance;max-width:26ch}
.page-implementation .lead{color:var(--muted);font-size:clamp(1rem,1.4vw,1.14rem);max-width:68ch;margin-top:16px;text-wrap:pretty}
.page-implementation .btn{display:inline-flex;align-items:center;justify-content:center;gap:9px;padding:13px 24px;border-radius:999px;font-weight:600;font-size:15px;border:1.5px solid transparent;cursor:pointer;white-space:nowrap;
    transition:transform .25s var(--ease),background-color .25s var(--ease),box-shadow .25s var(--ease),border-color .25s var(--ease)}
.page-implementation .btn-primary:disabled{background:var(--indigo-300);box-shadow:none;cursor:not-allowed;transform:none}
.page-implementation .btn-lg{padding:15px 30px;font-size:16px}
.page-implementation .phero::before{content:"";position:absolute;inset:0;z-index:-1;
    background:radial-gradient(1000px 560px at 90% 0%,rgba(44,127,114,.5),transparent 60%),radial-gradient(680px 460px at 2% 100%,rgba(15,111,106,.26),transparent 65%),linear-gradient(160deg,#0d1a17 0%,#12211d 44%,#183029 100%)}
.page-implementation .phero .wrap{padding:clamp(28px,3.6vw,42px) clamp(20px,4vw,44px) clamp(42px,5.5vw,60px)}
.page-implementation .crumb{display:flex;align-items:center;gap:9px;font-size:13.5px;color:rgba(233,238,247,.66);margin-bottom:24px;flex-wrap:wrap}
.page-implementation .phero-tag{display:inline-flex;align-items:center;gap:10px;font-size:13px;font-weight:600;letter-spacing:.02em;color:var(--indigo-200);background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.16);padding:8px 16px;border-radius:999px;backdrop-filter:blur(4px)}
.page-implementation .phero h1{font-size:clamp(1.9rem,3.9vw,3rem);font-weight:700;letter-spacing:-.025em;margin:18px 0 0;text-wrap:balance;line-height:1.14}
.page-implementation .phero .psub{margin-top:18px;font-size:clamp(1rem,1.4vw,1.16rem);color:rgba(233,238,247,.9);max-width:64ch;line-height:1.7;text-wrap:pretty}
.page-implementation .subnav{position:sticky;top:72px;z-index:var(--z-subnav);background:rgba(242,246,244,.9);backdrop-filter:blur(12px) saturate(1.3);border-bottom:1px solid var(--line)}
.page-implementation .subnav-in{display:flex;align-items:center;gap:4px;overflow-x:auto;scrollbar-width:none}
.page-implementation .subnav-in::-webkit-scrollbar{display:none}
.page-implementation .subnav a{position:relative;flex-shrink:0;padding:15px 15px 13px;font-size:14px;font-weight:600;color:var(--muted);white-space:nowrap;transition:color .2s}
.page-implementation .subnav a .n{display:inline-flex;align-items:center;justify-content:center;padding:0 7px;height:19px;margin-right:7px;border-radius:6px;background:var(--indigo-100);color:var(--indigo-600);font-size:11px;font-weight:700;font-family:"Spectral",serif}
.page-implementation .subnav a::after{content:"";position:absolute;left:15px;right:15px;bottom:-1px;height:2px;background:var(--cinnabar);transform:scaleX(0);transform-origin:left;transition:transform .3s var(--ease)}
.page-implementation .subnav a:hover{color:var(--indigo-900)}
.page-implementation .subnav a.active{color:var(--indigo-900)}
.page-implementation .subnav a.active .n{background:var(--cinnabar);color:#fff}
.page-implementation .subnav a.active::after{transform:scaleX(1)}
.page-implementation .toolhead{display:flex;align-items:flex-start;gap:16px;margin-bottom:6px}
.page-implementation .toolhead .th-ic{width:52px;height:52px;flex-shrink:0;border-radius:14px;background:var(--indigo-700);color:#fff;display:flex;align-items:center;justify-content:center}
.page-implementation .toolhead.eric .th-ic{background:var(--info)}
.page-implementation .toolhead.reaim .th-ic{background:var(--cinnabar)}
.page-implementation .toolhead .th-ic svg{width:28px;height:28px}
.page-implementation .th-tag{display:inline-block;font-size:11.5px;font-weight:700;color:var(--indigo-600);background:var(--indigo-100);padding:3px 10px;border-radius:999px;margin-bottom:8px}
.page-implementation .modes{display:inline-flex;background:var(--paper-2);border:1px solid var(--line);border-radius:12px;padding:4px;gap:3px;margin:clamp(20px,3vw,28px) 0 0}
.page-implementation .modes button{border:none;background:transparent;font-family:inherit;font-size:14px;font-weight:600;color:var(--muted);padding:10px 18px;border-radius:9px;cursor:pointer;transition:.2s;display:inline-flex;align-items:center;gap:9px}
.page-implementation .modes button .mn{width:20px;height:20px;border-radius:6px;background:var(--indigo-200);color:var(--indigo-800);display:inline-flex;align-items:center;justify-content:center;font-family:"Spectral",serif;font-weight:700;font-size:11px}
.page-implementation .modes button.on{background:var(--surface);color:var(--indigo-900);box-shadow:var(--shadow-sm)}
.page-implementation .modes button.on .mn{background:var(--cinnabar);color:#fff}
.page-implementation .mode-panel{margin-top:20px}
.page-implementation .mode-panel.is-hidden{display:none}
.page-implementation .mode-desc{font-size:14px;color:var(--muted);line-height:1.6;max-width:70ch;margin-bottom:18px}
.page-implementation .mode-desc b{color:var(--indigo-700)}
.page-implementation .cfir-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.page-implementation .cfir-dom{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:18px 18px 14px}
.page-implementation .cd-head{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.page-implementation .cd-n{width:26px;height:26px;flex-shrink:0;border-radius:8px;background:var(--indigo-900);color:#fff;display:flex;align-items:center;justify-content:center;font-family:"Spectral",serif;font-weight:700;font-size:13px}
.page-implementation .cd-head b{font-size:1.02rem;color:var(--indigo-900);font-family:"Spectral","Noto Serif SC",serif;font-weight:600}
.page-implementation .cd-head small{display:block;font-size:11px;color:var(--muted);font-weight:600;letter-spacing:.02em}
.page-implementation .cons{display:flex;flex-direction:column;gap:4px}
.page-implementation .con{display:flex;align-items:flex-start;gap:10px;padding:8px 9px;border-radius:9px;cursor:pointer;transition:background .15s}
.page-implementation .con:hover{background:var(--paper-2)}
.page-implementation .con input{appearance:none;-webkit-appearance:none;width:19px;height:19px;flex-shrink:0;margin-top:1px;border:1.6px solid var(--indigo-300);border-radius:6px;cursor:pointer;position:relative;transition:.15s}
.page-implementation .con input:checked{background:var(--cinnabar);border-color:var(--cinnabar)}
.page-implementation .con input:checked::after{content:"";position:absolute;left:5.5px;top:2px;width:5px;height:9px;border:solid #fff;border-width:0 2px 2px 0;transform:rotate(45deg)}
.page-implementation .con input:focus-visible{outline:2.5px solid var(--indigo-500);outline-offset:2px}
.page-implementation .con .ct{min-width:0}
.page-implementation .con .ct b{display:block;font-size:13.5px;font-weight:600;color:var(--ink);font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-implementation .con .ct span{display:block;font-size:11.5px;color:var(--muted);line-height:1.4;margin-top:1px}
.page-implementation .con.sel{background:var(--indigo-100)}
.page-implementation .selbar{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-top:22px;padding:16px 20px;background:var(--indigo-900);border-radius:14px;color:#fff}
.page-implementation .selbar .sb-n{font-size:14px;color:rgba(233,238,247,.86)}
.page-implementation .selbar .sb-n b{color:#fff;font-family:"Spectral",serif;font-size:1.15rem;margin:0 3px}
.page-implementation .selbar .sb-btns{display:flex;gap:10px;flex-wrap:wrap}
.page-implementation .ai-in{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:20px}
.page-implementation .ai-ta{width:100%;min-height:150px;resize:vertical;border:1.5px solid var(--line);border-radius:12px;padding:14px;font-family:inherit;font-size:14.5px;color:var(--ink);line-height:1.65;background:var(--paper)}
.page-implementation .ai-ta:focus{outline:none;border-color:var(--indigo-500);box-shadow:0 0 0 4px var(--indigo-100)}
.page-implementation .ai-ta::placeholder{color:#8895a8}
.page-implementation .ai-foot{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;margin-top:14px}
.page-implementation .ai-sample{font-family:inherit;font-size:13px;font-weight:600;color:var(--indigo-600);background:none;border:none;cursor:pointer;text-decoration:underline;text-underline-offset:3px}
.page-implementation .ai-sample:hover{color:var(--cinnabar-d)}
.page-implementation .rep{margin-top:clamp(26px,3.5vw,38px)}
.page-implementation .rep.is-hidden{display:none}
.page-implementation .rep-flag{display:inline-flex;align-items:center;gap:9px;font-size:12.5px;font-weight:700;color:var(--amber);background:var(--amber-bg);border:1px solid #e7d39a;padding:7px 14px;border-radius:999px;margin-bottom:18px}
.page-implementation .rep-sum{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:18px}
.page-implementation .rsum{display:flex;flex-direction:column;gap:3px;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:15px 20px}
.page-implementation .rsum b{font-family:"Spectral","Noto Serif SC",serif;font-weight:700;font-size:1.6rem;color:var(--indigo-900);line-height:1}
.page-implementation .rsum span{font-size:12.5px;color:var(--muted)}
.page-implementation .rsum.warm b{color:var(--cinnabar-d)}
.page-implementation .ai-note{background:linear-gradient(180deg,#fff,var(--indigo-100));border:1px solid var(--indigo-200);border-radius:14px;padding:16px 18px;margin-bottom:18px;font-size:14px;color:var(--ink);line-height:1.6}
.page-implementation .ai-note b{color:var(--indigo-700)}
.page-implementation .ai-note .ain-h{display:flex;align-items:center;gap:8px;font-weight:700;color:var(--indigo-800);margin-bottom:6px}
.page-implementation .ai-note .ain-h svg{width:17px;height:17px;color:var(--cinnabar)}
.page-implementation .res-tools{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:14px}
.page-implementation .res-tools h3{font-size:1.2rem;color:var(--indigo-900)}
.page-implementation .res-tools .rt-btns{display:flex;gap:10px;flex-wrap:wrap}
.page-implementation .tbl-wrap{border:1px solid var(--line);border-radius:16px;overflow:hidden;background:var(--surface)}
.page-implementation .tbl-scroll{overflow-x:auto}
.page-implementation table.rep-tbl{width:100%;border-collapse:collapse;min-width:820px;font-size:13.5px}
.page-implementation table.rep-tbl th{background:var(--indigo-900);color:#fff;text-align:left;font-family:"Source Sans 3","Noto Sans SC",sans-serif;font-weight:600;font-size:12.5px;letter-spacing:.02em;padding:13px 16px;white-space:nowrap}
.page-implementation table.rep-tbl td{padding:14px 16px;border-top:1px solid var(--line);vertical-align:top;line-height:1.55;color:var(--ink)}
.page-implementation table.rep-tbl tr:hover td{background:var(--paper)}
.page-implementation table.rep-tbl .grp td{background:var(--indigo-100);font-weight:700;color:var(--indigo-800);font-size:12.5px}
.page-implementation .cst{white-space:nowrap;font-weight:700;color:var(--indigo-900)}
.page-implementation .cst small{display:block;font-weight:400;color:var(--muted);font-size:11.5px;margin-top:2px}
.page-implementation .strat{display:flex;flex-direction:column;gap:9px}
.page-implementation .strat .st1{display:block}
.page-implementation .strat .st1 b{color:var(--indigo-800);font-weight:700}
.page-implementation .strat .st1 span{display:block;font-size:12.5px;color:var(--muted);margin-top:2px;line-height:1.5}
.page-implementation .src-chip{display:inline-block;font-size:11px;font-weight:600;color:var(--info);background:var(--info-bg);padding:2px 9px;border-radius:999px;margin-top:5px}
.page-implementation .sev{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:700;padding:4px 11px;border-radius:999px;white-space:nowrap}
.page-implementation .sev::before{content:"";width:7px;height:7px;border-radius:50%}
.page-implementation .sev-h{color:var(--cinnabar-d);background:rgba(192,54,44,.09)}
.page-implementation .sev-h::before{background:var(--cinnabar)}
.page-implementation .sev-m{color:var(--amber);background:var(--amber-bg)}
.page-implementation .sev-m::before{background:var(--amber)}
.page-implementation .sev-l{color:var(--indigo-600);background:var(--indigo-100)}
.page-implementation .sev-l::before{background:var(--indigo-500)}
.page-implementation .rep-empty{text-align:center;padding:clamp(30px,4vw,52px) 20px;background:var(--surface);border:1.5px dashed var(--line);border-radius:16px}
.page-implementation .rep-empty svg{width:40px;height:40px;color:var(--indigo-300);margin:0 auto 12px}
.page-implementation .rep-empty b{display:block;font-family:"Spectral","Noto Serif SC",serif;font-size:1.24rem;color:var(--indigo-900);margin-bottom:7px}
.page-implementation .rep-empty p{font-size:14px;color:var(--muted);max-width:52ch;margin:0 auto;line-height:1.6}
.page-implementation .filt{display:flex;flex-wrap:wrap;gap:8px;margin:clamp(20px,3vw,28px) 0 0}
.page-implementation .fchip{font-size:13px;font-weight:600;color:var(--indigo-700);background:var(--surface);border:1.5px solid var(--line);padding:7px 15px;border-radius:999px;cursor:pointer;transition:.2s}
.page-implementation .fchip:hover{border-color:var(--indigo-300);background:var(--indigo-100)}
.page-implementation .fchip.on{background:var(--info);border-color:var(--info);color:#fff}
.page-implementation .eric-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;margin-top:20px}
.page-implementation .ecard{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:20px;display:flex;flex-direction:column;gap:9px;transition:.22s var(--ease)}
.page-implementation .ecard:hover{transform:translateY(-3px);box-shadow:var(--shadow-md);border-color:var(--info)}
.page-implementation .ecard.hide{display:none}
.page-implementation .ecat{align-self:flex-start;font-size:11px;font-weight:700;color:var(--info);background:var(--info-bg);padding:3px 11px;border-radius:999px}
.page-implementation .ecard h4{font-size:1.06rem;color:var(--indigo-900);font-family:"Spectral","Noto Serif SC",serif;font-weight:600;line-height:1.25}
.page-implementation .ecard p{font-size:13px;color:var(--muted);line-height:1.55}
.page-implementation .ecard .emap{margin-top:auto;padding-top:8px;font-size:12px;color:var(--indigo-700)}
.page-implementation .ecard .emap b{color:var(--cinnabar-d)}
.page-implementation .raim-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin-top:clamp(22px,3vw,30px)}
.page-implementation .rcard{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:22px;position:relative}
.page-implementation .rletter{width:44px;height:44px;border-radius:12px;background:var(--indigo-100);color:var(--indigo-700);display:flex;align-items:center;justify-content:center;font-family:"Spectral",serif;font-weight:700;font-size:20px;margin-bottom:14px}
.page-implementation .rcard h4{font-size:1.1rem;color:var(--indigo-900);margin-bottom:3px}
.page-implementation .rcard h4 small{display:block;font-family:"Source Sans 3","Noto Sans SC",sans-serif;font-weight:600;font-size:11.5px;color:var(--info);letter-spacing:.02em;margin-top:3px}
.page-implementation .rcard p{font-size:13px;color:var(--muted);line-height:1.55;margin-top:8px}
.page-implementation .rcard .rmetric{margin-top:12px;font-size:12.5px;color:var(--ink);background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:9px 12px;line-height:1.5}
.page-implementation .rcard .rmetric b{color:var(--indigo-700)}
.page-implementation .rscore{position:absolute;top:20px;right:20px;font-family:"Spectral",serif;font-weight:700;font-size:1.1rem;color:var(--info)}
@media print{
.page-implementation .phero,.page-implementation .subnav,.page-implementation .modes,.page-implementation .cfir-grid,.page-implementation .selbar,.page-implementation .ai-in,.page-implementation .filt,.page-implementation .eric-grid,.page-implementation .raim-grid,.page-implementation .res-tools .rt-btns,.page-implementation .rep-empty{display:none !important}
.page-implementation body{background:#fff}
.page-implementation table.rep-tbl{min-width:0;font-size:11px}
}
</style>
