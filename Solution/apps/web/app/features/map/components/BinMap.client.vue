<script setup lang="ts">
import L from 'leaflet';
import type { Location } from '~/shared/api/contracts/locations';
import type { Point } from '~/shared/domain/geometry';
import { DEFAULT_WORKSPACE } from '~/shared/config/workspace';
import { coordinateSourceLabel } from '~/shared/domain/coordinates';
import { mapBasemap } from '../basemap';
const config = useRuntimeConfig();
const basemap = mapBasemap(config.public.maptilerApiKey);
const props = defineProps<{
    locations: Location[];
    selected: string;
    route?: Point[];
}>();
const emit = defineEmits<{
    select: [
        id: string
    ];
}>();
const host = ref<HTMLElement>();
let map: L.Map | undefined;
let markers: L.LayerGroup | undefined;
let routeLayer: L.LayerGroup | undefined;
let resizeObserver: ResizeObserver | undefined;
let tiles: L.TileLayer | undefined;
const tilesUnavailable = ref(false);
function draw() {
    if (!map || !markers)
        return;
    markers.clearLayers();
    routeLayer?.clearLayers();
    if (props.route?.length && routeLayer) {
        const line = L.polyline(props.route.map(p => [p.latitude, p.longitude] as [
            number,
            number
        ]), { color: '#087f48', weight: 3, dashArray: '7 7' }).addTo(routeLayer);
        props.route.slice(0, -1).forEach((p, i) => L.marker([p.latitude, p.longitude], {
            icon: L.divIcon({ className: 'route-marker', html: `<span>${i === 0 ? 'D' : i}</span>`, iconSize: [30, 30], iconAnchor: [15, 15] }),
        }).addTo(routeLayer!));
        map.fitBounds(line.getBounds(), { padding: [35, 35], maxZoom: 15 });
    }
    if (!props.route?.length && props.selected) {
        const selected = props.locations.find(l => l.locationId === props.selected);
        if (selected)
            map.setView([selected.latitude, selected.longitude], 15);
    }
    for (const location of props.locations) {
        L.circleMarker([location.latitude, location.longitude], {
            radius: location.locationId === props.selected ? 9 : 5,
            color: location.locationId === props.selected ? '#b45309' : '#16735a',
            fillOpacity: 0.8, weight: 2,
        }).bindTooltip(location.locationId).on('click', () => emit('select', location.locationId)).addTo(markers);
    }
}
onMounted(() => {
    map = L.map(host.value!).setView([DEFAULT_WORKSPACE.depot.latitude, DEFAULT_WORKSPACE.depot.longitude], 13);
    tiles = L.tileLayer(basemap.url, {
        attribution: basemap.attribution, maxZoom: basemap.maxZoom,
    }).addTo(map);
    tiles.on('tileerror', () => { tilesUnavailable.value = true; });
    tiles.on('tileload', () => { tilesUnavailable.value = false; });
    resizeObserver = new ResizeObserver(() => map?.invalidateSize());
    resizeObserver.observe(host.value!);
    markers = L.layerGroup().addTo(map);
    routeLayer = L.layerGroup().addTo(map);
    draw();
});
watch(() => [props.locations, props.selected, props.route], draw);
onBeforeUnmount(() => { resizeObserver?.disconnect(); map?.remove(); });
</script>
<template>
  <div class="map-wrapper">
    <div ref="host" class="map" :aria-label="`Map of bin locations in Heilbronn · ${basemap.provider} · ${coordinateSourceLabel(locations)}`" />
    <a v-if="basemap.provider === 'MapTiler OMT'" class="maptiler-logo" href="https://www.maptiler.com/" target="_blank" rel="noopener noreferrer" aria-label="MapTiler map provider">
      <img src="https://api.maptiler.com/resources/logo.svg" alt="MapTiler" width="100" height="25" />
    </a>
    <div v-if="tilesUnavailable" class="map-connection-warning" role="status">Map tiles are unavailable. Location markers and the route preview remain visible.</div>
  </div>
</template>
