import { render, screen } from '@testing-library/vue'
import userEvent from '@testing-library/user-event'
import TableList from '../src/pages/SchemaManager/components/TableList.vue'

describe('Schema 表列表搜索', () => {
  test('按表名和备注过滤列表', async () => {
    render(TableList, {
      props: {
        tables: [
          { id: 1, name: 'orders', original_comment: '订单表' },
          { id: 2, name: 'refunds', original_comment: '退款记录' },
          { id: 3, name: 'users', original_comment: '用户信息' }
        ],
        selectedTable: null
      }
    })

    expect(screen.getByText('orders')).toBeInTheDocument()
    expect(screen.getByText('refunds')).toBeInTheDocument()
    expect(screen.getByText('users')).toBeInTheDocument()

    await userEvent.type(screen.getByPlaceholderText('搜索表名...'), 'refund')

    expect(screen.queryByText('orders')).not.toBeInTheDocument()
    expect(screen.getByText('refunds')).toBeInTheDocument()
    expect(screen.queryByText('users')).not.toBeInTheDocument()

    await userEvent.clear(screen.getByPlaceholderText('搜索表名...'))
    await userEvent.type(screen.getByPlaceholderText('搜索表名...'), '用户')

    expect(screen.queryByText('orders')).not.toBeInTheDocument()
    expect(screen.queryByText('refunds')).not.toBeInTheDocument()
    expect(screen.getByText('users')).toBeInTheDocument()
  })
})
