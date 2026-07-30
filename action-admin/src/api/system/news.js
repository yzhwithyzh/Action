import request from '@/utils/request'

// 查询官网新闻列表
export function listNews(query) {
  return request({
    url: '/action/admin/news/list',
    method: 'get',
    params: query
  })
}

// 查询官网新闻详细
export function getNews(newsId) {
  return request({
    url: '/action/admin/news/' + newsId,
    method: 'get'
  })
}

// 新增官网新闻
export function addNews(data) {
  return request({
    url: '/action/admin/news',
    method: 'post',
    data: data
  })
}

// 修改官网新闻
export function updateNews(data) {
  return request({
    url: '/action/admin/news',
    method: 'put',
    data: data
  })
}

// 删除官网新闻
export function delNews(newsId) {
  return request({
    url: '/action/admin/news/' + newsId,
    method: 'delete'
  })
}
