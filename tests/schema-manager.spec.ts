import { fireEvent, render, waitFor } from '@testing-library/vue'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SchemaManagerPage from '../src/pages/SchemaManager/index.vue'
import { get, post, streamSse } from '../src/services/request'

const dialogState = vi.hoisted(() => ({
  warning: vi.fn(),
}))

vi.mock('naive-ui', () => {
  const passthrough = (tag = 'div') => defineComponent({
    setup(_, { slots, attrs }) {
      return () => h(tag, attrs, slots.default?.())
    },
  })

  return {
    NButton: defineComponent({
      emits: ['click'],
      setup(_, { slots, emit, attrs }) {
        return () => h('button', { ...attrs, onClick: () => emit('click') }, slots.default?.())
      },
    }),
    NCard: passthrough(),
    NIcon: passthrough('span'),
    NInput: defineComponent({
      props: ['value'],
      emits: ['update:value'],
      setup(props, { emit, attrs }) {
        return () => h('input', {
          ...attrs,
          value: props.value ?? '',
          onInput: (event: Event) => emit('update:value', (event.target as HTMLInputElement).value),
        })
      },
    }),
    NScrollbar: passthrough(),
    NSelect: defineComponent({
      props: ['value', 'options'],
      emits: ['update:value'],
      setup(props, { emit }) {
        return () => h('select', {
          'data-testid': 'source-select',
          value: props.value ?? '',
          onChange: (event: Event) => emit('update:value', Number((event.target as HTMLSelectElement).value)),
        }, (props.options ?? []).map((option: any) => h('option', { value: option.value }, option.label)))
      },
    }),
    NText: passthrough('span'),
    useDialog: () => dialogState,
    useMessage: () => ({
      error: vi.fn(),
      success: vi.fn(),
      warning: vi.fn(),
    }),
  }
})

vi.mock('../src/services/request', () => ({
  get: vi.fn(),
  patch: vi.fn(),
  post: vi.fn(),
  streamSse: vi.fn(),
}))

const renderPage = () => {
  const App = defineComponent({
    components: { SchemaManagerPage },
    template: '<SchemaManagerPage />',
  })

  return render(App)
}

describe('Schema 管理页面', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(streamSse).mockResolvedValue(undefined)
    vi.mocked(get).mockImplementation(async (path: string) => {
      if (path === '/datasources/') {
        return [
          { id: 1, name: 'Primary_DB', db_type: 'mysql' },
          { id: 2, name: 'Analytics_DB', db_type: 'postgresql' },
        ]
      }
      if (path === '/schema/tables/1') {
        return [{ id: 10, name: 'users', original_comment: '用户表' }]
      }
      if (path === '/schema/tables/2') {
        return [
          { id: 20, name: 'events', original_comment: '事件表' },
          { id: 21, name: 'sessions', original_comment: '会话表' },
        ]
      }
      if (path === '/schema/knowledge/status/1') {
        return { task: null, actual_table_count: 1 }
      }
      if (path === '/schema/knowledge/status/2') {
        return { task: null, actual_table_count: 2 }
      }
      if (path === '/schema/fields/10' || path === '/schema/fields/20') {
        return []
      }
      return null
    })
  })

  it('知识库同步确认后使用打开弹窗时的数据源', async () => {
    vi.mocked(post).mockResolvedValue({ id: 99, status: 'pending', completed_tables: 0, total_tables: 1 })

    const { getAllByText, getByText, getByTestId } = renderPage()

    await waitFor(() => {
      expect(getAllByText('users').length).toBeGreaterThan(0)
    })

    getByText('同步到知识库').click()
    const confirm = dialogState.warning.mock.calls[0][0]

    await waitFor(() => {
      expect(getByTestId('source-select')).toHaveValue('1')
    })
    await fireEvent.update(getByTestId('source-select'), '2')

    await confirm.onPositiveClick()

    expect(post).toHaveBeenCalledWith('/schema/knowledge/sync/1')
  })
})
