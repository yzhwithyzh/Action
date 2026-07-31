<script setup lang="ts">
/**
 * index.html 迁移而来。
 * 模板与样式保持原状；样式已加 .page-index 命名空间，避免 SPA 路由切换时跨页污染。
 */
const { t } = useI18n()

useHead({
  title: t('index._title'),
  meta: [{ name: 'description', content: t('index._desc') }],
})

interface HomeNewsRow {
  newsId: number
  categoryZh: string | null
  categoryEn: string | null
  titleZh: string | null
  titleEn: string | null
  summaryZh: string | null
  summaryEn: string | null
  thumbUrl: string | null
  publishDate: string | null
  linkUrl: string | null
  isExternal: '0' | '1' | null
}

const { pick } = useBilingual()

// 首页新闻区与 /news 同源，只取前 3 条。顺序照接口返回，不在前端二次排序
// （DAO 已按 置顶 > 发布日期倒序 NULLS LAST > id 倒序 排好）。
// swr：新闻由后台随时发布，不能停在构建期那一刻的快照上。
const { data: newsRes } = await useSiteList<HomeNewsRow>('/news', { pageNum: 1, pageSize: 3 }, 'home-news', { swr: true })
const newsRows = computed<HomeNewsRow[]>(() => newsRes.value?.rows ?? [])

/** `2026-07-01` → `2026-07` */
const ym = (d: string | null) => (d ? d.slice(0, 7) : '')

/** 与 /news 列表同一套规则：没配 linkUrl 的落到站内详情页，不能渲染成无 href 的死链 */
const hrefOf = (r: HomeNewsRow) => r.linkUrl || `/news/${r.newsId}`
const opensNewTab = (r: HomeNewsRow) => r.isExternal === '1' && !!r.linkUrl

useReveal()
</script>

<template>
  <div class="page-index">
    <!-- ===================== Hero ===================== -->
    <section class="hero">
      <div class="wrap">
        <div class="hero-grid">
          <div class="hero-inner">
            <span class="tag reveal"><span class="dot"></span><span>{{ t('index.s001') }}</span></span>
            <h1 class="reveal" v-html="t('index.s002')"></h1>
            <p class="sub reveal">{{ t('index.s003') }}</p>
            <div class="hero-cta reveal">
              <NuxtLink to="/assistant" class="btn btn-primary btn-lg"><span class="rich" v-html="t('index.s004')"></span></NuxtLink>
              <a href="#modules" class="btn btn-onDark btn-lg">{{ t('index.s005') }}</a>
            </div>
            <div class="hero-trust reveal">
              <span>{{ t('index.s006') }}</span>
              <span>{{ t('index.s007') }}</span>
              <span>{{ t('index.s008') }}</span>
            </div>
          </div>
          <!-- 工具预览：报告助手第一步「立项匹配」界面预览 -->
          <div class="tp-shell reveal">
            <div class="tp" role="img" aria-label="报告助手界面预览：选择研究类型为随机对照试验，自动挂载 CONSORT、STRICTA、SPIRIT 规范，逐条校验报告完整性清单，当前完整性 82%。">
              <div class="tp-chrome" aria-hidden="true">
                <span class="tp-dots"><i></i><i></i><i></i></span>
                <span class="tp-title">{{ t('index.s009') }}</span>
                <span class="tp-live">{{ t('index.s010') }}</span>
              </div>
              <div class="tp-body" aria-hidden="true">
                <div class="tp-step">
                  <span class="tp-lab">{{ t('index.s011') }}</span>
                  <div class="tp-select"><span>{{ t('index.s012') }}</span>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="m6 9 6 6 6-6" /></svg></div>
                </div>
                <div class="tp-step">
                  <span class="tp-lab">{{ t('index.s013') }}</span>
                  <div class="tp-chips"><span>CONSORT</span><span class="hot">STRICTA</span><span>SPIRIT</span></div>
                </div>
                <div class="tp-step">
                  <span class="tp-lab">{{ t('index.s014') }}</span>
                  <ul class="tp-checks">
                    <li class="ok"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M20 6 9 17l-5-5" /></svg><span>{{ t('index.s015') }}</span></li>
                    <li class="ok"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M20 6 9 17l-5-5" /></svg><span>{{ t('index.s016') }}</span></li>
                    <li class="todo"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M12 8v5M12 16h.01" /><circle cx="12" cy="12" r="9" /></svg><span>{{ t('index.s017') }}</span></li>
                  </ul>
                </div>
                <div class="tp-foot">
                  <span class="tp-meter"><i></i></span>
                  <span class="tp-pct">{{ t('index.s018') }}</span>
                </div>
              </div>
            </div>
            <p class="tp-cap reveal">{{ t('index.s019') }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ===================== 平台模块总览 ===================== -->
    <section class="sec modules" id="modules">
      <div class="wrap">
        <span class="kicker reveal">{{ t('index.s020') }}</span>
        <h2 class="title reveal">{{ t('index.s021') }}</h2>
        <p class="lead reveal">{{ t('index.s022') }}</p>
        <div class="mod-grid">

          <!-- 模块 1：报告规范体系 -->
          <NuxtLink class="mod-card reveal" to="/guidelines">
            <svg class="mod-ic" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M12 6h18l8 8v28a2 2 0 0 1-2 2H12a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2Z" /><path d="M30 6v8h8" /><path d="M16 24h16M16 30h16M16 36h10" /></svg>
            <h3>{{ t('index.s023') }}</h3>
            <p class="mod-desc">{{ t('index.s024') }}</p>
            <ul class="mod-list" aria-hidden="true">
              <li>RCT · CONSORT/STRICTA</li><li>方案 · SPIRIT</li><li>系统综述 · PRISMA</li><li>病例 · CARE</li><li>指南 · RIGHT</li><li>动物 · ARRIVE</li>
            </ul>
            <span class="mod-go" v-html="t('index.s025')"></span>
          </NuxtLink>

          <!-- 模块 2：报告助手（核心） -->
          <NuxtLink class="mod-card feat reveal" to="/assistant">
            <span class="mod-badge">{{ t('index.s026') }}</span>
            <svg class="mod-ic" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="7" y="9" width="34" height="30" rx="3" /><path d="M7 17h34M14 25h9M14 31h14" /><circle cx="31" cy="28" r="5" /><path d="M34.5 31.5 38 35" /></svg>
            <h3>{{ t('index.s027') }}</h3>
            <p class="mod-desc">{{ t('index.s028') }}</p>
            <ul class="mod-list" aria-hidden="true">
              <li>研究类型匹配</li><li>在线模板</li><li>内容校验</li><li>AI 辅助撰写</li><li>导出分享</li>
            </ul>
            <span class="mod-go" v-html="t('index.s029')"></span>
          </NuxtLink>

          <!-- 模块 3：实施科学工具 -->
          <NuxtLink class="mod-card reveal" to="/implementation">
            <svg class="mod-ic" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="24" cy="24" r="6" /><path d="M24 6v6M24 36v6M6 24h6M36 24h6M11 11l4.5 4.5M32.5 32.5 37 37M37 11l-4.5 4.5M15.5 32.5 11 37" /></svg>
            <h3>{{ t('index.s030') }}</h3>
            <p class="mod-desc">{{ t('index.s031') }}</p>
            <ul class="mod-list" aria-hidden="true">
              <li>CFIR 评估优化</li><li>ERIC 策略匹配</li><li>RE-AIM 转化评价</li>
            </ul>
            <span class="mod-go" v-html="t('index.s032')"></span>
          </NuxtLink>

          <!-- 模块：方法学评估工具 -->
          <NuxtLink class="mod-card reveal" to="/srd">
            <span class="mod-badge">{{ t('index.s033') }}</span>
            <svg class="mod-ic" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="7" y="6" width="20" height="26" rx="2.5" /><rect x="21" y="16" width="20" height="26" rx="2.5" /><path d="M11 13h10M11 19h7M25 23h10M25 29h7" /></svg>
            <h3>{{ t('index.s034') }}</h3>
            <p class="mod-desc">{{ t('index.s035') }}</p>
            <ul class="mod-list" aria-hidden="true">
              <li>SRD 重复性评估</li><li>逐条比对</li><li>整体判定</li><li>导出表格</li>
            </ul>
            <span class="mod-go" v-html="t('index.s036')"></span>
          </NuxtLink>

          <!-- 模块 4：协作与专家咨询 -->
          <NuxtLink class="mod-card reveal" to="/collaborate">
            <svg class="mod-ic" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="16" cy="17" r="6" /><circle cx="33" cy="20" r="5" /><path d="M6 40c0-6 4.5-10 10-10s10 4 10 10" /><path d="M27 40c0-4.5 2.8-8 6.5-8s6.5 2.5 7.5 6" /></svg>
            <h3>{{ t('index.s037') }}</h3>
            <p class="mod-desc">{{ t('index.s038') }}</p>
            <ul class="mod-list" aria-hidden="true">
              <li>专家咨询通道</li><li>用户交流论坛</li><li>机构合作网络</li>
            </ul>
            <span class="mod-go" v-html="t('index.s039')"></span>
          </NuxtLink>

        </div>
      </div>
    </section>

    <!-- ===================== 最近新闻 ===================== -->
    <section class="sec news" id="news">
      <div class="wrap">
        <div class="sec-head">
          <div>
            <span class="kicker reveal">{{ t('index.s040') }}</span>
            <h2 class="title reveal">{{ t('index.s041') }}</h2>
          </div>
          <NuxtLink class="see-all reveal" to="/news"><span class="rich" v-html="t('index.s042')"></span></NuxtLink>
        </div>
        <div class="news-list">
          <NuxtLink
            v-for="(r, idx) in newsRows"
            :key="r.newsId"
            :to="hrefOf(r)"
            class="news-item reveal"
            :target="opensNewTab(r) ? '_blank' : undefined"
            :rel="opensNewTab(r) ? 'noopener noreferrer' : undefined"
          >
            <img
              v-if="r.thumbUrl"
              class="news-thumb"
              :src="r.thumbUrl"
              :alt="pick(r, 'title')"
              loading="lazy"
              width="800"
              height="520"
            />
            <div class="news-body">
              <div class="news-topline">
                <time v-if="r.publishDate" :datetime="ym(r.publishDate)">{{ ym(r.publishDate) }}</time>
                <span class="news-cat" :class="{ up: idx === 0 }">{{ pick(r, 'category') }}</span>
              </div>
              <h3>{{ pick(r, 'title') }}</h3>
              <p>{{ pick(r, 'summary') }}</p>
            </div>
            <span class="news-go" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path v-if="opensNewTab(r)" d="M7 17 17 7M8 7h9v9" />
                <path v-else d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </span>
          </NuxtLink>
        </div>
      </div>
    </section>

    <!-- ===================== 资源中心 ===================== -->
    <section class="sec resources" id="resources" style="background:var(--paper-2)">
      <div class="wrap">
        <span class="kicker reveal">{{ t('index.s052') }}</span>
        <h2 class="title reveal">{{ t('index.s053') }}</h2>
        <p class="lead reveal">{{ t('index.s054') }}</p>
        <div class="res-cards">
          <a class="res-row reveal" href="https://www.equator-network.org" target="_blank" rel="noopener noreferrer">
            <img class="res-logo" src="/assets/logo-equator.png" alt="" loading="lazy" width="96" height="96" />
            <span class="rr-main"><b>EQUATOR Network</b><span>{{ t('index.s055') }}</span></span>
            <svg class="r-ext" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M7 17 17 7M8 7h9v9" /></svg><span class="vh">{{ t('index.s056') }}</span>
          </a>
          <a class="res-row reveal" href="https://www.cochrane.org" target="_blank" rel="noopener noreferrer">
            <img class="res-logo" src="/assets/logo-cochrane.png" alt="" loading="lazy" width="96" height="96" />
            <span class="rr-main"><b>Cochrane</b><span>{{ t('index.s057') }}</span></span>
            <svg class="r-ext" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M7 17 17 7M8 7h9v9" /></svg><span class="vh">{{ t('index.s058') }}</span>
          </a>
          <a class="res-row reveal" href="https://www.consort-spirit.org" target="_blank" rel="noopener noreferrer">
            <img class="res-logo" src="/assets/logo-consort.png" alt="" loading="lazy" width="96" height="96" />
            <span class="rr-main"><b>CONSORT &amp; SPIRIT</b><span>{{ t('index.s059') }}</span></span>
            <svg class="r-ext" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M7 17 17 7M8 7h9v9" /></svg><span class="vh">{{ t('index.s060') }}</span>
          </a>
          <a class="res-row reveal" href="https://www.prisma-statement.org" target="_blank" rel="noopener noreferrer">
            <img class="res-logo" src="/assets/logo-prisma.png" alt="" loading="lazy" width="96" height="96" />
            <span class="rr-main"><b>PRISMA</b><span>{{ t('index.s061') }}</span></span>
            <svg class="r-ext" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M7 17 17 7M8 7h9v9" /></svg><span class="vh">{{ t('index.s062') }}</span>
          </a>
          <a class="res-row reveal" href="https://arriveguidelines.org" target="_blank" rel="noopener noreferrer">
            <img class="res-logo" src="/assets/logo-arrive.png" alt="" loading="lazy" width="96" height="96" />
            <span class="rr-main"><b>ARRIVE</b><span>{{ t('index.s063') }}</span></span>
            <svg class="r-ext" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M7 17 17 7M8 7h9v9" /></svg><span class="vh">{{ t('index.s064') }}</span>
          </a>
          <a class="res-row reveal" href="https://www.care-statement.org" target="_blank" rel="noopener noreferrer">
            <img class="res-logo" src="/assets/logo-care.png" alt="" loading="lazy" width="96" height="96" />
            <span class="rr-main"><b>CARE</b><span>{{ t('index.s065') }}</span></span>
            <svg class="r-ext" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M7 17 17 7M8 7h9v9" /></svg><span class="vh">{{ t('index.s066') }}</span>
          </a>
        </div>
      </div>
    </section>
  </div>
</template>

<style>
.page-index .skip-link{position:absolute;left:12px;top:-60px;z-index:var(--z-toast);background:var(--indigo-700);color:#fff;
    font-family:"Source Sans 3","Noto Sans SC",sans-serif;font-weight:600;font-size:15px;padding:12px 20px;border-radius:10px;
    transition:top .2s var(--ease)}
.page-index .sec{padding:clamp(52px,7vw,92px) 0}
.page-index .kicker{
    display:inline-flex;align-items:center;gap:9px;
    font-size:13.5px;font-weight:600;letter-spacing:.02em;color:var(--indigo-500);
    font-family:"Source Sans 3","Noto Sans SC",sans-serif;margin-bottom:16px;
  }
.page-index .kicker.on-dark{color:var(--indigo-200)}
.page-index h2.title{
    font-size:clamp(1.7rem,3.4vw,2.5rem);color:var(--indigo-900);
    letter-spacing:-.02em;text-wrap:balance;max-width:24ch;
  }
.page-index h2.title.on-dark{color:#fff}
.page-index .lead{
    color:var(--muted);font-size:clamp(1.02rem,1.4vw,1.16rem);
    max-width:64ch;margin-top:18px;text-wrap:pretty;
  }
.page-index .lead.on-dark{color:rgba(233,238,247,.86)}
.page-index .sec-head{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;flex-wrap:wrap}
.page-index .see-all{display:inline-flex;align-items:center;gap:8px;font-family:"Source Sans 3","Noto Sans SC",sans-serif;
    font-weight:600;font-size:15px;color:var(--indigo-700);white-space:nowrap;transition:color .2s var(--ease)}
.page-index .see-all .arrow{transition:transform .3s var(--ease)}
.page-index .see-all:hover{color:var(--cinnabar)}
.page-index .see-all:hover .arrow{transform:translateX(3px)}
.page-index .btn{
    display:inline-flex;align-items:center;gap:9px;padding:13px 24px;border-radius:999px;
    font-family:"Source Sans 3","Noto Sans SC",sans-serif;font-weight:600;font-size:15px;
    border:1.5px solid transparent;cursor:pointer;transition:transform .25s var(--ease),
    background-color .25s var(--ease),box-shadow .25s var(--ease),border-color .25s var(--ease);
    white-space:nowrap;
  }
.page-index .btn-lg{padding:15px 28px;font-size:15.5px}
.page-index .hero{position:relative;overflow:hidden;background:var(--indigo-900);color:#fff;isolation:isolate}
.page-index .hero::before{content:"";position:absolute;inset:0;z-index:-1;
    background:
      radial-gradient(1100px 620px at 88% 4%,var(--indigo-600),transparent 60%),
      radial-gradient(760px 520px at 4% 96%,var(--indigo-800),transparent 65%),
      linear-gradient(160deg,var(--indigo-900) 0%,var(--indigo-900) 42%,var(--indigo-800) 100%);}
.page-index .hero .wrap{position:relative;padding:clamp(60px,7.5vw,100px) clamp(20px,4vw,44px) clamp(56px,7vw,84px)}
.page-index .hero-grid{display:grid;grid-template-columns:minmax(0,1.06fr) minmax(0,.94fr);gap:clamp(40px,5vw,76px);align-items:center}
.page-index .hero-inner{min-width:0}
.page-index .tag{
    display:inline-flex;align-items:center;gap:10px;font-size:13px;font-weight:600;letter-spacing:.02em;
    color:var(--indigo-200);background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.16);
    padding:8px 16px;border-radius:999px;backdrop-filter:blur(4px);
    font-family:"Source Sans 3","Noto Sans SC",sans-serif;
  }
.page-index .tag .dot{width:7px;height:7px;border-radius:50%;background:var(--cinnabar);box-shadow:0 0 0 4px rgba(192,54,44,.25)}
.page-index .hero h1{
    font-size:clamp(2.05rem,4.4vw,3.5rem);font-weight:700;letter-spacing:-.025em;
    margin:22px 0 0;text-wrap:balance;line-height:1.14;
  }
.page-index .hero h1 .hl{color:var(--indigo-200)}
.page-index .hero .sub{
    margin-top:22px;font-size:clamp(1.05rem,1.5vw,1.22rem);color:rgba(233,238,247,.9);
    max-width:54ch;line-height:1.72;text-wrap:pretty;overflow-wrap:break-word;
  }
.page-index .hero-cta{display:flex;gap:14px;flex-wrap:wrap;margin-top:34px}
.page-index .hero-trust{display:flex;flex-direction:column;gap:11px;margin-top:38px;padding-top:26px;
    border-top:1px solid rgba(255,255,255,.14);font-size:14.5px;color:rgba(233,238,247,.82)}
.page-index .hero-trust span{display:inline-flex;align-items:flex-start;gap:10px;font-family:"Source Sans 3","Noto Sans SC",sans-serif;line-height:1.45}
.page-index .hero-trust span::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--cinnabar);flex-shrink:0;margin-top:7px}
.page-index .tp-shell{position:relative;min-width:0}
.page-index .tp-shell::before{content:"";position:absolute;inset:auto -8% -14% 12%;height:60%;z-index:-1;
    background:radial-gradient(closest-side,var(--indigo-500),transparent);filter:blur(10px)}
.page-index .tp{background:var(--surface);border-radius:var(--radius-lg);box-shadow:0 34px 80px rgba(0,0,0,.45);
    overflow:hidden;color:var(--ink);width:100%;max-width:456px;margin-left:auto}
.page-index .tp-chrome{display:flex;align-items:center;gap:8px;padding:13px 18px;background:var(--paper-2);border-bottom:1px solid var(--line)}
.page-index .tp-dots{display:flex;gap:6px}
.page-index .tp-dots i{width:10px;height:10px;border-radius:50%;background:#cdd6e6;display:block}
.page-index .tp-title{margin-left:6px;font-family:"Spectral","Noto Serif SC",serif;font-weight:600;font-size:14px;color:var(--indigo-900)}
.page-index .tp-live{margin-left:auto;font-size:11.5px;font-weight:700;color:var(--cinnabar-d);background:rgba(192,54,44,.09);
    padding:3px 9px;border-radius:999px;font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-index .tp-body{padding:20px 20px 18px;display:flex;flex-direction:column;gap:15px}
.page-index .tp-step{display:flex;flex-direction:column;gap:8px}
.page-index .tp-lab{font-size:12px;font-weight:700;color:var(--indigo-500);letter-spacing:.03em;
    font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-index .tp-select{display:flex;align-items:center;justify-content:space-between;border:1.5px solid var(--indigo-200);
    background:var(--indigo-100);border-radius:10px;padding:11px 14px;font-weight:600;color:var(--indigo-900);font-size:14.5px}
.page-index .tp-select svg{width:16px;height:16px;color:var(--indigo-500)}
.page-index .tp-chips{display:flex;gap:8px;flex-wrap:wrap}
.page-index .tp-chips span{font-size:13px;font-weight:600;padding:6px 12px;border-radius:999px;background:var(--indigo-100);
    color:var(--indigo-700);font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-index .tp-chips span.hot{background:rgba(192,54,44,.1);color:var(--cinnabar-d)}
.page-index .tp-checks{list-style:none;display:flex;flex-direction:column;gap:10px}
.page-index .tp-checks li{display:flex;align-items:flex-start;gap:10px;font-size:14px;color:var(--ink);line-height:1.45}
.page-index .tp-checks li svg{width:18px;height:18px;flex-shrink:0;margin-top:1px}
.page-index .tp-checks .ok svg{color:var(--indigo-500)}
.page-index .tp-checks .todo{color:var(--muted)}
.page-index .tp-checks .todo svg{color:var(--cinnabar)}
.page-index .tp-foot{display:flex;align-items:center;gap:12px;padding-top:14px;border-top:1px solid var(--line)}
.page-index .tp-meter{flex:1;height:8px;border-radius:999px;background:var(--paper-2);overflow:hidden}
.page-index .tp-meter i{display:block;height:100%;width:82%;border-radius:999px;
    background:linear-gradient(90deg,var(--indigo-500),var(--indigo-600))}
.page-index .tp-pct{font-size:13px;font-weight:700;color:var(--indigo-700);font-family:"Source Sans 3","Noto Sans SC",sans-serif;white-space:nowrap}
.page-index .tp-cap{margin-top:14px;text-align:center;font-size:12.5px;color:rgba(233,238,247,.62);
    font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-index .mod-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(256px,1fr));gap:16px;margin-top:clamp(30px,4vw,44px)}
.page-index .mod-card{display:flex;flex-direction:column;gap:13px;background:var(--surface);border:1px solid var(--line);
    border-radius:var(--radius-lg);padding:28px 26px;position:relative;color:inherit;
    transition:transform .25s var(--ease),box-shadow .25s var(--ease),border-color .25s var(--ease)}
.page-index .mod-card:hover{transform:translateY(-3px);box-shadow:var(--shadow-md);border-color:var(--indigo-200)}
.page-index .mod-card.feat{border-color:var(--indigo-300);background:linear-gradient(180deg,#fff,var(--indigo-100))}
.page-index .mod-ic{width:34px;height:34px;color:var(--indigo-600)}
.page-index .mod-card h3{font-size:1.24rem;color:var(--indigo-900);letter-spacing:-.01em}
.page-index .mod-desc{font-size:14.5px;color:var(--muted);line-height:1.58}
.page-index .mod-list{list-style:none;display:flex;flex-wrap:wrap;gap:6px}
.page-index .mod-list li{font-size:12.5px;font-weight:600;color:var(--indigo-700);background:var(--indigo-100);
    padding:4px 10px;border-radius:999px;font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-index .mod-go{margin-top:auto;display:inline-flex;align-items:center;gap:7px;font-weight:600;font-size:14px;
    color:var(--cinnabar);font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-index .mod-go .arrow{transition:transform .3s var(--ease)}
.page-index .mod-card:hover .mod-go .arrow{transform:translateX(3px)}
.page-index .mod-badge{position:absolute;top:22px;right:22px;font-size:11.5px;font-weight:700;color:var(--cinnabar-d);
    background:rgba(192,54,44,.09);padding:4px 10px;border-radius:999px;font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-index .toolzone{position:relative;overflow:hidden;background:var(--indigo-900);color:#fff;isolation:isolate;
    padding:clamp(48px,6.5vw,88px) 0}
.page-index .toolzone::before{content:"";position:absolute;inset:0;z-index:-1;
    background:
      radial-gradient(900px 520px at 86% 8%,rgba(44,127,114,.42),transparent 62%),
      linear-gradient(158deg,#12211d 0%,#183029 100%)}
.page-index .tool-feature{display:grid;grid-template-columns:1fr 1fr;gap:clamp(36px,5vw,64px);align-items:start}
.page-index .tf-copy{min-width:0}
.page-index .tf-copy h2{font-size:clamp(1.7rem,3.4vw,2.4rem);color:#fff;letter-spacing:-.02em;text-wrap:balance;line-height:1.16;max-width:18ch}
.page-index .tf-desc{color:rgba(233,238,247,.86);font-size:clamp(1.02rem,1.4vw,1.14rem);line-height:1.7;margin-top:18px;max-width:52ch;text-wrap:pretty}
.page-index .tf-feats{list-style:none;display:grid;grid-template-columns:1fr 1fr;gap:12px 24px;margin-top:26px}
.page-index .tf-feats li{display:flex;align-items:flex-start;gap:10px;font-size:14.5px;color:rgba(233,238,247,.94);line-height:1.42}
.page-index .tf-feats li svg{width:19px;height:19px;flex-shrink:0;margin-top:1px;color:var(--indigo-200)}
.page-index .tf-cta{display:flex;gap:14px;flex-wrap:wrap;margin-top:30px}
.page-index .tf-flow{display:flex;flex-direction:column;gap:12px;min-width:0}
.page-index .tf-step{display:flex;gap:16px;align-items:flex-start;background:rgba(255,255,255,.05);
    border:1px solid rgba(255,255,255,.13);border-radius:14px;padding:16px 18px;
    transition:transform .25s var(--ease),background .25s var(--ease),border-color .25s var(--ease)}
.page-index .tf-step:hover{transform:translateX(3px);background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.24)}
.page-index .tf-num{flex-shrink:0;width:34px;height:34px;border-radius:10px;display:flex;align-items:center;justify-content:center;
    font-family:"Spectral","Noto Serif SC",serif;font-weight:700;font-size:16px;color:#fff;
    background:var(--indigo-600);border:1px solid var(--indigo-500)}
.page-index .tf-step:last-child .tf-num{background:var(--cinnabar);border-color:var(--cinnabar)}
.page-index .tf-scopy{min-width:0}
.page-index .tf-scopy b{display:block;font-family:"Spectral","Noto Serif SC",serif;font-weight:600;font-size:1.08rem;color:#fff;margin-bottom:3px}
.page-index .tf-scopy span{display:block;font-size:14px;color:rgba(233,238,247,.76);line-height:1.5}
@media(max-width:900px){
.page-index .tool-feature{grid-template-columns:1fr;gap:36px}
.page-index .tf-feats{max-width:520px}
}
@media(max-width:560px){
.page-index .tf-feats{grid-template-columns:1fr}
}
.page-index .impl{background:var(--paper-2)}
.page-index .impl-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-top:clamp(30px,4vw,44px)}
.page-index .impl-card{display:flex;flex-direction:column;gap:12px;background:var(--surface);border:1px solid var(--line);
    border-radius:var(--radius-lg);padding:28px 26px;
    transition:transform .25s var(--ease),box-shadow .25s var(--ease),border-color .25s var(--ease)}
.page-index .impl-card:hover{transform:translateY(-3px);box-shadow:var(--shadow-md);border-color:var(--indigo-200)}
.page-index .impl-chip{align-self:flex-start;display:inline-flex;align-items:center;gap:7px;font-size:12px;font-weight:700;
    color:var(--indigo-600);background:var(--indigo-100);padding:4px 12px;border-radius:999px;
    font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-index .impl-chip::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--cinnabar)}
.page-index .impl-card h3{font-size:1.22rem;color:var(--indigo-900);letter-spacing:-.01em;line-height:1.25}
.page-index .impl-card h3 small{display:block;font-family:"Source Sans 3","Noto Sans SC",sans-serif;font-weight:600;
    font-size:12.5px;color:var(--indigo-500);margin-top:5px;letter-spacing:.03em}
.page-index .impl-card p{font-size:14.5px;color:var(--muted);line-height:1.6}
.page-index .impl-tag{margin-top:auto;align-self:flex-start;font-size:12px;font-weight:600;color:var(--muted);
    background:var(--paper);border:1px solid var(--line);padding:4px 11px;border-radius:999px;
    font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-index .news-list{margin-top:clamp(30px,4vw,40px);display:grid;gap:1px;background:var(--line);border:1px solid var(--line);
    border-radius:var(--radius-lg);overflow:hidden}
.page-index .news-item{display:grid;grid-template-columns:184px 1fr auto;gap:26px;align-items:center;
    background:var(--surface);padding:24px 28px;transition:background .2s var(--ease)}
.page-index .news-item:hover{background:var(--paper)}
.page-index .news-thumb{width:184px;height:120px;object-fit:cover;border-radius:12px;display:block;background:var(--indigo-900)}
.page-index .news-body{min-width:0}
.page-index .news-topline{display:flex;align-items:center;gap:12px;margin-bottom:9px}
.page-index .news-item time{font-family:"Source Sans 3",sans-serif;font-weight:600;color:var(--muted);font-size:13.5px;letter-spacing:.01em}
.page-index .news-cat{font-size:12px;font-weight:600;color:var(--indigo-600);background:var(--indigo-100);
    border-radius:6px;padding:3px 10px;font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-index .news-cat.up{color:var(--cinnabar-d);background:rgba(192,54,44,.08)}
.page-index .news-body h3{font-size:1.28rem;color:var(--indigo-900);margin-bottom:6px;line-height:1.32;text-wrap:pretty}
.page-index .news-body p{color:var(--muted);font-size:1rem;line-height:1.6;max-width:64ch}
.page-index .news-go{width:40px;height:40px;border-radius:50%;border:1.5px solid var(--line);color:var(--indigo-500);
    display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:.25s var(--ease)}
.page-index .news-go svg{width:18px;height:18px}
.page-index .news-item:hover .news-go{border-color:var(--cinnabar);color:var(--cinnabar);transform:translateX(3px)}
.page-index .res-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;margin-top:clamp(30px,4vw,40px)}
.page-index .res-row{display:flex;align-items:center;gap:15px;background:var(--surface);border:1px solid var(--line);
    border-radius:var(--radius-lg);padding:20px 22px;text-decoration:none;color:inherit;
    transition:transform .22s var(--ease),box-shadow .22s var(--ease),border-color .22s var(--ease)}
.page-index .res-row:hover{transform:translateY(-3px);box-shadow:var(--shadow-md);border-color:var(--indigo-200)}
.page-index .res-logo{width:48px;height:48px;border-radius:12px;flex-shrink:0}
.page-index .res-row .rr-main{flex:1;min-width:0}
.page-index .res-row b{display:block;font-family:"Spectral","Noto Serif SC",serif;font-weight:600;font-size:1.08rem;color:var(--indigo-900)}
.page-index .res-row .rr-main span{display:block;font-size:13.5px;color:var(--muted);margin-top:2px}
.page-index .res-row .r-ext{width:19px;height:19px;color:var(--indigo-300);flex-shrink:0;transition:color .2s,transform .2s}
.page-index .res-row:hover .r-ext{color:var(--cinnabar);transform:translate(2px,-2px)}
@media (prefers-reduced-motion:no-preference){
.page-index html.js .reveal{opacity:0;transform:translateY(18px);
      transition:opacity .8s var(--ease),transform .8s var(--ease)}
.page-index html.js .reveal.is-visible{opacity:1;transform:none}
}
@media(max-width:960px){
.page-index .hero-grid{grid-template-columns:1fr;gap:44px}
.page-index .tp{max-width:520px;margin:0 auto}
.page-index .tp-shell::before{display:none}
}
@media(max-width:820px){
.page-index .news-item{grid-template-columns:1fr;gap:16px;padding:22px}
.page-index .news-thumb{width:100%;height:190px}
.page-index .news-go{display:none}
.page-index .mobile-menu .btn{width:100%;justify-content:center;margin-top:24px}
}
.page-index .hero{color:var(--ink)}
.page-index .hero::before{background:
    radial-gradient(1000px 560px at 88% -6%,rgba(87,190,174,.32),transparent 62%),
    radial-gradient(660px 460px at 0% 108%,rgba(207,70,53,.13),transparent 66%),
    linear-gradient(162deg,#e9f3ee 0%,#f2f6f2 46%,#f6efe4 108%)}
.page-index .hero .tag{color:var(--indigo-700);background:rgba(255,255,255,.78);border:1px solid var(--line)}
.page-index .hero h1{color:var(--ink)}
.page-index .hero h1 .hl{color:var(--cinnabar)}
.page-index .hero .sub{color:var(--muted)}
.page-index .hero-trust{border-top-color:var(--line);color:var(--ink)}
.page-index .hero .btn-onDark{border-color:var(--line);color:var(--indigo-700);background:var(--surface)}
.page-index .hero .btn-onDark:hover{border-color:var(--indigo-500);background:var(--indigo-100)}
.page-index .tp{box-shadow:0 24px 58px rgba(44,122,112,.20);border:1px solid var(--line)}
.page-index .tp-cap{color:var(--muted)}
</style>
