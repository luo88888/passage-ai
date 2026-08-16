# AGENTS.md

本文件为 AI 助手在处理本仓库代码时提供指导。

## 项目简介

**AI 文章创作平台**：用户输入一个主题，系统通过 **LangGraph 状态机**编排多个 LLM 智能体，
自动完成「选题研究 → 标题生成 → 大纲规划 → 正文创作 → 配图生成 → 图文合并」，最终产出一篇图文并茂的完整文章。

核心特点：

- **多智能体编排**：LangGraph 编排 7 个创作智能体（标题、大纲、AI 修改大纲、正文、配图分析、配图生成、内容合并）+ 1 个新闻信息采集智能体（LangChain `create_agent`）
- **人机协同断点**：标题确认、大纲确认、AI 修改大纲共 3 个 interrupt 点，边生成边确认
- **多源配图**：Pexels、Mermaid CLI、Iconify、Bing 表情包、AI-SVG、智谱 GLM-Image（配置 key 后启用），失败自动降级 Picsum
- **实时进度流**：SSE 推送生成进度，大纲/正文流式输出；历史事件重放 + `?after=` 断点续传；创作页 `?taskId=` 恢复进行中任务
- **用户体系**：注册 / 登录 / VIP 会员 / 积分系统（注册赠送、签到、后付费段级结算、明细分页、模型用量统计、管理端），充值暂未开放
- **运营能力**：意见反馈（截图上传 + 管理员回复 + 站内信联动）、站内信（系统通知 / 管理端单发、批量、全体广播）
- **限流防爆破**：Redis 固定窗口（IP 注册频率、账号级 + IP 级登录失败锁定、反馈每日限流、签到防重）
- **支付**：Stripe checkout / webhook 代码已实现，当前前端「立即开通」走免支付直开（Stripe 暂未启用）
- **管理看板**：后台统计、用户管理、积分管理、模型计价、反馈管理、站内信管理

## 技术栈

| 层级 | 技术 |
| :--- | :--- |
| 前端 | Vue 3、Vite 8、Ant Design Vue 4、Pinia、Vue Router 4、ECharts、Axios、@umijs/openapi（openapi2ts 生成 API 客户端） |
| 后端 | Python 3.11（`.python-version`，pyproject 声明 `>=3.10`）、FastAPI 0.115、SQLAlchemy 2.0、databases（异步） |
| 编排 | LangGraph 1.1、LangChain `create_agent`（信息采集）、SQLite Checkpointer（断点续跑） |
| 存储 | MySQL（业务数据）、Redis（Session / 去重 / 限流 / 签到防重）、SQLite（图检查点）、本地文件存储（图片） |
| LLM | DeepSeek、小米 MiMo（按智能体独立配置，空值回退全局默认） |
| 图片 | Pexels、Mermaid CLI、Iconify、Bing 表情包、AI-SVG、智谱 GLM-Image、Picsum 兜底 |
| 搜索/抓取 | Serper（新闻搜索）、ddgs（网页内容抓取转 Markdown） |
| 支付 | Stripe（代码已实现，当前未启用） |
| 包管理 | 后端 uv（`uv.lock`）、前端 npm |

## 快速开始

环境要求：Python 3.10+（推荐 3.11）、Node.js `^22.18.0 || >=24.12.0`、MySQL 8.0+、Redis、uv；
Mermaid 配图需全局安装 `@mermaid-js/mermaid-cli`（`mmdc`）。

```bash
# 后端（端口 8567）
cd backend
uv sync
cp .env.example .env   # 按需填写数据库/Redis/各 LLM 与图片服务密钥
uv run python scripts/init_db.py          # 幂等建库建表（DDL 唯一源：sql/init_db.sql）
uv run python scripts/seed_data.py        # 可选：演示账号 / 模型计价种子数据
uv run python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8567

# 前端（端口 5173，同源 /api 由 Vite 代理到后端 8567）
cd frontend
npm install
npm run dev
```

- 环境变量见 `backend/.env.example` 与 `backend/app/config/` 配置包（按主题拆分的 Pydantic Settings mixin，`from app.config import settings`，大小写不敏感）
- API 文档：`http://localhost:8567/api/docs`；OpenAPI JSON 位于 `/api/v3/api-docs`，前端执行 `npm run openapi:refresh` 拉取到 `frontend/openapi.json` 后由 `openapi2ts` 生成 API 客户端
- 静态图片：后端挂载 `/static`（`backend/static/images/`），`STATIC_BASE_URL` 配置访问域名
- Stripe 启用后的本地联调：`stripe listen --forward-to localhost:8567/api/webhook/stripe`

## 目录结构

```
passage-ai/
├── backend/                      # FastAPI 后端（Python 3.11 / uv）
│   ├── app/
│   │   ├── main.py               # FastAPI 入口：CORS、lifespan、全局异常、路由注册、/static 挂载
│   │   ├── config/               # 配置包：base/agent/images/llm/payment/pricing/quota mixin
│   │   ├── database.py / redis.py / deps.py / exceptions.py
│   │   ├── count_semaphore.py    # 进程内信号量（智谱生图限并发）
│   │   ├── graph/                # ⭐ LangGraph 文章生成状态机
│   │   │   ├── builder.py        #   图拓扑组装（节点 + 条件边 + interrupt + compile）
│   │   │   ├── constants.py      #   12 个接入节点 + review/seo 占位节点名
│   │   │   ├── checkpointer.py   #   SQLite checkpointer（backend/data/checkpoints.sqlite）
│   │   │   ├── graph_runner.py   #   文章异步任务服务：start/resume + 并发守卫 + 失败兜底
│   │   │   ├── sse_bridge.py     #   图节点 → SSE 消息转换
│   │   │   ├── edges/            #   bootstrap_routing / outline_routing；review_routing 占位
│   │   │   └── nodes/            #   12 个图节点 + _orchestrator.py（编排器单例）
│   │   ├── agent/                # LLM 智能体层
│   │   │   ├── orchestrator.py   #   ArticleAgentOrchestrator：持有 7 个创作智能体
│   │   │   ├── agents/           #   title/outline/ai_modify_outline/content/image_analyzer/image_generator_agent/content_merger
│   │   │   ├── base_agent.py / context/   # 基类、流式输出处理
│   │   │   └── information_collector/     # 新闻采集（LangChain create_agent + Serper + ddgs 抓取）
│   │   ├── llm_factory/          # factory / deepseek / mimo / token_usage_handler
│   │   ├── routers/              # article/user/payment/statistics/points/admin_points/feedback/message/health
│   │   ├── services/             # 文章/积分/计价/结算/用量/日志/用户/支付/统计/反馈/站内信 + 配图服务 + local_file_service
│   │   ├── models/               # 10 张表 ORM（article/user/payment/agent_log/user_points/points_transaction/model_pricing/model_usage_record/feedback/message）+ enums.py
│   │   ├── schemas/              # article/common/image/payment/points/statistic/user/feedback/message
│   │   ├── managers/sse_manager.py  # SSE 连接管理（task_id → 有界历史 + 实时队列）
│   │   ├── constants/            # article / points / prompt / user / feedback / message
│   │   └── utils/                # logger / password / session / rate_limit / json_tool / path_tool
│   ├── sql/init_db.sql           # 唯一 DDL 源（10 张表全量建表）
│   ├── scripts/                  # init_db.py / seed_data.py / get_graph_image.py / bcript.py
│   ├── static/                   # default_avatar 入库；images/ 生成图片不入库
│   ├── data/ logs/               # SQLite 检查点、运行日志（gitignore）
│   └── tests/                    # 手工探索脚本（gitignore，test_qwen_llm.py 为历史遗留入库文件）
├── frontend/                     # Vue 3 前端（Vite）
│   ├── index.html / vite.config.js / jsconfig.json / tsconfig.json / openapi2ts.config.ts / package.json
│   └── src/
│       ├── main.js / App.vue / request.ts / access.ts
│       ├── router/index.js       # / /create /article/:taskId /article/list /points /vip /feedback /message /user/* /admin/* /payment/*
│       ├── stores/loginUser.ts   # Pinia 当前用户
│       ├── api/                  # openapi2ts 生成的客户端（article/user/payment/statistics/points/feedback/message/health）
│       ├── layouts/ + components/ + pages/ + utils/ + constants/ + types/
│       └── openapi.json          # openapi:refresh 拉取的 API 快照（入库）
├── docs/images/                  # README 引用截图（入库）
├── README.md / TODO.md / TODOs.md / LICENSE / .gitignore
└── 本地或临时目录（gitignore）：temp/、passage/、个人笔记/、local data/ 等
```

## 核心架构

### LangGraph 文章生成流水线（backend/app/graph/）

当前接入图的节点共 12 个（`graph/constants.py` 有权威说明）：

- **副作用节点**（落库 + 阶段流转 + SSE）：`bootstrap`、`confirm_title`、`confirm_outline`、`ai_modify_outline`、`finalize`
- **智能体节点**（纯 LLM/配图工作 + SSE）：`generate_title`、`generate_outline`、`generate_content`、`image_analyzer`、`image_generator`、`merger`
- **研究节点**：`research`（仅新闻题材，bootstrap 后条件边进入；采集失败不阻塞主流程，结果结构化落库 `article.researchData`）
- **占位节点**：`review`、`seo` 已建文件但未注册进 builder

```
START → bootstrap
       ├─ genre=news → research ─┐
       └─ 其他 → generate_title ←┘
       → confirm_title [⏸ interrupt]
       → generate_outline → confirm_outline [⏸ interrupt]
       → 有 modify_suggestion → ai_modify_outline [⏸ interrupt，可循环]
       → generate_content → image_analyzer → image_generator → merger → finalize → END
```

- interrupt 锚点设在副作用节点**之后**：先落库 + 发 SSE 事件，再暂停等用户输入
- 检查点：SQLite（`backend/data/checkpoints.sqlite`），FastAPI lifespan 初始化，LangGraph `thread_id = taskId`
- 任务调度：`graph/graph_runner.py` 的 `article_async_service` 单例负责 `start` / `resume`、同 taskId 并发守卫（reserve/attach/release）、失败兜底（结算已发生用量、标记 FAILED、释放并发名额、推 ERROR、关闭 SSE）

### 状态管理

- 图状态与智能体状态统一为 `schemas/article.py` 的 Pydantic `ArticleState`，LangGraph `StateGraph(ArticleState)` 直接使用
- 节点读写 `state` 字段并返回 dict；结构化子对象用 `model_dump(by_alias=True)` 序列化，供 checkpointer 持久化与 SSE 下发
- 人工输入（标题 / 大纲 / 修改建议）由 `graph_runner.resume` 通过 `aupdate_state` 注入

### 人机协同流程

1. `POST /api/article/create` → Redis 幂等去重 + `require_create_slot` 校验 + 事务内原子占用 `activeTaskCount` 名额 → `start()` 跑到 `confirm_title` interrupt
2. `POST /api/article/confirm-title`（选标题 + 补充描述）→ 余额复查 → 落库 → `resume()` 跑到 `confirm_outline` interrupt
3. `POST /api/article/ai-modify-outline`（仅 VIP，可循环）或用户直接编辑大纲
4. `POST /api/article/confirm-outline` → 清空 `modify_suggestion` → `resume()` 跑到 `finalize` 完成

### SSE 进度流

- 后端：`graph/sse_bridge.py` → `managers/sse_manager.py`（每个 taskId 维护有界历史缓冲 + 实时队列，SSE 帧携带 `id: <seq>`）
- 消息类型见 `models/enums.py` 的 `SseMessageTypeEnum`：AGENT1-5、IMAGE_COMPLETE、MERGE_COMPLETE、ALL_COMPLETE、ERROR、TITLE_GENERATED、OUTLINE_GENERATED、AI_MODIFY_OUTLINE_COMPLETE/FAILED、RESEARCH_COMPLETE 等
- 流式约定：`AGENT2_STREAMING:` / `AGENT3_STREAMING:` 前缀格式，桥接层剥前缀为 `{type, content}`；`IMAGE_COMPLETE:` 同理
- 断点续传：`GET /api/article/progress/{taskId}?after=<seq>` 先重放 `seq > after` 的历史，再续接实时流；前端 `utils/sse.ts` 封装 `EventSource` 并记录 `lastEventId`
- 创作页恢复：`/create?taskId=` 拉取文章按 phase 恢复；详情页「去创作页观察进度」走同一入口

### 配图架构

- 所有图片服务实现 `BaseImageSearchService`（`services/image_search_service.py`）
- `ParallelImageGenerator` 单例（`services/image_generator.py`）：按 `ImageMethodEnum` 分发、`asyncio.Semaphore` 限并发、失败自动降级（Picsum 兜底并上传本地）
- 当前注册服务：Pexels、Mermaid、Iconify、Bing 表情包、AI-SVG；智谱在配置 `zhipu_api_key` 后注册；Nano Banana 服务实现保留但暂未注册
- 可配置开关与 VIP 门控：启用列表同时驱动 LLM 提示词表（`build_image_methods_guide`）与创作页选项接口（`/api/article/options`）；普通用户默认 Pexels/Mermaid/Iconify/表情包，VIP 解锁 AI 生图与 SVG 图表
- 数据流：`ImageRequirement` → `service.get_image_data()` → `ImageData` → `LocalFileService.upload_image_data()` → URL

### 积分系统

- 数据层：`user_points`（余额 + version 乐观锁）、`points_transaction`（流水）、`model_pricing`（模型计价）、`model_usage_record`（用量埋点）
- 服务：`points_service.py`（余额/流水/签到/结算/管理员调整，`FOR UPDATE` + version）、`pricing_service.py`（计价查询）、`settlement_service.py`（按段增量结算 + 启动对账 `activeTaskCount`）、`model_usage_service.py`（用量埋点与统计）
- 规则：注册赠送 500 积分，每日签到 +100（Redis 防重）；按实际模型用量 × 计价后付费结算；允许透支，上限 `max_debt_points=200`；单用户并发上限 `max_active_tasks=5`（admin 豁免）；续跑/修改前余额复查
- 接口：`/points`（余额、签到、流水、用量统计）、`/admin/points`（看板、调整、用量查询）、`/admin/model-pricing`（计价 CRUD）
- 充值暂未开放；`USAGE_RESERVE` / `USAGE_REFUND` 为兼容保留类型，不再产生新流水

## 开发约定与代码风格

1. **语言**：代码注释、提交信息、对话统一使用中文；提交信息遵循 Conventional Commits（`feat:` / `fix:` / `refactor:` / `chore:` 等）
2. **注释风格**：Python 用 Google 风格 docstring（`Args:` / `Returns:` / `Raises:` / `Attributes:`）；TypeScript/Vue 用 JSDoc（关键函数与组件 props/emits）
3. **配置优先**：可配置项写入 `app/config/`（`.env` 驱动），禁止硬编码密钥与魔法数字（常量集中在 `constants/`）
4. **数据库列名**：MySQL 列 camelCase，SQLAlchemy 用 `Column("camelCase", ...)`；ORM 字段名 snake_case
5. **API 响应统一**：`BaseResponse`（code / data / message），业务错误抛 `BusinessException` + `ErrorCode`
6. **依赖注入**：路由通过 `Depends(get_db)` 拿 `databases.Database`，通过 `Depends(require_login)` / `require_admin` / `require_create_slot` 鉴权
7. **避免循环导入**：必要时在函数体内 import（如 `article_service` 内引用 `settlement_service`）
8. **失败边界**：`graph_runner._handle_failure` 兜底图节点异常；`research`、`ai_modify_outline` 等节点内部捕获非致命错误，不阻塞主流程
9. **异步任务**：`asyncio.create_task` 启动后台任务，`graph_runner` 的 reserve/attach/release 持有引用并充当同 taskId 并发守卫
10. **并发安全**：共享资源优先原子 SQL，必要时行锁 / 乐观锁（`user.activeTaskCount` 原子 `UPDATE`；`points_service` 用 `FOR UPDATE` + version）
11. **去重**：创建文章用 Redis 幂等键 `dedup:article:{userId}:{fingerprint}`，`dedup_window_seconds` 窗口内禁止重复提交
12. **限流防爆破**：注册（IP 固定窗口）、登录（账号级 + IP 级失败锁定）、反馈每日限流、签到防重均基于 Redis；参数见 `config/quota.py`（`trust_forwarded_headers` 默认 False）
13. 完成代码修改后不立即提交 git，待用户审核并显式要求后再提交

## 数据库

- MySQL（业务数据）：共 10 张表——`user`、`article`、`agent_log`、`payment_record`、`user_points`、`points_transaction`、`model_pricing`、`model_usage_record`、`feedback`、`message`
- Redis：Session（`utils/session.py`）、任务去重、注册/登录限流、签到防重、反馈每日限流
- SQLite：LangGraph 检查点（`backend/data/`，gitignore）
- DDL：`backend/sql/init_db.sql` 为唯一 DDL 源；`scripts/init_db.py` 幂等建库建表；`scripts/seed_data.py` 手动执行（演示账号/模型计价）
- `user.quota` 为遗留展示/统计字段（注册默认 5），积分余额权威在 `user_points.balance`

## 测试

- 未配置 pytest/CI 测试套件；`backend/tests/` 为独立手工探索脚本（被 `.gitignore` 的 `tests/` / `*test*` 规则排除，`test_qwen_llm.py` 为历史遗留入库文件）
- 新增功能后建议至少手动跑一遍核心链路：创建文章 → 确认标题 → 确认大纲 → 看 SSE 进度 → 完成

## 注意事项 / 已知问题

- 完整待办见 `TODO.md`；`TODOs.md` 为已完成事项清单（站内信、意见反馈、注册/登录限流）
- `review`（内容审核）、`seo`（SEO 优化）为占位节点，未接入 builder
- 积分充值暂未开放；Stripe 支付代码已实现但当前未启用，前端走免支付直开永久 VIP
- Nano Banana（Gemini）配图服务实现保留，因额度原因暂未注册，不在创作选项中暴露
- 不入库目录/文件：`temp/`、`passage/`、`个人笔记/`、`local data/`、`backend/docs/`、`backend/data/`、`backend/logs/`、`backend/static/images/`、`.env` 等；`docs/images/` 与 `backend/static/default_avatar/` 入库
- `.claude/`、`.codex/`、`CLAUDE.local.md`、`.mcp.json` 等 IDE/工具本地配置不入库
- `ArticleStyleEnum` 已弃用，新流程使用 `genre`（题材）+ `language_style`（语言风格）；`style` 字段保留兼容存量数据
