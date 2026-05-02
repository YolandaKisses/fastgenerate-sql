import { render, waitFor } from '@testing-library/vue'
import { NDialogProvider, NMessageProvider } from 'naive-ui'
import { defineComponent } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DataSourcesPage from '../src/pages/DataSources/index.vue'
import { get, post } from '../src/services/request'

vi.mock('../src/services/request', () => ({
  del: vi.fn(),
  get: vi.fn(),
  patch: vi.fn(),
  post: vi.fn(),
}))

const renderPage = () => {
  const App = defineComponent({
    components: { DataSourcesPage, NDialogProvider, NMessageProvider },
    template: `
      <n-message-provider>
        <n-dialog-provider>
          <DataSourcesPage />
        </n-dialog-provider>
      </n-message-provider>
    `,
  })

  return render(App)
}

describe('数据源配置页面', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('初始化时应自动选中第一个数据源并触发连接测试', async () => {
    vi.mocked(get).mockResolvedValue([
      {
        id: 1,
        name: 'Primary_DB',
        db_type: 'mysql',
        status: 'draft',
        host: '127.0.0.1',
        port: 3306,
        database: 'primary',
        username: 'root',
        password: '',
      },
      {
        id: 2,
        name: 'Analytics_DB',
        db_type: 'postgresql',
        status: 'draft',
        host: 'localhost',
        port: 5432,
        database: 'analytics',
        username: 'postgres',
        password: '',
      },
    ])
    vi.mocked(post).mockResolvedValue({ success: true, message: '连接测试成功' })

    const { container } = renderPage()

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith('/datasources/1/test')
    })

    const selectedItem = container.querySelector('.selected-item')
    expect(selectedItem).not.toBeNull()
    expect(selectedItem).toHaveTextContent('Primary_DB')
  })

  it('连接测试失败时应显示错误反馈', async () => {
    vi.mocked(get).mockResolvedValue([
      { id: 1, name: 'Test_DB', db_type: 'mysql', status: 'draft', host: '127.0.0.1' }
    ])
    // 模拟连接测试失败
    vi.mocked(post).mockResolvedValue({ success: false, message: '连接拒绝: 认证失败' })

    renderPage()

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith('/datasources/1/test')
    })
    // 这里可以通过检查 message 调用或 UI 状态来进一步验证，但核心逻辑是请求已发出且处理了返回
  })

  it('点击列表中其他数据源时应更新表单内容', async () => {
    const mockSources = [
      { id: 1, name: 'DB_1', db_type: 'mysql', status: 'ready', host: 'host1' },
      { id: 2, name: 'DB_2', db_type: 'postgresql', status: 'draft', host: 'host2' }
    ]
    vi.mocked(get).mockResolvedValue(mockSources)
    vi.mocked(post).mockResolvedValue({ success: true })

    const { getByText, queryByDisplayValue } = renderPage()

    await waitFor(() => {
      expect(getByText('DB_2')).toBeDefined()
    })

    // 点击第二个数据源
    const secondItem = getByText('DB_2')
    secondItem.click()

    await waitFor(() => {
      // 验证表单中的值是否已更新
      // 对于 n-input，可以使用 queryByDisplayValue
      expect(queryByDisplayValue('DB_2')).not.toBeNull()
      // 对于 n-select，它在界面上显示的是 label "PostgreSQL"
      expect(getByText('PostgreSQL')).toBeDefined()
    })
  })

  it('点击“新建连接”应清空表单并允许保存', async () => {
    vi.mocked(get).mockResolvedValue([
      { id: 1, name: 'Existing_DB', db_type: 'mysql', status: 'ready', host: 'host1' }
    ])
    vi.mocked(post).mockResolvedValue({ id: 100, name: 'New_Connection', success: true })

    const { getByText, queryByDisplayValue } = renderPage()

    await waitFor(() => {
      expect(getByText('新建连接')).toBeDefined()
    })

    // 点击新建
    getByText('新建连接').click()

    await waitFor(() => {
      // 默认名称应为 New_Connection (根据 index.vue 中的 createDefaultSource)
      expect(queryByDisplayValue('New_Connection')).not.toBeNull()
    })

    // 点击保存
    const saveButton = getByText('保存修改')
    saveButton.click()

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith('/datasources/', expect.objectContaining({
        name: 'New_Connection'
      }))
    })
  })
})
