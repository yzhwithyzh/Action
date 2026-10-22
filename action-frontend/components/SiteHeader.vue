<script setup lang="ts">
/**
 * 顶栏 —— 迁移自 assets/site.js 的 HEADER 常量。
 * 导航数据保持单一来源；当前页高亮由路由自动判断（原实现按文件名判断）。
 */
const { t, locale, setLocale } = useI18n()
const route = useRoute()

interface NavItem {
  key: string
  to: string
  /** 高亮匹配的路由 path；带 hash 的锚点链接需单独指定 */
  match: string
}

// 顶栏一律平铺，没有下拉分组：三个 AI 工具页原先折在「智能工具」下拉里，
// 现已提到一级 —— 少一次点击，且三页彼此没有从属关系。
// 代价是英文标签一排放不下，见 chrome.css 里 .menu 的字号/间距与 ≤1180 断点。
const NAV: NavItem[] = [
  // 标签是「首页」，落点就必须是首页顶部：仍指向 /#modules 的话，点「首页」会直接
  // 滚到平台模块区，跳过 Hero。首页里的「了解平台模块」按钮仍保留 #modules 锚点。
  { key: 'platform', to: '/', match: '/' },
  { key: 'guidelines', to: '/guidelines', match: '/guidelines' },
  { key: 'assistant', to: '/assistant', match: '/assistant' },
  { key: 'methodology', to: '/srd', match: '/srd' },
  { key: 'implementation', to: '/implementation', match: '/implementation' },
  { key: 'collaborate', to: '/collaborate', match: '/collaborate' },
  { key: 'news', to: '/news', match: '/news' },
  // 中文标签是「成果」不是「成果发表」：这是第 9 项，英文那版（Publications）本来就是
  // 一排里最长的词，两个字与四个字在 ≤1180px 那一档差着一整行
  { key: 'publications', to: '/publications', match: '/publications' },
  { key: 'about', to: '/about', match: '/about' },
]

const isCurrent = (item: NavItem) => route.path === item.match

const { guest, isLoggedIn, logout, fetchMe } = useAuth()

/** 登录/注册/找回密码这几页自身不作为跳回目标，改为透传它们已经带着的 redirect */
const AUTH_PATHS = ['/login', '/register', '/forgot-password']
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

/**
 * 顶栏英文版收窄项间距的类（`chrome.css` 的 `.menu.is-en`）。
 *
 * **不能直接绑 `locale !== 'zh'`。** 站点是构建期预渲染（`nitro.preset: 'static'`），
 * 那份 HTML 按默认语言 zh 渲染，里面是 `class="menu"`；访客带着 `action_lang=en` 的 cookie
 * 刷新时，客户端首次渲染算出来的是 `class="menu is-en"` —— 而 **Vue 的 hydration 只修文本、
 * 不修 class**（`runtime-core` 的 `hydrateElement`：文本不一致就地 `el.textContent=` 改掉，
 * props 不一致只记一条 mismatch 警告，真正 patchProp 的仅限事件、`.prop` 修饰符与
 * `dynamicProps`，而 class 走 CLASS patchFlag，从不进 `dynamicProps`）。
 * 结果是刷新后得到「英文文案 + 中文那档 20px 间距」，8 个英文全称排不下折成两行，
 * 与点语言按钮切出来的样子对不上（那是普通响应式更新，class 打得上）。
 *
 * 挂个 hydrated 开关把首帧对齐：服务端与客户端首次渲染都不带这个类 → 无 mismatch →
 * 挂载后置真，走正常的响应式 patch。两条路径由此收敛到同一个结果。
 * 这个 patch 在挂载后的同一批微任务里 flush，早于浏览器绘制，看不到中间态。
 */
const hydrated = ref(false)
const menuIsEn = computed(() => hydrated.value && locale.value !== 'zh')

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

// 路由切换后收起移动菜单
watch(() => route.fullPath, () => {
  menuOpen.value = false
})

const switchLang = () => {
  setLocale(locale.value === 'zh' ? 'en' : 'zh')
}

// 全站构建期预渲染（`nitro.preset: 'static'`），登录态只能在客户端判定：
// 回填必须放 onMounted，且顶栏那块整体裹 <ClientOnly>，否则会被烤进静态 HTML。
onMounted(() => {
  hydrated.value = true
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
      <!--
        品牌标识用甲方给的正式 logo（图标 + ACTION 字标一体）。字标已经在图里，
        旁边只留机构名，不再重复写一遍 ACTION。图片 alt 留空是因为链接自身有
        aria-label（「ACTION 首页」），再给 alt 就会读成两遍。
        width/height 写死只为让浏览器提前算出宽高比、首屏不抖，实际大小由 CSS 高度定。
      -->
      <NuxtLink class="brand" to="/" :aria-label="t('brand.homeAria')">
        <img class="brand-logo" src="/assets/action-logo.png" alt="" width="760" height="181">
        
      </NuxtLink>

      <!--
        英文标签是全称、还会折行，项间距要比中文那版更紧一档（见 chrome.css 的 .menu.is-en）。
        这里用类而不是 CSS 的 `html[lang^="en"]`：`nuxt.config.ts` 把 htmlAttrs.lang 写死成
        zh-CN，切语言时 <html lang> 并不跟着变，靠它选不中。
        绑的是 `menuIsEn` 而不是 `locale !== 'zh'`，原因见 script 里那段注释（hydration 不修 class）。
      -->
      <nav class="menu" :class="{ 'is-en': menuIsEn }" :aria-label="t('nav.aria')">
        <NuxtLink
          v-for="item in NAV"
          :key="item.key"
          :to="item.to"
          :class="{ cur: isCurrent(item) }"
          :aria-current="isCurrent(item) ? 'page' : undefined"
        >{{ t(`nav.${item.key}`) }}</NuxtLink>
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
              <NuxtLink
                class="auth-name" to="/account" :title="t('nav.accountLink')"
                :aria-current="route.path === '/account' ? 'page' : undefined"
              ><span>{{ guest?.username }}</span></NuxtLink>
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
    <NuxtLink
      v-for="item in NAV"
      :key="item.key"
      :to="item.to"
      :aria-current="isCurrent(item) ? 'page' : undefined"
    >{{ t(`nav.${item.key}`) }}</NuxtLink>
    <!-- 顶栏那份在 ≤600px 会被收起，移动菜单里必须有一份等价入口 -->
    <ClientOnly>
      <template v-if="isLoggedIn">
        <span class="mm-user">{{ t('auth.loggedInAs', { name: guest?.username ?? '' }) }}</span>
        <NuxtLink to="/account">{{ t('nav.accountLink') }}</NuxtLink>
        <button type="button" class="mm-auth" @click="onLogout">{{ t('nav.logout') }}</button>
      </template>
      <template v-else>
        <NuxtLink :to="loginLink">{{ t('nav.login') }}</NuxtLink>
        <NuxtLink :to="registerLink">{{ t('nav.register') }}</NuxtLink>
      </template>
    </ClientOnly>
  </nav>
</template>
