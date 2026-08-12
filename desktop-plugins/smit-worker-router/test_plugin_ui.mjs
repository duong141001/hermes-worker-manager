import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const source = readFileSync(new URL('./plugin.js', import.meta.url), 'utf8')

test('offers Auto and the shared Hermes reasoning scale', () => {
  assert.match(source, /\['auto', 'Auto'\]/)
  assert.match(source, /REASONING_EFFORTS\.map/)
  assert.match(source, /reasoningEffortLabel/)
})

test('handoff language offers Auto Random and all fixed locales', () => {
  assert.match(source, /\['auto', 'Auto \(Random\)'\]/)
  assert.match(source, /\['en', 'English'\]/)
  assert.match(source, /\['fr', 'Français'\]/)
  assert.match(source, /\['ru', 'Русский'\]/)
})



test('each model has its own effort and fast preset', () => {
  assert.match(source, /ctxStorage\.get\('model_presets', \{\}\)/)
  assert.match(source, /\[presetKey\(next\.provider, next\.model\)\]: \{/)
  assert.match(source, /presetFor: \(rowProvider, rowModel\) => modelPresets\[presetKey\(rowProvider, rowModel\)\] \|\| \{\}/)
  assert.match(source, /applyPreset:/)
  assert.match(source, /reasoningEffortLabel\(reasoning\)/)
})

test('worker activity mounts only for active rows and shows task label', () => {
  assert.match(source, /function WorkerMonitor/)
  assert.match(source, /workerRows\.length \? workerRows\.map\(item => jsx\(ActivityRow/)
  assert.match(source, /item\.task_label \|\| t\('waiting'\)/)
  assert.doesNotMatch(source, /noWorkers/)
  assert.doesNotMatch(source, /status\.idle/)
  assert.doesNotMatch(source, /status\.failed/)
})

test('active worker uses a pulsing green dot and can show current tool', () => {
  assert.match(source, /ACTIVITY_DOT = 'animate-pulse bg-emerald-500'/)
  assert.match(source, /t\('usingTool', item\.current_tool\)/)
  assert.match(source, /item\.reasoning_effort \? reasoningEffortLabel/)
  assert.match(source, /item\.fast \? 'Fast'/)
  assert.match(source, /item\.locale \? `LOCALE \$\{item\.locale\}`/)
})

test('active worker shows compact real token, API call, and elapsed metadata including zero', () => {
  assert.match(source, /function UsageMeta\(\{ item, t, elapsed = false \}\)/)
  assert.match(source, /item\.input_tokens \?\? 0/)
  assert.match(source, /item\.output_tokens \?\? 0/)
  assert.match(source, /item\.total_tokens \?\? 0/)
  assert.match(source, /item\.api_calls \?\? 0/)
  assert.match(source, /font-mono text-\[10px\]/)
  assert.match(source, /jsx\(UsageMeta, \{ item, t, elapsed: true \}\)/)
})

test('duration formatter consumes API seconds without millisecond conversion', () => {
  assert.match(source, /function formatDuration\(secondsValue\)/)
  assert.match(source, /Math\.floor\(Number\(secondsValue\) \|\| 0\)/)
  assert.doesNotMatch(source, /Math\.floor\(\(Number\(secondsValue\) \|\| 0\) \/ 1000\)/)
})

test('active elapsed prefers the live duration_seconds counter before timestamp fallback', () => {
  assert.match(source, /const elapsedSeconds = item\.duration_seconds \?\? \(item\.started_at \? Math\.max\(0, \(Date\.now\(\) - Date\.parse\(item\.started_at\)\) \/ 1000\) : 0\)/)
  assert.match(source, /elapsed \? `\$\{t\('elapsed'\)\} \$\{formatDuration\(elapsedSeconds\)\}` : ''/)
  assert.doesNotMatch(source, /item\.(?:elapsed_ms|duration_ms)/)
})

test('polls worker history with activity and caps rendered history at 50 rows', () => {
  assert.match(source, /ctxRest\('\/history'\)/)
  assert.match(source, /setHistoryRows\(\(result\.workers \|\| result\.history \|\| \[\]\)\.slice\(0, 50\)\)/)
  assert.match(source, /refreshWorkers\(\)/)
  assert.match(source, /window\.setInterval\(refreshWorkers, 2000\)/)
})

test('worker history is permanent, collapsible, localized, and metadata-only', () => {
  assert.match(source, /function HistoryRow\(\{ item, t \}\)/)
  assert.match(source, /jsx\('details'/)
  assert.match(source, /t\('workerHistory'\)/)
  assert.match(source, /historyRows\.map\(item => jsx\(HistoryRow/)
  assert.match(source, /workerHistory: 'Worker history'/)
  assert.match(source, /workerHistory: 'Lịch sử worker'/)
  for (const safeField of ['status', 'model', 'reasoning_effort', 'fast', 'locale', 'started_at', 'completed_at', 'duration_seconds', 'api_calls', 'cost_usd']) {
    assert.match(source, new RegExp(`item\\.${safeField}`))
  }
  for (const forbiddenField of ['prompt', 'context', 'transcript', 'log', 'path', 'tool_output']) {
    assert.doesNotMatch(source, new RegExp(`item\\.${forbiddenField}`))
  }
})

test('worker history disclosure defaults closed, restores and persists its stable preference', () => {
  assert.match(source, /const HISTORY_EXPANDED_KEY = 'worker_history_expanded'/)
  assert.match(source, /useState\(\(\) => ctxStorage\.get\(HISTORY_EXPANDED_KEY, false\)\)/)
  assert.match(source, /const toggleHistory = \(\) => \{/)
  assert.match(source, /ctxStorage\.set\(HISTORY_EXPANDED_KEY, next\)/)
  assert.match(source, /setHistoryExpanded\(next\)/)
})

test('worker history has an accessible localized disclosure with an always-visible count', () => {
  assert.match(source, /jsx\('button', \{/)
  assert.match(source, /type: 'button'/)
  assert.match(source, /'aria-expanded': historyExpanded/)
  assert.match(source, /'aria-controls': 'worker-history-content'/)
  assert.match(source, /'aria-label': historyExpanded \? t\('collapseWorkerHistory'\) : t\('expandWorkerHistory'\)/)
  assert.match(source, /onClick: toggleHistory/)
  assert.match(source, /historyExpanded \? jsx\('div', \{/)
  assert.match(source, /id: 'worker-history-content'/)
  assert.match(source, /expandWorkerHistory: 'Show worker history'/)
  assert.match(source, /collapseWorkerHistory: 'Hide worker history'/)
  assert.match(source, /expandWorkerHistory: 'Hiển thị lịch sử worker'/)
  assert.match(source, /collapseWorkerHistory: 'Ẩn lịch sử worker'/)
  assert.match(source, /t\('historyCount', historyRows\.length\)/)
})

test('collapsed history keeps polling independently of disclosure state', () => {
  assert.match(source, /ctxRest\('\/history'\)/)
  assert.match(source, /window\.setInterval\(refreshWorkers, 2000\)/)
  assert.doesNotMatch(source, /if \(historyExpanded\).*ctxRest\('\/history'\)/s)
})

test('expanded history maps completion, duration, and cost from the live API contract', () => {
  assert.match(source, /item\.completed_at \? `\$\{t\('finished'\)\}: \$\{item\.completed_at\}` : ''/)
  assert.match(source, /item\.duration_seconds != null \? `\$\{t\('duration'\)\}: \$\{formatDuration\(item\.duration_seconds\)\}` : ''/)
  assert.match(source, /item\.cost_usd != null \? jsx\('div', \{ children: `\$\{t\('cost'\)\}: \$\{item\.cost_usd\}` \}\) : null/)
  assert.doesNotMatch(source, /item\.(?:finished_at|duration_ms|cost)(?:\W|$)/)
})

test('active worker rotates random expressive moods without immediate repeat', () => {
  assert.match(source, /'\(⊙_⊙\)', 'musing…'/)
  assert.match(source, /'\( •̀ᴗ•́ \)', 'synthesizing…'/)
  assert.match(source, /'\(°□°\)', 'pondering…'/)
  assert.match(source, /while \(next === previous\)/)
  assert.match(source, /Math\.floor\(Math\.random\(\) \* ACTIVITY_MOODS\.length\)/)
})

test('worker mood timer rotates every 2.6s and cleans up on unmount', () => {
  assert.match(source, /window\.setInterval\(\(\) => setMood\(previous => pickMood\(previous\)\), 2600\)/)
  assert.match(source, /return \(\) => window\.clearInterval\(timer\)/)
  assert.match(source, /'aria-hidden': true/)
  assert.match(source, /className: 'shimmer mt-1 truncate/)
  assert.match(source, /jsx\(ActivityMood, \{\}\)/)
})

test('test selected model remains real and single-model only', () => {
  assert.match(source, /ctxRest\('\/test-selected'.*body: \{ provider, model \}/s)
  assert.doesNotMatch(source, /\/test-all/)
})

test('all settings persist together through POST settings', () => {
  assert.match(source, /const next = \{ capability, language, provider, model, reasoning, fast, handoff_enabled: handoffEnabled, \.\.\.changes \}/)
  assert.match(source, /ctxRest\('\/settings', \{ method: 'POST', body: next \}\)/)
})

test('uses semantic result colors', () => {
  assert.match(source, /testing: 'text-amber-/)
  assert.match(source, /passed: 'text-emerald-/)
  assert.match(source, /failed: 'text-\(--ui-danger/)
})

test('uses neutral Worker Manager branding while retaining the internal plugin id and locales', () => {
  assert.match(source, /const ID = 'smit-worker-router'/)
  assert.match(source, /name: 'Worker Manager'/)
  assert.match(source, /title: 'Worker Manager'/)
  assert.equal(source.match(/title: 'Worker Manager'/g)?.length, 3)
  assert.doesNotMatch(source, /title: '(?:SMIT worker|Trình quản lý Worker)'/)
  assert.match(source, /title: 'Worker Manager', data:/)
})

test('builds provider and provider-specific model pickers from safe settings metadata', () => {
  assert.match(source, /normalizeProviders\(settings\.providers/)
  assert.match(source, /t\('provider'\)/)
  assert.match(source, /providerItems/)
  assert.match(source, /WorkerModelPicker/)
  assert.match(source, /ModelCatalogMenu/)
  assert.match(source, /selectProvider/)
  assert.match(source, /provider, model/)
})

test('keys model presets by provider and model', () => {
  assert.match(source, /const presetKey = \(provider, model\) => `\$\{provider\}:\$\{model\}`/)
  assert.match(source, /modelPresets\[presetKey\(next\.provider, next\.model\)\]/)
  assert.match(source, /modelPresets\[presetKey\(rowProvider, rowModel\)\]/)
})

test('refresh workers posts once for settings while monitor owns activity and history', () => {
  assert.match(source, /ctxRest\('\/refresh-workers', \{ method: 'POST' \}\)/)
  assert.match(source, /const result = await ctxRest\('\/refresh-workers', \{ method: 'POST' \}\)/)
  assert.match(source, /result\.settings/)
  const workerMonitorSlice = source.slice(source.indexOf('function WorkerMonitor'), source.indexOf('function WorkerRow'))
  assert.match(workerMonitorSlice, /ctxRest\('\/activity'\)/)
  assert.match(workerMonitorSlice, /ctxRest\('\/history'\)/)
  assert.doesNotMatch(source, /Promise\.all\(\[ctxRest\('\/settings'\), ctxRest\('\/activity'\), ctxRest\('\/history'\)\]\)/)
  assert.match(source, /setRefreshing\(true\)/)
  assert.match(source, /finally \{ setRefreshing\(false\) \}/)

  assert.match(source, /disabled: refreshing/)
})

test('refresh retains a valid selection and otherwise uses a provider/model fallback', () => {
  assert.match(source, /nextProviders\.some\(item => item\.id === currentProvider\)/)
  assert.match(source, /providerMeta.*models.*includes\(currentModel\)/s)
  assert.match(source, /nextProviders\[0\]/)
  assert.match(source, /providerMeta.*models\[0\]/s)
})

test('clear history posts to the clear endpoint and updates the history view', () => {
  assert.match(source, /ctxRest\('\/clear-history', \{ method: 'POST' \}\)/)
  assert.match(source, /setHistoryRows\(\[\]\)/)
  assert.match(source, /t\('clearHistory'\)/)
  assert.match(source, /'aria-label': t\('clearHistory'\)/)
})

test('handoff controls language visibility and obeys a locked-on setting', () => {
  assert.match(source, /const \[handoffEnabled, setHandoffEnabled\]/)
  assert.match(source, /const \[handoffLocked, setHandoffLocked\]/)
  assert.match(source, /checked: handoffEnabled/)
  assert.match(source, /disabled: handoffLocked/)
  assert.match(source, /locked \? true : Boolean\(settings\.handoff_enabled\)/)
  assert.match(source, /handoffEnabled \? jsx\('label'/)
  assert.match(source, /handoffEnabled \? jsx\(Picker/)
})

test('renames the test action to selected worker profile', () => {
  assert.match(source, /testSelected: 'Test selected worker profile'/)
  assert.doesNotMatch(source, /Test selected SMIT model/)
})

test('native model catalog owns capability reasoning and fast controls', () => {
  assert.doesNotMatch(source, /ModelCapabilityPanel/)
  assert.doesNotMatch(source, /showCapabilities/)
  assert.doesNotMatch(source, /onMouseEnter/)
  assert.match(source, /ModelCatalogMenu/)
})

test('adapts live provider slug and model capability map', () => {
  const normalizeProvidersSource = source.match(/function normalizeProviders\s*\([^)]*\)\s*\{[\s\S]*?\n\}/)?.[0] ?? ''
  assert.match(normalizeProvidersSource, /const id = .*item\.slug/)
  assert.match(normalizeProvidersSource, /\.\.\.\(item\.capabilities \|\| \{\}\)/)
  assert.match(normalizeProvidersSource, /label: item\.label \|\| item\.name \|\| id/)
})
test('both locale dictionaries define every worker UI source-contract key', () => {
  const requiredLocaleKeys = [
    'provider',
    'handoffEnabled',
    'handoffLocked',
    'refreshWorkers',
    'refreshingWorkers',
    'workersRefreshed',
    'refreshFailed',
    'clearHistory',
    'historyCleared',
    'clearHistoryFailed',
    'capabilityReasoning',
    'capabilityThinking',
    'capabilityFast',
    'yes',
    'no',
  ];

  for (const locale of ['en', 'vi']) {
    for (const key of requiredLocaleKeys) {
      assert.match(
        source,
        new RegExp(`\\b${locale}\\s*:\\s*\\{[\\s\\S]*?\\b${key}\\s*:`, 'm'),
        `${locale} locale must define ${key}`,
      );
    }
  }
});

test('uses the native Hermes model catalog in a compact worker profile trigger', () => {
  assert.match(source, /ModelCatalogMenu/)
  assert.match(source, /ModelMenuCloseContext/)
  assert.match(source, /DropdownMenu/)
  assert.match(source, /DropdownMenuContent/)
  assert.match(source, /DropdownMenuTrigger/)
  assert.match(source, /Codicon/)
  assert.match(source, /function\s+WorkerModelPicker\s*\(/)
  assert.match(source, /\{[\s\S]*?current[\s\S]*?select[\s\S]*?applyPreset[\s\S]*?presetFor[\s\S]*?setOptions[\s\S]*?\}/)
  assert.match(source, /selected[^\n]*(?:model|Model)[^\n]*(?:label|Label)|(?:model|Model)[^\n]*(?:label|Label)[^\n]*selected/)
  assert.match(source, /reasoningEffortLabel/)
  assert.match(source, /Fast/)
  assert.match(source, /jsx\(Codicon,\s*\{[\s\S]*?name:\s*['"]chevron-down['"][\s\S]*?\}\)/)
})

test('refresh is an accessible icon beside Provider', () => {
  assert.match(source, /(?:Provider[\s\S]{0,500}(?:flex|row)|(?:flex|row)[\s\S]{0,500}Provider)/)
  assert.match(source, /jsx\(Button/)
  assert.match(source, /variant:\s*['"]ghost['"]/)
  assert.match(source, /size:\s*['"](?:icon|xs)['"]/)
  assert.match(source, /['"]aria-label['"]:\s*t\(['"]refreshWorkers['"]\)/)
  assert.match(source, /disabled:\s*refreshing/)
  assert.match(source, /jsx\(Codicon,\s*\{\s*name:\s*['"]refresh['"]/)
  assert.doesNotMatch(source, /children:\s*refreshing\s*\?\s*t\(['"]refreshingWorkers['"]\)\s*:\s*t\(['"]refreshWorkers['"]\)/)
})

test('settings and monitor are separate panes', () => {
  assert.match(source, /function\s+WorkerMonitor\s*\(/)
  const workerPaneStart = source.search(/function\s+WorkerPane\s*\(/)
  const workerMonitorStart = source.search(/function\s+WorkerMonitor\s*\(/)
  assert.notEqual(workerPaneStart, -1)
  assert.notEqual(workerMonitorStart, -1)
  const workerPane = source.slice(workerPaneStart, workerMonitorStart)
  const workerMonitor = source.slice(workerMonitorStart)
  for (const symbol of ['ActivityRow', 'HistoryRow', "ctxRest('/activity')", "ctxRest('/history')", 'clearHistory', 'HISTORY_EXPANDED_KEY']) {
    assert.doesNotMatch(workerPane, new RegExp(symbol.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
    assert.match(workerMonitor, new RegExp(symbol.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
})

test('registers a separate Worker Monitor pane', () => {
  assert.match(source, /ctx\.registerMany\s*\(/)
  assert.match(source, /id:\s*["']settings-pane["']/)
  assert.match(source, /id:\s*["']monitor-pane["']/)
  assert.match(source, /title:\s*["']Worker Manager["']/)
  assert.match(source, /title:\s*["']Worker Monitor["']/)
  assert.match(source, /id:\s*["']settings-pane["'][\s\S]*?area:\s*["']panes["']/)
  assert.match(source, /id:\s*["']monitor-pane["'][\s\S]*?area:\s*["']panes["']/)
  assert.match(source, /id:\s*["']settings-pane["'][\s\S]*?placement:\s*["']right["'][\s\S]*?width:/)
  assert.match(source, /id:\s*["']monitor-pane["'][\s\S]*?placement:\s*["']right["'][\s\S]*?width:/)
})

test('inactive native model option edits update storage and reactive preset state', async () => {
  const pickerStart = source.indexOf('function WorkerModelPicker')
  const paneStart = source.indexOf('function WorkerPane')
  const monitorStart = source.indexOf('function WorkerMonitor')
  const workerPickerSource = source.slice(pickerStart, paneStart)
  const workerPaneSource = source.slice(paneStart, monitorStart)
  assert.match(
    workerPickerSource,
    /function\s+WorkerModelPicker\s*\(\s*\{[^}]*\bsetModelPresets\b[^}]*\}\s*\)/s,
    'WorkerModelPicker props include setModelPresets',
  )
  assert.match(
    workerPickerSource,
    /setOptions\s*:\s*\([^)]*\)\s*=>\s*\{(?=[\s\S]*?ctxStorage\.set\(\s*['"]model_presets['"]\s*,\s*nextPresets\s*\))(?=[\s\S]*?setModelPresets\(\s*nextPresets\s*\))[\s\S]*?\}/,
    "inactive setOptions persists model_presets and updates reactive preset state",
  )
  assert.match(
    workerPaneSource,
    /jsx\(WorkerModelPicker,\s*\{[\s\S]*?setModelPresets/,
    'WorkerPane passes setModelPresets to WorkerModelPicker',
  )
})
