<script setup lang="ts">
const { asOf } = useWorkspaceData();
const { view } = useWorkspaceNavigation();
</script>
<template>
  <div class="page-body">
    <header class="section-title">
      <div>
        <p class="eyebrow">PREDICTIVE FORECASTS</p>
        <h1>A home for future forecasts.</h1>
        <p>Historical baseline: {{ asOf }}</p>
      </div>
    </header>
    <UiCard class="integration-panel">
      <GlassFractionBadge material="brown" />
      <GlassFractionBadge material="green" />
      <GlassFractionBadge material="white" />
      <h2>Forecast model not connected</h2>
      <p>Your colleague’s model will provide predicted fill levels. Until that integration is ready, this application shows actual collection records only.</p>
      <dl>
        <dt>Bin identity</dt>
        <dd>Location UUID + glass color</dd>
        <dt>Required forecast fields</dt>
        <dd>Target date, predicted fill, generation date</dd>
        <dt>Historical replay</dt>
        <dd>Training inputs and forecast generation must respect the chosen cutoff</dd>
      </dl>
      <UiButton label="Review historical records" @click="view = 'history'" />
    </UiCard>
  </div>
</template>
