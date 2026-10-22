<template>
  <div class="app-container">
    <!-- 概览：语料构成披露的后台版本。阴性结果篇数刻意与阳性并排显示 —— 这批语料
         阴性 0 篇，是必须让维护者一眼看见的事实，藏进二级页面就等于没披露 -->
    <el-row :gutter="10" class="mb8 stat-row" v-if="stats.total">
      <el-col :span="4">
        <div class="stat"><div class="sv">{{ stats.total }}</div><div class="sl">文献总数</div></div>
      </el-col>
      <el-col :span="4">
        <div class="stat"><div class="sv">{{ stats.recent5 }}</div><div class="sl">近 5 年</div></div>
      </el-col>
      <el-col :span="4">
        <div class="stat clickable" @click="quickFilter('quality', 'needReview')">
          <div class="sv warn">{{ stats.pending }}</div><div class="sl">待复核</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat clickable" @click="quickFilter('quality', 'contaminated')">
          <div class="sv warn">{{ stats.contaminated }}</div><div class="sl">夹带未处理</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat clickable" @click="quickFilter('quality', 'truncated')">
          <div class="sv warn">{{ stats.truncated }}</div><div class="sl">正文截断</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat clickable" @click="quickFilter('quality', 'lowYear')">
          <div class="sv warn">{{ stats.lowYear }}</div><div class="sl">年份存疑</div>
        </div>
      </el-col>
    </el-row>

    <el-alert type="info" :closable="false" class="mb8" show-icon>
      本表是<b>「研究背景与讨论智能生成」的唯一数据源</b>，记录由 <code>python -m tools.lit_ingest</code>
      从 PDF 离线抽取而来，<b>不支持手工新增</b>——一条记录必须对应一个真实的 PDF 文件，凭空建一条会得到一份没有原文可核的元数据。补语料请跑抽取脚本。
      <br />
      这里的主要工作是<b>复核</b>：先看上方四个橙色数字，逐类清掉。判为「剔除」的记录会同步停用、不再进检索。
      <br />
      <b>效应方向按主要结局判，不按摘要结论句判。</b>中文文献摘要常写「疗效显著」而数据是终点组间无差异（P&gt;0.05）——
      这一列一旦判错，生成背景时的「证据不一致检测」会整个失效，模型就会把混合证据写成「疗效确切」。
      当前语料<b>阴性结果 {{ stats.negative }} 篇</b>，阳性 {{ stats.positive }} 篇，存在明显发表偏倚。
    </el-alert>

    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="88px">
      <el-form-item label="关键词" prop="keyword">
        <el-input v-model="queryParams.keyword" placeholder="标题 / 期刊 / 作者 / 摘要 / 病种" clearable
                  style="width: 250px" @keyup.enter="handleQuery" />
      </el-form-item>
      <el-form-item label="语料编号" prop="corpusNo">
        <el-input v-model="queryParams.corpusNo" placeholder="如 100" clearable style="width: 110px"
                  @keyup.enter="handleQuery" />
      </el-form-item>
      <el-form-item label="病种类目" prop="conditionGroup">
        <el-select v-model="queryParams.conditionGroup" placeholder="全部" clearable filterable style="width: 190px">
          <el-option v-for="g in groupOptions" :key="g.name" :label="`${g.name}（${g.hits}）`" :value="g.name" />
        </el-select>
      </el-form-item>
      <el-form-item label="研究设计" prop="studyDesign">
        <el-select v-model="queryParams.studyDesign" placeholder="全部" clearable style="width: 160px">
          <el-option v-for="d in DESIGNS" :key="d.value" :label="d.label" :value="d.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="效应方向" prop="effectDirection">
        <el-select v-model="queryParams.effectDirection" placeholder="全部" clearable style="width: 150px">
          <el-option v-for="d in DIRECTIONS" :key="d.value" :label="d.label" :value="d.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="质量标记" prop="quality">
        <el-select v-model="queryParams.quality" placeholder="全部" clearable style="width: 160px">
          <el-option label="待复核" value="needReview" />
          <el-option label="夹带未处理" value="contaminated" />
          <el-option label="正文截断" value="truncated" />
          <el-option label="年份存疑" value="lowYear" />
          <el-option label="抽取失败" value="failed" />
        </el-select>
      </el-form-item>
      <el-form-item label="复核状态" prop="reviewStatus">
        <el-select v-model="queryParams.reviewStatus" placeholder="全部" clearable style="width: 130px">
          <el-option v-for="r in REVIEWS" :key="r.value" :label="r.label" :value="r.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="语言" prop="lang">
        <el-select v-model="queryParams.lang" placeholder="全部" clearable style="width: 100px">
          <el-option label="中文" value="zh" />
          <el-option label="英文" value="en" />
        </el-select>
      </el-form-item>
      <el-form-item label="出版年" prop="yearBegin">
        <el-input v-model="queryParams.yearBegin" placeholder="起" clearable style="width: 90px" />
        <span class="year-sep">-</span>
        <el-input v-model="queryParams.yearEnd" placeholder="止" clearable style="width: 90px" />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="全部" clearable style="width: 110px">
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
        <el-button type="success" plain icon="Edit" :disabled="single" @click="handleUpdate"
                   v-hasPermi="['action:literature:edit']">修改</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="primary" plain icon="Select" :disabled="multiple" @click="handleReview('ok')"
                   v-hasPermi="['action:literature:edit']">标记已核</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="warning" plain icon="CircleClose" :disabled="multiple" @click="handleReview('rejected')"
                   v-hasPermi="['action:literature:edit']">剔除（停用）</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="danger" plain icon="Delete" :disabled="multiple" @click="handleDelete"
                   v-hasPermi="['action:literature:remove']">删除</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table v-loading="loading" :data="litList" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="50" align="center" />
      <el-table-column label="编号" prop="corpusNo" width="66" align="center" />
      <el-table-column label="题名" prop="title" min-width="280" show-overflow-tooltip>
        <template #default="scope">
          <!-- 显示的是**原文题名**（中文文献即中文题名）：引用输出用的就是这一列，
               而甲方给的 目录.xlsx 全是英文译名，靠它引用的话读者检索不到原文 -->
          <span>{{ scope.row.title }}</span>
          <!-- 质量标记直接挂在标题上：复核时最先要看的就是这几个 -->
          <el-tag v-if="scope.row.contamination === '1' && !['ok', 'na'].includes(scope.row.cleanStatus)"
                  type="danger" size="small" class="ml4">夹带</el-tag>
          <el-tag v-else-if="scope.row.cleanStatus === 'ok'" type="success" size="small" class="ml4">已切除</el-tag>
          <el-tag v-if="scope.row.truncated === '1'" type="warning" size="small" class="ml4">截断</el-tag>
          <el-tag v-if="scope.row.yearConfidence !== 'high'" type="warning" size="small" class="ml4">年份存疑</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="期刊 / 年份" width="180" show-overflow-tooltip>
        <template #default="scope">
          <div>{{ scope.row.journal || "—" }}</div>
          <div class="sub">{{ scope.row.year || "年份不详" }} · {{ scope.row.lang === "en" ? "英文" : "中文" }}</div>
        </template>
      </el-table-column>
      <el-table-column label="设计" prop="studyDesign" width="88" align="center">
        <template #default="scope">
          <el-tag :type="scope.row.studyDesign === 'protocol' ? 'info' : ''" size="small">
            {{ designLabel(scope.row.studyDesign) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="n" prop="sampleSize" width="62" align="center">
        <template #default="scope">{{ scope.row.sampleSize ?? "—" }}</template>
      </el-table-column>
      <el-table-column label="效应方向" prop="effectDirection" width="100" align="center">
        <template #default="scope">
          <el-tag :type="directionType(scope.row.effectDirection)" size="small">
            {{ directionLabel(scope.row.effectDirection) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="病种类目" width="150" show-overflow-tooltip>
        <template #default="scope">{{ (scope.row.conditionGroup || []).join(" / ") || "—" }}</template>
      </el-table-column>
      <el-table-column label="复核" prop="reviewStatus" width="86" align="center">
        <template #default="scope">
          <el-tag :type="reviewType(scope.row.reviewStatus)" size="small">
            {{ reviewLabel(scope.row.reviewStatus) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" prop="status" width="72" align="center">
        <template #default="scope">
          <dict-tag :options="sys_normal_disable" :value="scope.row.status" />
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" width="170" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="handleText(scope.row)"
                     v-hasPermi="['action:literature:query']">原文</el-button>
          <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)"
                     v-hasPermi="['action:literature:edit']">修改</el-button>
          <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)"
                     v-hasPermi="['action:literature:remove']">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <pagination v-show="total > 0" :total="total" v-model:page="queryParams.pageNum"
                v-model:limit="queryParams.pageSize" @pagination="getList" />

    <!-- 编辑抽屉。字段多，用抽屉而不是对话框，右侧还能同时对着原文核 -->
    <el-drawer :title="title" v-model="open" size="52%" :close-on-click-modal="false">
      <el-form ref="litRef" :model="form" :rules="rules" label-width="96px">
        <el-alert v-if="form.contaminationNote" type="warning" :closable="false" class="mb8" show-icon>
          <b>PDF 夹带其他论文内容：</b>{{ form.contaminationNote }}
          <template v-if="form.intruders && form.intruders.length">
            <br /><b>混入：</b>{{ form.intruders.join(" / ") }}
          </template>
          <template v-if="form.cleanStatus === 'ok'">
            <br /><span class="ok">已自动切除，保留原文的 {{ form.cleanRatio }}%</span>
          </template>
        </el-alert>
        <el-alert v-if="form.truncated === '1'" type="warning" :closable="false" class="mb8" show-icon>
          <b>正文截断：</b>本文含「下转第 X 页」而续页不在这个 PDF 里，讨论后段与自身参考文献缺失。
          切除夹带救不了这个，前台展示时应提示读者。
        </el-alert>

        <el-descriptions :column="3" size="small" border class="mb8">
          <el-descriptions-item label="语料编号">{{ form.corpusNo }}</el-descriptions-item>
          <el-descriptions-item label="页数">{{ form.pages ?? "—" }}</el-descriptions-item>
          <el-descriptions-item label="正文字符">{{ form.textChars ?? "—" }}</el-descriptions-item>
          <el-descriptions-item label="文件名" :span="3">{{ form.fileName }}</el-descriptions-item>
          <el-descriptions-item label="抽取模型" :span="2">{{ form.extractModel || "—" }}</el-descriptions-item>
          <el-descriptions-item label="抽取时间">{{ parseTime(form.extractTime, "{y}-{m}-{d}") || "—" }}</el-descriptions-item>
        </el-descriptions>

        <el-form-item label="原文题名" prop="title">
          <el-input v-model="form.title" type="textarea" :rows="2"
                    placeholder="按 PDF 原语言照录，中文文献填中文题名。引用输出用这一列" />
        </el-form-item>
        <el-form-item label="英文题名">
          <el-input v-model="form.titleEn" type="textarea" :rows="2"
                    placeholder="取自 目录.xlsx，同时是抽取时的防夹带锚。英文文献与上面同值" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="出版年" prop="year">
              <el-input v-model.number="form.year" placeholder="如 2023" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="年份可信度">
              <el-select v-model="form.yearConfidence" style="width: 100%">
                <el-option label="high 有明确依据" value="high" />
                <el-option label="low 正文无依据" value="low" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="语言">
              <el-select v-model="form.lang" style="width: 100%">
                <el-option label="中文" value="zh" />
                <el-option label="英文" value="en" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="年份依据">
          <el-input v-model="form.yearEvidence" placeholder="抽取时判定出版年所依据的正文原文片段，供复核" />
          <div class="tip">正文首两页平均出现 4 个不同年份（参考文献年、基金年、收稿年、作者出生年），所以要留依据。</div>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="16">
            <el-form-item label="期刊">
              <el-input v-model="form.journal" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="国家">
              <el-input v-model="form.country" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="作者">
          <tag-editor v-model="form.authors" placeholder="回车添加，顺序即署名顺序" />
        </el-form-item>

        <el-divider content-position="left">证据属性</el-divider>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="研究设计">
              <el-select v-model="form.studyDesign" style="width: 100%">
                <el-option v-for="d in DESIGNS" :key="d.value" :label="d.label" :value="d.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="样本量">
              <el-input v-model.number="form.sampleSize" placeholder="总样本量" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="效应方向">
              <el-select v-model="form.effectDirection" style="width: 100%">
                <el-option v-for="d in DIRECTIONS" :key="d.value" :label="d.label" :value="d.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="主要结果">
          <el-input v-model="form.findingSummary" type="textarea" :rows="3" />
          <div class="tip">
            效应方向<b>按主要结局判</b>：摘要写「疗效显著」而终点组间无差异（P&gt;0.05）的，一律填「无差异」；
            主要结局阴性、次要结局阳性的也填「无差异」，把两者都写进这里。
          </div>
        </el-form-item>
        <el-form-item label="研究对象">
          <el-input v-model="form.population" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="摘要">
          <el-input v-model="form.abstract" type="textarea" :rows="4" />
        </el-form-item>

        <el-divider content-position="left">PICO 标签</el-divider>
        <el-form-item label="病种">
          <tag-editor v-model="form.condition" />
        </el-form-item>
        <el-form-item label="病种类目">
          <tag-editor v-model="form.conditionGroup" />
          <div class="tip">
            上位类目，<b>覆盖度统计与检索扩展按它算</b>（原始病种标签 485 个、80% 只出现一次，按原始标签算几乎所有方向都会被判「本库撑不住」）。
            批量维护走 <code>python -m tools.lit_conditions</code>。
          </div>
        </el-form-item>
        <el-form-item label="干预">
          <tag-editor v-model="form.intervention" />
        </el-form-item>
        <el-form-item label="对照">
          <tag-editor v-model="form.comparator" />
          <div class="tip">
            <b>只写措施名，不要写剂量、给药方式、疗程。</b>生成背景时按它把研究分成「vs 假针刺」和「vs 阳性药」两组做不一致检测，
            写成自由描述会让分组静默错分，而结果看着完全正常。
          </div>
        </el-form-item>
        <el-form-item label="结局指标">
          <tag-editor v-model="form.outcomes" />
        </el-form-item>
        <el-form-item label="中医证候">
          <tag-editor v-model="form.tcmSyndrome" />
        </el-form-item>

        <el-divider content-position="left">针灸方案</el-divider>
        <el-form-item label="穴位">
          <tag-editor v-model="form.acuPoints" placeholder="国际代码优先，如 ST36、EX-HN3" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="针法">
              <el-input v-model="form.acuMethod" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="电针频率">
              <el-input v-model="form.acuFrequency" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="得气">
              <el-select v-model="form.acuDeqi" clearable style="width: 100%">
                <el-option label="报告了得气" value="1" />
                <el-option label="明确未得气" value="0" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="留针(min)">
              <el-input v-model.number="form.acuRetentionMin" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="治疗次数">
              <el-input v-model.number="form.acuSessions" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="疗程(周)">
              <el-input v-model.number="form.acuCourseWeeks" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">复核</el-divider>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="复核状态">
              <el-select v-model="form.reviewStatus" style="width: 100%">
                <el-option v-for="r in REVIEWS" :key="r.value" :label="r.label" :value="r.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="form.status" style="width: 100%">
                <el-option v-for="dict in sys_normal_disable" :key="dict.value" :label="dict.label"
                           :value="dict.value" />
              </el-select>
              <div class="tip">停用即不进检索。</div>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cancel">取 消</el-button>
        <el-button type="primary" @click="submitForm">确 定</el-button>
      </template>
    </el-drawer>

    <!-- 原文抽屉。cleanText 与 fullText 分两个 tab：复核时要能看到「切掉的到底是什么」 -->
    <el-drawer :title="`#${textRow.corpusNo} 原文`" v-model="textOpen" size="46%">
      <el-tabs v-model="textTab" v-loading="textLoading">
        <el-tab-pane :label="`检索用正文（${(textData.cleanText || textData.fullText || '').length} 字符）`" name="clean">
          <pre class="raw">{{ textData.cleanText || textData.fullText || "（无）" }}</pre>
        </el-tab-pane>
        <el-tab-pane v-if="textData.cleanText" :label="`PDF 原始正文（${(textData.fullText || '').length} 字符）`"
                     name="full">
          <el-alert type="info" :closable="false" class="mb8" show-icon>
            这是切除夹带前的原文。检索与展示用的是左边那份；这份留着是为了能核对切掉的内容、切错时能回滚。
          </el-alert>
          <pre class="raw">{{ textData.fullText }}</pre>
        </el-tab-pane>
      </el-tabs>
    </el-drawer>
  </div>
</template>

<script setup name="Literature">
import {
  getLiteratureStats,
  listConditionGroup,
  listLiterature,
  getLiterature,
  getLiteratureText,
  updateLiterature,
  reviewLiterature,
  delLiterature
} from "@/api/system/literature";
import TagEditor from "./TagEditor.vue";

const { proxy } = getCurrentInstance();
const { sys_normal_disable } = proxy.useDict("sys_normal_disable");

const DESIGNS = [
  { value: "rct", label: "随机对照" },
  { value: "nrct", label: "非随机对照" },
  { value: "sr_meta", label: "系统综述/Meta" },
  { value: "animal", label: "动物/机制" },
  { value: "case_series", label: "病例系列" },
  { value: "protocol", label: "研究方案" },
  { value: "other", label: "其他" }
];
const DIRECTIONS = [
  { value: "positive", label: "阳性" },
  { value: "no_difference", label: "无差异" },
  { value: "negative", label: "阴性" },
  { value: "unclear", label: "无法判定" }
];
const REVIEWS = [
  { value: "pending", label: "待复核" },
  { value: "ok", label: "已核" },
  { value: "fixed", label: "已修正" },
  { value: "rejected", label: "已剔除" }
];

const litList = ref([]);
const groupOptions = ref([]);
const stats = ref({});
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");
const textOpen = ref(false);
const textLoading = ref(false);
const textTab = ref("clean");
const textRow = ref({});
const textData = ref({});

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 20,
    keyword: undefined,
    corpusNo: undefined,
    conditionGroup: undefined,
    studyDesign: undefined,
    effectDirection: undefined,
    lang: undefined,
    reviewStatus: undefined,
    quality: undefined,
    yearBegin: undefined,
    yearEnd: undefined,
    status: undefined
  },
  rules: {
    title: [{ required: true, message: "标题不能为空", trigger: "blur" }]
  }
});

const { queryParams, form, rules } = toRefs(data);

const designLabel = v => DESIGNS.find(d => d.value === v)?.label || v || "—";
const directionLabel = v => DIRECTIONS.find(d => d.value === v)?.label || v || "—";
const reviewLabel = v => REVIEWS.find(d => d.value === v)?.label || v || "—";
const directionType = v =>
  ({ positive: "success", no_difference: "warning", negative: "danger" })[v] || "info";
const reviewType = v => ({ ok: "success", fixed: "success", rejected: "danger" })[v] || "warning";

/** 顶部概览卡片点一下就筛出对应的那批 —— 复核的主线就是「看见数字 → 逐类清掉」 */
function quickFilter(field, value) {
  proxy.resetForm("queryRef");
  queryParams.value[field] = value;
  handleQuery();
}

function getList() {
  loading.value = true;
  listLiterature(queryParams.value).then(res => {
    litList.value = res.rows;
    total.value = res.total;
    loading.value = false;
  });
}

function refreshStats() {
  getLiteratureStats().then(res => (stats.value = res.data || {}));
}

function cancel() {
  open.value = false;
  reset();
}

function reset() {
  form.value = {};
  proxy.resetForm("litRef");
}

function handleQuery() {
  queryParams.value.pageNum = 1;
  getList();
}

function resetQuery() {
  proxy.resetForm("queryRef");
  handleQuery();
}

function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.litId);
  single.value = selection.length !== 1;
  multiple.value = !selection.length;
}

function handleUpdate(row) {
  reset();
  const litId = row?.litId || ids.value[0];
  getLiterature(litId).then(res => {
    form.value = res.data;
    open.value = true;
    title.value = `#${res.data.corpusNo} 复核参考文献`;
  });
}

function handleText(row) {
  textRow.value = row;
  textOpen.value = true;
  textTab.value = "clean";
  textLoading.value = true;
  textData.value = {};
  getLiteratureText(row.litId)
    .then(res => (textData.value = res.data || {}))
    .finally(() => (textLoading.value = false));
}

function submitForm() {
  proxy.$refs["litRef"].validate(valid => {
    if (!valid) return;
    updateLiterature(form.value).then(() => {
      proxy.$modal.msgSuccess("修改成功");
      open.value = false;
      getList();
      refreshStats();
    });
  });
}

/** 批量复核。剔除会同步停用，所以单独确认一次 —— 它改的不只是一个标记 */
function handleReview(status) {
  const litIds = ids.value.join(",");
  const label = reviewLabel(status);
  const extra = status === "rejected" ? "，并同步停用（不再进入检索）" : "";
  proxy.$modal
    .confirm(`确认将选中的 ${ids.value.length} 条标记为「${label}」${extra}？`)
    .then(() => reviewLiterature({ litIds, reviewStatus: status }))
    .then(() => {
      getList();
      refreshStats();
      proxy.$modal.msgSuccess("操作成功");
    })
    .catch(() => {});
}

function handleDelete(row) {
  const litIds = row?.litId || ids.value.join(",");
  proxy.$modal
    .confirm(`确认删除语料编号为「${row?.corpusNo || litIds}」的文献？元数据逻辑删除，全文将被物理删除。`)
    .then(() => delLiterature(litIds))
    .then(() => {
      getList();
      refreshStats();
      proxy.$modal.msgSuccess("删除成功");
    })
    .catch(() => {});
}

listConditionGroup().then(res => (groupOptions.value = res.data || []));
refreshStats();
getList();
</script>

<style scoped>
.stat-row .stat {
  background: var(--el-fill-color-light);
  border-radius: 6px;
  padding: 10px 0;
  text-align: center;
}
.stat-row .stat.clickable {
  cursor: pointer;
}
.stat-row .stat.clickable:hover {
  background: var(--el-color-primary-light-9);
}
.stat-row .sv {
  font-size: 22px;
  font-weight: 600;
  line-height: 1.2;
}
.stat-row .sv.warn {
  color: var(--el-color-warning);
}
.stat-row .sl {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}
.sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
  margin-top: 2px;
}
.ok {
  color: var(--el-color-success);
}
.ml4 {
  margin-left: 4px;
}
.year-sep {
  padding: 0 6px;
  color: var(--el-text-color-secondary);
}
.raw {
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  line-height: 1.75;
  max-height: calc(100vh - 200px);
  overflow: auto;
  margin: 0;
  font-family: Menlo, Consolas, monospace;
}
</style>
