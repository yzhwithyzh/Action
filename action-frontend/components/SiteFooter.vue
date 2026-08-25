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
  { key: 'publications', to: '/publications' },
  { key: 'about', to: '/about' },
  { key: 'resources', to: '/#resources' },
]
</script>

<template>
  <footer>
    <div class="wrap">
      <div class="fgrid">
        <div class="fbrand">
          <!-- 页脚是 --indigo-900 深底，必须用浅色那一版：深绿字标压上去等于没有 -->
          <img
            class="fbrand-logo" src="/assets/action-logo-light.png" :alt="t('brand.name')"
            width="760" height="181"
          >
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
          <a class="fmail" href="mailto:action_acu@163.com">action_acu@163.com</a>
          <a>{{ t('footer.org') }}</a>
          <a>{{ t('footer.address') }}</a>
        </div>
      </div>

      <div class="copy">
        <span>{{ t('footer.copyright') }}</span>
        <!-- 备案号要求是指向 beian.miit.gov.cn 的可点链接，所以这条走 v-html；
             文案里的标签由后端白名单把关（action_vo.py 的 assert_safe_markup） -->
        <span v-html="t('footer.icp')" />
      </div>
    </div>
  </footer>
</template>

