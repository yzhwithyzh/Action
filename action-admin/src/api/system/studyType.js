import request from '@/utils/request'

// 查询研究类型列表（不分页：这是张词表，眼下 8 行）
export function listStudyType(query) {
  return request({
    url: '/action/admin/study-type/list',
    method: 'get',
    params: query
  })
}

// 新增研究类型
export function addStudyType(data) {
  return request({
    url: '/action/admin/study-type',
    method: 'post',
    data: data
  })
}

// 修改研究类型（两张子表整体覆盖）
export function updateStudyType(data) {
  return request({
    url: '/action/admin/study-type',
    method: 'put',
    data: data
  })
}

// 删除研究类型（连同关联规范标签与统计推荐）
export function delStudyType(typeIds) {
  return request({
    url: '/action/admin/study-type/' + typeIds,
    method: 'delete'
  })
}
