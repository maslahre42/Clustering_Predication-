import { createRequire } from 'node:module'
import { readFile, writeFile, mkdir } from 'node:fs/promises'

const require = createRequire(new URL('../../apps/web/package.json', import.meta.url))
const { parse, compileScript } = require('vue/compiler-sfc')
const { transpileModule, ModuleKind, ScriptTarget } = require('typescript')
const { createRenderer, h, nextTick, ref } = require('vue')
export { h, nextTick, ref }

const appRoot = new URL('../../apps/web/app/', import.meta.url)
const output = new URL('../../apps/web/.nuxt/component-tests/', import.meta.url)
const components = {
  CollectionDatePicker: 'shared/ui/CollectionDatePicker.vue',
  HistoryTable: 'features/history/components/HistoryTable.vue',
  MonthlyCollectionTable: 'features/analytics/components/MonthlyCollectionTable.vue',
  MaterialAnalyticsTable: 'features/analytics/components/MaterialAnalyticsTable.vue',
  ProposalRoutesTable: 'features/proposal/components/ProposalRoutesTable.vue',
  ProposalSettingsForm: 'features/proposal/components/ProposalSettingsForm.vue',
  ForecastExplorer: 'features/proposal/components/ForecastExplorer.vue',
  SimulationResults: 'features/proposal/components/SimulationResults.vue',
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
