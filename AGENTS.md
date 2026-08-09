# AGENTS.md

本文件为 AI 助手在处理本仓库代码时提供指导。

## 项目简介

**AI 文章创作平台**：用户输入一个主题，系统通过 **LangGraph 状态机**编排多个 LLM 智能体，
自动完成「选题研究 → 标题生成 → 大纲规划 → 正文创作 → 配图生成 → 图文合并」，最终产出一篇图文并茂的完整文章。

核心特点：

- **多智能体编排**：LangGraph 编排 6 个创作智能体（标题、大纲、正文、配图分析、配图生成、内容合并）+ 1 个新闻信息采集智能体
- **人机协同断点**：标题确认、大纲确认、AI 修改大纲共 3 个 interrupt 点，边生成边确认
- **多源配图**：Pexels、智谱 GLM-Image、Nano Banana(Gemini)、Mermaid、Iconify、Bing 表情包、AI-SVG 图表等，失败自动降级（Picsum 兜底）
- **实时进度流**：SSE 推送生成进度，正文/大纲流式输出；重新进入创作页可恢复上次进度（历史事件重放 + `?after=` 断点续传）
- **用户体系**：注册 / 登录 / VIP 会员 / 配额管理 / 积分系统（签到 / 用量计费 / 明细 / 管理端，充值暂未开放）
- **注册/登录限流防爆破**：Redis 固定窗口限流（IP 注册频率、账号级 + IP 级登录失败锁定）
- **在线支付**：Stripe 一键开通永久 VIP
- **管理看板**：后台统计、用户管理、积分管理与模型计价

## 技术栈

| 层级 | 技术 |
| :--- | :--- |
| 前端 | Vue 3、Vite、Ant Design Vue 4、Pinia、Vue Router 4、ECharts、Axios、@umijs/openapi（openapi2ts 生成 API 客户端） |
| 后端 | Python 3.11（`.python-version`，pyproject 声明 `>=3.10`）、FastAPI 0.115、SQLAlchemy 2.0、databases(异步) |
| 编排 | LangGraph、LangChain（信息采集用 `create_agent`）、SQLite Checkpointer（断点续跑） |
| 存储 | MySQL（业务数据）、Redis（Session / 去重 / 配额信号量 / 注册登录限流）、SQLite（图检查点）、本地文件存储（图片，替代原腾讯云 COS） |
| LLM | DeepSeek、小米 MiMo（按智能体可独立配置，空值回退全局默认） |
| 图片 | Pexels、智谱 GLM-Image、Nano Banana(Gemini)、Mermaid CLI、Iconify、Bing 表情包、AI-SVG、Picsum 兜底 |
| 支付 | Stripe |
| 包管理 | 后端 uv（`uv.lock`）、前端 npm |

## 快速开始

环境要求：Python 3.10+（推荐 3.11）、Node.js `^22.18.0 || >=24.12.0`、MySQL、Redis。

```bash
# 后端（端口 8567）
cd backend
cp .env.example .env   # 按需填写数据库/Redis/各 LLM 与图片服务密钥
uv run python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8567

# 前端（端口 5173）
cd frontend
npm install
npm run dev
```

- 所有环境变量见 `backend/.env.example` 与 `backend/app/config/` 配置包（按主题拆分的 Pydantic Settings mixin，`from app.config import settings`，大小写不敏感）
- 数据库初始化：全新环境执行 `cd backend && uv run python scripts/init_db.py`（幂等建库建表，DDL 与 `backend/sql/init_db.sql` 保持一致）；种子数据另设独立脚本 `scripts/seed_data.py`，需手动执行（演示账号/模型计价）
- 静态图片访问：后端挂载 `/static`（`backend/static/images/`），`STATIC_BASE_URL` 配置访问域名
- API 文档：`http://localhost:8567/api/docs`（FastAPI 自带 OpenAPI）；前端 API 客户端由 `npm run openapi2ts` 从 `http://localhost:8567/api/v3/api-docs` 生成
- Stripe 本地联调：`stripe listen --forward-to localhost:8567/api/webhook/stripe`

## 目录结构

```
passageAI/
├── backend/                      # FastAPI 后端（Python 3.11 / uv）
│   ├── app/
│   │   ├── main.py               # FastAPI 入口：CORS、lifespan、全局异常、路由注册、/static 挂载
│   │   ├── config/               # 配置包：按主题拆分的 Pydantic Settings mixin（base/agent/images/llm/payment/quota）
│   │   │   └── __init__.py       #   Settings 组合类 + settings 单例（from app.config import settings）
│   │   ├── database.py           # SQLAlchemy 同步引擎 + databases 异步连接（get_db 依赖注入）
│   │   ├── redis.py              # Redis 异步客户端（init/close/get_client 单例）
│   │   ├── deps.py               # 认证依赖：get_current_user / require_login / require_admin / require_create_slot
│   │   ├── exceptions.py         # BusinessException + ErrorCode + throw_if / throw_if_not
│   │   ├── count_semaphore.py    # 用量配额信号量
│   │   │
│   │   ├── graph/                # ⭐ LangGraph 文章生成状态机
│   │   │   ├── builder.py        #   图拓扑组装（节点注册 + 边 + interrupt + compile）
│   │   │   ├── state.py          #   dict 形态 ArticleState（JSON 可序列化，供 checkpointer）
│   │   │   ├── constants.py      #   节点名常量（含未接入的 review/seo 占位）
│   │   │   ├── checkpointer.py   #   SQLite checkpointer（backend/data/checkpoints.sqlite）
│   │   │   ├── sse_bridge.py     #   SSE 发送（make_emit / send_sse_message）
│   │   │   ├── edges/            #   条件边路由（bootstrap_routing、review_routing 占位）
│   │   │   └── nodes/            #   每节点一文件（bootstrap/title/outline/content/...）
│   │   │       ├── compat.py     #   dict 图状态 ↔ class 智能体状态适配
│   │   │       ├── _orchestrator.py  # 智能体编排器单例（懒加载，避免循环导入）
│   │   │       ├── research.py   #   信息采集节点（新闻题材，结果结构化落库）
│   │   │       ├── seo.py / review.py  # 占位节点（暂未接入 builder）
│   │   │
│   │   ├── agent/                # LLM 智能体层（被图节点调用）
│   │   │   ├── base_agent.py     #   BaseAgent：_call_llm / 流式 / JSON 解析（json_repair 兜底）/ 提示词工具
│   │   │   ├── orchestrator.py   #   ArticleAgentOrchestrator：持有 6 个创作智能体
│   │   │   ├── image_generator.py#   ParallelImageGenerator 单例（服务分发 + 并行生图 + 降级）
│   │   │   ├── agents/           #   title/outline/content/image_analyzer/image_generator_agent/content_merger
│   │   │   ├── context/          #   流式输出处理器
│   │   │   └── information_collector/  # 新闻采集（LangChain create_agent + Serper + 网页抽取）
│   │   │
│   │   ├── llm_factory/          # LLM 提供商抽象 → langchain_core BaseChatModel
│   │   │   ├── factory.py        #   get_chat_model / get_structured_model / resolve_agent_config
│   │   │   ├── deepseek.py
│   │   │   └── mimo.py           #   小米 MiMo
│   │   │
│   │   ├── routers/              # REST API（均挂 /api 前缀）
│   │   │   ├── article.py        #   创作 CRUD + SSE 进度 + 确认标题/大纲/AI 改大纲
│   │   │   ├── user.py           #   注册/登录/登出/个人中心（资料/密码/头像）+ 管理员用户管理
│   │   │   ├── payment.py        #   Stripe checkout + webhook
│   │   │   ├── statistics.py     #   管理端统计
│   │   │   ├── points.py         #   积分中心：余额 / 每日签到 / 流水明细 / 模型用量统计
│   │   │   ├── admin_points.py   #   管理员积分调整 + 模型计价（/admin/model-pricing CRUD）
│   │   │   └── health.py
│   │   │
│   │   ├── services/             # 业务逻辑
│   │   │   ├── article_service.py      #   文章 DB 操作 + 配额/积分校验 + 去重 + 并发任务名额原子占用
│   │   │   ├── article_async_service.py #  图 start/resume + 失败兜底（_handle_failure）
│   │   │   ├── points_service.py       #   积分账户（余额/流水/签到/结算/管理员调整，乐观锁）
│   │   │   ├── pricing_service.py      #   模型计价查询
│   │   │   ├── settlement_service.py   #   后付费段级结算 + activeTaskCount 启动对账
│   │   │   ├── model_usage_service.py  #   模型用量埋点与统计
│   │   │   ├── agent_log_service.py    #   智能体执行日志
│   │   │   ├── user_service.py / payment_service.py / statistics_service.py
│   │   │   └── 配图服务：image_search_service(基类) + pexels / zhipu / nano_banana /
│   │   │        mermaid / iconify / emoji_pack / svg_diagram / picsum(降级) / cos(遗留) / local_file
│   │   │
│   │   ├── models/               # SQLAlchemy ORM（camelCase 列名）
│   │   │   ├── article.py / user.py / payment.py / agent_log.py / enums.py
│   │   │   └── 积分：user_points.py / points_transaction.py / model_pricing.py / model_usage_record.py
│   │   ├── schemas/              # Pydantic 请求/响应模型（article/common/image/payment/points/statistic/user）
│   │   ├── managers/sse_manager.py  # SSE 连接管理（task_id → queue）
│   │   ├── constants/            # 常量：article / points / prompt / user
│   │   └── utils/                # logger / password / session(Redis) / rate_limit(注册登录限流) / json_tool(JSON 修复) / path_tool
│   │
│   ├── data/                     # SQLite 检查点（gitignore）
│   ├── logs/                     # 运行日志（gitignore）
│   ├── sql/                      # 建表/迁移 SQL 脚本（手动执行；init_db.sql 为全量合并版）
│   ├── scripts/                  # 运维/辅助脚本（init_db.py 建库建表、seed_data.py 种子数据、get_graph_image.py）
│   ├── tests/                    # 独立手工测试脚本（非 pytest 套件，gitignore）
│   ├── static/                   # 本地图片存储（gitignore 中 images/）
│   ├── .env / .env.example / .python-version / pyproject.toml / uv.lock
│
├── frontend/                     # Vue 3 前端（Vite）
│   ├── index.html / vite.config.js / jsconfig.json / openapi2ts.config.ts / package.json
│   └── src/
│       ├── main.js / App.vue
│       ├── request.ts            # Axios 实例（baseURL → localhost:8567，withCredentials，401 拦截）
│       ├── access.ts             # 路由守卫（登录 + 管理员校验）
│       ├── router/index.js       # 路由：/ /create /article/:taskId /article/list /points /vip /user/* /admin/* /payment/*
│       ├── stores/loginUser.ts   # Pinia 当前用户
│       ├── api/                  # openapi2ts 生成的 API 客户端（article/payment/points/statistics/user Controller）
│       ├── layouts/BasicLayout.vue
│       ├── components/           # GlobalHeader / GlobalFooter / article(ExecutionLogPanel, ResearchPanel, OutlineEditor)
│       ├── pages/                # HomePage / article(Create, Detail, List) / user(Login, Register, Profile, Settings)
│       │                         # vip / payment(PaymentResult) / points(PointsPage) / admin(Statistics, UserManage, PointsAdmin, ModelPricing)
│       ├── utils/                # articleStatus / export / markdown / permission / sse(EventSource 封装)
│       └── constants/user.ts
│
├── docs/                         # 设计/开发计划文档（如 积分系统开发计划.md；gitignore）
├── README.md / TODO.md / LICENSE / .gitignore / .mcp.json / CLAUDE.local.md
├── local data/                   # 本地参考素材（gitignore）
├── passage/                      # 示例文章（gitignore）
├── temp/                         # 临时文件（gitignore）
└── 个人笔记/                      # 个人笔记（gitignore）
```

## 核心架构

### LangGraph 文章生成流水线（backend/app/graph/）

当前接入图的节点共 12 个（`graph/constants.py` 有权威说明）：

```
START → bootstrap
       → [条件边：新闻题材?] → research（信息采集，仅新闻）┐
       → generate_title → confirm_title [⏸ interrupt]
       → generate_outline → confirm_outline [⏸ interrupt]
       → [条件边：有 modify_suggestion?] → ai_modify_outline [⏸ interrupt，可循环]
       → generate_content → image_analyzer → image_generator → merger → finalize → END
```

- **副作用节点**（写库 + 发阶段 SSE）：`bootstrap`、`confirm_title`、`confirm_outline`、`ai_modify_outline`、`finalize`
- **智能体节点**（纯 LLM 工作 + 流式 SSE）：`generate_title`、`generate_outline`、`generate_content`、`image_analyzer`、`image_generator`、`merger`
- **研究节点**：`research`（仅新闻题材，bootstrap 后条件边进入，结果结构化落库 `article.researchData`）
- **占位节点**：`review`（内容审核）、`seo`（SEO 优化）已建文件但**未注册进 builder**，待实现
- interrupt 锚点设在副作用节点**之后**：先落库 + 发 SSE 事件，再暂停等用户输入
- 检查点：SQLite（`backend/data/checkpoints.sqlite`），FastAPI lifespan 中初始化

### 状态管理

- **图状态**（`graph/state.py`）：`ArticleState` TypedDict，全部字段 JSON 可序列化（str/list[dict]/dict），供 LangGraph checkpointer 持久化
- **智能体状态**（`schemas/article.py` 的 `ArticleState`）：Pydantic 模型对象，供智能体使用
- **适配层**（`graph/nodes/compat.py`）：`to_class_state(dict)` / `merge_to_dict(class)` 双向转换，每个节点边界都要走一遍

### 人机协同流程

1. `POST /api/article/create` → `article_async_service.start()` → 图跑到 `confirm_title` interrupt
2. `POST /api/article/confirm-title`（选标题 + 补充描述）→ `resume()` → 图跑到 `confirm_outline` interrupt
3. `POST /api/article/ai-modify-outline`（可循环）或用户直接编辑大纲
4. `POST /api/article/confirm-outline` → 图一路跑到 `finalize` 完成

### SSE 进度流

- 后端：`graph/sse_bridge.py` → `managers/sse_manager.py`（全局队列，按 `task_id` 索引）
- 消息类型：`models/enums.py` 的 `SseMessageTypeEnum`（AGENT1-5 / IMAGE / MERGE / ALL_COMPLETE / TITLE_GENERATED / OUTLINE_GENERATED / AI_MODIFY_OUTLINE_COMPLETE / RESEARCH_COMPLETE / ERROR ...）
- 流式约定：agent 流式内容用 `TYPE:content` 前缀格式；完成事件携带结构化数据
- 断点续传：`GET /api/article/progress/{taskId}?after=<eventId>` 重放历史事件；重新进入创作页用 `?taskId=` 恢复上次进度（含流式大纲/正文中断点恢复）
- 前端：`utils/sse.ts` 封装 `EventSource`，订阅 `GET /api/article/progress/{taskId}`

### 配图架构

- 所有图片服务实现 `BaseImageSearchService`（`services/image_search_service.py`）
- `ParallelImageGenerator` 单例（`agent/image_generator.py`）注册可用服务：按 `ImageMethodEnum` 分发、`asyncio.Semaphore` 限并发、失败自动降级（Picsum 兜底）
- 可配置开关：如 `zhipu_api_key` 为空则跳过智谱服务；启用列表同时驱动 LLM 提示词表与前端创作页选项接口（`/api/article/creation-options`）
- 数据流：`ImageRequirement` → `service.get_image_data()` → `ImageData` → `LocalFileService.upload_image_data()` → URL
- 枚举 `ImageMethodEnum`：PEXELS / NANO_BANANA / ZHIPU / MERMAID / ICONIFY / EMOJI_PACK / SVG_DIAGRAM / PICSUM(降级)

### 积分系统（v1.3：后付费段级结算 + 透支护栏 + 并发限制）

- 数据层：`user_points`（余额 + 乐观锁 version）、`points_transaction`（流水）、`model_pricing`（模型计价）、`model_usage_record`（用量埋点）
- 服务：`points_service.py`（余额/流水/签到/结算/管理员调整）、`pricing_service.py`（计价查询）、`settlement_service.py`（段级结算 + `activeTaskCount` 启动对账）、`model_usage_service.py`（用量埋点与统计）
- 接口：`routers/points.py`（余额 / `POST /points/checkin` 签到 / 流水明细 / 用量统计）、`routers/admin_points.py`（管理员积分调整 + `/admin/model-pricing` CRUD）
- 前端：`/points` 积分中心页（余额卡 + 每日签到 + 明细分页 + 用量统计），`/admin/points` 积分管理、`/admin/model-pricing` 模型计价
- 计费与护栏：按实际模型用量 × 计价后付费扣费；创建前 `require_create_slot` 校验余额（允许透支，上限 `max_debt_points=200`）+ 单用户并发限制（`max_active_tasks=5`），续跑/修改前余额复查
- 注册即赠送 100 积分（注册事务内发放），每日签到 10 积分（Redis 防重）
- 规则见 `docs/积分系统开发计划.md` v1.3 与 `constants/points.py`；v1.2「预扣-结算」设计已废弃（`USAGE_RESERVE` / `USAGE_REFUND` 仅兼容保留），积分充值暂未开放

## 开发约定与代码风格

1. **语言**：代码注释、提交信息、对话统一使用中文；提交信息遵循 Conventional Commits（`feat:` / `fix:` / `refactor:` / `chore:` 等）
2. **注释风格**：
   - Python：Google 风格 docstring —— 函数含 `Args:` / `Returns:` / `Raises:`，类含 `Attributes:`（项目内普遍使用，见各服务/模型文件）
   - TypeScript/Vue：JSDoc 风格，关键函数与组件 props/emits 含 `@param` / `@returns` / `@throws`
3. **配置优先**：可配置项写入 `app/config/` 配置包（由 `.env` 驱动，`from app.config import settings`），禁止在代码中硬编码密钥与魔法数字（常量集中在 `constants/`）
4. **数据库列名**：MySQL 表列使用 camelCase，SQLAlchemy 中用 `Column("camelCase", ...)` 映射；ORM 字段名 snake_case
5. **API 响应统一**：`BaseResponse`（code / data / message），业务错误抛 `BusinessException` + `ErrorCode`，由全局异常处理器统一兜底
6. **依赖注入**：FastAPI 路由通过 `Depends(get_db)` 拿 `databases.Database`，通过 `Depends(require_login)` / `require_admin` 做鉴权
7. **避免循环导入**：图节点在函数体内 import `ArticleService` / `AgentLogService`；`graph/nodes/_orchestrator.py` 懒加载编排器单例（注释约定「函数体内 import，避免循环导入」）
8. **状态适配**：dict 图状态 ↔ Pydantic 智能体状态必须在每个节点边界用 `compat.py` 转换
9. **失败边界**：`article_async_service._handle_failure` 兜底图节点异常；单个节点（如 research）内部捕获非致命错误
10. **异步任务**：`asyncio.create_task` 启动后台任务，`article_async_service.register_task` 持有引用防止 GC
11. **并发安全**：多用户并发系统，涉及共享资源（配额/积分扣减、任务状态、支付记录）必须注意竞态：优先原子 SQL 而非「先查后改」；必要时行锁 / 乐观锁 / 分布式锁（如 `points_service` 用 `FOR UPDATE` + `version` 乐观锁；`user.activeTaskCount` 用原子 `UPDATE ... SET activeTaskCount = activeTaskCount + 1` 占用名额）
12. **去重**：创建文章用 Redis 幂等键（`dedup:article:{userId}:{fingerprint}`，`dedup_window_seconds` 窗口内禁止重复提交）
13. **限流防爆破**：注册（IP 固定窗口）与登录（账号级 + IP 级失败计数锁定）基于 Redis 实现，见 `utils/rate_limit.py`，参数见 `config/quota.py`（`trust_forwarded_headers` 默认 False，防止伪造头绕过）
14. 完成代码修改后不立即提交到 git，待用户审核完成，显式要求提交时再提交

## 数据库

- MySQL（业务数据）：SQLAlchemy 同步引擎（模型定义）+ `databases` 异步（FastAPI 查询）；连接串 `settings.database_url`
- Redis：Session（`utils/session.py`）、任务去重、配额信号量、注册/登录限流防爆破
- SQLite：LangGraph 检查点（`backend/data/`，gitignore）
- 建表/迁移：`backend/sql/*.sql` 为手动执行脚本，无迁移框架；`init_db.sql` 已合并历史增量脚本为全量建表 DDL，`scripts/init_db.py` 可一键幂等执行（建库建表）；种子数据由 `scripts/seed_data.py` 手动执行（幂等）
- 模型文件：`backend/app/models/`（article、user、payment、agent_log、user_points、points_transaction、model_pricing、model_usage_record、enums）

## 测试

- 未配置 pytest/CI 测试套件；`backend/tests/` 为独立手工探索脚本（`serper_search.py`、`test_image_generate.py`、`test_qwen_llm.py` 等），且被 `.gitignore` 排除（`test/`、`tests/`、`*test*`）
- 新增功能后建议至少手动跑一遍核心链路：创建文章 → 确认标题 → 确认大纲 → 看 SSE 进度 → 完成

## 注意事项 / 已知问题

- 完整待办见 `TODO.md`（配图方式部分未完成、内容审核/SEO Agent 未实现、积分充值暂未开放、若干 BUG 修复等）
- `docs/`、`temp/`、`passage/`、`个人笔记/`、`local data/` 等目录在 `.gitignore` 中，不入库
- `.claude/`、`.codex/`、`CLAUDE.local.md`、`.mcp.json` 不入库（IDE/工具本地配置）
- `ArticleStyleEnum` 已弃用，新流程使用 `genre`（题材）+ `language_style`（语言风格）；`style` 字段保留兼容存量数据
