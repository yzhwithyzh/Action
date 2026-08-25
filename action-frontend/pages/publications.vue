<script setup lang="ts">
/**
 * 成果发表列表页。
 *
 * 数据来自 `/action/site/publications`（分页）与 `/action/site/publication-years`（年份词表）。
 * **搜索与年份筛选都走后端**：两者都映射成查询参数，由 `useSiteList` 的响应式 query
 * 触发重取 —— 前端过滤只能过滤到当前这一页，条目一多就会「搜不到明明存在的论文」。
 *
 * 分组是**渲染层**的事：接口已按「年份倒序 → 年内 sortNum」排好，这里只是在年份变化处
 * 插一个年份标题。所以一页之内可能出现两个年份段，翻页后接着往下排，这是对的 ——
 * 不这么做就得一次把所有年份全拉下来。
 *
 * 标题、作者、期刊照发表原文显示，**不走 `pick()` 双语选值**：库里就没有 `*Zh`/`*En`
 * 那两列。一篇论文的标题同时也是引用信息，翻译过去读者既检索不到也引用不了
 * （与 `pages/srd.vue` 的「原文引用」列同一个道理）。页面上的栏目标题、按钮字才是 i18n。
 *
 * 文件位置：列表页是 `pages/publications.vue`，详情页在 `pages/publication/[id].vue`
 * （单数）。同名的 `publications.vue` + `publications/` 目录并存时，前者会被 Nuxt 当成
 * 需要 `<NuxtPage>` 的父级路由，列表内容会连同详情一起渲染 —— 同 `guidelines` / `guideline`。
 */
import type { PublicationRow } from '~/composables/usePublications'

const { t } = useI18n()
const { authorLine, citeLine } = usePublications()

useHead({
  title: t('publications._title'),
  meta: [{ name: 'description', content: t('publications._desc') }],
})

interface YearRow {
  year: number | null
  count: number
}

const PAGE_SIZE = 10

const searchText = ref('')
/** 真正打进接口的那个词。输入框每敲一下就发请求太吵，隔 350ms 再同步过去 */
const keyword = ref('')
const activeYear = ref<number | null>(null)
const pageNum = ref(1)

let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(searchText, (value) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    keyword.value = value.trim()
    pageNum.value = 1
  }, 350)
})
onBeforeUnmount(() => clearTimeout(searchTimer))

const query = computed(() => ({
  pageNum: pageNum.value,
  pageSize: PAGE_SIZE,
  ...(keyword.value ? { keyword: keyword.value } : {}),
  ...(activeYear.value === null ? {} : { year: activeYear.value }),
}))

const { data: res, status, error, refresh } = await useSiteList<PublicationRow>(
  '/publications',
  query,
  'publications-page',
)
/** 年份词表跟着关键词走（不跟着已选年份走，否则选完一个年份就再也切不回别的年份） */
const { data: yearRes } = await useSiteObject<YearRow[]>('/publication-years', 'publication-years', {
  query: computed(() => (keyword.value ? { keyword: keyword.value } : {})),
})

const rows = computed<PublicationRow[]>(() => res.value?.rows ?? [])
const total = computed(() => res.value?.total ?? 0)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const isPending = computed(() => status.value === 'pending')
const hasError = computed(() => Boolean(error.value))
const years = computed<YearRow[]>(() => yearRes.value?.data ?? [])

/**
 * 在年份变化处插一个标题。接口已经排好序，这里只按相邻两行是否同年判断，
 * 不做任何重排 —— 重排会把后台定的年内顺序打乱。
 */
const grouped = computed(() => {
  const out: { year: number | null, items: PublicationRow[] }[] = []
  for (const row of rows.value) {
    const year = row.publicationYear ?? null
    const last = out[out.length - 1]
    if (last && last.year === year) last.items.push(row)
    else out.push({ year, items: [row] })
  }

  return out
})

const selectYear = (year: number | null) => {
  if (activeYear.value === year) return
  activeYear.value = year
  // 换筛选必须回第 1 页：停在第 3 页再切年份，新结果可能根本没有第 3 页
  pageNum.value = 1
}

const goPage = (p: number) => {
  const next = Math.min(Math.max(1, p), totalPages.value)
  if (next === pageNum.value) return
  pageNum.value = next
}

const pageItems = computed(() => {
  const last = totalPages.value
  const cur = pageNum.value
  const start = Math.max(1, Math.min(cur - 2, last - 4))
  const end = Math.min(last, Math.max(cur + 2, 5))

  return Array.from({ length: end - start + 1 }, (_, i) => start + i)
})

// 筛选/翻页换出来的新行由 useReveal 的 MutationObserver 自动登记，不用手动 rescan
useReveal()

watch(pageNum, async () => {
  await nextTick()
  document.getElementById('plist')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
})
</script>

<template>
  <div class="page-pubs">
    <section class="sec" id="publications">
      <div class="wrap">
        <div class="p-intro">
          <div>
            <span class="kicker reveal">{{ t('publications.kicker') }}</span>
            <h2 class="title reveal">{{ t('publications.title') }}</h2>
            <p class="reveal">{{ t('publications.intro') }}</p>
          </div>
        </div>

        <div class="pfilt reveal">
          <label class="psearch">
            <span class="vh">{{ t('publications.searchAria') }}</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
            </svg>
            <input
              v-model="searchText"
              type="search"
              :placeholder="t('publications.searchPlaceholder')"
              autocomplete="off"
            >
          </label>

          <div class="pyears" role="group" :aria-label="t('publications.yearFilterAria')">
            <button
              type="button" class="fchip"
              :class="{ on: activeYear === null }"
              :aria-pressed="activeYear === null"
              @click="selectYear(null)"
            >{{ t('publications.allYears') }}</button>
            <button
              v-for="y in years"
              :key="y.year ?? 'none'"
              type="button" class="fchip"
              :class="{ on: activeYear === y.year }"
              :aria-pressed="activeYear === y.year"
              @click="selectYear(y.year)"
            >{{ y.year ?? t('publications.noYear') }} <span class="cnt">{{ y.count }}</span></button>
          </div>

          <span v-if="!hasError && total" class="fcount">{{ t('publications.count', { n: total }) }}</span>
        </div>

        <!-- 取数失败单独成态：不能让空列表冒充「一篇都还没发表」 -->
        <div v-if="hasError" class="pstate pstate-err" role="alert">
          <p>{{ t('publications.loadError') }}</p>
          <button type="button" class="fchip" @click="refresh()">{{ t('publications.retry') }}</button>
        </div>

        <div v-else-if="!rows.length" class="pstate">
          <p>{{ isPending ? t('publications.loading') : t('publications.empty') }}</p>
          <p v-if="!isPending && (keyword || activeYear !== null)" class="phint">{{ t('publications.emptyHint') }}</p>
        </div>

        <!-- 重取期间保留旧行、只做降权，不清空：避免筛选/翻页时闪一次空框 -->
        <div v-else class="plist" id="plist" :class="{ busy: isPending }" :aria-busy="isPending">
          <section v-for="group in grouped" :key="group.year ?? 'none'" class="pgroup">
            <h3 class="pyear reveal">{{ group.year ?? t('publications.noYear') }}</h3>

            <article v-for="row in group.items" :key="row.publicationId" class="prow reveal">
              <h4>
                <NuxtLink :to="`/publication/${row.publicationId}`">{{ row.title }}</NuxtLink>
              </h4>
              <p v-if="row.authors?.length" class="pauthors">{{ authorLine(row.authors) }}</p>
              <p v-if="citeLine(row)" class="pcite">{{ citeLine(row) }}</p>

              <ul v-if="row.keywords?.length" class="pkw">
                <li v-for="kw in row.keywords.slice(0, 6)" :key="kw">{{ kw }}</li>
              </ul>

              <div class="pmeta">
                <a
                  v-if="row.doi"
                  class="pdoi"
                  :href="`https://doi.org/${row.doi}`"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <span class="lbl">DOI</span>{{ row.doi }}
                  <span class="vh">{{ t('common.newWindow') }}</span>
                </a>
                <NuxtLink class="pgo" :to="`/publication/${row.publicationId}`">
                  {{ t('publications.viewDetail') }}
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                    <path d="M5 12h14M13 6l6 6-6 6" />
                  </svg>
                </NuxtLink>
              </div>
            </article>
          </section>
        </div>

        <nav v-if="!hasError && totalPages > 1" class="pager" :aria-label="t('publications.pagerAria')">
          <button type="button" class="pbtn" :disabled="pageNum <= 1" @click="goPage(pageNum - 1)">
            {{ t('publications.prevPage') }}
          </button>
          <button
            v-for="p in pageItems"
            :key="p"
            type="button"
            class="pbtn pnum"
            :class="{ on: p === pageNum }"
            :aria-current="p === pageNum ? 'page' : undefined"
            @click="goPage(p)"
          >{{ p }}</button>
          <button type="button" class="pbtn" :disabled="pageNum >= totalPages" @click="goPage(pageNum + 1)">
            {{ t('publications.nextPage') }}
          </button>
          <span class="vh" aria-live="polite">{{ t('publications.pageOf', { cur: pageNum, all: totalPages }) }}</span>
        </nav>
      </div>
    </section>
  </div>
</template>

<style>
.page-pubs .sec{padding:clamp(40px,5vw,68px) 0;scroll-margin-top:130px}
.page-pubs .p-intro{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;flex-wrap:wrap;margin-bottom:clamp(22px,3vw,30px)}
.page-pubs h2.title{font-size:clamp(1.5rem,2.8vw,2.1rem);color:var(--indigo-900);letter-spacing:-.02em;line-height:1.2}
.page-pubs .p-intro p{font-size:14px;color:var(--muted);max-width:62ch;margin-top:8px;line-height:1.6}
.page-pubs .pfilt{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin-bottom:clamp(20px,3vw,28px)}
.page-pubs .psearch{position:relative;display:flex;align-items:center;flex:1 1 280px;max-width:420px}
.page-pubs .psearch svg{position:absolute;left:14px;width:17px;height:17px;color:var(--indigo-300);pointer-events:none}
.page-pubs .psearch input{font-family:inherit;width:100%;font-size:14px;color:var(--ink);background:var(--surface);border:1.5px solid var(--line);border-radius:999px;padding:10px 16px 10px 40px;transition:.2s var(--ease)}
.page-pubs .psearch input::placeholder{color:var(--muted)}
.page-pubs .psearch input:focus{outline:none;border-color:var(--indigo-300);box-shadow:0 0 0 3px var(--indigo-100)}
.page-pubs .pyears{display:flex;flex-wrap:wrap;gap:8px}
.page-pubs .fchip{font-family:inherit;font-size:13.5px;font-weight:600;color:var(--indigo-700);background:var(--surface);border:1.5px solid var(--line);padding:8px 15px;border-radius:999px;cursor:pointer;transition:.2s var(--ease);font-variant-numeric:tabular-nums}
.page-pubs .fchip:hover{border-color:var(--indigo-300);background:var(--indigo-100)}
.page-pubs .fchip.on{background:var(--indigo-700);border-color:var(--indigo-700);color:#fff}
.page-pubs .fchip .cnt{font-size:11.5px;font-weight:700;opacity:.62;margin-left:3px}
.page-pubs .fcount{margin-left:auto;font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums}
.page-pubs .pstate{border:1px solid var(--line);border-radius:var(--radius-lg);background:var(--surface);padding:clamp(32px,5vw,56px) 24px;text-align:center;color:var(--muted);font-size:14.5px}
.page-pubs .pstate-err{color:var(--cinnabar-d)}
.page-pubs .pstate .fchip{margin-top:16px}
.page-pubs .pstate .phint{margin-top:8px;font-size:13.5px}
.page-pubs .plist.busy{opacity:.55;transition:opacity .18s var(--ease);pointer-events:none}
.page-pubs #plist{scroll-margin-top:120px}
.page-pubs .pgroup+.pgroup{margin-top:clamp(26px,3.4vw,40px)}
.page-pubs .pyear{display:inline-block;font-family:"Spectral",serif;font-size:clamp(1.3rem,2.2vw,1.7rem);font-weight:700;color:var(--indigo-900);letter-spacing:-.01em;padding-bottom:6px;border-bottom:2px solid var(--cinnabar);margin-bottom:clamp(14px,2vw,20px);font-variant-numeric:tabular-nums}
.page-pubs .prow{padding:clamp(16px,2vw,22px) 0;border-top:1px solid var(--line)}
.page-pubs .prow:first-of-type{border-top:0;padding-top:0}
.page-pubs .prow h4{font-size:clamp(1.04rem,1.6vw,1.2rem);line-height:1.4;color:var(--indigo-900);text-wrap:pretty}
.page-pubs .prow h4 a{color:inherit;transition:color .2s var(--ease)}
.page-pubs .prow h4 a:hover{color:var(--cinnabar)}
.page-pubs .pauthors{margin-top:7px;font-size:13.5px;color:var(--ink);line-height:1.6}
.page-pubs .pcite{margin-top:4px;font-size:13.5px;color:var(--muted);font-style:italic;line-height:1.6}
.page-pubs .pkw{list-style:none;display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.page-pubs .pkw li{font-size:11.5px;font-weight:600;color:var(--indigo-700);background:var(--indigo-100);border-radius:999px;padding:3px 10px;line-height:1.5}
.page-pubs .pmeta{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-top:12px}
.page-pubs .pdoi{font-size:12.5px;color:var(--indigo-600);word-break:break-all;transition:color .2s var(--ease)}
.page-pubs .pdoi:hover{color:var(--cinnabar)}
.page-pubs .pdoi .lbl{font-weight:700;color:var(--muted);margin-right:6px;letter-spacing:.04em}
.page-pubs .pgo{margin-left:auto;display:inline-flex;align-items:center;gap:6px;font-size:13.5px;font-weight:600;color:var(--indigo-700);transition:color .2s var(--ease)}
.page-pubs .pgo svg{width:15px;height:15px;transition:transform .25s var(--ease)}
.page-pubs .pgo:hover{color:var(--cinnabar)}
.page-pubs .pgo:hover svg{transform:translateX(3px)}
.page-pubs .pager{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:clamp(20px,3vw,28px);justify-content:center}
.page-pubs .pbtn{font-family:inherit;font-size:13.5px;font-weight:600;color:var(--indigo-700);background:var(--surface);border:1.5px solid var(--line);padding:8px 15px;border-radius:999px;cursor:pointer;transition:.2s var(--ease)}
.page-pubs .pbtn:hover:not(:disabled){border-color:var(--indigo-300);background:var(--indigo-100)}
.page-pubs .pbtn:disabled{opacity:.4;cursor:default}
.page-pubs .pbtn.pnum{min-width:38px;padding:8px 10px;font-variant-numeric:tabular-nums}
.page-pubs .pbtn.on{background:var(--indigo-700);border-color:var(--indigo-700);color:#fff}
@media(max-width:640px){
.page-pubs .fcount{margin-left:0}
.page-pubs .pgo{margin-left:0}
}
</style>
