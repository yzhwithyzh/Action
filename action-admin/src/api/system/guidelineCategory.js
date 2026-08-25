import request from '@/utils/request'

// 查询报告规范分类列表
export function listGuidelineCategory(query) {
  return request({
    url: '/action/admin/guideline-category/list',
    method: 'get',
    params: query
  })
}

// 查询报告规范分类详细
export function getGuidelineCategory(catId) {
  return request({
    url: '/action/admin/guideline-category/' + catId,
    method: 'get'
  })
}

// 新增报告规范分类
export function addGuidelineCategory(data) {
  return request({
    url: '/action/admin/guideline-category',
    method: 'post',
    data: data
  })
}

// 修改报告规范分类
export function updateGuidelineCategory(data) {
  return request({
    url: '/action/admin/guideline-category',
    method: 'put',
    data: data
  })
}

// 删除报告规范分类
export function delGuidelineCategory(catId) {
  return request({
    url: '/action/admin/guideline-category/' + catId,
    method: 'delete'
  })
}
