<script setup lang="ts">
const { t, locale } = useI18n()

// 原实现在 <head> 里同步加 .js 类，用于「无 JS 时不隐藏内容」的渐进增强样式
useHead({
  htmlAttrs: {
    class: 'js',
    lang: computed(() => (locale.value === 'zh' ? 'zh-CN' : 'en-US')),
  },
})
</script>

<template>
 
  <SiteHeader />
  <main id="main">
    <slot />
  </main>
  <SiteFooter />
</template>
