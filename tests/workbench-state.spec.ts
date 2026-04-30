import { describe, expect, it } from 'vitest'
import { appendHermesClarification, compactResultForStorage, formatClarification, startNextProcessRound } from '../src/pages/Workbench/workbenchState'

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

  it('appends a new user process step without dropping previous rounds', () => {
    const previousSteps = [
      {
        phase: 'user_question',
        actor: 'user' as const,
        message: '第一轮问题',
        timestamp: 1,
      },
      {
        phase: 'completed',
        actor: 'hermes' as const,
        message: '已完成',
        timestamp: 2,
      },
    ]

    const nextSteps = startNextProcessRound(previousSteps, '第二轮问题', 3)

    expect(nextSteps).toEqual([
      ...previousSteps,
      {
        phase: 'user_question',
        actor: 'user',
        message: '第二轮问题',
        timestamp: 3,
      },
    ])
  })

  it('keeps clarification details inside the process history', () => {
    const previousSteps = [
      {
        phase: 'user_question',
        actor: 'user' as const,
        message: '1',
        timestamp: 1,
      },
      {
        phase: 'completed',
        actor: 'hermes' as const,
        message: '需要澄清',
        timestamp: 2,
      },
    ]

    const nextSteps = appendHermesClarification(previousSteps, '请选择：\nA) 账户表', 3)

    expect(nextSteps).toEqual([
      previousSteps[0],
      {
        phase: 'clarification',
        actor: 'hermes',
        message: '需要澄清',
        detail: '请选择：\nA) 账户表',
        timestamp: 2,
      },
    ])
  })

  it('formats clarification choices vertically in the process history', () => {
    const nextSteps = appendHermesClarification(
      [],
      '您的输入"1"含义不明确，请确认您的具体需求：  A) 查看 demo_users 表的数据 B) 查看 user_orders 表的数据 C) 查看 user_profiles 表的数据 D) 查看 user_login_logs 表的数据',
      1,
    )

    expect(nextSteps[0].detail).toBe([
      '您的输入"1"含义不明确，请确认您的具体需求：',
      'A) 查看 demo_users 表的数据',
      'B) 查看 user_orders 表的数据',
      'C) 查看 user_profiles 表的数据',
      'D) 查看 user_login_logs 表的数据',
    ].join('\n'))
  })
})
