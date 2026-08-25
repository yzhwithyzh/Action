import request from '@/utils/request'

// 查询站点文案列表
export function listSiteText(query) {
  return request({
    url: '/action/admin/site-text/list',
    method: 'get',
    params: query
  })
}

// 查询分组词表（含每组词条数与已改动数）
export function listSiteTextGroups() {
  return request({
    url: '/action/admin/site-text/groups',
    method: 'get'
  })
}

// 查询站点文案详细
export function getSiteText(textId) {
  return request({
    url: '/action/admin/site-text/' + textId,
    method: 'get'
  })
}

// 修改站点文案（只有 textZh / textEn / remark 会被后端采纳）
export function updateSiteText(data) {
  return request({
    url: '/action/admin/site-text',
    method: 'put',
    data: data
  })
}

// 还原为代码里的默认文案，textIds 传 'all' 表示全部还原
export function restoreSiteText(textIds) {
  return request({
    url: '/action/admin/site-text/restore/' + textIds,
    method: 'put'
  })
}

// 查询官网重新生成状态
export function getSiteRebuildState() {
  return request({
    url: '/action/admin/site-text/rebuild',
    method: 'get'
  })
}

// 触发官网重新生成
export function triggerSiteRebuild() {
  return request({
    url: '/action/admin/site-text/rebuild',
    method: 'post'
  })
}
