<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="80px">
      <el-form-item label="关键词" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="按文案内容或键名搜索"
          clearable
          style="width: 260px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="所在页面" prop="pageKey">
        <el-select v-model="queryParams.pageKey" placeholder="全部页面" clearable style="width: 220px">
          <el-option v-for="g in groups" :key="g.pageKey" :label="g.pageLabel" :value="g.pageKey">
            <span>{{ g.pageLabel }}</span>
            <span class="opt-count">{{ g.changed ? g.changed + " / " : "" }}{{ g.total }}</span>
          </el-option>
        </el-select>
      </el-form-item>
      <el-form-item label="改动" prop="onlyChanged">
        <el-select v-model="queryParams.onlyChanged" placeholder="全部" clearable style="width: 140px">
          <el-option label="只看已改动" :value="true" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-alert type="info" :closable="false" class="mb8" show-icon>
      <template #default>
        这里是官网各页面的文字：标题、导语、正文段落、按钮文字。<b>一条记录对应页面上的一处文字</b>，
        不知道要改哪条时，把官网上看到的那句话复制到「关键词」里搜。
        <br />
        改完保存，<b>访客刷新页面就能看到新文案</b>；但搜索引擎和微信分享卡片看到的还是上次生成的页面，
        要让它们也更新，点下面的「重新生成官网」。
      </template>
    </el-alert>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button
          type="primary"
          plain
          icon="Refresh"
          :loading="rebuild.status === 'running'"
          :disabled="rebuild.status === 'disabled'"
          @click="handleRebuild"
          v-hasPermi="['action:siteText:rebuild']"
        >{{ rebuild.status === "running" ? "正在生成官网…" : "重新生成官网" }}</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="warning"
          plain
          icon="RefreshLeft"
          :disabled="multiple"
          @click="handleRestore"
          v-hasPermi="['action:siteText:edit']"
        >还原所选</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="danger"
          plain
          icon="RefreshLeft"
          @click="handleRestoreAll"
          v-hasPermi="['action:siteText:edit']"
        >全部还原默认</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <!-- 构建状态。disabled 时说明运维还没在后端 .env 里配构建命令，此处如实写明，
         不做成「点了没反应」—— 那种最难排查。 -->
    <el-alert
      v-if="rebuild.status && rebuild.status !== 'idle'"
      :type="rebuildAlertType"
      :closable="false"
      class="mb8"
      show-icon
    >
      <template #title>
        <span>{{ rebuildTitle }}</span>
        <span v-if="rebuild.startedAt" class="rb-meta">
          开始 {{ rebuild.startedAt }}
          <template v-if="rebuild.finishedAt">· 结束 {{ rebuild.finishedAt }}</template>
          <template v-if="rebuild.startedBy">· 触发人 {{ rebuild.startedBy }}</template>
        </span>
      </template>
      <pre v-if="rebuild.message" class="rb-log">{{ rebuild.message }}</pre>
    </el-alert>

    <el-table v-loading="loading" :data="textList" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="55" align="center" />
      <el-table-column label="所在页面" align="center" prop="pageLabel" width="120" />
      <el-table-column label="中文文案" align="left" prop="textZh" min-width="280">
        <template #default="scope">
          <div class="cell-text" :class="{ 'is-changed': scope.row.textZh !== scope.row.defaultZh }">
            {{ scope.row.textZh || "（空）" }}
          </div>
          <div v-if="scope.row.textZh !== scope.row.defaultZh" class="cell-default">
            原文：{{ scope.row.defaultZh || "（空）" }}
          </div>
        </template>
      </el-table-column>
      <el-table-column label="英文文案" align="left" prop="textEn" min-width="280">
        <template #default="scope">
          <div class="cell-text" :class="{ 'is-changed': scope.row.textEn !== scope.row.defaultEn }">
            {{ scope.row.textEn || "（空）" }}
          </div>
          <div v-if="scope.row.textEn !== scope.row.defaultEn" class="cell-default">
            原文：{{ scope.row.defaultEn || "（空）" }}
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" align="center" width="90">
        <template #default="scope">
          <el-tag v-if="isChanged(scope.row)" type="warning" size="small">已改动</el-tag>
          <span v-else class="cell-muted">默认</span>
        </template>
      </el-table-column>
      <el-table-column label="键名" align="left" prop="textKey" width="180">
        <template #default="scope">
          <span class="cell-key">{{ scope.row.textKey }}</span>
          <el-tag v-if="scope.row.hasMarkup === '1'" type="info" size="small" class="ml4">含标签</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" width="150" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['action:siteText:edit']">
            修改
          </el-button>
          <el-button
            link
            type="primary"
            icon="RefreshLeft"
            :disabled="!isChanged(scope.row)"
            @click="handleRestore(scope.row)"
            v-hasPermi="['action:siteText:edit']"
          >还原</el-button>
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

    <!-- 修改文案对话框 -->
    <el-dialog title="修改文案" v-model="open" width="820px" append-to-body>
      <el-form ref="textRef" :model="form" :rules="rules" label-width="96px">
        <el-form-item label="位置">
          <span class="dlg-meta">{{ form.pageLabel }}</span>
          <span class="cell-key ml8">{{ form.textKey }}</span>
        </el-form-item>

        <el-alert v-if="form.hasMarkup === '1'" type="warning" :closable="false" class="mb8" show-icon>
          这条文案里含 HTML 标签（如 <code>&lt;span class="hl"&gt;</code> 的高亮、行内小图标），
          它在官网上是按 HTML 渲染的。改动时请<b>保留原有标签结构</b>，只改中间的文字；
          可用标签仅限 a/span/b/i/em/strong/br/sup/sub/small 与 svg 图标，其余会被后端拒绝；
          <code>&lt;a&gt;</code> 的地址只能是 http(s):// 完整网址、/ 开头的站内路径、#锚点或 mailto:。
        </el-alert>

        <el-form-item label="中文文案" prop="textZh">
          <el-input v-model="form.textZh" type="textarea" :autosize="{ minRows: 2, maxRows: 10 }" maxlength="5000" show-word-limit />
          <div class="form-default">
            <span class="form-default-label">默认：</span>{{ form.defaultZh || "（空）" }}
            <el-button v-if="form.textZh !== form.defaultZh" link type="primary" @click="form.textZh = form.defaultZh">
              用回默认
            </el-button>
          </div>
        </el-form-item>

        <el-form-item label="英文文案" prop="textEn">
          <el-input v-model="form.textEn" type="textarea" :autosize="{ minRows: 2, maxRows: 10 }" maxlength="5000" show-word-limit />
          <div class="form-default">
            <span class="form-default-label">默认：</span>{{ form.defaultEn || "（空）" }}
            <el-button v-if="form.textEn !== form.defaultEn" link type="primary" @click="form.textEn = form.defaultEn">
              用回默认
            </el-button>
          </div>
        </el-form-item>

        <el-form-item label="备注" prop="remark">
          <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="为什么改这条（选填）" maxlength="500" />
        </el-form-item>
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

<script setup name="SiteText">
import {
  listSiteText,
  listSiteTextGroups,
  getSiteText,
  updateSiteText,
  restoreSiteText,
  getSiteRebuildState,
  triggerSiteRebuild
} from "@/api/system/siteText";

const { proxy } = getCurrentInstance();

const textList = ref([]);
const groups = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const multiple = ref(true);
const total = ref(0);
const rebuild = ref({ status: "", message: "" });
// 构建要跑几分钟，页面在 running 时轮询；离开页面时必须清掉，否则定时器留在后台空转
let rebuildTimer = null;

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 20,
    keyword: undefined,
    pageKey: undefined,
    onlyChanged: undefined
  },
  rules: {
    textZh: [{ max: 5000, message: "中文文案不能超过5000个字符", trigger: "blur" }],
    textEn: [{ max: 5000, message: "英文文案不能超过5000个字符", trigger: "blur" }]
  }
});

const { queryParams, form, rules } = toRefs(data);

const rebuildAlertType = computed(() => {
  if (rebuild.value.status === "success") return "success";
  if (rebuild.value.status === "failed") return "error";
  if (rebuild.value.status === "disabled") return "info";
  return "warning";
});

const rebuildTitle = computed(() => {
  switch (rebuild.value.status) {
    case "running":
      return "官网正在重新生成，通常需要几分钟，可以关掉这个页面";
    case "success":
      return "官网已重新生成";
    case "failed":
      return "官网重新生成失败";
    case "disabled":
      return "「重新生成官网」尚未启用";
    default:
      return "";
  }
});

/** 与默认值不同即为「已改动」，判定口径与后端公开接口一致 */
function isChanged(row) {
  return row.textZh !== row.defaultZh || row.textEn !== row.defaultEn;
}

/** 查询站点文案列表 */
function getList() {
  loading.value = true;
  listSiteText(queryParams.value).then(response => {
    textList.value = response.rows;
    total.value = response.total;
    loading.value = false;
  });
}

/** 查询分组词表 */
function getGroups() {
  listSiteTextGroups().then(response => {
    groups.value = response.data || [];
  });
}

/** 查询构建状态；running 时安排下一次轮询 */
function getRebuildState() {
  getSiteRebuildState().then(response => {
    rebuild.value = response.data || { status: "idle" };
    clearTimeout(rebuildTimer);
    if (rebuild.value.status === "running") {
      rebuildTimer = setTimeout(getRebuildState, 5000);
    }
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
    textId: undefined,
    textKey: undefined,
    pageLabel: undefined,
    textZh: undefined,
    textEn: undefined,
    defaultZh: undefined,
    defaultEn: undefined,
    hasMarkup: "0",
    remark: undefined
  };
  proxy.resetForm("textRef");
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
  ids.value = selection.map(item => item.textId);
  multiple.value = !selection.length;
}

/** 修改按钮操作 */
function handleUpdate(row) {
  reset();
  getSiteText(row.textId).then(response => {
    form.value = response.data;
    open.value = true;
  });
}

/** 提交按钮 */
function submitForm() {
  proxy.$refs["textRef"].validate(valid => {
    if (valid) {
      updateSiteText(form.value).then(() => {
        proxy.$modal.msgSuccess("修改成功");
        open.value = false;
        getList();
        getGroups();
      });
    }
  });
}

/** 还原为默认文案；不传 row 时还原选中的多条 */
function handleRestore(row) {
  const textIds = row && row.textId ? row.textId : ids.value.join(",");
  proxy.$modal
    .confirm("确认把选中的 " + (row && row.textId ? 1 : ids.value.length) + " 条文案还原为代码里的默认文案？")
    .then(function () {
      return restoreSiteText(textIds);
    })
    .then(() => {
      getList();
      getGroups();
      proxy.$modal.msgSuccess("已还原");
    })
    .catch(() => {});
}

/** 全部还原：范围是整张表，不只是当前页，所以单独确认一次 */
function handleRestoreAll() {
  proxy.$modal
    .confirm("这会丢弃后台对官网文案的全部改动，把所有文案还原成代码里的默认值。确认继续？")
    .then(function () {
      return restoreSiteText("all");
    })
    .then(() => {
      getList();
      getGroups();
      proxy.$modal.msgSuccess("已全部还原为默认文案");
    })
    .catch(() => {});
}

/** 触发官网重新生成 */
function handleRebuild() {
  proxy.$modal
    .confirm("将按后端配置的命令重新生成官网静态页面，通常需要几分钟。确认开始？")
    .then(function () {
      return triggerSiteRebuild();
    })
    .then(() => {
      proxy.$modal.msgSuccess("已开始重新生成");
      getRebuildState();
    })
    .catch(() => {});
}

onBeforeUnmount(() => clearTimeout(rebuildTimer));

getList();
getGroups();
getRebuildState();
</script>

<style scoped>
.cell-text {
  line-height: 1.6;
  word-break: break-word;
}
.cell-text.is-changed {
  color: #b88230;
  font-weight: 500;
}
.cell-default {
  margin-top: 2px;
  font-size: 12px;
  line-height: 1.5;
  color: #909399;
  word-break: break-word;
}
.cell-key {
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  color: #606266;
}
.cell-muted {
  font-size: 12px;
  color: #909399;
}
.opt-count {
  float: right;
  font-size: 12px;
  color: #909399;
}
.form-default {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: #909399;
  word-break: break-word;
}
.form-default-label {
  color: #c0c4cc;
}
.dlg-meta {
  font-weight: 500;
}
.rb-meta {
  margin-left: 10px;
  font-size: 12px;
  font-weight: 400;
  color: #909399;
}
.rb-log {
  margin: 6px 0 0;
  max-height: 180px;
  overflow: auto;
  font-family: Consolas, Monaco, monospace;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}
.ml4 {
  margin-left: 4px;
}
.ml8 {
  margin-left: 8px;
}
</style>
