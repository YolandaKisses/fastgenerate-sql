<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, h } from "vue";
import {
  NLayout,
  NTree,
  NScrollbar,
  NEmpty,
  NSpin,
  useMessage,
  type TreeOption,
  NIcon,
  NSplit,
} from "naive-ui";
import {
  FolderOutline,
  DocumentTextOutline,
  BookOutline,
  EarthOutline,
} from "@vicons/ionicons5";
import MarkdownIt from "markdown-it";
import container from "markdown-it-container";
import hljs from "highlight.js";
import "highlight.js/styles/github.css";
import { get } from "../../services/request";
import { useRoute, useRouter } from "vue-router";

const message = useMessage();
const route = useRoute();
const router = useRouter();

const treeData = ref<TreeOption[]>([]);
const expandedKeys = ref<string[]>([]);
const currentContent = ref("");
const currentPath = ref("");
const isLoadingTree = ref(false);
const isLoadingContent = ref(false);

// 初始化 MarkdownIt
const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, { language: lang }).value;
      } catch (__) {}
    }
    return ""; // 使用默认的转义
  },
});

// 添加自定义容器支持 (VuePress 风格)
const containers = ["tip", "warning", "danger", "info", "details"];
containers.forEach((type) => {
  md.use(container, type, {
    render: function (tokens: any[], idx: number) {
      const m = tokens[idx].info.trim().match(new RegExp(`^${type}\\s*(.*)$`));
      if (tokens[idx].nesting === 1) {
        const title = m && m[1] ? m[1] : "";
        if (type === "details") {
          const summary = title
            ? `<summary class="custom-container-title">${title}</summary>`
            : "";
          return `<details class="custom-container ${type}">${summary}\n`;
        }
        const titleBlock = title
          ? `<p class="custom-container-title">${title}</p>\n`
          : "";
        return `<div class="custom-container ${type}">${titleBlock}`;
      } else {
        if (type === "details") {
          return "</details>\n";
        }
        return "</div>\n";
      }
    },
  });
});

const fetchTree = async () => {
  isLoadingTree.value = true;
  try {
    const data = await get("/wiki/tree");
    treeData.value = transformToTreeOptions(data);

    // 如果 URL 中有初始路径，尝试加载
    const initialPath = route.query.path as string;
    if (initialPath) {
      loadContent(initialPath);
    } else if (treeData.value.length > 0) {
      // 默认加载目录中的第一个 Markdown 文件
      const firstFile = findFirstFile(treeData.value);
      if (firstFile) loadContent(firstFile);
    }
  } catch (err) {
    message.error("加载目录树失败");
  } finally {
    isLoadingTree.value = false;
  }
};

const renderIcon = (icon: any) => {
  return () => h(NIcon, null, { default: () => h(icon) });
};

const normalizeLabel = (value: string) => value.replace(/\.(md|html)$/i, "");

type TreeStats = {
  documents: number;
  sections: number;
};

const collectTreeStats = (options: TreeOption[]): TreeStats => {
  return options.reduce<TreeStats>(
    (acc, option) => {
      if (option.isLeaf) {
        acc.documents += 1;
      } else {
        acc.sections += 1;
      }

      if (option.children) {
        const childStats = collectTreeStats(option.children);
        acc.documents += childStats.documents;
        acc.sections += childStats.sections;
      }

      return acc;
    },
    { documents: 0, sections: 0 },
  );
};

const treeStats = computed(() => collectTreeStats(treeData.value));

const currentDocumentTitle = computed(() => {
  if (!currentPath.value) return "选择一篇文档开始阅读";
  const name = currentPath.value.split("/").pop() || currentPath.value;
  return normalizeLabel(name);
});

const currentPathSegments = computed(() => {
  if (!currentPath.value) return [];
  return currentPath.value.split("/").map((segment) => normalizeLabel(segment));
});

const renderTreeLabel = ({ option }: { option: TreeOption }) => {
  const key = String(option.key ?? "");
  const isDirectory = !option.isLeaf;
  const isActive = key === currentPath.value;
  const isAncestor =
    isDirectory &&
    !isActive &&
    Boolean(currentPath.value) &&
    currentPath.value.startsWith(`${key}/`);

  return h(
    "span",
    {
      class: [
        "wiki-tree-label",
        isDirectory ? "is-directory" : "is-document",
        isActive ? "is-active" : "",
        isAncestor ? "is-ancestor" : "",
      ],
    },
    [
      h(
        "span",
        { class: "wiki-tree-label__title" },
        String(option.label ?? ""),
      ),
      !isDirectory
        ? h(
            "span",
            { class: "wiki-tree-label__meta" },
            key.endsWith(".html") ? "HTML" : "Markdown",
          )
        : null,
    ],
  );
};

const transformToTreeOptions = (nodes: any[]): TreeOption[] => {
  return nodes.map((node) => {
    let icon = DocumentTextOutline;
    if (node.isDir) {
      icon = FolderOutline;
    } else if (node.path.endsWith(".html")) {
      icon = EarthOutline;
    }

    return {
      label: node.name,
      key: node.path,
      isLeaf: !node.isDir,
      prefix: renderIcon(icon),
      children: node.children
        ? transformToTreeOptions(node.children)
        : undefined,
    };
  });
};

const findFirstFile = (options: TreeOption[]): string | null => {
  for (const opt of options) {
    if (opt.isLeaf) return opt.key as string;
    if (opt.children) {
      const found = findFirstFile(opt.children);
      if (found) return found;
    }
  }
  return null;
};

const isHtmlFile = ref(false);
const iframeUrl = ref("");

// 提取路径的所有父目录
const getParentPaths = (path: string): string[] => {
  const parts = path.split("/");
  const parents: string[] = [];
  for (let i = 1; i < parts.length; i++) {
    parents.push(parts.slice(0, i).join("/"));
  }
  return parents;
};

const loadContent = async (path: string) => {
  if (!path.endsWith(".md") && !path.endsWith(".html")) return;

  isLoadingContent.value = false; // 先重置
  currentPath.value = path;
  isLoadingContent.value = true;
  isHtmlFile.value = path.endsWith(".html");

  // 联动展开左侧目录
  const parents = getParentPaths(path);
  parents.forEach((p) => {
    if (!expandedKeys.value.includes(p)) {
      expandedKeys.value.push(p);
    }
  });

  if (isHtmlFile.value) {
    // 构造 raw 接口 URL (使用路径参数模式以支持相对路径)
    const baseUrl = import.meta.env.VITE_API_BASE_URL || "/api/v1";
    iframeUrl.value = `${baseUrl}/wiki/raw/${path}`;
    currentContent.value = "";
    isLoadingContent.value = false;
    router.replace({ query: { ...route.query, path } });
    return;
  }

  try {
    const data = await get(`/wiki/content?path=${encodeURIComponent(path)}`);
    let rawContent = data.content;

    // 提取并格式化 YAML Frontmatter
    const frontmatterRegex = /^---\r?\n([\s\S]*?)\r?\n---(\r?\n|$)/;
    const match = rawContent.match(frontmatterRegex);
    if (match) {
      const yamlContent = match[1];
      rawContent = rawContent.replace(
        frontmatterRegex,
        `::: info 📄 元数据 (Frontmatter)\n\`\`\`yaml\n${yamlContent}\n\`\`\`\n:::\n\n`,
      );
    }

    currentContent.value = md.render(rawContent);

    // 更新 URL，方便刷新
    router.replace({ query: { ...route.query, path } });
  } catch (err) {
    message.error("加载内容失败");
    currentContent.value = "";
  } finally {
    isLoadingContent.value = false;
  }
};

const handleSelect = (keys: string[]) => {
  if (keys.length > 0) {
    loadContent(keys[0]);
  }
};

// 拦截 Markdown 中的链接点击
const handleContentClick = (e: MouseEvent) => {
  const target = e.target as HTMLElement;
  const a = target.closest("a");
  if (a && a.getAttribute("href")) {
    const href = a.getAttribute("href") || "";
    // 处理相对路径链接
    if (
      (href.endsWith(".md") || href.endsWith(".html")) &&
      !href.startsWith("http")
    ) {
      e.preventDefault();
      // 计算相对路径
      const basePath = currentPath.value.split("/").slice(0, -1).join("/");
      let targetPath = "";
      if (href.startsWith("./")) {
        targetPath = basePath ? `${basePath}/${href.slice(2)}` : href.slice(2);
      } else if (href.startsWith("../")) {
        const parts = basePath.split("/");
        parts.pop();
        const newBase = parts.join("/");
        targetPath = newBase ? `${newBase}/${href.slice(3)}` : href.slice(3);
      } else {
        targetPath = basePath ? `${basePath}/${href}` : href;
      }
      loadContent(targetPath);
    }
  }
};

// 监听 iframe 发来的跳转请求
const handleMessage = (e: MessageEvent) => {
  if (e.data && e.data.type === "wiki-navigate") {
    const relativePath = e.data.path;
    // 计算绝对路径 (相对于 wiki 根目录)
    const currentDir = currentPath.value.split("/").slice(0, -1).join("/");
    const targetPath = currentDir
      ? `${currentDir}/${relativePath}`
      : relativePath;
    loadContent(targetPath);
  }
};

onMounted(() => {
  window.addEventListener("message", handleMessage);
  fetchTree();
});

onUnmounted(() => {
  window.removeEventListener("message", handleMessage);
});
</script>

<template>
  <div class="wiki-page">
    <n-layout position="absolute">
      <n-split
        direction="horizontal"
        default-size="480px"
        min="200px"
        max="600px"
      >
        <template #1>
          <div
            class="wiki-sider"
            style="
              display: flex;
              flex-direction: column;
              height: 100%;
              overflow: hidden;
            "
          >
            <div class="sider-backdrop"></div>
            <div class="sider-header">
              <div class="sider-header__eyebrow">
                <n-icon size="16" color="#3b82f6">
                  <BookOutline />
                </n-icon>
                <span>Wiki Navigation</span>
              </div>
              <div class="sider-header__title-row">
                <span class="sider-title">知识目录</span>
                <span class="sider-stat">{{ treeStats.documents }} 篇</span>
              </div>
              <p class="sider-description">
                像文档站一样浏览、定位和追踪当前知识路径。
              </p>
              <div class="sider-overview">
                <span>{{ treeStats.sections }} 个分组</span>
                <span class="sider-overview__dot"></span>
                <span>{{ isHtmlFile ? "HTML 页面" : "Markdown 文档" }}</span>
              </div>
              <div class="sider-active-card">
                <span class="sider-active-card__label">当前阅读</span>
                <strong class="sider-active-card__title">{{
                  currentDocumentTitle
                }}</strong>
                <div
                  v-if="currentPathSegments.length"
                  class="sider-breadcrumbs"
                >
                  <span
                    v-for="(segment, index) in currentPathSegments"
                    :key="`${segment}-${index}`"
                    class="sider-breadcrumbs__item"
                  >
                    {{ segment }}
                  </span>
                </div>
              </div>
            </div>
            <div class="sider-content">
              <n-scrollbar>
                <div class="tree-container">
                  <n-spin :show="isLoadingTree">
                    <n-tree
                      block-line
                      :data="treeData"
                      :render-label="renderTreeLabel"
                      :selected-keys="[currentPath]"
                      :expanded-keys="expandedKeys"
                      @update:selected-keys="handleSelect"
                      @update:expanded-keys="(keys) => (expandedKeys = keys)"
                      expand-on-click
                    />
                  </n-spin>
                </div>
              </n-scrollbar>
            </div>
          </div>
        </template>
        <template #2>
          <div
            class="wiki-main"
            style="
              display: flex;
              flex-direction: column;
              height: 100%;
              overflow: hidden;
            "
          >
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
                    <n-empty
                      v-else-if="!isLoadingContent"
                      description="请从左侧选择一个文档查看"
                    />
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
  background:
    radial-gradient(
      circle at top left,
      rgba(59, 130, 246, 0.08),
      transparent 26%
    ),
    linear-gradient(180deg, #f8fbff 0%, #ffffff 20%, #ffffff 100%);
}

.wiki-sider {
  position: relative;
  background: linear-gradient(
    180deg,
    rgba(248, 250, 252, 0.98),
    rgba(255, 255, 255, 0.98)
  );
  border-right: 1px solid rgba(226, 232, 240, 0.8);
  box-shadow: inset -1px 0 0 rgba(255, 255, 255, 0.9);
}

.sider-backdrop {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(circle at top, rgba(191, 219, 254, 0.35), transparent 34%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.6), rgba(248, 250, 252, 0));
}

.sider-header {
  position: relative;
  padding: 18px 18px 14px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.85);
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.sider-header__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #3b82f6;
}

.sider-header__title-row {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.sider-title {
  font-size: 18px;
  line-height: 1.2;
  font-weight: 700;
  color: #0f172a;
  white-space: nowrap;
}

.sider-stat {
  padding: 4px 9px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
  font-size: 11px;
  font-weight: 700;
}

.sider-description {
  margin: 0;
  font-size: 12px;
  line-height: 1.55;
  color: #64748b;
}

.sider-overview {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #64748b;
  font-size: 12px;
  font-weight: 500;
}

.sider-overview__dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #cbd5e1;
}

.sider-active-card {
  width: 100%;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid rgba(191, 219, 254, 0.9);
  background: linear-gradient(
    180deg,
    rgba(255, 255, 255, 0.95),
    rgba(239, 246, 255, 0.92)
  );
  box-shadow: 0 10px 22px rgba(148, 163, 184, 0.1);
}

.sider-active-card__label {
  display: block;
  margin-bottom: 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #64748b;
}

.sider-active-card__title {
  display: block;
  color: #0f172a;
  font-size: 13px;
  line-height: 1.45;
  word-break: break-word;
}

.sider-breadcrumbs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
}

.sider-breadcrumbs__item {
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  color: #475569;
  font-size: 11px;
  line-height: 1.2;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sider-content {
  flex: 1;
  min-height: 0;
  position: relative;
  background-color: transparent;
}

.main-content-scroll {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.tree-container {
  padding: 14px 10px 20px;
}

:deep(.n-tree-node) {
  align-items: center;
  margin-bottom: 4px;
}

:deep(.n-tree-node-switcher) {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 8px;
  color: #94a3b8;
  transition:
    background-color 0.2s ease,
    color 0.2s ease,
    transform 0.2s ease;
}

:deep(.n-tree-node-switcher:hover) {
  background: rgba(226, 232, 240, 0.8);
  color: #475569;
}

:deep(.n-tree-node-switcher__icon) {
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
}

:deep(.n-tree-node-content) {
  display: flex;
  align-items: center;
  min-height: 42px;
  padding: 4px 8px 4px 6px;
  border-radius: 14px;
  transition:
    background-color 0.2s ease,
    transform 0.2s ease;
}

:deep(.n-tree-node-content:hover) {
  background: rgba(241, 245, 249, 0.92);
  transform: translateX(1px);
}

:deep(.n-tree-node-content__prefix) {
  display: flex;
  align-items: center;
  margin-right: 10px;
  font-size: 16px;
  color: #94a3b8;
  transition: color 0.2s ease;
}

:deep(.n-tree-node-content__text) {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
}

:deep(.n-tree-node-content:hover .n-tree-node-content__prefix) {
  color: #64748b;
}

:deep(.n-tree-node--selected > .n-tree-node-content) {
  background: linear-gradient(
    90deg,
    rgba(219, 234, 254, 0.95),
    rgba(239, 246, 255, 0.92)
  );
  box-shadow: inset 3px 0 0 #2563eb;
}

:deep(
  .n-tree-node--selected > .n-tree-node-content .n-tree-node-content__prefix
) {
  color: #2563eb;
}

:deep(.wiki-tree-label) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  min-width: 0;
}

:deep(.wiki-tree-label__title) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  line-height: 1.35;
  color: #334155;
  transition:
    color 0.2s ease,
    font-weight 0.2s ease;
}

:deep(.wiki-tree-label__meta) {
  flex-shrink: 0;
  padding: 3px 7px;
  border-radius: 999px;
  background: rgba(241, 245, 249, 0.95);
  color: #94a3b8;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

:deep(.wiki-tree-label.is-directory .wiki-tree-label__title) {
  font-size: 13px;
  font-weight: 700;
  color: #64748b;
  letter-spacing: 0.01em;
}

:deep(.wiki-tree-label.is-ancestor .wiki-tree-label__title) {
  color: #0f172a;
}

:deep(.wiki-tree-label.is-active .wiki-tree-label__title) {
  color: #1d4ed8;
  font-weight: 700;
}

:deep(.wiki-tree-label.is-active .wiki-tree-label__meta) {
  background: rgba(219, 234, 254, 0.95);
  color: #2563eb;
}

.wiki-main {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 1)),
    #fff;
}

.content-wrapper {
  max-width: 900px;
  margin: 0 auto;
  padding: 40px 60px;
}

/* Markdown 样式补充 */
:deep(.markdown-body) {
  font-family:
    -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 16px;
  line-height: 1.6;
  color: #24292e;
}

:deep(.markdown-body h1) {
  font-size: 2em;
  border-bottom: 1px solid #eaecef;
  padding-bottom: 0.3em;
  margin-top: 24px;
  margin-bottom: 16px;
}
:deep(.markdown-body h2) {
  font-size: 1.5em;
  border-bottom: 1px solid #eaecef;
  padding-bottom: 0.3em;
  margin-top: 24px;
  margin-bottom: 16px;
}
:deep(.markdown-body h3) {
  font-size: 1.25em;
  margin-top: 24px;
  margin-bottom: 16px;
}

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

:deep(.markdown-body table th),
:deep(.markdown-body table td) {
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

:deep(.n-layout) {
  background: transparent !important;
}

:deep(.n-split) {
  height: 100%;
}

:deep(.n-split-pane) {
  overflow: hidden;
}

:deep(.n-split__resize-trigger-wrapper) {
  z-index: 30 !important;
  cursor: col-resize !important;
}

:deep(.n-split__resize-trigger) {
  cursor: col-resize !important;
}

@media (max-width: 960px) {
  .wiki-page {
    margin: -16px -16px;
  }

  .sider-header {
    padding: 20px 16px 16px;
  }

  .content-wrapper {
    padding: 28px 24px 40px;
  }
}
</style>
