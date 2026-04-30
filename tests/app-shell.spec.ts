import { render, screen } from '@testing-library/vue'
import userEvent from '@testing-library/user-event'
import App from '../src/App.vue'
import { router } from '../src/router'

describe('应用壳导航', () => {
  test('展示主要菜单与当前工作台页面', async () => {
    router.push('/workspace')
    await router.isReady()

    render(App, {
      global: {
        plugins: [router]
      }
    })

    expect(screen.getByRole('menu')).toBeInTheDocument()
    expect(screen.getByText('SQL AI')).toBeInTheDocument()
    expect(screen.getByText('v1.2.0')).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: '工作台' })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: '数据源配置' })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: '审计日志' })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: '设置' })).not.toBeInTheDocument()
    expect(screen.getByText('管理员用户')).toBeInTheDocument()

    expect(screen.getByRole('heading', { name: '工作台' })).toBeInTheDocument()

  })

  test('工作台展示问答主流程必需结构', async () => {
    router.push('/workspace')
    await router.isReady()

    render(App, {
      global: {
        plugins: [router]
      }
    })

    expect(screen.getByRole('heading', { name: '工作台' })).toBeInTheDocument()
    expect(screen.getByText('当前数据源')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'SQL 候选' })).toBeInTheDocument()
    expect(screen.getByText('生成 SQL 后会展示候选语句与解释说明。')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '执行结果' })).toBeInTheDocument()
    expect(screen.getByText('执行完成后，这里会展示结果表格或错误信息。')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '生成 SQL' })).toBeInTheDocument()
    expect(screen.getByText(/常见澄清场景/)).toBeInTheDocument()
  })

  test('数据源配置页展示连接与删除能力', async () => {
    router.push('/data-sources')
    await router.isReady()

    render(App, {
      global: {
        plugins: [router]
      }
    })

    expect(screen.getByRole('heading', { name: '数据源配置' })).toBeInTheDocument()
    expect(screen.getByText(/连接测试通过后即可进入工作台问答流程/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '测试连接' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '保存修改' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '删除数据源' })).toBeInTheDocument()
  })

  test('审计日志页提供筛选与详情，但不提供导出', async () => {
    router.push('/audit-logs')
    await router.isReady()

    render(App, {
      global: {
        plugins: [router]
      }
    })

    expect(screen.getByRole('heading', { name: '审计日志' })).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { name: '日志详情' }).length).toBeGreaterThan(0)
    expect(screen.getByText(/仅本地查看/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '导出' })).not.toBeInTheDocument()
  })

  test('Schema 管理页支持表级和字段级补充备注', async () => {
    router.push('/schema')
    await router.isReady()

    render(App, {
      global: {
        plugins: [router]
      }
    })

    expect(screen.getByRole('heading', { name: 'Schema 与备注管理' })).toBeInTheDocument()
    expect(screen.getByText(/表级和字段级/)).toBeInTheDocument()
  })
})
