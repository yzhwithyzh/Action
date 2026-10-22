<template>
  <div>
    <el-upload
      :action="uploadUrl"
      :before-upload="handleBeforeUpload"
      :on-success="handleUploadSuccess"
      :on-error="handleUploadError"
      name="file"
      :show-file-list="false"
      :headers="headers"
      class="editor-img-uploader"
      v-if="type == 'url'"
    >
      <i ref="uploadRef" class="editor-img-uploader"></i>
    </el-upload>
  </div>
  <div class="editor">
    <quill-editor
      ref="quillEditorRef"
      v-model:content="content"
      contentType="html"
      @textChange="(e) => $emit('update:modelValue', content)"
      :options="options"
      :style="styles"
    />
  </div>
</template>

<script setup>
import axios from 'axios';
import { QuillEditor } from "@vueup/vue-quill";
import "@vueup/vue-quill/dist/vue-quill.snow.css";
import { getToken } from "@/utils/auth";
import { isExternal } from "@/utils/validate";

const { proxy } = getCurrentInstance();
const emit = defineEmits(["update:modelValue"]);

const quillEditorRef = ref();
const headers = ref({
  Authorization: "Bearer " + getToken()
});

const props = defineProps({
  /* 编辑器的内容 */
  modelValue: {
    type: String,
  },
  /**
   * 图片上传接口。
   *
   * 默认 `/common/upload` 落**后端本地磁盘**，返回的是 `/profile/upload/...` 相对路径，
   * 只适合「图片和页面同域」的场景（后台通知公告就是）。
   *
   * **官网内容必须传 OSS 的地址**（如新闻正文的 `/action/admin/news/image`）：
   * 官网是另一个域的静态站，本地磁盘那条路径它取不到，正文里的图会整片裂；
   * 而且图片跟着后端机器走，换机或多副本部署就开天窗。
   */
  action: {
    type: String,
    default: "/common/upload"
  },
  /* 高度 */
  height: {
    type: Number,
    default: null,
  },
  /* 最小高度 */
  minHeight: {
    type: Number,
    default: null,
  },
  /* 只读 */
  readOnly: {
    type: Boolean,
    default: false,
  },
  /* 上传文件大小限制(MB) */
  fileSize: {
    type: Number,
    default: 5,
  },
  /* 类型（base64格式、url格式） */
  type: {
    type: String,
    default: "url",
  }
});

const uploadUrl = computed(() => import.meta.env.VITE_APP_BASE_API + props.action);

const options = ref({
  theme: "snow",
  bounds: document.body,
  debug: "warn",
  modules: {
    // 工具栏配置
    toolbar: [
      ["bold", "italic", "underline", "strike"],      // 加粗 斜体 下划线 删除线
      ["blockquote", "code-block"],                   // 引用  代码块
      [{ list: "ordered" }, { list: "bullet" }],      // 有序、无序列表
      [{ indent: "-1" }, { indent: "+1" }],           // 缩进
      [{ size: ["small", false, "large", "huge"] }],  // 字体大小
      [{ header: [1, 2, 3, 4, 5, 6, false] }],        // 标题
      [{ color: [] }, { background: [] }],            // 字体颜色、字体背景颜色
      [{ align: [] }],                                // 对齐方式
      ["clean"],                                      // 清除文本格式
      ["link", "image", "video"]                      // 链接、图片、视频
    ],
  },
  placeholder: "请输入内容",
  readOnly: props.readOnly
});

const styles = computed(() => {
  let style = {};
  if (props.minHeight) {
    style.minHeight = `${props.minHeight}px`;
  }
  if (props.height) {
    style.height = `${props.height}px`;
  }
  return style;
});

const content = ref("");
watch(() => props.modelValue, (v) => {
  if (v !== content.value) {
    content.value = v == undefined ? "<p></p>" : v;
  }
}, { immediate: true });

// 如果设置了上传地址则自定义图片上传事件
onMounted(() => {
  if (props.type == 'url') {
    let quill = quillEditorRef.value.getQuill();
    let toolbar = quill.getModule("toolbar");
    toolbar.addHandler("image", (value) => {
      if (value) {
        proxy.$refs.uploadRef.click();
      } else {
        quill.format("image", false);
      }
    });
    quill.root.addEventListener('paste', handlePasteCapture, true);
  }
});

// 上传前校检格式和大小
function handleBeforeUpload(file) {
  // 与后端 OSS 通道的 ALLOWED_IMAGE_EXTENSIONS 对齐：**不含 svg**（公网直链 + SVG
  // 可带脚本，后端刻意不放行），补上 webp/gif（后端认，这里原先漏了，选了才被拒）
  const type = ["image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"];
  const isJPG = type.includes(file.type);
  //检验文件格式
  if (!isJPG) {
    proxy.$modal.msgError(`图片格式错误，仅支持 jpg/jpeg/png/webp/gif`);
    return false;
  }
  // 校检文件大小
  if (props.fileSize) {
    const isLt = file.size / 1024 / 1024 < props.fileSize;
    if (!isLt) {
      proxy.$modal.msgError(`上传文件大小不能超过 ${props.fileSize} MB!`);
      return false;
    }
  }
  return true;
}

// 上传成功处理
function handleUploadSuccess(res, file) {
  // 如果上传成功
  if (res.code == 200) {
    // 获取富文本实例
    let quill = toRaw(quillEditorRef.value).getQuill();
    // 获取光标位置。粘贴时 savedRange 可能还没更新，退到当前选区、再退到末尾
    let length = quill.selection.savedRange?.index ?? quill.getSelection(true)?.index ?? quill.getLength();
    // 插入图片。**OSS 那条通道返回的是 http(s) 公网直链，不能再拼 baseUrl**
    // ——拼了会得到 `/dev-api/https://action-gmu.oss-...` 这种打不开的地址。
    // 本地磁盘通道返回的仍是 `/profile/upload/...` 相对路径，那种要拼。
    const src = isExternal(res.fileName) ? res.fileName : import.meta.env.VITE_APP_BASE_API + res.fileName;
    quill.insertEmbed(length, "image", src);
    // 调整光标到最后
    quill.setSelection(length + 1);
  } else {
    proxy.$modal.msgError(res.msg || "图片插入失败");
  }
}

// 上传失败处理
function handleUploadError() {
  proxy.$modal.msgError("图片插入失败");
}

/**
 * 复制粘贴图片处理。
 *
 * 拦下来自己传，不让 quill 走默认行为 —— 它会把图片转成 base64 内嵌进正文，
 * 一张截图就是几百 KB 的字符串，直接进数据库、再进官网每个页面的 hydration payload。
 *
 * **只拦得到「剪贴板里确实有图片文件」那一种**（截图、或在 Word 里单独点中一张图复制）。
 * 从 Word 选中一整段（文字 + 图）复制时，剪贴板里只有 text/html，图片是
 * `<img src="file:///C:/…/msohtmlclip1/…">` 这种指向本机临时目录的地址，
 * 这里的 items 里根本没有 image/* —— 那一种由下面的 `sweepPastedImages` 收尾。
 */
function handlePasteCapture(e) {
  const clipboard = e.clipboardData || window.clipboardData;
  let handled = false;
  if (clipboard && clipboard.items) {
    for (let i = 0; i < clipboard.items.length; i++) {
      const item = clipboard.items[i];
      if (item.type.indexOf('image') !== -1) {
        e.preventDefault();
        handled = true;
        insertImage(item.getAsFile());
      }
    }
  }
  if (!handled) {
    // 先记下粘贴前已有的图，**只处理这次新进来的那些** —— 否则编辑一条老新闻时
    // 粘一段文字，会顺带把正文里原有的图片也重传一遍，行为不可预测
    const quill = toRaw(quillEditorRef.value)?.getQuill();
    const before = new Set(quill ? quill.root.querySelectorAll("img") : []);
    // 让 quill 先把这段 HTML 粘进去，下一拍再扫。粘贴是同步事件，
    // 此刻编辑器里还没有新内容，必须等它落地
    setTimeout(() => sweepPastedImages(before), 0);
  }
}

/**
 * 粘贴落地后扫一遍正文里的图片，把「不能直接用的 src」处理掉。
 *
 * 三种形态，命运不同：
 *  · `data:image/…`（base64 内嵌）—— 能转成 Blob，上传后换成 OSS 直链。
 *    不处理的话这串 base64 会原样进数据库，一张图几百 KB。
 *  · `blob:`（浏览器内存对象）—— 能 fetch 到字节，同样上传后替换。
 *    不处理的话它**只在当前这个标签页有效**，刷新就成裂图，而且保存进库的是一条死链。
 *  · `file:///`（Word 整段复制时的本地临时文件）—— **浏览器读不到，救不了**。
 *    留着就是官网上的坏图，所以就地删掉并告诉用户该怎么做。
 */
async function sweepPastedImages(before = new Set()) {
  const quill = toRaw(quillEditorRef.value)?.getQuill();
  if (!quill) return;
  const images = Array.from(quill.root.querySelectorAll("img")).filter(img => !before.has(img));
  const local = images.filter(img => (img.getAttribute("src") || "").startsWith("file:"));
  const embedded = images.filter(img => /^(data:image\/|blob:)/i.test(img.getAttribute("src") || ""));

  // 读不到的那些先摘掉，别让它们跟着保存进库
  local.forEach(img => img.remove());
  if (local.length) {
    proxy.$modal.msgWarning(
      `有 ${local.length} 张图片来自 Word 的本地临时文件，浏览器无法读取，已跳过。` +
      `请在 Word 里单独点中图片复制后再粘贴，或用工具栏的图片按钮上传。`
    );
  }
  if (!embedded.length) {
    syncContent(quill);
    return;
  }

  proxy.$modal.loading(`正在上传 ${embedded.length} 张图片，请稍候...`);
  let failed = 0;
  for (const img of embedded) {
    try {
      const blob = await fetch(img.getAttribute("src")).then(r => r.blob());
      const ext = (blob.type.split("/")[1] || "png").replace("jpeg", "jpg");
      const file = new File([blob], `paste-${Date.now()}.${ext}`, { type: blob.type });
      if (!handleBeforeUpload(file)) {
        img.remove();
        continue;
      }
      const formData = new FormData();
      formData.append("file", file);
      const res = await axios.post(uploadUrl.value, formData, {
        headers: { "Content-Type": "multipart/form-data", Authorization: headers.value.Authorization },
        timeout: 120000
      });
      if (res.data?.code === 200) {
        img.setAttribute("src", isExternal(res.data.fileName)
          ? res.data.fileName
          : import.meta.env.VITE_APP_BASE_API + res.data.fileName);
      } else {
        failed++;
        img.remove();
      }
    } catch {
      failed++;
      // 传不上去的就摘掉：留着一张只在本标签页有效的 blob: 图，保存后就是死链
      img.remove();
    }
  }
  proxy.$modal.closeLoading();
  if (failed) {
    proxy.$modal.msgError(`有 ${failed} 张图片上传失败，已从正文中移除，请手动重新插入`);
  }
  syncContent(quill);
}

/**
 * 直接改了 DOM，同步回 v-model。
 *
 * 不能只指望 quill 自己的 MutationObserver：删节点它认，但改 `img` 的 src 属性
 * 未必会触发 text-change，那样父组件里的正文还留着 base64 / blob: 的旧值。
 * 同时写 `content` 与 emit 是为了让 `watch(() => props.modelValue)` 里那句
 * `v !== content.value` 判 false，避免回灌一次把光标顶掉。
 */
function syncContent(quill) {
  content.value = quill.root.innerHTML;
  emit("update:modelValue", content.value);
}

function insertImage(file) {
  // 粘贴这条原先绕过了格式与大小校验：粘一张 20MB 的截图会怼到后端才被拒，
  // 而下面又没有 catch，用户看到的是「粘了图什么都没发生」
  if (!file || !handleBeforeUpload(file)) {
    return;
  }
  const formData = new FormData();
  formData.append("file", file);
  proxy.$modal.loading("正在上传图片，请稍候...");
  axios
    .post(uploadUrl.value, formData, {
      headers: { "Content-Type": "multipart/form-data", Authorization: headers.value.Authorization },
      // 图片走 OSS，可能比一次普通请求慢；不给的话会吃到 axios 默认那 10 秒
      timeout: 120000
    })
    .then(res => {
      handleUploadSuccess(res.data);
    })
    .catch(() => {
      proxy.$modal.msgError("图片上传失败");
    })
    .finally(() => {
      proxy.$modal.closeLoading();
    });
}
</script>

<style>
.editor-img-uploader {
  display: none;
}
.editor, .ql-toolbar {
  white-space: pre-wrap !important;
  line-height: normal !important;
}
.quill-img {
  display: none;
}
.ql-snow .ql-tooltip[data-mode="link"]::before {
  content: "请输入链接地址:";
}
.ql-snow .ql-tooltip.ql-editing a.ql-action::after {
  border-right: 0px;
  content: "保存";
  padding-right: 0px;
}
.ql-snow .ql-tooltip[data-mode="video"]::before {
  content: "请输入视频地址:";
}
.ql-snow .ql-picker.ql-size .ql-picker-label::before,
.ql-snow .ql-picker.ql-size .ql-picker-item::before {
  content: "14px";
}
.ql-snow .ql-picker.ql-size .ql-picker-label[data-value="small"]::before,
.ql-snow .ql-picker.ql-size .ql-picker-item[data-value="small"]::before {
  content: "10px";
}
.ql-snow .ql-picker.ql-size .ql-picker-label[data-value="large"]::before,
.ql-snow .ql-picker.ql-size .ql-picker-item[data-value="large"]::before {
  content: "18px";
}
.ql-snow .ql-picker.ql-size .ql-picker-label[data-value="huge"]::before,
.ql-snow .ql-picker.ql-size .ql-picker-item[data-value="huge"]::before {
  content: "32px";
}
.ql-snow .ql-picker.ql-header .ql-picker-label::before,
.ql-snow .ql-picker.ql-header .ql-picker-item::before {
  content: "文本";
}
.ql-snow .ql-picker.ql-header .ql-picker-label[data-value="1"]::before,
.ql-snow .ql-picker.ql-header .ql-picker-item[data-value="1"]::before {
  content: "标题1";
}
.ql-snow .ql-picker.ql-header .ql-picker-label[data-value="2"]::before,
.ql-snow .ql-picker.ql-header .ql-picker-item[data-value="2"]::before {
  content: "标题2";
}
.ql-snow .ql-picker.ql-header .ql-picker-label[data-value="3"]::before,
.ql-snow .ql-picker.ql-header .ql-picker-item[data-value="3"]::before {
  content: "标题3";
}
.ql-snow .ql-picker.ql-header .ql-picker-label[data-value="4"]::before,
.ql-snow .ql-picker.ql-header .ql-picker-item[data-value="4"]::before {
  content: "标题4";
}
.ql-snow .ql-picker.ql-header .ql-picker-label[data-value="5"]::before,
.ql-snow .ql-picker.ql-header .ql-picker-item[data-value="5"]::before {
  content: "标题5";
}
.ql-snow .ql-picker.ql-header .ql-picker-label[data-value="6"]::before,
.ql-snow .ql-picker.ql-header .ql-picker-item[data-value="6"]::before {
  content: "标题6";
}
.ql-snow .ql-picker.ql-font .ql-picker-label::before,
.ql-snow .ql-picker.ql-font .ql-picker-item::before {
  content: "标准字体";
}
.ql-snow .ql-picker.ql-font .ql-picker-label[data-value="serif"]::before,
.ql-snow .ql-picker.ql-font .ql-picker-item[data-value="serif"]::before {
  content: "衬线字体";
}
.ql-snow .ql-picker.ql-font .ql-picker-label[data-value="monospace"]::before,
.ql-snow .ql-picker.ql-font .ql-picker-item[data-value="monospace"]::before {
  content: "等宽字体";
}
</style>
