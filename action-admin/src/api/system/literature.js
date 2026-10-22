import request from '@/utils/request'

// 查询文献库统计（顶部概览卡片）
export function getLiteratureStats() {
  return request({
    url: '/action/admin/literature/stats',
    method: 'get'
  })
}

// 查询病种类目词表（筛选下拉）
export function listConditionGroup() {
  return request({
    url: '/action/admin/literature/condition-groups',
    method: 'get'
  })
}

// 查询参考文献列表
export function listLiterature(query) {
  return request({
    url: '/action/admin/literature/list',
    method: 'get',
    params: query
  })
}

// 查询参考文献详细
export function getLiterature(litId) {
  return request({
    url: '/action/admin/literature/' + litId,
    method: 'get'
  })
}

// 查询参考文献全文（单篇正文中位 1.8 万字符，点开「查看原文」时才拉）
export function getLiteratureText(litId) {
  return request({
    url: '/action/admin/literature/' + litId + '/text',
    method: 'get'
  })
}

// 修改参考文献
export function updateLiterature(data) {
  return request({
    url: '/action/admin/literature',
    method: 'put',
    data: data
  })
}

// 批量置复核状态（判为剔除时后端会同步停用，不再进检索）
export function reviewLiterature(data) {
  return request({
    url: '/action/admin/literature/review',
    method: 'put',
    data: data
  })
}

// 删除参考文献
export function delLiterature(litIds) {
  return request({
    url: '/action/admin/literature/' + litIds,
    method: 'delete'
  })
}
