import test from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdtempSync, writeFileSync, readFileSync, mkdirSync, rmSync, existsSync } from 'node:fs'
import { tmpdir, EOL } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../', import.meta.url))
const makefile = join(root, 'Makefile')

function fixture(t) {
  const directory = mkdtempSync(join(tmpdir(), 'garbage-collector-make-'))
  t.after(() => rmSync(directory, { recursive: true, force: true }))
  const log = join(directory, 'commands.jsonl')
  const overrides = {}
  for (const tool of ['dotnet', 'pnpm', 'aspire', 'python']) {
    const executable = join(directory, `${tool} tool`)
    writeFileSync(executable, `#!/usr/bin/env node
import { appendFileSync } from 'node:fs';
import { EOL } from 'node:os';
const args = process.argv.slice(2);
appendFileSync(process.env.GC_MAKE_TEST_LOG, JSON.stringify({ tool: ${JSON.stringify(tool)}, args }) + EOL);
if (process.env.GC_MAKE_FAIL_TOOL === ${JSON.stringify(tool)} && process.env.GC_MAKE_FAIL_COMMAND === args[0]) process.exit(17);
`, { mode: 0o755 })
    overrides[tool === 'python' ? 'PYTHON' : tool.toUpperCase()] = executable
  }
  function run(target, options = {}) {
    const result = spawnSync('make', ['--no-print-directory', '-f', makefile, ...Object.entries(overrides).map(([key, value]) => `${key}=${value}`), ...(target ? [target] : []), ...(options.args ?? [])], {
      cwd: options.cwd ?? root,
      env: { ...process.env, GC_MAKE_TEST_LOG: log, ...options.env }, encoding: 'utf8',
    })
    assert.ifError(result.error)
    return result
  }
  function commands() {
    return existsSync(log) ? readFileSync(log, 'utf8').trim().split(EOL).filter(Boolean).map(line => JSON.parse(line)) : []
  }
  return { directory, run, commands }
}

test('default make command lists help without invoking application tools', t => {
  const f = fixture(t), result = f.run()
  assert.equal(result.status, 0, result.stderr)
  assert.match(result.stdout, /make setup/)
  assert.match(result.stdout, /make run/)
  assert.match(result.stdout, /make test/)
  assert.deepEqual(f.commands(), [])
})

test('setup restores the solution and uses pnpm frozen dependencies', t => {
  const f = fixture(t), result = f.run('setup')
  assert.equal(result.status, 0, result.stderr)
  assert.deepEqual(f.commands(), [
    { tool: 'dotnet', args: ['restore', 'GarbageCollector.slnx', '--disable-parallel'] },
    { tool: 'pnpm', args: ['--dir', 'apps/web', 'install', '--frozen-lockfile'] },
  ])
})

test('dev starts Aspire once and separate-server targets use the correct tools', t => {
  const f = fixture(t)
  for (const target of ['dev', 'api', 'web']) assert.equal(f.run(target).status, 0)
  assert.deepEqual(f.commands(), [
    { tool: 'dotnet', args: ['run', '--project', 'apps/apphost'] },
    { tool: 'dotnet', args: ['run', '--project', 'apps/api'] },
    { tool: 'pnpm', args: ['--dir', 'apps/web', 'dev'] },
  ])
})

test('combined tests honor configuration and run the in-process backend runner before frontend tests', t => {
  const f = fixture(t), result = f.run('test', { args: ['CONFIGURATION=Release', '-j4'] })
  assert.equal(result.status, 0, result.stderr)
  const commands = f.commands()
  assert.equal(commands.length, 3)
  assert.equal(commands[0].tool, 'dotnet')
  assert.equal(commands[0].args[0], 'build')
  assert.equal(commands[0].args[commands[0].args.indexOf('--configuration') + 1], 'Release')
  assert.deepEqual(commands[1], { tool: 'dotnet', args: ['tests/GarbageCollector.TestRunner/bin/Release/net10.0/GarbageCollector.TestRunner.dll'] })
  assert.deepEqual(commands[2], { tool: 'pnpm', args: ['--dir', 'apps/web', 'test'] })
})

test('backend build failure stops the test workflow before any runner or frontend command', t => {
  const f = fixture(t), result = f.run('test', { env: { GC_MAKE_FAIL_TOOL: 'dotnet', GC_MAKE_FAIL_COMMAND: 'build' } })
  assert.notEqual(result.status, 0)
  assert.equal(f.commands().length, 1)
})

test('check runs tests, type checking and builds in order without publishing', t => {
  const f = fixture(t), result = f.run('check')
  assert.equal(result.status, 0, result.stderr)
  assert.deepEqual(f.commands().map(({ tool, args }) => [tool, args[0]]), [
    ['dotnet', 'build'], ['dotnet', 'tests/GarbageCollector.TestRunner/bin/Debug/net10.0/GarbageCollector.TestRunner.dll'],
    ['pnpm', '--dir'], ['pnpm', '--dir'], ['dotnet', 'build'], ['pnpm', '--dir'],
  ])
  assert.deepEqual(f.commands().filter(command => command.tool === 'pnpm').map(command => command.args.at(-1)), ['test', 'typecheck', 'build'])
})

test('Compose publishing and deployment stay separate and preserve output paths with spaces', t => {
  const f = fixture(t)
  for (const target of ['compose', 'deploy']) assert.equal(f.run(target, { args: ['ENVIRONMENT=Staging', 'OUTPUT_DIR=output directory'] }).status, 0)
  assert.deepEqual(f.commands().map(command => command.args), ['publish', 'deploy'].map(command => [command,
    '--apphost', 'apps/apphost/GarbageCollector.AppHost.csproj', '--environment', 'Staging', '-o', 'output directory',
  ]))
})

test('clean removes generated outputs and dependencies while preserving source and deployment data', t => {
  const f = fixture(t)
  const generated = ['apps/web/.nuxt', 'apps/web/.output', 'apps/web/node_modules', '.mypy_cache', '.pnpm-store']
  for (const project of ['apps/api', 'apps/apphost', 'tests/GarbageCollector.Api.Tests', 'tests/GarbageCollector.AppHost.Tests', 'tests/GarbageCollector.TestRunner']) {
    for (const output of ['bin', 'obj']) generated.push(`${project}/${output}`)
  }
  for (const path of generated) {
    mkdirSync(join(f.directory, path), { recursive: true })
    writeFileSync(join(f.directory, path, 'generated-file'), 'generated')
  }
  const preserved = ['sql.db', 'sql.before-locations.db', 'apps/api/Program.cs', 'apps/web/pnpm-lock.yaml', 'idea of UI:UX/screen.png', 'aspire-output/.env', 'aspire-output/docker-compose.yaml', '.git/.DS_Store']
  for (const path of preserved) {
    mkdirSync(join(f.directory, path, '..'), { recursive: true })
    writeFileSync(join(f.directory, path), 'preserved')
  }
  for (const path of ['.DS_Store', 'apps/web/.DS_Store']) writeFileSync(join(f.directory, path), 'metadata')
  const result = f.run('clean', { cwd: f.directory })
  assert.equal(result.status, 0, result.stderr)
  for (const path of [...generated, '.DS_Store', 'apps/web/.DS_Store']) assert.equal(existsSync(join(f.directory, path)), false, path)
  for (const path of preserved) assert.equal(readFileSync(join(f.directory, path), 'utf8'), 'preserved', path)
  assert.deepEqual(f.commands(), [])
  assert.equal(f.run('clean', { cwd: f.directory }).status, 0, 'clean can run twice without installed tools or outputs')
})
