import { createApp, h } from 'vue'
import { createPinia } from 'pinia'
import { NConfigProvider, GlobalThemeOverrides, zhCN, dateZhCN } from 'naive-ui'
import App from './App.vue'
import { router } from './router'

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#2080f0',
    primaryColorHover: '#4098fc',
    primaryColorPressed: '#1060c9',
    primaryColorSuppl: '#4098fc',
    borderRadius: '4px',
    textColor1: '#181c22',
    textColor2: '#414753',
    textColor3: '#717785',
    borderColor: '#efeff5',
    bodyColor: '#fbfcfd',
    cardColor: '#ffffff'
  },
  Card: {
    borderRadius: '8px',
    borderColor: '#efeff5',
  }
}

const app = createApp({
  render: () =>
    h(NConfigProvider, { themeOverrides, locale: zhCN, dateLocale: dateZhCN }, {
      default: () => h(App)
    })
})

app.use(createPinia())
app.use(router)
app.mount('#app')
