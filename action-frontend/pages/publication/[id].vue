<script setup lang="ts">
/**
 * 成果发表详情页。
 *
 * 路由是 `/publication/[id]`（单数），列表页是 `pages/publications.vue` ——
 * 建 `pages/publications/` 目录会把列表页变成需要 `<NuxtPage>` 的父级路由
 * （同 `guidelines` / `guideline`、`about` / `team`）。
 *
 * 数据取 `/action/site/publications/{id}`，只返回未删除的记录；已停用（status='1'）的
 * 仍可按 id 直达，但不会出现在列表里 —— 与团队成员、报告规范详情同一口径。
 *
 * 页面上的论文信息一律**照发表原文**显示，不做双语选值（库里就没有那两列），
 * 理由见 `composables/usePublications.ts` 的文件头。
 */
import type { PublicationRow } from '~/composables/usePublications'

const route = useRoute()
const { t } = useI18n()
const { authorLine, citeLine } = usePublications()

const id = computed(() => String(route.params.id ?? ''))

// 详情页是否被预渲染取决于构建时列表页有没有爬到它，取不到时靠客户端那次重取补上
const { data: res } = await useSiteObject<PublicationRow>(`/publications/${id.value}`, `publication:${id.value}`)
const row = computed<PublicationRow | null>(() => res.value?.data ?? null)

const affiliations = computed(() => row.value?.affiliations ?? [])
/** 引用文本后台可留空，那时按字段现拼一条，不让「如何引用」整块消失 */
const citation = computed(() => {
  const stored = (row.value?.citationText ?? '').trim()
  if (stored) return stored
  if (!row.value) return ''
  const line = citeLine(row.value)
  const author = authorLine(row.value.authors, 3)

  return [author && `${author}.`, `${row.value.title}.`, line && `${line}.`, row.value.doi && `doi:${row.value.doi}`]
    .filter(Boolean)
    .join(' ')
})

useHead({
  title: computed(() => (row.value?.title ? `${row.value.title} | ACTION` : t('publicationDetail.notFound'))),
  meta: [
    {
      name: 'description',
      content: computed(() => (row.value?.abstract || '').slice(0, 180) || t('publications._desc')),
    },
  ],
})

/**
 * 复制引用。
 *
 * `navigator.clipboard` 在非 HTTPS 或用户拒权时会抛 —— 那时如实提示失败，
 * 不假装复制成功（用户会去粘一段根本没进剪贴板的文字）。
 */
const copyState = ref<'' | 'ok' | 'fail'>('')
let copyTimer: ReturnType<typeof setTimeout> | undefined
const copyCitation = async () => {
  clearTimeout(copyTimer)
  try {
    await navigator.clipboard.writeText(citation.value)
    copyState.value = 'ok'
  }
  catch {
    copyState.value = 'fail'
  }
  copyTimer = setTimeout(() => (copyState.value = ''), 2400)
}
onBeforeUnmount(() => clearTimeout(copyTimer))

useReveal()
</script>

<template>
  <div class="page-pub-detail">
    <section class="sec">
      <div class="wrap">
        <nav class="crumb" :aria-label="t('publicationDetail.crumbAria')">
          <NuxtLink to="/">{{ t('nav.platform') }}</NuxtLink>
          <span aria-hidden="true">/</span>
          <NuxtLink to="/publications">{{ t('nav.publications') }}</NuxtLink>
          <span aria-hidden="true">/</span>
          <span class="cur">{{ row?.title || t('publicationDetail.notFound') }}</span>
        </nav>

        <article v-if="row" class="pub">
          <header class="pub-head reveal">
            <span v-if="row.journal" class="pub-journal">{{ row.journal }}</span>
            <h1>{{ row.title }}</h1>

            <!--
              作者右上角那个数字是机构角标（affiliationIndex + 1），对应下面的机构列表。
              后台没标机构时 affiliationIndex 是 null，这里就不画角标 —— 兜底成 1
              等于给每位作者凭空挂上第一家单位。
            -->
            <p v-if="row.authors?.length" class="pub-authors">
              <span v-for="(author, idx) in row.authors" :key="idx">
                {{ author.name }}<sup v-if="author.affiliationIndex !== null && author.affiliationIndex !== undefined">{{ author.affiliationIndex + 1 }}</sup><span v-if="idx < row.authors.length - 1">, </span>
              </span>
            </p>

            <p v-if="citeLine(row)" class="pub-src">{{ citeLine(row) }}</p>

            <p v-if="row.doi" class="pub-doi">
              <span class="lbl">DOI</span>
              <a :href="`https://doi.org/${row.doi}`" target="_blank" rel="noopener noreferrer">
                {{ row.doi }}
                <span class="vh">{{ t('common.newWindow') }}</span>
              </a>
            </p>
          </header>

          <img v-if="row.coverImageUrl" class="pub-cover reveal" :src="row.coverImageUrl" :alt="row.title">

          <div v-if="affiliations.length" class="pub-block reveal">
            <h2>{{ t('publicationDetail.affiliations') }}</h2>
            <ol class="pub-affs">
              <li v-for="(affil, idx) in affiliations" :key="idx"><sup>{{ idx + 1 }}</sup>{{ affil }}</li>
            </ol>
          </div>

          <div v-if="row.abstract" class="pub-block reveal">
            <h2>{{ t('publicationDetail.abstract') }}</h2>
            <p class="pub-abstract">{{ row.abstract }}</p>
          </div>

          <div v-if="row.keywords?.length" class="pub-block reveal">
            <h2>{{ t('publicationDetail.keywords') }}</h2>
            <ul class="pub-kw">
              <li v-for="kw in row.keywords" :key="kw">{{ kw }}</li>
            </ul>
          </div>

          <div v-if="citation" class="pub-cite reveal">
            <div class="pub-cite-top">
              <h2>{{ t('publicationDetail.howToCite') }}</h2>
              <button type="button" class="pub-copy" @click="copyCitation">
                {{ copyState === 'ok'
                  ? t('publicationDetail.copied')
                  : copyState === 'fail' ? t('publicationDetail.copyFailed') : t('publicationDetail.copyCitation') }}
              </button>
            </div>
            <p>{{ citation }}</p>
            <span class="vh" aria-live="polite">{{ copyState === 'ok' ? t('publicationDetail.copied') : '' }}</span>
          </div>

          <p v-if="row.sourceUrl || row.pdfUrl" class="pub-acts reveal">
            <a v-if="row.sourceUrl" class="btn btn-solid" :href="row.sourceUrl" target="_blank" rel="noopener noreferrer">
              {{ t('publicationDetail.readOnPublisher') }}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <path d="M7 17 17 7M8 7h9v9" />
              </svg>
              <span class="vh">{{ t('common.newWindow') }}</span>
            </a>
            <a v-if="row.pdfUrl" class="btn btn-line" :href="row.pdfUrl" target="_blank" rel="noopener noreferrer">
              {{ t('publicationDetail.downloadPdf') }}
              <span class="vh">{{ t('common.newWindow') }}</span>
            </a>
          </p>
        </article>

        <div v-else class="pub-404 reveal">
          <h1>{{ t('publicationDetail.notFound') }}</h1>
          <p>{{ t('publicationDetail.notFoundDesc') }}</p>
        </div>

        <p class="pub-back reveal">
          <NuxtLink to="/publications">&larr; {{ t('publicationDetail.back') }}</NuxtLink>
        </p>
      </div>
    </section>
  </div>
</template>

<style>
.page-pub-detail .sec{padding:clamp(32px,4.4vw,60px) 0}
.page-pub-detail .wrap{max-width:820px}
.page-pub-detail .crumb{display:flex;align-items:center;gap:9px;font-size:13.5px;color:var(--muted);margin-bottom:26px;flex-wrap:wrap}
.page-pub-detail .crumb a{color:var(--indigo-600);transition:color .2s var(--ease)}
.page-pub-detail .crumb a:hover{color:var(--cinnabar)}
.page-pub-detail .crumb .cur{color:var(--indigo-900);font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:38ch}
.page-pub-detail .pub-head{border-bottom:1px solid var(--line);padding-bottom:clamp(18px,2.4vw,26px)}
.page-pub-detail .pub-journal{display:inline-block;font-size:12px;font-weight:700;color:var(--indigo-600);background:var(--indigo-100);border-radius:999px;padding:4px 13px;margin-bottom:14px}
.page-pub-detail h1{font-size:clamp(1.5rem,3vw,2.15rem);color:var(--indigo-900);letter-spacing:-.02em;line-height:1.26;text-wrap:balance}
.page-pub-detail .pub-authors{margin-top:16px;font-size:14.5px;color:var(--ink);line-height:1.75;text-wrap:pretty}
.page-pub-detail .pub-authors sup{font-size:10.5px;color:var(--cinnabar);font-weight:700;margin-left:1px}
.page-pub-detail .pub-src{margin-top:8px;font-size:14px;color:var(--muted);font-style:italic}
.page-pub-detail .pub-doi{margin-top:10px;font-size:13px;word-break:break-all}
.page-pub-detail .pub-doi .lbl{font-weight:700;color:var(--muted);margin-right:6px;letter-spacing:.04em}
.page-pub-detail .pub-doi a{color:var(--indigo-600);text-decoration:underline;text-underline-offset:3px;transition:color .2s var(--ease)}
.page-pub-detail .pub-doi a:hover{color:var(--cinnabar)}
.page-pub-detail .pub-cover{display:block;width:100%;margin-top:clamp(22px,3vw,32px);border-radius:var(--radius-lg);border:1px solid var(--line);object-fit:cover}
.page-pub-detail .pub-block{margin-top:clamp(24px,3.2vw,34px)}
.page-pub-detail .pub-block h2{font-size:12.5px;font-weight:700;color:var(--indigo-900);text-transform:uppercase;letter-spacing:.03em;margin-bottom:12px;font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-pub-detail .pub-abstract{font-size:15.5px;line-height:1.85;color:var(--ink);white-space:pre-line;text-wrap:pretty}
.page-pub-detail .pub-affs{list-style:none;font-size:13.5px;color:var(--muted);line-height:1.7}
.page-pub-detail .pub-affs li{padding-left:2px}
.page-pub-detail .pub-affs sup{color:var(--cinnabar);font-weight:700;font-size:10.5px;margin-right:5px}
.page-pub-detail .pub-kw{list-style:none;display:flex;flex-wrap:wrap;gap:7px}
.page-pub-detail .pub-kw li{font-size:12.5px;font-weight:600;color:var(--indigo-700);background:var(--paper);border:1px solid var(--line);border-radius:999px;padding:5px 13px;line-height:1.4}
.page-pub-detail .pub-cite{margin-top:clamp(24px,3.2vw,34px);background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:clamp(16px,2.2vw,22px)}
.page-pub-detail .pub-cite-top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px}
.page-pub-detail .pub-cite h2{font-size:12.5px;font-weight:700;color:var(--indigo-900);text-transform:uppercase;letter-spacing:.03em;font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-pub-detail .pub-copy{font-family:inherit;font-size:12.5px;font-weight:700;color:var(--indigo-700);background:var(--surface);border:1.5px solid var(--line);border-radius:999px;padding:5px 14px;cursor:pointer;white-space:nowrap;transition:.2s var(--ease)}
.page-pub-detail .pub-copy:hover{border-color:var(--cinnabar);color:var(--cinnabar)}
.page-pub-detail .pub-cite p{font-size:13.5px;line-height:1.75;color:var(--ink);word-break:break-word}
.page-pub-detail .pub-acts{display:flex;flex-wrap:wrap;gap:12px;margin-top:clamp(24px,3.4vw,36px)}
.page-pub-detail .btn{display:inline-flex;align-items:center;gap:9px;padding:12px 22px;border-radius:999px;font-weight:600;font-size:14.5px;border:1.5px solid transparent;transition:.22s var(--ease)}
.page-pub-detail .btn svg{width:15px;height:15px}
.page-pub-detail .btn-solid{background:var(--indigo-700);color:#fff}
.page-pub-detail .btn-solid:hover{background:var(--indigo-800)}
.page-pub-detail .btn-line{border-color:var(--indigo-300);color:var(--indigo-700);background:var(--surface)}
.page-pub-detail .btn-line:hover{border-color:var(--cinnabar);color:var(--cinnabar);background:var(--paper)}
.page-pub-detail .pub-404{padding:clamp(40px,6vw,80px) 0;text-align:center}
.page-pub-detail .pub-404 p{margin-top:14px;color:var(--muted);font-size:14.5px}
.page-pub-detail .pub-back{margin-top:clamp(28px,4vw,44px);padding-top:clamp(18px,2.4vw,26px);border-top:1px solid var(--line);font-size:14.5px;font-weight:600}
.page-pub-detail .pub-back a{color:var(--indigo-600);transition:color .2s var(--ease)}
.page-pub-detail .pub-back a:hover{color:var(--cinnabar)}
</style>
