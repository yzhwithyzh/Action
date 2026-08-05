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
- **模型配置从 `ai_models` 表读**（`tools/common/model_registry.py`，与后端 AI 对话共用
  `AiModelService.get_usable_ai_model_pool_services`）：取到的是一个池子，按 `model_sort` 顺序
  「粘性 + 出错切换」，撞到限流/欠费就冻结 5 分钟换下一个，冻结表在 Redis 跨进程共享
- 已改造：`tools/srd_worker_tool`（包装 `tools/srd-engine` 纯算法引擎，见其 README）
- 已新增：`tools/checklist_worker_tool`（报告助手第三步：稿件 × 报告规范逐条校验，见其 README）
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

**官网内容图片一律存阿里云 OSS**（桶 `action-gmu` · 华南3 广州），不落后端磁盘 ——
官网是 `nitro.preset: 'static'` 的预渲染站，图片跟着后端机器走会在换机/多副本部署时开天窗。

- 配置 `OssSettings`（`config/env.py`，读 `.env` 的 `OSS_*`），工具 `utils/oss_util.py`
- 手写 OSS V1 签名 + httpx，**不引 `oss2`**，与 `module_action/service/mail_service.py` 对 DirectMail 的做法一致
- 上传口 `POST /action/admin/team-member/avatar`，后台页用 `ImageUpload` 直传；不走 `/common/upload`（那条落本地磁盘）
- 批量迁移/回填：`python -m tools.upload_team_avatars`，回写 DB 与种子 SQL 前会**匿名 GET 自检**，
  读不到就拒绝回写（传上去 ≠ 读得到；桶没授公共读时前台会整片裂图）

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
