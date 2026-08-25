<script setup lang="ts">
/**
 * guidelines.html 迁移而来。
 * 模板与样式基本保持原状；样式已加 .page-guidelines 命名空间，避免 SPA 路由切换时跨页污染。
 *
 * 三处例外：
 *  1. 筛选条原本写死成 7 个 chip，靠一张 CAT_OF 表把接口的 studyType 折算成 chip 键、
 *     标签另取 guidelines.s005–s010。后台新增规范时只要 studyType 不在那 6 个键里就会掉进
 *     'all'，任何 chip 都筛不出来、卡片上的「研究设计」标签还是空白（库里的 STROBE
 *     就是这个状态）。现改为读 `action_guideline_category` 表：chip、标签、图标同源，
 *     对应关系是 category.catKey === guideline.studyType，后台两个页面都从同一张表取值。
 *  2. 迁移时丢了 guidelines.html 的二级子栏目导航，四段里的后三段却留着 `is-hidden`
 *     （base.css 里是 `display:none !important`），于是「在线预览与下载 / 版本管理 /
 *     试点测试」三段从来没渲染过。现照 pages/about.vue 的写法把 Tab 补回来。
 *  3. 原第②段「在线预览与下载」的折叠列表已删除，改为独立页 `pages/guideline/[id].vue`：
 *     卡片点进去直接内嵌 PDF 原文，而不是在本页展开一对下载按钮。
 *     第③版本管理、第④试点测试两段内容待定稿，暂由 SHOW_WIP_TABS 关着（见下）。
 */
const { t } = useI18n()
const { pick } = useBilingual()

useHead({
  title: t('guidelines._title'),
  meta: [{ name: 'description', content: t('guidelines._desc') }],
})

// 规范目录与分类都是后台「规范目录管理 / 规范分类管理」页可随时改的内容；
// hydration 后自动重取一次，见 `useSiteApi` 的 `revalidate`（默认开）
const { data: glRes } = await useSiteList<GuidelineRow>(
  '/guidelines',
  { pageNum: 1, pageSize: 100 },
  'guidelines-page',
)
const rows = computed<GuidelineRow[]>(() => glRes.value?.rows ?? [])

const { data: catRes } = await useSiteObject<GuidelineCategoryRow[]>('/guideline-categories', 'guideline-cats')
const cats = computed<GuidelineCategoryRow[]>(() => catRes.value?.data ?? [])

/** catKey → 分类，卡片标签与图标都从这里取 */
const catMap = computed(() => new Map(cats.value.map((c) => [c.catKey, c])))
const catOf = (r: GuidelineRow) => (r.studyType ? catMap.value.get(r.studyType) : undefined)

/** 研究设计标签。分类被停用/删除时留空而不是回填 studyType 原值 —— 那是内部标识，不该露给访客 */
const catLabel = (r: GuidelineRow) => pick(catOf(r), 'name')

/** 卡片图标：分类表里一行一条 SVG path 的 d 属性，留空则不画 */
const iconOf = (r: GuidelineRow) => categoryIconPaths(catOf(r))

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
/**
 * 筛选直接比 studyType 与 catKey，不再经过任何映射表 —— 这正是原来筛不出来的病根：
 * 中间多一层硬编码映射，映射表没覆盖到的分类就会静默失配。
 * 用 CSS 隐藏而不卸载节点，理由同 news.vue（原页面也是 toggle('hide')）。
 */
const isHidden = (r: GuidelineRow) => activeCat.value !== 'all' && r.studyType !== activeCat.value

/** 空分类不渲染 chip：一个点下去必然空列表的按钮，比没有这个按钮更糟 */
const shownCats = computed(() => cats.value.filter((c) => rows.value.some((r) => r.studyType === c.catKey)))

const { rescan, revealNow } = useReveal()

function selectCat(key: string) {
  activeCat.value = key
  // 这一刀 MutationObserver 顶不了：筛选只是给卡片切 `.hide`（display:none ⇄ 可见），
  // 没有节点新增，观察不到。被藏起来时 IntersectionObserver 不会触发，
  // 显示回来若没人补扫就永远停在 .reveal{opacity:0} 上 —— 即「筛选对了但一片空白」。
  void rescan()
}

/**
 * 「版本管理 / 试点测试」两段暂不对外（内容待定稿），连子栏目导航一起藏起来 ——
 * 只剩一格的 Tab 条是纯噪音。改成 true 即整体恢复，两段模板与样式都还在。
 *
 * 关着的时候本页只有第①段分类导航，卡片直接跳 `/guideline/[id]` 看原文。
 */
const SHOW_WIP_TABS: boolean = false

/**
 * 二级子栏目 Tab —— 迁移自 guidelines.html 内联脚本，顺序即子导航顺序。
 * 各段内容同时在 DOM 里，只显示当前一段。
 */
const TABS = ['nav', 'versions', 'pilot'] as const
type Tab = (typeof TABS)[number]

const isTab = (v: string): v is Tab => (TABS as readonly string[]).includes(v)

/** SSR 预渲染时固定输出第一段，与原站首屏一致；带 hash 进来的情况在 onMounted 里纠正 */
const activeTab = ref<Tab>('nav')

/** @param id 目标子栏目 */
function goTab(id: Tab) {
  activeTab.value = id
  // 不走 router.replace：no_prefix 策略下 Nuxt 的 scrollBehavior 会按 hash 再跳一次，
  // 与下面的 scrollIntoView 打架。原生 replaceState 保留 history.state，路由状态不丢。
  window.history.replaceState(window.history.state, '', `#${id}`)
  nextTick(() => {
    revealNow(id)
    document.getElementById('gl-subnav')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

onMounted(() => {
  if (!SHOW_WIP_TABS) return
  const hash = window.location.hash.slice(1)
  if (!isTab(hash) || hash === activeTab.value) return
  // 深链进来只切换、不滚动 —— 子导航本身已在首屏
  activeTab.value = hash
  nextTick(() => revealNow(hash))
})

watch([rows, cats], () => {
  // 选中的分类可能在重取回来的新数据里没有规范了（后台改了归类或停用了分类），
  // 那个 chip 会从筛选条上消失，但 activeCat 还指着它 —— 结果是「一个都没选中却空列表」
  if (activeCat.value !== 'all' && !shownCats.value.some((c) => c.catKey === activeCat.value))
    activeCat.value = 'all'
})
</script>

<template>
  <div class="page-guidelines">
    <nav v-if="SHOW_WIP_TABS" class="subnav" id="gl-subnav" :aria-label="t('guidelines.tabsAria')">
      <div class="wrap subnav-in">
        <a
          v-for="(tab, i) in TABS"
          :key="tab"
          :href="`#${tab}`"
          :class="{ active: activeTab === tab }"
          :aria-current="activeTab === tab ? 'true' : undefined"
          @click.prevent="goTab(tab)"
        ><span class="n" aria-hidden="true">{{ i + 1 }}</span><span>{{ t(`guidelines.tabs.${tab}`) }}</span></a>
      </div>
    </nav>

    <!-- ===================== ① 分类导航 ===================== -->
    <section class="sec" id="nav" :class="{ 'is-hidden': SHOW_WIP_TABS && activeTab !== 'nav' }">
      <div class="wrap">
        <span class="kicker reveal">{{ t('guidelines.s001') }}</span>
        <h2 class="title reveal">{{ t('guidelines.s002') }}</h2>
        <p class="lead reveal">{{ t('guidelines.s003') }}</p>

        <div class="gl-filter reveal" role="group" :aria-label="t('guidelines.filterAria')">
          <button
            class="gl-chip"
            :class="{ on: activeCat === 'all' }"
            :aria-pressed="activeCat === 'all'"
            data-filter="all"
            @click="selectCat('all')"
          >
            {{ t('guidelines.s004') }}
          </button>
          <button
            v-for="c in shownCats"
            :key="c.catId"
            class="gl-chip"
            :class="{ on: activeCat === c.catKey }"
            :aria-pressed="activeCat === c.catKey"
            :data-filter="c.catKey"
            @click="selectCat(c.catKey)"
          >
            {{ pick(c, 'name') }}
          </button>
        </div>

        <div class="gl-grid">
          <!-- 点卡片进原文阅读页（内嵌 PDF），不再在本页展开折叠块 -->
          <NuxtLink
            v-for="r in rows"
            :key="r.guidelineId"
            class="gl-card reveal"
            :class="{ hide: isHidden(r) }"
            :to="`/guideline/${r.guidelineId}`"
            :data-cat="r.studyType"
          >
            <div class="gl-top">
              <span v-if="iconOf(r).length" class="gl-ic" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                  <path v-for="(d, k) in iconOf(r)" :key="k" :d="d" />
                </svg>
              </span>
              <span><span v-if="catLabel(r)" class="gl-type">{{ catLabel(r) }}</span><span class="gl-abbr">{{ r.code }}</span></span>
            </div>
            <p class="gl-basis">{{ pick(r, 'summary') }}</p>
            <div class="gl-meta"><span v-if="pick(r, 'version')">{{ pick(r, 'version') }}</span></div>
            <span class="gl-go" v-html="t('guidelines.s015')"></span>
          </NuxtLink>
        </div>
      </div>
    </section>
    <!-- ===================== ② 版本管理（暂不对外） ===================== -->
    <section v-if="SHOW_WIP_TABS" class="sec" id="versions" :class="{ 'is-hidden': activeTab !== 'versions' }">
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
                  <td>{{ pick(r, 'version') }}</td>
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
    <!-- ===================== ③ 试点测试（暂不对外） ===================== -->
    <section v-if="SHOW_WIP_TABS" class="sec" id="pilot" :class="{ 'is-hidden': activeTab !== 'pilot' }" style="background:var(--paper-2)">
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
              <!-- 原先跳第②段「在线预览与下载」，那一段已换成 /guideline/[id]，这里退回分类导航 -->
              <a class="btn btn-ghost" href="#nav" @click.prevent="goTab('nav')">{{ t('guidelines.s171') }}</a>
            </div>
            <p class="src reveal" v-html="t('guidelines.s172')"></p>
          </div>

          <aside class="pilot-facts reveal" :aria-label="t('guidelines.pilotFactsAria')">
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
/* 原「在线预览与下载」折叠列表（.dl-*）的样式随那一段一起删了 —— 现在原文在
   pages/guideline/[id].vue，样式也跟着走，别在这里留一套没人用的选择器。 */
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
/* beta/soon 迁移时只在 JS 里给了类名、没配样式；版本管理段此前被 is-hidden 遮着看不出来，
   现在这一段真的会渲染，缺样式就是一颗没颜色、没圆点的空药丸 */
.page-guidelines .st.beta{color:#8a5a00;background:rgba(214,158,46,.13)}
.page-guidelines .st.beta::before{background:#d69e2e}
.page-guidelines .st.soon{color:var(--muted);background:var(--paper-2)}
.page-guidelines .st.soon::before{background:var(--muted)}
/* 与 base.css 的 .is-hidden 同义，写在页面里是为了不依赖那条全局 !important（同 pages/about.vue） */
.page-guidelines .sec.is-hidden{display:none}
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
/* 揭示动画只在 base.css 里定义：加了 .page-guidelines 前缀的那两条永远匹配不上
   （html 不可能是某个 div 的后代），删掉以免误以为本页另有一套。 */
@media(max-width:1000px){
.page-guidelines .pilot-grid{grid-template-columns:1fr;gap:30px}
}
@media(max-width:820px){
.page-guidelines .pilot-facts{grid-template-columns:1fr 1fr}
.page-guidelines .mobile-menu .btn{width:100%;justify-content:center;margin-top:24px}
}
</style>
