import test from 'node:test'
import assert from 'node:assert/strict'
import { mapBasemap } from '../apps/web/app/features/map/basemap.ts'

test('missing MapTiler credentials keep normal OSM usable without unauthenticated provider requests', () => {
  for (const key of [undefined, '', '  ']) {
    const map = mapBasemap(key)
    assert.equal(map.provider, 'OpenStreetMap')
    assert.equal(map.url, 'https://tile.openstreetmap.org/{z}/{x}/{y}.png')
  }
})

test('configured MapTiler OMT uses its normal OpenStreetMap tiles', () => {
  const map = mapBasemap(' test-key ')
  assert.equal(map.provider, 'MapTiler OMT')
  assert.equal(map.url, 'https://api.maptiler.com/maps/openstreetmap/256/{z}/{x}/{y}{r}.png?key=test-key')
  assert.match(map.attribution, /MapTiler/)
  assert.match(map.attribution, /OpenStreetMap/)
})

test('MapTiler OMT retains provider and underlying map-data attribution', () => {
  const map = mapBasemap('key')
  assert.match(map.attribution, /https:\/\/www.maptiler.com\/copyright\//)
  assert.match(map.attribution, /https:\/\/www.openstreetmap.org\/copyright/)
  assert.doesNotMatch(map.url, /dark/)
})

test('MapTiler keys are encoded as one query value', () => {
  assert.ok(mapBasemap('key&extra=1').url.endsWith('?key=key%26extra%3D1'))
})
