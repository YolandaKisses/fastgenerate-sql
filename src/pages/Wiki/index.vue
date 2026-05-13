<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, h } from 'vue'
import { 
  NLayout, NLayoutSider, NLayoutContent, NTree, NScrollbar, NEmpty, NSpin,
  useMessage, type TreeOption, NIcon, NSplit
} from 'naive-ui'
import { FolderOutline, DocumentTextOutline, BookOutline, EarthOutline } from '@vicons/ionicons5'
import MarkdownIt from 'markdown-it'
import container from 'markdown-it-container'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import { get } from '../../services/request'
import { useRoute, useRouter } from 'vue-router'

const message = useMessage()
const route = useRoute()
const router = useRouter()

const treeData = ref<TreeOption[]>([])
const expandedKeys = ref<string[]>([])
const currentContent = ref('')
const currentPath = ref('')
const isLoadingTree = ref(false)
const isLoadingContent = ref(false)

// 初始化 MarkdownIt
const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, { language: lang }).value
      } catch (__) {}
    }
    return '' // 使用默认的转义
  }
})

// 添加自定义容器支持 (VuePress 风格)
const containers = ['tip', 'warning', 'danger', 'info', 'details']
containers.forEach(type => {
  md.use(container, type, {
    render: function (tokens, idx) {
      const m = tokens[idx].info.trim().match(new RegExp(`^${type}\\s*(.*)$`))
      if (tokens[idx].nesting === 1) {
        const title = m && m[1] ? m[1] : ''
        if (type === 'details') {
          const summary = title ? `<summary class="custom-container-title">${title}</summary>` : ''
          return `<details class="custom-container ${type}">${summary}\n`
        }
        const titleBlock = title ? `<p class="custom-container-title">${title}</p>\n` : ''
        return `<div class="custom-container ${type}">${titleBlock}`
      } else {
        if (type === 'details') {
          return '</details>\n'
        }
        return '</div>\n'
      }
    }
  })
})

const fetchTree = async () => {
  isLoadingTree.value = true
  try {
    const data = await get('/wiki/tree')
    treeData.value = transformToTreeOptions(data)
    
    // 如果 URL 中有初始路径，尝试加载
    const initialPath = route.query.path as string
    if (initialPath) {
      loadContent(initialPath)
    } else if (treeData.value.length > 0) {
      // 默认加载目录中的第一个 Markdown 文件
      const firstFile = findFirstFile(treeData.value)
      if (firstFile) loadContent(firstFile)
    }
  } catch (err) {
    message.error('加载目录树失败')
  } finally {
    isLoadingTree.value = false
  }
}

const renderIcon = (icon: any) => {
  return () => h(NIcon, null, { default: () => h(icon) })
}

const transformToTreeOptions = (nodes: any[]): TreeOption[] => {
  return nodes.map(node => {
    let icon = DocumentTextOutline
    if (node.isDir) {
      icon = FolderOutline
    } else if (node.path.endsWith('.html')) {
      icon = EarthOutline
    }
    
    return {
      label: node.name,
      key: node.path,
      isLeaf: !node.isDir,
      prefix: renderIcon(icon),
      children: node.children ? transformToTreeOptions(node.children) : undefined
    }
  })
}

const findFirstFile = (options: TreeOption[]): string | null => {
  for (const opt of options) {
    if (opt.isLeaf) return opt.key as string
    if (opt.children) {
      const found = findFirstFile(opt.children)
      if (found) return found
    }
  }
  return null
}

const isHtmlFile = ref(false)
const iframeUrl = ref('')

// 提取路径的所有父目录
const getParentPaths = (path: string): string[] => {
  const parts = path.split('/')
  const parents: string[] = []
  for (let i = 1; i < parts.length; i++) {
    parents.push(parts.slice(0, i).join('/'))
  }
  return parents
}

const loadContent = async (path: string) => {
  if (!path.endsWith('.md') && !path.endsWith('.html')) return
  
  isLoadingContent.value = false // 先重置
  currentPath.value = path
  isLoadingContent.value = true
  isHtmlFile.value = path.endsWith('.html')
  
  // 联动展开左侧目录
  const parents = getParentPaths(path)
  parents.forEach(p => {
    if (!expandedKeys.value.includes(p)) {
      expandedKeys.value.push(p)
    }
  })
  
  if (isHtmlFile.value) {
    // 构造 raw 接口 URL (使用路径参数模式以支持相对路径)
    const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    iframeUrl.value = `${baseUrl}/wiki/raw/${path}`
    currentContent.value = ''
    isLoadingContent.value = false
    router.replace({ query: { ...route.query, path } })
    return
  }

  try {
    const data = await get(`/wiki/content?path=${encodeURIComponent(path)}`)
    let rawContent = data.content
    
    // 提取并格式化 YAML Frontmatter
    const frontmatterRegex = /^---\r?\n([\s\S]*?)\r?\n---(\r?\n|$)/
    const match = rawContent.match(frontmatterRegex)
    if (match) {
      const yamlContent = match[1]
      rawContent = rawContent.replace(frontmatterRegex, `::: info 📄 元数据 (Frontmatter)\n\`\`\`yaml\n${yamlContent}\n\`\`\`\n:::\n\n`)
    }
    
    currentContent.value = md.render(rawContent)
    
    // 更新 URL，方便刷新
    router.replace({ query: { ...route.query, path } })
  } catch (err) {
    message.error('加载内容失败')
    currentContent.value = ''
  } finally {
    isLoadingContent.value = false
  }
}

const handleSelect = (keys: string[]) => {
  if (keys.length > 0) {
    loadContent(keys[0])
  }
}

// 拦截 Markdown 中的链接点击
const handleContentClick = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  const a = target.closest('a')
  if (a && a.getAttribute('href')) {
    const href = a.getAttribute('href') || ''
    // 处理相对路径链接
    if ((href.endsWith('.md') || href.endsWith('.html')) && !href.startsWith('http')) {
      e.preventDefault()
      // 计算相对路径
      const basePath = currentPath.value.split('/').slice(0, -1).join('/')
      let targetPath = ''
      if (href.startsWith('./')) {
        targetPath = basePath ? `${basePath}/${href.slice(2)}` : href.slice(2)
      } else if (href.startsWith('../')) {
        const parts = basePath.split('/')
        parts.pop()
        const newBase = parts.join('/')
        targetPath = newBase ? `${newBase}/${href.slice(3)}` : href.slice(3)
      } else {
        targetPath = basePath ? `${basePath}/${href}` : href
      }
      loadContent(targetPath)
    }
  }
}

// 监听 iframe 发来的跳转请求
const handleMessage = (e: MessageEvent) => {
  if (e.data && e.data.type === 'wiki-navigate') {
    const relativePath = e.data.path
    // 计算绝对路径 (相对于 wiki 根目录)
    const currentDir = currentPath.value.split('/').slice(0, -1).join('/')
    const targetPath = currentDir ? `${currentDir}/${relativePath}` : relativePath
    loadContent(targetPath)
  }
}

onMounted(() => {
  window.addEventListener('message', handleMessage)
  fetchTree()
})

onUnmounted(() => {
  window.removeEventListener('message', handleMessage)
})
</script>

<template>
  <div class="wiki-page">
    <n-layout position="absolute">
      <n-split direction="horizontal" default-size="280px" min="200px" max="600px">
        <template #1>
          <div class="wiki-sider" style="display: flex; flex-direction: column; height: 100%; overflow: hidden;">
            <div class="sider-header">
              <n-icon size="20" color="#18a058">
                <BookOutline />
              </n-icon>
              <span>知识目录</span>
            </div>
            <div class="sider-content">
              <n-scrollbar>
                <div class="tree-container">
                  <n-spin :show="isLoadingTree">
                    <n-tree
                      block-line
                      :data="treeData"
                      :selected-keys="[currentPath]"
                      :expanded-keys="expandedKeys"
                      @update:selected-keys="handleSelect"
                      @update:expanded-keys="(keys) => expandedKeys = keys"
                      expand-on-click
                    />
                  </n-spin>
                </div>
              </n-scrollbar>
            </div>
          </div>
        </template>
        <template #2>
          <div class="wiki-main" style="display: flex; flex-direction: column; height: 100%; overflow: hidden;">
            <div class="main-content-scroll">
              <n-scrollbar v-if="!isHtmlFile">
                <div class="content-wrapper">
                  <n-spin :show="isLoadingContent">
                    <div 
                      v-if="currentContent" 
                      class="markdown-body" 
                      v-html="currentContent"
                      @click="handleContentClick"
                    ></div>
                    <n-empty v-else-if="!isLoadingContent" description="请从左侧选择一个文档查看" />
                  </n-spin>
                </div>
              </n-scrollbar>
              <div v-else class="iframe-wrapper">
                <iframe :src="iframeUrl" class="wiki-iframe"></iframe>
              </div>
            </div>
          </div>
        </template>
      </n-split>
    </n-layout>
  </div>
</template>

<style scoped>
.wiki-page {
  position: relative;
  height: calc(100vh - 64px);
  margin: -24px -40px; /* 抵消 page-container 的 padding */
  background: #fff;
}

.wiki-sider {
  background: #fbfcfd;
  border-right: 1px solid #efeff5;
}

.sider-header {
  padding: 18px 24px;
  font-weight: 600;
  font-size: 16px;
  border-bottom: 1px solid #efeff5;
  color: #1f2225;
  display: flex;
  align-items: center;
  gap: 10px;
}

.sider-content {
  flex: 1;
  min-height: 0;
  background-color: #fbfcfd;
}

.main-content-scroll {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.tree-container {
  padding: 12px 8px;
}

:deep(.n-tree-node) {
  align-items: center;
}

:deep(.n-tree-node-switcher) {
  display: flex;
  align-items: center;
  justify-content: center;
}

:deep(.n-tree-node-switcher__icon) {
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
}

:deep(.n-tree-node-content) {
  display: flex;
  align-items: center;
  padding: 6px 0;
}

:deep(.n-tree-node-content__prefix) {
  display: flex;
  align-items: center;
  margin-right: 8px;
  font-size: 18px;
}

:deep(.n-tree-node-content__text) {
  font-size: 14px;
  color: #333639;
  line-height: 1;
  display: flex;
  align-items: center;
}

.wiki-main {
  background: #fff;
}

.content-wrapper {
  max-width: 900px;
  margin: 0 auto;
  padding: 40px 60px;
}

/* Markdown 样式补充 */
:deep(.markdown-body) {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 16px;
  line-height: 1.6;
  color: #24292e;
}

:deep(.markdown-body h1) { font-size: 2em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; margin-top: 24px; margin-bottom: 16px; }
:deep(.markdown-body h2) { font-size: 1.5em; border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; margin-top: 24px; margin-bottom: 16px; }
:deep(.markdown-body h3) { font-size: 1.25em; margin-top: 24px; margin-bottom: 16px; }

:deep(.markdown-body code) {
  background-color: rgba(27, 31, 35, 0.05);
  border-radius: 3px;
  font-size: 85%;
  margin: 0;
  padding: 0.2em 0.4em;
  font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
}

:deep(.markdown-body pre) {
  background-color: #f6f8fa;
  border-radius: 6px;
  font-size: 85%;
  line-height: 1.45;
  overflow: auto;
  padding: 16px;
  margin-bottom: 16px;
}

:deep(.markdown-body pre code) {
  background-color: transparent;
  padding: 0;
}

:deep(.markdown-body table) {
  border-collapse: collapse;
  width: 100%;
  margin-bottom: 16px;
}

:deep(.markdown-body table th), :deep(.markdown-body table td) {
  border: 1px solid #dfe2e5;
  padding: 6px 13px;
}

:deep(.markdown-body table tr:nth-child(2n)) {
  background-color: #f6f8fa;
}

:deep(.markdown-body a) {
  color: #0366d6;
  text-decoration: none;
}

:deep(.markdown-body a:hover) {
  text-decoration: underline;
}

/* 自定义容器 (VuePress 风格) */
:deep(.custom-container) {
  padding: 0.1rem 1.5rem;
  border-left-width: 0.5rem;
  border-left-style: solid;
  margin: 1rem 0;
}

:deep(.custom-container .custom-container-title) {
  font-weight: 600;
  margin-bottom: -0.4rem;
}

:deep(.custom-container.tip) {
  background-color: #f3f5f7;
  border-color: #42b983;
}

:deep(.custom-container.warning) {
  background-color: #fff7d0;
  border-color: #e7c000;
  color: #6b5900;
}

:deep(.custom-container.danger) {
  background-color: #ffe6e6;
  border-color: #c00;
  color: #4d0000;
}

:deep(.custom-container.info) {
  background-color: #eef9fd;
  border-color: #2080f0;
}

:deep(.custom-container.details) {
  background-color: #f8f8f8;
  border-color: #d1d5db;
}

:deep(.custom-container.details summary) {
  cursor: pointer;
  outline: none;
  margin-bottom: 0.5rem;
  padding-top: 0.5rem;
  padding-bottom: 0.5rem;
}

.iframe-wrapper {
  flex: 1;
  width: 100%;
  height: 100%;
  overflow: hidden;
  display: flex;
}

.wiki-iframe {
  width: 100%;
  height: 100%;
  border: none;
  background: #1e1e1e;
  flex: 1;
}
</style>
