export type WorkbenchMessage = {
  role: 'user' | 'assistant'
  content: string
}

export type WorkbenchResult = {
  status: string
  columns?: string[]
  rows?: any[]
  row_count?: number
  duration_ms?: number
  truncated_for_storage?: boolean
  storage_row_count?: number
}

export type HermesProcessStep = {
  phase: string
  actor: 'user' | 'assistant' | 'hermes' | 'system'
  message: string
  detail?: string
  timestamp: number
}

export type WorkbenchWindowState = {
  datasourceId: number | null
  sql: string
  explanation: string
  clarification: string
  result: WorkbenchResult | null
  executed: boolean
  history: WorkbenchMessage[]
  auditLogId: number | null
  hermesSessionId: string | null
  hermesSteps: HermesProcessStep[]
}

export type WorkbenchWindow = {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  state: WorkbenchWindowState
}

const GENERATED_TITLE_PATTERNS = [/^新查询$/, /^窗口 \d+$/]

export function formatClarification(text: string) {
  return text
    .replace(/\s+([A-D]\))/g, '\n$1')
    .replace(/：\s+/g, '：\n')
    .trim()
}

export function compactResultForStorage(result: WorkbenchResult | null) {
  if (!result) return null
  const rows = result.rows || []
  if (rows.length <= 100) return result
  return {
    ...result,
    rows: rows.slice(0, 100),
    truncated_for_storage: true,
    storage_row_count: 100,
  }
}

export function startNextProcessRound(previousSteps: HermesProcessStep[], question: string, timestamp: number) {
  return [
    ...previousSteps,
    {
      phase: 'user_question',
      actor: 'user' as const,
      message: question,
      timestamp,
    },
  ]
}

export function appendHermesClarification(previousSteps: HermesProcessStep[], detail: string, timestamp: number) {
  const formatted = formatClarification(detail)
  const last = previousSteps[previousSteps.length - 1]
  if (last?.phase === 'completed' && last.actor === 'hermes') {
    return [
      ...previousSteps.slice(0, -1),
      {
        phase: 'clarification',
        actor: 'hermes' as const,
        message: '需要澄清',
        detail: formatted,
        timestamp: last.timestamp,
      },
    ]
  }
  return [
    ...previousSteps,
    {
      phase: 'clarification',
      actor: 'hermes' as const,
      message: '需要澄清',
      detail: formatted,
      timestamp,
    },
  ]
}

export function groupHermesProcessRounds(steps: HermesProcessStep[]) {
  const rounds: Array<{ key: string; index: number; question: string; steps: HermesProcessStep[] }> = []
  let current: { key: string; index: number; question: string; steps: HermesProcessStep[] } | null = null
  steps.forEach((step, index) => {
    if (step.phase === 'user_question') {
      current = {
        key: `${step.timestamp}-${rounds.length}`,
        index: rounds.length + 1,
        question: step.message,
        steps: [step],
      }
      rounds.push(current)
      return
    }
    if (!current) {
      current = {
        key: `${step.timestamp}-${index}`,
        index: rounds.length + 1,
        question: '',
        steps: [],
      }
      rounds.push(current)
    }
    current.steps.push(step)
  })
  return rounds
}

export function compactMessageHistoryForStorage(history: WorkbenchMessage[]) {
  return history.slice(-50)
}

export function buildWorkbenchAskStreamParams(input: {
  datasourceId: number
  question: string
  history: WorkbenchMessage[]
  hermesSessionId: string | null
}) {
  const params = new URLSearchParams()
  params.set('datasource_id', String(input.datasourceId))
  params.set('question', input.question)
  if (input.hermesSessionId) {
    params.set('hermes_session_id', input.hermesSessionId)
  }
  if (input.history.length) {
    params.set('history', JSON.stringify(input.history))
  }
  return params
}

export function actorForWorkbenchPhase(phase: string) {
  if (phase === 'retrieving_schema' || phase === 'warning') return 'system'
  if (phase === 'calling_hermes' || phase === 'completed' || phase === 'clarification') return 'hermes'
  if (phase === 'user_question') return 'user'
  return 'assistant'
}

export function createWorkbenchWindow(index: number, timestamp: number): WorkbenchWindow {
  return {
    id: `workbench-window-${timestamp}`,
    title: '新查询',
    createdAt: timestamp,
    updatedAt: timestamp,
    state: {
      datasourceId: null,
      sql: '',
      explanation: '',
      clarification: '',
      result: null,
      executed: false,
      history: [],
      auditLogId: null,
      hermesSessionId: null,
      hermesSteps: [],
    },
  }
}

export function generateWorkbenchWindowTitle(question: string) {
  const trimmed = question.trim()
  if (!trimmed) return '新查询'
  if (/^[A-Z ]+$/.test(trimmed)) return trimmed
  return trimmed
    .replace(/^帮我|^请|^查询一下|^查询|^统计|^看一下/g, '')
    .replace(/[的了吧吗呢呀]/g, '')
    .replace(/\s+/g, '')
    .slice(0, 16) || '新查询'
}

export function isGeneratedWorkbenchWindowTitle(title: string) {
  return GENERATED_TITLE_PATTERNS.some((pattern) => pattern.test(title))
}

export function buildInitialWorkbenchWindows(legacyState: Partial<WorkbenchWindowState> | null, timestamp: number) {
  const window = createWorkbenchWindow(1, timestamp)
  if (legacyState) {
    window.title = legacyState.history?.[0]?.content ? generateWorkbenchWindowTitle(legacyState.history[0].content) : '新查询'
    window.state = {
      ...window.state,
      ...legacyState,
      history: legacyState.history || [],
    }
  }
  return {
    windows: [window],
    activeWindowId: window.id,
  }
}

export function closeWorkbenchWindow(windows: WorkbenchWindow[], targetId: string, timestamp = Date.now()) {
  const next = windows.filter((window) => window.id !== targetId)
  if (next.length === 0) {
    const fresh = createWorkbenchWindow(1, timestamp)
    return { windows: [fresh], activeWindowId: fresh.id }
  }
  const removedIndex = windows.findIndex((window) => window.id === targetId)
  const activeWindow = next[Math.min(removedIndex, next.length - 1)]
  return { windows: next, activeWindowId: activeWindow.id }
}

export function resetWorkbenchWindowForDatasource(previous: WorkbenchWindowState, datasourceId: number) {
  return {
    ...previous,
    datasourceId,
    sql: '',
    explanation: '',
    clarification: '',
    result: null,
    executed: false,
    history: [],
    auditLogId: null,
    hermesSessionId: null,
    hermesSteps: [],
  }
}
