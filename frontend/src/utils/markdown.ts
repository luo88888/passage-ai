/**
 * Markdown 渲染封装
 * 使用 marked 解析，输出经 DOMPurify 净化后返回安全的 HTML 字符串。
 */
import { marked } from 'marked'
import DOMPurify from 'dompurify'

// 基础配置：开启 GitHub 风格 markdown + 换行转 <br>
marked.setOptions({
  breaks: true,
  gfm: true,
})

/**
 * 将 markdown 字符串渲染为净化后的 HTML
 *
 * dompurify v3 的默认导出在浏览器环境下会自动绑定 .sanitize 方法；
 * 此处直接调用，运行在浏览器（Vite 应用前端）中。
 */
export function renderMarkdown(md: string | undefined | null): string {
  if (!md) return ''
  try {
    const raw = marked.parse(md) as string
    return DOMPurify.sanitize(raw)
  } catch (e) {
    console.error('markdown 渲染失败:', e)
    return ''
  }
}