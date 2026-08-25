<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="80px">
      <el-form-item label="关键词" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="标识 / 中英名称"
          clearable
          style="width: 220px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="分类状态" clearable style="width: 140px">
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
        <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['action:guidelineCategory:add']">新增</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="success"
          plain
          icon="Edit"
          :disabled="single"
          @click="handleUpdate"
          v-hasPermi="['action:guidelineCategory:edit']"
        >修改</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="danger"
          plain
          icon="Delete"
          :disabled="multiple"
          @click="handleDelete"
          v-hasPermi="['action:guidelineCategory:remove']"
        >删除</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-alert type="info" :closable="false" class="mb8" show-icon>
      本表是官网「报告规范」页第①段筛选条的词表：每条分类对应一个筛选按钮，卡片上的「研究设计」标签与图标也取自这里。
      <b>分类标识就是规范目录里「研究设计」字段的取值</b>，两边靠它对上，所以分类下已有规范时不允许再改标识（改名称不受限）。
      顺序按「显示顺序」升序，「全部」按钮由前台固定排在最前、不占一条记录。
    </el-alert>

    <el-table v-loading="loading" :data="categoryList" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="55" align="center" />
      <el-table-column label="图标" align="center" width="70">
        <template #default="scope">
          <svg
            v-if="iconPathList(scope.row.iconPaths).length"
            class="cat-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.7"
          >
            <path v-for="(d, i) in iconPathList(scope.row.iconPaths)" :key="i" :d="d" />
          </svg>
          <span v-else class="cat-muted">无</span>
        </template>
      </el-table-column>
      <el-table-column label="分类标识" align="left" prop="catKey" width="140">
        <template #default="scope"><span class="cat-key">{{ scope.row.catKey }}</span></template>
      </el-table-column>
      <el-table-column label="名称（中文）" align="left" prop="nameZh" width="180" />
      <el-table-column label="名称（英文）" align="left" prop="nameEn" width="200" />
      <el-table-column label="备注" align="left" prop="remark" :show-overflow-tooltip="true" />
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
            v-hasPermi="['action:guidelineCategory:edit']"
          >修改</el-button>
          <el-button
            link
            type="primary"
            icon="Delete"
            @click="handleDelete(scope.row)"
            v-hasPermi="['action:guidelineCategory:remove']"
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

    <!-- 添加或修改报告规范分类对话框 -->
    <el-dialog :title="title" v-model="open" width="720px" append-to-body>
      <el-form ref="categoryRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="分类标识" prop="catKey">
              <el-input
                v-model="form.catKey"
                placeholder="如 rct / protocol / sr"
                maxlength="32"
                :disabled="form.catId != undefined"
              />
              <div class="form-tip">
                小写字母、数字、下划线与连字符。规范目录里的「研究设计」存的就是这个值，
                <b>建好之后不可再改</b>（改了会让已挂在它下面的规范从前台筛选条上消失）。
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="显示顺序" prop="sortNum">
              <el-input-number v-model="form.sortNum" :min="0" controls-position="right" style="width: 100%" />
              <div class="form-tip">筛选条中的位置，越小越靠前；留空则自动排到末尾。</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="名称（中）" prop="nameZh">
              <el-input v-model="form.nameZh" placeholder="如：随机对照试验" maxlength="200" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="名称（英）" prop="nameEn">
              <el-input v-model="form.nameEn" placeholder="e.g. RCT" maxlength="300" />
              <div class="form-tip">留空时英文界面回落中文名。</div>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="图标 path" prop="iconPaths">
              <el-input
                v-model="form.iconPaths"
                type="textarea"
                :rows="4"
                placeholder="每行一条 SVG &lt;path&gt; 的 d 属性，留空则前台不画图标"
              />
              <div class="form-tip">
                画布为 24×24、描边式图标（fill="none" / stroke-width 1.7）。示例：<code>M4 5h16M4 5v14M4 19h16</code>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="图标预览">
              <svg
                v-if="previewPaths.length"
                class="cat-icon cat-icon-lg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.7"
              >
                <path v-for="(d, i) in previewPaths" :key="i" :d="d" />
              </svg>
              <span v-else class="cat-muted">未填写 path</span>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-radio-group v-model="form.status">
                <el-radio v-for="dict in sys_normal_disable" :key="dict.value" :value="dict.value">{{ dict.label }}</el-radio>
              </el-radio-group>
              <div class="form-tip">停用后该筛选按钮从官网消失，挂在它下面的规范也会跟着筛不出来。</div>
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

<script setup name="GuidelineCategory">
import {
  listGuidelineCategory,
  getGuidelineCategory,
  addGuidelineCategory,
  updateGuidelineCategory,
  delGuidelineCategory
} from "@/api/system/guidelineCategory";

const { proxy } = getCurrentInstance();
const { sys_normal_disable } = proxy.useDict("sys_normal_disable");

const categoryList = ref([]);
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
    catKey: [
      { required: true, message: "分类标识不能为空", trigger: "blur" },
      {
        pattern: /^[a-z0-9_-]+$/,
        message: "只能包含小写字母、数字、下划线与连字符",
        trigger: "blur"
      }
    ],
    nameZh: [
      { required: true, message: "中文名称不能为空", trigger: "blur" },
      { max: 200, message: "中文名称不能超过200个字符", trigger: "blur" }
    ]
  }
});

const { queryParams, form, rules } = toRefs(data);

/** 一行一条 path，前台也是这么拆的 */
function iconPathList(iconPaths) {
  if (!iconPaths) return [];
  return iconPaths
    .split("\n")
    .map(d => d.trim())
    .filter(Boolean);
}

const previewPaths = computed(() => iconPathList(form.value.iconPaths));

/** 查询报告规范分类列表 */
function getList() {
  loading.value = true;
  listGuidelineCategory(queryParams.value).then(response => {
    categoryList.value = response.rows;
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
    catId: undefined,
    catKey: undefined,
    nameZh: undefined,
    nameEn: undefined,
    iconPaths: undefined,
    // 新增时不传 sortNum，后端会自动排到筛选条末尾
    sortNum: undefined,
    status: "0",
    remark: undefined
  };
  proxy.resetForm("categoryRef");
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
  ids.value = selection.map(item => item.catId);
  single.value = selection.length != 1;
  multiple.value = !selection.length;
}

/** 新增按钮操作 */
function handleAdd() {
  reset();
  open.value = true;
  title.value = "添加规范分类";
}

/** 修改按钮操作 */
function handleUpdate(row) {
  reset();
  const catId = row.catId || ids.value;
  getGuidelineCategory(catId).then(response => {
    form.value = response.data;
    open.value = true;
    title.value = "修改规范分类";
  });
}

/** 提交按钮 */
function submitForm() {
  proxy.$refs["categoryRef"].validate(valid => {
    if (valid) {
      if (form.value.catId != undefined) {
        updateGuidelineCategory(form.value).then(() => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addGuidelineCategory(form.value).then(() => {
          proxy.$modal.msgSuccess("新增成功");
          open.value = false;
          getList();
        });
      }
    }
  });
}

/** 删除按钮操作 —— 分类下还有规范时后端会拒绝，提示照原样弹出 */
function handleDelete(row) {
  const catIds = row.catId || ids.value;
  proxy.$modal
    .confirm('是否确认删除分类编号为"' + catIds + '"的数据项？')
    .then(function () {
      return delGuidelineCategory(catIds);
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
.cat-icon {
  width: 24px;
  height: 24px;
  color: #409eff;
  vertical-align: middle;
}
.cat-icon-lg {
  width: 44px;
  height: 44px;
}
.cat-key {
  font-family: Consolas, Monaco, monospace;
}
.cat-muted {
  font-size: 12px;
  color: #909399;
}
.form-tip {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: #909399;
}
.form-tip code {
  padding: 0 4px;
  background: #f5f7fa;
  border-radius: 3px;
}
</style>
