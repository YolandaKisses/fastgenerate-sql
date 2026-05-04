import { describe, expect, it } from 'vitest'
import {
  actorForWorkbenchPhase,
  appendHermesClarification,
  buildInitialWorkbenchWindows,
  closeWorkbenchWindow,
  compactMessageHistoryForStorage,
  compactResultForStorage,
  createWorkbenchWindow,
  formatClarification,
  generateWorkbenchWindowTitle,
  groupHermesProcessRounds,
  isGeneratedWorkbenchWindowTitle,
  resetWorkbenchWindowForDatasource,
  startNextProcessRound,
} from '../src/pages/Workbench/workbenchState'

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

  it('groups process steps into user question rounds', () => {
    const rounds = groupHermesProcessRounds([
      {
        phase: 'user_question',
        actor: 'user',
        message: '第一轮问题',
        timestamp: 1,
      },
      {
        phase: 'completed',
        actor: 'hermes',
        message: '已完成',
        timestamp: 2,
      },
      {
        phase: 'user_question',
        actor: 'user',
        message: '第二轮问题',
        timestamp: 3,
      },
      {
        phase: 'calling_hermes',
        actor: 'hermes',
        message: '正在调用 Hermes Agent...',
        timestamp: 4,
      },
    ])

    expect(rounds).toHaveLength(2)
    expect(rounds[0]).toMatchObject({
      key: '1-0',
      index: 1,
      question: '第一轮问题',
    })
    expect(rounds[0].steps).toHaveLength(2)
    expect(rounds[1]).toMatchObject({
      key: '3-1',
      index: 2,
      question: '第二轮问题',
    })
    expect(rounds[1].steps).toHaveLength(2)
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

  it('keeps only recent message history entries for browser storage', () => {
    const history = Array.from({ length: 55 }, (_, idx) => ({
      role: idx % 2 === 0 ? 'user' as const : 'assistant' as const,
      content: `message-${idx + 1}`,
    }))

    const compacted = compactMessageHistoryForStorage(history)

    expect(compacted).toHaveLength(50)
    expect(compacted[0].content).toBe('message-6')
    expect(compacted[49].content).toBe('message-55')
  })

  it('classifies sqlite retrieval as a system process step', () => {
    expect(actorForWorkbenchPhase('retrieving_schema')).toBe('system')
    expect(actorForWorkbenchPhase('warning')).toBe('system')
    expect(actorForWorkbenchPhase('calling_hermes')).toBe('hermes')
  })

  it('creates an empty workbench window with a neutral draft title', () => {
    const window = createWorkbenchWindow(2, 100)

    expect(window).toMatchObject({
      id: 'workbench-window-100',
      title: '新查询',
      createdAt: 100,
      updatedAt: 100,
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
    })
  })

  it('restores legacy single-state storage as the first workbench window', () => {
    const restored = buildInitialWorkbenchWindows({
      datasourceId: 3,
      sql: 'select * from users',
      explanation: '用户列表',
      history: [{ role: 'user', content: '查用户' }],
      hermesSessionId: 'session-1',
    }, 200)

    expect(restored.activeWindowId).toBe(restored.windows[0].id)
    expect(restored.windows).toHaveLength(1)
    expect(restored.windows[0]).toMatchObject({
      title: '用户',
      state: {
        datasourceId: 3,
        sql: 'select * from users',
        explanation: '用户列表',
        history: [{ role: 'user', content: '查用户' }],
        hermesSessionId: 'session-1',
      },
    })
  })

  it('extracts semantic keywords from the first question for tab title', () => {
    expect(generateWorkbenchWindowTitle('帮我查询一下最近30天每个城市的用户数量趋势')).toBe('30天城市用户数量趋势')
    expect(generateWorkbenchWindowTitle('统计订单表里各渠道支付金额')).toBe('订单表渠道支付金额')
    expect(generateWorkbenchWindowTitle('SHOW TABLES')).toBe('SHOW TABLES')
  })

  it('only auto-renames draft or legacy window titles', () => {
    expect(isGeneratedWorkbenchWindowTitle('新查询')).toBe(true)
    expect(isGeneratedWorkbenchWindowTitle('窗口 3')).toBe(true)
    expect(isGeneratedWorkbenchWindowTitle('30天城市用户数量趋势')).toBe(false)
    expect(isGeneratedWorkbenchWindowTitle('我的留存分析')).toBe(false)
  })

  it('closes the active workbench window and activates a neighbor', () => {
    const first = createWorkbenchWindow(1, 1)
    const second = createWorkbenchWindow(2, 2)
    const third = createWorkbenchWindow(3, 3)

    const result = closeWorkbenchWindow([first, second, third], second.id)

    expect(result.windows.map((window) => window.id)).toEqual([first.id, third.id])
    expect(result.activeWindowId).toBe(third.id)
  })

  it('keeps one empty workbench window when closing the last window', () => {
    const only = createWorkbenchWindow(1, 1)

    const result = closeWorkbenchWindow([only], only.id, 10)

    expect(result.windows).toHaveLength(1)
    expect(result.activeWindowId).toBe(result.windows[0].id)
    expect(result.windows[0].state.history).toEqual([])
  })

  it('starts a fresh hermes session when a window changes datasource', () => {
    const previous = createWorkbenchWindow(1, 1).state
    previous.datasourceId = 1
    previous.sql = 'select * from old_table'
    previous.explanation = '旧查询'
    previous.history = [
      { role: 'user', content: '查旧表' },
      { role: 'assistant', content: '旧 SQL' },
    ]
    previous.auditLogId = 12
    previous.hermesSessionId = 'hermes-old-session'
    previous.hermesSteps = [
      {
        phase: 'completed',
        actor: 'hermes',
        message: '已完成',
        timestamp: 1,
      },
    ]

    const next = resetWorkbenchWindowForDatasource(previous, 2)

    expect(next).toMatchObject({
      datasourceId: 2,
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
  })
})
