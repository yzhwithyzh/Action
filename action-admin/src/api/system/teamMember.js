import request from '@/utils/request'

// 查询团队成员列表
export function listTeamMember(query) {
  return request({
    url: '/action/admin/team-member/list',
    method: 'get',
    params: query
  })
}

// 查询团队成员详细
export function getTeamMember(memberId) {
  return request({
    url: '/action/admin/team-member/' + memberId,
    method: 'get'
  })
}

// 新增团队成员
export function addTeamMember(data) {
  return request({
    url: '/action/admin/team-member',
    method: 'post',
    data: data
  })
}

// 修改团队成员
export function updateTeamMember(data) {
  return request({
    url: '/action/admin/team-member',
    method: 'put',
    data: data
  })
}

// 删除团队成员
export function delTeamMember(memberId) {
  return request({
    url: '/action/admin/team-member/' + memberId,
    method: 'delete'
  })
}
