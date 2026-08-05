<script setup lang="ts">
/**
 * 团队成员详情页。
 *
 * 从「关于我们 → 如何组织」的名单卡片点进来 —— docx 更新版给每位成员补了
 * 数百字履历，全塞进卡片会把名单撑成一堵墙，故拆成独立页承载完整内容。
 *
 * 路由放在 `/team/[id]` 而不是 `/about/team/[id]`：`pages/about.vue` 已存在，
 * 再建 `pages/about/` 目录会让它变成需要 `<NuxtPage>` 的父级路由，把现有页面拆散。
 *
 * 数据取 `/action/site/team-members/{id}`，该接口只返回未删除的成员；
 * 已停用（status='1'）的成员仍可按 id 直达，但不会出现在名单里。
 */
const route = useRoute()
const { t } = useI18n()
const { pick } = useBilingual()

const id = computed(() => String(route.params.id ?? ''))

// swr：详情页是否被预渲染取决于构建时 /about 有没有爬到它，取不到时得靠客户端补
const { data: res } = await useSiteObject<TeamMemberRow>(
  `/team-members/${id.value}`,
  `team-member:${id.value}`,
  { swr: true },
)
const row = computed<TeamMemberRow | null>(() => res.value?.data ?? null)

const name = computed(() => pick(row.value, 'name'))
const fullName = computed(() => displayName(row.value?.honorific ?? null, name.value))
const summary = computed(() => pick(row.value, 'summary'))
/** 履历缺失时退到一句话简介 —— 后台新增成员可能只填了 summary */
const bio = computed(() => pick(row.value, 'bio') || summary.value)
const contribution = computed(() => pick(row.value, 'contribution'))
const tags = computed(() => splitExpertise(pick(row.value, 'expertise')))

const groupLabel = computed(() => (row.value ? t(`team.groups.${row.value.groupKey}`) : ''))

/** 姓名首字母，头像缺失时占位（与名单卡片一致） */
const initials = computed(() => {
  const parts = (row.value?.nameEn || row.value?.nameZh || '').split(/[\s-]+/).filter(Boolean)

  return parts.slice(0, 2).map((p) => p[0]?.toUpperCase() ?? '').join('')
})

useHead({
  title: computed(() => (name.value ? `${fullName.value} | ACTION` : t('team.notFound'))),
  meta: [{ name: 'description', content: computed(() => summary.value || t('team._desc')) }],
})

useReveal()
</script>

<template>
  <div class="page-team-detail">
    <section class="sec">
      <div class="wrap">
        <nav class="crumb" :aria-label="t('about.hero.crumbAria')">
          <NuxtLink to="/">{{ t('about.hero.crumbHome') }}</NuxtLink>
          <span aria-hidden="true">/</span>
          <NuxtLink to="/about#about">{{ t('about.hero.crumbCurrent') }}</NuxtLink>
          <span aria-hidden="true">/</span>
          <span class="cur">{{ name || t('team.notFound') }}</span>
        </nav>

        <article v-if="row" class="prof">
          <header class="prof-head reveal">
            <img
              v-if="row.avatarUrl"
              class="prof-av"
              :src="row.avatarUrl"
              :alt="fullName"
              width="180"
              height="228"
            >
            <span v-else class="prof-av prof-av-txt" aria-hidden="true">{{ initials }}</span>

            <div class="prof-id">
              <span class="prof-grp">{{ groupLabel }}</span>
              <h1>{{ fullName }}</h1>
              <p v-if="pick(row, 'title')" class="prof-title">{{ pick(row, 'title') }}</p>
              <p v-if="pick(row, 'affiliation')" class="prof-aff">{{ pick(row, 'affiliation') }}</p>
              <p v-if="pick(row, 'role')" class="prof-role">
                <span class="lbl">{{ t('team.roleLabel') }}</span>{{ pick(row, 'role') }}
              </p>

              <ul v-if="tags.length" class="prof-tags" :aria-label="t('team.expertise')">
                <li v-for="tag in tags" :key="tag">{{ tag }}</li>
              </ul>

              <p v-if="row.homepageUrl || row.email" class="prof-links">
                <a v-if="row.homepageUrl" :href="row.homepageUrl" target="_blank" rel="noopener noreferrer">
                  {{ t('team.homepage') }}
                  <span class="vh">{{ t('common.newWindow') }}</span>
                </a>
                <a v-if="row.email" :href="`mailto:${row.email}`">{{ t('team.email') }}</a>
              </p>
            </div>
          </header>

          <div v-if="bio" class="prof-block reveal">
            <h2>{{ t('team.bio') }}</h2>
            <p>{{ bio }}</p>
          </div>

          <div v-if="contribution" class="prof-block prof-contrib reveal">
            <h2>{{ t('team.contribution') }}</h2>
            <p>{{ contribution }}</p>
          </div>
        </article>

        <div v-else class="prof-404 reveal">
          <h1>{{ t('team.notFound') }}</h1>
          <p>{{ t('team.notFoundDesc') }}</p>
        </div>

        <p class="prof-back reveal">
          <NuxtLink to="/about#about">&larr; {{ t('team.back') }}</NuxtLink>
        </p>
      </div>
    </section>
  </div>
</template>

<style>
.page-team-detail .sec{padding:clamp(32px,4.4vw,60px) 0}
.page-team-detail .wrap{max-width:820px}
.page-team-detail .crumb{display:flex;align-items:center;gap:9px;font-size:13.5px;color:var(--muted);margin-bottom:26px;flex-wrap:wrap}
.page-team-detail .crumb a{color:var(--indigo-600);transition:color .2s var(--ease)}
.page-team-detail .crumb a:hover{color:var(--cinnabar)}
.page-team-detail .crumb .cur{color:var(--indigo-900);font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:38ch}
.page-team-detail .prof-head{display:flex;gap:clamp(20px,3vw,32px);align-items:flex-start;border-bottom:1px solid var(--line);padding-bottom:clamp(20px,2.8vw,30px)}
.page-team-detail .prof-av{width:180px;height:228px;flex-shrink:0;border-radius:var(--radius-lg);object-fit:cover;object-position:center top;background:var(--indigo-100);border:1px solid var(--line)}
.page-team-detail .prof-av-txt{display:flex;align-items:center;justify-content:center;background:var(--indigo-700);color:#fff;font-family:"Spectral",serif;font-weight:700;font-size:52px;border-color:transparent}
.page-team-detail .prof-id{min-width:0}
.page-team-detail .prof-grp{display:inline-block;font-size:12px;font-weight:700;color:var(--indigo-600);background:var(--indigo-100);border-radius:999px;padding:3px 12px}
.page-team-detail h1{margin-top:12px;font-size:clamp(1.5rem,3vw,2.1rem);color:var(--indigo-900);letter-spacing:-.02em;line-height:1.24;text-wrap:balance}
.page-team-detail .prof-title{margin-top:8px;font-size:14.5px;font-weight:600;color:var(--indigo-800)}
.page-team-detail .prof-aff{margin-top:4px;font-size:14px;color:var(--indigo-600);font-weight:600;line-height:1.5;text-wrap:pretty}
.page-team-detail .prof-role{margin-top:8px;font-size:13.5px;color:var(--indigo-800);line-height:1.5}
.page-team-detail .prof-role .lbl{color:var(--muted);margin-right:5px}
.page-team-detail .prof-tags{list-style:none;display:flex;flex-wrap:wrap;gap:7px;margin-top:14px}
.page-team-detail .prof-tags li{font-size:12px;color:var(--indigo-700);background:var(--paper);border:1px solid var(--line);border-radius:999px;padding:4px 11px;line-height:1.4}
.page-team-detail .prof-links{display:flex;gap:16px;flex-wrap:wrap;margin-top:16px;font-size:13.5px;font-weight:600}
.page-team-detail .prof-links a{color:var(--indigo-600);text-decoration:underline;text-underline-offset:3px;transition:color .2s var(--ease)}
.page-team-detail .prof-links a:hover{color:var(--cinnabar)}
.page-team-detail .prof-block{margin-top:clamp(24px,3.2vw,34px)}
.page-team-detail .prof-block h2{font-size:12.5px;font-weight:700;color:var(--indigo-900);text-transform:uppercase;letter-spacing:.03em;margin-bottom:12px;font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-team-detail .prof-block p{font-size:15.5px;line-height:1.85;color:var(--ink);text-wrap:pretty}
.page-team-detail .prof-contrib{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:clamp(18px,2.4vw,24px)}
.page-team-detail .prof-contrib h2{display:flex;align-items:center;gap:8px;color:var(--cinnabar-d)}
.page-team-detail .prof-contrib h2::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--cinnabar)}
.page-team-detail .prof-404{padding:clamp(40px,6vw,80px) 0;text-align:center}
.page-team-detail .prof-404 p{margin-top:14px;color:var(--muted);font-size:14.5px}
.page-team-detail .prof-back{margin-top:clamp(28px,4vw,44px);padding-top:clamp(18px,2.4vw,26px);border-top:1px solid var(--line);font-size:14.5px;font-weight:600}
.page-team-detail .prof-back a{color:var(--indigo-600);transition:color .2s var(--ease)}
.page-team-detail .prof-back a:hover{color:var(--cinnabar)}
@media(max-width:640px){
.page-team-detail .prof-head{flex-direction:column}
.page-team-detail .prof-av{width:140px;height:178px}
}
</style>
