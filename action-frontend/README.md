# action-frontend

ACTION 官网（对外品牌站）—— Nuxt 3 + SSG。由根目录原有的 8 个静态 HTML 页面迁移而来。

与 `action-admin`（RuoYi 后台管理界面）是两个独立前端：本项目对外，`action-admin` 对内。

## 环境要求

- Node.js ≥ 20（开发机为 v22.19.0）
- 后端 `action-backend` 运行在 `127.0.0.1:9098`（接口代理目标）

## 安装

```bash
npm install --legacy-peer-deps
```

> **`--legacy-peer-deps` 是必须的，不是偷懒。** npm 10.9.3 的 arborist 在解析 Nuxt 的 peer 依赖图时会崩溃：
> `TypeError: Cannot read properties of null (reading 'edgesOut')`（栈顶为 `#loadPeerSet`）。
> 该参数绕开出问题的解析路径。若日后升级到修复此 bug 的 npm 版本，可去掉该参数重新验证。

## 常用命令

```bash
npm run dev        # 开发服务器，http://localhost:3010
npm run generate   # 构建静态站点，产物在 .output/public
npm run preview    # 本地预览构建产物
```

> 端口由 `nuxt.config.ts` 的 `devServer.port` 固定为 3010（不设则走 Nuxt 默认 3000，
> 且被占用时会自动 +1）。开发服务器在 Windows 上会监听 IPv6 回环，
> 用 `http://localhost:3010` 访问，直接用 `http://127.0.0.1:3010` 可能连不上。

## 样式分层（务必保持加载顺序）

迁移前，8 个页面各自内联一整份 `<style>`，并由 `assets/site.js` 在运行时向 `<head>`
追加一份顶栏/页脚样式覆盖各页同名规则。迁移后拆成三层，**顺序即优先级**：

| 文件 | 内容 | 顺序 |
|---|---|---|
| `assets/css/base.css` | 设计令牌、重置、排版、按钮、kicker、栅格 | 1 |
| `assets/css/chrome.css` | 顶栏与页脚（原 `site.js` 注入，权威） | 2 |
| 各页 SFC 的 `<style>` | 页面专属 | 3 |

前两层在 `nuxt.config.ts` 的 `css: []` 中按序声明，**不要调换**。

迁移时剥离了各页内联的 `header` / `.nav` / `.menu` / `.lang` 等规则——它们在原实现中
就已被 `site.js` 的 chrome 样式完全覆盖，属于死代码，剥离不改变任何视觉表现。

## 设计令牌

配色为**新中式天青 + 朱砂**（`:root` 注释标注「甲方定稿」）：

- 主色 `--indigo-500: #2c7f72`（变量名沿用 indigo，实际值是天青）
- 强调 `--cinnabar: #cf4635`
- 纸面 `--paper: #f2f6f4`

> 根目录 `DESIGN.md` 记录的是更早的靛青方案（`#1e3253`），**已过期**，以本项目实际令牌为准。

## 双语

`@nuxtjs/i18n`，`strategy: 'no_prefix'`——与原站一致，同一 URL 内切换语言，不做 `/en` 前缀路由。
文案在 `i18n/locales/{zh,en}.json`。原实现把英文放在 DOM 的 `data-en` 属性上，迁移时已抽出。

## 接口代理

开发期 `nuxt.config.ts` 的 `routeRules` 把 `/dev-api/**` 代理到 `http://127.0.0.1:9098/**`。
生产部署需在 Nginx 等反向代理上做等价配置。

> `apiBase` 在静态构建时就被写死进产物（`runtimeConfig.public` 对 SSG 而言是构建期常量），
> 线上运行时改 `NUXT_PUBLIC_API_BASE` **不生效**，要改只能重新构建。

## 取数与构建期数据（务必先读）

`nitro.preset: 'static'` + `ssr: true` 意味着：**页面里 `useSiteList` / `useSiteObject` 的结果，
是在 `npm run generate` 那一刻烤进 HTML 的。**由此有两条硬约束：

**1. 构建时后端必须可达。** 否则代理返回 502，`useSiteApi` 的 `default` 把它兜成空数组，
构建照样"成功"，但产物是空壳——曾经发生过一次，`/`、`/news`、`/guidelines`、`/assistant`、
`/implementation` 五个页面把 502 连同错误信息一起写进了线上 HTML。构建前先确认：

```bash
curl "http://127.0.0.1:9098/action/site/news?pageNum=1&pageSize=3"   # 期望 200 且 rows 非空
```

构建后可自查产物里有没有把错误烤进去：

```bash
grep -l "Bad Gateway" .output/public/**/*.html   # 应无输出
```

**2. 后台改完，访客刷新即见 —— 这是默认行为，页面不用做任何事。**
`useSiteList` / `useSiteObject` 会在 hydration 完成后再跟后端对一次，有变化就换掉。
首屏依然是预渲染的静态 HTML（SEO 与首屏速度不受影响）。要关掉得显式传 `{ revalidate: false }`，
正常不要关（原先是反过来的 `{ swr: true }` opt-in，见下）。

**改 `useSiteApi.ts` 时唯一不能碰的一行：那次重取必须挂在 `onNuxtReady`，不能是 `onMounted`。**
Nuxt 的 `useAsyncData.execute()` 只要看到 `nuxtApp.isHydrating` 为真，就先问 `getCachedData()`，
而默认实现在 hydration 期间**无视 `refresh:manual`**、直接返回 `nuxtApp.payload.data[key]`
（静态站里就是 `_payload.json` 那份构建期快照）—— 于是 `refresh()` 用旧数据立刻 resolve，
**一个请求都不发**。而 `isHydrating` 要到 `app:suspense:resolve` 才置 false，那在页面
`onMounted` 之后。这个坑真踩过：`{ swr: true }` 开了整整一圈，线上「后台改完刷多少次都是旧的」，
`plugins/site-texts.ts` 的文案却能刷出来 —— 差别只在它用的是 `onNuxtReady`。
改动前后各构建一次、用无头浏览器对比过：`onMounted` 版拿不到新数据，`onNuxtReady` 版拿得到。

**这一层管不了搜索引擎和微信分享卡片**：它们只看首屏 HTML，仍是构建期快照。
要「后台一发布、爬虫立刻可见」，得改 `preset: 'node-server'` 实时 SSR，或给发布动作挂重建钩子
——后者已经有了：后台「站点文案管理」页的「重新生成官网」按钮（见下一节）。

**3. 接口数据换进来的节点会自动揭示，不用再写 `watch(rows, rescan)`。**
`.reveal` 的观察者原本只在 `onMounted` 建一次，重取换掉的新节点没人观察就永远停在
`opacity:0` —— 「数据对、行数对，但整块空白」，且和「后台还没填内容」长得一模一样。
`useReveal` 现在挂了 MutationObserver 接管新增节点。**唯一顶不了的是 display 切换**
（`/guidelines` 的筛选 chip 给卡片切 `.hide`，没有节点新增），那里仍需手动 `rescan()`。

## 版面文案（i18n 的可编辑副本）

`i18n/locales/{zh,en}.json` 那 934 条文案在后端 `action_site_text` 表里有一份可编辑副本，
后台改完由 `plugins/site-texts.ts` 在 i18n 之上 merge 一层。**默认文案仍以这两份 JSON 为准**，
改默认文案就改 JSON，然后在 action-backend 下重跑 `python -m tools.extract_site_texts` 同步。

接口 `GET /action/site/texts` 只返回被改过的词条，没人改过时是空对象。插件里三处不能动的细节
（扁平键必须先 unflatten、构建期取数进 payload 以避免 hydration 不匹配、切语言后要重新 merge）
写在文件头注释里，改之前先读。整体说明见仓库根 `CLAUDE.md` 的「站点文案」一节。

**3. `/news/[id]` 详情页靠爬取生成。** `crawlLinks` 从 `/news` 列表页的 `<NuxtLink>` 发现它们，
而只有**没配 `linkUrl`** 的条目才会指向站内详情页。构建后新增的这类新闻不会有对应的静态文件，
需要 Nginx 把未命中的路径回落到 `200.html`（SPA fallback），交给客户端渲染。
