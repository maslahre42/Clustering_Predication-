<script setup lang="ts">
import { toRef } from 'vue';
import type { CollectionProposal } from '~/shared/api/contracts/proposal';
import type { Location } from '~/shared/api/contracts/locations';
import { formatHours, formatRisk } from '../domain/proposal';
import { createRouteMapState } from '../state/createRouteMapState';
const props = withDefaults(defineProps<{ proposal: CollectionProposal; locations?: Location[] }>(), { locations: () => [] });
const state = createRouteMapState(toRef(props, 'proposal'), toRef(props, 'locations'));
const { model, selectedTruck, selectedLoad, selectedStop, showUnserved, expanded, fitVersion,
  visibleTrucks, stops, activeStop, missing, provenance, loads } = state;
</script>
<template>
  <section v-if="model.trucks.length" class="proposal-map-panel" :class="{ 'proposal-map-expanded': expanded }" aria-label="Optimized collection route map">
    <div class="proposal-map-heading">
      <div><p class="eyebrow">YOUR FLEET, ON THE MAP</p><h3>Follow the collection route</h3><p>{{ proposal.planDate }} · {{ provenance }}</p></div>
      <div class="proposal-map-actions"><UiButton label="Fit routes" mode="outline" @click="state.fit" /><UiButton :label="expanded ? 'Compact map' : 'Expand map'" mode="outline" @click="expanded = !expanded" /></div>
    </div>
    <p class="proposal-map-routing-mode">Street routing · {{ proposal.plan.totals.distanceKm?.toFixed(1) ?? '—' }} km · compact service sectors · unloading between loads, yard return at the end.</p>
    <div class="proposal-map-trucks" role="group" aria-label="Show routes by truck">
      <button type="button" :aria-pressed="selectedTruck == null" class="proposal-map-truck" @click="state.selectTruck(null)"><strong>All trucks</strong><span>{{ model.trucks.length }} vehicles · {{ proposal.plan.totals.stops }} stops</span></button>
      <button v-for="truck in model.trucks" :key="truck.truck" type="button" :aria-pressed="selectedTruck === truck.truck" class="proposal-map-truck" :style="{ '--truck-color': truck.color }" @click="state.selectTruck(truck.truck)">
        <strong><i aria-hidden="true" />Truck {{ truck.truck }}<small v-if="truck.territory"> · {{ truck.territory }}</small></strong><span>{{ truck.stopCount }} stops · {{ truck.loads }} loads · {{ formatHours(truck.hours) }}</span>
      </button>
    </div>
    <div class="proposal-map-toolbar">
      <UiSelect v-if="selectedTruck != null" v-model="selectedLoad" label="Map load" :options="loads" :allow-empty="false" />
      <UiCheckbox v-model="showUnserved" label="Show unserved stops" />
      <span><b class="proposal-map-yard-key">Y</b> Yard <b class="proposal-map-unload-key">U</b> Unloading <b class="proposal-map-stop-key">1</b> Collection order</span>
    </div>
    <div class="proposal-map-layout">
      <div class="proposal-map-canvas">
        <ClientOnly>
          <ProposalLeafletMap :trucks="visibleTrucks" :yard="model.yard" :disposal="model.disposal" :unserved="showUnserved ? model.unserved : []" :active-stop="activeStop" :fit-version="fitVersion" @select="selectedStop = $event" />
          <template #fallback><div class="proposal-map-loading" role="status">Loading OpenStreetMap…</div></template>
        </ClientOnly>
      </div>
      <aside class="proposal-map-itinerary" aria-label="Mapped route itinerary">
        <div class="proposal-map-itinerary-heading"><h4>{{ selectedTruck == null ? 'Collection sequence' : `Truck ${selectedTruck} itinerary` }}</h4><p>Choose a numbered stop to inspect it.</p></div>
        <p v-if="!stops.length" class="proposal-map-empty">No collection stops in this selection have valid coordinates. The route table below retains the complete plan.</p>
        <template v-for="truck in visibleTrucks" :key="truck.truck">
          <div class="proposal-map-itinerary-truck" :style="{ color: truck.color }">Truck {{ truck.truck }} · {{ (truck.weightKg / 1000).toFixed(1) }} t total</div>
          <p class="proposal-map-endpoint">{{ selectedLoad && selectedLoad !== '1' ? 'U · Start after unloading' : 'Y · Depart yard' }}</p>
          <template v-for="(stop, index) in truck.stops" :key="stop.key">
            <p v-if="index === 0 || truck.stops[index - 1]?.load !== stop.load" class="proposal-map-load">Load {{ stop.load }}</p>
            <button class="proposal-map-stop" type="button" :aria-pressed="selectedStop === stop.key" :aria-label="`Truck ${stop.truck}, stop ${stop.sequence}, location ${stop.locationId}`" @click="selectedStop = stop.key">
              <span class="proposal-map-stop-number" :style="{ background: stop.color }">{{ stop.sequence }}</span>
              <span><strong>Location {{ stop.locationId.slice(0, 8) }}</strong><small>{{ stop.materials.join(' · ') }} · {{ Math.round(stop.weightKg) }} kg</small><small>{{ stop.mandatory ? 'Must empty' : 'If time allows' }} · {{ formatRisk(stop.risk) }} risk</small></span>
            </button>
            <p v-if="index === truck.stops.length - 1 || truck.stops[index + 1]?.load !== stop.load" class="proposal-map-endpoint">U · Unload {{ stop.load }}</p>
          </template>
          <p v-if="!selectedLoad || Number(selectedLoad) === truck.loads" class="proposal-map-endpoint">Y · Return to yard</p>
        </template>
      </aside>
    </div>
    <div v-if="activeStop" class="proposal-map-inspection" role="status"><strong>Truck {{ activeStop.truck }} · Load {{ activeStop.load }} · Stop {{ activeStop.sequence }}</strong><span>{{ activeStop.locationId }}</span><span>{{ activeStop.provenance }} coordinates · {{ activeStop.latitude.toFixed(5) }}, {{ activeStop.longitude.toFixed(5) }}</span></div>
    <p v-if="missing" class="proposal-map-missing" role="status">{{ missing }} stops across the selected trucks have missing or invalid coordinates. Their positions are omitted and route lines break at those stops.</p>
    <p v-if="visibleTrucks.some(truck => !truck.paths.length)" class="proposal-map-missing" role="status">Street geometry is missing for this selection. Recalculate the proposal; no straight-line route is drawn.</p>
    <p class="proposal-map-disclaimer">Road geometry and driving costs: OSRM / OpenStreetMap, car profile. No flying-distance fallback. Car routes do not establish truck-specific access, height or weight permissions. Site assignments may be synthetic; yard and unloading positions remain configured assumptions.</p>
  </section>
</template>
