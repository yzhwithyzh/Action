<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="80px">
      <el-form-item label="关键词" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="名称 / 说明 / 地址"
          clearable
          style="width: 220px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="资源状态" clearable style="width: 140px">
          <el-option v-for="dict in sys_normal_disable" :key="dict.value" :label="dict.label" :value="dict.value" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['action:resourceLink:add']">新增</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="success"
          plain
          icon="Edit"
          :disabled="single"
          @click="handleUpdate"
          v-hasPermi="['action:resourceLink:edit']"
        >修改</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="danger"
          plain
          icon="Delete"
          :disabled="multiple"
          @click="handleDelete"
          v-hasPermi="['action:resourceLink:remove']"
        >删除</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-alert type="info" :closable="false" class="mb8" show-icon>
      本表是官网首页第④段「资源中心 · 国际报告规范组织与循证枢纽」的卡片：一条记录一张卡片，
      按「显示顺序」升序排列，<b>访客点击一律在新标签页打开</b>。中英名称与说明各自成对，英文留空时英文界面回落中文。
      栏目自身的标题与导语不在这里，仍在前端多语言文案中。
    </el-alert>

    <el-table v-loading="loading" :data="linkList" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="55" align="center" />
      <el-table-column label="标识图" align="center" width="80">
        <template #default="scope">
          <el-image v-if="scope.row.logoUrl" :src="scope.row.logoUrl" class="link-logo" fit="contain" />
          <span v-else class="link-muted">无</span>
        </template>
      </el-table-column>
      <el-table-column label="名称（中文）" align="left" prop="nameZh" width="180" />
      <el-table-column label="名称（英文）" align="left" prop="nameEn" width="180" />
      <el-table-column label="说明（中文）" align="left" prop="summaryZh" :show-overflow-tooltip="true" />
      <el-table-column label="说明（英文）" align="left" prop="summaryEn" :show-overflow-tooltip="true" />
      <el-table-column label="链接地址" align="left" prop="url" width="240" :show-overflow-tooltip="true">
        <template #default="scope">
          <el-link :href="scope.row.url" target="_blank" rel="noopener noreferrer" type="primary">{{ scope.row.url }}</el-link>
        </template>
      </el-table-column>
      <el-table-column label="显示顺序" align="center" prop="sortNum" width="90" />
      <el-table-column label="状态" align="center" prop="status" width="80">
        <template #default="scope">
          <dict-tag :options="sys_normal_disable" :value="scope.row.status" />
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" width="150" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button
            link
            type="primary"
            icon="Edit"
            @click="handleUpdate(scope.row)"
            v-hasPermi="['action:resourceLink:edit']"
          >修改</el-button>
          <el-button
            link
            type="primary"
            icon="Delete"
            @click="handleDelete(scope.row)"
            v-hasPermi="['action:resourceLink:remove']"
          >删除</el-button>
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

    <!-- 添加或修改资源中心链接对话框 -->
    <el-dialog :title="title" v-model="open" width="720px" append-to-body>
      <el-form ref="linkRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="名称（中）" prop="nameZh">
              <el-input v-model="form.nameZh" placeholder="如：EQUATOR Network" maxlength="200" />
              <div class="form-tip">专名（EQUATOR、Cochrane）中英两栏填同一串即可。</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="名称（英）" prop="nameEn">
              <el-input v-model="form.nameEn" placeholder="e.g. EQUATOR Network" maxlength="300" />
              <div class="form-tip">留空时英文界面回落中文名。</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="说明（中）" prop="summaryZh">
              <el-input v-model="form.summaryZh" placeholder="如：报告规范国际总枢纽" maxlength="500" />
              <div class="form-tip">显示在名称下方的一句话，宜短。</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="说明（英）" prop="summaryEn">
              <el-input v-model="form.summaryEn" placeholder="e.g. Reporting-guideline hub" maxlength="800" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="链接地址" prop="url">
              <el-input v-model="form.url" placeholder="https://www.equator-network.org" maxlength="500" />
              <div class="form-tip">必须是 http:// 或 https:// 开头的完整外部地址，前台一律新标签页打开。</div>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="标识图" prop="logoUrl">
              <!-- 直传阿里云 OSS（action-gmu · 华南3 广州），返回的是公网地址，
                   不走 /common/upload 的本地磁盘通道 —— 官网是静态站，图片不能跟着后端机器走。
                   迁移进来的 6 条用的是随前端打包的 /assets/logo-*.png，不必替换。
                   file-type 与后端 ALLOWED_IMAGE_EXTENSIONS 对齐，**不含 svg**（公网直链 +
                   SVG 可带脚本，后端刻意不放行），这里多列一种只会让用户选完才被拒。 -->
              <image-upload
                v-model="form.logoUrl"
                :limit="1"
                :file-size="5"
                :file-type="['png', 'jpg', 'jpeg', 'webp']"
                :drag="false"
                action="/action/admin/resource-link/logo"
              />
              <div class="form-tip">留空则前台只显示名称与说明，不画图。方形图最佳（前台按 48×48 圆角展示）。</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="显示顺序" prop="sortNum">
              <el-input-number v-model="form.sortNum" :min="0" controls-position="right" style="width: 100%" />
              <div class="form-tip">越小越靠前；留空则自动排到末尾。</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-radio-group v-model="form.status">
                <el-radio v-for="dict in sys_normal_disable" :key="dict.value" :value="dict.value">{{ dict.label }}</el-radio>
              </el-radio-group>
              <div class="form-tip">停用后该卡片从官网首页消失。</div>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注" prop="remark">
              <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="请输入备注" maxlength="500" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" @click="submitForm">确 定</el-button>
          <el-button @click="cancel">取 消</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="ResourceLink">
import {
  listResourceLink,
  getResourceLink,
  addResourceLink,
  updateResourceLink,
  delResourceLink
} from "@/api/system/resourceLink";

const { proxy } = getCurrentInstance();
const { sys_normal_disable } = proxy.useDict("sys_normal_disable");

const linkList = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    keyword: undefined,
    status: undefined
  },
  rules: {
    nameZh: [
      { required: true, message: "中文名称不能为空", trigger: "blur" },
      { max: 200, message: "中文名称不能超过200个字符", trigger: "blur" }
    ],
    url: [
      { required: true, message: "链接地址不能为空", trigger: "blur" },
      {
        pattern: /^https?:\/\/\S+$/,
        message: "必须是 http:// 或 https:// 开头的完整外部地址",
        trigger: "blur"
      }
    ]
  }
});

const { queryParams, form, rules } = toRefs(data);

/** 查询资源中心链接列表 */
function getList() {
  loading.value = true;
  listResourceLink(queryParams.value).then(response => {
    linkList.value = response.rows;
    total.value = response.total;
    loading.value = false;
  });
}

/** 取消按钮 */
function cancel() {
  open.value = false;
  reset();
}

/** 表单重置 */
function reset() {
  form.value = {
    linkId: undefined,
    nameZh: undefined,
    nameEn: undefined,
    summaryZh: undefined,
    summaryEn: undefined,
    url: undefined,
    logoUrl: undefined,
    // 新增时不传 sortNum，后端会自动排到末尾
    sortNum: undefined,
    status: "0",
    remark: undefined
  };
  proxy.resetForm("linkRef");
}

/** 搜索按钮操作 */
function handleQuery() {
  queryParams.value.pageNum = 1;
  getList();
}

/** 重置按钮操作 */
function resetQuery() {
  proxy.resetForm("queryRef");
  handleQuery();
}

/** 多选框选中数据 */
function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.linkId);
  single.value = selection.length != 1;
  multiple.value = !selection.length;
}

/** 新增按钮操作 */
function handleAdd() {
  reset();
  open.value = true;
  title.value = "添加资源链接";
}

/** 修改按钮操作 */
function handleUpdate(row) {
  reset();
  const linkId = row.linkId || ids.value;
  getResourceLink(linkId).then(response => {
    form.value = response.data;
    open.value = true;
    title.value = "修改资源链接";
  });
}

/** 提交按钮 */
function submitForm() {
  proxy.$refs["linkRef"].validate(valid => {
    if (valid) {
      if (form.value.linkId != undefined) {
        updateResourceLink(form.value).then(() => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addResourceLink(form.value).then(() => {
          proxy.$modal.msgSuccess("新增成功");
          open.value = false;
          getList();
        });
      }
    }
  });
}

/** 删除按钮操作 */
function handleDelete(row) {
  const linkIds = row.linkId || ids.value;
  proxy.$modal
    .confirm('是否确认删除资源编号为"' + linkIds + '"的数据项？')
    .then(function () {
      return delResourceLink(linkIds);
    })
    .then(() => {
      getList();
      proxy.$modal.msgSuccess("删除成功");
    })
    .catch(() => {});
}

getList();
</script>

<style scoped>
.link-logo {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  vertical-align: middle;
}
.link-muted {
  font-size: 12px;
  color: #909399;
}
.form-tip {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: #909399;
}
</style>
