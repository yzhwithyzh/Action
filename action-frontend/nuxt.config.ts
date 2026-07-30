// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2026-07-28',
  devtools: { enabled: true },

  // 固定开发端口，避免 3000 被占用时 Nuxt 自动 +1，导致代理/文档里的地址对不上
  devServer: { port: 3010 },

  // 官网是对外品牌站，SEO 与首屏重要 —— 构建期预渲染为静态 HTML
  ssr: true,
  nitro: {
    preset: 'static',
    prerender: {
      // 新闻详情 `/news/[id]` 没有固定路由表，靠爬取 `/news` 列表页里的 <NuxtLink> 发现。
      // 显式写出来是因为这层依赖不写下来看不出：列表页不渲染某条新闻，它的详情页就不会被生成。
      crawlLinks: true,
      routes: ['/'],
    },
  },

  // 全局样式的加载顺序即优先级，必须保持：
  //   base   令牌 / 重置 / 排版 / 按钮
  //   chrome 顶栏与页脚（原 assets/site.js 运行时追加在最后，优先级最高）
  // 页面专属样式写在各自 SFC 的 <style> 里，天然排在两者之后。
  css: [
    '~/assets/css/base.css',
    '~/assets/css/chrome.css',
  ],

  modules: ['@nuxtjs/i18n'],

  i18n: {
    strategy: 'no_prefix', // 与现状一致：同一 URL 内切换语言，不做 /en 前缀路由
    defaultLocale: 'zh',
    locales: [
      { code: 'zh', language: 'zh-CN', name: '中文', file: 'zh.json' },
      { code: 'en', language: 'en-US', name: 'English', file: 'en.json' },
    ],
    detectBrowserLanguage: {
      useCookie: true,
      cookieKey: 'action_lang',
      redirectOn: 'root',
      alwaysRedirect: false,
      fallbackLocale: 'zh',
    },
    bundle: { optimizeTranslationDirective: false },
    compilation: {
      // 原站用 innerHTML 切换双语，部分文案本身带标签（如 <span class="hl">…</span>）。
      // vue-i18n 默认 strictMessage 会拒绝编译含 HTML 的消息，这里放开；
      // 对应模板中这些条目以 v-html 渲染，内容全部来自本仓库静态文案，无外部输入。
      strictMessage: false,
      escapeHtml: false,
    },
  },

  app: {
    head: {
      htmlAttrs: { lang: 'zh-CN' },
      meta: [
        { charset: 'UTF-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1.0' },
      ],
      link: [
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600;700&family=Source+Sans+3:wght@400;500;600;700&family=Noto+Serif+SC:wght@500;600;700&family=Noto+Sans+SC:wght@400;500;700&display=swap',
        },
      ],
    },
  },

  // 后端接口代理：开发期把 /dev-api 转发到 action-backend
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || '/dev-api',
    },
  },

  routeRules: {
    '/dev-api/**': { proxy: 'http://127.0.0.1:9098/**' },
  },
})
