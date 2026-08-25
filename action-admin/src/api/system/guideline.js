import request from '@/utils/request'

// 查询报告规范目录列表
export function listGuideline(query) {
  return request({
    url: '/action/admin/guideline/list',
    method: 'get',
    params: query
  })
}

// 查询报告规范详细
export function getGuideline(guidelineId) {
  return request({
    url: '/action/admin/guideline/' + guidelineId,
    method: 'get'
  })
}

// 新增报告规范
export function addGuideline(data) {
  return request({
    url: '/action/admin/guideline',
    method: 'post',
    data: data
  })
}

// 修改报告规范
export function updateGuideline(data) {
  return request({
    url: '/action/admin/guideline',
    method: 'put',
    data: data
  })
}

// 删除报告规范
export function delGuideline(guidelineId) {
  return request({
    url: '/action/admin/guideline/' + guidelineId,
    method: 'delete'
  })
}

// 查询报告规范分类（规范表单的「研究设计」下拉用）
export function listGuidelineCategory(query) {
  return request({
    url: '/action/admin/guideline-category/list',
    method: 'get',
    params: query
  })
}
