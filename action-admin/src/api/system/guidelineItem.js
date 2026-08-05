import request from '@/utils/request'

// 查询报告规范目录（条目管理页的规范下拉用）
export function listGuideline(query) {
  return request({
    url: '/action/admin/guideline/list',
    method: 'get',
    params: query
  })
}

// 查询规范条目列表
export function listGuidelineItem(query) {
  return request({
    url: '/action/admin/guideline-item/list',
    method: 'get',
    params: query
  })
}

// 查询规范条目详细
export function getGuidelineItem(itemId) {
  return request({
    url: '/action/admin/guideline-item/' + itemId,
    method: 'get'
  })
}

// 新增规范条目
export function addGuidelineItem(data) {
  return request({
    url: '/action/admin/guideline-item',
    method: 'post',
    data: data
  })
}

// 修改规范条目
export function updateGuidelineItem(data) {
  return request({
    url: '/action/admin/guideline-item',
    method: 'put',
    data: data
  })
}

// 删除规范条目
export function delGuidelineItem(itemId) {
  return request({
    url: '/action/admin/guideline-item/' + itemId,
    method: 'delete'
  })
}
