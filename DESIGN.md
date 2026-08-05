---
name: ACTION
description: 针刺临床研究智能平台——学术权威、国际现代、智能高效的靛青档案馆
colors:
  indigo-900: "#141d33"
  indigo-800: "#182644"
  indigo-700: "#1e3253"
  indigo-600: "#274266"
  indigo-500: "#31598f"
  indigo-300: "#8ba3c4"
  indigo-200: "#c9d6e8"
  indigo-100: "#e4ebf5"
  paper: "#f7f8fb"
  paper-2: "#eef1f7"
  surface: "#ffffff"
  ink: "#16202f"
  muted: "#566378"
  line: "#dbe2ee"
  cinnabar: "#c0362c"
  cinnabar-deep: "#9e2a22"
typography:
  display:
    fontFamily: "Spectral, 'Noto Serif SC', Georgia, serif"
    fontSize: "clamp(2.2rem, 5.2vw, 4rem)"
    fontWeight: 700
    lineHeight: 1.14
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Spectral, 'Noto Serif SC', Georgia, serif"
    fontSize: "clamp(1.7rem, 3.4vw, 2.6rem)"
    fontWeight: 600
    lineHeight: 1.18
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Spectral, 'Noto Serif SC', Georgia, serif"
    fontSize: "1.3rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  body:
    fontFamily: "'Source Sans 3', 'Noto Sans SC', system-ui, sans-serif"
    fontSize: "clamp(1rem, 1.4vw, 1.15rem)"
    fontWeight: 400
    lineHeight: 1.7
    letterSpacing: "normal"
  label:
    fontFamily: "'Source Sans 3', 'Noto Sans SC', system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.02em"
rounded:
  sm: "7px"
  md: "10px"
  lg: "12px"
  xl: "20px"
  pill: "999px"
spacing:
  xs: "8px"
  sm: "14px"
  md: "20px"
  lg: "24px"
  section: "clamp(64px, 9vw, 120px)"
components:
  button-primary:
    backgroundColor: "{colors.cinnabar}"
    textColor: "{colors.surface}"
    rounded: "{rounded.pill}"
    padding: "13px 24px"
  button-primary-hover:
    backgroundColor: "{colors.cinnabar-deep}"
    textColor: "{colors.surface}"
    rounded: "{rounded.pill}"
    padding: "13px 24px"
  button-ink:
    backgroundColor: "{colors.indigo-700}"
    textColor: "{colors.surface}"
    rounded: "{rounded.pill}"
    padding: "13px 24px"
  button-ghost:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.indigo-700}"
    rounded: "{rounded.pill}"
    padding: "13px 24px"
  overview-item:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.xl}"
    padding: "26px 26px"
  search-box:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.xl}"
    padding: "4px 6px 4px 18px"
  news-item:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    padding: "26px 28px"
  resource-row:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    padding: "15px 6px"
---

# Design System: ACTION

## 1. Overview

**Creative North Star: "靛青档案馆 The Indigo Archive"**

ACTION 的界面是一座墨水般的方法学档案馆：**靛青为墨、朱砂为批、冷白为纸**。它服务的是针刺临床研究者——在投稿截止前的深夜书桌上核对报告规范的人。所以这套系统的第一性是可信与沉静，而非热闹。权威来自克制的留白、扎实的内容层级与精确的排版，绝不靠视觉喧哗去证明自己。

颜色策略是 **Committed**：深靛墨蓝在 Hero、智能工具、CTA、页脚等区块整片承载品牌，冷白纸面在内容区呼吸，二者交替形成"墨—纸"的档案节奏。文化底蕴不靠传统符号堆砌——靛青同时是国际学术的"墨水蓝"与"青出于蓝"的中医文化色，让中医气质从颜色的**选择**里长出来，而不是贴上去。朱砂是唯一的暖，取自印章朱批，克制到只出现在主行动与极少数印记上。

这套系统明确拒绝三样东西（承接 PRODUCT.md 的反面参考）：**傅头叫卖式的 SaaS 落地页**（渐变堆砌、大数字英雄卡片、催促式转化）、**花哨的保健品/养生商业网站**、以及**俗套的政府/医院官网**（僵硬、拥挤、老气，尤其是那种扁平的"医院蓝"）。靛青是刻意反"医院蓝"的选择。

**Key Characteristics:**
- 墨—纸交替：深靛墨区块与冷白内容区分段承载
- 朱砂克制：暖色点睛面积 ≤5%，只给关键行动与印记
- 衬线权威 + 无衬线高效的双轴排版
- 中英双语同为一等公民
- 自定义线性图示，而非摆拍照片或圆角图标盒

## 2. Colors

一套以深靛墨蓝为骨、冷白为纸、印章朱砂为唯一暖点的克制学术调色板。

### Primary
- **深靛墨蓝 Deep Indigo Ink** (`#1e3253`，最深 `#141d33`)：品牌主色。深色区块（Hero、智能工具、CTA 带、页脚）整片沉浸的底色，也是主"墨"按钮（button-ink）的填充。`#141d33` 是最深的沉浸底，`#182644`/`#274266` 用于同区块内的层次与卡面。
- **交互靛蓝 Interactive Indigo** (`#31598f`)：链接、段首短划之外的次级强调、图示描边。可读的中间调蓝。

### Secondary
- **印章朱砂 Seal Cinnabar** (`#c0362c`，深 `#9e2a22`)：唯一的暖色强调，取自印章/朱批。仅用于主 CTA 填充、Hero 星座中的少数高亮节点、段首短划、以及关键状态标记。面积极小是它权威感的来源。

### Neutral
- **冷白纸面 Cool Paper** (`#f7f8fb`，次级 `#eef1f7`)：页面主背景。微偏蓝的冷白，**不是暖奶油/宣纸**。`#eef1f7` 用于分区错落（如四支柱区）。
- **纯白卡面 Surface White** (`#ffffff`)：卡片、引文块、条目 hover 的抬升面。
- **墨蓝黑正文 Ink** (`#16202f`)：正文与标题主色，对冷白约 15:1。
- **次要墨灰 Muted** (`#566378`)：次要说明文字，对冷白约 5.5:1（达标）。
- **描边线 Line** (`#dbe2ee`)：分隔线、卡片描边、条目下边界。
- **靛调阶梯 Indigo tints** (`#e4ebf5` / `#c9d6e8` / `#8ba3c4`)：浅靛用于 chip 底、深色区文字、图示节点等。

### Named Rules
**The Ink-and-Paper Rule.** 深靛墨与冷白纸交替承载分区；同一屏内不混入第三种背景大色。墨区讲权威，纸区讲内容。

**The One-Warm Rule.** 朱砂是全站唯一的暖色，任意视口内其着色面积 ≤5%。它的稀有就是它的力量——多一处，权威就少一分。

**The No-Hospital-Blue Rule.** 禁止扁平的企业"医院蓝/政府蓝"（如 `#005bac` 一类）。蓝必须是深靛墨这一支，带墨水与靛青的文化厚度。

## 3. Typography

**Display Font:** Spectral（拉丁）/ Noto Serif SC 思源宋体（中文），衬线
**Body Font:** Source Sans 3（拉丁）/ Noto Sans SC 思源黑体（中文），无衬线
**Label Font:** 同 Body（Source Sans 3 / Noto Sans SC）

**Character:** 双轴对比——衬线承载学术权威与书卷气（标题），无衬线承载智能高效与清晰可读（正文、UI、标签）。刻意规避 reflex-reject 字体（Fraunces / Playfair / Inter / DM 等）。拉丁字符走 Spectral / Source Sans，CJK 自动回落思源系，中英双语同一套观感。

### Hierarchy
- **Display** (Spectral/思源宋体, 700, `clamp(2.2rem,5.2vw,4rem)`, lh 1.14, ls -0.025em)：仅 Hero 主标题。`text-wrap:balance`。
- **Headline** (600, `clamp(1.7rem,3.4vw,2.6rem)`, lh 1.18, ls -0.02em)：各 section 标题（`.title`），`max-width:20ch` + balance。
- **Title** (600, ~`1.3rem`, lh 1.2)：卡片/条目标题（支柱卡、规范条目、工具卡）。
- **Body** (Source Sans/思源黑体, 400, `1rem–1.15rem`, lh 1.7)：正文与说明。正文行长 ≤ 60ch，`text-wrap:pretty`。
- **Label** (600, `13px`, ls 0.02em)：段首标记 kicker、chip、状态标签。**非**大写宽字距 eyebrow。

### Named Rules
**The Serif-Authority Rule.** 标题一律衬线（Spectral/思源宋体），正文与 UI 一律无衬线。不在正文里用衬线"装文艺"，也不在标题里用无衬线"求现代"。

**The One-Kicker Rule.** 段首标记是一套统一体系：13px 无衬线 + 一道朱砂短划前缀。它是品牌语法，**不是**每段一个的大写宽字距 eyebrow。

## 4. Elevation

默认平面，按需抬升。静态下卡片与条目是**平面 + 细描边**（`1px #dbe2ee`），依靠色块、描边与留白分层；阴影只作为**状态反馈**在 hover / 抬升时出现，绝不作为静态装饰满屏铺开。深靛墨区块本身即是"抬升"的最高层，不再叠加投影。

### Shadow Vocabulary
- **sm 细影** (`box-shadow: 0 1px 2px rgba(20,29,51,.06), 0 2px 8px rgba(20,29,51,.05)`)：条目 hover、引文块静置的极轻抬升。
- **md 中影** (`box-shadow: 0 10px 30px rgba(20,29,51,.10)`)：卡片 hover 抬升、次级按钮 hover。
- **lg 重影** (`box-shadow: 0 24px 60px rgba(20,29,51,.16)`)：旗舰卡 hover 等强抬升场景。

### Named Rules
**The Flat-By-Default Rule.** 表面静置即平面；阴影是对状态（hover / focus / 抬升）的回应，不是默认外观。若一个卡片静止时就带重投影，那是 2014 年的 App，不是 ACTION。

## 5. Components

### Buttons
- **Shape:** 全圆角胶囊（`border-radius: 999px`），内边距 `13px 24px`。
- **Primary（主行动）:** 印章朱砂填充 `#c0362c` + 白字，带朱砂柔光 `0 6px 18px rgba(192,54,44,.28)`。用于"获取规范与工具"等唯一主行动。
- **Ink（次级实心）:** 深靛墨 `#1e3253` + 白字。用于顶栏"获取规范"等。
- **Ghost（幽灵）:** 透明底 + `#c9d6e8` 描边 + `#1e3253` 字；hover 描边转 `#31598f`、底转 `#e4ebf5`。
- **On-Dark（深色区）:** 半透明白描边 + 白字，用于靛墨区块内的次要行动。
- **Hover / Focus:** 主/次实心按钮 hover 上移 2px + 加深底色；箭头 `.arrow` 右移 3px；焦点态 `outline: 2.5px solid #31598f; offset 3px`。

### Cards（轻量 · 概览项）
纯白卡（`20px` 圆角 + `1px #dbe2ee` 描边），静置平面。首页只用**轻量卡**，不用大图标卡阵、不嵌套。
- **Overview 概览项（`.ov-item`）:** 关于区的一行式信息卡——小图标 + 衬线标题 + 一行说明；报告规范卡内联列出各研究类型规范（RCT·CONSORT / 方案·SPIRIT / 系统综述·PRISMA / 病例·CARE / 指南 / 动物·ARRIVE），智能工具卡列出两个工具，底部用 `.ov-tag` 状态胶囊（`margin-top:auto` 对齐：规范陆续开放 / 即将上线·内测中）。自适应网格 `repeat(auto-fit,minmax(232px,1fr))`。**报告规范与工具的详情收在这三张卡里，不再单独起整屏区块。**
- **禁止**：等大"图标 + 标题 + 段落"卡片阵无限重复、嵌套卡片、静置就带重投影。

### Navigation
- **Style:** sticky 顶栏，冷白半透明 + `backdrop-filter: blur(14px)`，底部 `1px #dbe2ee`。
- **Typography:** 无衬线 15px `#1e3253`；hover 现朱砂下划线（`scaleX` 展开）。
- **Mobile (≤820px):** 折叠为汉堡；点击展开 `position:fixed` 全屏冷白浮层，链接为大号思源宋体。语言切换（中/EN）常驻。

### Inputs / Search（全站检索）
- **Style:** 纯白胶囊输入框（`20px` 圆角），左侧靛蓝放大镜、右侧圆形清除键；`1.5px #dbe2ee` 描边。
- **Focus:** `focus-within` 时描边转 `#31598f` + `4px` 靛光环（`box-shadow:0 0 0 4px var(--indigo-100)`）。
- **结果下拉：** `position:absolute` 悬于 `position:relative` 的包裹层内，**不置于 `overflow:hidden` 容器中**（否则被裁剪）；`z-index:var(--z-dropdown)`，`--shadow-lg`，`max-height:min(60vh,440px)` 可滚动。
- **结果项：** 类型标签（站内靛 chip / 外链朱砂 chip）+ 标题 + 副标题；hover 底 `#eef1f7`。中英双语索引，任一语言均可命中。

### News Item（新闻条）
- **Style:** `160px 108px 1fr` 三栏——左列**缩略图**（`.news-thumb`，`10px` 圆角，`object-fit:cover`）+ 中列日期（靛墨粗体）与分类 chip（一般靛，"规范更新"用朱砂淡底）+ 右列衬线标题 + 次要正文。行分隔用 `1px #dbe2ee`，hover 底转冷白。
- **Mobile (≤820px):** 单列堆叠，缩略图转 `180px` 全宽横幅，日期与分类并排一行。
- **配图：** 缩略图为 `assets/news-*.jpg`（Unsplash 真实照片：针刺特写 / 研究者协作 / 数据仪表盘），本地文件、带描述性 `alt`；替换真实素材建议 ~16:11、补 `alt`。

### Resource Row（外链卡 · `.res-row` in `.res-cards`）
- **Style:**「资源中心」全宽栏的外链——左侧 `46px` **logo 占位**（`.res-logo`，`12px` 圆角）+ 名称（衬线）+ 一行说明 + 右上外链箭头（↗），在 `repeat(auto-fit,minmax(300px,1fr))` 的 `.res-cards` 网格里各成一张带描边的卡；hover 底转纯白 + 描边转靛 + 箭头转朱砂。
- **logo：** `assets/logo-*.png`（gen-image 生成的一套靛青主题图标：枢纽 / 森林图 / 流程 / 漏斗 / 实验鼠 / 病例夹；源 128px，显示 46px）。**真实官方机构 logo 应从官网下载替换，不用 AI 生成**（版权 + 准确性）。
- **外链：** 一律 `target="_blank" rel="noopener noreferrer"`，并附视觉隐藏「（在新窗口打开）」屏读提示。
- **合作 / 关联机构：** 未定链接不放占位空卡；正式文案里**不写"持续补充""待补充"等 WIP/过程性措辞**，只描述已展示的内容（这类内部状态不该面向用户）。

## 6. Do's and Don'ts

### Do:
- **Do** 用深靛墨与冷白交替分区（Ink-and-Paper Rule）；墨区讲权威，纸区讲内容。
- **Do** 把朱砂当唯一暖色，任意视口着色面积 ≤5%，只给主行动与关键印记（One-Warm Rule）。
- **Do** 标题一律衬线（Spectral/思源宋体）、正文一律无衬线（Source Sans/思源黑体）。
- **Do** 让卡片静置平面 + `1px #dbe2ee` 描边，阴影只在 hover 出现（Flat-By-Default Rule）。
- **Do** 正文对冷白确保 ≥4.5:1；次要文字用 `#566378` 而非更浅的灰。
- **Do** 用自定义线性图示（经络/结构/数据）承载"影像"，中英文同为一等公民。
- **Do** 下载区用诚实状态（即将上线 / 需授权），不放死链。
- **Do** 外链一律 `target="_blank" rel="noopener noreferrer"`；检索结果下拉放在非 `overflow:hidden` 容器中（否则被裁剪）。
- **Do** 用诚实占位区分未定内容：新闻加"示例内容待替换"提示，未定伙伴用虚线占位卡。

### Don't:
- **Don't** 使用扁平的"医院蓝/政府蓝"（如 `#005bac`）；蓝只能是深靛墨这一支（No-Hospital-Blue Rule）。
- **Don't** 做成傅头叫卖式 SaaS 落地页：渐变堆砌、**大数字英雄卡片模板**、催促式转化。
- **Don't** 做成花哨的保健品/养生商业网站，或俗套拥挤老气的政府/医院官网。
- **Don't** 用 `border-left/right` 大于 1px 的彩色侧边条做卡片/提示的强调。
- **Don't** 用 `background-clip:text` 的渐变文字；强调靠字重与字号。
- **Don't** 把玻璃拟态、满屏动效当默认装饰。
- **Don't** 用等大的"图标 + 标题 + 段落"卡片阵无限重复；也不要嵌套卡片。
- **Don't** 在每个 section 顶部堆小号大写宽字距 eyebrow；段首标记只用统一的 One-Kicker 体系。
- **Don't** 用宣纸/奶油暖白做主背景；纸面是微偏蓝的冷白。
