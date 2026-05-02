import { render, screen } from '@testing-library/vue'
import { NLayout } from 'naive-ui'
import { describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import AppSidebar from '../src/components/layout/AppSidebar.vue'
import LoginPage from '../src/pages/Login/index.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ path: '/login', query: {} }),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
}))

vi.mock('naive-ui', async (importActual) => {
  const actual = await importActual<typeof import('naive-ui')>()

  return {
    ...actual,
    useDialog: () => ({ warning: vi.fn() }),
    useMessage: () => ({
      error: vi.fn(),
      success: vi.fn(),
      warning: vi.fn(),
    }),
  }
})

const SidebarHarness = defineComponent({
  setup() {
    return () => h(NLayout, { hasSider: true }, () => h(AppSidebar))
  },
})

describe('brand logo', () => {
  it('renders the generated FastGenerate SQL logo on the login page', () => {
    render(LoginPage)

    expect(screen.getByAltText('FastGenerate SQL logo')).toBeInTheDocument()
  })

  it('renders the generated FastGenerate SQL logo in the sidebar', () => {
    render(SidebarHarness)

    expect(screen.getByAltText('FastGenerate SQL logo')).toBeInTheDocument()
  })
})
