import request from '@/utils/request'

// 查询资源中心链接列表
export function listResourceLink(query) {
  return request({
    url: '/action/admin/resource-link/list',
    method: 'get',
    params: query
  })
}

// 查询资源中心链接详细
export function getResourceLink(linkId) {
  return request({
    url: '/action/admin/resource-link/' + linkId,
    method: 'get'
  })
}

// 新增资源中心链接
export function addResourceLink(data) {
  return request({
    url: '/action/admin/resource-link',
    method: 'post',
    data: data
  })
}

// 修改资源中心链接
export function updateResourceLink(data) {
  return request({
    url: '/action/admin/resource-link',
    method: 'put',
    data: data
  })
}

// 删除资源中心链接
export function delResourceLink(linkId) {
  return request({
    url: '/action/admin/resource-link/' + linkId,
    method: 'delete'
  })
}
