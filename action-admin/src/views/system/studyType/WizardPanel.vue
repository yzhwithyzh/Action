<template>
  <div>
    <el-alert type="info" :closable="false" class="mb8" show-icon>
      官网报告助手第一步的<b>分支问卷</b>（依据《ACTION智能匹配研究类型.docx》）：从「第一题」开始，用户每选一个选项，
      要么<b>弹出下一题</b>，要么<b>判定为一类研究</b>——判定出的那一类挂哪些规范、推荐哪些统计方法、给什么专属提示，在「判定结果」页签里维护。
      <br />
      选项上也可以带一句提示：只对选了这一项的人显示（如「设假针 / 安慰剂对照」那条），与判定结果自身的提示一起出现在匹配卡片底部。
      保存时会校验整棵树（第一题唯一、每个选项二选一、不能互相指成环、判定的类型必须存在且启用），不通过则不保存。
    </el-alert>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['action:studyType:add']">新增题目</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button plain icon="Refresh" @click="getList">刷新</el-button>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="14">
        <el-table v-loading="loading" :data="questions" row-key="questionId">
          <el-table-column label="标识" width="130">
            <template #default="scope">
              <code>{{ scope.row.qKey }}</code>
              <el-tag v-if="scope.row.isRoot === '1'" type="danger" size="small" class="ml4">第一题</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="题干" min-width="200">
            <template #default="scope">
              <div>{{ scope.row.textZh }}</div>
              <div class="muted">{{ scope.row.textEn }}</div>
            </template>
          </el-table-column>
          <el-table-column label="选项 → 去向" min-width="260">
            <template #default="scope">
              <div v-for="o in scope.row.options" :key="o.optKey" class="opt-line">
                <code>{{ o.optKey }}</code> {{ o.labelZh }}
                <span class="arrow">→</span>
                <span v-if="o.nextQuestionId" class="to-q">{{ questionLabel(o.nextQuestionId) }}</span>
                <el-tag v-else-if="o.resultTypeKey" size="small" :type="typeOf(o.resultTypeKey) ? 'success' : 'danger'">
                  {{ typeLabel(o.resultTypeKey) }}
                </el-tag>
                <el-tag v-else size="small" type="danger">未设置</el-tag>
                <el-tag v-if="o.tipZh" size="small" type="warning" effect="plain" class="ml4">带提示</el-tag>
              </div>
              <span v-if="!scope.row.options.length" class="muted">无选项</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" align="center" width="120" class-name="small-padding fixed-width">
            <template #default="scope">
              <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['action:studyType:edit']">修改</el-button>
              <el-button link type="primary" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['action:studyType:remove']">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-col>

      <!-- 从第一题展开的整棵树：比逐行看表格更容易一眼看出「哪条分支没收口」 -->
      <el-col :span="10">
        <el-card shadow="never" header="流程预览（从第一题展开）">
          <div v-if="!flow.length" class="muted">还没有第一题</div>
          <div v-for="(line, i) in flow" :key="i" class="flow-line" :style="{ paddingLeft: line.depth * 20 + 'px' }">
            <template v-if="line.kind === 'q'">
              <b>问题 {{ line.no }}</b> · {{ line.text }}
            </template>
            <template v-else-if="line.kind === 'r'">
              <span class="muted">{{ line.opt }} →</span>
              <el-tag size="small" :type="line.ok ? 'success' : 'danger'">{{ line.text }}</el-tag>
            </template>
            <template v-else-if="line.kind === 'loop'">
              <span class="muted">{{ line.opt }} →</span> <el-tag size="small" type="danger">{{ line.text }}</el-tag>
            </template>
            <template v-else>
              <span class="muted">{{ line.opt }} ↓</span>
            </template>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog :title="title" v-model="open" width="960px" append-to-body>
      <el-form ref="qRef" :model="form" :rules="rules" label-width="96px">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="题目标识" prop="qKey">
              <el-input v-model="form.qKey" placeholder="如 randomized" />
              <div class="hint">仅后台辨认用</div>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="第一题">
              <el-switch v-model="form.isRoot" active-value="1" inactive-value="0" />
              <div class="hint">设为第一题会取消原来那道</div>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="列表顺序">
              <el-input-number v-model="form.sortNum" :min="0" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="题干（中文）" prop="textZh">
              <el-input v-model="form.textZh" placeholder="如：是否采用随机分组？" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="题干（英文）">
              <el-input v-model="form.textEn" placeholder="Is random group allocation adopted?" />
            </el-form-item>
          </el-col>
        </el-row>
        <div class="hint mb8" style="padding-left: 96px">官网会自动加上「问题 N」前缀，题干里不必写。</div>

        <el-form-item label="选项">
          <div class="opt-list">
            <div v-for="(o, i) in form.options" :key="i" class="opt-card">
              <div class="opt-row">
                <el-input v-model="o.optKey" placeholder="标识" class="w-key" />
                <el-input v-model="o.labelZh" placeholder="选项文字（中文）" />
                <el-input v-model="o.labelEn" placeholder="English" />
                <el-button link icon="Top" :disabled="i === 0" @click="move(i, -1)" />
                <el-button link icon="Bottom" :disabled="i === form.options.length - 1" @click="move(i, 1)" />
                <el-button link type="danger" icon="Delete" @click="form.options.splice(i, 1)" />
              </div>
              <div class="opt-row">
                <el-radio-group v-model="o.goto" size="small">
                  <el-radio-button value="next">弹出下一题</el-radio-button>
                  <el-radio-button value="result">判定为</el-radio-button>
                </el-radio-group>
                <el-select v-if="o.goto === 'next'" v-model="o.nextQuestionId" placeholder="选择下一题" style="flex: 1">
                  <el-option
                    v-for="q in questions.filter(x => x.questionId !== form.questionId)"
                    :key="q.questionId"
                    :label="`${q.qKey} — ${q.textZh}`"
                    :value="q.questionId"
                  />
                </el-select>
                <el-select v-else v-model="o.resultTypeKey" filterable placeholder="选择研究类型" style="flex: 1">
                  <el-option
                    v-for="t in types"
                    :key="t.typeKey"
                    :label="`${t.nameZh}（${t.typeKey}）${t.status === '1' ? ' · 已停用' : ''}`"
                    :value="t.typeKey"
                    :disabled="t.status === '1'"
                  />
                </el-select>
              </div>
              <div class="opt-row">
                <el-input v-model="o.tipZh" placeholder="选中时额外提示（中文，可留空）" type="textarea" :rows="1" autosize />
                <el-input v-model="o.tipEn" placeholder="Tip (English, optional)" type="textarea" :rows="1" autosize />
              </div>
            </div>
            <el-button link type="primary" icon="Plus" @click="addOption">添加选项</el-button>
            <div class="hint">
              标识只能是字母、数字、下划线，同一题内不重复；它会进官网链接（<code>?path=A.y.y</code>），改了之后旧的分享链接会回落到默认选项。
              选项顺序即官网按钮顺序，<b>第一个选项是默认选中项</b>。
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" @click="submitForm">确 定</el-button>
          <el-button @click="open = false">取 消</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="StudyWizardPanel">
import { listStudyWizard, addWizardQuestion, updateWizardQuestion, delWizardQuestion } from '@/api/system/studyType'

const props = defineProps({
  /** 全部研究类型（含停用），判定结果的下拉与名称显示用 */
  types: { type: Array, default: () => [] }
})

const { proxy } = getCurrentInstance()

const questions = ref([])
const loading = ref(false)
const open = ref(false)
const title = ref('')
const form = ref({})
const rules = {
  qKey: [
    { required: true, message: '题目标识不能为空', trigger: 'blur' },
    { pattern: /^[a-z][a-z0-9_]*$/, message: '小写字母开头的字母、数字与下划线', trigger: 'blur' }
  ],
  textZh: [{ required: true, message: '中文题干不能为空', trigger: 'blur' }]
}

function typeOf(key) {
  return props.types.find(t => t.typeKey === key && t.status !== '1')
}

function typeLabel(key) {
  const t = props.types.find(x => x.typeKey === key)
  if (!t) return `${key}（不存在）`
  return t.status === '1' ? `${t.nameZh}（已停用）` : t.nameZh
}

function questionLabel(id) {
  const q = questions.value.find(x => x.questionId === id)
  return q ? `问题：${q.textZh}` : '（题目已不存在）'
}

/** 从第一题深度优先展开，逐行摆出来；遇到环就标红停下 */
const flow = computed(() => {
  const byId = new Map(questions.value.map(q => [q.questionId, q]))
  const root = questions.value.find(q => q.isRoot === '1')
  const lines = []
  function walk(q, depth, no, trail) {
    lines.push({ kind: 'q', depth, no, text: q.textZh })
    for (const o of q.options) {
      const opt = `${o.optKey}. ${o.labelZh}`
      if (o.resultTypeKey) {
        lines.push({ kind: 'r', depth: depth + 1, opt, text: typeLabel(o.resultTypeKey), ok: !!typeOf(o.resultTypeKey) })
      } else if (o.nextQuestionId && byId.has(o.nextQuestionId)) {
        if (trail.includes(o.nextQuestionId)) {
          lines.push({ kind: 'loop', depth: depth + 1, opt, text: '循环！' })
        } else {
          lines.push({ kind: 'o', depth: depth + 1, opt })
          walk(byId.get(o.nextQuestionId), depth + 2, no + 1, [...trail, o.nextQuestionId])
        }
      } else {
        lines.push({ kind: 'r', depth: depth + 1, opt, text: '未设置去向', ok: false })
      }
    }
  }
  if (root) walk(root, 0, 1, [root.questionId])
  return lines
})

function getList() {
  loading.value = true
  listStudyWizard()
    .then(res => {
      questions.value = res.data || []
    })
    .finally(() => {
      loading.value = false
    })
}

function toFormOption(o) {
  return {
    optKey: o.optKey,
    labelZh: o.labelZh,
    labelEn: o.labelEn || '',
    goto: o.nextQuestionId ? 'next' : 'result',
    nextQuestionId: o.nextQuestionId || undefined,
    resultTypeKey: o.resultTypeKey || '',
    tipZh: o.tipZh || '',
    tipEn: o.tipEn || ''
  }
}

function addOption() {
  form.value.options.push(toFormOption({ optKey: '', labelZh: '' }))
}

function move(i, d) {
  const arr = form.value.options
  ;[arr[i], arr[i + d]] = [arr[i + d], arr[i]]
}

function handleAdd() {
  form.value = { questionId: undefined, qKey: '', textZh: '', textEn: '', isRoot: '0', sortNum: undefined, options: [] }
  addOption()
  title.value = '新增题目'
  open.value = true
  nextTick(() => proxy.resetForm('qRef'))
}

function handleUpdate(row) {
  // 深拷贝：直接引用的话，在弹窗里删一个选项再点取消，列表上那行也跟着没了
  form.value = { ...row, options: row.options.map(toFormOption) }
  title.value = '修改题目'
  open.value = true
}

function submitForm() {
  proxy.$refs['qRef'].validate(valid => {
    if (!valid) return
    const bad = form.value.options.find(o => !/^[A-Za-z0-9_]+$/.test(o.optKey || '') || !(o.labelZh || '').trim())
    if (bad) {
      proxy.$modal.msgError('每个选项都要填标识（字母、数字、下划线）与中文文字')
      return
    }
    // 二选一在这里就收口：只把当前去向那一栏发给后端，另一栏清空
    const payload = {
      ...form.value,
      options: form.value.options.map(({ goto, ...o }) => ({
        ...o,
        nextQuestionId: goto === 'next' ? o.nextQuestionId || null : null,
        resultTypeKey: goto === 'result' ? o.resultTypeKey || '' : ''
      }))
    }
    const req = payload.questionId ? updateWizardQuestion(payload) : addWizardQuestion(payload)
    req.then(res => {
      // 后端把「有题目走不到」之类的警告拼在 msg 里，用 alert 让人看完
      if (res.msg && res.msg !== '保存成功') {
        proxy.$alert(res.msg, '已保存', { confirmButtonText: '知道了' })
      } else {
        proxy.$modal.msgSuccess('保存成功')
      }
      open.value = false
      getList()
    })
  })
}

function handleDelete(row) {
  proxy.$modal
    .confirm(`确认删除题目「${row.textZh}」及其全部选项？若还有别的选项指向它，删除会被拒绝。`)
    .then(() => delWizardQuestion(row.questionId))
    .then(res => {
      getList()
      proxy.$modal.msgSuccess(res.msg || '删除成功')
    })
    .catch(() => {})
}

getList()

defineExpose({ getList })
</script>

<style scoped>
.muted {
  color: #909399;
  font-size: 12px;
}
.ml4 {
  margin-left: 4px;
}
.hint {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
  margin-top: 2px;
}
.opt-line {
  line-height: 1.9;
  font-size: 13px;
}
.opt-line .arrow {
  color: #c0c4cc;
  margin: 0 4px;
}
.to-q {
  color: #409eff;
}
.flow-line {
  line-height: 2;
  font-size: 13px;
}
.opt-list {
  width: 100%;
}
.opt-card {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 10px;
  margin-bottom: 10px;
}
.opt-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.opt-row:last-child {
  margin-bottom: 0;
}
.w-key {
  width: 140px;
  flex-shrink: 0;
}
</style>
