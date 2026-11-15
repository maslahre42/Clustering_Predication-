import { createRequire } from 'node:module'
import { readFile, writeFile, mkdir } from 'node:fs/promises'

const require = createRequire(new URL('../../apps/web/package.json', import.meta.url))
const { parse, compileScript } = require('vue/compiler-sfc')
const { transpileModule, ModuleKind, ScriptTarget } = require('typescript')
const { createRenderer, h, nextTick, ref } = require('vue')
export { h, nextTick, ref }

const appRoot = new URL('../../apps/web/app/', import.meta.url)
// Node runs test files in separate processes. Shared output names can be read mid-write by another process.
const output = new URL(`../../apps/web/.nuxt/component-tests/${process.pid}/`, import.meta.url)
const components = {
  LocationClusterList: 'features/planning/components/LocationClusterList.vue',
  PlanningFillMeter: 'features/planning/components/PlanningFillMeter.vue',
  PlanningFilters: 'features/planning/components/PlanningFilters.vue',
  HistoricalFillMeter: 'shared/ui/HistoricalFillMeter.vue',
  CollectionDatePicker: 'shared/ui/CollectionDatePicker.vue',
  HistoryTable: 'features/history/components/HistoryTable.vue',
  MonthlyCollectionTable: 'features/analytics/components/MonthlyCollectionTable.vue',
  MaterialAnalyticsTable: 'features/analytics/components/MaterialAnalyticsTable.vue',
  CollectionPatternTrends: 'features/analytics/components/CollectionPatternTrends.vue',
  CollectionDynamicsPanel: 'features/analytics/components/CollectionDynamicsPanel.vue',
  CollectionPatternEvidence: 'features/analytics/components/CollectionPatternEvidence.vue',
  OperatingCosts: 'features/proposal/components/OperatingCosts.vue',
  FillTimingTable: 'features/proposal/components/FillTimingTable.vue',
  ScenarioComparison: 'features/proposal/components/ScenarioComparison.vue',
  PlanPresentation: 'features/proposal/components/PlanPresentation.vue',
  ProposalRoutesTable: 'features/proposal/components/ProposalRoutesTable.vue',
  ProposalRouteMap: 'features/proposal/components/ProposalRouteMap.vue',
  ProposalSettingsForm: 'features/proposal/components/ProposalSettingsForm.vue',
  ForecastAnalysis: 'features/proposal/components/ForecastAnalysis.vue',
  ForecastExplorer: 'features/proposal/components/ForecastExplorer.vue',
  SimulationResults: 'features/proposal/components/SimulationResults.vue',
  ProjectValidationResults: 'features/proposal/components/ProjectValidationResults.vue',
  ProposalDataEvidence: 'features/proposal/components/ProposalDataEvidence.vue',
  CapacityPlanning: 'features/proposal/components/CapacityPlanning.vue',
  CapacityResults: 'features/proposal/components/CapacityResults.vue',
  JointPlanningResults: 'features/proposal/components/JointPlanningResults.vue',
}

/** Compile actual components. Resolve runtime imports against their original source. */
export async function component(name) {
  const sourceUrl = new URL(components[name] ?? `shared/ui/controls/${name}.vue`, appRoot)
  const source = await readFile(sourceUrl, 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: name, inlineTemplate: true })
  const compiled = transpileModule(script.content, {
    compilerOptions: { module: ModuleKind.ESNext, target: ScriptTarget.ES2022 },
  }).outputText
  const resolved = compiled.replace(/from (['"])([^'"]+)\1/g, (match, quote, specifier) => {
    if (!specifier.startsWith('.') && !specifier.startsWith('~/')) return match
    const target = specifier.startsWith('~/')
      ? new URL(specifier.slice(2), appRoot)
      : new URL(specifier, sourceUrl)
    if (!/\.(ts|mjs|js)$/.test(target.pathname)) target.pathname += '.ts'
    return `from ${JSON.stringify(target.href)}`
  })
  await mkdir(output, { recursive: true })
  const target = new URL(`${name}.mjs`, output)
  await writeFile(target, resolved)
  return (await import(target.href)).default
}

export function descendants(n) { return [n, ...n.children.flatMap(descendants)] }
const node = (tag, text = '') => ({
  tag, text, props: {}, children: [], parent: null, focused: false,
  listeners: {},
  addEventListener(event, handler) { (this.listeners[event] ??= []).push(handler) },
  removeEventListener(event, handler) { this.listeners[event] = (this.listeners[event] ?? []).filter(value => value !== handler) },
  focus() { this.focused = true },
  querySelector(selector) {
    const date = selector.match(/data-date="([^"]+)"/)
    return descendants(this).find(n => date ? n.props['data-date'] === date[1] : n.tag === selector)
  },
})
const renderer = createRenderer({
  createElement: tag => node(tag), createText: text => node('#text', text), createComment: text => node('#comment', text),
  setText: (n, text) => { n.text = text }, setElementText: (n, text) => { n.text = text; n.children = [] },
  patchProp: (n, key, old, value) => { n.props[key] = value },
  insert: (child, parent, anchor) => {
    if (child.parent) child.parent.children.splice(child.parent.children.indexOf(child), 1)
    child.parent = parent
    const index = anchor ? parent.children.indexOf(anchor) : -1
    parent.children.splice(index < 0 ? parent.children.length : index, 0, child)
  },
  remove: child => { if (child.parent) child.parent.children.splice(child.parent.children.indexOf(child), 1) },
  parentNode: child => child.parent, nextSibling: child => child.parent?.children[child.parent.children.indexOf(child) + 1],
  insertStaticContent: (text, parent) => { const n = node('#static', text); n.parent = parent; parent.children.push(n); return [n, n] },
})
export function mount(t, Component, props = {}, slots, components = {}) {
  const root = node('root'), changes = [], applied = []
  const app = renderer.createApp({ render: () => h(Component, { ...props, 'onUpdate:modelValue': value => changes.push(value), onApply: value => applied.push(value) }, slots) })
  for (const [name, control] of Object.entries(components)) app.component(name, control)
  app.mount(root)
  t.after(() => app.unmount())
  const all = n => [n, ...n.children.flatMap(all)]
  return { root, changes, applied, all: () => all(root), find: tag => all(root).find(n => n.tag === tag), text: () => all(root).filter(n => n.tag !== '#comment').map(n => n.text).join(' ') }
}
