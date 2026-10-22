<script setup lang="ts">
/**
 * CFIR 构念下的子条目树（①②… 与 ①-1…），自己递归渲染下一级。
 * 数据来自 /implementation/cfir 的 constructs[].elements，源头是 tools/cfir_acu_framework.py。
 */
export interface CfirElement {
  elementId: number
  label: string | null
  nameZh: string | null
  nameEn: string | null
  conceptZh: string | null
  conceptEn: string | null
  exampleZh: string | null
  exampleEn: string | null
  originZh: string | null
  originEn: string | null
  source: string | null
  children: CfirElement[]
}

defineProps<{ items: CfirElement[] }>()

const { t } = useI18n()
const { pick } = useBilingual()

/** 示例一行一条 */
const examples = (e: CfirElement) => (pick(e, 'example') || '').split('\n').filter(Boolean)
</script>

<template>
  <ul class="cfir-els">
    <li v-for="e in items" :key="e.elementId">
      <div class="el-h"><span v-if="e.label" class="el-no">{{ e.label }}</span><b>{{ pick(e, 'name') }}</b></div>
      <p v-if="pick(e, 'concept')" class="el-c">{{ pick(e, 'concept') }}</p>
      <p v-for="(x, i) in examples(e)" :key="i" class="el-x"><i>{{ t('implementation.lblExample') }}</i>{{ x }}</p>
      <div v-if="e.source || pick(e, 'origin')" class="el-meta">
        <span v-if="e.source" class="el-src">{{ t('implementation.lblSource') }} {{ e.source }}</span>
        <span v-if="pick(e, 'origin')" class="el-org">{{ pick(e, 'origin') }}</span>
      </div>
      <CfirElements v-if="e.children?.length" :items="e.children" />
    </li>
  </ul>
</template>
