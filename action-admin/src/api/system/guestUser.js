import request from '@/utils/request'

// 查询官网访客列表
export function listGuestUser(query) {
  return request({
    url: '/action/admin/guest/list',
    method: 'get',
    params: query
  })
}

// 查询官网访客详细
export function getGuestUser(userId) {
  return request({
    url: '/action/admin/guest/' + userId,
    method: 'get'
  })
}

// 停用 / 启用官网访客
export function changeGuestUserStatus(userId, status) {
  return request({
    url: '/action/admin/guest/status',
    method: 'put',
    data: { userId, status }
  })
}
