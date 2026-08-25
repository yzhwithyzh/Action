import request from '@/utils/request'

// 查询成果发表列表
export function listPublication(query) {
  return request({
    url: '/action/admin/publication/list',
    method: 'get',
    params: query
  })
}

// 查询成果发表详细
export function getPublication(publicationId) {
  return request({
    url: '/action/admin/publication/' + publicationId,
    method: 'get'
  })
}

// 新增成果发表
export function addPublication(data) {
  return request({
    url: '/action/admin/publication',
    method: 'post',
    data: data
  })
}

// 修改成果发表
export function updatePublication(data) {
  return request({
    url: '/action/admin/publication',
    method: 'put',
    data: data
  })
}

// 删除成果发表
export function delPublication(publicationId) {
  return request({
    url: '/action/admin/publication/' + publicationId,
    method: 'delete'
  })
}

// 两个解析口都要**单独放宽超时**：`utils/request.js` 里 axios 实例的默认超时是 10 秒
// （RuoYi 的默认值，对普通 CRUD 合适），而这两条要等外部服务与模型跑完，10 秒必然不够。
// 不改全局那个默认值 —— 那会让所有卡住的请求都拖上一两分钟才报错。
// axios 的 per-request timeout 会覆盖实例默认值。

// 按 DOI 解析元数据（走 Crossref，只认 DOI 与 doi.org 链接，不抓任意网址）
// 后端最坏情况：Crossref 15 秒 + PubMed 两跳各 8 秒
export function parsePublicationDoi(source) {
  return request({
    url: '/action/admin/publication/parse-doi',
    method: 'post',
    data: { source },
    timeout: 60000
  })
}

// 上传 PDF 提取元数据（走 ai_models 模型池；这份 PDF 不会被存下来）
// 后端那一侧的上限是 150 秒（`_PDF_TIMEOUT_SECONDS`），这里留出余量
export function parsePublicationPdf(data) {
  return request({
    url: '/action/admin/publication/parse-pdf',
    method: 'post',
    data: data,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000
  })
}
