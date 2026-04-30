import { describe, expect, it } from 'vitest'
import { compactResultForStorage, formatClarification } from '../src/pages/Workbench/workbenchState'

describe('workbench state helpers', () => {
  it('formats A/B/C/D clarification options as compact lines', () => {
    const text = '请选择：  A) 用户资料  B) 用户订单  C) 登录日志  D) 账户余额'

    expect(formatClarification(text)).toBe([
      '请选择：',
      'A) 用户资料',
      'B) 用户订单',
      'C) 登录日志',
      'D) 账户余额',
    ].join('\n'))
  })

  it('keeps execution result small enough for browser state restore', () => {
    const rows = Array.from({ length: 150 }, (_, idx) => ({ id: idx + 1 }))
    const result = compactResultForStorage({
      status: 'success',
      columns: ['id'],
      rows,
      row_count: rows.length,
      duration_ms: 12,
    })

    if (!result) throw new Error('expected compact result')
    expect(result.rows).toHaveLength(100)
    expect(result.truncated_for_storage).toBe(true)
    expect(result.storage_row_count).toBe(100)
    expect(result.row_count).toBe(150)
  })
})
