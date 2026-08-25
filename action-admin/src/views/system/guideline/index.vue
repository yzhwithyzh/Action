<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="80px">
      <el-form-item label="研究设计" prop="studyType">
        <el-select v-model="queryParams.studyType" placeholder="全部" clearable style="width: 200px" @change="handleQuery">
          <el-option v-for="c in categoryOptions" :key="c.catKey" :label="categoryLabel(c)" :value="c.catKey" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="代号 / 名称 / 简介"
          clearable
          style="width: 220px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="开放状态" prop="releaseState">
        <el-select v-model="queryParams.releaseState" placeholder="全部" clearable style="width: 140px">
          <el-option v-for="s in releaseOptions" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="规范状态" clearable style="width: 140px">
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
        <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['action:guideline:add']">新增</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="success"
          plain
          icon="Edit"
          :disabled="single"
          @click="handleUpdate"
          v-hasPermi="['action:guideline:edit']"
        >修改</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="danger"
          plain
          icon="Delete"
          :disabled="multiple"
          @click="handleDelete"
          v-hasPermi="['action:guideline:remove']"
        >删除</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-alert type="info" :closable="false" class="mb8" show-icon>
      本表驱动官网「报告规范」页的分类导航卡片、在线预览与下载、版本管理三段，改动会直接影响前台。
      「研究设计」决定这份规范归到哪个筛选按钮下，取值来自<b>「规范分类管理」</b>页；逐条 checklist 在<b>「规范条目管理」</b>页维护。
    </el-alert>

    <el-table v-loading="loading" :data="guidelineList" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="55" align="center" />
      <el-table-column label="代号" align="left" prop="code" width="120">
        <template #default="scope"><span class="gl-code">{{ scope.row.code }}</span></template>
      </el-table-column>
      <el-table-column label="名称（中文）" align="left" prop="nameZh" :show-overflow-tooltip="true" />
      <el-table-column label="研究设计" align="center" prop="studyType" width="140">
        <template #default="scope">
          <el-tag v-if="knownCategory(scope.row.studyType)" type="info">{{ studyTypeLabel(scope.row.studyType) }}</el-tag>
          <!-- 分类表里查无此键 = 这份规范在官网既筛不出来、卡片标签也是空白，必须显眼 -->
          <el-tooltip
            v-else-if="scope.row.studyType"
            content="该分类不在「规范分类管理」中，官网筛选条会漏掉这份规范，请改成表内的分类"
          >
            <el-tag type="danger">{{ scope.row.studyType }} ?</el-tag>
          </el-tooltip>
          <span v-else class="gl-muted">未归类</span>
        </template>
      </el-table-column>
      <el-table-column label="版本" align="center" width="180" :show-overflow-tooltip="true">
        <template #default="scope">
          <div>{{ scope.row.versionZh }}</div>
          <div v-if="scope.row.versionEn" class="gl-muted">{{ scope.row.versionEn }}</div>
        </template>
      </el-table-column>
      <el-table-column label="开放状态" align="center" prop="releaseState" width="100">
        <template #default="scope">
          <el-tag :type="releaseTagType(scope.row.releaseState)">{{ releaseLabel(scope.row.releaseState) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="下载 / 原文" align="center" width="130">
        <template #default="scope">
          <span class="gl-links">
            <el-tag v-if="scope.row.fileUrlZh" size="small" type="success">中</el-tag>
            <el-tag v-if="scope.row.fileUrlEn" size="small" type="success">英</el-tag>
            <el-tag v-if="scope.row.externalUrl" size="small">原文</el-tag>
            <span v-if="!scope.row.fileUrlZh && !scope.row.fileUrlEn && !scope.row.externalUrl" class="gl-muted">无</span>
          </span>
        </template>
      </el-table-column>
      <el-table-column label="排序" align="center" prop="sortNum" width="70" />
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
            v-hasPermi="['action:guideline:edit']"
          >修改</el-button>
          <el-button
            link
            type="primary"
            icon="Delete"
            @click="handleDelete(scope.row)"
            v-hasPermi="['action:guideline:remove']"
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

    <!-- 添加或修改报告规范对话框 -->
    <el-dialog :title="title" v-model="open" width="960px" append-to-body>
      <el-form ref="guidelineRef" :model="form" :rules="rules" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="规范代号" prop="code">
              <el-input v-model="form.code" placeholder="如 STRICTA / PRISMA" maxlength="64" />
              <div class="form-tip">全库唯一（不分大小写）。「规范条目管理」按它挂 checklist 条目。</div>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="研究设计" prop="studyType">
              <el-select v-model="form.studyType" placeholder="请选择" clearable style="width: 100%">
                <el-option v-for="c in categoryOptions" :key="c.catKey" :label="categoryLabel(c)" :value="c.catKey" />
              </el-select>
              <div class="form-tip">决定官网上归到哪个筛选按钮；缺分类请先去「规范分类管理」添加。</div>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="显示顺序" prop="sortNum">
              <el-input-number v-model="form.sortNum" :min="0" controls-position="right" style="width: 100%" />
              <div class="form-tip">留空则自动排到目录末尾。</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="名称（中）" prop="nameZh">
              <el-input v-model="form.nameZh" placeholder="如：STRICTA（针刺临床试验干预措施报告标准）" maxlength="300" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="名称（英）" prop="nameEn">
              <el-input v-model="form.nameEn" placeholder="e.g. STRICTA (Standards for Reporting…)" maxlength="500" />
              <div class="form-tip">留空时英文界面回落中文名。</div>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="简介（中）" prop="summaryZh">
              <el-input v-model="form.summaryZh" type="textarea" :rows="3" placeholder="分类卡片与下载面板都用这段" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="简介（英）" prop="summaryEn">
              <el-input v-model="form.summaryEn" type="textarea" :rows="3" placeholder="Shown on the card and the download panel" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="版本（中）" prop="versionZh">
              <el-input v-model="form.versionZh" placeholder="如：2010 修订 · 6 领域 / 17 条目" maxlength="64" />
              <div class="form-tip">原样显示在卡片与版本管理表里，不做解析。</div>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="版本（英）" prop="versionEn">
              <el-input v-model="form.versionEn" placeholder="e.g. Revised 2010 · 6 domains / 17 items" maxlength="64" />
              <div class="form-tip">留空时英文界面回落中文版本号（会原样显示中文）。</div>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="开放状态" prop="releaseState">
              <el-select v-model="form.releaseState" placeholder="请选择" style="width: 100%">
                <el-option v-for="s in releaseOptions" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="中文版下载" prop="fileUrlZh">
              <!-- 直传阿里云 OSS（action-gmu · 华南3 广州），存进库里的是公网直链，
                   不走 /common/upload 的本地磁盘通道 —— 官网是静态站，文件不能跟着后端机器走 -->
              <file-upload
                v-model="form.fileUrlZh"
                :limit="1"
                :file-size="30"
                :file-type="['pdf']"
                :drag="false"
                action="/action/admin/guideline/file"
              />
              <div class="form-tip">留空则前台不显示「中文版」下载按钮。</div>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="英文版下载" prop="fileUrlEn">
              <file-upload
                v-model="form.fileUrlEn"
                :limit="1"
                :file-size="30"
                :file-type="['pdf']"
                :drag="false"
                action="/action/admin/guideline/file"
              />
              <div class="form-tip">留空则前台不显示「英文版」下载按钮。</div>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="外部原文链接" prop="externalUrl">
              <el-input v-model="form.externalUrl" placeholder="如 https://doi.org/10.1136/bmjebm-2025-113641" maxlength="500" />
              <div class="form-tip">三个链接全空时，前台的「下载与原文」整块不渲染。</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="标识图" prop="logoUrl">
              <el-input v-model="form.logoUrl" placeholder="规范 logo 地址，可留空" maxlength="300" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-radio-group v-model="form.status">
                <el-radio v-for="dict in sys_normal_disable" :key="dict.value" :value="dict.value">{{ dict.label }}</el-radio>
              </el-radio-group>
              <div class="form-tip">停用后官网不再展示这份规范。</div>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注" prop="remark">
              <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="仅后台可见" maxlength="500" />
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

<script setup name="Guideline">
import {
  listGuideline,
  getGuideline,
  addGuideline,
  updateGuideline,
  delGuideline,
  listGuidelineCategory
} from "@/api/system/guideline";

const { proxy } = getCurrentInstance();
const { sys_normal_disable } = proxy.useDict("sys_normal_disable");

/** 与后端 GuidelineModel.release_state 的 Literal 一一对应，只有三态，不值得为它建一条字典 */
const releaseOptions = [
  { value: "open", label: "开放" },
  { value: "beta", label: "内测" },
  { value: "soon", label: "即将上线" }
];

const guidelineList = ref([]);
/** 「研究设计」下拉的取值域，来自 action_guideline_category */
const categoryOptions = ref([]);
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
    studyType: undefined,
    keyword: undefined,
    releaseState: undefined,
    status: undefined
  },
  rules: {
    code: [
      { required: true, message: "规范代号不能为空", trigger: "blur" },
      { max: 64, message: "规范代号不能超过64个字符", trigger: "blur" }
    ],
    nameZh: [
      { required: true, message: "中文名称不能为空", trigger: "blur" },
      { max: 300, message: "中文名称不能超过300个字符", trigger: "blur" }
    ]
  }
});

const { queryParams, form, rules } = toRefs(data);

function categoryLabel(cat) {
  return cat.nameEn ? `${cat.nameZh}（${cat.nameEn}）` : cat.nameZh;
}

function knownCategory(studyType) {
  return categoryOptions.value.some(c => c.catKey === studyType);
}

function studyTypeLabel(studyType) {
  const hit = categoryOptions.value.find(c => c.catKey === studyType);
  return hit ? hit.nameZh : studyType;
}

function releaseLabel(state) {
  const hit = releaseOptions.find(s => s.value === state);
  return hit ? hit.label : state || "—";
}

function releaseTagType(state) {
  if (state === "open") return "success";
  if (state === "beta") return "warning";
  return "info";
}

/** 取分类下拉的取值域。停用的分类也取回来，否则历史数据会被误标成「查无此键」 */
function getCategories() {
  return listGuidelineCategory({ pageNum: 1, pageSize: 200 }).then(response => {
    categoryOptions.value = response.rows || [];
  });
}

/** 查询报告规范列表 */
function getList() {
  loading.value = true;
  listGuideline(queryParams.value).then(response => {
    guidelineList.value = response.rows;
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
    guidelineId: undefined,
    code: undefined,
    nameZh: undefined,
    nameEn: undefined,
    studyType: queryParams.value.studyType || undefined,
    summaryZh: undefined,
    summaryEn: undefined,
    versionZh: undefined,
    versionEn: undefined,
    fileUrlZh: undefined,
    fileUrlEn: undefined,
    externalUrl: undefined,
    logoUrl: undefined,
    releaseState: "open",
    // 新增时不传 sortNum，后端会自动排到目录末尾
    sortNum: undefined,
    status: "0",
    remark: undefined
  };
  proxy.resetForm("guidelineRef");
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
  ids.value = selection.map(item => item.guidelineId);
  single.value = selection.length != 1;
  multiple.value = !selection.length;
}

/** 新增按钮操作 */
function handleAdd() {
  reset();
  open.value = true;
  title.value = "添加报告规范";
}

/** 修改按钮操作 */
function handleUpdate(row) {
  reset();
  const guidelineId = row.guidelineId || ids.value;
  getGuideline(guidelineId).then(response => {
    form.value = response.data;
    open.value = true;
    title.value = "修改报告规范";
  });
}

/** 提交按钮 */
function submitForm() {
  proxy.$refs["guidelineRef"].validate(valid => {
    if (valid) {
      if (form.value.guidelineId != undefined) {
        updateGuideline(form.value).then(() => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addGuideline(form.value).then(() => {
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
  const guidelineIds = row.guidelineId || ids.value;
  proxy.$modal
    .confirm('是否确认删除规范编号为"' + guidelineIds + '"的数据项？该规范的 checklist 条目不会一并删除。')
    .then(function () {
      return delGuideline(guidelineIds);
    })
    .then(() => {
      getList();
      proxy.$modal.msgSuccess("删除成功");
    })
    .catch(() => {});
}

// 列表里要靠分类表判断「研究设计」是否有效，先取分类再取列表
getCategories().finally(getList);
</script>

<style scoped>
.gl-code {
  font-family: Consolas, Monaco, monospace;
  font-weight: 600;
}
.gl-links {
  display: inline-flex;
  gap: 4px;
}
.gl-muted {
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
