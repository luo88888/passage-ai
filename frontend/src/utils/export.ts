/**
 * 文章导出工具：支持导出 Markdown 与渲染后的 HTML 两种格式
 */
import { marked } from 'marked'
import DOMPurify from 'dompurify'

/** 触发浏览器下载 */
function download(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/** 清洗文件名中的非法字符 */
function safeFilename(name: string): string {
  const cleaned = (name || '').replace(/[\\/:*?"<>|]/g, '').trim()
  return cleaned || 'article'
}

/**
 * 导出原始 Markdown（含图片 markdown 语法）
 */
export function exportMarkdown(name: string, mdContent: string) {
  if (!mdContent) return
  download(`${safeFilename(name)}.md`, mdContent, 'text/markdown;charset=utf-8')
}

/**
 * 导出渲染后的 HTML（图片以链接形式嵌入，附带基础排版样式，可独立打开）
 */
export function exportHtml(name: string, mdContent: string) {
  if (!mdContent) return
  const body = DOMPurify.sanitize(marked.parse(mdContent) as string)
  const html = `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${safeFilename(name)}</title>
<style>
body{max-width:840px;margin:40px auto;padding:0 20px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Work Sans',sans-serif;line-height:1.8;color:#0F172A}
h1,h2,h3{font-family:'Outfit',-apple-system,sans-serif;line-height:1.3}
img{max-width:100%;border-radius:12px;margin:16px 0}
pre{background:#F1F5F9;padding:14px 16px;border-radius:8px;overflow:auto}
code{background:#F1F5F9;padding:2px 6px;border-radius:4px;font-size:0.92em}
blockquote{border-left:4px solid #22C55E;margin:0;padding:4px 16px;color:#475569;background:#F8FAFC;border-radius:0 8px 8px 0}
a{color:#16A34A}
</style>
</head>
<body>
${body}
</body>
</html>`
  download(`${safeFilename(name)}.html`, html, 'text/html;charset=utf-8')
}

/**
 * 复制文本到剪贴板（优先 Clipboard API，非安全上下文用 execCommand 兜底）
 *
 * Args:
 *     text: 要复制的文本内容。
 *
 * Returns:
 *     是否复制成功。
 */
export async function copyText(text: string): Promise<boolean> {
  if (!text) return false
  // 优先使用现代 Clipboard API（需要 https 或 localhost 安全上下文）
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch (e) {
    // 失败则走下面的兜底方案
  }
  // 兜底：隐藏 textarea + execCommand('copy')
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return ok
  } catch (e) {
    return false
  }
}
