# CLAUDE.md

## Design Context

本项目的战略设计上下文见根目录 **[PRODUCT.md](PRODUCT.md)**（由 `/impeccable init` 生成）。任何界面设计/改动前请先读它。

要点速览：
- **Register**: `brand`（品牌型资讯站）· **Platform**: `web` · **双语**：中英文对等
- **ACTION** = ACupuncTure Intelligent helper ON clinical research：学术主导、非营利的针刺临床研究智能平台（报告规范 + 智能工具 + 培训 + 协作）。
- **首要用户**：针刺临床研究者 · **首要 CTA**：下载/使用报告规范与工具 · **次要 CTA**：了解平台/阅读使命。
- **气质**：学术权威严谨 · 国际化现代 · 智能高效 · 中医专业底蕴。
- **反面参考**：傅头叫卖式 SaaS 落地页 · 花哨保健品网站 · 俗套政府/医院官网。
- **注意**：现有 `index.html` 把 ACTION 误写为「多中心 RCT 招募站」，与真实使命不符——以真实使命为准，首页待重做。

视觉系统文档 `DESIGN.md` 暂未生成；首页重做后可运行 `/impeccable document` 捕获真实 tokens。

## Worker 工具框架

`action-backend/tools/` 下的长耗时 AI 工具统一走 **Redis 队列驱动的常驻 worker** 形态，公共骨架在
**[action-backend/tools/common/README.md](action-backend/tools/common/README.md)**（配置、队列、任务状态、日志/SSE、停止、断点、优雅关闭）。

- 工作目录一律是 `action-backend/`（`python -m tools.srd_worker_tool`），不是仓库根
- 每个 worker 在 `action-backend/` 下配一套同形态的运维脚本：`start_/stop_/restart_/status_<name>_worker.sh`
  + `_<name>_worker_common.sh`（被前四个 source）+ `start_<name>_worker.py`（入口）
  + `.env.<name>-worker.example`。**`APP_ENV` 要显式传成 `--env`**（`config/env.py` 靠命令行参数
  选 `.env`，光设环境变量会被覆盖回 dev，表现是「生产机上的 worker 在查开发库」）；
  **stop 前要核 PID 的命令行**（进程崩过后 PID 会被复用，只判存活会 kill 掉无关进程）
- **模型配置从 `ai_models` 表读**（`tools/common/model_registry.py`，与后端 AI 对话共用
  `AiModelService.get_usable_ai_model_pool_services`）：取到的是一个池子，按 `model_sort` 顺序
  「粘性 + 出错切换」，撞到限流/欠费就冻结 5 分钟换下一个，冻结表在 Redis 跨进程共享
- **结构化输出方式也在 `ai_models` 里**（`structured_method` 列，增量 SQL
  `sql/ai-model-structured-method-pg.sql`）：`json_schema` / `function_calling` / `json_mode` / `text`，
  厂商支持情况**按模型**不同（同一个 deepseek 在官方端点与火山方舟上就不一样）。
  **留空即可** —— worker 从 `json_schema` 起探测、逐级降级、跑通后回写这一列；
  列非空时不覆盖（人工钉死优先）。加这一列是因为探测要拿**带着整篇正文的真实请求**去撞墙，
  实测一次几分钟，不记住就每个任务重付一次
- 已改造：`tools/srd_worker_tool`（包装 `tools/srd-engine` 纯算法引擎，见其 README）
- 已新增：`tools/checklist_worker_tool`（报告助手第三步：稿件 × 报告规范。一次任务出两类判定
  ——逐条完整性 `engine/audit.py` 与全稿逻辑一致性/术语标准化 `engine/consistency.py`，见其 README）
- 新增工具照抄 `tools/srd_worker_tool` 骨架：只写 `XxxSessionTask.process()` + 一份配置
- 算法与服务分层：引擎不认识 Redis/HTTP，worker 不重写算法
- `tools/data_extraction_worker_tool` 是外部搬来的**参考样板**，依赖本仓库不存在的 module_common/MySQL，不可直接运行

## 团队成员与图片存储

「关于我们 → 如何组织」的名单来自 `action_team_member` 表，不再是写死的 i18n 文案。

- 表：`sql/action-team-pg.sql`（建表 + 13 位成员中英双语数据），菜单 `sql/action-team-menu-pg.sql`（`action:teamMember:*`）
- 素材源：`ACTION网站及其材料/About us/How we are organised(2).docx`；头像原图留在 `action-backend/tools/team-avatars/`
- 简介分三层，各用各的：`summary`（名单卡片一句话）· `bio`（详情页履历）· `contribution`（对 ACTION 的贡献，单独成块）
- 前台：`pages/about.vue` 名单 + `pages/team/[id].vue` 详情页（路由不放 `/about/team/[id]`——
  `pages/about.vue` 已存在，再建 `pages/about/` 会把它变成需要 `<NuxtPage>` 的父级路由）
- 姓名：docx 只给拉丁字姓名。9 位中国籍的 `name_zh` 是推断填的**待甲方核对**；
  4 位韩国籍不译。称谓（Prof./Dr.）只在非汉字姓名前显示，见 `composables/useTeamMembers.ts` 的 `displayName`

**官网内容图片与可下载文档一律存阿里云 OSS**（桶 `action-gmu` · 华南3 广州），不落后端磁盘 ——
官网是 `nitro.preset: 'static'` 的预渲染站，文件跟着后端机器走会在换机/多副本部署时开天窗。

- 配置 `OssSettings`（`config/env.py`，读 `.env` 的 `OSS_*`），工具 `utils/oss_util.py`
- 手写 OSS V1 签名 + httpx，**不引 `oss2`**，与 `module_action/service/mail_service.py` 对 DirectMail 的做法一致
- 上传口两条，都不走 `/common/upload`（那条落本地磁盘）：
  `POST /action/admin/team-member/avatar`（图片，5MB，后台用 `ImageUpload`）与
  `POST /action/admin/guideline/file`（报告规范原文，**仅 PDF**，30MB，后台用 `FileUpload`）
- 白名单一种格式就一条通道：这里产出的是匿名可读的公网直链，放行 doc/xls/zip 等于开了个任意文件托管口
- 批量迁移/回填：`python -m tools.upload_team_avatars`，回写 DB 与种子 SQL 前会**匿名 GET 自检**，
  读不到就拒绝回写（传上去 ≠ 读得到；桶没授公共读时前台会整片裂图）
- **默认域名下的对象一律被阿里云强制加 `Content-Disposition: attachment`**
  （响应头 `x-oss-force-download: true`，桶没绑已备案的自有域名就改不掉）。
  `<img>`/`<video>` 不看这个头，所以图片一直正常；`<iframe>` 与地址栏直开看，于是**PDF 直链
  只会触发下载、预览区一片空白**。要内嵌预览就得由后端转一道：
  `GET /action/site/guidelines/{id}/file` 用 `OssUtil.fetch_public_object` 取回字节、
  以 `Content-Disposition: inline` 吐出（只放行本桶的 `.pdf`——转发任意 URL 是 SSRF，
  把 html 以 inline 挂到本站域名下是同源脚本面）。下载按钮反而该继续用 OSS 直链，
  那个场景要的正是 attachment。哪天给桶绑上自有域名，这一层可以整个撤掉

## 官网取数：后台改了，前台就得能看见

官网是 `nitro.preset: 'static'` 的预渲染站，页面里 `useSiteList` / `useSiteObject` 的结果
是 `npm run generate` 那一刻烤进 HTML 的。**「后台点了保存、官网纹丝不动」这类问题已经根治，
但根治靠的是两个反直觉的实现细节，改动前必读 `action-frontend/composables/useSiteApi.ts`
与 `useReveal.ts` 的文件头注释。**

- **重取默认开，不是逐页 opt-in。** 原先叫 `{ swr: true }`、默认关，于是「这块当初以为不会改、
  后来进了后台管理页」的内容就永远停在构建期快照上。现在要关得显式传 `{ revalidate: false }`
- **那次重取必须挂 `onNuxtReady`，挂 `onMounted` 会静默失效。** Nuxt 的
  `useAsyncData.execute()` 在 `nuxtApp.isHydrating` 期间**无视 `refresh:manual`**，
  直接拿 `payload.data[key]`（静态站里就是 `_payload.json` 的构建期快照）立刻 resolve，
  一个请求都不发；而 `isHydrating` 要到 `app:suspense:resolve` 才置 false，那在 `onMounted`
  之后。`plugins/site-texts.ts` 一直用的就是 `onNuxtReady`，所以历史上「文案能刷新、
  列表数据不能」—— 差别只在这一处
- **换进来的新节点由 `useReveal` 的 MutationObserver 自动揭示**，页面不用再写
  `watch(rows, rescan)`。漏了的表现是「数据对、行数对，但整块空白」（`.reveal{opacity:0}`），
  和「后台还没填内容」长得一模一样，极难归因。**唯一顶不了 display 切换**
  （`/guidelines` 筛选 chip 切 `.hide`，无节点新增），那里仍要手动 `rescan()`
- **信封的业务码要判**：出参是「HTTP 200 + code 500」风格，不判 `code !== 200` 就会被
  `default` 兜成空数组、静默渲染成「本来就没有」，构建期发生等于把空白烤进产物

**按 locale 变化的 `class` / `style` 不能直接绑 `locale`。** 预渲染出来的 HTML 永远是默认语言
zh 那一版，访客带 `action_lang=en` 的 cookie 刷新时客户端首帧就是 en，两边对不上 ——
而 **Vue 的 hydration 只修文本与 `dynamicProps`，不修 class/style**（文本会就地
`el.textContent=` 改掉，class 只记一条 mismatch 警告）。表现是「文案是英文的、样式却是中文那档」，
且只在**刷新**时出现，点语言按钮切换一切正常，极易被当成偶发。改法见 `SiteHeader.vue` 的
`menuIsEn`：挂个 `hydrated` 开关让首帧一致，挂载后再置真。文本与 `:aria-label` 这类不受影响。

**locale 只是触发源之一，「任何构建期拿不到的值」都算**：`pages/assistant.vue` 的向导位置
（step 与第一步答案）同步进了 URL query，还原就只能放在 `onMounted` 里 —— 预渲染出来的
永远是 step=1 那一版，setup 阶段按 query 算出 step=2 的话，面板显隐那个
`:class="{ 'is-hidden': … }"` 会对不上，表现是「步骤条停在第 2 步、内容还是第 1 步」，
且只在直接打开带 query 的地址时出现。挂载后再赋值是普通响应式更新，class 会正常 patch。
这个 query 是给登录往返用的：`?redirect=` 带着 `route.fullPath` 走，位置不进 URL
就等于「第二步撞上登录墙 → 登录回来落在第一步、答案清空」。构造与校验在
`composables/wizardQuery.ts`（纯函数，`test/wizardQuery.spec.ts` 钉住）。

**这一层只保证「访客刷新即见」，搜索引擎与微信分享卡片看的首屏 HTML 仍是上次构建的产物**
—— 那要靠后台「站点文案管理」页的「重新生成官网」按钮，见下一节。

## 站点文案（后台可改的版面文字）

官网各页的**标题 / 导语 / 正文段落 / 按钮字**共 934 条，原本只存在于
`action-frontend/i18n/locales/{zh,en}.json`，改一个字要改代码 + 重新 `npm run generate`。
现在库里有一份可编辑副本，后台「站点文案管理」页维护，前台在 i18n 之上 merge 一层。

- 表：`action_site_text`（`sql/action-site-text-pg.sql`，**由脚本生成，不要手改**），
  菜单 `sql/action-site-text-menu-pg.sql`（`action:siteText:*`）
- **前端每加一批 `$t()` 键，都要同步进这张表**：不同步官网照样显示（回落 i18n JSON 的
  默认值），但后台「站点文案管理」里看不见、也就改不了 —— 这类「明明是页面上的字，
  后台却搜不到」的问题只可能是漏了这一步
- 增量 SQL 用 **`NNN-` 数字前缀**（首份 `sql/001-action-site-text-srd-export-pg.sql`），
  编号只增不减，序号最大的就是最新的；全量文件不编号 —— 它们是可反复执行的快照，
  没有先后可言。增量与全量对同一批键的写入语义必须逐字一致（那段 `on conflict`
  照抄生成器，别改写），否则「先增量后全量」与反过来跑会得到不同结果
- 同步脚本 `python -m tools.extract_site_texts`：读前端两份 locale JSON 重新生成上面那份 SQL。
  前端加了新词条、或改了默认文案，重跑一次再执行即可（**可反复运行**）
- 后台页面 `action-admin/src/views/system/siteText/index.vue`，公开接口 `GET /action/site/texts`
- 前台接管在 `plugins/site-texts.ts`

**`default_*` 与 `text_*` 不是中英那种对称关系**，别看串：
`default_zh/en` 是代码里的原始文案（跟着 JSON 走，后台只读），`text_zh/en` 才是当前生效值。
**公开接口只返回 `text_* <> default_*` 的行** —— 这层挂在每个页面上，
整包 934 条会给每份 HTML 的 hydration payload 白压约 120KB；没人改过时它返回 `{zh:{},en:{}}`。
「还原默认」就是把 `text_*` 写回 `default_*`。同理，同步 SQL 的 `on conflict` 里那个 `case`
不能删：少了它，前端改一句默认文案后，所有未被人工覆盖的行都会突然变成「已改动」，
并把旧文案当覆盖项吐给前台，等于代码里的修改永远上不了线。

**后台只能改，不能增删词条。** 一条文案对应模板里一个 `$t()` 键，键由代码定义 ——
后台建键会建出没人读的孤儿行，后台删键会让官网上一段文字凭空消失且无从查起。
增删走同步脚本。写接口也只采纳 `textZh/textEn/remark`，其余字段原样 PUT 回来会被丢掉。

**改动会进 `v-html`，所以写接口有标签白名单**（`ALLOWED_TEXT_TAGS`，见 `action_vo.py`）：
`nuxt.config.ts` 开了 `escapeHtml: false`，69 条词条本身带着 `<span class="hl">` 与行内 SVG 图标。
白名单按实照列（span/b/i/em/strong/br/sup/sub/small/svg/circle/path），
另挡 `on*=` 事件属性与 `javascript:/vbscript:/data:` 伪协议。放开等于把后台文本框
变成往公开页面注入任意 HTML 的口子。

`<a>` 也在白名单里（页脚 ICP 备案号按工信部要求必须是指向 beian.miit.gov.cn 的可点链接），
但 **`href` 单独收口**：只放行 `http(s)://` 完整网址、`/` 开头的站内路径、`#` 锚点、`mailto:`，
协议相对地址 `//evil.com` 不放。判之前先 `html.unescape` 再剔空白/控制字符
—— `&#106;avascript:` 与 `java\tscript:` 在浏览器里都会还原成 `javascript:`，只匹配原文等于没判。

**放行标签只是一半，另一半在前台模板**：`{{ t('x') }}` 是文本插值，标签会被原样显示成源码，
必须那一处写成 `v-html`（已改的有 `SiteFooter.vue` 的 `footer.icp`）。
后台保存成功但官网显示出一串 `<a href=...>`，就是漏了这一步。

前台合并有三个点，改 `plugins/site-texts.ts` 前先看清：
① **扁平键不能直接 merge** —— `t('index.s052')` 走路径解析，必须先 `unflatten` 成嵌套对象，
否则 merge 了也取不到（实测过）；② 构建期取一次进 payload、客户端从 payload 同步 merge，
所以**没有 hydration 不匹配**，挂载后再取一次让访客刷新即见新文案；
③ **切语言后要重新 merge，且必须 merge 两次** —— 加载该语言的消息会把先前 merge 进去的
覆盖项冲掉。只挂 `i18n:localeSwitched` 不够：`strategy: 'no_prefix'` 下 @nuxtjs/i18n 的
`composer.setLocale` 发完这个钩子后**还会再 `loadLocaleMessages(locale)` 一遍**，
把刚补上的覆盖项二次盖掉，所以另外包了一层 `setLocale`（`patchSetLocale`）在最后再补一次。
少任意一处的表现都是「首屏是新的，切一次语言变回旧的」。

### 重新生成官网

访客刷新即见新文案，但**搜索引擎与微信分享卡片只看首屏 HTML**，那还是上次构建的产物。
后台「站点文案管理」页的「重新生成官网」按钮跑一次预渲染构建把改动烤进去。

- 配置 `SiteBuildSettings`（`config/env.py`，读 `.env` 的 `SITE_REBUILD_*`），默认关闭，
  未配置时接口如实返回 `disabled`，不做静默降级
- **命令由运维在 `.env` 写死，接口不接受任何来自请求的参数**，且 `shlex.split` 成 argv 直接
  exec、不经 shell：这是个执行 shell 的口子，一旦有用户输入能拼进命令行，
  后台任一有该权限的账号就等于拿到了服务器
- 全局互斥用 Redis `setnx`（两个构建同时往 `.output` 里写 = 产物损坏），状态也在 Redis 不在内存
  —— 后端可能多副本，而构建是全局一件事

## 首页资源中心

首页第④段「资源中心 · 国际报告规范组织与循证枢纽」的外链卡片来自 `action_resource_link` 表，
不再是 `pages/index.vue` 里写死的 6 个 `<a>` + i18n 文案。

- 表：`sql/action-resource-link-pg.sql`（建表 + 6 条种子：EQUATOR / Cochrane / CONSORT & SPIRIT /
  PRISMA / ARRIVE / CARE），菜单 `sql/action-resource-link-menu-pg.sql`（`action:resourceLink:*`）
- 后台页面 `action-admin/src/views/system/resourceLink/index.vue`，公开接口 `GET /action/site/resource-links`
- `url` 只收 `http(s)://` 绝对地址（VO 里校验）：这个值直接进 `<a href>` 且 `target="_blank"`，
  放开协议等于把 `javascript:` 之类的注入面留给后台文本框；站内路径也不该出现在这一段
- `logo_url` 一律 OSS 公网直链：种子那 6 张由 `python -m tools.upload_resource_logos` 从
  `action-frontend/public/assets/logo-*.png` 传上去并回写 DB 与种子 SQL（键用文件名，可重复执行），
  后台新传的走 `POST /action/admin/resource-link/logo`。
  **别改回 `/assets/` 相对路径** —— 后台是另一个域，相对路径在「资源中心管理」页会 404 裂图；
  原图留在 `public/assets/` 不要删，`action_news` 有 4 条新闻的 `thumb_url` 还指着同一批文件
- **栏目自身的标题/导语仍在 i18n**（`index.s052–s054`），它不是列表数据；
  原先每条卡片一个的说明键（s055/s057/…）已随迁移删除，只留下共用的「（在新窗口打开）」`index.s056`

## 成果发表

顶栏第 9 项「成果发表 / Publications」：列表页 `pages/publications.vue` + 详情页
`pages/publication/[id].vue`（单数，理由同 `guidelines`/`guideline`），数据来自
`action_publication` 表，后台「成果发表管理」页维护。

- 表：`sql/action-publication-pg.sql`（**无种子** —— 装的是甲方自己的发表成果），
  菜单 `sql/action-publication-menu-pg.sql`（`action:publication:*`，menu_id 1112-1116），
  文案增量 `sql/022-action-site-text-publications-pg.sql`（36 条）
- 公开接口三个：`GET /action/site/publications`（分页，支持 keyword/year）·
  `/publication-years`（年份词表）· `/publications/{id}`（详情）
- **`/publication-years` 不叫 `/publications/years`**：那会与 `/publications/{id}` 撞路径，
  FastAPI 按声明顺序匹配，谁在前谁生效 —— 换个顺序就静默换掉命中的那个口
- **列表接口刻意不返回 `abstract` 与 `citationText`**（`PublicationService._LIST_OMIT`）：
  官网是预渲染站，一页 10 条摘要就是几万字没人看的文本被烤进 HTML

**这张表没有 `*_zh`/`*_en` 双语列，不要「补齐」。** 标题、作者、期刊、摘要是**发表原文**，
同时也是引用信息 —— 译一遍读者既检索不到也引用不了（同 SRD 那两列「原文引用」的道理）。
中英两种界面显示的都是它，所以前台**不走 `pick()`**；页面上的栏目标题、按钮字才是 i18n。

**`authors` / `affiliations` / `keywords` 三列是 JSON 文本**，转换收在
`PublicationService._encode` / `_decode`，DAO 与控制器都不认识这件事。三个要点：
① 作者顺序即署名顺序，任何存储/渲染层的重排都是学术事故，所以不拆子表、不用 jsonb；
② `affiliationIndex` 是机构下标，**没标机构时是 null 不是 0**（0 是第一家单位，
兜底成 0 会给每位作者凭空挂上别人的单位，而页面上那个角标看着完全正常）；
③ `_encode` 必须守住 `exclude_unset` —— 无脑写 `[]` 会把「没打算改作者的那次编辑」
变成「清空作者」。后台删机构时同步重排作者下标（`removeAffiliation`）。

**`PublicationModel` 与 `PublicationAuthorModel` 额外开了 `populate_by_name`**：这一对除了接
HTTP 入参，还要在服务层用 snake_case 字段名直接构造（解析层的产出、库里读回来的字典）。
pydantic v2 在只有 alias 时对多余的 snake_case 键是**静默忽略**而不是报错 ——
不开这个开关，`PublicationModel(**fields)` 会安静地得到一个字段全 None 的空模型。

### 录入：DOI 与 PDF 两条自动解析

后台表单顶上两个按钮，都只产出**草稿**回填表单等人核对，一个字段都不自己入库。
纯函数在 `service/publication_parse.py`（可离线单测，见 `tools/tests/test_publication_parse.py`），
发请求/调模型那层在 `service/publication_meta_service.py`。

- **DOI 走 Crossref**（主路，出版社登记的权威元数据）。**只认 DOI 与 doi.org 链接，
  不做「粘个网址就抓」** —— 让服务器 GET 调用方给定的地址就是 SSRF（内网、云元数据服务、
  本机其它端口）。Crossref 主机写死在代码里，用户输入只作为路径里的 DOI 出现
- **摘要与关键词由 PubMed 补，这不是可选项而是必需的**：Crossref **根本没有作者关键词字段**
  （它的 `subject` 是期刊级学科分类，且 2023 年起已从出参撤下，实测一律 `[]`，所以
  `from_crossref` **刻意不映射它** —— 映射了只会让人以为「有时能解析出关键词」）；
  摘要则要出版社存过才有，**Elsevier / JAMA / BMJ 都不存**（针刺领域常投的
  Complementary Therapies in Medicine、J Integr Med 全在这一档）。按同一个 DOI 查一次
  PubMed（esearch → efetch），取 `<AbstractText>` 与作者 `<Keyword>`，没有作者关键词时
  回落 MeSH —— **回落要在提示语里标明**，MeSH 是索引员事后打的受控词、不是作者写的关键词
- **PubMed 这一跳的任何失败都吞掉**（`_fetch_pubmed` 返回空并落 info 日志）：Crossref
  那份草稿已经能用，不该因为兜底不通就让整次解析报错。但提示语要分清
  「查通了这篇没有」与「压根没连上」——后者多半是服务器没有外网出口，是运维要处理的事。
  NCBI 主机同样写死，DOI 只作为检索词进 params
- **PDF 走 `ai_models` 模型池**（兜底：预印本、会议摘要没有 DOI）。复用
  `AiAssistService.complete()`，**不要另抄一份轮询逻辑**；提示词里那三条「不要编造」
  硬约束每次都发 —— 凭空多出一位作者或一个卷期是学术诚信问题
- **这条传 `max_tokens=None`，即整个不下发这个参数**（`_call_one` 里判 None 跳过）。
  抽取的输出长度取决于论文有几位作者、摘要多长，事先估不准；**给一个猜的数字就会撞截断**
  ——踩过一次：给 2000，一篇 20 位作者的研究列到第 12 位断掉，而截断的现场只报得出
  「模型返回的 JSON 无法解析」，根因（额度不够、还被「AI模型管理」里那栏「最大输出」
  再压低一道）完全看不出来。第四步的改写仍然限长，那个场景的输出长度是可预期的
- 这条路上传的 PDF **只在内存里过一道，不落 OSS 也不落磁盘**。要在官网提供全文下载
  是另一个口（`POST /action/admin/publication/file`），那个桶整桶公共读，只放有权公开分发的全文
- `doi` 列存**裸标识符**：VO 的 `check_doi` 会把 `https://doi.org/` 前缀剥掉。
  不剥的话前台拼出 `https://doi.org/https://doi.org/10.x/y` 的死链
- 引用文本留空时由后端按字段拼一条（`build_citation_text`），**填了就不覆盖** ——
  各刊格式要求不同，自动拼的只是个够用的默认值

## SRD 系统综述重复性评估

`pages/srd.vue` 已从「一份写死的示例」接成**真跑**：上传两篇综述 PDF → 后端入队 →
`tools/srd_worker_tool` 常驻 worker 干活 → 结果落 `action_srd_*` 四张表 → 按账号回看历史。
增量建表见 `sql/action-srd-run-pg.sql`（跑在 `action-website-pg.sql` 之后）。

- 接口在 `action_site_controller.py` 的「SRD 真实评估」一段，服务层 `SrdService`。
  提交/轮询/停止/历史/详情/删除六个口，**除示例外全部要访客登录**且提交挂限流
  （`ApiNamespace.ACTION_SRD_ASSESS`）—— 一次评估是几十次模型调用
- **后端与 worker 必须共享文件系统**（README 的 systemd 示例本来就是同机）：
  输入 PDF 由后端写进 `vf_admin/private_upload_path/srd/{session_id}/`、以 `path` 交给 worker，
  结果 `result.json` 由后端按摘要里的 `files.json` 路径读回来。
  刻意**不走 OSS**：那个桶是整桶公共读，用户上传的综述原文不该变成公网可下载的对象。
  任务到终态后整个 `{session_id}/` 目录删掉
- **落库在轮询接口里做，不在 worker 里**：worker 只认 Redis 不认业务库，两个系统别焊死。
  代价是「用户关掉页面就没人来落库」，由历史列表接口顺带对账（未终结的记录补查一次状态）
- 这条链路要连着提交好几次事务，而会话是 `expire_on_commit=True`：
  **别把 ORM 对象跨 commit 传下去**，一律用 `_SrdRun` 这个普通值快照
  （跨过去的话，下一次读属性会触发懒加载，在 async 会话里直接抛 `MissingGreenlet`，实测过）
- **判定列不许有 server_default**（`overall_level` / `level` 的 `default 'mod'` 已删）：
  列有默认值时 SQLAlchemy 会把显式传入的 `None` 当成「没给值」省掉，于是「刚排队的任务」
  和「全领域证据不足」都会被静默写成「中度重复」。前台同理 —— `level` 为 null 渲染成
  「无法判定」的中性灰，不兜进四档里任何一档
- **一条都没评出来 = 没有结论，两道闸**（踩过一次：判定输出被截断，34 条全 unclear，
  却以 `[success] 结论：无重复` 收尾）：
  ① 引擎 `aggregate()` 在**没有任何可评分条目**时把 `overall_level` 判成 `None`，不查表
  —— 四个领域各自「证据不足按无重复算」会凑出一个 `none`，而 `none` 在前台就是「无重复」，
  和「两篇毫无重复」长得一模一样；② worker 的 `_reject_if_unjudgeable` 把这种结果判任务失败，
  **且不落断点**（落了的话重跑直接复用这份空报告，再也不会重算）。
  抽取缓存还在，重新入队同一个 `session_id` 就能接着跑，不用重花抽取的钱

### 评分口径（读数别看反）

引擎 0.8.0 起：**每条目 0–3 分，分越高越重复**
（3 完全相同 / 2 部分相同 / 1 部分不同 / 0 完全不同 / `unclear` 证据不足，不计分也不进分母）。
领域满分 = 3 × 条目数（/24 /18 /42 /18，合计 **/102**），重复百分比 = 得分 ÷ 满分 × 100，
再走表 2 分箱、表 3 查表。

**甲方那份 Excel（`ACTION网站及其材料/方法学评估工具/…SRD copy.xlsx`）表 1 的表头写的
恰恰相反**：「完全相同 0分 | 部分相同 1分 | 部分不同 2分 | 完全不同 3分」。0.7.x 照抄了它，
0.8.0 按甲方后来的定稿（「分数即相似度」）翻了过来。**拿那份 xlsx 来核这套代码会读反**，
口径的唯一真源是 `srd-engine/schemas.py` 的 `RATING_LABEL_*`。

翻转是**分数方向与百分比公式一起改**的，净效果是 **pct / level / overall_level 一格不动** ——
同一次评估在两版下结论完全相同，翻的只是分数这一层的标注。所以：

- 存量数据走 `sql/013-action-srd-score-flip-pg.sql`（只翻 rating/score/score_sum，
  **不碰 pct 与判定**；顺手把 pct 也翻了的话历史结论就真的反了）。幂等闸是 `engine_version` ——
  翻完给它追加 `(scores flipped to 0.8.0)`，翻转是自逆运算，没闸跑两遍就翻回去了
- 0.7.x 的 `result.json` 由 `AssessmentResult._accept_legacy_rating` 按 `engine_version` 自动翻。
  **判据只能是版本号**：翻转前后 rating 取值域一模一样（都是 '0'–'3'），单看一份结果
  无从分辨方向，所以这层挂在 `AssessmentResult` 上而不是 `ItemResult` 上
- `RATING_VERDICT`（3/2→dup，1/0→diff）与领域的 `dup_count`/`diff_count` 在翻转下**不变**：
  0↔3、1↔2 对调后恰好还落在原来那一侧
- 站点文案 `srd.rt0`–`srd.rt3` 这几个键**互换了含义**，013 里对它们强制 `text_* := default_*`。
  这是站点文案表唯一一处该冲掉人工覆盖的地方 —— 平时保留覆盖是对的，
  但键的所指变了，留着就等于把 3 分那档标成「完全不同」

**分数与重复百分比现在同向，但色阶仍跟着「重复程度」走、不跟着分数大小走**：
条目色阶是 3 分朱砂 → 0 分青（`.sc-3` … `.sc-0`，看着像「大数字偏红」，别顺手改回来），
领域与整体用另一套重复度色阶，两者刻意不共用颜色。

口径的唯一真源在引擎（`srd-engine/aggregate.py` + `schemas.py`），后端只做搬运；
`SrdService.RATING_SCORE` 是那张表的一份副本（不想为 5 个键把引擎整包拖进后端进程），
**改引擎的评分档位时记得同步它**（0.8.0 翻的是标签不是这层映射，所以它一字未动）。
条目层因此只有 `rating`/`score`，原来的 `action_srd_item.level`/`pct` 已删
—— 百分比是领域与整体才有的量。

示例数据（`is_sample='1'` 那条）的评分由原 pct 折算、领域与整体按同一套公式重算过，
现在与方法说明面板里写的算法是自洽的；**改示例请一并重算，别手填**。

### 「原文引用」那两列装的是原语言，不是英文

`action_srd_item.cite_a_en` / `cite_b_en` 存的是引擎的 `cite_a`/`cite_b` ——
**文献原文的逐字片段，保持原语言**；`cite_*_zh` 才是它的中文翻译。列名沿用了全库
`*_zh`/`*_en` 的双语命名，但这一对不是中英对照关系。

于是 `pages/srd.vue` 的引用列**刻意不走 `pick()`**：pick 在中文界面一律取 `*Zh`，
表现就是「上传的是英文文献，原文引用整列却是中文」—— 逐字引用是人工复核时唯一能
拿回原文去核的东西，一经翻译就核不动了。主行永远是 `citeAEn`（原文），译文由表头
那个「显示中文译文」开关点开、且只在中文界面、且译文与原文不同（中文文献两列同值）时才出现。

### 导出 Excel

结果区「导出 Excel」按钮：`GET /action/site/srd/assessments/{id}/export?lang=zh|en`
（示例走公开的 `/srd/sample/export`，与「看」的可见性规则一一对应）。三张工作表
概览 / 领域 / 条目明细，排版在 `module_action/service/srd_export_service.py`
（纯函数：模型 → 字节，离线可单测，见 `tests/test_srd_export.py`）。

- **数据源是业务库，不是引擎的 `result.json`** —— 那份文件在任务到终态后连同 session
  目录一起删了，而历史列表里三个月前的记录也得能导
- 与 `tools/srd-engine/export_excel.py` **不是一回事，别合并**：那个跑在引擎侧、读
  `pair-*.json`、一次导十对带评分锚点，是给方法学专家核金标准集用的
- xlsx 在后端拼（openpyxl 本来就在依赖里），不引前端的 SheetJS —— 那要往这个静态站里
  压几百 KB。代价是档位文案在后端又有一份副本（`srd_export_service._LEVEL/_RATING`），
  改判定档位时连同 `SrdService.RATING_SCORE` 与前台 i18n 一起改
- **`ResponseUtil.streaming` 默认不带 Content-Type，这里必须显式给 xlsx 的 media type**：
  本站错误走「HTTP 200 + code≠200」的 JSON 信封，前端就是靠这个头把「一份 xlsx」
  和「同一条通道上回来的错误信封」分开的（`useAuth.authedBlob`）。不给的话用户会
  下载到一个几百字节、打不开的「xlsx」，还以为是 Excel 坏了

整体判定理由 `overall_reason_*` 由引擎模板化生成（`aggregate.build_overall_reason`），
0.7.1 起**只讲查表这一步**，不再逐领域复述「得分 13/24（重复度 46%）低重复」：
那些数字在同一屏的领域卡片上逐个列着，抄第二遍就把「怎么得出这个结论的」这条唯一的
新信息埋没了。`provisional` / 待复核条数同理不再往这段话尾巴上挂 —— 它们是结果对象上的
独立字段，展示端各有各的位置。模型名 / 调用次数 / 耗时那一行也已从判定卡片撤掉
（数据仍在库里，是运维口径不是用户口径）。

## 报告规范 checklist

六份针刺报告规范（STRICTA / SPIRIT / PRISMA / CARE / RIGHT / ARRIVE）的**逐条 checklist** 已入库，
共 282 条，中英对齐，是报告助手第二步（结构化模板）与第三步（逐条校验）唯一的数据源。

- 表：`action_guideline_item`（`sql/action-checklist-pg.sql` 建表 + 灌数据，含补录的 STROBE 规范行）
- 抽取脚本：`tools/extract_checklists.py`，源文件是 `ACTION网站及其材料/针刺报告规范/` 下各规范的中英文版 docx
  —— **改条目请走后台「规范条目管理」页面，别手改生成的 SQL**
- 后台菜单：`sql/action-checklist-menu-pg.sql`（`action:guidelineItem:*`），页面
  `action-admin/src/views/system/guidelineItem/index.vue`
- 一份规范可能含多张清单表（RCT = CONSORT 主表 + 摘要表 + STRICTA 表），用 `part_no` 保留出处，
  前台按 `sort_num` 合并成一条流水清单
- 「研究类型 → 用哪份 checklist」由 `action_study_type.hot_guideline` 决定

### 第二步的第二条路：导入已有稿件

`POST /action/site/report-drafts/import`（multipart，docx/pdf/txt/md）。建表见
`sql/019-action-report-draft-import-pg.sql`，解析在 `service/manuscript_parse.py`（纯函数）。

**补的是这个洞**：导入口原先只在第三步，而第三步只产出**只读**判定 —— 第四步没有草稿条目
可写回、第五步的数据源是草稿于是整个导不出、下次再来还得重新粘一遍。而「哪些条目没覆盖」
第三步其实已经算出来了，缺的只是把它落成一份可继续加工的草稿。

- **原稿与条目框两份并存，这是整个设计的支点。** `action_report_draft.source_text` 存整篇
  原稿，**docx 导出正文以它为准**；条目框只装「从原稿摘出来的对应段落」，是对照与改写的
  工作面。不这么分的话导出会把用户的论文打散重排 —— 一句话常同时答好几条，而讨论、致谢、
  参考文献不对应任何条目、会凭空消失。`test_report_export.py` 用「讨论段必须还在、
  且不许插占位符」钉住
- **导入 = 跑一次 checklist 校验**，同一套 worker、同一个引擎、同一张结果表，
  区别只在 `action_report_review.purpose='import'` —— **只有那一次跑完才回填草稿**。
  不分用途的话，用户之后每复查一次就把自己在第二步的编辑悄悄盖掉一遍
- **回填按行号取原文，不用 `evidence`**：evidence 是引擎截到 200 字符的片段，拿它当条目
  正文，用户看到的是一句被砍断的话。行号口径的唯一定义在 `engine/audit.py::line_map`
  （空行不占号），后端 `_manuscript_line_map` 直接 import 它，不另造实现
- **回填只填空框**，已有内容的条目一律跳过
- 建草稿是同步的、映射是异步的：**映射失败不等于白导**，原稿已经存下了，用户可以逐条填
  或去第三步重跑
- 解析层的两个坑：**docx 的表格必须取**（基线特征、结局指标在中文论文里几乎总在表格里，
  漏了会让一整批条目被误判成「未报告」）；**PDF 要把硬换行粘回去**（PDF 按视觉行断句，
  不粘的话「第 12 行」指向半句话）。`.doc` 单独给「用 Word 另存为 .docx」的提示 ——
  它是这里最常见的一次失败
- `pymupdf` 此前只是 srd-engine 的可选 extra，做成后端功能后已在 `requirements.txt` 显式钉住

### 2→3→4→2 这个环

**第四步独立可用，工作清单只是有草稿时的快捷方式。** 它原先是一屏静态演示，对前三步状态的
引用次数是 **0** —— 既没有输入也没有输出。第一版改造把它接成了「第三步判定的工作清单」，
并强制要求 `draft_id` + `item_id`。

**那一版的论证是错的，别照着它再改回去。** 当时的理由是：《智能报告辅助工具.docx》第 4 节
那句「遵循 STRICTA 条目规范」露了馅 —— 遵循哪一条？所以必须先站在某一条上。但这句话要的是
**「知道按哪份规范写」，而那个信息第一步就给了**；把「需要规范」读成「需要具体条目」，
再推出「需要草稿和判定」，就把已经写好稿、直接来第三步的用户整个挡在了第四步之外。
文档第 4 节四项功能（续写 / 背景生成 / 润色 / 翻译）的输入**全是用户直接给的**
——关键词、研究方向、要润色的那段话、要翻译的摘要，没有一项依赖第二步或第三步；
其中背景生成与翻译**天然挂不到某一条上**，硬塞进逐条清单本身就是错配。

实际撞出来的现象：外部粘贴稿件跑完第三步，79 条判定、64 条待办摆在那儿，第四步一个字
都出不来（`GET /report-drafts/{id}/review` 取的是「某份草稿最近一次校验」，而这次校验
`draft_id` 是空的）。见 `AssistRequestModel` 与 `report_assist_prompt` 的模块 docstring。

现在的第四步有**两条路**，由 `AssistRequestModel` 有没有 `draft_id` 分：

- **独立模式（主体，默认）**：用户自己填关键词或粘一段正文，`guideline_code` 只告诉模型
  「按哪份规范写」。任何时候都能用，不需要草稿、不需要跑过校验。
  结果有两个去处：**没有草稿时只能「复制」**；有草稿时可以当场选一条条目写回
  （复用 `PUT /report-assist/apply`，后端一个字没改）。**写回的永远是当前打开的那份草稿**
  —— 选草稿走 `openDraft`，这样 `body` 里就是该条目的现有正文，既能在覆盖前摆给用户看，
  写回后同步 `body` 也一定同步对了草稿；允许写进「没打开的那一份」的话，
  这两件事都要另发请求，且极易把第二步的编辑态更新到另一份草稿上去。
  写回是整条覆盖，所以**覆盖前先显示该条目现有正文**并给一个「追加到末尾」的出路
- **草稿模式（快捷方式）**：第二步逐条填 → 第三步判定 → **判定落库**
  （`action_report_review` + `action_report_review_item`，`sql/010` 建表、`sql/014` 扩成台账）
  → 第四步按「描述模糊 / 未报告」列出待办 → 用户点「采用」**写回 `action_report_draft_item`**。
  这条路仍然完整，它顺带给第三步找回了价值：对着自己刚填的稿做完整性判定近乎循环论证，
  但它产出的 vague 列表正好是这里的输入

**前端第四步的空状态只剩「未登录」一道**（要调模型，匿名放开等于把账单交给公网）。
「还没有草稿 / 还没跑过校验」降级成下半段的一句说明（`.wk-hint`），不再 `v-else` 掉整块面板
—— 那两句文案也跟着改了（`sql/017`），原文「这一步才知道要改什么」在新版里是假的。

- **落库时机在 014 改过，别照着 010 的文件头理解这两张表。** 010 时它只服务第四步：
  仅当稿件就是第二步初稿时落、由**前端**在轮到 completed 那一刻另调 `POST /report-reviews`
  写入、不存稿件也不存 `evidence`。那样有两个洞，而它们在「刷新一下页面，刚跑完的校验就没了」
  上撞成同一个 —— 跑失败/被停/用户关掉页面的任务一条都没留下（恰恰是要排查的那批），
  且外部粘贴稿件的用户（第三步真正的主用户）在库里一个字都没有。
  现在是**提交即落一行 `pending` 台账，轮询到终态时由后端落判定**，
  `draft_id` 可空、`run_status` 记录任务生命周期；`POST /report-reviews` 已撤
  —— 两条写入路径并存必然漂移，所以撤掉一条而不是两条都留
- **AI 调用走同步接口 + `ai_models` 模型池，不走 Redis 队列**（`ai_assist_service.py`）。
  另外两个 worker 是几分钟级的任务，续写/润色是**秒级交互**，套队列会变成「提交→排队→轮询」。
  顺序轮询 + 出错切换，但**不做跨进程冻结** —— 那是为几分钟一次的任务做的优化，这里维护成本
  高于收益。池子空了或全挂了如实报错，**不静默返回空串**（那会被用户读成「AI 觉得没什么好改的」）
- **提示词是纯函数**（`report_assist_prompt.py`，可离线单测）。三条硬约束每次都发：不编造研究
  数据（样本量/p 值/随访时长一律留 `【待补充】`占位）、不新增未提供的方法学事实、只输出正文。
  这是学术报告工具，混进一个编造的 `n=120, p=0.03` 是科研诚信事故，不是文风问题
- **条目要求进 system 当指令，不进 user 当素材** —— 进了 user 模型就会把它抄进正文，
  与 `report_compose_service` 那条「条目要求原文不许进稿件」是同一个坑的两端
- **改写结果不自动写回**，由用户显式「采用」。让模型改用户的稿子而不问一声是不能接受的。
  写回走**单条覆盖**，套用第二步的整体覆盖语义会把没带上的其余条目全部清空
- **写回之后不许把 `dirty` 置 false。** 写回是后端「整份读回来、只换这一条、再写回去」，
  读的是**库里**那份 —— 客户端待保存的其他条目改动根本不在其中。而 `dirty` 一旦置假，
  `saveDraft` 开头那句 `if (!dirty) return` 就把 `touchDraft` 排好的那次自动保存整个吞掉：
  用户在第二步敲了几句、4 秒内切到第四步点「采用」，那几句就没了。踩过一次（原
  `applySuggestion` 就是这么写的）
- 前端 `POLISH_STYLES` 与后端 `report_assist_prompt._STYLE_RULES` 的键一一对应，
  改档位时两边一起改 —— 后端拿不认识的键会兜到 rigorous，表现是「选了没反应」

### 第三步的校验历史（014）

第三步现在有一份可回看的历史（`GET/DELETE /action/site/checklist-reviews`），
点开还原整屏结果、包括当时提交的稿件。改这一层前先读
`sql/014-action-report-review-history-pg.sql` 的文件头 —— 隐私口径就是在那里翻的。

- **「稿件不入库」这条承诺已经作废，别再按它写代码。** 014 起 `manuscript` 与逐条
  `evidence` 随台账一起落库：evidence 是判定引用的原文逐字片段，而它**脱离正文就是一句
  回不到上下文的孤立引文**，所以要么两个都不存（回看只剩「第12条 描述模糊」，没有原文可核）、
  要么一起存。甲方选了后者。`assistant.rvHint` 那句文案**已同步改写**
  （`sql/015-action-site-text-review-history-pg.sql`）——**这两份必须同一批上线**，
  先上 014 就等于页面上挂着一句假承诺
- **对价是删除时真删正文**：`soft_delete_review_dao` 置 `del_flag='2'` 的同时把
  `manuscript` 与 `evidence` 物理清空，台账那几列（session_id / 状态 / 错误 / 计数 / 时间）
  留着。用户点「删除」期待的是「那篇稿子没了」，不是「列表里看不见了」；
  而排障要的恰好是留下的那几列，它们不含任何稿件内容
- **对账照抄 SRD**：落库在轮询接口里做不在 worker 里（worker 只认 Redis 不认业务库），
  代价是「用户关掉页面就没人来落库」，由历史列表接口顺带补查一次 worker 状态兜底。
  同理这条链路要连着提交好几次事务，**别把 ORM 对象跨 commit 传下去** —— 用 `_ReviewRun` 快照。
  **踩过一次**：`submit_review_services` 在 commit 之后才去取 `guideline.code` 拼入队 payload，
  于是每次提交都在落库成功之后抛 `MissingGreenlet`（"greenlet_spawn has not been called"），
  表现是「历史里多了一条 pending，页面却报错」。规范的 id 与 code 现在在 commit 前就抄成普通值
- **提交口撞上限时会先对账再判**（`_reconcile_pending`）。并发闸数的是 pending/running 的行，
  而那种行未必真在跑：入队失败、worker 崩了、Redis 状态过了 TTL 都会留下永远等不到终态的孤儿，
  照样占着名额。只数不对账的话两个孤儿就把账号**永久**锁死，而用户只看得到一句
  「你已有 2 个校验在进行中」且怎么等都不消失。对账有 Redis 往返，所以只在真撞上限时才做
- **前端刷新后会认领回还在跑的任务**（`resumeReview`）：从历史里找到 pending/running 那条，
  接回 `session_id` 继续轮询，进度条从中途接上。任务本来就在 worker 那边照跑不误，
  014 之前丢的只是前端那根线头
- **草稿删除时校验记录不删，只摘掉 `draft_id`**（`detach_reviews_of_draft_dao`）。
  010 时那里是物理删，理由是「判定脱离草稿没有意义」—— 那个理由随 014 失效了，
  每条记录现在自带稿件快照，是能独立回看的历史。跟着草稿删等于用户没要求过的数据丢失
- **`get_latest_review_dao` 必须过滤 `run_status='completed'`**：台账化之后表里会有排队中、
  跑挂了的行，第四步取到它们就会拿着一份空判定列出「0 条待办」，和「这份稿子全绿」
  长得一模一样
- 历史每人留 20 条（`KEEP_HISTORY`，按**访客**修剪不按草稿 —— 外部粘贴的稿件没有草稿可依附），
  同时在跑的上限 2 个。每行挂着一整篇稿件，比 010 时更该管上限
- 库里 `lines` 是逗号分隔字符串，worker 直接吐回的是数字数组，**回看时要转**，
  不转的表现是「报告于第 3,7,12 行」整串挤在一个占位里
- **结果区那块稿件原文的行号，编法必须与 worker 的 `engine/audit.py::number_lines` 一致**：
  那边**空行原样输出但不占行号**，所以「第 8 行」指的是第 8 个**非空**行。照物理行号编的话，
  稿件里出现第一个空行之后全线错位 —— 而错位的表现极其温和：行号仍在合法范围内、
  面板照常滚过去、高亮照常亮起，**只是指着一段不相干的话**。实测一份 2193 字的稿件：
  物理 77 行 / 有效 39 行。前端那份实现在 `composables/manuscriptLines.ts`（纯函数），
  由 `test/manuscriptLines.spec.ts` 钉住，**两边任何一边改编号规则都要同步**。
  它还得认 `\f` `\v` 等 Python `splitlines()` 会断而 `split('\n')` 不断的字符
  —— 从 PDF/Word 粘出来的稿件里分页符很常见，少认一个后面整体偏移

### 操作留痕

文档 3.4 的「操作日志」。表 `action_report_trail`（`sql/011-action-report-trail-pg.sql`），
接口 `POST/GET /action/site/report-trails`。此前 `trail` 只是前端内存里的 8 条，刷新即失。

- **只存结构化的数字与枚举，不存渲染好的句子。** 句子里迟早会混进稿件正文片段
  （「已提交稿件：本研究纳入 120 例……」）。原来的理由是这会绕过第三步「稿件不入库」的承诺；
  014 之后稿件本来就存了，但这条**照旧不改** —— 留痕表没有删除入口（审计记录能删就不是
  审计记录），而校验历史有。正文只该躺在那个删得掉的地方，不该顺着句子渗进这张删不掉的表。
  人读的那句话由前端 `trailText()` 按 i18n 拼，库里只有 `event` 键与几个计数。
  `event` 是 `Literal` 白名单不是自由文本，唯一的自由文本 `note` 仅供系统诊断且限长 300
- **最该留痕的是 `event=applied`** —— 第四步把模型生成的文字写回 `action_report_draft_item`，
  那是这套工具里真正的「关键数据修改」。投稿时被问起「AI 参与了多少」，这张表就是答案。
  这条**由服务端在 `apply_services` 里自己记，不走接口**：靠前端调用的话，前端不调就没了
- 全稿一致性事件复用同三个计数列（issue→missing、warn→vague、ok→reported），
  免得为一个事件另开三列；渲染时按 `event` 分支取回去
- 草稿删除时**留痕不删**：「这份稿子有哪几段来自模型」在草稿删掉之后反而更需要答得出来，
  所以 `draft_id` 只是弱关联，不做级联
- **踩过一次 `MissingGreenlet`**：`add_trail_services` 原本先 commit 再装出参，而会话是
  `expire_on_commit=True`，commit 后读任何 ORM 属性（包括主键）都会触发懒加载。
  现在是 flush 拿到主键 → 装出参 → 再 commit，`tests/test_report_trail.py` 钉住

### 第五步：导出

`GET /action/site/report-drafts/{id}/export?fmt=docx|xlsx|json&lang=zh|en`，排版在
`module_action/service/report_export_service.py`（纯函数：模型 → 字节，离线可单测，
见 `tests/test_report_export.py`）。三种格式各答一个问题：**docx** 稿件本身（按章节分节 +
附录对照表）· **xlsx** 投稿随附的 checklist 对照表（带第三步判定）· **json** 结构化留档。

- **数据源是业务库那份草稿，不是第二步合成的那段文本** —— 后者是瞬时产物，用户可能压根
  没点过「生成初稿」
- **「条目要求原文不进正文」在这里有个边界**：docx 的**正文**不含要求原文（同
  `report_compose_service`，抄进去第三步会判成「已报告」），但 **docx 附录表与 xlsx 必须有**
  —— 那张表的用途正是让编辑逐条对照「这条要求你写在哪」。区别在于那段文字是以「稿件」
  还是以「对照表」的身份出现，`test_report_export.py` 用「要求原文必须出现在附录标题之后」
  这条断言钉住
- **不出 PDF**（文档第 5 节要的「合规 PDF」）：服务端生成中文 PDF 要在服务器装中文字体，
  字体缺失时是**整篇方块字而不是报错** —— 这种失败方式在导出场景代价太高，docx 自己另存更可靠
- `python-docx` 此前只是 agno 的**传递依赖**，做生产功能后已在 `requirements.txt` 显式钉住
- 同 SRD 导出：**`ResponseUtil.streaming` 必须显式给 media type**，前端靠它把「一份文件」
  和「同一条通道回来的错误信封」分开（`useAuth.authedBlob`）
- **「加密分享链接」与「版本快照对比」两段已关掉**（`assistant.vue` 的 `SHOW_WIP_SHARE=false`，
  同 `guidelines.vue` 的 `SHOW_WIP_TABS`）。不是排期问题，是两个未定的设计：分享链接一旦真发
  就是个**匿名可读的未发表稿件外链**，有效期/撤销/评论存哪/被转发怎么办要先定，不是加个随机串
  了事；版本对比要先有快照模型。留着一个会复制出真链接的按钮，用户会以为它真的分享了什么

**助手实际服务两类人，五步向导只是目录、不是必经路径。** 从零开始写的人第 2 步是主菜，
第 3 步的完整性判定几乎必然全绿（对着 checklist 逐条填出来的稿，再逐条判「报告了吗」近乎
循环论证，真正有信息量的只有「描述模糊」和全稿一致性那半）；已经写好稿的人第 2 步整个用不上，
第 3 步才是主菜。第一步末尾因此有个**路线岔口**（`stage`：`draft` / `manuscript` / 空=没选），
按选择给步骤条加「可跳过 / 初稿后」角标、给第 2 步加跳转提示、给第 3 步换一套说法。
**只标注不拦截**——两条路的步骤都点得进去；也**不替用户默认选一个**，猜错就是把人推到
用不到的那一步。取值与 URL 同步的构造/校验都在 `composables/wizardQuery.ts`。

**「唯一的数据源」是字面意思：第二步不许再有第二套字段。** 原先编辑页右栏挂着一组
「针灸特色专属字段」（选穴依据 / 进针手法 / 得气 / 对照措施，主表 `acu_*` 五列），
用户填一次、合成初稿时按关键词挂到语义最近的那条条目下面。**已整体撤除**，理由是它
与 checklist 重复且后台管不到：库里 6 份规范有 5 份本身就是针刺适配版
（STRICTA / SPIRIT-TCM / PRISMA-Acu / CARE-Acu / RIGHT-Acu），这些内容各有对应条目
（实测命中：选穴 0–3 条、进针 0–3 条、得气 0–1 条、对照 0–7 条），
用户两处都填时初稿里同一段针刺方案会输出两遍，正好撞在第三步的一致性检查上。
唯一真缺口是 ARRIVE（通用动物实验规范，21 条零针刺内容）——**那是内容问题，
后台「规范条目管理」加几条就行，不要再往代码里加字段**。
`acu_*` 五列留在库与 ORM 里不读不写（撤除前存过的草稿还在里面），见
`module_action/entity/do/action_do.py` 的 `ActionReportDraft` docstring。

同理，`ComposeItem` **刻意不带条目要求原文**：条目要求长得就像一句合格的报告，
抄进稿件后第三步会把这句要求本身判成「已报告」，整轮逐条判定作废。这条不靠自觉遵守，
靠合成层的数据结构里根本没有那个值 —— 见 `service/report_compose_service.py` 的模块 docstring。

## 报告规范目录与分类

`pages/guidelines.vue` 的四段内容全部由库驱动，后台三个页面各管一层：

- **规范目录管理**（`action_guideline`）—— 卡片、下载面板、版本管理表的数据源，
  页面 `action-admin/src/views/system/guideline/index.vue`，菜单 `sql/action-guideline-menu-pg.sql`。
  中英文原文 PDF 在这个页面直传 OSS（见上一节），`file_url_zh/en` 存的是公网直链；
  前台下载按钮的格式角标由 URL 扩展名推出，不再写死 DOCX
- **规范分类管理**（`action_guideline_category`，建表 + 8 条种子见 `sql/action-guideline-category-pg.sql`）
  —— 第①段筛选条的词表，chip 文案、卡片「研究设计」标签、卡片图标（`icon_paths`，一行一条 SVG path）同源
- **规范条目管理**（`action_guideline_item`）—— 逐条 checklist，见上一节

**`action_guideline.study_type` 的取值域就是 `action_guideline_category.cat_key`**，不另设关联列。
写接口会校验分类存在（`GuidelineService._assert_study_type_exists`），分类下有规范时不许改键、不许删除
—— 这三道闸拦的是同一件事：`study_type` 落在分类表外的规范，在前台任何 chip 都筛不出来、标签还是空白。

与 `action_study_type` 的分工：那张表是**报告助手第一步的问卷词表**（类型 → 规范 + 统计推荐），
分类表是**规范目录的陈列分类**。两者用途不同，不要合并（这也了结了 deferred-work 的 W23「两套词表」），
但**同一类研究在两边取同样的 key**（protocol / animal / guideline），只是不构成外键关系。

问卷词表原先只有 5 行（rct/nrct/case/sr/obs），于是 SPIRIT 79 + RIGHT 42 + ARRIVE 21 共 **142 条
checklist 在助手里没有任何路径能走到** —— 明明在规范目录页陈列着，第一步却选不出来。
`sql/003-action-study-type-protocol-animal-guideline-pg.sql` 补齐到 8 行。前端选项在
`pages/assistant.vue` 的 `TYPE_OPTS`，**文案键的后缀就是 `type_key`**（`assistant.typeOpt.<key>`）——
往表里加类型时要同步加 i18n 词条并进 `action_site_text`，否则新选项显示成键名本身。

**`hot_guideline` 必须指向 `action_guideline.code` 且那份规范真有条目**：它决定第二步展开哪份
checklist。眼下 `obs → STROBE` 是 0 条（仓库里没有 STROBE 的中英素材），前台靠 `noItems`
在第三步禁用按钮并说明原因 —— 原先按钮照样可点，要等提交到后端才报错。

**这三张表的 id 都是显式写死插入的，serial 序列因此一直停在 1**，后台新增第一条就撞主键。
全量文件与 003 增量末尾都补了 `setval`，新加种子数据时照做。

`pages/guidelines.vue` 眼下**只对外开第①段分类导航**：卡片点击跳独立页
`pages/guideline/[id].vue`（路由用单数 —— 建 `pages/guidelines/` 目录会把目录页变成需要 `<NuxtPage>`
的父级路由），那页用 `<iframe>` 内嵌 PDF 原文，中英两版都有时给切换按钮；
详情取数走 `GET /action/site/guidelines/{id}`，**iframe 的地址是 `GET /action/site/guidelines/{id}/file`
而不是 OSS 直链**（理由见上一节的强制下载）。原第②段「在线预览与下载」的折叠列表连同 `.dl-*` 样式已删。

「版本管理 / 试点测试」两段内容待定稿，由 `guidelines.vue` 里的 `SHOW_WIP_TABS = false` 连同子栏目 Tab
一起关着（模板与样式都还在，改成 true 即恢复）—— 别再给这几段留静态的 `is-hidden`，
`base.css` 里那条是 `display:none !important`；Tab 互斥切换的写法照抄 `pages/about.vue`。

两页共用的字段类型与小工具放 `composables/useGuidelines.ts`（`GuidelineRow` / `GuidelineCategoryRow` /
`categoryIconPaths`），别在页面里各抄一份 interface。
