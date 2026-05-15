# TODO

## 功能拓展

### 多配图方式拓展

- [X] 实现 `ImageSearchService` 抽象接口，支持多配图方式的搜索和处理。
- [ ] Nano Banana（Gemini AI 生图）
- [X] Mermaid 流程图
- [X] Iconify 图标库，检索开源图标
- [X] 表情包搜索：基于 Bing 图片检索表情包
- [X] SVG 概念示意图：使用 AI 生成矢量图
- [X] 腾讯云 COS 统一上传：所有配图统一存储管理
- [X] AI 根据内容自动选择配图方式
- [ ] 用户上传图片

### 用户交互增强

- [X] AI 生成多个标题方案供用户选择
- [X] 支持章节修改、AI 辅助修改大纲

## BUG 修复

- [ ] 腾讯云 COS 图片无法访问
- [ ] confirm 绕过 update_phase
- [ ] asyncio.create_task GC 风险
- [ ] phase2-3 未重置 status
- [ ] agent2 缺 None 校验
- [ ] 配额检查名不副实

## 测试

- [ ] 测试图片服务的稳定性