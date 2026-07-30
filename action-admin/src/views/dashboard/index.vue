<template>
  <div class="welcome">
    <div class="welcome-card">
      <div class="brand">ACTION</div>
      <div class="brand-full">
        ACupuncTure Intelligent helper ON clinical research
      </div>
      <h1 class="greeting">{{ greeting }}，{{ displayName }}</h1>
      <p class="subtitle">欢迎使用 ACTION 管理系统</p>
      <p class="desc">
        针刺临床研究智能平台 · 报告规范 · 智能工具 · 培训与协作
      </p>
    </div>
  </div>
</template>

<script setup>
import useUserStore from "@/store/modules/user";

defineOptions({
  name: "DashBoard",
});

const userStore = useUserStore();

const displayName = computed(
  () => userStore.nickName || userStore.name || "研究者"
);

const greeting = computed(() => {
  const hour = new Date().getHours();
  if (hour < 6) return "夜深了";
  if (hour < 12) return "早上好";
  if (hour < 14) return "中午好";
  if (hour < 18) return "下午好";
  return "晚上好";
});
</script>

<style scoped lang="less">
.welcome {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - 130px);
  padding: 24px;
}

.welcome-card {
  width: 100%;
  max-width: 720px;
  padding: 56px 48px;
  text-align: center;
  background-color: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  box-shadow: var(--el-box-shadow-light);
}

.brand {
  font-size: 40px;
  font-weight: 600;
  letter-spacing: 6px;
  color: var(--el-color-primary);
}

.brand-full {
  margin-top: 8px;
  font-size: 13px;
  letter-spacing: 1px;
  color: var(--el-text-color-secondary);
}

.greeting {
  margin: 32px 0 0;
  font-size: 24px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.subtitle {
  margin: 12px 0 0;
  font-size: 16px;
  color: var(--el-text-color-regular);
}

.desc {
  margin: 24px 0 0;
  font-size: 14px;
  line-height: 22px;
  color: var(--el-text-color-secondary);
}

@media screen and (max-width: 576px) {
  .welcome-card {
    padding: 40px 24px;
  }
  .brand {
    font-size: 32px;
  }
}
</style>
