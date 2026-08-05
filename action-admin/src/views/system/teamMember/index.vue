<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="80px">
      <el-form-item label="所属组" prop="groupKey">
        <el-select v-model="queryParams.groupKey" placeholder="全部" clearable style="width: 200px" @change="handleQuery">
          <el-option v-for="g in groupOptions" :key="g.value" :label="g.label" :value="g.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="姓名 / 机构 / 简介"
          clearable
          style="width: 220px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="成员状态" clearable style="width: 140px">
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
        <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['action:teamMember:add']">新增</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="success"
          plain
          icon="Edit"
          :disabled="single"
          @click="handleUpdate"
          v-hasPermi="['action:teamMember:edit']"
        >修改</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="danger"
          plain
          icon="Delete"
          :disabled="multiple"
          @click="handleDelete"
          v-hasPermi="['action:teamMember:remove']"
        >删除</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-alert type="info" :closable="false" class="mb8" show-icon>
      本表驱动官网「关于我们 → 如何组织」的成员名单与 /team/&#123;id&#125; 成员详情页，改动会直接影响前台。
      头像上传后直接存进阿里云 OSS（action-gmu · 华南3 广州），建议用竖版证件照，前台按 3:4 裁切显示。
    </el-alert>

    <el-table v-loading="loading" :data="memberList" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="55" align="center" />
      <el-table-column label="头像" align="center" width="80">
        <template #default="scope">
          <el-image
            v-if="scope.row.avatarUrl"
            :src="scope.row.avatarUrl"
            style="width: 40px; height: 50px; border-radius: 4px"
            fit="cover"
          >
            <template #error><span class="avatar-fallback">无图</span></template>
          </el-image>
          <span v-else class="avatar-fallback">无图</span>
        </template>
      </el-table-column>
      <el-table-column label="所属组" align="center" prop="groupKey" width="130">
        <template #default="scope">{{ groupLabel(scope.row.groupKey) }}</template>
      </el-table-column>
      <el-table-column label="姓名" align="left" prop="nameZh" width="150">
        <template #default="scope">{{ scope.row.honorific ? scope.row.honorific + ' ' : '' }}{{ scope.row.nameZh }}</template>
      </el-table-column>
      <el-table-column label="职称 / 头衔" align="left" prop="titleZh" width="160" :show-overflow-tooltip="true" />
      <el-table-column label="所属机构" align="left" prop="affiliationZh" width="200" :show-overflow-tooltip="true" />
      <el-table-column label="一句话简介（中文）" align="left" prop="summaryZh" :show-overflow-tooltip="true" />
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
            v-hasPermi="['action:teamMember:edit']"
          >修改</el-button>
          <el-button
            link
            type="primary"
            icon="Delete"
            @click="handleDelete(scope.row)"
            v-hasPermi="['action:teamMember:remove']"
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

    <!-- 添加或修改团队成员对话框 -->
    <el-dialog :title="title" v-model="open" width="960px" append-to-body>
      <el-form ref="memberRef" :model="form" :rules="rules" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="所属组" prop="groupKey">
              <el-select v-model="form.groupKey" placeholder="请选择" style="width: 100%">
                <el-option v-for="g in groupOptions" :key="g.value" :label="g.label" :value="g.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="称谓" prop="honorific">
              <el-input v-model="form.honorific" placeholder="Prof. / Dr.，可留空" maxlength="32" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="组内顺序" prop="sortNum">
              <el-input-number v-model="form.sortNum" :min="0" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="姓名（中）" prop="nameZh">
              <el-input v-model="form.nameZh" placeholder="中文名；外籍成员无汉字名时填罗马字" maxlength="200" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="姓名（英）" prop="nameEn">
              <el-input v-model="form.nameEn" placeholder="e.g. Myeong Soo Lee" maxlength="200" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="职称（中）" prop="titleZh">
              <el-input v-model="form.titleZh" placeholder="如：首席研究员" maxlength="300" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="职称（英）" prop="titleEn">
              <el-input v-model="form.titleEn" placeholder="e.g. Principal Researcher" maxlength="500" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="机构（中）" prop="affiliationZh">
              <el-input v-model="form.affiliationZh" placeholder="如：北京中医药大学" maxlength="500" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="机构（英）" prop="affiliationEn">
              <el-input v-model="form.affiliationEn" placeholder="e.g. Beijing University of Chinese Medicine" maxlength="800" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="ACTION 角色（中）" prop="roleZh">
              <el-input v-model="form.roleZh" placeholder="如：国际顾问委员 · 方法学" maxlength="300" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="ACTION 角色（英）" prop="roleEn">
              <el-input v-model="form.roleEn" placeholder="e.g. Advisory Board member · Methodology" maxlength="500" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="研究方向（中）" prop="expertiseZh">
              <el-input v-model="form.expertiseZh" placeholder="多个方向以顿号分隔，详情页会拆成标签" maxlength="500" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="研究方向（英）" prop="expertiseEn">
              <el-input v-model="form.expertiseEn" placeholder="Separate with semicolons" maxlength="800" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="一句话简介（中）" prop="summaryZh">
              <el-input v-model="form.summaryZh" type="textarea" :rows="2" placeholder="名单卡片上显示，建议 60-90 字" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="一句话简介（英）" prop="summaryEn">
              <el-input v-model="form.summaryEn" type="textarea" :rows="2" placeholder="Shown on the roster card" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="履历（中）" prop="bioZh">
              <el-input v-model="form.bioZh" type="textarea" :rows="4" placeholder="详情页正文，可写数百字" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="履历（英）" prop="bioEn">
              <el-input v-model="form.bioEn" type="textarea" :rows="4" placeholder="Biography shown on the profile page" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="对 ACTION 的贡献（中）" prop="contributionZh">
              <el-input v-model="form.contributionZh" type="textarea" :rows="3" placeholder="详情页单独成块，可留空" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="对 ACTION 的贡献（英）" prop="contributionEn">
              <el-input v-model="form.contributionEn" type="textarea" :rows="3" placeholder="Shown as a separate block, optional" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="头像" prop="avatarUrl">
              <!-- 直传阿里云 OSS（action-gmu · 华南3 广州），返回的是公网地址，
                   不走 /common/upload 的本地磁盘通道 —— 官网是静态站，图片不能跟着后端机器走 -->
              <image-upload
                v-model="form.avatarUrl"
                :limit="1"
                :file-size="5"
                :file-type="['png', 'jpg', 'jpeg', 'webp']"
                :drag="false"
                action="/action/admin/team-member/avatar"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="个人主页" prop="homepageUrl">
              <el-input v-model="form.homepageUrl" placeholder="学术档案链接，可留空" maxlength="500" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系邮箱" prop="email">
              <el-input v-model="form.email" placeholder="留空则前台不展示" maxlength="200" />
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

<script setup name="TeamMember">
import {
  listTeamMember,
  getTeamMember,
  addTeamMember,
  updateTeamMember,
  delTeamMember
} from "@/api/system/teamMember";

const { proxy } = getCurrentInstance();
const { sys_normal_disable } = proxy.useDict("sys_normal_disable");

/** 组只有两个且由前台分段渲染写死，不值得为它建一条字典 */
const groupOptions = [
  { value: "board", label: "国际顾问委员会" },
  { value: "core", label: "核心执行团队" }
];

const memberList = ref([]);
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
    groupKey: undefined,
    keyword: undefined,
    status: undefined
  },
  rules: {
    groupKey: [{ required: true, message: "所属组不能为空", trigger: "change" }],
    nameZh: [
      { required: true, message: "中文姓名不能为空", trigger: "blur" },
      { max: 200, message: "中文姓名不能超过200个字符", trigger: "blur" }
    ]
  }
});

const { queryParams, form, rules } = toRefs(data);

function groupLabel(groupKey) {
  const hit = groupOptions.find(g => g.value === groupKey);
  return hit ? hit.label : groupKey;
}

/** 查询团队成员列表 */
function getList() {
  loading.value = true;
  listTeamMember(queryParams.value).then(response => {
    memberList.value = response.rows;
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
    memberId: undefined,
    groupKey: queryParams.value.groupKey || "board",
    nameZh: undefined,
    nameEn: undefined,
    honorific: undefined,
    titleZh: undefined,
    titleEn: undefined,
    affiliationZh: undefined,
    affiliationEn: undefined,
    roleZh: undefined,
    roleEn: undefined,
    expertiseZh: undefined,
    expertiseEn: undefined,
    summaryZh: undefined,
    summaryEn: undefined,
    bioZh: undefined,
    bioEn: undefined,
    contributionZh: undefined,
    contributionEn: undefined,
    avatarUrl: undefined,
    homepageUrl: undefined,
    email: undefined,
    // 新增时不传 sortNum，后端会自动排到该组末尾
    sortNum: undefined,
    status: "0",
    remark: undefined
  };
  proxy.resetForm("memberRef");
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
  ids.value = selection.map(item => item.memberId);
  single.value = selection.length != 1;
  multiple.value = !selection.length;
}

/** 新增按钮操作 */
function handleAdd() {
  reset();
  open.value = true;
  title.value = "添加团队成员";
}

/** 修改按钮操作 */
function handleUpdate(row) {
  reset();
  const memberId = row.memberId || ids.value;
  getTeamMember(memberId).then(response => {
    form.value = response.data;
    open.value = true;
    title.value = "修改团队成员";
  });
}

/** 提交按钮 */
function submitForm() {
  proxy.$refs["memberRef"].validate(valid => {
    if (valid) {
      if (form.value.memberId != undefined) {
        updateTeamMember(form.value).then(() => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addTeamMember(form.value).then(() => {
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
  const memberIds = row.memberId || ids.value;
  proxy.$modal
    .confirm('是否确认删除成员编号为"' + memberIds + '"的数据项？')
    .then(function () {
      return delTeamMember(memberIds);
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
.avatar-fallback {
  font-size: 12px;
  color: #909399;
}
</style>
