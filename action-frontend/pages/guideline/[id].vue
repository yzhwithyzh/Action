<script setup lang="ts">
/**
 * 报告规范原文阅读页 —— 一份规范一页，中英文 PDF 直接内嵌预览。
 *
 * 取代了 `pages/guidelines.vue` 里原第②段「在线预览与下载」的折叠列表：那一段把六份规范
 * 挤在一屏里，展开后也只有两个下载按钮，「预览」名不副实。现在从分类导航的卡片点进来，
 * 落地即原文。
 *
 * 路由放在 `/guideline/[id]`（单数）而不是 `/guidelines/[id]`：`pages/guidelines.vue`
 * 已存在，再建 `pages/guidelines/` 目录会让它变成需要 `<NuxtPage>` 的父级路由，
 * 把现有页面拆散 —— 与 `pages/team/[id].vue` 避开 `pages/about.vue` 是同一回事。
 *
 * PDF 用 `<iframe>` 交给浏览器自带阅读器渲染，不引 pdf.js。但 **iframe 的地址是后端的
 * `/action/site/guidelines/{id}/file`，不是 OSS 直链**：阿里云对默认域名
 * `*.oss-cn-*.aliyuncs.com` 下的所有对象强制加 `Content-Disposition: attachment`
 * （`x-oss-force-download: true`）。`<img>` 不看这个头，所以站上的图片一直是好的；
 * iframe 看，于是直连 OSS 的结果是「点开就下载、预览区一片空白」。
 * 下载按钮反而要用 OSS 直链 —— 那个场景要的正是 attachment。
 *
 * iOS Safari 对 iframe 内的 PDF 只显示首页，所以「在新窗口打开」按钮始终在场，
 * 不是可选装饰。
 */
const route = useRoute()
const { t } = useI18n()
const { pick, isEn } = useBilingual()

const id = computed(() => String(route.params.id ?? ''))

const { data: res } = await useSiteObject<GuidelineRow>(
  `/guidelines/${id.value}`,
  `guideline:${id.value}`,
)
const row = computed<GuidelineRow | null>(() => res.value?.data ?? null)

const { data: catRes } = await useSiteObject<GuidelineCategoryRow[]>(
  '/guideline-categories',
  'guideline-cats',
)
/** 分类只为取「研究设计」标签与图标；分类被停用/删除时留空，不回填 studyType 原值（那是内部标识） */
const cat = computed<GuidelineCategoryRow | undefined>(() =>
  (catRes.value?.data ?? []).find((c) => c.catKey === row.value?.studyType))
const catLabel = computed(() => pick(cat.value, 'name'))
const icons = computed(() => categoryIconPaths(cat.value))

const name = computed(() => pick(row.value, 'name'))
const summary = computed(() => pick(row.value, 'summary'))
const version = computed(() => pick(row.value, 'version'))

/** 可选的原文版本，顺序即按钮顺序 */
const docs = computed(() => {
  const out: { key: 'zh' | 'en'; url: string; label: string }[] = []
  if (row.value?.fileUrlZh) out.push({ key: 'zh', url: row.value.fileUrlZh, label: t('guidelineDetail.langZh') })
  if (row.value?.fileUrlEn) out.push({ key: 'en', url: row.value.fileUrlEn, label: t('guidelineDetail.langEn') })

  return out
})

const siteUrl = useSiteUrl()

/** 用户点过的版本。null 表示还没点过，由界面语言决定看哪一版 */
const picked = ref<'zh' | 'en' | null>(null)
const activeDoc = computed(() => {
  if (!docs.value.length) return null

  return docs.value.find((d) => d.key === picked.value)
    ?? docs.value.find((d) => d.key === (isEn.value ? 'en' : 'zh'))
    ?? docs.value[0]
})

/** 预览地址：走后端转发（inline），不是 OSS 直链（attachment，见文件头注释） */
const viewUrl = computed(() =>
  (activeDoc.value ? siteUrl(`/guidelines/${id.value}/file?lang=${activeDoc.value.key}`) : ''))

useHead({
  title: computed(() => (row.value ? `${row.value.code} | ACTION` : t('guidelineDetail.notFound'))),
  meta: [{ name: 'description', content: computed(() => summary.value || t('guidelines._desc')) }],
})

useReveal()
</script>

<template>
  <div class="page-guideline-pdf">
    <section class="sec">
      <div class="wrap">
        <nav class="crumb" :aria-label="t('guidelineDetail.crumbAria')">
          <NuxtLink to="/">{{ t('about.hero.crumbHome') }}</NuxtLink>
          <span aria-hidden="true">/</span>
          <NuxtLink to="/guidelines">{{ t('guidelineDetail.crumbList') }}</NuxtLink>
          <span aria-hidden="true">/</span>
          <span class="cur">{{ row?.code || t('guidelineDetail.notFound') }}</span>
        </nav>

        <article v-if="row">
          <header class="gd-head reveal">
            <span v-if="icons.length" class="gd-ic" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                <path v-for="(d, k) in icons" :key="k" :d="d" />
              </svg>
            </span>
            <div class="gd-id">
              <span v-if="catLabel" class="gd-type">{{ catLabel }}</span>
              <h1>{{ row.code }}</h1>
              <p v-if="name" class="gd-name">{{ name }}</p>
              <p v-if="version" class="gd-ver">{{ version }}</p>
            </div>
          </header>

          <p v-if="summary" class="gd-lead reveal">{{ summary }}</p>

          <!-- 里面两块都可能没有（只有一种语言、又没填出处，眼下 6 份规范全是这种），
               整条不判空就只剩一根 border-bottom 横在页面上 -->
          <div v-if="docs.length > 1 || row.externalUrl" class="gd-bar reveal">
            <!-- 两版都有才给切换：只有一版时这排按钮只会让人以为另一版没加载出来 -->
            <div v-if="docs.length > 1" class="gd-langs" role="group" :aria-label="t('guidelineDetail.langAria')">
              <button
                v-for="d in docs"
                :key="d.key"
                class="gd-lang"
                :class="{ on: activeDoc?.key === d.key }"
                :aria-pressed="activeDoc?.key === d.key"
                @click="picked = d.key"
              >
                {{ d.label }}
              </button>
            </div>

            <!-- 「在新窗口打开 / 下载」两个按钮已去掉：浏览器自带的 PDF 阅读器工具条上本来就有
                 下载与打印，摆在外面是同一件事说两遍。移动端的兜底改挂在预览区下面那句提示里 -->
            <div v-if="row.externalUrl" class="gd-acts">
              <a class="gd-btn src" :href="row.externalUrl" target="_blank" rel="noopener noreferrer">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 5h11a2 2 0 0 1 2 2v13H6a2 2 0 0 1-2-2z" /><path d="M8 9h6M8 13h6" /></svg>
                <span>{{ t('guidelineDetail.source') }}</span>
                <span class="ext">{{ t('common.newWindow') }}</span>
              </a>
            </div>
          </div>

          <div v-if="activeDoc" class="gd-viewer reveal">
            <!-- :key 绑到 url：中英文切换时换的是同一个 iframe 的 src，
                 不换 key 部分浏览器会沿用已渲染的旧文档 -->
            <iframe
              :key="viewUrl"
              :src="viewUrl"
              :title="`${row.code} ${activeDoc.label}`"
              loading="lazy"
            />
          </div>
          <div v-else class="gd-empty reveal">
            <h2>{{ t('guidelineDetail.noFile') }}</h2>
            <p>{{ t('guidelineDetail.noFileDesc') }}</p>
            <p v-if="row.externalUrl">
              <a :href="row.externalUrl" target="_blank" rel="noopener noreferrer">
                {{ t('guidelineDetail.source') }}
                <span class="vh">{{ t('common.newWindow') }}</span>
              </a>
            </p>
          </div>

          <!-- iOS Safari 在 iframe 里只渲染 PDF 首页，这条不是客套话，是那种设备上唯一的出路 -->
          <i18n-t v-if="activeDoc" keypath="guidelineDetail.viewerNote" tag="p" class="gd-note reveal">
            <a :href="viewUrl" target="_blank" rel="noopener noreferrer">{{ t('guidelineDetail.openNewTab') }}</a>
          </i18n-t>
        </article>

        <div v-else class="gd-404 reveal">
          <h1>{{ t('guidelineDetail.notFound') }}</h1>
          <p>{{ t('guidelineDetail.notFoundDesc') }}</p>
        </div>

        <p class="gd-back reveal">
          <NuxtLink to="/guidelines">&larr; {{ t('guidelineDetail.back') }}</NuxtLink>
        </p>
      </div>
    </section>
  </div>
</template>

<style>
.page-guideline-pdf .sec{padding:clamp(28px,3.6vw,48px) 0}
.page-guideline-pdf .wrap{max-width:1100px}
.page-guideline-pdf .crumb{display:flex;align-items:center;gap:9px;font-size:13.5px;color:var(--muted);margin-bottom:18px;flex-wrap:wrap}
.page-guideline-pdf .crumb a{color:var(--indigo-600);transition:color .2s var(--ease)}
.page-guideline-pdf .crumb a:hover{color:var(--cinnabar)}
.page-guideline-pdf .crumb .cur{color:var(--indigo-900);font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:38ch}
.page-guideline-pdf .gd-head{display:flex;gap:clamp(14px,2vw,20px);align-items:flex-start}
.page-guideline-pdf .gd-ic{width:56px;height:56px;flex-shrink:0;border-radius:14px;background:var(--indigo-100);color:var(--indigo-600);
    display:flex;align-items:center;justify-content:center}
.page-guideline-pdf .gd-ic svg{width:30px;height:30px}
.page-guideline-pdf .gd-id{min-width:0}
.page-guideline-pdf .gd-type{display:inline-block;font-size:12px;font-weight:700;color:var(--indigo-600);background:var(--indigo-100);
    border-radius:999px;padding:3px 12px}
.page-guideline-pdf h1{margin-top:8px;font-family:"Spectral","Noto Serif SC",serif;font-size:clamp(1.5rem,2.8vw,2rem);
    font-weight:700;color:var(--indigo-900);letter-spacing:-.02em;line-height:1.16}
.page-guideline-pdf .gd-name{margin-top:6px;font-size:15px;color:var(--ink);line-height:1.5;text-wrap:pretty}
.page-guideline-pdf .gd-ver{margin-top:8px;display:inline-block;font-size:12px;font-weight:700;color:var(--indigo-600);
    background:var(--indigo-100);padding:4px 12px;border-radius:999px}
.page-guideline-pdf .gd-lead{margin-top:16px;font-size:14.5px;color:var(--muted);line-height:1.72;max-width:78ch;text-wrap:pretty}
.page-guideline-pdf .gd-bar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:14px;
    margin-top:16px;padding-bottom:12px;border-bottom:1px solid var(--line)}
.page-guideline-pdf .gd-langs{display:inline-flex;gap:4px;padding:4px;background:var(--paper-2);border:1px solid var(--line);border-radius:999px}
.page-guideline-pdf .gd-lang{font-size:13.5px;font-weight:600;color:var(--indigo-700);background:transparent;border:0;
    padding:7px 16px;border-radius:999px;cursor:pointer;transition:.2s var(--ease)}
.page-guideline-pdf .gd-lang:hover{color:var(--indigo-900)}
.page-guideline-pdf .gd-lang.on{background:var(--indigo-700);color:#fff}
.page-guideline-pdf .gd-acts{display:flex;flex-wrap:wrap;gap:9px}
.page-guideline-pdf .gd-btn{display:inline-flex;align-items:center;gap:9px;padding:10px 16px;border-radius:11px;
    border:1.5px solid var(--line);background:var(--surface);font-size:14px;font-weight:600;color:var(--indigo-800);
    transition:.2s var(--ease)}
.page-guideline-pdf .gd-btn:hover{border-color:var(--indigo-300);background:var(--indigo-100)}
.page-guideline-pdf .gd-btn svg{width:18px;height:18px;flex-shrink:0;color:var(--indigo-500)}
.page-guideline-pdf .gd-btn .ext{font-size:11px;font-weight:700;color:var(--muted);letter-spacing:.04em}
.page-guideline-pdf .gd-btn.src{border-color:var(--indigo-200);background:var(--indigo-100)}
.page-guideline-pdf .gd-btn.src svg{color:var(--cinnabar)}
.page-guideline-pdf .gd-viewer{margin-top:18px;border:1px solid var(--line);border-radius:var(--radius-lg);
    overflow:hidden;background:var(--paper-2);box-shadow:var(--shadow-sm)}
/* 阅读框自己有滚动条：鼠标停在上面时滚轮归 PDF 阅读器，页面滚动要把指针挪到两侧留白，
   或直接用页面滚动条 —— 内嵌 PDF 都是这个脾气，高度别再往上加 */
.page-guideline-pdf .gd-viewer iframe{display:block;width:100%;height:min(78vh,1100px);min-height:480px;border:0;background:var(--paper-2)}
.page-guideline-pdf .gd-note{margin-top:10px;font-size:12.5px;color:var(--muted);line-height:1.6}
.page-guideline-pdf .gd-note a{color:var(--indigo-600);font-weight:600;text-decoration:underline;text-underline-offset:3px}
.page-guideline-pdf .gd-note a:hover{color:var(--cinnabar)}
.page-guideline-pdf .gd-empty{margin-top:clamp(18px,2.4vw,24px);padding:clamp(30px,5vw,56px) 24px;text-align:center;
    background:var(--paper);border:1px dashed var(--line);border-radius:var(--radius-lg)}
.page-guideline-pdf .gd-empty h2{font-size:1.05rem;color:var(--indigo-900)}
.page-guideline-pdf .gd-empty p{margin-top:10px;font-size:14px;color:var(--muted);line-height:1.6}
.page-guideline-pdf .gd-empty a{color:var(--indigo-600);font-weight:600;text-decoration:underline;text-underline-offset:3px}
.page-guideline-pdf .gd-404{padding:clamp(40px,6vw,80px) 0;text-align:center}
.page-guideline-pdf .gd-404 p{margin-top:14px;color:var(--muted);font-size:14.5px}
.page-guideline-pdf .gd-back{margin-top:clamp(24px,3.4vw,38px);padding-top:clamp(16px,2.2vw,24px);border-top:1px solid var(--line);
    font-size:14.5px;font-weight:600}
.page-guideline-pdf .gd-back a{color:var(--indigo-600);transition:color .2s var(--ease)}
.page-guideline-pdf .gd-back a:hover{color:var(--cinnabar)}
@media(max-width:640px){
.page-guideline-pdf .gd-head{gap:12px}
.page-guideline-pdf .gd-ic{width:44px;height:44px}
.page-guideline-pdf .gd-ic svg{width:24px;height:24px}
.page-guideline-pdf .gd-viewer iframe{height:68vh;min-height:380px}
}
</style>
