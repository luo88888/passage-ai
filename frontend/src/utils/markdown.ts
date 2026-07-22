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
 *
 * 注：正文撰写阶段会插入 <imageN>描述</imageN> 图片标签（类似未知 HTML 自定义标签）。
 * 若直接交给 marked + DOMPurify，DOMPurify 会把不在白名单的未知标签连同内容剥离，导致
 * 流式预览里看不到图片占位信息。因此渲染前先把 <imageN>描述</imageN> 转成可见的文本占位符
 * 【配图N：描述】，仅作用于预览渲染，不影响后端标签契约（后端仍按原标签解析配图）。
 */
// 匹配 <image1>描述</image1> 这类配图占位标签（N 为数字，描述可包含中文/字母/符号）
const IMAGE_TAG_RE = /<image(\d+)>([\s\S]*?)<\/image\1>/g

/** 把正文里的 <imageN>描述</imageN> 标签转成可见的文本占位符（仅用于预览渲染） */
function visualizeImageTags(md: string): string {
  return md.replace(IMAGE_TAG_RE, (_m, n: string, desc: string) => {
    const d = (desc || '').trim() || '（未填写描述）'
    return `【配图${n}：${d}】`
  })
}

export function renderMarkdown(md: string | undefined | null): string {
  if (!md) return ''
  try {
    const visualized = visualizeImageTags(md)
    const raw = marked.parse(visualized) as string
    return DOMPurify.sanitize(raw)
  } catch (e) {
    console.error('markdown 渲染失败:', e)
    return ''
  }
}