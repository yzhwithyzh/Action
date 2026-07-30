<script setup lang="ts">
/**
 * news.html 迁移而来。
 * 模板与样式保持原状；样式已加 .page-news 命名空间，避免 SPA 路由切换时跨页污染。
 *
 * 列表数据来自 `/action/site/news`（原为 11 条硬编码）。
 * 注意：**不在前端二次排序**，照接口返回顺序渲染。接口现有顺序确实是反的
 * （DAO 的 `publish_date desc` 在 PG 下默认 NULLS FIRST，5 条无日期的领域新闻
 * 被顶到最前），那是 deferred-work.md 的 W21，须在 DAO 侧修；前端再排一次
 * 会导致前后端各有一套顺序。
 *
 * 文件位置说明：原为 `pages/news.vue`，因新增详情页 `pages/news/[id].vue` 而迁到
 * `pages/news/index.vue` —— Nuxt 下 `news.vue` 与 `news/` 目录并存时，前者会被当作
 * 带 `<NuxtPage>` 的父路由，列表内容会连同详情一起渲染。
 */
interface NewsRow {
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

const { t } = useI18n()
const { pick } = useBilingual()

useHead({
  title: t('news._title'),
  meta: [{ name: 'description', content: t('news._desc') }],
})

const { data: res } = await useSiteList<NewsRow>('/news', { pageNum: 1, pageSize: 50 }, 'news-page')
const rows = computed<NewsRow[]>(() => res.value?.rows ?? [])

/** 领域新闻（外链）归 field，团队动态归 team —— 与原页面的 data-cat 取值一致 */
const catOf = (r: NewsRow) => (r.isExternal === '1' ? 'field' : 'team')

/**
 * 没配 `linkUrl` 的条目落到站内详情页 `/news/{id}`。
 * 从前这里是 `:to="r.linkUrl || undefined"`，NuxtLink 会渲染成没有 href 的 <a>，
 * 于是后台新建但未填链接的新闻在官网上就是一条点不动的死行。
 */
const hrefOf = (r: NewsRow) => r.linkUrl || `/news/${r.newsId}`
/** 只有「标记为外链**且**确有链接」才开新窗口；缺链接时走的是站内详情，不能开新窗 */
const opensNewTab = (r: NewsRow) => r.isExternal === '1' && !!r.linkUrl

const activeCat = ref<'all' | 'team' | 'field'>('all')
/**
 * 筛选用 CSS 隐藏而**不卸载节点** —— 与原 news.html 的 classList.toggle('hide') 一致。
 * 若用 v-for 过滤，切回来的是全新 DOM：它不带 .is-visible，而 useReveal() 的
 * IntersectionObserver 只在 onMounted 建立一次，永远不会观察这些新节点，
 * 于是它们停在 `.reveal{opacity:0}` 上永久不可见。
 */
const isHidden = (r: NewsRow) => activeCat.value !== 'all' && catOf(r) !== activeCat.value

/** `2026-07-01` → `2026-07`；原页面 <time> 精度到年月 */
const ym = (d: string | null) => (d ? d.slice(0, 7) : '')

useReveal()
</script>

<template>
  <div class="page-news">
    <section class="sec" id="news">
      <div class="wrap">
        <div class="p-intro">
          <div>
            <span class="kicker reveal">{{ t('news.s001') }}</span>
            <h2 class="title reveal">{{ t('news.s002') }}</h2>
            <p class="reveal">{{ t('news.s003') }}</p>
          </div>
        </div>

        <div class="filt reveal" id="filter" role="group" aria-label="按标签筛选新闻">
          <button type="button" class="fchip" :class="{ on: activeCat === 'all' }" :aria-pressed="activeCat === 'all'" data-cat="all" @click="activeCat = 'all'">{{ t('news.s004') }}</button>
          <button type="button" class="fchip" :class="{ on: activeCat === 'team' }" :aria-pressed="activeCat === 'team'" data-cat="team" @click="activeCat = 'team'">{{ t('news.s005') }}</button>
          <button type="button" class="fchip" :class="{ on: activeCat === 'field' }" :aria-pressed="activeCat === 'field'" data-cat="field" @click="activeCat = 'field'">{{ t('news.s006') }}</button>
        </div>

        <div class="nlist" id="nlist">
          <NuxtLink
            v-for="r in rows"
            :key="r.newsId"
            :to="hrefOf(r)"
            class="nrow reveal"
            :class="[catOf(r), { hide: isHidden(r) }]"
            :data-cat="catOf(r)"
            :target="opensNewTab(r) ? '_blank' : undefined"
            :rel="opensNewTab(r) ? 'noopener noreferrer' : undefined"
          >
            <img
              v-if="r.thumbUrl"
              class="nthumb"
              :src="r.thumbUrl"
              :alt="pick(r, 'title')"
              loading="lazy"
              :width="r.isExternal === '1' ? 200 : 300"
              :height="r.isExternal === '1' ? 128 : 192"
            />
            <div class="nbody">
              <div class="ntop">
                <time v-if="r.publishDate" :datetime="ym(r.publishDate)">{{ ym(r.publishDate) }}</time>
                <span class="src" :class="catOf(r)">{{ pick(r, 'category') }}</span>
              </div>
              <h3>{{ pick(r, 'title') }}</h3>
              <p>{{ pick(r, 'summary') }}</p>
            </div>
            <span class="ngo" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path v-if="opensNewTab(r)" d="M7 17 17 7M8 7h9v9" />
                <path v-else d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </span>
            <span v-if="opensNewTab(r)" class="vh">{{ t('news.s019') }}</span>
          </NuxtLink>
        </div>
      </div>
    </section>
  </div>
</template>

<style>
.page-news .skip-link{position:absolute;left:12px;top:-60px;z-index:var(--z-toast);background:var(--indigo-700);color:#fff;font-weight:600;font-size:15px;padding:12px 20px;border-radius:10px;transition:top .2s var(--ease)}
.page-news .sec{padding:clamp(40px,5vw,68px) 0;scroll-margin-top:130px}
.page-news .btn{display:inline-flex;align-items:center;justify-content:center;gap:9px;padding:13px 24px;border-radius:999px;font-weight:600;font-size:15px;border:1.5px solid transparent;cursor:pointer;white-space:nowrap;transition:transform .25s var(--ease),background-color .25s var(--ease),box-shadow .25s var(--ease),border-color .25s var(--ease)}
.page-news .phero::before{content:"";position:absolute;inset:0;z-index:-1;background:radial-gradient(1000px 560px at 90% 0%,rgba(44,127,114,.5),transparent 60%),radial-gradient(680px 460px at 2% 100%,rgba(24,48,41,.7),transparent 65%),linear-gradient(160deg,#0d1a17 0%,#12211d 44%,#183029 100%)}
.page-news .phero .wrap{padding:clamp(28px,3.6vw,42px) clamp(20px,4vw,44px) clamp(38px,5vw,54px)}
.page-news .crumb{display:flex;align-items:center;gap:9px;font-size:13.5px;color:rgba(233,238,247,.66);margin-bottom:22px;flex-wrap:wrap}
.page-news .phero-tag{display:inline-flex;align-items:center;gap:10px;font-size:13px;font-weight:600;letter-spacing:.02em;color:var(--indigo-200);background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.16);padding:8px 16px;border-radius:999px;backdrop-filter:blur(4px)}
.page-news .phero h1{font-size:clamp(1.9rem,3.9vw,3rem);font-weight:700;letter-spacing:-.025em;margin:18px 0 0;text-wrap:balance;line-height:1.14}
.page-news .phero .psub{margin-top:18px;font-size:clamp(1rem,1.4vw,1.16rem);color:rgba(233,238,247,.9);max-width:62ch;line-height:1.7;text-wrap:pretty}
.page-news .subnav{position:sticky;top:72px;z-index:var(--z-subnav);background:rgba(242,246,244,.9);backdrop-filter:blur(12px) saturate(1.3);border-bottom:1px solid var(--line)}
.page-news .subnav-in{display:flex;align-items:center;gap:4px;overflow-x:auto;scrollbar-width:none}
.page-news .subnav-in::-webkit-scrollbar{display:none}
.page-news .subnav a{position:relative;flex-shrink:0;padding:15px 15px 13px;font-size:14.5px;font-weight:600;color:var(--muted);white-space:nowrap;transition:color .2s}
.page-news .subnav a .n{display:inline-flex;align-items:center;justify-content:center;width:19px;height:19px;margin-right:7px;border-radius:6px;background:var(--indigo-100);color:var(--indigo-600);font-size:11.5px;font-weight:700;font-family:"Spectral",serif}
.page-news .subnav a::after{content:"";position:absolute;left:15px;right:15px;bottom:-1px;height:2px;background:var(--cinnabar);transform:scaleX(0);transform-origin:left;transition:transform .3s var(--ease)}
.page-news .subnav a:hover,.page-news .subnav a.active{color:var(--indigo-900)}
.page-news .subnav a.active .n{background:var(--cinnabar);color:#fff}
.page-news .subnav a.active::after{transform:scaleX(1)}
.page-news .sec.is-hidden{display:none}
.page-news .p-intro{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;flex-wrap:wrap;margin-bottom:clamp(22px,3vw,30px)}
.page-news h2.title{font-size:clamp(1.5rem,2.8vw,2.1rem);color:var(--indigo-900);letter-spacing:-.02em;line-height:1.2}
.page-news .p-intro p{font-size:14px;color:var(--muted);max-width:56ch;margin-top:8px;line-height:1.6}
.page-news .filt{display:flex;flex-wrap:wrap;gap:9px;margin-bottom:clamp(20px,3vw,28px)}
.page-news .fchip{font-family:inherit;font-size:13.5px;font-weight:600;color:var(--indigo-700);background:var(--surface);border:1.5px solid var(--line);padding:8px 16px;border-radius:999px;cursor:pointer;transition:.2s var(--ease)}
.page-news .fchip:hover{border-color:var(--indigo-300);background:var(--indigo-100)}
.page-news .fchip.on{background:var(--indigo-700);border-color:var(--indigo-700);color:#fff}
.page-news .nrow.hide{display:none}
.page-news .nrow.field .nthumb{object-fit:contain;padding:16px;background:var(--surface);border:1px solid var(--line)}
.page-news .src{font-size:12px;font-weight:700;border-radius:6px;padding:3px 10px;white-space:nowrap}
.page-news .src.team{color:var(--indigo-600);background:var(--indigo-100)}
.page-news .src.field{color:var(--info);background:var(--info-bg)}
.page-news .feat{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:clamp(20px,3vw,36px);align-items:center;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius-lg);overflow:hidden;margin-bottom:20px}
.page-news .feat img{width:100%;height:100%;min-height:240px;object-fit:cover;display:block;background:var(--indigo-900)}
.page-news .feat .fx{padding:clamp(22px,3vw,38px)}
.page-news .feat .ntop{display:flex;align-items:center;gap:12px;margin-bottom:12px}
.page-news .feat h3{font-size:clamp(1.25rem,2.2vw,1.7rem);color:var(--indigo-900);line-height:1.25;text-wrap:balance}
.page-news .feat p{font-size:14.5px;color:var(--muted);line-height:1.65;margin-top:12px;max-width:52ch}
.page-news .feat .fgo{margin-top:20px;display:inline-flex;align-items:center;gap:8px;font-weight:600;font-size:14.5px;color:var(--cinnabar)}
.page-news .feat .fgo .arrow{transition:transform .3s var(--ease)}
.page-news .feat:hover .fgo .arrow{transform:translateX(3px)}
.page-news time{font-family:"Source Sans 3",sans-serif;font-weight:600;color:var(--muted);font-size:13px;letter-spacing:.01em;font-variant-numeric:tabular-nums;white-space:nowrap}
.page-news .ncat{font-size:12px;font-weight:700;color:var(--indigo-600);background:var(--indigo-100);border-radius:6px;padding:3px 10px;white-space:nowrap}
.page-news .ncat.up{color:var(--cinnabar-d);background:rgba(192,54,44,.08)}
.page-news .ncat.tool{color:var(--info);background:var(--info-bg)}
.page-news .ncat.collab{color:var(--amber);background:var(--amber-bg)}
.page-news .nlist{display:grid;gap:1px;background:var(--line);border:1px solid var(--line);border-radius:var(--radius-lg);overflow:hidden}
.page-news .nrow{display:grid;grid-template-columns:150px 1fr auto;gap:22px;align-items:center;background:var(--surface);padding:20px 24px;transition:background .2s var(--ease)}
.page-news .nrow:hover{background:var(--paper)}
.page-news .nrow .nthumb{width:150px;height:96px;object-fit:cover;border-radius:10px;display:block;background:var(--indigo-100)}
.page-news .nrow .nbody{min-width:0}
.page-news .nrow .ntop{display:flex;align-items:center;gap:11px;margin-bottom:8px}
.page-news .nrow h3{font-size:1.14rem;color:var(--indigo-900);line-height:1.32;text-wrap:pretty}
.page-news .nrow p{color:var(--muted);font-size:13.5px;line-height:1.55;margin-top:5px;max-width:70ch}
.page-news .ngo{width:38px;height:38px;border-radius:50%;border:1.5px solid var(--line);color:var(--indigo-500);display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:.25s var(--ease)}
.page-news .ngo svg{width:17px;height:17px}
.page-news .nrow:hover .ngo{border-color:var(--cinnabar);color:var(--cinnabar);transform:translateX(3px)}
.page-news .fnews{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:14px}
.page-news .fcard{display:flex;align-items:flex-start;gap:15px;background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:20px 22px;transition:.22s var(--ease)}
.page-news .fcard:hover{transform:translateY(-3px);box-shadow:var(--shadow-md);border-color:var(--indigo-200)}
.page-news .fcard .flogo{width:48px;height:48px;flex-shrink:0;border-radius:12px;border:1px solid var(--line);background:var(--paper);object-fit:contain;padding:5px}
.page-news .fcard .fbody{min-width:0;flex:1}
.page-news .fcard .ftop{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.page-news .fcard .fsrc{font-size:11.5px;font-weight:700;color:var(--indigo-600);letter-spacing:.02em}
.page-news .fcard h3{font-size:1.06rem;color:var(--indigo-900);line-height:1.3;text-wrap:pretty}
.page-news .fcard p{font-size:13px;color:var(--muted);line-height:1.55;margin-top:6px}
.page-news .fcard .fext{width:18px;height:18px;color:var(--indigo-300);flex-shrink:0;transition:color .2s,transform .2s}
.page-news .fcard:hover .fext{color:var(--cinnabar);transform:translate(2px,-2px)}
.page-news .note{display:inline-flex;align-items:center;gap:9px;font-size:12.5px;font-weight:600;color:var(--amber);background:var(--amber-bg);border:1px solid #e7d39a;padding:7px 14px;border-radius:999px;margin-top:22px}
@media(max-width:900px){
.page-news .feat{grid-template-columns:1fr}
.page-news .feat img{min-height:200px}
}
@media(max-width:640px){
.page-news .nrow{grid-template-columns:1fr;gap:14px}
.page-news .nrow .nthumb{width:100%;height:180px}
.page-news .ngo{display:none}
}
</style>
