import { render, screen, waitFor } from '@testing-library/vue'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import SchemaManagerPage from '../src/pages/SchemaManager/index.vue'

const mockMessage = {
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
  info: vi.fn()
}

vi.mock('naive-ui', async () => {
  const actual = await vi.importActual<typeof import('naive-ui')>('naive-ui')
  return {
    ...actual,
    useMessage: () => mockMessage
  }
})

describe('Schema 知识库同步', () => {
  test('点击同步到知识库后在页面展示成功进度', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [{ id: 1, name: 'sales', db_type: 'mysql' }]
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [{ id: 10, name: 'orders', original_comment: '订单表', supplementary_comment: '' }]
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => []
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: 99, status: 'pending' })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: 99, status: 'running', completed_tables: 1, total_tables: 3 })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: 99, status: 'completed', completed_tables: 3, total_tables: 3 })
      })

    vi.stubGlobal('fetch', fetchMock)

    render(SchemaManagerPage)

    expect(await screen.findByRole('button', { name: '同步到知识库' }, { timeout: 1500 })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '同步到知识库' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        'http://127.0.0.1:8000/api/v1/schema/knowledge/sync/1',
        { method: 'POST' }
      )
    })

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/api/v1/schema/knowledge/tasks/99')
    })

    await new Promise((resolve) => setTimeout(resolve, 1300))

    expect(await screen.findByText('知识库已同步成功 3 / 3')).toBeInTheDocument()

    vi.unstubAllGlobals()
  }, 8000)
})
