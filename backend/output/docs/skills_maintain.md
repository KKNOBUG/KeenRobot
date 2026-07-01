# KeenRobot Skill 实现与维护指南（智能聊天核心能力）

> 版本：2026-06-26  
> 定位：**智能聊天**中 Skill 能力的权威说明——实现思想、调用链、类型选型、能力边界、维护与配置  
> 关联：`CHAT_EXECUTION_FLOWS.md` · `TEST_SKILLS.md` · `HYBRID_AGENT_ORCHESTRATION.md` · `MCP_INTEGRATION.md`

---

## 阅读导航

| 你想了解… | 跳转 |
|-----------|------|
| Skill 从哪触发、怎么跑完 | **§2 调用链** |
| 选 chat / wizard / async | **§3 类型选择** |
| 能不能读知识库、能不能用 MCP | **§4 能力边界** |
| 新人怎么上手改 Skill | **§5 学习路径** |
| 复制粘贴配一个新 Skill | **§6 配置教程** |
| 线上问题怎么查 | **§7 排障** |

文档分 **两大部分**：

1. **实现逻辑与构建思想**（§1～§4）——读懂「为什么这样设计、代码怎么走」  
2. **维护 / 扩展 / 配置**（§5～§10）——动手改功能、配新 Skill、排障

---

# 第一部分：实现逻辑与构建思想

## 1. 构建思想（Design Philosophy）

### 1.1 Skill 在 KeenRobot 里是什么？

Skill **不是**独立的 Agent 进程，而是嵌入 **统一混合 Runtime**（`ChatAgentOrchestrator`）的能力包：

```text
磁盘 Skill 包（内容与版本）          DB 集成配置（路由与表单）
        │                                    │
        └──────────────┬─────────────────────┘
                       ▼
              interaction_mode 决定走哪条用户路径
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
      chat          wizard       async_job
   /chat/stream    intake+Run    intake+Celery
         │             │             │
         └─────────────┴─────────────┘
                       ▼
           ChatAgentOrchestrator（同一套 ReAct）
           RAG + SKILL.md 注入 + skill_* 工具 + MCP 工具
```

**核心设计决策：**

| 决策 | 含义 |
|------|------|
| **双层存储** | 磁盘管「写什么」、DB 管「怎么用」；内容迭代与集成配置解耦 |
| **单 Runtime** | chat / Run 共用 Orchestrator，避免多套 ReAct 分叉 |
| **按 mode 分流** | 用户交互形态不同（自由聊天 vs 表单任务），必须不同入口 API |
| **绑即注册工具** | chat 模式选中 Skill 即向 LLM 注册 `skill_read`/`skill_glob`；是否调用由模型决定（已移除 on_demand 关键词门控） |
| **Run 独立工作区** | wizard/async 有 `input/`、`output/`、`.skill_snapshot/`，支持 `skill_write` 写产物 |

### 1.2 与「智能聊天」其它能力的关系

智能聊天 = **会话绑定**（KB + chat Skill + MCP + 模型 + 深度思考）+ **两条 Skill 子路径**（chat 流式 / Run 任务）。

```text
智能聊天页 (views/chat/index.vue)
├── 普通发消息 ──────────► POST /chat/stream ──► Orchestrator
│     可选：KB + chat Skill + MCP（可同时）
│
└── Skill 任务向导 ──────► intake API + skill-runs API ──► execute_skill_run ──► Orchestrator(run_mode)
      可选：KB（Run.knowledge_base_ids）；收集中 UI 禁用 MCP
```

---

## 2. Skill 调用链

### 2.1 总览：三条路径、一个 Runtime

| 路径 | 用户动作 | 触发代码（前端） | 后端入口 | 执行核心 | 完成信号 |
|------|----------|------------------|----------|----------|----------|
| **A. chat** | 魔杖选 Skill → 发消息 | `sendMessage()` → `chatStream()` | `POST /chat/stream` | `stream_response` → Orchestrator | SSE `done` + DB assistant 消息 |
| **B. wizard** | Skill 任务 → 填表 → 确认 | `submitAndStart()` → `startSkillRun()` | `POST .../start` | `execute_skill_run` → Orchestrator | Run `completed` + execution 消息 + 产物 |
| **C. async_job** | 同 B | 同 B | 同 B（Celery） | `execute_skill_run_async` | 轮询 Run + execution 消息 |

---

### 2.2 路径 A：chat 模式 Skill

#### a. 触发入口（在哪一块代码触发）

| 层级 | 文件 · 符号 | 何时触发 |
|------|-------------|----------|
| **UI 选 Skill** | `frontend/src/views/chat/index.vue` · `selectedSkills` / `ChatFeaturePicker` | 用户点「选择 Skill」 |
| **绑定持久化** | 同上 · `schedulePersistConversationBindings` → `api.updateConversationBindings` | 选 Skill 后 300ms 防抖写 DB |
| **发消息** | 同上 · `sendMessage()` | 用户 Enter 发送（`skillIntakeLocked` 为 false） |
| **HTTP** | `frontend/src/api/index.js` · `chatStream()` | `POST /api/chat/stream`，body 含 `skill_ids`、`knowledge_base_ids`、`mcp_ids` |
| **View** | `conversation/views/chat_view.py` · `chat_stream` | 鉴权后进入编排 |
| **编排** | `conversation_crud.py` · `prepare_for_chat` | 校验 binding、写 user 消息 |
| **执行** | `conversation_crud.py` · `stream_response` → `_chat_orchestrator.stream` | **Skill 真正开始执行的位置** |

**关键分支（prepare 阶段）：**

```text
_partition_skill_ids(conv.skill_ids)
  → chat_skill_ids 传入 stream
  → wizard_ids 仅存会话，不参与 stream

_resolve_and_validate_bindings(..., chat_skill_ids=...)
  → mode != "chat" 则 ParameterException「需通过 Skill 向导执行」
```

#### b. 执行过程（触发后的调用轨迹）

```text
chat_view.chat_stream
  └─ prepare_for_chat
       ├─ _partition_skill_ids / _resolve_and_validate_bindings
       ├─ update_meta(conversation)
       └─ message.add_message(USER, question)
  └─ stream_response
       └─ ChatAgentOrchestrator.stream(skill_ids, mcp_ids, kb_ids, ...)
            ├─ bind_mcp_audit_context / McpCancelScope
            └─ _stream_impl
                 ├─ [可选] is_irrelevant_question → 寒暄短路
                 ├─ resolve_chat_binding(run_mode=False)
                 │    ├─ load_skill_for_binding（mode 须 chat）
                 │    ├─ ensure_chat_snapshot → runs/{uid}/chat_{conv}/.skill_snapshot/
                 │    ├─ load_skill_instruction(SKILL.md)
                 │    ├─ merge session MCP + execution.mcp_ids
                 │    └─ build skill_tools + mcp_tools → openai_tools
                 ├─ _retrieve_context(knowledge_base_ids)     ← KB 向量检索
                 ├─ build_hybrid_system_prompt(SKILL 指令 + RAG + MCP 元数据)
                 ├─ format_messages(chat_history)
                 └─ ReAct 或 stream_chat
                      ├─ llm.chat_with_tools
                      └─ ToolDispatcher.execute
                           ├─ skill_read / skill_glob → execute_skill_tool(cwd=快照父目录)
                           └─ mcp → McpSessionManager.call_tool
  └─ chat_view.event_generator
       ├─ yield SSE: meta / reasoning / token / process
       └─ message.add_message(ASSISTANT, full_response, process_trace)
```

**Skill 文件工具的工作目录（chat）：**

- `cwd` = `chat_{conversation_id}/`（快照的**父目录**）
- LLM 读 `.skill_snapshot/rules/demo.md` 等相对路径

#### c. 出口（如何认为执行完成 · 用户感知 · 最终代码）

| 维度 | 说明 |
|------|------|
| **后端认为完成** | Orchestrator 生成器结束；`chat_view` 收到全部 chunk 后 yield `event: done` |
| **持久化** | `conversation_crud.message.add_message(ASSISTANT, ...)` 写入 `process_trace`、token 用量 |
| **用户感知** | 助手气泡流式结束；可展开 process 看 skill/mcp 步骤；无 Run 产物下载 |
| **失败** | SSE `error` 或 assistant 消息为空；常见：`mode!=chat`、磁盘 Skill 未 sync、MCP 未 refresh |

**完成判定代码位置：**

```text
chat_view.py · event_generator 末尾 → yield done
chat_view.py · add_message(assistant)  ← 最终落库
```

---

### 2.3 路径 B：wizard 模式 Skill

#### a. 触发入口

| 层级 | 文件 · 符号 | 何时触发 |
|------|-------------|----------|
| **选 Skill 任务** | `chat/index.vue` · `handleWizardSkillPickerUpdate` → `openSkillIntake` | 用户点「Skill 任务」选 wizard Skill |
| **开始收集** | 同上 · `startSkillIntakeRequest` → `api.startSkillIntake` | `POST /conversations/{id}/skill-intake/start` |
| **填表** | `SkillIntakePanel.vue` · `goNext` / `onFileChange` | 上传、填字段、持久化 intake |
| **启动 Run** | `SkillIntakePanel.vue` · `submitAndStart` | 用户点「确认并开始」 |
| **HTTP 启动** | `api.startSkillRun(runId)` | `POST /skill-runs/{id}/start` |
| **后端执行** | `skill_run_crud.py` · `start_run` → `asyncio.create_task(execute_skill_run)` | **Skill Run 真正开始** |

#### b. 执行过程

```text
[收集阶段 — 尚未调用 LLM]
start_skill_intake
  └─ SkillRunCrud.create_run(pending)
  └─ message.add_message(assistant, skill_intake={phase:collecting, run_id})
  └─ update_meta(skill_ids=[wizard_id], mcp_ids=[])

SkillIntakePanel 循环:
  POST /skill-runs/{id}/files        → WorkspaceService.save_upload → input/
  POST /skill-runs/{id}/inputs       → merge run.input_data
  PUT  .../messages/{id}/skill-intake → 更新 phase / step_index

[执行阶段 — 调用 LLM]
submitAndStart:
  POST /skill-runs/{id}/validate     → skill_run_validator.validate_run_inputs
  POST /skill-runs/{id}/start
       ├─ ensure_skill_snapshot → .skill_snapshot/
       ├─ begin_skill_run_reply → execution 消息 + freeze_intake(submitted)
       └─ create_task(execute_skill_run)

execute_skill_run
  └─ skill_run_agent_stream(run_mode=True)
       └─ ChatAgentOrchestrator.stream
            ├─ resolve_chat_binding(run_mode=True)  ← 允许 wizard Skill
            ├─ skill_cwd = workspace.root
            ├─ skill_md_path = .skill_snapshot/SKILL.md
            ├─ allow_skill_write=True → skill_write 可写 output/
            ├─ _retrieve_context(run.knowledge_base_ids)
            └─ ReAct（无 chat_history，max_history_rounds=0）

并行: GET /skill-runs/{id}/stream ← SkillRunEventHub 订阅 SSE
```

#### c. 出口

| 维度 | 说明 |
|------|------|
| **后端认为完成** | `execute_skill_run` 循环结束无 error → `run.status = "completed"` |
| **持久化** | `persist_skill_run_conversation_message` 更新 execution 消息正文、`skill_run_ref`、`process_trace` |
| **产物** | `output/` 下文件；`GET /skill-runs/{id}/outputs` 列表与下载 |
| **用户感知** | intake 面板 phase=submitted；下方 execution 气泡流式/最终摘要；执行记录页可下载 |
| **失败** | `run.status=failed`，`error_message` 写入；execution 消息展示错误 |

**完成判定代码：**

```text
skill_run_executor.py · execute_skill_run
  → run.status = "completed"
  → persist_skill_run_conversation_message(...)
  → SkillRunEventHub.finish(run_id)
```

---

### 2.4 路径 C：async_job 模式

与 wizard **收集入口、过程相同**；差异：

| 环节 | 代码 |
|------|------|
| 触发启动 | `skill_run_crud.start_run` · `mode == "async_job"` |
| 异步投递 | `execute_skill_run_async.delay(run.id, user.id, question)` |
| Worker | `celery_scheduler/tasks/task_run_skill.py` → `execute_skill_run(..., publish_events=False)` |
| 出口 | 同 wizard，但 **无 Run SSE**；前端轮询 `GET /skill-runs/{id}` |
| 用户感知 | execution 消息首句「异步任务已提交…」；完成后轮询刷新 |

---

### 2.5 完整调用链路地图

```text
═══════════════════════════════════════════════════════════════════════════
                         KeenRobot Skill 调用链路总图
═══════════════════════════════════════════════════════════════════════════

[磁盘] workspace/.claude/skills/{skill_key}/SKILL.md
         │
         │ POST /skills/sync 或 /skills/upload
         ▼
[DB] keenrobot_skills (interaction_mode, input_schema, execution, is_enabled)
         │
         ├─────────────────────────────┬──────────────────────────────┐
         ▼                             ▼                              ▼
   interaction_mode=chat      interaction_mode=wizard      interaction_mode=async_job
         │                             │                              │
┌────────┴────────┐          ┌────────┴────────┐           ┌────────┴────────┐
│ 智能聊天页       │          │ 智能聊天页       │           │ 同 wizard 收集   │
│ 魔杖 Picker     │          │ Skill 任务 Picker│           │                 │
│ selectedSkills  │          │ SkillIntakePanel │           │                 │
└────────┬────────┘          └────────┬────────┘           └────────┬────────┘
         │ sendMessage                 │ submitAndStart                  │
         ▼                             ▼                              ▼
 POST /chat/stream              POST .../skill-intake/start      (同上 intake)
         │                             │                              │
         ▼                             ▼                              ▼
 conversation_crud              create_run(pending)              create_run(pending)
 .prepare_for_chat              + skill_intake 消息              + skill_intake 消息
 .stream_response                     │                              │
         │                       validate + start                      │
         │                             │                              │
         ▼                             ▼                              ▼
 skill_agent_stream              execute_skill_run                start_run → Celery
 (薄封装)                             │                              │
         │                             └──────────────┬───────────────┘
         │                                            ▼
         └──────────────────────► ChatAgentOrchestrator.stream ◄──────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    ▼                       ▼                       ▼
            binding_resolver          _retrieve_context      McpSessionManager
            ensure_chat_snapshot      (KB 向量)              (会话+内嵌 MCP)
            build_hybrid_system_prompt
                    │
                    ▼
            OpenAICompatibleLLM (stream_chat / chat_with_tools)
                    │
                    ▼
            ToolDispatcher → skill_read|glob|write / MCP call_tool
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
   chat: SSE /chat/stream   Run: Hub → SSE /skill-runs/{id}/stream
         │                     │
         ▼                     ▼
   add_message(assistant)   persist_skill_run_conversation_message
                             + output/ 产物
═══════════════════════════════════════════════════════════════════════════
```

---

## 3. Skill 类型选择

### 3.1 为什么区分 Skill 类型？

三种 `interaction_mode` 解决 **三类不同的用户契约**，不能共用同一条 API：

| 矛盾 | 若不区分会怎样 |
|------|----------------|
| **输入形态** | wizard 必须先上传文件、填表；若走 `/chat/stream`，无法校验结构化输入 |
| **输出形态** | 任务型 Skill 要写 `output/report.md`；chat 禁止 `skill_write`，避免污染会话 |
| **执行时长** | 长任务占满 HTTP/SSE；async_job 需 Celery 脱离 Web 进程 |
| **UI 形态** | 自由输入框 vs 多步向导 vs 后台轮询，前端组件完全不同 |

因此：**类型是路由键**，决定入口 API、工作区形态、进度推送方式；**不是**三套 LLM 引擎。

### 3.2 每一种 Skill 类型的用途

| 类型 | 典型场景 | 用户路径 | 工作区 | 写文件 | 进度 |
|------|----------|----------|--------|--------|------|
| **chat** | 领域助手、规范回复风格、按需读 Skill 包内规则 | 选 Skill → 像普通聊天一样提问 | 会话 `.skill_snapshot` | ❌ | chat SSE |
| **wizard** | 报告生成、ETL 单次任务、需上传+确认 | Skill 任务 → 向导 → 确认并开始 | `runs/.../input+output` | ✅ | Run SSE |
| **async_job** | 批处理、分钟级任务、无需盯进度 | 同 wizard 收集 | 同 wizard | ✅ | 轮询 |

**选型决策树：**

```text
需要多轮自由对话？ ──是──► 还需要先上传/填表才能跑？ ──否──► chat
                              │
                              └──是──► 执行 >1min 或必须后台？ ──是──► async_job
                                                              └──否──► wizard
```

### 3.3 配置字段全表：含义与代码生效点

#### DB 表 `keenrobot_skills`

| 字段 | 作用 | 生效代码（关键路径） |
|------|------|----------------------|
| `skill_key` | 磁盘目录名 | `skill_registry.get_skills_root() / skill_key`；快照复制源 |
| `name` / `description` | 管理页与 Picker 展示 | 前端列表；`SkillOut` |
| `skill_version` | 磁盘包 hash | `compute_skill_version`；`ensure_chat_snapshot` 比对是否重建 |
| `interaction_mode` | **路由键** | `_partition_skill_ids`；`load_skill_for_binding(run_mode)`；`SkillRunCrud.RUN_MODES`；前端 `skillPickerItems` / `wizardSkillPickerItems` 过滤 |
| `input_schema` | 向导步骤 + layout | `validate_input_schema`（启用门禁）；`SkillIntakePanel` 渲染步骤；`validate_run_inputs`；`WorkspaceService.layout_roots` / `step_target_path` |
| `execution.prefer_async` | 展示/文档用 | 实际 async 由 `interaction_mode=async_job` 决定 |
| `execution.estimated_duration` | 展示用 | 暂无后端强制逻辑 |
| `execution.mcp_ids` | Skill 内嵌 MCP | `resolve_embedded_mcp_ids` → `binding_resolver` 与会话 MCP 合并 |
| `is_enabled` | 是否可选 | `_validate_skill_access`；前端 Picker 过滤 |
| `source` | filesystem / custom | sync 写入 filesystem |

#### `input_schema` 子字段

| 字段 | chat | wizard/async | 生效代码 |
|------|------|--------------|----------|
| `wizard_steps[]` | 可 `[]` | 非空 | `skill_validation.validate_input_schema`；`SkillIntakePanel.wizardSteps`；`skill_run_validator` |
| `wizard_steps[].type` | — | file/dir/text/choice/confirm | 前端控件分支；validator 分支 |
| `wizard_steps[].key` | — | 必填 | 写入 `input_data[key]` 或决定 upload 路径 |
| `wizard_steps[].path` | — | 可选 | `WorkspaceService.step_target_path` |
| `layout.input_root` | 默认 input | 上传目录前缀 | `layout_roots` |
| `layout.output_root` | 默认 output | `skill_write` 允许前缀 | `skill_file_tools._resolve_write_path`；Run `output_prefix` |

#### 会话 / Run 级字段（非 Skill 表，但与 Skill 强相关）

| 字段 | 位置 | 作用 | 生效代码 |
|------|------|------|----------|
| `conversation.skill_ids` | 会话 | 绑定 Skill | `prepare_for_chat` / `sync_conversation_bindings` |
| `conversation.knowledge_base_ids` | 会话 | KB 与 Skill **并行** | `_retrieve_context` in Orchestrator |
| `conversation.mcp_ids` | 会话 | MCP 与 chat Skill **并行** | `resolve_chat_binding` session_mcp |
| `run.input_data` | SkillRun | 向导表单值 | 注入 Run system `extra_system`；validator |
| `run.knowledge_base_ids` | SkillRun | Run 级 KB | `skill_run_agent_stream` → Orchestrator |
| `message.skill_intake` | Message | 向导 UI 状态 | 前端 `SkillIntakePanel` |
| `message.skill_run_ref` | Message | 执行结果链接 | 前端 execution 气泡 |

### 3.4 如何配置一个新 Skill（标准流程）

```text
1. 编写磁盘包
   workspace/.claude/skills/{skill_key}/SKILL.md + 资源目录

2. 安装
   管理页「同步磁盘 Skill」或 POST /skills/upload

3. 管理页编辑（DB）
   - 选 interaction_mode
   - 粘贴 input_schema / execution JSON
   - wizard/async：配置 wizard_steps 后再启用
   - 可选：execution.mcp_ids 多选 MCP

4. 启用 is_enabled = true

5. 智能聊天验证
   - chat：魔杖选择 → 发消息
   - wizard/async：Skill 任务 → 走完向导 → 看执行记录与 output/
```

---

## 4. 能力边界评估（是否支持通用 Skill / 知识库 / MCP）

### 4.1 是否完整支持「通用 Skill」？

**结论：支持 KeenRobot 定义的通用 Skill 包形态；不是 Anthropic Claude Code 的 Skill SDK 1:1 移植。**

| 能力 | 支持度 | 说明 |
|------|--------|------|
| 磁盘 `SKILL.md` + 目录资源 | ✅ 完整 | `skill_registry` 扫描、版本 hash、zip 安装 |
| 指令注入 LLM | ✅ 完整 | `build_hybrid_system_prompt` 注入 `skill_instruction` |
| 文件读/列目录 | ✅ 完整 | `skill_read` / `skill_glob` |
| 文件写（任务产物） | ✅ Run 模式 | `skill_write` 仅 `run_mode` + `allow_skill_write=True` |
| 多 Skill 同时 chat | ❌ | 会话最多 **1 个** chat Skill |
| 自定义 Skill 工具（除 read/glob/write） | ❌ | 需改 `skill_file_tools.py` 扩展 |
| Elicitation / 人机回路 MCP | ❌ | 用 Skill 向导或对话替代 |
| Run 内调用会话 MCP | ❌ 当前 | `skill_run_agent_stream` 写死 `mcp_server_ids=[]` |

**「通用」实践建议：** 把流程写进 `SKILL.md`，静态资源放磁盘包，动态输入走 wizard `input/`，产物走 `output/`。

### 4.2 是否支持 Skill 读取「知识库文档」？

**结论：Skill 文件工具不读知识库；会话/Run 可同时开 KB，由 RAG 并行注入。**

```text
用户同时绑定：chat Skill + 知识库
                    │
                    ▼
        ChatAgentOrchestrator._stream_impl
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
 _retrieve_context(kb_ids)   resolve_chat_binding(skill)
 Chroma 向量检索              ensure_chat_snapshot
 → 写入 system prompt         → SKILL.md + skill_read 只读快照目录
   「参考资料」段落              （不含 KB 里的 PDF/文档）
```

| 方式 | 能否读到 KB 文档 | 机制 |
|------|------------------|------|
| 会话绑定 KB + chat Skill | ✅ | `_retrieve_context` → RAG prompt；与 Skill 正交 |
| Run 绑定 KB（intake 时传 `knowledge_base_ids`） | ✅ | `run.knowledge_base_ids` → 同上 |
| `skill_read` 读 KB 路径 | ❌ | 工具只能读快照/Run 工作区内的相对路径 |
| Skill 磁盘包内自带 PDF | ⚠️ 间接 | 放 `.skill_snapshot` 下，用 `skill_read` 读；**不是** KB 管理里的文档 |

**维护含义：** 要让 Skill「用企业知识」，应 **会话同时选 KB**，在 `SKILL.md` 里写「结合参考资料回答」，而不是指望 `skill_read` 访问 Chroma。

### 4.3 是否支持 Skill 使用 MCP？

**结论：chat 模式完整支持（会话 MCP + Skill 内嵌 MCP）；Run 模式当前不支持会话 MCP。**

| 场景 | MCP 来源 | 代码 |
|------|----------|------|
| chat Skill + 用户选 MCP | `conversation.mcp_ids` | `binding_resolver` session_mcp |
| chat Skill 内嵌 MCP | `execution.mcp_ids` | `resolve_embedded_mcp_ids` → embedded_mcp |
| 两者重复 server | 去重 | `merge_mcp_server_lists` 按 `server.id` |
| chat Skill + MCP 同轮调用 | ✅ | `ToolDispatcher` skill 步 + mcp 步 |
| wizard/async Run 执行 | ❌ 当前 | `skill_run_agent_stream(..., mcp_server_ids=[])` |
| wizard 收集中选 MCP | ❌ UI | `mcpPickerDisabled`；`start_skill_intake` 写 `mcp_ids=[]` |

**扩展 Run+MCP：** 改 `skill_agent.py` 传入 `mcp_server_ids`；`begin_skill_run_reply` / intake 放开 MCP 绑定。

---

# 第二部分：维护 / 扩展 / 配置教程

## 5. 新手学习路径（建议 3～5 天）

### Day 1：建立全局图景

1. 读本文 **§1～§2.5** + `CHAT_EXECUTION_FLOWS.md` §0～§4  
2. 本地打开 `test_chat_skill`，Skills 管理页 sync → 启用 → 聊天页魔杖选择 → 发 `ping`  
3. 对照浏览器 Network：`/chat/stream` SSE 事件

**验收：** 能说出 chat Skill 从 Picker 到 `add_message(assistant)` 的 5 个关键函数名。

### Day 2：磁盘包与 DB 配置

1. 读 `TEST_SKILLS.md`，走完 `test_wizard_skill` 向导全流程  
2. 读 `skill_registry.py`、`skill_validation.py`  
3. 管理页改 `input_schema` 一个字段，观察 `SkillIntakePanel` 变化

**验收：** 能独立写四步 `wizard_steps` JSON 并通过 validate。

### Day 3：Run 执行与 Orchestrator

1. 断点或日志跟踪：`start_run` → `execute_skill_run` → `skill_run_agent_stream`  
2. 读 `chat_agent_orchestrator.py` ReAct 循环、`tool_dispatcher.py`  
3. 查看 Run 工作区 `workspace/runs/{user_id}/{run_id}/`

**验收：** 能解释 `run_mode=True` 与 chat 的 3 处差异（校验、cwd、skill_write）。

### Day 4：KB + MCP 组合

1. chat 同时绑 KB + `test_chat_skill` + 一个 MCP，观察 process_trace  
2. 读 `binding_resolver.py` 内嵌 MCP 去重  
3. 读 `MCP_INTEGRATION.md` §4

**验收：** 能说明 KB 与 `skill_read` 的职责边界（§4.2）。

### Day 5：改一个真实 Skill

1. 复制 `test_chat_skill` 为新 `skill_key`，改 `SKILL.md`  
2. sync → 配置 → 启用 → 联调  
3. 可选：为 wizard 增加一步 `text` 字段，改 validator 与前端

**推荐代码阅读顺序：**

```text
views/chat/index.vue
  → api/index.js (chatStream)
  → conversation/views/chat_view.py
  → conversation_crud.py (prepare_for_chat, stream_response)
  → skill_agent.py
  → chat_agent_orchestrator.py
  → binding_resolver.py + tool_dispatcher.py + skill_file_tools.py
  → SkillIntakePanel.vue + skill_run_crud.py + skill_run_executor.py
```

---

## 6. 配置教程（逐步操作）

### 6.1 chat 模式（复制即用）

**磁盘：** `workspace/.claude/skills/my_chat_skill/SKILL.md`

**DB（管理页编辑抽屉）：**

| 项 | 值 |
|----|-----|
| 交互模式 | `chat` |
| 启用 | 开 |
| input_schema | 见下 |
| execution | `{"prefer_async":false,"estimated_duration":"short"}` |

```json
{
  "wizard_steps": [],
  "layout": { "cwd": ".", "input_root": "input", "output_root": "output" }
}
```

**验证：** 魔杖选中 → 普通问题无 tool 步骤 → 联调命令触发 `skill_read`。

### 6.2 wizard 模式

**input_schema 模板：** 见 §3.3 与 `test_wizard_skill`（file → text → choice → confirm）。

**SKILL.md 必写：** 输入从哪读（`input/`）、产物写哪（`output/`）、必用 `skill_read` 读哪些模板。

**验证：** 执行记录 `completed`；`GET .../outputs` 有文件。

### 6.3 async_job 模式

**前置：** Celery worker 已启动（见 `TEST_SKILLS.md`）。

**DB：** `interaction_mode=async_job`，`execution.prefer_async=true`。

**验证：** 无 Run SSE；轮询 `GET /skill-runs/{id}` 至 `completed`。

### 6.4 内嵌 MCP（仅 chat 绑定时生效）

管理页 execution 多选 MCP，或 JSON：

```json
{
  "prefer_async": false,
  "estimated_duration": "short",
  "mcp_ids": ["<MCP服务UUID>"]
}
```

生效链：`agent_crud.update_skill` → `validate_embedded_mcp_access` → 聊天时 `binding_resolver` 合并。

---

## 7. 常见问题与排障

| 现象 | 可能原因 | 排查 |
|------|----------|------|
| 「需通过 Skill 向导执行」 | wizard Skill 走了 `/chat/stream` 或 Run 未 `run_mode` | 查 `interaction_mode`、入口 API |
| 改了 SKILL.md 不生效 | 快照未刷新 | 改磁盘 hash / 新会话；Run 重新 start |
| 启用报 input_schema | wizard/async 未配 steps | `validate_skill_enable` |
| validate 缺文件 | upload 路径与 step 不一致 | `step_target_path` vs 实际上传 |
| wizard 空白执行 | 旧 bug：Run 未 run_mode | 确认 `load_skill_for_binding(run_mode=True)` |
| Skill 不读 KB | 设计如此 | 会话另选 KB，靠 RAG |
| Run 调不了 MCP | 当前未接 | §4.3 |
| async 一直 pending | Celery 未起 | worker 日志 |

---

## 8. 扩展开发指南

| 需求 | 改动点 | 风险 |
|------|--------|------|
| 新 wizard 步骤类型 | `WIZARD_STEP_TYPES` + validator + `SkillIntakePanel` | 前后端同步发版 |
| 新 Skill 工具 | `skill_file_tools.py` + `build_skill_tool_registry` | 路径安全 |
| Run 支持 MCP | `skill_run_agent_stream` + intake 绑定 | 工作区与审计 |
| Run SSE 跨 worker | `SkillRunEventHub` → Redis | 部署架构 |
| 多 chat Skill | `_resolve_and_validate_bindings` + 前端 | 工具/registry 冲突 |
| Skill 直读 KB | **不推荐**；应走 RAG | 权限与索引 |

**不要破坏的 invariant：**

- wizard/async **禁止**直接 `/chat/stream`  
- `skill_write` 仅 Run + `output/` 前缀  
- chat 快照与 Run 快照分离（会话 vs run 目录）

---

## 9. API 与状态机速查

### 9.1 核心 API

| 方法 | 路径 | Skill 场景 |
|------|------|------------|
| POST | `/chat/stream` | chat Skill 执行 |
| PUT | `/conversations/{id}/bindings` | 绑定 Skill |
| POST | `/conversations/{id}/skill-intake/start` | 开始 wizard 收集 |
| POST | `/skill-runs/{id}/validate` | 校验向导输入 |
| POST | `/skill-runs/{id}/start` | 启动 Run |
| GET | `/skill-runs/{id}/stream` | wizard 进度 SSE |
| GET | `/skill-runs/{id}/outputs/{path}` | 下载产物 |
| POST | `/skills/sync` | 磁盘 → DB |
| PUT | `/skills/{id}` | 改 integration 配置 |

### 9.2 状态机

**skill_intake.phase：** `collecting` → `confirming` → `submitted` | `cancelled` | `stale`

**SkillRun.status：** `pending` → `validated` → `running` → `completed` | `failed` | `cancelled`

---

## 10. 相关文档与测试 Skill

| 文档 | 内容 |
|------|------|
| `CHAT_EXECUTION_FLOWS.md` | 智能聊天全链路（含 Skill 章节） |
| `TEST_SKILLS.md` | test_chat / test_wizard / test_async_job 断言 |
| `HYBRID_AGENT_ORCHESTRATION.md` | Skill+MCP 组合、E2E 矩阵 |
| `MCP_INTEGRATION.md` | MCP 与 Skill 内嵌 |

| skill_key | 用途 |
|-----------|------|
| `test_chat_skill` | chat + 工具 + 普通对话共存 |
| `test_wizard_skill` | 四步向导 + 双产物 |
| `test_async_job_skill` | Celery + 三文件 |

---

*同步基准（2026-06-26）：单 `ChatAgentOrchestrator`；chat/Run 共用；KB 经 RAG 与 Skill 并行；chat Skill+MCP 可组合；Run `mcp_server_ids=[]`；绑 Skill 即注册 skill 工具。*
