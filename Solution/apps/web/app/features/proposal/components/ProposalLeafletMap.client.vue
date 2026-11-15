<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import L from 'leaflet';
import type { MapPoint, MapTruck, RouteMapModel, RouteMapStop } from '../domain/routeMap';
import { mapBasemap } from '~/features/map/basemap';
const props = defineProps<{ trucks: MapTruck[]; yard: MapPoint | null; disposal: MapPoint | null;
  unserved: RouteMapModel['unserved']; activeStop: RouteMapStop | null; fitVersion: number }>();
const emit = defineEmits<{ select: [key: string] }>();
const basemap = mapBasemap(useRuntimeConfig().public.maptilerApiKey);
const host = ref<HTMLElement>();
const tilesUnavailable = ref(false);
let map: L.Map | undefined, layer: L.LayerGroup | undefined, observer: ResizeObserver | undefined;
const markers = new Map<string, L.Marker>();
const latLng = (point: MapPoint): L.LatLngTuple => [point.latitude, point.longitude];

function icon(text: string, color: string, endpoint = false) {
  const element = document.createElement('span');
  element.textContent = text; element.style.backgroundColor = color;
  return L.divIcon({ className: endpoint ? 'proposal-leaflet-pin proposal-leaflet-endpoint' : 'proposal-leaflet-pin',
    html: element, iconSize: [32, 32], iconAnchor: [16, 16], popupAnchor: [0, -18] });
}
function popup(title: string, detail: string) {
  const content = document.createElement('div'), heading = document.createElement('strong'), body = document.createElement('p');
  heading.textContent = title; body.textContent = detail; content.append(heading, body); return content;
}
function fit() {
  if (!map) return;
  const points = props.trucks.flatMap(truck => truck.paths.flatMap(path => path.points)).map(latLng);
  props.trucks.forEach(truck => truck.stops.forEach(stop => points.push(latLng(stop))));
  props.unserved.forEach(stop => points.push(latLng(stop)));
  if (props.yard) points.push(latLng(props.yard));
  if (props.disposal) points.push(latLng(props.disposal));
  if (points.length) map.fitBounds(L.latLngBounds(points), { padding: [40, 40], maxZoom: 15, animate: false });
}
function focus() {
  if (!map || !props.activeStop) return;
  map.setView(latLng(props.activeStop), Math.max(map.getZoom(), 15), { animate: false });
  markers.get(props.activeStop.key)?.openPopup();
}
function draw() {
  if (!map || !layer) return;
  layer.clearLayers(); markers.clear();
  for (const truck of props.trucks) {
    for (const path of truck.paths) {
      const points = path.points.map(latLng);
      L.polyline(points, { color: '#ffffff', weight: 8, opacity: 0.9, interactive: false }).addTo(layer);
      L.polyline(points, { color: truck.color, weight: path.returning ? 3 : 4, opacity: path.returning ? 0.65 : 0.9,
        dashArray: path.returning ? '3 9' : undefined }).bindTooltip(`Truck ${truck.truck} · ${path.returning ? 'Return to yard' : `Load ${path.load}`}`).addTo(layer);
    }
    for (const stop of truck.stops) {
      const marker = L.marker(latLng(stop), { icon: icon(String(stop.sequence), truck.color),
        title: `Truck ${truck.truck}, stop ${stop.sequence}, location ${stop.locationId}`,
        alt: `Truck ${truck.truck}, stop ${stop.sequence}, location ${stop.locationId}`, keyboard: true })
        .bindPopup(popup(`Truck ${truck.truck} · Load ${stop.load} · Stop ${stop.sequence}`,
          `${stop.locationId} · ${stop.materials.join(', ')} · ${Math.round(stop.weightKg)} kg forecast · ${stop.provenance} coordinates`))
        .on('click', () => emit('select', stop.key)).addTo(layer);
      markers.set(stop.key, marker);
    }
  }
  for (const item of props.unserved) {
    L.circleMarker(latLng(item), { radius: 8, color: item.mandatory ? '#c34242' : '#66756f', weight: 2,
      dashArray: '3 3', fillOpacity: 0.1 }).bindPopup(popup(`Unserved · ${item.locationId}`, item.reason)).addTo(layer);
  }
  if (props.yard) L.marker(latLng(props.yard), { icon: icon('Y', '#223d35', true), zIndexOffset: 500, title: 'Configured yard', alt: 'Configured yard' })
    .bindPopup(popup('Yard · start and finish', 'Configured location; verify before dispatch.')).addTo(layer);
  if (props.disposal) L.marker(latLng(props.disposal), { icon: icon('U', '#b36820', true), zIndexOffset: 500, title: 'Configured unloading site', alt: 'Configured unloading site' })
    .bindPopup(popup('Unloading site', 'Trucks unload between loads and before returning to the yard.')).addTo(layer);
  fit(); focus();
}
onMounted(() => {
  map = L.map(host.value!, { scrollWheelZoom: false, zoomAnimation: false }).setView([49.0094, 8.4044], 12);
  L.tileLayer(basemap.url, { attribution: basemap.attribution, maxZoom: basemap.maxZoom }).addTo(map)
    .on('tileerror', () => { tilesUnavailable.value = true })
    .on('tileload', () => { tilesUnavailable.value = false });
  layer = L.layerGroup().addTo(map);
  observer = new ResizeObserver(() => map?.invalidateSize()); observer.observe(host.value!);
  draw();
});
watch(() => [props.trucks, props.yard, props.disposal, props.unserved], draw);
watch(() => props.fitVersion, fit);
watch(() => props.activeStop, focus);
onBeforeUnmount(() => { observer?.disconnect(); markers.clear(); const previous = map; map = undefined; previous?.stop(); previous?.remove(); });
</script>
<template>
  <div class="proposal-leaflet-wrapper">
    <div ref="host" class="proposal-leaflet-map" role="region" :aria-label="`Optimized truck routes · ${basemap.provider} · car street geometry from OSRM`" />
    <a v-if="basemap.provider === 'MapTiler OMT'" class="maptiler-logo" href="https://www.maptiler.com/" target="_blank" rel="noopener noreferrer" aria-label="MapTiler map provider"><img src="https://api.maptiler.com/resources/logo.svg" alt="MapTiler" width="100" height="25" /></a>
    <p v-if="tilesUnavailable" class="map-connection-warning" role="status">Map tiles are unavailable. Truck routes and markers remain visible.</p>
  </div>
</template>
