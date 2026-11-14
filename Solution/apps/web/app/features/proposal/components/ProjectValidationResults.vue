<script setup lang="ts">
import type { ForecastComparison, OptimizationCheck } from '~/shared/api/contracts/comparison';
defineProps<{ comparison: ForecastComparison; optimization: OptimizationCheck }>();
const score = (value: number | null) => value == null ? 'Not enough common cases' : value.toFixed(2);
</script>
<template>
  <section class="analytics-panel surface">
    <h3>Three-project forecast comparison on real observations</h3>
    <p>{{ comparison.targets }} eligible targets · {{ comparison.commonNumericCases }} shared uncensored numeric cases · {{ comparison.commonCensoredCases }} shared lower-bound cases · {{ comparison.unknownTargets }} unknown targets.</p>
    <div class="table-scroll"><table><thead><tr><th>Forecast</th><th>Available cases</th><th>Mean absolute error (pp)</th><th>Bias (pp)</th><th>Lower-bound shortfall (pp)</th></tr></thead><tbody>
      <tr v-for="model in comparison.models" :key="model.name"><td>{{ model.label }}</td><td>{{ model.available }} / {{ comparison.evaluated }}</td><td>{{ score(model.mae) }}</td><td>{{ score(model.bias) }}</td><td>{{ score(model.lowerBoundShortfall) }}</td></tr>
    </tbody></table></div>
    <p>{{ comparison.note }}</p>
    <h3>Zakaria’s independent optimization check</h3>
    <p>{{ optimization.date }} · {{ optimization.sites.length }} sampled sites · <strong>{{ optimization.status }}</strong>. {{ optimization.message }}</p>
    <p v-if="optimization.trucks != null">{{ optimization.trucks }} one-load trucks scheduled; capacity lower bound {{ optimization.fleetLowerBound }}.</p>
    <table v-if="optimization.routes?.length"><thead><tr><th>Truck</th><th>Sites in order</th><th>Weight</th><th>Volume</th><th>Hours</th></tr></thead><tbody>
      <tr v-for="route in optimization.routes" :key="route.truck"><td>{{ route.truck }}</td><td>{{ route.sites.join(' → ') }}</td><td>{{ route.weightKg.toFixed(0) }} kg</td><td>{{ route.volumeM3.toFixed(1) }} m³</td><td>{{ route.hours.toFixed(2) }}</td></tr>
    </tbody></table>
    <p>{{ optimization.note }}</p>
  </section>
</template>
