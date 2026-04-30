import { render, screen } from '@testing-library/vue'
import userEvent from '@testing-library/user-event'
import App from '../src/App.vue'
import { router } from '../src/router'

describe('应用壳导航', () => {
  test('展示四个中文一级菜单与当前工作台页面', async () => {
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
    expect(screen.getByRole('menuitem', { name: '设置' })).toBeInTheDocument()
    expect(screen.getByText('管理员用户')).toBeInTheDocument()

    expect(screen.getByRole('heading', { name: '工作台' })).toBeInTheDocument()

  })

  test('设置页展示模型配置表单与执行约束', async () => {
    router.push('/settings')
    await router.isReady()

    render(App, {
      global: {
        plugins: [router]
      }
    })

    expect(screen.getByRole('heading', { name: '设置' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '模型配置' })).toBeInTheDocument()
    expect(screen.getByLabelText('API 基础 URL')).toBeInTheDocument()
    expect(screen.getByLabelText('API 密钥 (API Key)')).toBeInTheDocument()
    expect(screen.getByLabelText('模型名称')).toBeInTheDocument()
    expect(screen.getByText('当前启用配置')).toBeInTheDocument()
    expect(screen.getByText(/本机应用数据目录/)).toBeInTheDocument()
    expect(screen.getByText('永不自动执行 SQL')).toBeInTheDocument()
    expect(screen.getByText('结果上限 500 行')).toBeInTheDocument()
    expect(screen.getByText('执行超时 30 秒')).toBeInTheDocument()
    expect(screen.getByText('仅允许只读查询')).toBeInTheDocument()
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
    expect(screen.getByLabelText('当前数据源')).toBeInTheDocument()
    expect(screen.getByLabelText('自然语言问题')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '澄清问题' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'SQL 候选' })).toBeInTheDocument()
    expect(screen.getByText('未执行')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'SQL 校验' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '执行确认' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '确认并执行' })).toBeDisabled()
    expect(screen.getByRole('heading', { name: '执行结果' })).toBeInTheDocument()
    expect(screen.getByText(/连接测试通过/)).toBeInTheDocument()
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
    expect(screen.getByLabelText('关键词搜索')).toBeInTheDocument()
    expect(screen.getByLabelText('执行状态筛选')).toBeInTheDocument()
    expect(screen.getByLabelText('数据源筛选')).toBeInTheDocument()
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
    expect(screen.getByLabelText('表级补充备注')).toBeInTheDocument()
    expect(screen.getByText('字段级补充备注')).toBeInTheDocument()
  })
})
