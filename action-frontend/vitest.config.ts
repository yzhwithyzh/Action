import { defineConfig } from 'vitest/config'

/**
 * 单测只覆盖**纯逻辑**（`composables/authValidation.ts`），不测组件渲染 ——
 * 所以不需要 Nuxt 环境、不需要 @vue/test-utils，node 环境跑就够了。
 *
 * `include` 写死在 `test/` 下：默认 glob 会把 `.nuxt/`、`.output/`、`dist/` 里
 * 构建产物中的同名文件也扫进来。
 */
export default defineConfig({
  test: {
    environment: 'node',
    include: ['test/**/*.spec.ts'],
  },
})
