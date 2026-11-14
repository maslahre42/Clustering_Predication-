const osmAttribution = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

/** MapTiler's OMT cartography is selected by provider style, without CSS filtering. */
export function mapBasemap(apiKey?: string) {
  const key = apiKey?.trim()
  if (!key) return {
    provider: 'OpenStreetMap',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: osmAttribution, maxZoom: 19,
  }
  return {
    provider: 'MapTiler OMT',
    url: `https://api.maptiler.com/maps/openstreetmap/256/{z}/{x}/{y}{r}.png?key=${encodeURIComponent(key)}`,
    attribution: `&copy; <a href="https://www.maptiler.com/copyright/">MapTiler</a>, ${osmAttribution}`,
    maxZoom: 20,
  }
}
