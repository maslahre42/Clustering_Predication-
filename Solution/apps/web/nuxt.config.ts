export default defineNuxtConfig({
  compatibilityDate: '2026-11-13',
  components: [
    { path: '~/components', pathPrefix: false },
    { path: '~/shared/ui', pathPrefix: false },
    ...['planning', 'history', 'inventory', 'map', 'manifest', 'analytics', 'system'].map(feature => ({
      path: `~/features/${feature}/components`, pathPrefix: false,
    })),
  ],
  css: ['leaflet/dist/leaflet.css', '~/assets/main.css'],
  runtimeConfig: {
    apiBase: 'http://localhost:5080',
    public: { maptilerApiKey: '' },
  },
  app: {
    head: {
      title: 'Garbage Collector',
      meta: [{ name: 'description', content: 'Glass collection history in Heilbronn' }],
      link: [{ rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }],
    },
  },
  devtools: { enabled: false },
})
