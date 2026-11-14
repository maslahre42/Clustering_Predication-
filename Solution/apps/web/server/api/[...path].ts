import { API_ROUTES } from '../../app/shared/api/routes'

export default defineEventHandler((event) => {
  const path = getRouterParam(event, 'path') || ''
  if (!Object.keys(API_ROUTES).includes(path)) throw createError({ statusCode: 404 })
  if (event.method !== 'GET' && !(event.method === 'POST' && ['proposal', 'forecast', 'simulation'].includes(path))) throw createError({ statusCode: 405 })
  const base = useRuntimeConfig(event).apiBase
  return proxyRequest(event, `${base}/api/${path}${getRequestURL(event).search}`)
})
