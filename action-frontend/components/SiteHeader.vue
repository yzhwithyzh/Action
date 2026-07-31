<script setup lang="ts">
/**
 * 顶栏 —— 迁移自 assets/site.js 的 HEADER 常量。
 * 导航数据保持单一来源；当前页高亮由路由自动判断（原实现按文件名判断）。
 */
const { t, locale, setLocale } = useI18n()
const route = useRoute()

interface NavItem {
  key: string
  to?: string
  /** 高亮匹配的路由 path；带 hash 的锚点链接需单独指定 */
  match?: string
  /** 有 children 时本项不是链接，而是顶栏上的一个下拉分组 */
  children?: NavItem[]
}

const NAV: NavItem[] = [
  // 标签是「首页」，落点就必须是首页顶部：仍指向 /#modules 的话，点「首页」会直接
  // 滚到平台模块区，跳过 Hero。首页里的「了解平台模块」按钮仍保留 #modules 锚点。
  { key: 'platform', to: '/', match: '/' },
  { key: 'guidelines', to: '/guidelines', match: '/guidelines' },
  // 三个 AI 工具页合并成一个下拉：顶栏一级项从 8 个降到 6 个，且它们本就是同一类东西。
  // 「报告规范」是首要 CTA，必须留在一级，不进这个组。
  {
    key: 'tools',
    children: [
      { key: 'assistant', to: '/assistant', match: '/assistant' },
      { key: 'methodology', to: '/srd', match: '/srd' },
      { key: 'implementation', to: '/implementation', match: '/implementation' },
    ],
  },
  { key: 'collaborate', to: '/collaborate', match: '/collaborate' },
  { key: 'news', to: '/news', match: '/news' },
  { key: 'about', to: '/about', match: '/about' },
]

const isCurrent = (item: NavItem) => route.path === item.match
/** 分组按钮的高亮：停在组内任一页面时点亮 */
const isGroupCurrent = (item: NavItem) => (item.children ?? []).some(isCurrent)

/* ---------- 顶栏下拉 ---------- */
const openKey = ref<string | null>(null)
let closeTimer: ReturnType<typeof setTimeout> | undefined

const openGroup = (key: string) => {
  clearTimeout(closeTimer)
  openKey.value = key
}
// 延迟关闭：鼠标从按钮斜着划向面板时会短暂离开容器，立即关会点不中
const scheduleClose = () => {
  clearTimeout(closeTimer)
  closeTimer = setTimeout(() => { openKey.value = null }, 160)
}
const closeGroup = () => {
  clearTimeout(closeTimer)
  openKey.value = null
}
const toggleGroup = (key: string) => {
  if (openKey.value === key) closeGroup()
  else openGroup(key)
}
// 焦点移出整个分组才关，Tab 在面板内部移动时保持展开
const onGroupBlur = (event: FocusEvent, key: string) => {
  const next = event.relatedTarget as Node | null
  const root = event.currentTarget as HTMLElement
  if (openKey.value === key && (!next || !root.contains(next))) closeGroup()
}

const onDocClick = (event: MouseEvent) => {
  if (!(event.target as HTMLElement).closest('.menu-grp')) closeGroup()
}
const onKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') closeGroup()
}
onMounted(() => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => {
  clearTimeout(closeTimer)
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onKeydown)
})

const { guest, isLoggedIn, logout, fetchMe } = useAuth()

/** 登录/注册两页自身不作为跳回目标，改为透传它们已经带着的 redirect */
const AUTH_PATHS = ['/login', '/register']
const authRedirect = computed(() => {
  if (!AUTH_PATHS.includes(route.path)) return route.fullPath
  const raw = route.query.redirect

  return typeof raw === 'string' ? raw : ''
})
/** 登录后跳回来源页；`resolveRedirect` 会在落地页再校验一次是不是站内路径 */
const authLink = (path: string) =>
  (authRedirect.value ? `${path}?redirect=${encodeURIComponent(authRedirect.value)}` : path)
const loginLink = computed(() => authLink('/login'))
const registerLink = computed(() => authLink('/register'))

const menuOpen = ref(false)
const toggleMenu = () => {
  menuOpen.value = !menuOpen.value
}

// 移动端菜单展开时给 <html> 加类，沿用原 chrome CSS 的 .menu-open 选择器
watchEffect(() => {
  if (import.meta.client) {
    document.documentElement.classList.toggle('menu-open', menuOpen.value)
  }
})

// 路由切换后收起移动菜单与顶栏下拉
watch(() => route.fullPath, () => {
  menuOpen.value = false
  closeGroup()
})

const switchLang = () => {
  setLocale(locale.value === 'zh' ? 'en' : 'zh')
}

// 全站构建期预渲染（`nitro.preset: 'static'`），登录态只能在客户端判定：
// 回填必须放 onMounted，且顶栏那块整体裹 <ClientOnly>，否则会被烤进静态 HTML。
onMounted(() => {
  void fetchMe()
})

const onLogout = async () => {
  await logout()
  // 登出停留在当前页，但移动菜单不会因路由变化自动收起，这里手动收
  menuOpen.value = false
}
</script>

<template>
  <header id="top">
    <div class="wrap nav">
      <NuxtLink class="brand" to="/" :aria-label="t('brand.homeAria')">
        <svg class="seal" viewBox="0 0 48 48" fill="none" aria-hidden="true">
          <rect x="1.5" y="1.5" width="45" height="45" rx="11" fill="var(--indigo-700)" />
          <rect x="1.5" y="1.5" width="45" height="45" rx="11" stroke="var(--indigo-500)" stroke-width="1" />
          <circle cx="24" cy="24" r="10.5" stroke="var(--indigo-200)" stroke-width="1.4" />
          <circle cx="24" cy="24" r="3" fill="var(--cinnabar)" />
          <path d="M24 4v12M24 32v12" stroke="#fff" stroke-width="1.6" stroke-linecap="round" />
          <circle
            cx="24" cy="24" r="10.5" stroke="var(--cinnabar)" stroke-width="1.4"
            stroke-dasharray="1.5 5" opacity=".7"
          />
        </svg>
        <span class="brand-txt">
          <b>{{ t('brand.name') }}</b>
          <small>{{ t('brand.org') }}</small>
        </span>
      </NuxtLink>

      <nav class="menu" :aria-label="t('nav.aria')">
        <template v-for="item in NAV" :key="item.key">
          <div
            v-if="item.children"
            class="menu-grp"
            :class="{ open: openKey === item.key }"
            @mouseenter="openGroup(item.key)"
            @mouseleave="scheduleClose"
            @focusin="openGroup(item.key)"
            @focusout="onGroupBlur($event, item.key)"
          >
            <button
              type="button"
              class="grp-btn"
              :class="{ cur: isGroupCurrent(item) }"
              :aria-expanded="openKey === item.key"
              aria-haspopup="true"
              @click.stop="toggleGroup(item.key)"
            >
              <span>{{ t(`nav.${item.key}`) }}</span>
              <svg
                viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"
                stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"
              ><path d="m6 9 6 6 6-6" /></svg>
            </button>
            <div class="grp-panel">
              <NuxtLink
                v-for="sub in item.children"
                :key="sub.key"
                :to="sub.to"
                :class="{ cur: isCurrent(sub) }"
                :aria-current="isCurrent(sub) ? 'page' : undefined"
              >
                <span class="gi-t">{{ t(`nav.${sub.key}`) }}</span>
                <span class="gi-d">{{ t(`nav.${sub.key}Desc`) }}</span>
              </NuxtLink>
            </div>
          </div>
          <NuxtLink
            v-else
            :to="item.to"
            :class="{ cur: isCurrent(item) }"
            :aria-current="isCurrent(item) ? 'page' : undefined"
          >{{ t(`nav.${item.key}`) }}</NuxtLink>
        </template>
      </nav>

      <div class="nav-actions">
        <button class="lang" :aria-label="t('nav.langAria')" @click="switchLang">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
            <circle cx="12" cy="12" r="9.2" />
            <path d="M2.8 12h18.4M12 2.8c2.6 2.5 4 5.8 4 9.2s-1.4 6.7-4 9.2c-2.6-2.5-4-5.8-4-9.2s1.4-6.7 4-9.2Z" />
          </svg>
          <span>{{ t('nav.langLabel') }}</span>
        </button>
        <!--
          登录入口不用 `.btn`：`chrome.css` 的 @media(max-width:900px) 会隐藏
          `.nav-actions .btn`，而且本仓没有全局 `.btn` 基础规则（形状由各页面自己写，
          header 不在任何 `.page-*` 作用域内）。这里照 `.lang` 的胶囊写法。
        -->
        <ClientOnly>
          <span class="auth-group" role="group" :aria-label="t('nav.accountAria')">
            <template v-if="isLoggedIn">
              <span class="auth-name" :title="guest?.username"><span>{{ guest?.username }}</span></span>
              <button type="button" class="auth-link" @click="onLogout">{{ t('nav.logout') }}</button>
            </template>
            <NuxtLink v-else class="auth-link" :to="loginLink">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
                <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
                <path d="M10 17l5-5-5-5M15 12H3" />
              </svg>
              <span>{{ t('nav.login') }}</span>
            </NuxtLink>
          </span>
        </ClientOnly>
        <button class="burger" :aria-label="t('nav.menuAria')" :aria-expanded="menuOpen" @click="toggleMenu">
          <span /><span /><span />
        </button>
      </div>
    </div>
  </header>

  <nav class="mobile-menu" :aria-label="t('nav.ariaMobile')">
    <!-- 移动端不做二级折叠：多一次点击换不来什么，直接把分组摊开成缩进的一段 -->
    <template v-for="item in NAV" :key="item.key">
      <div v-if="item.children" class="mm-grp">
        <span class="mm-lbl">{{ t(`nav.${item.key}`) }}</span>
        <div class="mm-sub">
          <NuxtLink
            v-for="sub in item.children"
            :key="sub.key"
            :to="sub.to"
            :class="{ cur: isCurrent(sub) }"
            :aria-current="isCurrent(sub) ? 'page' : undefined"
          >{{ t(`nav.${sub.key}`) }}</NuxtLink>
        </div>
      </div>
      <NuxtLink
        v-else
        :to="item.to"
        :aria-current="isCurrent(item) ? 'page' : undefined"
      >{{ t(`nav.${item.key}`) }}</NuxtLink>
    </template>
    <!-- 顶栏那份在 ≤600px 会被收起，移动菜单里必须有一份等价入口 -->
    <ClientOnly>
      <template v-if="isLoggedIn">
        <span class="mm-user">{{ t('auth.loggedInAs', { name: guest?.username ?? '' }) }}</span>
        <button type="button" class="mm-auth" @click="onLogout">{{ t('nav.logout') }}</button>
      </template>
      <template v-else>
        <NuxtLink :to="loginLink">{{ t('nav.login') }}</NuxtLink>
        <NuxtLink :to="registerLink">{{ t('nav.register') }}</NuxtLink>
      </template>
    </ClientOnly>
  </nav>
</template>
