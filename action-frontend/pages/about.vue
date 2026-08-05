<script setup lang="ts">
/**
 * about.html 迁移而来。
 * 模板与样式基本保持原状；样式已加 .page-about 命名空间，避免 SPA 路由切换时跨页污染。
 *
 * 例外是「如何组织」里的团队名单：原来是写死在 i18n 里的两组纯文字卡片，
 * 现改为读 `action_team_member` 表（带头像、按人跳 /team/[id] 详情页），
 * 对应的 about.s016–s027 / s029–s036 文案键已随之删除。
 */
const { t } = useI18n()
const { pick } = useBilingual()

useHead({
  title: t('about._title'),
  meta: [{ name: 'description', content: t('about._desc') }],
})

useReveal()

/**
 * 团队名单改为从 `action_team_member` 表取，后台「团队成员管理」页可增删改。
 * swr：名单是后台可随时改的内容，不开这个开关就要等下一次 `npm run generate` 才生效。
 */
const { data: teamRes } = await useSiteObject<TeamMemberRow[]>('/team-members', 'site-team-members', { swr: true })
const members = computed<TeamMemberRow[]>(() => teamRes.value?.data ?? [])

/**
 * 接口已按「组 → 组内顺序」排好，这里只做分段，不再排序。
 * 组标题沿用原有的 s015/s028 两条文案，引导语取自 docx 更新版。
 */
const groups = computed(() => [
  {
    key: 'board' as const,
    title: t('about.s015'),
    intro: t('about.team.boardIntro'),
    rows: members.value.filter((m) => m.groupKey === 'board'),
  },
  {
    key: 'core' as const,
    title: t('about.s028'),
    intro: t('about.team.coreIntro'),
    rows: members.value.filter((m) => m.groupKey === 'core'),
  },
])

/** 头像缺失时退回姓名首字母 —— 与迁移前的纯文字圆头像一致 */
function initials(row: TeamMemberRow): string {
  const parts = (row.nameEn || row.nameZh || '').split(/[\s-]+/).filter(Boolean)

  return parts.slice(0, 2).map((p) => p[0]?.toUpperCase() ?? '').join('')
}

/** 卡片副行：机构优先，没有机构（部分执行团队成员未给）时退到职称 */
function subline(row: TeamMemberRow): string {
  return pick(row, 'affiliation') || pick(row, 'title')
}

/**
 * 子栏目 Tab —— 迁移自 about.html 内联脚本。
 * 五段内容同时在 DOM 里，只显示当前一段；顺序即子导航顺序。
 */
const TABS = ['about', 'mission', 'support', 'contact', 'legal'] as const
type Tab = (typeof TABS)[number]

const isTab = (v: string): v is Tab => (TABS as readonly string[]).includes(v)

/** SSR 预渲染时固定输出第一段，与原站首屏一致；带 hash 进来的情况在 onMounted 里纠正 */
const activeTab = ref<Tab>('about')

/**
 * 切过来的这段是从 display:none 变可见的，IntersectionObserver 虽然也会补触发，
 * 但那样内容会先空一帧再淡入。原站是直接落位，这里保持同样的即时感。
 */
function revealNow(id: Tab) {
  for (const el of document.getElementById(id)?.querySelectorAll('.reveal') ?? [])
    el.classList.add('is-visible')
}

function goTab(id: Tab) {
  activeTab.value = id
  // 不走 router.replace：no_prefix 策略下 Nuxt 的 scrollBehavior 会按 hash 再跳一次，
  // 与下面的 scrollIntoView 打架。原生 replaceState 保留 history.state，路由状态不丢。
  window.history.replaceState(window.history.state, '', `#${id}`)
  nextTick(() => {
    revealNow(id)
    document.getElementById('about-subnav')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

onMounted(() => {
  const hash = window.location.hash.slice(1)
  if (!isTab(hash) || hash === activeTab.value) return
  // 深链进来只切换、不滚动 —— 子导航本身已在首屏
  activeTab.value = hash
  nextTick(() => revealNow(hash))
})
</script>

<template>
  <div class="page-about">
    <section class="phero">
      <img class="phero-bg" src="/assets/hero-about.png" alt="" aria-hidden="true" width="1600" height="900">
      <div class="wrap">
        <nav class="crumb reveal" :aria-label="t('about.hero.crumbAria')">
          <NuxtLink to="/">{{ t('about.hero.crumbHome') }}</NuxtLink>
          <span class="sep" aria-hidden="true">/</span>
          <b>{{ t('about.hero.crumbCurrent') }}</b>
        </nav>
        <span class="phero-tag reveal"><span class="dot" aria-hidden="true"></span><span>{{ t('about.hero.tag') }}</span></span>
        <h1 class="reveal" v-html="t('about.hero.title')"></h1>
        <p class="psub reveal">{{ t('about.hero.sub') }}</p>
      </div>
    </section>

    <nav class="subnav" id="about-subnav" :aria-label="t('about.tabsAria')">
      <div class="wrap subnav-in">
        <a
          v-for="tab in TABS"
          :key="tab"
          :href="`#${tab}`"
          :class="{ active: activeTab === tab }"
          :aria-current="activeTab === tab ? 'true' : undefined"
          @click.prevent="goTab(tab)"
        >{{ t(`about.tabs.${tab}`) }}</a>
      </div>
    </nav>

    <!-- ===================== ① 关于我们 ===================== -->
    <section class="sec" id="about" :class="{ 'is-hidden': activeTab !== 'about' }">
      <div class="wrap">
        <div class="p-intro">
          <span class="kicker reveal">{{ t('about.s001') }}</span>
          <h2 class="reveal">{{ t('about.s002') }}</h2>
          <p class="lead reveal">{{ t('about.s003') }}</p>
        </div>

        <div class="subh reveal">{{ t('about.s004') }}</div>
        <div class="pillars">
          <div class="pillar reveal"><span class="pi" aria-hidden="true"><svg viewbox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4" /><path d="M10 13h4M10 16h4" /></svg></span><b>{{ t('about.s005') }}</b><p>{{ t('about.s006') }}</p></div>
          <div class="pillar reveal"><span class="pi" aria-hidden="true"><svg viewbox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="4" y="4" width="16" height="14" rx="2" /><path d="M4 9h16M9 18v3M15 18v3M7 21h10" /></svg></span><b>{{ t('about.s007') }}</b><p>{{ t('about.s008') }}</p></div>
          <div class="pillar reveal"><span class="pi" aria-hidden="true"><svg viewbox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 4 2 9l10 5 10-5-10-5Z" /><path d="M6 11v5c0 1.5 3 3 6 3s6-1.5 6-3v-5" /></svg></span><b>{{ t('about.s009') }}</b><p>{{ t('about.s010') }}</p></div>
          <div class="pillar reveal"><span class="pi" aria-hidden="true"><svg viewbox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="9" cy="8" r="3" /><circle cx="17" cy="10" r="2.5" /><path d="M4 19c0-3 2-5 5-5s5 2 5 5M15 19c0-2 1.5-3.5 3-3.5" /></svg></span><b>{{ t('about.s011') }}</b><p>{{ t('about.s012') }}</p></div>
        </div>

        <div class="subh reveal">{{ t('about.s013') }}</div>
        <p class="lead reveal" style="margin-top:0">{{ t('about.s014') }}</p>

        <template v-for="g in groups" :key="g.key">
          <div class="subh reveal" style="margin-top:26px;color:var(--indigo-500)">{{ g.title }}</div>
          <p class="grp-intro reveal">{{ g.intro }}</p>
          <div class="people">
            <NuxtLink v-for="m in g.rows" :key="m.memberId" class="person reveal" :to="`/team/${m.memberId}`">
              <img
                v-if="m.avatarUrl"
                class="pav"
                :src="m.avatarUrl"
                :alt="pick(m, 'name')"
                width="76"
                height="96"
                loading="lazy"
              >
              <span v-else class="pav pav-txt" aria-hidden="true">{{ initials(m) }}</span>
              <span class="px">
                <b>{{ displayName(m.honorific, pick(m, 'name')) }}</b>
                <span v-if="subline(m)" class="aff">{{ subline(m) }}</span>
                <span v-if="pick(m, 'summary')" class="role">{{ pick(m, 'summary') }}</span>
                <span class="more">{{ t('about.team.viewProfile') }} &rarr;</span>
              </span>
            </NuxtLink>
          </div>
        </template>

        <p v-if="!members.length" class="grp-intro reveal">{{ t('about.team.empty') }}</p>
      </div>
    </section>
    <!-- ===================== ② 使命与愿景 ===================== -->
    <section class="sec" id="mission" :class="{ 'is-hidden': activeTab !== 'mission' }">
      <div class="wrap">
        <div class="p-intro">
          <span class="kicker reveal">{{ t('about.s037') }}</span>
          <h2 class="reveal">{{ t('about.s038') }}</h2>
        </div>
        <div class="mv" style="margin-top:clamp(22px,3vw,30px)">
          <div class="mvcard mission reveal">
            <span class="mvk" v-html="t('about.s039')"></span>
            <h3>{{ t('about.s040') }}</h3>
            <p>{{ t('about.s041') }}</p>
          </div>
          <div class="mvcard vision reveal">
            <span class="mvk" v-html="t('about.s042')"></span>
            <h3>{{ t('about.s043') }}</h3>
            <p>{{ t('about.s044') }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ===================== ③ 支持 ACTION ===================== -->
    <section class="sec" id="support" :class="{ 'is-hidden': activeTab !== 'support' }">
      <div class="wrap">
        <div class="p-intro">
          <span class="kicker reveal">{{ t('about.s045') }}</span>
          <h2 class="reveal">{{ t('about.s046') }}</h2>
          <p class="lead reveal">{{ t('about.s047') }}</p>
        </div>
        <div class="sup" style="margin-top:clamp(22px,3vw,30px)">
          <div class="supcard reveal"><span class="si" aria-hidden="true"><svg viewbox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M20 6 9 17l-5-5" /></svg></span><b>{{ t('about.s048') }}</b><p>{{ t('about.s049') }}</p></div>
          <div class="supcard reveal"><span class="si" aria-hidden="true"><svg viewbox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="9" cy="8" r="3" /><path d="M4 20c0-3 2-5 5-5s5 2 5 5M16 6h5M18.5 3.5v5" /></svg></span><b>{{ t('about.s050') }}</b><p>{{ t('about.s051') }}</p></div>
          <div class="supcard reveal"><span class="si" aria-hidden="true"><svg viewbox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M8 10h8M8 14h5" /><path d="M4 5h16v12H9l-4 4V5z" /></svg></span><b>{{ t('about.s052') }}</b><p>{{ t('about.s053') }}</p></div>
          <div class="supcard reveal"><span class="si" aria-hidden="true"><svg viewbox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M3 21h18M5 21V9l7-5 7 5v12M9 21v-6h6v6" /></svg></span><b>{{ t('about.s054') }}</b><p>{{ t('about.s055') }}</p></div>
          <div class="supcard reveal"><span class="si" aria-hidden="true"><svg viewbox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 21C6 17 3 13 3 8.5A4.5 4.5 0 0 1 12 6a4.5 4.5 0 0 1 9 2.5C21 13 18 17 12 21Z" /></svg></span><b>{{ t('about.s056') }}</b><p>{{ t('about.s057') }}</p></div>
        </div>
        <div style="margin-top:clamp(24px,3vw,32px)">
          <a href="mailto:action@gztcm-action.cn?subject=支持 / 参与 ACTION" class="btn btn-primary" v-html="t('about.s058')"></a>
        </div>
      </div>
    </section>

    <!-- ===================== ④ 联系我们 ===================== -->
    <section class="sec" id="contact" :class="{ 'is-hidden': activeTab !== 'contact' }">
      <div class="wrap">
        <div class="p-intro">
          <span class="kicker reveal">{{ t('about.s059') }}</span>
          <h2 class="reveal">{{ t('about.s060') }}</h2>
        </div>
        <div class="contact" style="margin-top:clamp(22px,3vw,30px)">
          <div class="cbig reveal">
            <div class="cmk">{{ t('about.s061') }}</div>
            <a class="cmail" href="mailto:action@gztcm-action.cn"><svg viewbox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></svg>action@gztcm-action.cn</a>
            <p class="cnote">{{ t('about.s062') }}</p>
            <div class="cbtns">
              <a href="mailto:action@gztcm-action.cn?subject=ACTION 咨询" class="btn btn-primary btn-sm">{{ t('about.s063') }}</a>
              <NuxtLink to="/collaborate" class="btn btn-onDark btn-sm">{{ t('about.s064') }}</NuxtLink>
            </div>
          </div>
          <div class="cinfo">
            <div class="crow reveal"><span class="ci" aria-hidden="true"><svg viewbox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M3 21h18M5 21V9l7-5 7 5v12M9 21v-6h6v6" /></svg></span><span><b>{{ t('about.s065') }}</b><span>{{ t('about.s066') }}</span></span></div>
            <div class="crow reveal"><span class="ci" aria-hidden="true"><svg viewbox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 21s7-6.5 7-11a7 7 0 1 0-14 0c0 4.5 7 11 7 11Z" /><circle cx="12" cy="10" r="2.5" /></svg></span><span><b>{{ t('about.s067') }}</b><span>{{ t('about.s068') }}</span></span></div>
            <div class="crow reveal"><span class="ci" aria-hidden="true"><svg viewbox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l4 2" /></svg></span><span><b>{{ t('about.s069') }}</b><span>{{ t('about.s070') }}</span></span></div>
            <div class="crow reveal"><span class="ci" aria-hidden="true"><svg viewbox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M4 4h16v16H4z" /><path d="m4 7 8 6 8-6" /></svg></span><span><b>{{ t('about.s071') }}</b><span>gztcm-action.cn</span></span></div>
          </div>
        </div>
      </div>
    </section>

    <!-- ===================== ⑤ 声明与条款 ===================== -->
    <section class="sec" id="legal" :class="{ 'is-hidden': activeTab !== 'legal' }">
      <div class="wrap">
        <div class="p-intro">
          <span class="kicker reveal">{{ t('about.s072') }}</span>
          <h2 class="reveal">{{ t('about.s073') }}</h2>
        </div>
        <div class="legal reveal">
          <div class="legal-block">
            <h3><span class="li" aria-hidden="true"><svg viewbox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 3l8 4v6c0 4.5-3.2 7-8 8-4.8-1-8-3.5-8-8V7z" /><path d="M9 12l2 2 4-4" /></svg></span><span>{{ t('about.s074') }}</span></h3>
            <p>{{ t('about.s075') }}</p>
            <p>{{ t('about.s076') }}</p>
          </div>
          <div class="legal-block">
            <h3><span class="li" aria-hidden="true"><svg viewbox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><ellipse cx="12" cy="6" rx="8" ry="3" /><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></svg></span><span>{{ t('about.s077') }}</span></h3>
            <ul>
              <li>{{ t('about.s078') }}</li>
              <li>{{ t('about.s079') }}</li>
              <li>{{ t('about.s080') }}</li>
            </ul>
          </div>
          <div class="legal-block">
            <h3><span class="li" aria-hidden="true"><svg viewbox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" /><path d="M12 9v4M12 17h.01" /></svg></span><span>{{ t('about.s081') }}</span></h3>
            <ul>
              <li>{{ t('about.s082') }}</li>
              <li>{{ t('about.s083') }}</li>
              <li>{{ t('about.s084') }}</li>
            </ul>
          </div>
          <div class="legal-block">
            <h3><span class="li" aria-hidden="true"><svg viewbox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></svg></span><span>{{ t('about.s085') }}</span></h3>
            <ul>
              <li>{{ t('about.s086') }}</li>
              <li>{{ t('about.s087') }}</li>
              <li>{{ t('about.s088') }}</li>
              <li>{{ t('about.s089') }}</li>
            </ul>
            <p class="upd">{{ t('about.s090') }}</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style>
.page-about .skip-link{position:absolute;left:12px;top:-60px;z-index:var(--z-toast);background:var(--indigo-700);color:#fff;font-weight:600;font-size:15px;padding:12px 20px;border-radius:10px;transition:top .2s var(--ease)}
.page-about .sec{padding:clamp(40px,5.5vw,72px) 0;scroll-margin-top:130px}
.page-about .sec.is-hidden{display:none}
.page-about h2.title{font-size:clamp(1.55rem,2.9vw,2.2rem);color:var(--indigo-900);letter-spacing:-.02em;text-wrap:balance;max-width:26ch;line-height:1.2}
.page-about .lead{color:var(--muted);font-size:clamp(1rem,1.4vw,1.14rem);max-width:70ch;margin-top:16px;text-wrap:pretty}
.page-about .subh{font-size:12.5px;font-weight:700;color:var(--indigo-900);text-transform:uppercase;letter-spacing:.03em;margin:clamp(30px,4vw,44px) 0 16px;font-family:"Source Sans 3","Noto Sans SC",sans-serif}
.page-about .subh:first-child{margin-top:0}
.page-about .btn{display:inline-flex;align-items:center;justify-content:center;gap:9px;padding:13px 24px;border-radius:999px;font-weight:600;font-size:15px;border:1.5px solid transparent;cursor:pointer;white-space:nowrap;transition:transform .25s var(--ease),background-color .25s var(--ease),box-shadow .25s var(--ease),border-color .25s var(--ease)}
/* 浅色 Hero（甲方定稿的天青主题）。base.css 里的浅色覆盖是无命名空间的 `.phero::before`，
   会输给这里的 `.page-about .phero::before`，所以渐变本身必须写成浅色版——否则深底叠上
   base.css 给的深色字。面包屑 / 标签 / 副标题同理，一并按浅底取色。 */
.page-about .phero::before{content:"";position:absolute;inset:0;z-index:-1;background:
  radial-gradient(1000px 560px at 88% -6%,rgba(87,190,174,.30),transparent 62%),
  radial-gradient(660px 460px at 0% 108%,rgba(207,70,53,.10),transparent 66%),
  linear-gradient(162deg,#e9f3ee 0%,#f2f6f2 46%,#f6efe4 108%)}
.page-about .phero .wrap{padding:clamp(28px,3.6vw,42px) clamp(20px,4vw,44px) clamp(40px,5vw,56px)}
.page-about .crumb{display:flex;align-items:center;gap:9px;font-size:13.5px;color:var(--muted);margin-bottom:22px;flex-wrap:wrap}
.page-about .crumb a{color:var(--indigo-700)}
.page-about .crumb a:hover{color:var(--cinnabar)}
.page-about .crumb .sep{color:var(--indigo-300)}
.page-about .crumb b{color:var(--indigo-900)}
.page-about .phero-tag{display:inline-flex;align-items:center;gap:10px;font-size:13px;font-weight:600;letter-spacing:.02em;color:var(--indigo-700);background:rgba(255,255,255,.75);border:1px solid var(--line);padding:8px 16px;border-radius:999px;backdrop-filter:blur(4px)}
.page-about .phero h1{font-size:clamp(1.9rem,3.9vw,3rem);font-weight:700;letter-spacing:-.025em;margin:18px 0 0;text-wrap:balance;line-height:1.14}
.page-about .phero .psub{margin-top:18px;font-size:clamp(1rem,1.4vw,1.16rem);color:var(--muted);max-width:64ch;line-height:1.7;text-wrap:pretty}
.page-about .subnav{position:sticky;top:72px;z-index:var(--z-subnav);background:rgba(242,246,244,.9);backdrop-filter:blur(12px) saturate(1.3);border-bottom:1px solid var(--line)}
.page-about .subnav-in{display:flex;align-items:center;gap:2px;overflow-x:auto;scrollbar-width:none}
.page-about .subnav-in::-webkit-scrollbar{display:none}
.page-about .subnav a{position:relative;flex-shrink:0;padding:15px 15px 13px;font-size:14.5px;font-weight:600;color:var(--muted);white-space:nowrap;transition:color .2s}
.page-about .subnav a::after{content:"";position:absolute;left:15px;right:15px;bottom:-1px;height:2px;background:var(--cinnabar);transform:scaleX(0);transform-origin:left;transition:transform .3s var(--ease)}
.page-about .subnav a:hover,.page-about .subnav a.active{color:var(--indigo-900)}
.page-about .subnav a.active::after{transform:scaleX(1)}
.page-about .p-intro h2{font-size:clamp(1.5rem,2.8vw,2.1rem);color:var(--indigo-900);letter-spacing:-.02em;line-height:1.2}
.page-about .pillars{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px;margin-top:4px}
.page-about .pillar{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:22px}
.page-about .pillar .pi{width:42px;height:42px;border-radius:11px;background:var(--indigo-100);color:var(--indigo-600);display:flex;align-items:center;justify-content:center;margin-bottom:14px}
.page-about .pillar .pi svg{width:22px;height:22px}
.page-about .pillar b{display:block;font-family:"Spectral","Noto Serif SC",serif;font-weight:600;font-size:1.1rem;color:var(--indigo-900);margin-bottom:7px;line-height:1.25}
.page-about .pillar p{font-size:13.5px;color:var(--muted);line-height:1.6}
.page-about .grp-intro{font-size:13.5px;color:var(--muted);line-height:1.7;max-width:78ch;margin:-6px 0 16px;text-wrap:pretty}
.page-about .people{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px}
.page-about .person{display:flex;gap:16px;background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:18px 20px;transition:.2s var(--ease)}
.page-about .person:hover{border-color:var(--indigo-200);box-shadow:var(--shadow-sm);transform:translateY(-2px)}
/* 头像用竖版：docx 里给的多是标准证件照/半身像，横版裁切会切到肩膀以外 */
.page-about .person .pav{width:76px;height:96px;flex-shrink:0;border-radius:12px;object-fit:cover;object-position:center top;background:var(--indigo-100);border:1px solid var(--line)}
.page-about .person .pav-txt{display:flex;align-items:center;justify-content:center;background:var(--indigo-700);color:#fff;font-family:"Spectral",serif;font-weight:700;font-size:22px;border-color:transparent}
.page-about .person .px{min-width:0;display:flex;flex-direction:column}
.page-about .person b{display:block;font-size:15px;color:var(--indigo-900);font-family:"Source Sans 3","Noto Sans SC",sans-serif;font-weight:700}
.page-about .person .aff{display:block;font-size:12.5px;color:var(--indigo-600);font-weight:600;margin:2px 0 6px}
/* 简介统一压成 3 行：卡片高度不齐会让整片名单看起来像没排过版 */
.page-about .person .role{display:-webkit-box;-webkit-line-clamp:3;line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;font-size:12.5px;color:var(--muted);line-height:1.55}
.page-about .person .more{margin-top:auto;padding-top:9px;font-size:12px;font-weight:700;color:var(--indigo-600);transition:color .2s var(--ease)}
.page-about .person:hover .more{color:var(--cinnabar)}
.page-about .mv{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.page-about .mvcard{border-radius:var(--radius-lg);padding:clamp(24px,3vw,36px);position:relative;overflow:hidden;isolation:isolate}
.page-about .mvcard.mission{background:var(--indigo-900);color:#fff}
.page-about .mvcard.mission::before{content:"";position:absolute;inset:0;z-index:-1;background:radial-gradient(500px 260px at 100% 0,rgba(44,127,114,.45),transparent 60%)}
.page-about .mvcard.vision{background:var(--surface);border:1px solid var(--line)}
.page-about .mvcard .mvk{display:inline-flex;align-items:center;gap:8px;font-size:12.5px;font-weight:700;letter-spacing:.03em;margin-bottom:14px}
.page-about .mvcard.mission .mvk{color:var(--indigo-200)}
.page-about .mvcard.vision .mvk{color:var(--cinnabar-d)}
.page-about .mvcard .mvk svg{width:18px;height:18px}
.page-about .mvcard h3{font-family:"Spectral","Noto Serif SC",serif;font-weight:600;font-size:clamp(1.3rem,2.2vw,1.7rem);line-height:1.25;margin-bottom:14px}
.page-about .mvcard.mission h3{color:#fff}
.page-about .mvcard.vision h3{color:var(--indigo-900)}
.page-about .mvcard p{font-size:14.5px;line-height:1.72}
.page-about .mvcard.mission p{color:rgba(233,238,247,.9)}
.page-about .mvcard.vision p{color:var(--muted)}
.page-about .sup{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
.page-about .supcard{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:22px;transition:.2s var(--ease)}
.page-about .supcard:hover{transform:translateY(-3px);box-shadow:var(--shadow-md);border-color:var(--indigo-200)}
.page-about .supcard .si{width:40px;height:40px;border-radius:11px;background:var(--info-bg);color:var(--info);display:flex;align-items:center;justify-content:center;margin-bottom:13px}
.page-about .supcard .si svg{width:21px;height:21px}
.page-about .supcard b{display:block;font-family:"Spectral","Noto Serif SC",serif;font-weight:600;font-size:1.08rem;color:var(--indigo-900);margin-bottom:6px;line-height:1.3}
.page-about .supcard p{font-size:13.5px;color:var(--muted);line-height:1.6}
.page-about .contact{display:grid;grid-template-columns:1.1fr 1fr;gap:clamp(20px,3vw,36px);align-items:start}
.page-about .cbig{background:var(--indigo-900);color:#fff;border-radius:var(--radius-lg);padding:clamp(24px,3vw,38px);isolation:isolate;position:relative;overflow:hidden}
.page-about .cbig::before{content:"";position:absolute;inset:0;z-index:-1;background:radial-gradient(500px 260px at 100% 0,rgba(44,127,114,.45),transparent 60%)}
.page-about .cbig .cmk{font-size:12.5px;font-weight:700;color:var(--indigo-200);letter-spacing:.03em;margin-bottom:10px}
.page-about .cbig .cmail{display:inline-flex;align-items:center;gap:10px;font-family:"Spectral","Noto Serif SC",serif;font-weight:600;font-size:clamp(1.15rem,2vw,1.5rem);color:#fff;word-break:break-all}
.page-about .cbig .cmail svg{width:22px;height:22px;flex-shrink:0;color:var(--indigo-200)}
.page-about .cbig .cmail:hover{color:var(--indigo-200)}
.page-about .cbig .cnote{font-size:13.5px;color:rgba(233,238,247,.82);margin-top:14px;line-height:1.6}
.page-about .cinfo{display:flex;flex-direction:column;gap:12px}
.page-about .crow{display:flex;align-items:flex-start;gap:13px;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px 18px}
.page-about .crow .ci{width:38px;height:38px;flex-shrink:0;border-radius:10px;background:var(--indigo-100);color:var(--indigo-600);display:flex;align-items:center;justify-content:center}
.page-about .crow .ci svg{width:20px;height:20px}
.page-about .crow b{display:block;font-size:12.5px;font-weight:700;color:var(--indigo-800)}
.page-about .crow span{display:block;font-size:13.5px;color:var(--muted);margin-top:2px;line-height:1.5}
.page-about .cbtns{display:flex;gap:12px;flex-wrap:wrap;margin-top:16px}
.page-about .legal{max-width:80ch}
.page-about .legal-block{padding:clamp(20px,2.6vw,28px) 0;border-top:1px solid var(--line)}
.page-about .legal-block:first-child{border-top:none;padding-top:0}
.page-about .legal-block h3{display:flex;align-items:center;gap:11px;font-size:1.2rem;color:var(--indigo-900);margin-bottom:12px}
.page-about .legal-block h3 .li{width:34px;height:34px;flex-shrink:0;border-radius:9px;background:var(--indigo-100);color:var(--indigo-600);display:flex;align-items:center;justify-content:center}
.page-about .legal-block h3 .li svg{width:19px;height:19px}
.page-about .legal-block p{font-size:14px;color:var(--ink);line-height:1.7;margin-bottom:10px}
.page-about .legal-block ul{list-style:none;display:flex;flex-direction:column;gap:8px;margin:6px 0 4px}
.page-about .legal-block li{position:relative;padding-left:18px;font-size:13.5px;color:var(--muted);line-height:1.6}
.page-about .legal-block li::before{content:"";position:absolute;left:2px;top:9px;width:6px;height:6px;border-radius:50%;background:var(--cinnabar)}
.page-about .legal-block .upd{font-size:12.5px;color:var(--muted);margin-top:6px}
.page-about .legal-block b{color:var(--indigo-800)}
@media(max-width:900px){
.page-about .mv,.page-about .contact{grid-template-columns:1fr}
}
</style>
