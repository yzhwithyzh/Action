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

// ---------------------------------------------------------------- 分支问卷（第一步，sql/041）

// 查询整棵问卷（全部题与选项）
export function listStudyWizard() {
  return request({
    url: '/action/admin/study-wizard/list',
    method: 'get'
  })
}

// 新增题目（选项整体覆盖）
export function addWizardQuestion(data) {
  return request({
    url: '/action/admin/study-wizard',
    method: 'post',
    data: data
  })
}

// 修改题目（选项整体覆盖）
export function updateWizardQuestion(data) {
  return request({
    url: '/action/admin/study-wizard',
    method: 'put',
    data: data
  })
}

// 删除题目
export function delWizardQuestion(questionIds) {
  return request({
    url: '/action/admin/study-wizard/' + questionIds,
    method: 'delete'
  })
}
