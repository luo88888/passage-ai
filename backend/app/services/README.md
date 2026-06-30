# 配图模块说明

## 整体架构

```
用户请求（topic + 可选 enabledImageMethods）
  │
  ▼
ArticleAgentOrchestrator（编排 5 个智能体）
  │
  ├─ Agent1: 标题生成
  ├─ Agent2: 大纲生成
  ├─ Agent3: 正文生成
  ├─ Agent4: 配图需求分析 ─── 读 build_image_methods_guide() → 输出 ImageRequirement[]
  └─ Agent5: 图片获取      ─── 调 ParallelImageGenerator.generate() → 并行拉图
         │
         ▼
  ParallelImageGenerator（策略调度 + 并行控制）
         │
         ├─ service_map: Dict[ImageMethodEnum, BaseImageSearchService]
         │    ├─ PexelsService       → Pexels API 搜索真实图（URL 类型）
         │    ├─ MermaidService      → mmdc CLI 渲染流程图（BYTES 类型）
         │    ├─ IconifyService      → 开源图标库检索（URL 类型）
         │    ├─ EmojiPackService    → Bing 搜表情包（URL 类型）
         │    └─ SvgDiagramService   → LLM 生成 SVG 矢量图（BYTES 类型）
         │
         └─ get_image_and_upload(): get_image_data() → LocalFileService.upload_image_data() → URL
              异常或失败 → 降级到 PICSUM 兜底图
```

## 核心文件

| 文件 | 职责 |
|---|---|
| `app/models/enums.py` | `ImageMethodEnum` — 定义所有配图方式（value/label/description/是否AI生图/是否兜底） |
| `app/schemas/image.py` | `ImageRequest`（请求入参）、`ImageData`（字节/URL/dataURL 三种类型封装） |
| `app/services/image_search_service.py` | `BaseImageSearchService` 抽象基类 — 所有配图服务必须继承 |
| `app/services/pexels_service.py` 等 | 各配图服务的具体实现 |
| `app/services/local_file_service.py` | 本地文件存储（替代 COS），将 ImageData 持久化并返回可访问 URL |
| `app/agent/image_generator.py` | `ParallelImageGenerator` — 服务注册、策略分发、并行调度、降级兜底 |
| `app/services/article_service.py` | VIP 门控：`_default_non_vip_image_methods` / `_vip_only_image_methods` |
| `app/agent/agents/image_analyzer.py` | Agent4 — 分析正文后输出 `ImageRequirement[]` |
| `app/agent/agents/image_generator_agent.py` | Agent5 — 调用 `ParallelImageGenerator.generate()` 并行拉图 |

## 数据流

```
ImageRequest { keywords, prompt, position, type }
    │
    ▼
BaseImageSearchService.get_image_data(request)
    │
    ├─ 图库检索类（Pexels/Iconify/EmojiPack）:
    │    request.keywords → 调 API 搜索 → ImageData.from_url(url)
    │
    └─ AI 生图类（Mermaid/SvgDiagram）:
         request.prompt → 本地渲染或调 LLM → ImageData.from_bytes(...)
    │
    ▼
ImageData { bytes | url | data_url, mime_type, data_type }
    │
    ▼
LocalFileService.upload_image_data(image_data, folder)
    → 下载/写盘 → 返回 static URL
```

## ImageData 三种类型

| DataType | 说明 | 典型来源 |
|---|---|---|
| `BYTES` | 内存中的二进制数据 | Mermaid mmdc 渲染、SVG LLM 生成 |
| `URL` | 外部图片链接 | Pexels API、Iconify、Bing 搜图 |
| `DATA_URL` | base64 编码的小图/缩略图 | 暂未使用 |

## 降级机制

1. 服务不可用（`is_available() == False`）→ 降级
2. `get_image_data()` 返回 None 或无效 → 降级
3. `upload_image_data()` 失败 → 降级
4. 任何未捕获异常 → 降级
5. 降级目标：`PICSUM` 随机图（`ImageMethodEnum.get_fallback_method()`）

## 新增配图服务 checklist

当你需要新增一种配图方式时，按以下顺序修改：

### 1. `app/models/enums.py` — 添加枚举成员

在 `ImageMethodEnum` 中新增一行，格式：`NAME = "VALUE", "中文标签", "简短说明"`

```python
NEW_SERVICE = "NEW_SERVICE", "新服务名", "适合xxx场景"
```

注意：如果是 AI 生图，需要在 `is_ai_generated()` 方法中加上；如果是兜底图，需要在 `is_fallback()` 中加上。

### 2. `app/services/xxx_service.py` — 新建服务类

继承 `BaseImageSearchService`，必须实现：

| 方法/属性 | 说明 |
|---|---|
| `name`（类属性） | 与 `ImageMethodEnum.value` 一致，如 `"NEW_SERVICE"` |
| `description`（类属性） | 一句话适用场景，供 LLM 选择配图方式时参考 |
| `usage`（类属性） | 使用指南（可多行），指导 LLM 如何填写 keywords/prompt |
| `is_ai_generate`（类属性） | 是否为 AI 生图方式 |
| `get_image_data(request)` | 核心方法：接收 `ImageRequest`，返回 `ImageData` 或 None |
| `get_method()` | 返回对应的 `ImageMethodEnum` 枚举值 |
| `get_fallback_image(position)` | 返回兜底图 URL（通常用 `ArticleConstant.PICSUM_URL_TEMPLATE`） |
| `is_available()` | 可选覆写，检查前置依赖是否就绪（如 CLI 是否安装） |

参考代码模板：[pexels_service.py](pexels_service.py)（图库检索类）/ [mermaid_service.py](mermaid_service.py)（AI 生图类）

### 3. `app/agent/image_generator.py` — 注册服务

- **顶部 import**: 新增一行 `from app.services.xxx_service import XxxService`
- **`_register_services()` 方法**: 在 `services` 列表中加入 `XxxService()`
- **`_get_folder_for_method()` 方法**: 在 `folder_map` 字典中加入新映射

```python
# _register_services
services = [
    PexelsService(),
    # ... 其他已有服务 ...
    XxxService(),  # ← 新增这行
]

# _get_folder_for_method
folder_map = {
    # ... 其他已有映射 ...
    ImageMethodEnum.NEW_SERVICE: "new-service-folder",  # ← 新增这行
}
```

### 4. `app/services/article_service.py` — VIP 门控

在 `__init__` 中决定新服务的 VIP 策略：

- **普通用户可用**：加到 `_default_non_vip_image_methods` 列表
- **VIP 专属**：加到 `_vip_only_image_methods` 集合

```python
self._default_non_vip_image_methods = [
    ImageMethodEnum.PEXELS.value,
    # ...
    ImageMethodEnum.NEW_SERVICE.value,  # ← 普通用户可用
]
# 或
self._vip_only_image_methods = {
    ImageMethodEnum.NANO_BANANA.value,
    ImageMethodEnum.NEW_SERVICE.value,  # ← VIP 专属
}
```

### 5. 无需修改的部分

以下文件**不需要手动改**，它们通过抽象层自动适配：

- **前端接口** `/article/options` — 通过 `get_enabled_methods()` 动态返回已注册服务列表
- **配图提示词** `build_image_methods_guide()` — 从各服务的 `name/description/usage` 属性动态拼表格
- **编排器** `ArticleAgentOrchestrator` / Agent4 / Agent5 — 通过 `ParallelImageGenerator` 统一调度
- **文件存储** `LocalFileService` — 通过 `ImageData` 统一封装，不关心具体来源
