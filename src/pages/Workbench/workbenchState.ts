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

export const MESSAGE_HISTORY_STORAGE_LIMIT = 50

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
