<script setup lang="ts">
/** 页脚 —— 迁移自 assets/site.js 的 FOOTER 常量。 */
const { t } = useI18n()

const PLATFORM_LINKS = [
  { key: 'guidelines', to: '/guidelines' },
  { key: 'methodology', to: '/srd' },
  { key: 'assistant', to: '/assistant' },
  { key: 'implementation', to: '/implementation' },
]

const MORE_LINKS = [
  { key: 'collaborate', to: '/collaborate' },
  { key: 'news', to: '/news' },
  { key: 'about', to: '/about' },
  { key: 'resources', to: '/#resources' },
]
</script>

<template>
  <footer>
    <div class="wrap">
      <div class="fgrid">
        <div class="fbrand">
          <svg class="seal" viewBox="0 0 48 48" fill="none" aria-hidden="true">
            <rect x="1.5" y="1.5" width="45" height="45" rx="11" fill="var(--indigo-700)" />
            <circle cx="24" cy="24" r="10.5" stroke="var(--indigo-200)" stroke-width="1.4" />
            <circle cx="24" cy="24" r="3" fill="var(--cinnabar)" />
            <path d="M24 4v12M24 32v12" stroke="#fff" stroke-width="1.6" stroke-linecap="round" />
          </svg>
          <b class="fbrand-name">{{ t('brand.name') }}</b>
          <p>{{ t('footer.desc') }}</p>
        </div>

        <div>
          <h2>{{ t('footer.platform') }}</h2>
          <nav>
            <NuxtLink v-for="l in PLATFORM_LINKS" :key="l.key" :to="l.to">
              {{ t(`footer.links.${l.key}`) }}
            </NuxtLink>
          </nav>
        </div>

        <div>
          <h2>{{ t('footer.more') }}</h2>
          <nav>
            <NuxtLink v-for="l in MORE_LINKS" :key="l.key" :to="l.to">
              {{ t(`footer.links.${l.key}`) }}
            </NuxtLink>
          </nav>
        </div>

        <div class="fcontact">
          <h2>{{ t('footer.contact') }}</h2>
          <a class="fmail" href="mailto:action@gztcm-action.cn">action@gztcm-action.cn</a>
          <a>{{ t('footer.org') }}</a>
          <a>{{ t('footer.address') }}</a>
        </div>
      </div>

      <div class="copy">
        <span>{{ t('footer.copyright') }}</span>
        <span>{{ t('footer.icp') }}</span>
      </div>
    </div>
  </footer>
</template>

<style>
/* 原实现里品牌名是 <b> 上的内联样式，这里提出为类，视觉等价 */
.fbrand-name {
  color: #fff;
  font-family: 'Spectral', 'Noto Serif SC', serif;
  letter-spacing: .06em;
  font-size: 18px;
}
</style>
