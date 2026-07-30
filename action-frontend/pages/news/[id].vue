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

const { data: res } = await useSiteObject<NewsRow>(`/news/${id.value}`, `news-detail:${id.value}`)
const row = computed<NewsRow | null>(() => res.value?.data ?? null)

const title = computed(() => pick(row.value, 'title'))
const summary = computed(() => pick(row.value, 'summary'))
/** 正文缺失时退到摘要 —— 现存 11 条种子数据的 content_zh/content_en 全为空 */
const content = computed(() => pick(row.value, 'content'))

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
        <nav class="crumb" aria-label="面包屑">
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
