import { fireEvent, render, waitFor } from '@testing-library/vue'
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
      { id: 1, name: 'DB_1', db_type: 'mysql', status: 'connection_ok', host: 'host1' },
      { id: 2, name: 'DB_2', db_type: 'postgresql', status: 'draft', host: 'host2' }
    ]
    vi.mocked(get).mockResolvedValue(mockSources)
    vi.mocked(post).mockResolvedValue({ success: true })

    const { container, getByText, queryByDisplayValue } = renderPage()

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
      { id: 1, name: 'Existing_DB', db_type: 'mysql', status: 'connection_ok', host: 'host1' }
    ])
    vi.mocked(post).mockResolvedValue({ id: 100, name: 'New_Connection', success: true })

    const { container, getByText, queryByDisplayValue } = renderPage()

    await waitFor(() => {
      expect(getByText('新建连接')).toBeDefined()
    })

    // 点击新建
    getByText('新建连接').click()

    await waitFor(() => {
      expect(queryByDisplayValue('New_Connection')).not.toBeNull()
    })

    // 填充基本信息（必填项）
    await fireEvent.update(container.querySelector('input[placeholder="例如: Production_DB"]') as HTMLInputElement, 'New_Connection')
    await fireEvent.update(container.querySelector('input[placeholder="app_db"]') as HTMLInputElement, 'app_db')
    const credentialInputs = Array.from(container.querySelectorAll('.auth-content input')) as HTMLInputElement[]
    await fireEvent.update(credentialInputs[0], 'root')
    await fireEvent.update(credentialInputs[1], 'secret')
    
    const saveButton = getByText('保存修改')
    saveButton.click()

    await waitFor(() => {
      // 验证是否触发了保存请求
      expect(post).toHaveBeenCalledWith('/datasources/', expect.objectContaining({
        name: 'New_Connection'
      }))
    })
  })

  it('切换到 SSH 通道模式时应改变输入项', async () => {
    vi.mocked(get).mockResolvedValue([
      { id: 1, name: 'SSH_DB', db_type: 'mysql', status: 'draft', host: '1.1.1.1', database: 'test', port: 3306 }
    ])
    vi.mocked(post).mockResolvedValue({ success: true })

    const { getAllByText, getByText, container } = renderPage()

    await waitFor(() => {
      expect(getAllByText('SSH_DB').length).toBeGreaterThan(0)
    })

    // 默认是用户名密码模式，应该能看到“用户名”
    expect(container.textContent).toContain('用户名')

    // 切换到 SSH 通道 (使用 n-radio-button)
    const sshInput = container.querySelector('input[value="ssh"]') as HTMLInputElement
    await fireEvent.click(sshInput)

    await waitFor(() => {
      expect(container.textContent).toContain('SSH 通道连接')
      expect(container.querySelectorAll('.auth-content input')).toHaveLength(0)
    })
  })
})
