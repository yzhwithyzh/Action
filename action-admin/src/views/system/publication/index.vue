<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="80px">
      <el-form-item label="关键词" prop="keyword">
        <el-input
          v-model="queryParams.keyword"
          placeholder="标题 / 作者 / 期刊 / DOI"
          clearable
          style="width: 240px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="年份" prop="year">
        <el-input-number v-model="queryParams.year" :min="1800" :max="2100" controls-position="right" style="width: 140px" />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="全部状态" clearable style="width: 140px">
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
        <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['action:publication:add']">新增</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="success"
          plain
          icon="Edit"
          :disabled="single"
          @click="handleUpdate"
          v-hasPermi="['action:publication:edit']"
        >修改</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="danger"
          plain
          icon="Delete"
          :disabled="multiple"
          @click="handleDelete"
          v-hasPermi="['action:publication:remove']"
        >删除</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-alert type="info" :closable="false" class="mb8" show-icon>
      本表是官网「成果发表」页的论文列表：一条记录一篇论文，前台<b>按发表年份分组倒序</b>排列，
      同年内按「显示顺序」排。标题、作者、期刊、摘要一律<b>照发表原文录入、不要翻译</b>——
      这些同时也是引用信息，译过之后读者既检索不到也引用不了；中英两种界面显示的都是它。
      录入时优先用「按 DOI 解析」，那是出版社登记的权威元数据。
    </el-alert>

    <el-table v-loading="loading" :data="publicationList" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="55" align="center" />
      <el-table-column label="标题" align="left" prop="title" :show-overflow-tooltip="true" min-width="260" />
      <el-table-column label="作者" align="left" width="200" :show-overflow-tooltip="true">
        <template #default="scope">{{ summarizeAuthors(scope.row.authors) }}</template>
      </el-table-column>
      <el-table-column label="期刊" align="left" prop="journal" :show-overflow-tooltip="true" width="180" />
      <el-table-column label="年份" align="center" prop="publicationYear" width="80" />
      <el-table-column label="DOI" align="left" prop="doi" width="200" :show-overflow-tooltip="true">
        <template #default="scope">
          <el-link
            v-if="scope.row.doi"
            :href="'https://doi.org/' + scope.row.doi"
            target="_blank"
            rel="noopener noreferrer"
            type="primary"
          >{{ scope.row.doi }}</el-link>
          <span v-else class="pub-muted">—</span>
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
            v-hasPermi="['action:publication:edit']"
          >修改</el-button>
          <el-button
            link
            type="primary"
            icon="Delete"
            @click="handleDelete(scope.row)"
            v-hasPermi="['action:publication:remove']"
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

    <!-- 添加或修改成果发表对话框 -->
    <el-dialog :title="title" v-model="open" width="980px" append-to-body destroy-on-close>
      <el-form
        ref="pubRef"
        :model="form"
        :rules="rules"
        label-width="110px"
        v-loading="parsing"
        element-loading-text="正在解析，请稍候…"
      >
        <el-divider content-position="left">自动录入（可跳过）</el-divider>

        <el-form-item label="按 DOI 解析">
          <el-input v-model="parseSource" placeholder="粘贴 DOI 或 doi.org 链接，如 10.1016/j.ctim.2024.103041">
            <template #append>
              <el-button :disabled="!parseSource || parsing" @click="handleParseDoi">解析</el-button>
            </template>
          </el-input>
          <div class="form-tip">
            向 Crossref 查一次并填入下方表单，<b>不会直接保存</b>，请逐项核对。
            只认 DOI 与 doi.org 链接；<b>不支持粘任意网址</b>——让服务器去抓任意地址会变成内网探测的入口。
            <br>
            <b>摘要与关键词由 PubMed 补</b>：Crossref 没有「作者关键词」这个字段，摘要也要出版社存过才有
            （Elsevier、JAMA、BMJ 都不存）。两处都没有时会在提示里说明，那时请手填或改用「按 PDF 解析」。
          </div>
        </el-form-item>

        <el-form-item label="按 PDF 解析">
          <el-upload :show-file-list="false" :before-upload="handleParsePdf" accept=".pdf" :disabled="parsing">
            <el-button :disabled="parsing" icon="UploadFilled">选择 PDF 并解析</el-button>
          </el-upload>
          <div class="form-tip">
            没有 DOI（预印本、会议摘要、刚接收）时用这条：抽出 PDF 开头的文字交给 AI 提取标题/作者/机构/摘要。
            这份 PDF <b>只用于解析，不会被存下来</b>；要在官网提供全文下载请用下面的「全文 PDF」。
            <b>AI 提取的准确度不如 DOI，请逐项核对。</b>
          </div>
        </el-form-item>

        <el-divider content-position="left">基本信息</el-divider>

        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" type="textarea" :rows="2" placeholder="论文标题，照发表原文录入" maxlength="500" show-word-limit />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="期刊" prop="journal">
              <el-input v-model="form.journal" placeholder="期刊名称" maxlength="300" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="DOI" prop="doi">
              <el-input v-model="form.doi" placeholder="10.xxxx/yyyy" maxlength="200" />
              <div class="form-tip">粘整条 doi.org 链接也行，后端会剥成裸 DOI。</div>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="年份" prop="publicationYear">
              <el-input-number v-model="form.publicationYear" :min="1800" :max="2100" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="卷" prop="volume">
              <el-input v-model="form.volume" placeholder="volume" maxlength="50" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="期" prop="issue">
              <el-input v-model="form.issue" placeholder="issue" maxlength="50" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="页码" prop="pages">
              <el-input v-model="form.pages" placeholder="145-152 或 103041" maxlength="50" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">作者与机构</el-divider>

        <el-form-item label="机构列表">
          <div class="pub-editor">
            <div v-for="(affil, idx) in form.affiliations" :key="'af' + idx" class="pub-editor__row">
              <span class="pub-editor__index">{{ idx + 1 }}.</span>
              <el-input v-model="form.affiliations[idx]" placeholder="机构完整名称" />
              <el-button type="danger" link icon="Delete" @click="removeAffiliation(idx)" />
            </div>
            <el-button size="small" icon="Plus" @click="addAffiliation">添加机构</el-button>
            <div class="form-tip">序号就是作者行里选的那个机构，删除机构时下面的作者会自动重新对号。</div>
          </div>
        </el-form-item>

        <el-form-item label="作者列表">
          <div class="pub-editor">
            <div v-for="(author, idx) in form.authors" :key="'au' + idx" class="pub-editor__row">
              <span class="pub-editor__index">{{ idx + 1 }}.</span>
              <el-input v-model="form.authors[idx].name" placeholder="姓名（照署名原文）" style="flex: 2" />
              <el-select
                v-model="form.authors[idx].affiliationIndex"
                placeholder="所属机构（可留空）"
                clearable
                style="flex: 3"
              >
                <el-option
                  v-for="(affil, affilIdx) in form.affiliations"
                  :key="affilIdx"
                  :label="affilIdx + 1 + '. ' + (affil || '(未命名)')"
                  :value="affilIdx"
                />
              </el-select>
              <el-button type="danger" link icon="Delete" @click="removeAuthor(idx)" />
            </div>
            <el-button size="small" icon="Plus" @click="addAuthor">添加作者</el-button>
            <div class="form-tip"><b>顺序即署名顺序，别随手调。</b>前台按这个顺序展示，引用文本也按它生成。</div>
          </div>
        </el-form-item>

        <el-divider content-position="left">内容</el-divider>

        <el-form-item label="摘要" prop="abstract">
          <el-input v-model="form.abstract" type="textarea" :rows="6" placeholder="摘要正文（纯文本，照发表原文）" />
        </el-form-item>

        <el-form-item label="关键词">
          <div class="pub-tags">
            <el-tag v-for="(kw, idx) in form.keywords" :key="idx" closable @close="removeKeyword(idx)">{{ kw }}</el-tag>
            <el-input
              v-if="keywordInputVisible"
              ref="keywordInputRef"
              v-model="keywordInputValue"
              size="small"
              style="width: 160px"
              @keyup.enter="addKeyword"
              @blur="addKeyword"
            />
            <el-button v-else size="small" icon="Plus" @click="showKeywordInput">添加关键词</el-button>
          </div>
        </el-form-item>

        <el-form-item label="引用文本" prop="citationText">
          <el-input v-model="form.citationText" type="textarea" :rows="2" placeholder="留空则保存时按上面的字段自动拼一条" />
          <div class="form-tip">前台详情页「如何引用」那一块显示的就是这一段，访客可一键复制。填了就以填的为准。</div>
        </el-form-item>

        <el-divider content-position="left">链接与展示</el-divider>

        <el-form-item label="原文链接" prop="sourceUrl">
          <el-input v-model="form.sourceUrl" placeholder="https://…（出版社/期刊页面）" maxlength="500" />
          <div class="form-tip">前台「阅读原文」按钮，新标签页打开。只收 http:// 或 https:// 开头的完整地址。</div>
        </el-form-item>

        <el-form-item label="全文 PDF" prop="pdfUrl">
          <!-- 直传阿里云 OSS（action-gmu · 华南3 广州），存的是公网直链，
               不走 /common/upload 的本地磁盘通道 —— 官网是静态站，文件不能跟着后端机器走 -->
          <file-upload
            v-model="form.pdfUrl"
            :limit="1"
            :file-size="30"
            :file-type="['pdf']"
            :drag="false"
            action="/action/admin/publication/file"
          />
          <div class="form-tip">
            留空则前台不显示下载按钮。<b>这个存储桶是公开可读的</b>，
            只放已正式发表、有权公开分发的全文（注意出版社的版权政策）。
          </div>
        </el-form-item>

        <el-form-item label="配图" prop="coverImageUrl">
          <image-upload
            v-model="form.coverImageUrl"
            :limit="1"
            :file-size="5"
            :file-type="['png', 'jpg', 'jpeg', 'webp']"
            :drag="false"
            action="/action/admin/publication/cover"
          />
          <div class="form-tip">留空则详情页用纯色页头。横图最佳（前台作页头底图，会压暗处理）。</div>
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="显示顺序" prop="sortNum">
              <el-input-number v-model="form.sortNum" :min="0" controls-position="right" style="width: 100%" />
              <div class="form-tip">同一年内越小越靠前；留空则自动排到该年末尾。</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-radio-group v-model="form.status">
                <el-radio v-for="dict in sys_normal_disable" :key="dict.value" :value="dict.value">{{ dict.label }}</el-radio>
              </el-radio-group>
              <div class="form-tip">停用后该论文从官网列表与详情页消失。</div>
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

<script setup name="Publication">
import {
  listPublication,
  getPublication,
  addPublication,
  updatePublication,
  delPublication,
  parsePublicationDoi,
  parsePublicationPdf
} from "@/api/system/publication";

const { proxy } = getCurrentInstance();
const { sys_normal_disable } = proxy.useDict("sys_normal_disable");

const publicationList = ref([]);
const open = ref(false);
const loading = ref(true);
const parsing = ref(false);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");
const parseSource = ref("");
const keywordInputVisible = ref(false);
const keywordInputValue = ref("");
const keywordInputRef = ref(null);

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    keyword: undefined,
    year: undefined,
    status: undefined
  },
  rules: {
    title: [
      { required: true, message: "标题不能为空", trigger: "blur" },
      { max: 500, message: "标题不能超过500个字符", trigger: "blur" }
    ],
    sourceUrl: [
      { pattern: /^https?:\/\/\S+$/, message: "必须是 http:// 或 https:// 开头的完整地址", trigger: "blur" }
    ]
  }
});

const { queryParams, form, rules } = toRefs(data);

/** 列表里那一栏作者：三位以上写 et al.，与引用文本口径一致 */
function summarizeAuthors(authors) {
  if (!authors || authors.length === 0) return "—";
  const names = authors.slice(0, 3).map(a => a.name);
  return names.join(", ") + (authors.length > 3 ? ", et al." : "");
}

/** 查询成果发表列表 */
function getList() {
  loading.value = true;
  listPublication(queryParams.value).then(response => {
    publicationList.value = response.rows;
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
    publicationId: undefined,
    title: undefined,
    authors: [],
    affiliations: [],
    abstract: undefined,
    keywords: [],
    journal: undefined,
    volume: undefined,
    issue: undefined,
    pages: undefined,
    publicationYear: undefined,
    doi: undefined,
    sourceUrl: undefined,
    pdfUrl: undefined,
    coverImageUrl: undefined,
    citationText: undefined,
    // 新增时不传 sortNum，后端会自动排到该年末尾
    sortNum: undefined,
    status: "0",
    remark: undefined
  };
  parseSource.value = "";
  keywordInputVisible.value = false;
  keywordInputValue.value = "";
  proxy.resetForm("pubRef");
}

/** 搜索按钮操作 */
function handleQuery() {
  queryParams.value.pageNum = 1;
  getList();
}

/** 重置按钮操作 */
function resetQuery() {
  proxy.resetForm("queryRef");
  queryParams.value.year = undefined;
  handleQuery();
}

/** 多选框选中数据 */
function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.publicationId);
  single.value = selection.length != 1;
  multiple.value = !selection.length;
}

/** 新增按钮操作 */
function handleAdd() {
  reset();
  open.value = true;
  title.value = "添加成果发表";
}

/** 修改按钮操作 */
function handleUpdate(row) {
  reset();
  const publicationId = row.publicationId || ids.value;
  getPublication(publicationId).then(response => {
    // 三个列表字段后端一定给数组，这里仍兜一次：手改过库的老数据可能是 null
    form.value = { ...response.data };
    form.value.authors = form.value.authors || [];
    form.value.affiliations = form.value.affiliations || [];
    form.value.keywords = form.value.keywords || [];
    open.value = true;
    title.value = "修改成果发表";
  });
}

/**
 * 把解析回来的草稿灌进表单。
 *
 * 「谁赢」这件事分得很清：解析结果覆盖论文本身的字段（标题/作者/期刊…），
 * 但**不碰运营字段**（id / 排序 / 状态 / 已上传的全文与配图 / 备注）——
 * 那些是管理员在这台机器上做的决定，重新解析一次不该把它们抹掉。
 */
function applyDraft(draft) {
  const keep = {
    publicationId: form.value.publicationId,
    sortNum: form.value.sortNum,
    status: form.value.status || "0",
    pdfUrl: form.value.pdfUrl,
    coverImageUrl: form.value.coverImageUrl,
    remark: form.value.remark
  };
  form.value = {
    ...form.value,
    ...draft,
    ...keep,
    authors: draft.authors || [],
    affiliations: draft.affiliations || [],
    keywords: draft.keywords || []
  };
}

/**
 * 解析结果的提示。
 *
 * 后端会在 msg 里说清「哪几项没拿到、关键词是不是 MeSH 主题词」——
 * 这类提示得让人看见：摘要与关键词是空的时候，一句绿色的「解析成功」加两个空框，
 * 会被当成解析坏了，而实际该做的是手填或改用 PDF 解析。所以带「未能获取」的走警告色。
 */
function notifyParsed(msg, fallback) {
  const text = msg || fallback;
  if (text.includes("未能获取")) {
    proxy.$modal.msgWarning(text);
  } else {
    proxy.$modal.msgSuccess(text);
  }
}

/** 已经填了内容时，解析前先问一句 —— 覆盖的是管理员刚敲进去的字 */
function confirmOverwrite() {
  if (!form.value.title) return Promise.resolve();
  return proxy.$modal.confirm("解析结果会覆盖已填写的论文信息（不影响排序、状态与已上传的文件），是否继续？");
}

/** 按 DOI 解析 */
function handleParseDoi() {
  if (!parseSource.value) return;
  confirmOverwrite()
    .then(() => {
      parsing.value = true;
      return parsePublicationDoi(parseSource.value);
    })
    .then(response => {
      applyDraft(response.data || {});
      notifyParsed(response.msg, "解析成功，请核对各字段后保存");
    })
    .catch(() => {})
    .finally(() => {
      parsing.value = false;
    });
}

/**
 * 按 PDF 解析。
 *
 * 返回 false 阻止 el-upload 自己发请求：这个口不是上传口，它只解析、不存文件，
 * 请求要带上 axios 那套鉴权与错误处理（走 @/api）。
 */
function handleParsePdf(file) {
  confirmOverwrite()
    .then(() => {
      parsing.value = true;
      const fd = new FormData();
      fd.append("file", file);
      return parsePublicationPdf(fd);
    })
    .then(response => {
      applyDraft(response.data || {});
      notifyParsed(response.msg, "解析成功，请逐项核对后保存");
    })
    .catch(() => {})
    .finally(() => {
      parsing.value = false;
    });
  return false;
}

/** 提交按钮 */
function submitForm() {
  proxy.$refs["pubRef"].validate(valid => {
    if (!valid) return;
    // 空姓名的作者行后端也会丢，这里先清一遍，免得「机构序号越界」报在一行空作者上
    const payload = {
      ...form.value,
      authors: (form.value.authors || []).filter(a => (a.name || "").trim()),
      affiliations: (form.value.affiliations || []).filter(a => (a || "").trim())
    };
    if (payload.publicationId != undefined) {
      updatePublication(payload).then(() => {
        proxy.$modal.msgSuccess("修改成功");
        open.value = false;
        getList();
      });
    } else {
      addPublication(payload).then(() => {
        proxy.$modal.msgSuccess("新增成功");
        open.value = false;
        getList();
      });
    }
  });
}

/** 删除按钮操作 */
function handleDelete(row) {
  const publicationIds = row.publicationId || ids.value;
  proxy.$modal
    .confirm('是否确认删除成果编号为"' + publicationIds + '"的数据项？')
    .then(function () {
      return delPublication(publicationIds);
    })
    .then(() => {
      getList();
      proxy.$modal.msgSuccess("删除成功");
    })
    .catch(() => {});
}

function addAffiliation() {
  form.value.affiliations.push("");
}

/**
 * 删机构时把作者的机构序号重新对号。
 *
 * 不重排的话，删掉第 1 家单位后，原本挂着第 2 家的作者会指向第 3 家 ——
 * 页面上那个角标仍是个合法数字，只有作者本人看得出来挂错了单位。
 */
function removeAffiliation(idx) {
  form.value.affiliations.splice(idx, 1);
  form.value.authors.forEach(a => {
    if (a.affiliationIndex === null || a.affiliationIndex === undefined) return;
    if (a.affiliationIndex === idx) {
      a.affiliationIndex = null;
    } else if (a.affiliationIndex > idx) {
      a.affiliationIndex -= 1;
    }
  });
}

function addAuthor() {
  form.value.authors.push({ name: "", affiliationIndex: null });
}

function removeAuthor(idx) {
  form.value.authors.splice(idx, 1);
}

function showKeywordInput() {
  keywordInputVisible.value = true;
  nextTick(() => {
    keywordInputRef.value?.focus();
  });
}

function addKeyword() {
  const value = keywordInputValue.value.trim();
  if (value && !form.value.keywords.includes(value)) {
    form.value.keywords.push(value);
  }
  keywordInputVisible.value = false;
  keywordInputValue.value = "";
}

function removeKeyword(idx) {
  form.value.keywords.splice(idx, 1);
}

getList();
</script>

<style scoped>
.pub-editor {
  width: 100%;
}
.pub-editor__row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.pub-editor__index {
  min-width: 26px;
  color: #909399;
  font-size: 13px;
}
.pub-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.pub-muted {
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
