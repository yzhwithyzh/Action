<template>
  <div class="app-container">
    <el-tabs v-model="tab">
    <!-- 问卷决定「怎么问」，判定结果决定「问完给什么」。先摆问卷：甲方改分支逻辑时来的是这一页 -->
    <el-tab-pane label="分支问卷" name="wizard">
      <wizard-panel :types="allTypes" />
    </el-tab-pane>
    <el-tab-pane label="判定结果（研究类型）" name="types">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="80px">
      <el-form-item label="关键词" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="标识 / 中英名称"
          clearable
          style="width: 240px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['action:studyType:add']">新增</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="success"
          plain
          icon="Edit"
          :disabled="single"
          @click="handleUpdate"
          v-hasPermi="['action:studyType:edit']"
        >修改</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="danger"
          plain
          icon="Delete"
          :disabled="multiple"
          @click="handleDelete"
          v-hasPermi="['action:studyType:remove']"
        >删除</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-alert type="info" :closable="false" class="mb8" show-icon>
      这里是分支问卷的<b>判定结果</b>：用户答完问卷落到哪一类研究，匹配卡片上就显示这一类的挂载规范、推荐统计方法与专属提示。
      与「规范分类管理」用途不同（那张是规范目录页的陈列分类），两边对同一类研究取同样的标识，但不构成关联。
      <br />
      <b>「重点推荐规范」决定第二步展开哪份 checklist</b>，是这页最要紧的一个字段；「关联规范标签」只是匹配卡片上的展示 chip，可以填库里没有的说明性文字。
      <b>新增的类型要在「分支问卷」里挂到某个选项上</b>，官网才选得到。
    </el-alert>

    <el-table v-loading="loading" :data="typeList" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="55" align="center" />
      <el-table-column label="标识" prop="typeKey" width="120">
        <template #default="scope"><code>{{ scope.row.typeKey }}</code></template>
      </el-table-column>
      <el-table-column label="名称（中文）" prop="nameZh" :show-overflow-tooltip="true" min-width="160" />
      <el-table-column label="名称（英文）" prop="nameEn" :show-overflow-tooltip="true" min-width="180" />
      <el-table-column label="重点推荐规范" align="center" width="150">
        <template #default="scope">
          <el-tag v-if="scope.row.hotGuideline" type="danger" effect="dark">{{ scope.row.hotGuideline }}</el-tag>
          <span v-else class="muted">未设置</span>
          <!-- 条目数是这一列真正的信息量：0 条就意味着第二步展不开 -->
          <div class="hint" :class="{ warn: itemCount(scope.row.hotGuidelineId) === 0 }">
            {{ itemCountText(scope.row.hotGuidelineId) }}
          </div>
        </template>
      </el-table-column>
      <el-table-column label="可切换规范" align="center" width="170">
        <template #default="scope">
          <template v-if="(scope.row.checklistOptions || []).length > 1">
            <div v-for="o in scope.row.checklistOptions.slice(1)" :key="o.guidelineId">
              <el-tag type="warning" effect="plain">{{ o.code }}</el-tag>
              <div class="hint" :class="{ warn: !o.itemCount }">{{ o.itemCount ? `${o.itemCount} 条条目` : '该规范暂无条目' }}</div>
            </div>
          </template>
          <span v-else class="muted">无</span>
        </template>
      </el-table-column>
      <el-table-column label="关联规范标签" min-width="220">
        <template #default="scope">
          <el-tag
            v-for="g in scope.row.guidelines"
            :key="g"
            class="mr4"
            :type="g === scope.row.hotGuideline ? 'danger' : 'info'"
            effect="plain"
          >{{ g }}</el-tag>
          <span v-if="!scope.row.guidelines || !scope.row.guidelines.length" class="muted">无</span>
        </template>
      </el-table-column>
      <el-table-column label="统计推荐" align="center" width="90">
        <template #default="scope">{{ (scope.row.stats || []).length }} 条</template>
      </el-table-column>
      <el-table-column label="专属提示" min-width="200" :show-overflow-tooltip="true">
        <template #default="scope">
          <span v-if="scope.row.tipZh">{{ scope.row.tipZh }}</span>
          <span v-else class="muted">无</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" align="center" width="70">
        <template #default="scope">
          <el-tag v-if="scope.row.status === '1'" type="info">停用</el-tag>
          <el-tag v-else type="success">正常</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="顺序" prop="sortNum" align="center" width="70" />
      <el-table-column label="操作" align="center" width="140" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['action:studyType:edit']">修改</el-button>
          <el-button link type="primary" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['action:studyType:remove']">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog :title="title" v-model="open" width="820px" append-to-body>
      <el-form ref="typeRef" :model="form" :rules="rules" label-width="120px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="类型标识" prop="typeKey">
              <el-input v-model="form.typeKey" placeholder="小写字母开头，如 rct / protocol" />
              <div class="hint">分支问卷的选项按它指向这里；改了会连带改过去</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="显示顺序" prop="sortNum">
              <el-input-number v-model="form.sortNum" :min="0" controls-position="right" style="width: 100%" />
              <div class="hint">留空则排到末尾</div>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="名称（中文）" prop="nameZh">
              <el-input v-model="form.nameZh" placeholder="如：随机对照试验" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="名称（英文）" prop="nameEn">
              <el-input v-model="form.nameEn" placeholder="Randomised controlled trial" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 存的是规范 id 不是代号：代号在「规范目录管理」里可改，按字符串挂的话一改名就全部指空（sql/048） -->
        <el-form-item label="重点推荐规范" prop="hotGuidelineId">
          <el-select v-model="form.hotGuidelineId" clearable filterable placeholder="决定第二步展开哪份 checklist" style="width: 100%">
            <el-option
              v-for="g in guidelineOptions"
              :key="g.guidelineId"
              :label="`${g.code} — ${g.nameZh || ''}`"
              :value="g.guidelineId"
            >
              <span>{{ g.code }}</span>
              <span class="opt-count" :class="{ warn: (itemCounts[g.guidelineId] || 0) === 0 }">
                {{ itemCounts[g.guidelineId] || 0 }} 条
              </span>
            </el-option>
          </el-select>
          <div class="hint" :class="{ warn: form.hotGuidelineId && itemCount(form.hotGuidelineId) === 0 }">
            {{ hotHint }}
          </div>
        </el-form-item>

        <!-- 与重点推荐规范同样按 id 挂（sql/056）。一份草稿只对应一份规范，用户在第二步顶部切换 -->
        <el-form-item label="可切换规范" prop="altGuidelineIds">
          <el-select v-model="form.altGuidelineIds" multiple filterable placeholder="第二步除重点推荐规范外，还能切换到的规范" style="width: 100%">
            <el-option
              v-for="g in guidelineOptions.filter(x => x.guidelineId !== form.hotGuidelineId)"
              :key="g.guidelineId"
              :label="`${g.code} — ${g.nameZh || ''}`"
              :value="g.guidelineId"
            >
              <span>{{ g.code }}</span>
              <span class="opt-count" :class="{ warn: (itemCounts[g.guidelineId] || 0) === 0 }">
                {{ itemCounts[g.guidelineId] || 0 }} 条
              </span>
            </el-option>
          </el-select>
          <div class="hint">
            选了的话，报告助手第二步顶部会出现规范切换按钮（重点推荐规范排第一）。每份规范各写各的草稿；0 条条目的规范会标「条目待录入」。
          </div>
        </el-form-item>

        <el-form-item label="关联规范标签">
          <el-select
            v-model="form.guidelines"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="第一步匹配结果卡片上的 chip，可自由填写"
            style="width: 100%"
          >
            <el-option v-for="g in guidelineOptions" :key="g.code" :label="g.code" :value="g.code" />
          </el-select>
          <div class="hint">
            只是展示标签，<b>不校验</b>——库里现有「针灸专属条目」「GRADE 证据分级」这类值就不是真实规范代号。拖动顺序即 chip 的排列顺序。
          </div>
        </el-form-item>

        <el-form-item label="统计方法推荐">
          <div class="stat-list">
            <div v-for="(s, i) in form.stats" :key="i" class="stat-row">
              <el-input v-model="s.textZh" placeholder="中文，如：主要结局用协方差分析，以基线值为协变量" />
              <el-input v-model="s.textEn" placeholder="English" />
              <el-button link type="danger" icon="Delete" @click="form.stats.splice(i, 1)" />
            </div>
            <el-button link type="primary" icon="Plus" @click="form.stats.push({ textZh: '', textEn: '' })">添加一条</el-button>
            <div v-if="!form.stats.length" class="hint">第一步匹配结果卡片上的「推荐统计方法」清单，可留空</div>
          </div>
        </el-form-item>

        <el-form-item label="专属提示">
          <div class="stat-list">
            <el-input v-model="form.tipZh" type="textarea" autosize placeholder="中文，如：重点完整记录针刺穴位、操作手法、得气反应与不良事件。" class="mb8" />
            <el-input v-model="form.tipEn" type="textarea" autosize placeholder="English" />
            <div class="hint">显示在匹配卡片底部。只对某个答案成立的提示（如「设假针」），请写在分支问卷对应选项上</div>
          </div>
        </el-form-item>

        <el-form-item label="状态" prop="status">
          <el-radio-group v-model="form.status">
            <el-radio value="0">正常</el-radio>
            <el-radio value="1">停用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" @click="submitForm">确 定</el-button>
          <el-button @click="cancel">取 消</el-button>
        </div>
      </template>
    </el-dialog>
    </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup name="StudyType">
import { listStudyType, addStudyType, updateStudyType, delStudyType } from '@/api/system/studyType'
import { listGuideline } from '@/api/system/guideline'
import { listGuidelineItem } from '@/api/system/guidelineItem'
import WizardPanel from './WizardPanel.vue'

const { proxy } = getCurrentInstance()

const tab = ref('wizard')
const typeList = ref([])
/** 不受关键词筛选的全量类型，给分支问卷的下拉与名称显示用 */
const allTypes = ref([])
const guidelineOptions = ref([])
/** 规范id -> checklist 条目数。0 条就意味着选它作重点规范时第二步展不开 */
const itemCounts = ref({})
const open = ref(false)
const loading = ref(true)
const showSearch = ref(true)
const ids = ref([])
const single = ref(true)
const multiple = ref(true)
const title = ref('')

const data = reactive({
  form: {},
  queryParams: { keyword: undefined },
  rules: {
    typeKey: [
      { required: true, message: '类型标识不能为空', trigger: 'blur' },
      { pattern: /^[a-z][a-z0-9_]*$/, message: '只能是小写字母开头的字母、数字与下划线', trigger: 'blur' }
    ],
    nameZh: [{ required: true, message: '中文名称不能为空', trigger: 'blur' }]
  }
})
const { queryParams, form, rules } = toRefs(data)

function itemCount(id) {
  return id ? itemCounts.value[id] || 0 : 0
}

function itemCountText(id) {
  if (!id) return ''
  const n = itemCount(id)
  return n ? `${n} 条条目` : '该规范暂无条目'
}

const hotHint = computed(() => {
  if (!form.value.hotGuidelineId) return '留空则第二步展不开任何清单'
  const n = itemCount(form.value.hotGuidelineId)
  return n
    ? `第二步会展开这份规范的 ${n} 条 checklist 条目`
    : '这份规范目前 0 条条目，第二步会是一片空白——可以先存，但需尽快在「规范条目管理」补齐'
})

function getList() {
  loading.value = true
  listStudyType(queryParams.value).then(res => {
    typeList.value = res.data || []
    if (!queryParams.value.keyword) allTypes.value = typeList.value
    loading.value = false
  })
}

/** 拉规范目录与各自的条目数，供「重点推荐规范」下拉与提示用 */
function getGuidelines() {
  // 这两个接口要的是 action:guideline:* 权限，只授了 studyType 权限的账号会 403。
  // 静默吞掉：取不到选项时下拉为空、改不了重点规范，但列表与其余字段照常可编辑，不该整页报错
  listGuideline({ pageNum: 1, pageSize: 200 })
    .then(res => {
      guidelineOptions.value = res.rows || res.data || []
      guidelineOptions.value.forEach(g => {
        listGuidelineItem({ guidelineId: g.guidelineId, pageNum: 1, pageSize: 1 })
          .then(r => {
            itemCounts.value = { ...itemCounts.value, [g.guidelineId]: r.total || 0 }
          })
          .catch(() => {})
      })
    })
    .catch(() => {})
}

function cancel() {
  open.value = false
  reset()
}

function reset() {
  form.value = {
    typeId: undefined,
    typeKey: '',
    nameZh: '',
    nameEn: '',
    hotGuidelineId: undefined,
    altGuidelineIds: [],
    sortNum: undefined,
    status: '0',
    tipZh: '',
    tipEn: '',
    guidelines: [],
    stats: []
  }
  proxy.resetForm('typeRef')
}

function handleQuery() {
  getList()
}

function resetQuery() {
  proxy.resetForm('queryRef')
  handleQuery()
}

function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.typeId)
  single.value = selection.length !== 1
  multiple.value = !selection.length
}

function handleAdd() {
  reset()
  open.value = true
  title.value = '新增研究类型'
}

function handleUpdate(row) {
  reset()
  const target = row.typeId ? row : typeList.value.find(t => t.typeId === ids.value[0])
  // 深拷贝子表：直接引用的话，用户在弹窗里删一行、点取消，列表上那行也没了
  form.value = {
    ...target,
    guidelines: [...(target.guidelines || [])],
    altGuidelineIds: [...(target.altGuidelineIds || [])],
    stats: (target.stats || []).map(s => ({ ...s }))
  }
  open.value = true
  title.value = '修改研究类型'
}

function submitForm() {
  proxy.$refs['typeRef'].validate(valid => {
    if (!valid) return
    // 空行不提交：整体覆盖语义下，一行空的统计推荐会在前台渲染成一个空的 li
    const payload = {
      ...form.value,
      // 清空下拉时 el-select 给的可能是 ''，后端这个字段是 int，统一成 null 表示「不挂」
      hotGuidelineId: form.value.hotGuidelineId || null,
      // 与重点推荐重复的剔掉（换了重点推荐之后，原先多选里可能正好有它）
      altGuidelineIds: (form.value.altGuidelineIds || []).filter(id => id !== form.value.hotGuidelineId),
      stats: (form.value.stats || []).filter(s => (s.textZh || '').trim())
    }
    const req = payload.typeId ? updateStudyType(payload) : addStudyType(payload)
    req.then(res => {
      // 后端会把「前台还需同步」这件事放进 msg 里，用 alert 而不是转瞬即逝的 toast
      if (res.msg && res.msg.length > 12) {
        proxy.$alert(res.msg, '已保存', { confirmButtonText: '知道了' })
      } else {
        proxy.$modal.msgSuccess(payload.typeId ? '修改成功' : '新增成功')
      }
      open.value = false
      getList()
    })
  })
}

function handleDelete(row) {
  const delIds = row.typeId ? [row.typeId] : ids.value
  const names = typeList.value.filter(t => delIds.includes(t.typeId)).map(t => t.nameZh).join('、')
  proxy.$modal
    .confirm(`确认删除研究类型「${names}」？其关联规范标签与统计推荐会一并删除，且不可恢复。`)
    .then(() => delStudyType(delIds.join(',')))
    .then(res => {
      getList()
      proxy.$modal.msgSuccess(res.msg || '删除成功')
    })
    .catch(() => {})
}

getList()
getGuidelines()
</script>

<style scoped>
.muted {
  color: #909399;
}
.mr4 {
  margin-right: 4px;
}
.hint {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
  margin-top: 2px;
}
.hint.warn {
  color: #e6a23c;
}
.opt-count {
  float: right;
  color: #909399;
  font-size: 12px;
}
.opt-count.warn {
  color: #e6a23c;
}
.stat-list {
  width: 100%;
}
.stat-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}
.stat-row .el-input:first-child {
  flex: 1.1;
}
</style>
