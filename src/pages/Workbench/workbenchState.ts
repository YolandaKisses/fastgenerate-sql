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

export const formatClarification = (text: string) => {
  return text
    .replace(/\s+([A-Z]\))/g, '\n$1')
    .replace(/\s+(-\s+)/g, '\n$1')
    .replace(/\n{2,}/g, '\n')
    .trim()
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
