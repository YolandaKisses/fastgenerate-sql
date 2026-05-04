export type QueryResultState = {
  status: string
  columns?: string[]
  column_comments?: Record<string, string>
  rows?: any[]
  row_count?: number
  duration_ms?: number
  message?: string
  truncated_for_storage?: boolean
  storage_row_count?: number
}

export type HermesProcessStepState = {
  phase: string
  message: string
  detail?: string
  actor?: 'user' | 'system' | 'hermes'
  timestamp: number
}

export type HermesProcessRoundState = {
  key: string
  index: number
  question: string
  steps: HermesProcessStepState[]
}

export type MessageHistoryEntry = {
  role: 'user' | 'assistant'
  content: string
}

export type WorkbenchWindowSnapshot = {
  datasourceId: number | null
  sql: string
  explanation: string
  clarification: string
  result: QueryResultState | null
  executed: boolean
  history: MessageHistoryEntry[]
  auditLogId: number | null
  hermesSessionId: string | null
  hermesSteps: HermesProcessStepState[]
}

export type WorkbenchWindowState = {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  state: WorkbenchWindowSnapshot
}

export type WorkbenchWindowsState = {
  activeWindowId: string
  windows: WorkbenchWindowState[]
}

export const MESSAGE_HISTORY_STORAGE_LIMIT = 50
export const DRAFT_WORKBENCH_WINDOW_TITLE = '新查询'

const LEGACY_WINDOW_TITLE_PATTERN = /^窗口 \d+$/

export const isGeneratedWorkbenchWindowTitle = (title: string) => {
  return title === DRAFT_WORKBENCH_WINDOW_TITLE || LEGACY_WINDOW_TITLE_PATTERN.test(title)
}

export const generateWorkbenchWindowTitle = (question: string) => {
  const normalized = question.trim().replace(/\s+/g, ' ')
  if (!normalized) return DRAFT_WORKBENCH_WINDOW_TITLE

  const asciiOnly = /^[\x00-\x7F]+$/.test(normalized)
  if (asciiOnly) {
    return normalized.length > 18 ? `${normalized.slice(0, 18)}...` : normalized
  }

  let title = normalized
    .replace(/[“”"'`’‘]/g, '')
    .replace(/[，。！？；：、,.!?;:()[\]{}<>《》【】]/g, '')
    .replace(/\s+/g, '')

  const stopWords = [
    '帮我查询一下',
    '帮我查一下',
    '查询一下',
    '统计一下',
    '帮我',
    '帮忙',
    '请帮',
    '请问',
    '我想要',
    '我想',
    '想要',
    '查询',
    '查',
    '查看',
    '看看',
    '统计',
    '显示',
    '生成',
    '列出',
    '分析',
    '一下',
    '最近',
    '每个',
    '各个',
    '按照',
    '根据',
    '关于',
    '里面',
    '里',
    '中',
    '的',
    '各',
    '数据',
  ]

  for (const word of stopWords) {
    title = title.split(word).join('')
  }

  title = title || normalized
  return title.length > 14 ? `${title.slice(0, 14)}...` : title
}

export const emptyWorkbenchWindowSnapshot = (): WorkbenchWindowSnapshot => ({
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
})

export const createWorkbenchWindow = (
  index: number,
  timestamp = Date.now(),
): WorkbenchWindowState => ({
  id: `workbench-window-${timestamp}`,
  title: DRAFT_WORKBENCH_WINDOW_TITLE,
  createdAt: timestamp,
  updatedAt: timestamp,
  state: emptyWorkbenchWindowSnapshot(),
})

export const normalizeWorkbenchWindowSnapshot = (state: Partial<WorkbenchWindowSnapshot> = {}): WorkbenchWindowSnapshot => ({
  datasourceId: state.datasourceId ?? null,
  sql: state.sql ?? '',
  explanation: state.explanation ?? '',
  clarification: state.clarification ?? '',
  result: compactResultForStorage(state.result ?? null),
  executed: Boolean(state.executed ?? state.result),
  history: compactMessageHistoryForStorage(state.history ?? []),
  auditLogId: state.auditLogId ?? null,
  hermesSessionId: state.hermesSessionId ?? null,
  hermesSteps: state.hermesSteps ?? [],
})

export const resetWorkbenchWindowForDatasource = (
  previous: WorkbenchWindowSnapshot,
  datasourceId: number | null,
): WorkbenchWindowSnapshot => ({
  ...emptyWorkbenchWindowSnapshot(),
  datasourceId,
})

const looksLikeWindowsState = (value: any): value is WorkbenchWindowsState => {
  return Boolean(value?.activeWindowId && Array.isArray(value?.windows))
}

export const buildInitialWorkbenchWindows = (
  savedState?: any,
  timestamp = Date.now(),
): WorkbenchWindowsState => {
  if (looksLikeWindowsState(savedState)) {
    const windows = savedState.windows
      .filter((window: any) => window?.id)
      .map((window: any) => {
        const state = normalizeWorkbenchWindowSnapshot(window.state ?? {})
        const rawTitle = String(window.title || DRAFT_WORKBENCH_WINDOW_TITLE)
        const firstUserQuestion = state.history.find((item) => item.role === 'user')?.content
        const title = isGeneratedWorkbenchWindowTitle(rawTitle) && firstUserQuestion
          ? generateWorkbenchWindowTitle(firstUserQuestion)
          : rawTitle

        return {
          id: String(window.id),
          title,
          createdAt: Number(window.createdAt || timestamp),
          updatedAt: Number(window.updatedAt || window.createdAt || timestamp),
          state,
        }
      })

    if (windows.length > 0) {
      const activeWindowId = windows.some((window) => window.id === savedState.activeWindowId)
        ? savedState.activeWindowId
        : windows[0].id
      return { activeWindowId, windows }
    }
  }

  const firstWindow = createWorkbenchWindow(1, timestamp)
  firstWindow.state = normalizeWorkbenchWindowSnapshot(savedState ?? {})
  const firstUserQuestion = firstWindow.state.history.find((item) => item.role === 'user')?.content
  if (firstUserQuestion) {
    firstWindow.title = generateWorkbenchWindowTitle(firstUserQuestion)
  }
  return {
    activeWindowId: firstWindow.id,
    windows: [firstWindow],
  }
}

export const closeWorkbenchWindow = (
  windows: WorkbenchWindowState[],
  targetWindowId: string,
  timestamp = Date.now(),
): WorkbenchWindowsState => {
  const targetIndex = windows.findIndex((window) => window.id === targetWindowId)
  if (targetIndex === -1) {
    const fallback = windows[0] ?? createWorkbenchWindow(1, timestamp)
    return {
      activeWindowId: fallback.id,
      windows: windows.length > 0 ? windows : [fallback],
    }
  }

  const remaining = windows.filter((window) => window.id !== targetWindowId)
  if (remaining.length === 0) {
    const nextWindow = createWorkbenchWindow(1, timestamp)
    return {
      activeWindowId: nextWindow.id,
      windows: [nextWindow],
    }
  }

  const nextActive = remaining[Math.min(targetIndex, remaining.length - 1)]
  return {
    activeWindowId: nextActive.id,
    windows: remaining,
  }
}

export const actorForWorkbenchPhase = (phase: string): HermesProcessStepState['actor'] => {
  if (phase === 'retrieving_schema' || phase === 'warning') return 'system'
  return 'hermes'
}

export const formatClarification = (text: string) => {
  return text
    .replace(/\s+([A-Z]\))/g, '\n$1')
    .replace(/\s+(-\s+)/g, '\n$1')
    .replace(/\n{2,}/g, '\n')
    .trim()
}

export const startNextProcessRound = (
  existingSteps: HermesProcessStepState[],
  question: string,
  timestamp = Date.now(),
): HermesProcessStepState[] => {
  return [
    ...existingSteps,
    {
      phase: 'user_question',
      actor: 'user',
      message: question,
      timestamp,
    },
  ]
}

export const groupHermesProcessRounds = (
  steps: HermesProcessStepState[],
): HermesProcessRoundState[] => {
  const rounds: HermesProcessRoundState[] = []
  let currentSteps: HermesProcessStepState[] = []

  const pushRound = () => {
    if (currentSteps.length === 0) return
    const firstStep = currentSteps[0]
    const questionStep = currentSteps.find((step) => step.phase === 'user_question')

    rounds.push({
      key: `${firstStep.timestamp}-${rounds.length}`,
      index: rounds.length + 1,
      question: questionStep?.message || firstStep.message,
      steps: currentSteps,
    })
  }

  for (const step of steps) {
    if (step.phase === 'user_question' && currentSteps.length > 0) {
      pushRound()
      currentSteps = []
    }
    currentSteps.push(step)
  }

  pushRound()
  return rounds
}

export const appendHermesClarification = (
  existingSteps: HermesProcessStepState[],
  message: string,
  timestamp = Date.now(),
): HermesProcessStepState[] => {
  const lastStep = existingSteps[existingSteps.length - 1]
  const clarificationStep: HermesProcessStepState = {
    phase: 'clarification',
    actor: 'hermes',
    message: '需要澄清',
    detail: formatClarification(message),
    timestamp,
  }

  if (lastStep?.phase === 'completed' && lastStep.message === '需要澄清') {
    return [
      ...existingSteps.slice(0, -1),
      {
        ...clarificationStep,
        timestamp: lastStep.timestamp,
      },
    ]
  }

  return [...existingSteps, clarificationStep]
}

export const compactMessageHistoryForStorage = (
  history: MessageHistoryEntry[],
  limit = MESSAGE_HISTORY_STORAGE_LIMIT,
): MessageHistoryEntry[] => {
  if (history.length <= limit) return history
  return history.slice(-limit)
}

export const compactResultForStorage = (result: QueryResultState | null): QueryResultState | null => {
  if (!result) return null
  const compact = { ...result }
  if (Array.isArray(compact.rows) && compact.rows.length > 100) {
    compact.rows = compact.rows.slice(0, 100)
    compact.truncated_for_storage = true
    compact.storage_row_count = compact.rows.length
  }
  return compact
}
