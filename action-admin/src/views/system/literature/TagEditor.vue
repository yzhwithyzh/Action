<template>
  <div class="tag-editor">
    <el-tag
      v-for="(item, idx) in list"
      :key="idx"
      closable
      class="tg"
      :disable-transitions="false"
      @close="remove(idx)"
    >{{ item }}</el-tag>
    <el-input
      v-if="adding"
      ref="inputRef"
      v-model="draft"
      class="tg-input"
      size="small"
      @keyup.enter="confirm"
      @blur="confirm"
    />
    <el-button v-else size="small" class="tg-add" @click="startAdd">+ {{ placeholder }}</el-button>
  </div>
</template>

<script setup>
/**
 * 数组字段编辑器：参考文献的 11 个 JSON 列（作者 / 病种 / 干预 / 对照 / 结局 / 穴位…）共用。
 *
 * 【为什么不做成逗号分隔的输入框】这些值本身可能含逗号（「电针，2/100 Hz」「HAMD-17，第4周」），
 * 用逗号切会把一个标签劈成两个，而劈错了在页面上看着完全正常 —— 直到检索时匹配不上。
 *
 * 【顺序有意义】`authors` 的顺序就是署名顺序，任何重排都是学术事故，所以这里只支持
 * 末尾追加与删除，不提供排序。要调顺序就删了重加，让这件事显性发生。
 */
const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  placeholder: { type: String, default: "添加" }
});
const emit = defineEmits(["update:modelValue"]);

const { proxy } = getCurrentInstance();
const adding = ref(false);
const draft = ref("");

const list = computed(() => props.modelValue || []);

function startAdd() {
  adding.value = true;
  nextTick(() => proxy.$refs.inputRef?.focus());
}

function confirm() {
  const v = draft.value.trim();
  // 去重：同一个标签加两遍在检索里没有任何额外意义，只会让展示变脏
  if (v && !list.value.includes(v)) {
    emit("update:modelValue", [...list.value, v]);
  }
  draft.value = "";
  adding.value = false;
}

function remove(idx) {
  const next = [...list.value];
  next.splice(idx, 1);
  emit("update:modelValue", next);
}
</script>

<style scoped>
.tag-editor {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  width: 100%;
}
.tg-input {
  width: 150px;
}
.tg-add {
  border-style: dashed;
}
</style>
