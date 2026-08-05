<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="80px">
      <el-form-item label="所属规范" prop="guidelineId">
        <el-select v-model="queryParams.guidelineId" placeholder="全部规范" clearable style="width: 240px" @change="handleQuery">
          <el-option
            v-for="g in guidelineOptions"
            :key="g.guidelineId"
            :label="g.code + ' · ' + g.nameZh"
            :value="g.guidelineId"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="清单表" prop="partNo">
        <el-select v-model="queryParams.partNo" placeholder="全部" clearable style="width: 200px" @change="handleQuery">
          <el-option v-for="p in partOptions" :key="p.partNo" :label="p.label" :value="p.partNo" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="条目号 / 领域 / 条目内容"
          clearable
          style="width: 220px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="条目状态" clearable style="width: 140px">
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
        <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['action:guidelineItem:add']">新增</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="success"
          plain
          icon="Edit"
          :disabled="single"
          @click="handleUpdate"
          v-hasPermi="['action:guidelineItem:edit']"
        >修改</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="danger"
          plain
          icon="Delete"
          :disabled="multiple"
          @click="handleDelete"
          v-hasPermi="['action:guidelineItem:remove']"
        >删除</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-alert type="info" :closable="false" class="mb8" show-icon>
      条目是报告助手第二步（结构化模板）与第三步（逐条校验）共用的数据源，改动会直接影响官网前台。
    </el-alert>

    <el-table v-loading="loading" :data="itemList" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="55" align="center" />
      <el-table-column label="规范" align="center" prop="guidelineId" width="100">
        <template #default="scope">{{ guidelineCode(scope.row.guidelineId) }}</template>
      </el-table-column>
      <el-table-column label="表" align="center" prop="partNo" width="60" />
      <el-table-column label="条目号" align="center" prop="itemNoZh" width="90" />
      <el-table-column label="领域" align="left" prop="domainZh" width="180" :show-overflow-tooltip="true" />
      <el-table-column label="条目内容（中文）" align="left" prop="contentZh" :show-overflow-tooltip="true" />
      <el-table-column label="扩展 / 对照" align="left" prop="extensionZh" width="220" :show-overflow-tooltip="true" />
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
            v-hasPermi="['action:guidelineItem:edit']"
          >修改</el-button>
          <el-button
            link
            type="primary"
            icon="Delete"
            @click="handleDelete(scope.row)"
            v-hasPermi="['action:guidelineItem:remove']"
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

    <!-- 添加或修改规范条目对话框 -->
    <el-dialog :title="title" v-model="open" width="900px" append-to-body>
      <el-form ref="itemRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="所属规范" prop="guidelineId">
              <el-select v-model="form.guidelineId" placeholder="请选择规范" style="width: 100%">
                <el-option
                  v-for="g in guidelineOptions"
                  :key="g.guidelineId"
                  :label="g.code + ' · ' + g.nameZh"
                  :value="g.guidelineId"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="清单表序号" prop="partNo">
              <el-input-number v-model="form.partNo" :min="1" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="显示顺序" prop="sortNum">
              <el-input-number v-model="form.sortNum" :min="0" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="表标题（中）" prop="partZh">
              <el-input v-model="form.partZh" placeholder="如：STRICTA 2010 清单" maxlength="300" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="表标题（英）" prop="partEn">
              <el-input v-model="form.partEn" placeholder="e.g. STRICTA 2010 Checklist" maxlength="500" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="领域（中）" prop="domainZh">
              <el-input v-model="form.domainZh" placeholder="如：方法：试验设计" maxlength="300" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="领域（英）" prop="domainEn">
              <el-input v-model="form.domainEn" placeholder="e.g. Methods: Trial design" maxlength="500" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="条目号（中）" prop="itemNoZh">
              <el-input v-model="form.itemNoZh" placeholder="如 1a；无编号可留空" maxlength="64" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="条目号（英）" prop="itemNoEn">
              <el-input v-model="form.itemNoEn" placeholder="通常与中文一致" maxlength="64" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="条目内容（中）" prop="contentZh">
              <el-input v-model="form.contentZh" type="textarea" :rows="3" placeholder="请输入中文条目内容" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="条目内容（英）" prop="contentEn">
              <el-input v-model="form.contentEn" type="textarea" :rows="3" placeholder="请输入英文条目内容" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="扩展列名（中）" prop="extLabelZh">
              <el-input v-model="form.extLabelZh" placeholder="如：非药物临床试验扩展条目" maxlength="200" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="扩展列名（英）" prop="extLabelEn">
              <el-input v-model="form.extLabelEn" placeholder="e.g. Extension for NPT trials" maxlength="300" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="扩展内容（中）" prop="extensionZh">
              <el-input v-model="form.extensionZh" type="textarea" :rows="2" placeholder="无扩展内容时填 — 或留空" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="扩展内容（英）" prop="extensionEn">
              <el-input v-model="form.extensionEn" type="textarea" :rows="2" placeholder="无扩展内容时填 — 或留空" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-radio-group v-model="form.status">
                <el-radio v-for="dict in sys_normal_disable" :key="dict.value" :value="dict.value">{{ dict.label }}</el-radio>
              </el-radio-group>
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

<script setup name="GuidelineItem">
import {
  listGuideline,
  listGuidelineItem,
  getGuidelineItem,
  addGuidelineItem,
  updateGuidelineItem,
  delGuidelineItem
} from "@/api/system/guidelineItem";

const { proxy } = getCurrentInstance();
const { sys_normal_disable } = proxy.useDict("sys_normal_disable");

const itemList = ref([]);
const guidelineOptions = ref([]);
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
    guidelineId: undefined,
    partNo: undefined,
    keyword: undefined,
    status: undefined
  },
  rules: {
    guidelineId: [{ required: true, message: "所属规范不能为空", trigger: "change" }],
    contentZh: [{ required: true, message: "中文条目内容不能为空", trigger: "blur" }],
    itemNoZh: [{ max: 64, message: "条目号不能超过64个字符", trigger: "blur" }]
  }
});

const { queryParams, form, rules } = toRefs(data);

/** 清单表下拉：一份规范可能含多张表（RCT = CONSORT 主表 + 摘要表 + STRICTA 表），
 *  选定规范后才有意义，选项从当前页数据里归纳，避免为此再加一个接口。 */
const partOptions = computed(() => {
  const seen = new Map();
  itemList.value.forEach(it => {
    if (it.partNo != null && !seen.has(it.partNo)) {
      seen.set(it.partNo, { partNo: it.partNo, label: it.partNo + " · " + (it.partZh || "") });
    }
  });
  return [...seen.values()].sort((a, b) => a.partNo - b.partNo);
});

/** 列表里只存 guidelineId，展示时换成规范代号 */
function guidelineCode(guidelineId) {
  const hit = guidelineOptions.value.find(g => g.guidelineId === guidelineId);
  return hit ? hit.code : guidelineId;
}

/** 查询规范条目列表 */
function getList() {
  loading.value = true;
  listGuidelineItem(queryParams.value).then(response => {
    itemList.value = response.rows;
    total.value = response.total;
    loading.value = false;
  });
}

/** 拉规范目录，供筛选与表单下拉使用 */
function getGuidelines() {
  listGuideline({ pageNum: 1, pageSize: 100 }).then(response => {
    guidelineOptions.value = response.rows || [];
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
    itemId: undefined,
    guidelineId: queryParams.value.guidelineId,
    partNo: 1,
    partZh: undefined,
    partEn: undefined,
    domainZh: undefined,
    domainEn: undefined,
    itemNoZh: undefined,
    itemNoEn: undefined,
    contentZh: undefined,
    contentEn: undefined,
    extLabelZh: undefined,
    extLabelEn: undefined,
    extensionZh: undefined,
    extensionEn: undefined,
    // 新增时不传 sortNum，后端会自动排到该规范末尾
    sortNum: undefined,
    status: "0",
    remark: undefined
  };
  proxy.resetForm("itemRef");
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
  ids.value = selection.map(item => item.itemId);
  single.value = selection.length != 1;
  multiple.value = !selection.length;
}

/** 新增按钮操作 */
function handleAdd() {
  reset();
  open.value = true;
  title.value = "添加规范条目";
}

/** 修改按钮操作 */
function handleUpdate(row) {
  reset();
  const itemId = row.itemId || ids.value;
  getGuidelineItem(itemId).then(response => {
    form.value = response.data;
    open.value = true;
    title.value = "修改规范条目";
  });
}

/** 提交按钮 */
function submitForm() {
  proxy.$refs["itemRef"].validate(valid => {
    if (valid) {
      if (form.value.itemId != undefined) {
        updateGuidelineItem(form.value).then(() => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addGuidelineItem(form.value).then(() => {
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
  const itemIds = row.itemId || ids.value;
  proxy.$modal
    .confirm('是否确认删除条目编号为"' + itemIds + '"的数据项？')
    .then(function () {
      return delGuidelineItem(itemIds);
    })
    .then(() => {
      getList();
      proxy.$modal.msgSuccess("删除成功");
    })
    .catch(() => {});
}

getGuidelines();
getList();
</script>
