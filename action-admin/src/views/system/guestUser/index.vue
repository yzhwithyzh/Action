<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="80px">
      <el-form-item label="关键词" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="邮箱 / 用户名 / 机构 / 职位"
          clearable
          style="width: 240px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="账号状态" clearable style="width: 140px">
          <el-option v-for="dict in sys_normal_disable" :key="dict.value" :label="dict.label" :value="dict.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="注册时间" style="width: 308px">
        <el-date-picker
          v-model="dateRange"
          value-format="YYYY-MM-DD"
          type="daterange"
          range-separator="-"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
        ></el-date-picker>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-alert type="info" :closable="false" class="mb8" show-icon>
      这里是在官网自助注册的访客账号，与「用户管理」里的后台账号分开管理：访客不能登录后台，后台也不能给访客分配角色。
      <b>停用即时生效</b>，访客已登录的会话在下一次操作时被拒。这里不提供重置密码，访客忘记密码请在官网登录页走「忘记密码」。
    </el-alert>

    <el-table v-loading="loading" :data="guestList">
      <el-table-column label="邮箱" align="left" prop="email" min-width="200" :show-overflow-tooltip="true" />
      <el-table-column label="用户名" align="left" prop="nickName" width="140" :show-overflow-tooltip="true" />
      <el-table-column label="所属机构" align="left" prop="institution" min-width="180" :show-overflow-tooltip="true" />
      <el-table-column label="职位" align="left" prop="position" width="120" :show-overflow-tooltip="true" />
      <el-table-column label="名下工作" align="center" width="210">
        <template #default="scope">
          <span class="work">草稿 {{ scope.row.draftCount }}</span>
          <span class="work">SRD {{ scope.row.srdCount }}</span>
          <span class="work">校验 {{ scope.row.reviewCount }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" align="center" width="90">
        <template #default="scope">
          <el-switch
            v-model="scope.row.status"
            active-value="0"
            inactive-value="1"
            :disabled="!canEdit"
            @change="handleStatusChange(scope.row)"
          ></el-switch>
        </template>
      </el-table-column>
      <el-table-column label="最后登录" align="center" prop="loginDate" width="160">
        <template #default="scope">
          <span>{{ scope.row.loginDate ? parseTime(scope.row.loginDate) : '从未登录' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="注册时间" align="center" prop="createTime" width="160">
        <template #default="scope">
          <span>{{ parseTime(scope.row.createTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" width="90" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="handleView(scope.row)" v-hasPermi="['action:guestUser:query']">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <pagination
      v-show="total > 0"
      :total="total"
      v-model:page="queryParams.pageNum"
      v-model:limit="queryParams.pageSize"
      @pagination="getList"
    />

    <!-- 访客详情 -->
    <el-dialog title="访客详情" v-model="open" width="640px" append-to-body>
      <el-descriptions v-if="detail" :column="2" border>
        <el-descriptions-item label="邮箱" :span="2">{{ detail.email }}</el-descriptions-item>
        <el-descriptions-item label="用户名">{{ detail.nickName || '—' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <dict-tag :options="sys_normal_disable" :value="detail.status === '1' ? '1' : '0'" />
        </el-descriptions-item>
        <el-descriptions-item label="所属机构" :span="2">{{ detail.institution || '—' }}</el-descriptions-item>
        <el-descriptions-item label="职位" :span="2">{{ detail.position || '—' }}</el-descriptions-item>
        <el-descriptions-item label="注册时间">{{ parseTime(detail.createTime) }}</el-descriptions-item>
        <el-descriptions-item label="密码更新">{{ detail.pwdUpdateDate ? parseTime(detail.pwdUpdateDate) : '—' }}</el-descriptions-item>
        <el-descriptions-item label="最后登录">{{ detail.loginDate ? parseTime(detail.loginDate) : '从未登录' }}</el-descriptions-item>
        <el-descriptions-item label="登录 IP">{{ detail.loginIp || '—' }}</el-descriptions-item>
        <el-descriptions-item label="报告草稿">{{ detail.draftCount }}</el-descriptions-item>
        <el-descriptions-item label="SRD 评估">{{ detail.srdCount }}</el-descriptions-item>
        <el-descriptions-item label="稿件校验">{{ detail.reviewCount }}</el-descriptions-item>
        <el-descriptions-item label="背景生成">{{ detail.backgroundCount }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="open = false">关 闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="GuestUser">
import { listGuestUser, getGuestUser, changeGuestUserStatus } from "@/api/system/guestUser";
import { checkPermi } from "@/utils/permission";

const { proxy } = getCurrentInstance();
const { sys_normal_disable } = proxy.useDict("sys_normal_disable");

const guestList = ref([]);
const loading = ref(true);
const showSearch = ref(true);
const total = ref(0);
const dateRange = ref([]);
const open = ref(false);
const detail = ref(null);
const canEdit = checkPermi(["action:guestUser:edit"]);

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    keyword: undefined,
    status: undefined
  }
});

const { queryParams } = toRefs(data);

/** 查询访客列表 */
function getList() {
  loading.value = true;
  listGuestUser(proxy.addDateRange(queryParams.value, dateRange.value)).then(response => {
    // status 为 NULL 的历史账号按正常处理（与后端 is_guest_account_disabled 同一口径：只有 '1' 算停用）
    guestList.value = response.rows.map(row => ({ ...row, status: row.status === "1" ? "1" : "0" }));
    total.value = response.total;
    loading.value = false;
  });
}

/** 搜索按钮操作 */
function handleQuery() {
  queryParams.value.pageNum = 1;
  getList();
}

/** 重置按钮操作 */
function resetQuery() {
  dateRange.value = [];
  proxy.resetForm("queryRef");
  handleQuery();
}

/** 停用 / 启用 */
function handleStatusChange(row) {
  const text = row.status === "0" ? "启用" : "停用";
  proxy.$modal
    .confirm('确认要' + text + '访客"' + row.email + '"吗？' + (row.status === "1" ? "停用后该访客会立即被登出、无法再登录。" : ""))
    .then(function () {
      return changeGuestUserStatus(row.userId, row.status);
    })
    .then(() => {
      proxy.$modal.msgSuccess(text + "成功");
    })
    .catch(function () {
      row.status = row.status === "0" ? "1" : "0";
    });
}

/** 详情 */
function handleView(row) {
  detail.value = null;
  getGuestUser(row.userId).then(response => {
    detail.value = response.data;
    open.value = true;
  });
}

getList();
</script>

<style scoped>
.work {
  display: inline-block;
  margin: 0 4px;
  font-size: 12px;
  color: #606266;
}
</style>
