import {
  Button,
  Codicon,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
  ModelCatalogMenu,
  ModelMenuCloseContext,
  REASONING_EFFORTS,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Switch,
  host,
  reasoningEffortLabel,
  usePluginI18n
} from '@hermes/plugin-sdk'
import { useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'smit-worker-router'
const HISTORY_EXPANDED_KEY = 'worker_history_expanded'
const CAPABILITIES = [
  ['auto', 'Auto'],
  ['frontend_code', 'Frontend code'],
  ['backend_code', 'Backend code'],
  ['research', 'Research'],
  ['architecture_review', 'Architecture review'],
  ['fast_general', 'Fast general work']
]
const LANGUAGES = [['auto', 'Auto (Random)'], ['en', 'English'], ['fr', 'Français'], ['ru', 'Русский']]
const REASONING = REASONING_EFFORTS.map(value => [value, reasoningEffortLabel(value)])

const TEST_TONE = {
  idle: 'text-(--ui-text-secondary)',
  testing: 'text-amber-600 dark:text-amber-400',
  passed: 'text-emerald-600 dark:text-emerald-400',
  failed: 'text-(--ui-danger,#f87171)'
}
const ACTIVITY_DOT = 'animate-pulse bg-emerald-500'
const ACTIVITY_TEXT = 'text-emerald-600 dark:text-emerald-400'
const ACTIVITY_MOODS = [
  ['(⊙_⊙)', 'musing…'],
  ['( •̀ᴗ•́ )', 'synthesizing…'],
  ['(°□°)', 'pondering…'],
  ['(¬‿¬)', 'connecting dots…'],
  ['(ง •̀_•́)ง', 'working it out…'],
  ['(｡•̀ᴗ-)✧', 'formulating…'],
  ['(・・ ) ?', 'considering…'],
  ['(⌐■_■)', 'analyzing…']
]

function pickMood(previous) {
  if (ACTIVITY_MOODS.length <= 1) return ACTIVITY_MOODS[0]
  let next = previous
  while (next === previous) {
    next = ACTIVITY_MOODS[Math.floor(Math.random() * ACTIVITY_MOODS.length)]
  }
  return next
}

function ActivityMood() {
  const [mood, setMood] = useState(() => pickMood(null))

  useEffect(() => {
    const timer = window.setInterval(() => setMood(previous => pickMood(previous)), 2600)
    return () => window.clearInterval(timer)
  }, [])

  return jsx('div', {
    'aria-hidden': true,
    className: 'shimmer mt-1 truncate font-mono text-[10px] text-(--ui-text-tertiary)',
    children: `… ${mood[0]} ${mood[1]}`
  })
}

function Picker({ value, onValueChange, items }) {
  return jsx(Select, {
    value, onValueChange,
    children: [
      jsx(SelectTrigger, { children: jsx(SelectValue, {}) }),
      jsx(SelectContent, { children: items.map(([itemValue, label]) => jsx(SelectItem, { value: itemValue, children: label }, itemValue)) })
    ]
  })
}

const presetKey = (provider, model) => `${provider}:${model}`

function normalizeProviders(value, legacyModels = [], legacyOptions = {}) {
  const entries = Array.isArray(value)
    ? value.map(item => typeof item === 'string' ? { id: item, label: item } : item)
    : Object.entries(value || {}).map(([id, item]) => ({ id, ...(Array.isArray(item) ? { models: item } : item) }))
  const providers = entries.map((item, index) => {
    const id = item.id || item.slug || item.value || item.name || String(index)
    const rawModels = item.models || []
    const models = rawModels.map(model => typeof model === 'string' ? model : (model.id || model.value || model.name)).filter(Boolean)
    const capabilityMap = {
      ...(item.model_options || item.options || {}),
      ...(item.capabilities || {})
    }
    const options = {}
    rawModels.forEach(model => {
      const modelId = typeof model === 'string' ? model : (model.id || model.value || model.name)
      if (!modelId) return
      const capabilities = typeof model === 'object'
        ? (model.capabilities || model.options || capabilityMap[modelId] || {})
        : (capabilityMap[modelId] || {})
      options[modelId] = {
        reasoning: Boolean(capabilities.reasoning),
        thinking: Boolean(capabilities.thinking),
        fast: Boolean(capabilities.fast)
      }
    })
    return { id, label: item.label || item.name || id, models, options }
  })
  if (!providers.length && legacyModels.length) providers.push({ id: 'default', label: 'Default', models: legacyModels, options: legacyOptions })
  return providers
}


function formatDuration(secondsValue) {
  const totalSeconds = Math.max(0, Math.floor(Number(secondsValue) || 0))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  return hours ? `${hours}h ${minutes}m ${seconds}s` : minutes ? `${minutes}m ${seconds}s` : `${seconds}s`
}

function UsageMeta({ item, t, elapsed = false }) {
  const input = item.input_tokens ?? 0
  const output = item.output_tokens ?? 0
  const total = item.total_tokens ?? 0
  const calls = item.api_calls ?? 0
  const elapsedSeconds = item.duration_seconds ?? (item.started_at ? Math.max(0, (Date.now() - Date.parse(item.started_at)) / 1000) : 0)
  return jsx('div', {
    className: 'font-mono text-[10px] leading-tight text-(--ui-text-quaternary)',
    children: [
      `${t('tokens.input')} ${input}`,
      `${t('tokens.output')} ${output}`,
      `${t('tokens.total')} ${total}`,
      `${t('apiCalls')} ${calls}`,
      elapsed ? `${t('elapsed')} ${formatDuration(elapsedSeconds)}` : ''
    ].filter(Boolean).join(' · ')
  })
}

function HistoryRow({ item, t }) {
  const overview = [item.status, item.model].filter(Boolean).join(' · ')
  const configuration = [
    item.reasoning_effort ? `${t('reasoning')}: ${reasoningEffortLabel(item.reasoning_effort)}` : '',
    item.fast ? t('fast') : '',
    item.locale ? `${t('locale')}: ${item.locale}` : ''
  ].filter(Boolean).join(' · ')
  const timestamps = [
    item.started_at ? `${t('started')}: ${item.started_at}` : '',
    item.completed_at ? `${t('finished')}: ${item.completed_at}` : '',
    item.duration_seconds != null ? `${t('duration')}: ${formatDuration(item.duration_seconds)}` : ''
  ].filter(Boolean).join(' · ')

  return jsx('details', {
    className: 'border-b border-(--ui-border-subtle) p-2 last:border-0',
    children: [
      jsxs('summary', { className: 'cursor-pointer list-inside text-xs text-(--ui-text-primary)', children: [
        jsx('span', { className: 'line-clamp-2', children: item.task_label || t('untitledTask') }),
        overview ? jsx('span', { className: 'ml-1 font-mono text-[10px] text-(--ui-text-quaternary)', children: overview }) : null
      ] }),
      jsxs('div', { className: 'mt-2 grid gap-1 pl-3 font-mono text-[10px] text-(--ui-text-quaternary)', children: [
        configuration ? jsx('div', { children: configuration }) : null,
        timestamps ? jsx('div', { children: timestamps }) : null,
        jsx(UsageMeta, { item, t }),
        item.cost_usd != null ? jsx('div', { children: `${t('cost')}: ${item.cost_usd}` }) : null
      ] })
    ]
  }, item.id)
}

function ActivityRow({ item, t }) {
  return jsxs('div', {
    className: 'grid grid-cols-[auto_minmax(0,1fr)] gap-2 border-b border-(--ui-border-subtle) p-2 last:border-0',
    children: [
      jsx('span', { 'aria-hidden': true, className: `mt-1 size-2 rounded-full ${ACTIVITY_DOT}` }),
      jsxs('div', { className: 'min-w-0', children: [
        jsx('div', { className: `text-[10px] font-medium ${ACTIVITY_TEXT}`, children: t('status.running') }),
        jsx('div', { className: 'line-clamp-2 text-xs text-(--ui-text-primary)', children: item.task_label || t('waiting') }),
        jsx(ActivityMood, {}),
        item.current_tool ? jsx('div', { className: 'truncate text-[10px] text-(--ui-text-secondary)', children: t('usingTool', item.current_tool) }) : null,
        jsx('div', { className: 'font-mono text-[10px] text-(--ui-text-quaternary)', children: [item.model, item.locale ? `LOCALE ${item.locale}` : '', item.reasoning_effort ? reasoningEffortLabel(item.reasoning_effort) : '', item.fast ? 'Fast' : '', item.tool_count ? `${item.tool_count} tools` : ''].filter(Boolean).join(' · ') }),
        jsx(UsageMeta, { item, t, elapsed: true }),
        jsx('div', { className: 'truncate font-mono text-[10px] text-(--ui-text-quaternary)', children: item.profile })
      ] })
    ]
  }, item.id)
}

function WorkerModelPicker({ provider, model, reasoning, fast, modelPresets, setModelPresets, save, setProvider, setModel }) {
  const t = usePluginI18n(ID)
  const [open, setOpen] = useState(false)
  const controller = {
    current: { provider, model, effort: reasoning, fast },
    select: (nextModel, nextProvider) => {
      setProvider(nextProvider)
      setModel(nextModel)
      return true
    },
    applyPreset: (preset, row) => {
      void save({ provider: row.provider, model: row.model, reasoning: preset.effort ?? 'medium', fast: Boolean(preset.fast) })
    },
    presetFor: (rowProvider, rowModel) => modelPresets[presetKey(rowProvider, rowModel)] || {},
    setOptions: (patch, row) => {
      if (row.isActive) {
        void save({
          ...(patch.effort !== undefined ? { reasoning: patch.effort } : {}),
          ...(patch.fast !== undefined ? { fast: patch.fast } : {}),
        })
        return
      }
      const key = presetKey(row.provider, row.model)
      const nextPresets = {
        ...modelPresets,
        [key]: {
          ...(modelPresets[key] || {}),
          ...(patch.effort !== undefined ? { effort: patch.effort } : {}),
          ...(patch.fast !== undefined ? { fast: patch.fast } : {}),
        },
      }
      ctxStorage.set('model_presets', nextPresets)
      setModelPresets(nextPresets)
    },
  }
  const selectedModelLabel = model || t('model')
  const selectedMeta = [reasoning && reasoning !== 'none' ? reasoningEffortLabel(reasoning) : '', fast ? 'Fast' : ''].filter(Boolean).join(' · ')
  const triggerLabel = selectedMeta ? `${selectedModelLabel} · ${selectedMeta}` : selectedModelLabel
  return jsx(DropdownMenu, {
    open,
    onOpenChange: setOpen,
    children: [
      jsx(DropdownMenuTrigger, {
        asChild: true,
        children: jsx(Button, {
          variant: 'outline',
          className: 'h-8 w-full justify-between gap-2 px-2.5 text-xs font-normal',
          'aria-label': triggerLabel,
          children: [
            jsx('span', { className: 'min-w-0 truncate', children: triggerLabel }),
            jsx(Codicon, { className: 'shrink-0 opacity-50', name: 'chevron-down', size: '0.7rem' }),
          ],
        }),
      }),
      jsx(DropdownMenuContent, {
        align: 'start',
        className: 'w-72 p-0',
        children: jsx(ModelMenuCloseContext.Provider, {
          value: () => setOpen(false),
          children: jsx(ModelCatalogMenu, { controller, includeMoa: false }),
        }),
      }),
    ],
  })
}

function WorkerPane() {
  const t = usePluginI18n(ID)
  const [capability, setCapability] = useState(() => ctxStorage.get('default_capability', 'auto'))
  const [language, setLanguage] = useState(() => ctxStorage.get('default_language', 'auto'))
  const [provider, setProvider] = useState(() => ctxStorage.get('default_provider', ''))
  const [model, setModel] = useState(() => ctxStorage.get('default_model', ''))
  const [reasoning, setReasoning] = useState(() => ctxStorage.get('default_reasoning', 'high'))
  const [lastReasoning, setLastReasoning] = useState(() => ctxStorage.get('last_reasoning', 'high'))
  const [fast, setFast] = useState(() => ctxStorage.get('default_fast', false))
  const [handoffEnabled, setHandoffEnabled] = useState(() => ctxStorage.get('handoff_enabled', true))
  const [handoffLocked, setHandoffLocked] = useState(false)
  const [modelPresets, setModelPresets] = useState(() => ctxStorage.get('model_presets', {}))
  const [providers, setProviders] = useState([])
  const [modelOptions, setModelOptions] = useState({})
  const [refreshing, setRefreshing] = useState(false)
  const [testState, setTestState] = useState('idle')
  const [testSummary, setTestSummary] = useState('')

  const applySettings = (settings, currentProvider = provider, currentModel = model) => {
    const nextProviders = normalizeProviders(settings.providers, settings.models || [], settings.model_options || {})
    const chosenProvider = nextProviders.some(item => item.id === currentProvider) ? currentProvider : (settings.provider || nextProviders[0]?.id || '')
    const providerMeta = nextProviders.find(item => item.id === chosenProvider) || nextProviders[0]
    const models = providerMeta?.models || []
    const chosenModel = models.includes(currentModel) ? currentModel : (models.includes(settings.model) ? settings.model : (models[0] || ''))
    setProviders(nextProviders)
    setProvider(chosenProvider)
    setModel(chosenModel)
    setModelOptions(providerMeta?.options || {})
    setCapability(settings.capability || capability)
    setLanguage(settings.language || language)
    setReasoning(settings.reasoning_effort || reasoning)
    setLastReasoning(settings.reasoning_effort === 'none' ? 'high' : (settings.reasoning_effort || reasoning))
    setFast(Boolean(settings.fast))
    const locked = Boolean(settings.handoff_locked)
    setHandoffLocked(locked)
    setHandoffEnabled(locked ? true : Boolean(settings.handoff_enabled))
  }

  useEffect(() => {
    void ctxRest('/settings').then(settings => applySettings(settings)).catch(() => host.notify({ kind: 'error', message: t('loadFailed') }))
  }, [])

  const save = async changes => {
    const next = { capability, language, provider, model, reasoning, fast, handoff_enabled: handoffEnabled, ...changes }
    try {
      await ctxRest('/settings', { method: 'POST', body: next })
      ctxStorage.set('default_capability', next.capability)
      ctxStorage.set('default_language', next.language)
      ctxStorage.set('default_provider', next.provider)
      ctxStorage.set('default_model', next.model)
      ctxStorage.set('default_reasoning', next.reasoning)
      ctxStorage.set('default_fast', next.fast)
      ctxStorage.set('handoff_enabled', next.handoff_enabled)
      const previousPreset = modelPresets[presetKey(next.provider, next.model)] || {}
      const nextPresets = {
        ...modelPresets,
        [presetKey(next.provider, next.model)]: {
          effort: next.reasoning,
          fast: next.fast,
          lastEffort: next.reasoning === 'none' ? (previousPreset.lastEffort || lastReasoning || 'medium') : next.reasoning
        }
      }
      ctxStorage.set('model_presets', nextPresets)
      setModelPresets(nextPresets)
      if (next.reasoning !== 'none') {
        ctxStorage.set('last_reasoning', next.reasoning)
        setLastReasoning(next.reasoning)
      }
      setCapability(next.capability); setLanguage(next.language); setProvider(next.provider); setModel(next.model); setReasoning(next.reasoning); setFast(next.fast); setHandoffEnabled(next.handoff_enabled)
      setTestState('idle'); setTestSummary('')
      host.notify({ kind: 'success', message: t('saved') })
    } catch {
      host.notify({ kind: 'error', message: t('failed') })
    }
  }

  const providerItems = providers.map(item => [item.id, item.label])
  const providerMeta = providers.find(item => item.id === provider)

  const selectProvider = value => {
    const nextProvider = providers.find(item => item.id === value)
    const nextModel = nextProvider?.models[0] || ''
    setModelOptions(nextProvider?.options || {})
    void save({ provider: value, model: nextModel, reasoning: 'none', fast: false })
  }

  const testSelected = async () => {
    setTestState('testing'); setTestSummary(t('testingModel', model))
    try {
      const result = await ctxRest('/test-selected', { method: 'POST', body: { provider, model } })
      const passed = Boolean(result.ok)
      setTestState(passed ? 'passed' : 'failed')
      setTestSummary(passed ? t('testSummary', model) : t('testFailedModel', model))
      host.notify({ kind: passed ? 'success' : 'error', message: passed ? t('testPassed') : t('testFailed') })
    } catch {
      setTestState('failed'); setTestSummary(t('testFailedModel', model))
      host.notify({ kind: 'error', message: t('testFailed') })
    }
  }

  const refreshAll = async () => {
    setRefreshing(true)
    try {
      const result = await ctxRest('/refresh-workers', { method: 'POST' })
      const settings = result.settings || {}
      applySettings(settings, provider, model)
      host.notify({ kind: 'success', message: t('workersRefreshed') })
    } catch {
      host.notify({ kind: 'error', message: t('refreshFailed') })
    } finally { setRefreshing(false) }
  }

  return jsxs('div', {
    className: 'flex h-full min-h-0 flex-col gap-3 p-3 text-sm',
    children: [
      jsx('div', { className: 'font-medium', children: t('title') }),
      jsx('div', { className: 'text-(--ui-text-tertiary)', children: t('description') }),
      jsx('label', { className: 'text-xs text-(--ui-text-secondary)', children: t('capability') }),
      jsx(Picker, { value: capability, onValueChange: value => void save({ capability: value }), items: CAPABILITIES }),
      jsxs('div', { className: 'grid grid-cols-[minmax(0,1fr)_auto] items-end gap-1', children: [jsx('div', { className: 'grid min-w-0 gap-1', children: [jsx('label', { className: 'text-xs text-(--ui-text-secondary)', children: t('provider') }), jsx(Picker, { value: provider, onValueChange: selectProvider, items: providerItems })] }), jsx(Button, { variant: 'ghost', size: 'icon', 'aria-label': t('refreshWorkers'), title: t('refreshWorkers'), 'aria-busy': refreshing, disabled: refreshing, onClick: () => void refreshAll(), children: jsx(Codicon, { name: 'refresh', className: refreshing ? 'animate-spin' : '', size: '0.8rem' }) })] }),
      jsx(WorkerModelPicker, { provider, model, reasoning, fast, modelPresets, setModelPresets, save, setProvider, setModel }),
      jsxs('div', { className: 'flex items-center justify-between', children: [
        jsx('label', { className: 'text-xs text-(--ui-text-secondary)', children: t('handoffEnabled') }),
        jsx(Switch, { checked: handoffEnabled, disabled: handoffLocked, size: 'xs', 'aria-label': t('handoffEnabled'), onCheckedChange: checked => void save({ handoff_enabled: checked }) })
      ] }),
      handoffLocked ? jsx('div', { className: 'text-[10px] text-(--ui-text-quaternary)', children: t('handoffLocked') }) : null,
      handoffEnabled ? jsx('label', { className: 'text-xs text-(--ui-text-secondary)', children: t('language') }) : null,
      handoffEnabled ? jsx(Picker, { value: language, onValueChange: value => void save({ language: value }), items: LANGUAGES }) : null,
      jsx(Button, { variant: 'secondary', className: 'w-full', disabled: testState === 'testing', onClick: () => void testSelected(), children: testState === 'testing' ? t('testing') : t('testSelected') }),
      testSummary ? jsx('div', { 'aria-live': 'polite', className: `text-xs font-medium ${TEST_TONE[testState]}`, children: testSummary }) : null,




      jsx('div', { className: 'text-xs text-(--ui-text-quaternary)', children: t('role') }),
      jsx('div', { className: 'text-xs text-(--ui-text-quaternary)', children: t('note') })
    ]
  })
}

function WorkerMonitor() {
  const t = usePluginI18n(ID)
  const [activeWorkers, setActiveWorkers] = useState(0)
  const [workerRows, setWorkerRows] = useState([])
  const [historyRows, setHistoryRows] = useState([])
  const [historyExpanded, setHistoryExpanded] = useState(() => ctxStorage.get(HISTORY_EXPANDED_KEY, false))
  useEffect(() => {
    let alive = true
    const refreshWorkers = () => {
      void ctxRest('/activity').then(result => { if (alive) { setActiveWorkers(result.active || 0); setWorkerRows(result.workers || []) } }).catch(() => {})
      void ctxRest('/history').then(result => { if (alive) setHistoryRows((result.workers || result.history || []).slice(0, 50)) }).catch(() => {})
    }
    refreshWorkers()
    const timer = window.setInterval(refreshWorkers, 2000)
    return () => { alive = false; window.clearInterval(timer) }
  }, [])
  const clearHistory = async () => {
    try { await ctxRest('/clear-history', { method: 'POST' }); setHistoryRows([]); host.notify({ kind: 'success', message: t('historyCleared') }) }
    catch { host.notify({ kind: 'error', message: t('clearHistoryFailed') }) }
  }
  const toggleHistory = () => { const next = !historyExpanded; ctxStorage.set(HISTORY_EXPANDED_KEY, next); setHistoryExpanded(next) }
  return jsxs('div', { className: 'flex h-full min-h-0 flex-col gap-3 p-3 text-sm', children: [
    jsx('div', { className: 'font-medium', children: t('monitorTitle') }),
    jsxs('section', { className: 'flex min-h-0 flex-1 flex-col gap-2', children: [
      jsxs('div', { className: 'flex items-center justify-between', children: [jsx('div', { className: 'text-xs font-medium text-(--ui-text-primary)', children: t('workerActivity') }), jsx('div', { className: 'text-xs text-emerald-600 dark:text-emerald-400', children: t('activeWorkers', activeWorkers) })] }),
      jsx('div', { className: 'min-h-0 flex-1 overflow-y-auto rounded border border-(--ui-border-subtle)', children: workerRows.length ? workerRows.map(item => jsx(ActivityRow, { item, t }, item.id)) : jsx('div', { className: 'p-2 text-xs text-(--ui-text-quaternary)', children: t('waiting') }) })
    ] }),
    jsxs('section', { className: 'flex flex-col gap-2 border-t border-(--ui-border-subtle) pt-3', children: [
      jsxs('div', { className: 'flex items-center justify-between', children: [
        jsx('button', { type: 'button', 'aria-expanded': historyExpanded, 'aria-controls': 'worker-history-content', 'aria-label': historyExpanded ? t('collapseWorkerHistory') : t('expandWorkerHistory'), onClick: toggleHistory, className: 'flex flex-1 cursor-pointer items-center justify-between text-left', children: [jsx('span', { className: 'text-xs font-medium text-(--ui-text-primary)', children: t('workerHistory') }), jsx('span', { className: 'mr-2 font-mono text-[10px] text-(--ui-text-quaternary)', children: t('historyCount', historyRows.length) })] }),
        jsx(Button, { variant: 'ghost', size: 'sm', 'aria-label': t('clearHistory'), onClick: () => void clearHistory(), children: t('clearHistory') })
      ] }),
      historyExpanded ? jsx('div', { id: 'worker-history-content', className: 'min-h-0 max-h-80 overflow-y-auto rounded border border-(--ui-border-subtle)', children: historyRows.length ? historyRows.map(item => jsx(HistoryRow, { item, t }, item.id)) : jsx('div', { className: 'p-2 text-xs text-(--ui-text-quaternary)', children: t('noHistory') }) }) : null
    ] })
  ] })
}

let ctxStorage
let ctxRest

export default {
  id: ID, name: 'Worker Manager',
  register(ctx) {
    ctxStorage = ctx.storage
    ctxRest = ctx.rest
    ctx.i18n.register({
      en: {
    provider: 'Provider',
    handoffEnabled: 'Handoff enabled',
    handoffLocked: 'Handoff locked',
    refreshWorkers: 'Refresh workers',
    refreshingWorkers: 'Refreshing workers…',
    workersRefreshed: 'Workers refreshed',
    refreshFailed: 'Refresh failed',
    clearHistory: 'Clear history',
    historyCleared: 'History cleared',
    clearHistoryFailed: 'Failed to clear history',
    capabilityReasoning: 'Reasoning',
    capabilityThinking: 'Thinking',
    capabilityFast: 'Fast',
    yes: 'Yes',
    no: 'No',
        title: 'Worker Manager', monitorTitle: 'Worker Monitor', description: 'Choose a task role, worker profile, reasoning effort, and handoff language.',
        capability: 'Worker capability', model: 'Worker profile', thinking: 'Thinking', reasoning: 'Reasoning effort', fast: 'Fast', language: 'Handoff language', saved: 'Worker Manager defaults saved.',
        failed: 'Could not save Worker Manager defaults.', loadFailed: 'Could not load registered worker profiles.',
        testSelected: 'Test selected worker profile', testing: 'Testing selected model…', testingModel: model => `Testing ${model}…`, testPassed: 'Selected model test passed.', testFailed: 'Selected model test failed.', testSummary: model => `${model} passed.`, testFailedModel: model => `${model} failed.`,
        workerActivity: 'Worker activity', activeWorkers: count => `${count} active`, waiting: 'Waiting for assigned task', usingTool: tool => `Using ${tool}`,
        workerHistory: 'Worker history', historyCount: count => `${count}/50`, expandWorkerHistory: 'Show worker history', collapseWorkerHistory: 'Hide worker history', noHistory: 'No worker history yet.', untitledTask: 'Untitled task',
        tokens: { input: 'Input', output: 'Output', total: 'Total' }, apiCalls: 'API calls', elapsed: 'Elapsed', locale: 'Locale', started: 'Started', finished: 'Finished', duration: 'Duration', cost: 'Cost',
        status: { running: 'Running' },
        role: 'Worker role: leaf (enforced for isolated external children).', note: 'Active cards show only active workers. History uses sanitized task labels and safe metadata; context is never displayed.'
      },
      vi: {
    provider: 'Nhà cung cấp',
    handoffEnabled: 'Đã bật chuyển giao',
    handoffLocked: 'Đã khóa chuyển giao',
    refreshWorkers: 'Làm mới worker',
    refreshingWorkers: 'Đang làm mới worker…',
    workersRefreshed: 'Đã làm mới worker',
    refreshFailed: 'Làm mới thất bại',
    clearHistory: 'Xóa lịch sử',
    historyCleared: 'Đã xóa lịch sử',
    clearHistoryFailed: 'Không thể xóa lịch sử',
    capabilityReasoning: 'Lập luận',
    capabilityThinking: 'Suy nghĩ',
    capabilityFast: 'Nhanh',
    yes: 'Có',
    no: 'Không',
        title: 'Worker Manager', monitorTitle: 'Worker Monitor', description: 'Chọn vai trò tác vụ, hồ sơ worker, mức reasoning và ngôn ngữ handoff.',
        capability: 'Capability worker', model: 'Hồ sơ worker', thinking: 'Thinking', reasoning: 'Mức reasoning', fast: 'Fast', language: 'Ngôn ngữ handoff', saved: 'Đã lưu mặc định Worker Manager.',
        failed: 'Không thể lưu mặc định Worker Manager.', loadFailed: 'Không thể tải hồ sơ worker đã đăng ký.',
        testSelected: 'Test hồ sơ worker đã chọn', testing: 'Đang test model đã chọn…', testingModel: model => `Đang test ${model}…`, testPassed: 'Model đã chọn đã pass.', testFailed: 'Model đã chọn test thất bại.', testSummary: model => `${model} đã pass.`, testFailedModel: model => `${model} thất bại.`,
        workerActivity: 'Worker đang làm gì', activeWorkers: count => `${count} đang chạy`, waiting: 'Đang chờ nhiệm vụ', usingTool: tool => `Đang dùng ${tool}`,
        workerHistory: 'Lịch sử worker', historyCount: count => `${count}/50`, expandWorkerHistory: 'Hiển thị lịch sử worker', collapseWorkerHistory: 'Ẩn lịch sử worker', noHistory: 'Chưa có lịch sử worker.', untitledTask: 'Tác vụ chưa đặt tên',
        tokens: { input: 'Đầu vào', output: 'Đầu ra', total: 'Tổng' }, apiCalls: 'Lượt gọi API', elapsed: 'Đã chạy', locale: 'Ngôn ngữ', started: 'Bắt đầu', finished: 'Kết thúc', duration: 'Thời lượng', cost: 'Chi phí',
        status: { running: 'Đang chạy' },
        role: 'Vai trò worker: leaf (bắt buộc để cô lập child external).', note: 'Thẻ đang chạy chỉ hiển thị worker active. Lịch sử chỉ dùng nhãn tác vụ đã làm sạch và metadata an toàn; không hiển thị context.'
      }
    })
    ctx.registerMany([{ id: 'settings-pane', area: 'panes', title: 'Worker Manager', data: { placement: 'right', width: '340px' }, render: () => jsx(WorkerPane, {}) }, { id: 'monitor-pane', area: 'panes', title: 'Worker Monitor', data: { placement: 'right', width: '420px' }, render: () => jsx(WorkerMonitor, {}) }])
  }
}
