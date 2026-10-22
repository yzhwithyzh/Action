<script setup lang="ts">
/**
 * 新闻详情页。
 *
 * 只服务「没有配置 linkUrl」的条目 —— 配了链接的在列表页就直接跳走了（站内路由或外链）。
 * 数据取 `/action/site/news/{id}`，该接口只返回 `status='0'` 的已发布新闻，
 * 停用/已删的条目拿不到 data，落到下方的「未找到」态。
 *
 * 正文用 v-html 渲染：后台是富文本编辑器录入的 HTML，这是内容型字段的固有形态。
 * 来源仅限已登录且持有 `action:news:add|edit` 的后台管理员，与匿名输入无关。
 */
interface NewsRow {
  newsId: number
  categoryZh: string | null
  categoryEn: string | null
  titleZh: string | null
  titleEn: string | null
  summaryZh: string | null
  summaryEn: string | null
  contentZh: string | null
  contentEn: string | null
  thumbUrl: string | null
  publishDate: string | null
  linkUrl: string | null
  isExternal: '0' | '1' | null
}

const route = useRoute()
const { t } = useI18n()
const { pick } = useBilingual()

const id = computed(() => String(route.params.id ?? ''))

// 详情页是否被预渲染取决于构建时列表页有没有爬到它，取不到时靠客户端那次重取补上
const { data: res } = await useSiteObject<NewsRow>(`/news/${id.value}`, `news-detail:${id.value}`)
const row = computed<NewsRow | null>(() => res.value?.data ?? null)

const title = computed(() => pick(row.value, 'title'))
const summary = computed(() => pick(row.value, 'summary'))
/**
 * 段首的 Tab / 全角空格 → `data-indent` 标记，由 CSS 渲染成首行缩进 2 字。
 *
 * 【为什么要转】后台录入时习惯敲一个 Tab 做首行缩进，在编辑器里看着是对的
 * （`Editor` 组件给自己加了 `white-space: pre-wrap`，保留了 Tab 的宽度），
 * 但 HTML 的默认 `white-space: normal` 会把 Tab **折叠成一个普通空格** ——
 * 于是发到官网缩进就没了。两边的 `white-space` 不一致，这是唯一的原因。
 *
 * 【为什么不给所有 `<p>` 一律加缩进】**哪一段要缩进是录入者定的**。
 * 实测线上那条新闻的英文正文：电头 `GUANGZHOU, China – August 22, 2026 –`
 * 没敲 Tab，后面 6 个正文段都敲了 —— 一律缩进会把电头也顶进去。
 * 按语言分（中文缩进、英文不缩进）同样是错的：这条新闻中英文都敲了 Tab。
 */
const INDENT_AT_PARAGRAPH_START = /(<p\b[^>]*)>[\s　]+/g
const content = computed(() =>
  pick(row.value, 'content').replace(INDENT_AT_PARAGRAPH_START, '$1 data-indent>'),
)

useHead({
  title: computed(() => (title.value ? `${title.value} | ACTION` : t('newsDetail.notFound'))),
  meta: [{ name: 'description', content: computed(() => summary.value || t('news._desc')) }],
})

useReveal()
</script>

<template>
  <div class="page-news-detail">
    <section class="sec">
      <div class="wrap">
        <nav class="crumb" :aria-label="t('newsDetail.crumbAria')">
          <NuxtLink to="/">{{ t('nav.platform') }}</NuxtLink>
          <span aria-hidden="true">/</span>
          <NuxtLink to="/news">{{ t('nav.news') }}</NuxtLink>
          <span aria-hidden="true">/</span>
          <span class="cur">{{ title || t('newsDetail.notFound') }}</span>
        </nav>

        <article v-if="row" class="art">
          <header class="art-head reveal">
            <div class="art-meta">
              <time v-if="row.publishDate" :datetime="row.publishDate">{{ row.publishDate }}</time>
              <span v-if="pick(row, 'category')" class="src">{{ pick(row, 'category') }}</span>
            </div>
            <h1>{{ title }}</h1>
            <p v-if="summary" class="art-sum">{{ summary }}</p>
          </header>

          <img v-if="row.thumbUrl" class="art-thumb reveal" :src="row.thumbUrl" :alt="title" />

          <div v-if="content" class="art-body reveal" v-html="content" />
          <p v-else class="art-empty reveal">{{ t('newsDetail.noContent') }}</p>

          <p v-if="row.linkUrl" class="art-origin reveal">
            <a
              class="btn btn-line"
              :href="row.linkUrl"
              :target="row.isExternal === '1' ? '_blank' : undefined"
              :rel="row.isExternal === '1' ? 'noopener noreferrer' : undefined"
            >
              {{ t('newsDetail.readOrigin') }}
              <span v-if="row.isExternal === '1'" class="vh">{{ t('common.newWindow') }}</span>
            </a>
          </p>
        </article>

        <div v-else class="art-404 reveal">
          <h1>{{ t('newsDetail.notFound') }}</h1>
          <p>{{ t('newsDetail.notFoundDesc') }}</p>
        </div>

        <p class="art-back reveal">
          <NuxtLink to="/news">&larr; {{ t('newsDetail.back') }}</NuxtLink>
        </p>
      </div>
    </section>
  </div>
</template>

<style>
.page-news-detail .sec{padding:clamp(32px,4.4vw,60px) 0}
.page-news-detail .wrap{max-width:820px}
.page-news-detail .crumb{display:flex;align-items:center;gap:9px;font-size:13.5px;color:var(--muted);margin-bottom:26px;flex-wrap:wrap}
.page-news-detail .crumb a{color:var(--indigo-600);transition:color .2s var(--ease)}
.page-news-detail .crumb a:hover{color:var(--cinnabar)}
.page-news-detail .crumb .cur{color:var(--indigo-900);font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:38ch}
.page-news-detail .art-head{border-bottom:1px solid var(--line);padding-bottom:clamp(18px,2.4vw,26px)}
.page-news-detail .art-meta{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:14px}
.page-news-detail time{font-family:"Source Sans 3",sans-serif;font-weight:600;color:var(--muted);font-size:13px;font-variant-numeric:tabular-nums}
.page-news-detail .src{font-size:12px;font-weight:700;border-radius:6px;padding:3px 10px;color:var(--indigo-600);background:var(--indigo-100);white-space:nowrap}
.page-news-detail h1{font-size:clamp(1.6rem,3.2vw,2.3rem);color:var(--indigo-900);letter-spacing:-.02em;line-height:1.24;text-wrap:balance}
.page-news-detail .art-sum{margin-top:14px;font-size:clamp(.98rem,1.3vw,1.08rem);color:var(--muted);line-height:1.7;max-width:64ch;text-wrap:pretty}
.page-news-detail .art-thumb{display:block;width:100%;margin-top:clamp(22px,3vw,32px);border-radius:var(--radius-lg);border:1px solid var(--line);object-fit:cover}
.page-news-detail .art-body{margin-top:clamp(22px,3vw,32px);font-size:15.5px;line-height:1.85;color:var(--ink)}
.page-news-detail .art-body p{margin:0 0 1.1em}
.page-news-detail .art-body h2{font-size:1.35rem;color:var(--indigo-900);margin:1.8em 0 .7em;line-height:1.3}
.page-news-detail .art-body h3{font-size:1.14rem;color:var(--indigo-900);margin:1.6em 0 .6em;line-height:1.35}
.page-news-detail .art-body ul,.page-news-detail .art-body ol{margin:0 0 1.1em;padding-left:1.5em}
.page-news-detail .art-body li{margin-bottom:.45em}
.page-news-detail .art-body a{color:var(--indigo-600);text-decoration:underline;text-underline-offset:3px}
.page-news-detail .art-body a:hover{color:var(--cinnabar)}
.page-news-detail .art-body img{max-width:100%;height:auto;border-radius:12px;margin:1.2em 0}
.page-news-detail .art-body blockquote{margin:1.4em 0;padding:2px 0 2px 18px;border-left:3px solid var(--indigo-300);color:var(--muted)}
.page-news-detail .art-body table{width:100%;border-collapse:collapse;margin:1.3em 0;font-size:14.5px}
.page-news-detail .art-body th,.page-news-detail .art-body td{border:1px solid var(--line);padding:9px 12px;text-align:left}
.page-news-detail .art-body th{background:var(--paper);font-weight:600;color:var(--indigo-900)}
/* 首行缩进 2 字。**只缩进录入时敲了 Tab 的那些段落**（script 里把段首的
   Tab / 全角空格转成了 data-indent）—— HTML 的默认 white-space 会把 Tab 折叠成
   一个普通空格，编辑器里看着有缩进、发到官网就没了（编辑器给自己开了
   white-space:pre-wrap，两边不一致），所以缩进要由样式来做、但**由内容来决定**。
   中英文一视同仁：实测那条新闻中英文正文都敲了 Tab，按语言分是错的。 */
.page-news-detail .art-body>p[data-indent]{text-indent:2em}
/* ---- 以下是 Quill 2 生成的内容类。官网没引 quill 的 CSS，不补这些就全是死类 ---- */
/* 对齐 */
.page-news-detail .art-body .ql-align-center{text-align:center;text-indent:0}
.page-news-detail .art-body .ql-align-right{text-align:right;text-indent:0}
.page-news-detail .art-body .ql-align-justify{text-align:justify}
/* 字号（与 quill.snow.css 的取值一致，改了两边会对不上） */
.page-news-detail .art-body .ql-size-small{font-size:.75em}
.page-news-detail .art-body .ql-size-large{font-size:1.5em}
.page-news-detail .art-body .ql-size-huge{font-size:2.5em}
.page-news-detail .art-body .ql-font-serif{font-family:"Spectral","Noto Serif SC",serif}
.page-news-detail .art-body .ql-font-monospace{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
/* 工具栏的「缩进」按钮：Quill 给的是整段左缩进，每级 3em（li 上另算，见下） */
.page-news-detail .art-body .ql-indent-1{padding-left:3em}
.page-news-detail .art-body .ql-indent-2{padding-left:6em}
.page-news-detail .art-body .ql-indent-3{padding-left:9em}
.page-news-detail .art-body .ql-indent-4{padding-left:12em}
/* 列表。**Quill 2 的无序列表也是 <ol>**，靠 li[data-list] 区分，项目符号由
   <span class="ql-ui"> 的 ::before 生成 —— 不补这一段，无序列表会被浏览器
   按 ol 的默认样式渲染成「1. 2. 3.」，而那个 span 是空的、什么都不显示。 */
.page-news-detail .art-body li{list-style-type:none;padding-left:1.5em;position:relative;text-indent:0}
.page-news-detail .art-body li>.ql-ui:before{display:inline-block;margin-left:-1.5em;margin-right:.3em;text-align:right;white-space:nowrap;width:1.2em;color:var(--muted)}
.page-news-detail .art-body li[data-list=bullet]>.ql-ui:before{content:"\2022"}
.page-news-detail .art-body ol{counter-reset:ql-list}
.page-news-detail .art-body li[data-list=ordered]{counter-increment:ql-list}
.page-news-detail .art-body li[data-list=ordered]>.ql-ui:before{content:counter(ql-list) ". "}
/* 代码块 */
.page-news-detail .art-body pre{background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:1.3em 0;overflow-x:auto;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13.5px;line-height:1.7;text-indent:0;white-space:pre-wrap}
.page-news-detail .art-empty{margin-top:clamp(22px,3vw,32px);font-size:14.5px;color:var(--muted)}
.page-news-detail .art-origin{margin-top:clamp(24px,3.4vw,36px)}
.page-news-detail .art-origin .btn{display:inline-flex;align-items:center;gap:9px;padding:12px 22px;border-radius:999px;font-weight:600;font-size:14.5px;border:1.5px solid var(--indigo-300);color:var(--indigo-700);background:var(--surface);transition:.22s var(--ease)}
.page-news-detail .art-origin .btn:hover{border-color:var(--cinnabar);color:var(--cinnabar);background:var(--paper)}
.page-news-detail .art-404{padding:clamp(40px,6vw,80px) 0;text-align:center}
.page-news-detail .art-404 p{margin-top:14px;color:var(--muted);font-size:14.5px}
.page-news-detail .art-back{margin-top:clamp(28px,4vw,44px);padding-top:clamp(18px,2.4vw,26px);border-top:1px solid var(--line);font-size:14.5px;font-weight:600}
.page-news-detail .art-back a{color:var(--indigo-600);transition:color .2s var(--ease)}
.page-news-detail .art-back a:hover{color:var(--cinnabar)}
</style>
