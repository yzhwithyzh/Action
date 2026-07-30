<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="80px">
      <el-form-item label="中文标题" prop="titleZh">
        <el-input
          v-model="queryParams.titleZh"
          placeholder="请输入中文标题"
          clearable
          style="width: 200px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="分类" prop="categoryZh">
        <el-input
          v-model="queryParams.categoryZh"
          placeholder="请输入中文分类"
          clearable
          style="width: 200px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="新闻状态" clearable style="width: 200px">
          <el-option
            v-for="dict in sys_normal_disable"
            :key="dict.value"
            :label="dict.label"
            :value="dict.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="发布日期" style="width: 308px">
        <el-date-picker
          v-model="dateRange"
          value-format="YYYY-MM-DD"
          type="daterange"
          range-separator="-"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button
          type="primary"
          plain
          icon="Plus"
          @click="handleAdd"
          v-hasPermi="['action:news:add']"
        >新增</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="success"
          plain
          icon="Edit"
          :disabled="single"
          @click="handleUpdate"
          v-hasPermi="['action:news:edit']"
        >修改</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="danger"
          plain
          icon="Delete"
          :disabled="multiple"
          @click="handleDelete"
          v-hasPermi="['action:news:remove']"
        >删除</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table v-loading="loading" :data="newsList" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="55" align="center" />
      <el-table-column label="编号" align="center" prop="newsId" width="80" />
      <el-table-column label="缩略图" align="center" prop="thumbUrl" width="100">
        <template #default="scope">
          <image-preview :src="scope.row.thumbUrl" :width="50" :height="50" />
        </template>
      </el-table-column>
      <el-table-column label="中文标题" align="left" prop="titleZh" :show-overflow-tooltip="true" />
      <el-table-column label="英文标题" align="left" prop="titleEn" :show-overflow-tooltip="true" />
      <el-table-column label="分类" align="center" prop="categoryZh" width="120" />
      <el-table-column label="发布日期" align="center" prop="publishDate" width="120" />
      <el-table-column label="置顶" align="center" prop="isTop" width="70">
        <template #default="scope">
          <el-tag v-if="scope.row.isTop === '1'" type="danger">是</el-tag>
          <el-tag v-else type="info">否</el-tag>
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
            v-hasPermi="['action:news:edit']"
          >修改</el-button>
          <el-button
            link
            type="primary"
            icon="Delete"
            @click="handleDelete(scope.row)"
            v-hasPermi="['action:news:remove']"
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

    <!-- 添加或修改官网新闻对话框 -->
    <el-dialog :title="title" v-model="open" width="900px" append-to-body>
      <el-form ref="newsRef" :model="form" :rules="rules" label-width="90px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="中文标题" prop="titleZh">
              <el-input v-model="form.titleZh" placeholder="请输入中文标题" maxlength="300" show-word-limit />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="英文标题" prop="titleEn">
              <el-input v-model="form.titleEn" placeholder="请输入英文标题" maxlength="500" show-word-limit />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="中文分类" prop="categoryZh">
              <el-input v-model="form.categoryZh" placeholder="如：平台动态" maxlength="50" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="英文分类" prop="categoryEn">
              <el-input v-model="form.categoryEn" placeholder="e.g. Platform News" maxlength="50" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="中文摘要" prop="summaryZh">
              <el-input v-model="form.summaryZh" type="textarea" :rows="3" placeholder="请输入中文摘要" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="英文摘要" prop="summaryEn">
              <el-input v-model="form.summaryEn" type="textarea" :rows="3" placeholder="请输入英文摘要" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="发布日期" prop="publishDate">
              <el-date-picker
                v-model="form.publishDate"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择发布日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="显示顺序" prop="sortNum">
              <el-input-number v-model="form.sortNum" :min="0" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="状态" prop="status">
              <el-radio-group v-model="form.status">
                <el-radio
                  v-for="dict in sys_normal_disable"
                  :key="dict.value"
                  :value="dict.value"
                >{{ dict.label }}</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="是否置顶" prop="isTop">
              <el-radio-group v-model="form.isTop">
                <el-radio value="1">是</el-radio>
                <el-radio value="0">否</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="16">
            <el-form-item label="跳转链接" prop="linkUrl">
              <el-input v-model="form.linkUrl" placeholder="站内路由或完整外部URL，留空则跳详情页" maxlength="500" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="外部链接" prop="isExternal">
              <el-radio-group v-model="form.isExternal">
                <el-radio value="1">是</el-radio>
                <el-radio value="0">否</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="16">
            <el-form-item label="缩略图" prop="thumbUrl">
              <image-upload v-model="form.thumbUrl" :limit="1" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="中文正文" prop="contentZh">
              <editor v-model="form.contentZh" :min-height="192" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="英文正文" prop="contentEn">
              <editor v-model="form.contentEn" :min-height="192" />
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

<script setup name="News">
import { listNews, getNews, addNews, updateNews, delNews } from "@/api/system/news";

const { proxy } = getCurrentInstance();
const { sys_normal_disable } = proxy.useDict("sys_normal_disable");

const newsList = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");
const dateRange = ref([]);

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    titleZh: undefined,
    categoryZh: undefined,
    status: undefined
  },
  rules: {
    titleZh: [
      { required: true, message: "中文标题不能为空", trigger: "blur" },
      { max: 300, message: "中文标题不能超过300个字符", trigger: "blur" }
    ]
  }
});

const { queryParams, form, rules } = toRefs(data);

/** 查询官网新闻列表 */
function getList() {
  loading.value = true;
  listNews(proxy.addDateRange(queryParams.value, dateRange.value)).then(response => {
    newsList.value = response.rows;
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
    newsId: undefined,
    categoryZh: undefined,
    categoryEn: undefined,
    titleZh: undefined,
    titleEn: undefined,
    summaryZh: undefined,
    summaryEn: undefined,
    contentZh: undefined,
    contentEn: undefined,
    thumbUrl: undefined,
    linkUrl: undefined,
    isExternal: "0",
    publishDate: undefined,
    isTop: "0",
    sortNum: 0,
    status: "0",
    remark: undefined
  };
  proxy.resetForm("newsRef");
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

/** 多选框选中数据 */
function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.newsId);
  single.value = selection.length != 1;
  multiple.value = !selection.length;
}

/** 新增按钮操作 */
function handleAdd() {
  reset();
  open.value = true;
  title.value = "添加官网新闻";
}

/** 修改按钮操作 */
function handleUpdate(row) {
  reset();
  const newsId = row.newsId || ids.value;
  getNews(newsId).then(response => {
    form.value = response.data;
    open.value = true;
    title.value = "修改官网新闻";
  });
}

/** 提交按钮 */
function submitForm() {
  proxy.$refs["newsRef"].validate(valid => {
    if (valid) {
      if (form.value.newsId != undefined) {
        updateNews(form.value).then(response => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addNews(form.value).then(response => {
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
  const newsIds = row.newsId || ids.value;
  proxy.$modal
    .confirm('是否确认删除新闻编号为"' + newsIds + '"的数据项？')
    .then(function () {
      return delNews(newsIds);
    })
    .then(() => {
      getList();
      proxy.$modal.msgSuccess("删除成功");
    })
    .catch(() => {});
}

getList();
</script>
