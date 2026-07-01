# 混合智能体统一编排 — 设计与实施计划

> 版本：2026-06-26  
> 状态：**Phase 0～5 已实施**（2026-06-26，含 RAG 路径统一）  
> 关联：`MCP_INTEGRATION.md`、`CHAT_EXECUTION_FLOWS.md`、`conversation_crud.py`、`orchestrator.py`、`skill_agent.py`  
> 目标：企业级稳定态 — 单一聊天 Runtime、可组合 Agent 能力、调用链清晰、去除模糊策略

---

## 1. 背景与决策

### 1.1 产品定位

KeenRobot 智能聊天是 **混合智能体（Hybrid Agent）**：

| 层级 | 能力 | 用户感知 |
|------|------|----------|
| **基础** | 流式问答 | 直接对话 |
| **增强** | 知识库 RAG | 可绑定多个 KB，横切所有模式 |
| **Agent 能力包** | MCP Agent | 用户在会话中启用 → 外部 MCP 工具可用 |
| **Agent 能力包** | Skill Agent | 用户在会话中启用 → Skill 指令 + 文件工具可用 |

**核心原则（已确认）：**

1. **MCP 与 Skill 是独立的 Agent 能力包**，由用户在会话中 **显式启用**（绑定），再与 **同一个会话 LLM** 交互。
2. **解除** 聊天层 Skill 与会话级 MCP 的 **硬互斥**；允许 **1 chat Skill + N MCP** 同时绑定（MCP 多选；chat Skill 仍单选，见 §3.2）。
3. **统一编排**：聊天 ReAct 只保留 **一条** Runtime 管道，收拢 `McpAgentOrchestrator` 与 `skill_agent_stream` 的重复逻辑。
4. **企业级稳定态**：删除 `on_demand`、关键词门控等模糊策略；能力边界 **可配置、可预期、可审计**。
5. **是否调用具体工具** 仍由 LLM function calling 决定；**是否具备工具能力** 由会话绑定决定（绑了即注册工具，不再「有时连工具链都不进」）。

### 1.2 明确不做 / 不在本期

| 项 | 说明 |
|----|------|
| **Elicitation** | 已放弃，见 `MCP_INTEGRATION.md` |
| **多 chat Skill 并列** | 仍限制 1 个 chat Skill（多 snapshot / 多指令冲突） |
| **LLM 调 LLM 子 Agent** | 不引入；「Agent」= 能力包 + 编排，非第二个模型进程 |
| **wizard / async_job 与 MCP 自由组合** | intake / Run 路径保持独立；Run 可复用 ToolDispatcher |
| **Supervisor 自动路由** | 不自动猜用户要用 MCP 还是 Skill；由 **会话绑定** 声明 |

---

## 2. 现状问题

### 2.1 调用链分散

```text
POST /chat/stream
  → stream_response
       ├─ skill_ids → skill_agent_stream → _skill_agent_loop
       ├─ mcp_ids   → McpAgentOrchestrator.stream
       └─ 否则      → ChatAgentOrchestrator（tools=[]，等价原 rag_stream）
```

三套入口、两套 ReAct 循环（Skill / MCP），RAG 第三套；审计、取消、SSE 事件格式重复维护。

### 2.2 互斥与语义冲突

- 后端 `Skill 与 MCP 不能同时启用`；前端 picker 互斥 watcher。
- 与「混合智能体、能力可组合」目标不一致。
- Skill 已通过 `execution.mcp_ids` 内嵌 MCP，证明 **组合可行**，互斥仅为路由层历史约束。

### 2.3 模糊策略（需移除）

| 策略 | 问题 |
|------|------|
| `chat_tools: on_demand` | 绑 Skill 但未命中关键词时不注册工具，与「启用 Skill Agent」叙事冲突 |
| `_CHAT_TOOL_TRIGGER_PATTERNS` | 正则 brittle、难审计、与 MCP「绑即注册」不对称 |
| `use_tools` 三分支 | 同一绑定在不同消息上行为不一致 |

**目标态：** 会话绑定声明能力 → Runtime **始终** 按绑定组装 tools + system → LLM **按需** call_tool（与 MCP 一致）。

---

## 3. 目标架构

### 3.1 概念模型

```text
┌──────────────────────────────────────────────────────────────────┐
│  Hybrid Chat Runtime（一次 /chat/stream 请求）                     │
│                                                                   │
│  SessionBinding（会话级，用户显式启用）                            │
│    · knowledge_base_ids[]   横切 RAG                              │
│    · chat_skill_id?         0~1  Skill Agent 能力包               │
│    · mcp_server_ids[]       0~N  MCP Agent 能力包                 │
│    · model_config / enable_thinking                               │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  ChatAgentOrchestrator（统一 ReAct + SSE）                   │ │
│  │    1. resolve_binding → 加载 Skill snapshot / MCP servers  │ │
│  │    2. build_context → RAG + Skill 指令 + MCP metadata        │ │
│  │    3. build_tool_registry → Skill tools ∪ MCP tools          │ │
│  │    4. McpSessionManager（有 MCP 才 open）                    │ │
│  │    5. ReAct loop → ToolDispatcher.execute                    │ │
│  │    6. audit / cancel / process_trace                         │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                    │
│                    同一会话 LLM（OpenAICompatibleLLM）             │
└──────────────────────────────────────────────────────────────────┘
```

**「独立 Agent」含义：** Skill Agent、MCP Agent 是 **可独立启用的能力模块**（指令块 + 工具集 + 运行时依赖），不是独立 LLM 服务。

### 3.2 绑定规则（企业级稳定态）

| 绑定项 |  cardinality | 校验 |
|--------|--------------|------|
| 知识库 | 0~N | 现有 `_validate_kb_access` |
| chat Skill | 0~1 | `interaction_mode=chat`，有 `skill_key` |
| 会话 MCP | 0~N | 已 refresh tools，`is_enabled` |
| Skill 内嵌 MCP | 自动 | `execution.mcp_ids` 与 `mcp_server_ids` **并集去重** |
| wizard Skill | 独立 | 仍走 intake / Run，**不**与会话 MCP 绑定混在同一 `/chat/stream` ReAct |

**删除：** Skill ∩ MCP 非空 → 400。

### 3.3 统一路由

```text
POST /chat/stream
  → prepare_chat_stream（绑定校验、写 user message）
  → stream_response
       ├─ 有 chat_skill_id 或 mcp_ids 或 仅 KB 需 Agent？ 
       │     → ChatAgentOrchestrator.stream（统一入口）
       └─ 无 Skill、无 MCP、无工具需求
             → 可选：仍走 Orchestrator（tools=[]）或保留 rag_stream 轻量短路（见 Phase 4）
```

**推荐终态：** 全部走 `ChatAgentOrchestrator`；`tools=[]` 时等价原 `rag_stream`，减少第三套链路。

### 3.4 工具策略（替代 on_demand）

| 绑定 | 工具注册 | LLM 行为 |
|------|----------|----------|
| 无 Skill、无 MCP | 无 tools | 纯流式 + RAG |
| 仅 Skill | skill_read, skill_glob（chat 无 write） | prompt 约束；**按需 call** |
| 仅 MCP | MCP tools | prompt 约束；**按需 call** |
| Skill + MCP | 合并 registry（前缀防冲突） | 同一 ReAct；**按需 call** |

**删除：** `chat_tools`、`on_demand`、`always`、`_CHAT_TOOL_TRIGGER_PATTERNS`、`_question_needs_skill_tools`。

**保留：** `HYBRID_AGENT_CHAT_SKILL_SECTION` 中「普通对话勿滥调工具」改为 **企业级表述**（与 MCP 规则对称），而非代码层禁用 tool 链。

### 3.5 目标包结构

```text
backend/applications/agent/
├── orchestrator/
│   ├── chat_agent_orchestrator.py   # 统一 ReAct + SSE（原 mcp/orchestrator 升格）
│   ├── binding_resolver.py          # 加载 Skill/MCP/KB、去重、校验
│   ├── context_builder.py           # system prompt 分段组装
│   └── tool_dispatcher.py           # Skill / MCP 工具执行
├── policies/
│   └── hybrid_agent_policy.py       # 原 McpAgentPolicy 扩展/更名
└── ...（skill_file_tools 不变）

backend/applications/mcp/
├── session_manager.py               # 不变，Host 层
├── client_factory.py
├── callbacks.py
├── audit.py
├── cancel_scope.py
└── adapters.py

backend/applications/base/rag/
├── chain.py                         # RAG 检索（被 context_builder 调用）
├── skill_agent.py                   # 变薄：Run/wizard 专用 + delegate 可选
└── llm.py
```

**命名建议：** `McpAgentOrchestrator` → `ChatAgentOrchestrator`；`McpAgentPolicy` → `HybridAgentPolicy`（保留 `applications/mcp/policies.py` 再 export 别名一个版本，逐步删除）。

---

## 4. 核心组件设计

### 4.1 `ResolvedChatBinding`

```python
@dataclass
class ResolvedChatBinding:
    knowledge_base_ids: list[str]
    chat_skill: Skill | None
    chat_skill_snapshot: Path | None      # .skill_snapshot 目录
    chat_skill_cwd: Path | None         # 工作区根
    mcp_servers: list[McpServer]        # 会话 MCP ∪ Skill 内嵌 MCP，按 server.id 去重
    openai_tools: list[dict]
    tool_registry: dict[str, ToolRoute] # openai_name → ToolRoute

@dataclass
class ToolRoute:
    kind: Literal["skill", "mcp"]
    skill_tool: str | None              # skill_read / skill_glob / skill_write
    mcp_server: McpServer | None
    mcp_tool_name: str | None
```

### 4.2 `ToolDispatcher`

```python
class ToolDispatcher:
    def __init__(self, *, ctx: ToolExecutionContext): ...

    async def execute(
        self,
        openai_tool_name: str,
        arguments: dict,
        *,
        step_dict: dict,
    ) -> tuple[str, dict]:  # result_text, updated step_dict
```

- **Skill 分支：** `execute_skill_tool(cwd, ...)` → `SkillStep`
- **MCP 分支：** `mcp_session.call_tool(...)` → `McpStep`
- **Cancel / Audit：** 统一在 MCP 分支走现有 `cancel_scope` / `schedule_mcp_audit`；Skill 文件工具可选记 audit（event_type=`skill_tool`）

### 4.3 `ChatAgentOrchestrator.stream`

**输入：** `question`, `user`, `conversation_id`, `ResolvedChatBinding`, `HybridAgentPolicy`, LLM 参数。

**流程：**

1. `bind_mcp_audit_context` / `bind_mcp_cancel_scope`（有 MCP 或 Skill 内嵌 MCP 时）
2. `format_messages` + `context_builder.build_system(...)`
3. 若 `binding.openai_tools` 非空 → `McpSessionManager.open_servers`
4. 可选 `inject_resource_contents`（仅 MCP servers）
5. ReAct：`max_tool_rounds`、`parallel_tool_calls`、`on_max_rounds`（统一 policy）
6. `_dispatch_tool_calls` → `ToolDispatcher`
7. `drain_process_events`（sampling / log）
8. `_stream_final_answer` 或 `llm.stream_chat`（无 tools 时）

**System prompt 分段（顺序）：**

1. `HYBRID_AGENT_CORE_SYSTEM_PROMPT`（统一行为准则：RAG、工具按需、中文、安全）
2. Skill 段（若启用）：`HYBRID_AGENT_CHAT_SKILL_SECTION` + SKILL.md 正文
3. MCP 段（若启用）：`build_mcp_metadata_block` + 可选 resource 注入
4. RAG 段：`_resolve_system_prompt`

### 4.4 `HybridAgentPolicy`

```python
@dataclass
class HybridAgentPolicy:
    max_tool_rounds: int = 10
    parallel_tool_calls: bool = True
    on_max_rounds: Literal["error", "summarize"] = "summarize"
    inject_resource_contents: bool = True
    max_injected_resource_chars: int = 8000
    max_resources_per_server: int = 5
    sampling_mode: Literal["reject", "llm"] = "llm"
    log_mcp_progress: bool = True
    audit_enabled: bool = True
    audit_max_chars: int = 4096
    # chat 模式 Skill 禁止 skill_write（Run 模式 override）
    allow_skill_write: bool = False
```

---

## 5. 与现有模块的关系

| 模块 | 变更 |
|------|------|
| `conversation_crud.stream_response` | 单入口 `ChatAgentOrchestrator`；删互斥 |
| `conversation_crud._resolve_and_validate_bindings` | 删 Skill∩MCP 校验；保留 chat Skill ≤1 |
| `mcp/orchestrator.py` | 迁移 → `agent/orchestrator/chat_agent_orchestrator.py`；旧类 deprecated 1 版本 |
| `skill_agent_stream` | 解析 Skill snapshot 后 **delegate** Orchestrator |
| `_skill_agent_loop`（Run） | Phase 2 改用 `ToolDispatcher`；保留 cwd / write / Run 取消 |
| `rag_stream` | thin wrapper → `ChatAgentOrchestrator`（需 `user`） |
| `McpSessionManager` | 不变 |
| `frontend chat/index.vue` | 去互斥 watcher；Skill + MCP 可同时选 |
| `TEST_SKILLS.md` | 删除 `chat_tools` / on_demand 文档 |
| `CHAT_EXECUTION_FLOWS.md` | 重写 §B/C 为统一 Hybrid 流 |
| `MCP_INTEGRATION.md` | §2.4 更新：Skill 与 MCP 可组合 |

---

## 6. 实施阶段

### Phase 0 — 基线与文档冻结（1 天）

- [x] 本文件评审通过
- [x] E2E 基线用例跑通并记录（见 §8）
- [x] ~~Feature flag~~：未引入，直接切换统一 Orchestrator

**交付：** 基线报告；无行为变更。

---

### Phase 1 — ToolDispatcher + BindingResolver（2~3 天）

- [x] 新增 `binding_resolver.py`：加载 Skill/MCP、内嵌 MCP 并集、build registry
- [x] 新增 `tool_dispatcher.py`：从 `skill_agent._execute_agent_tool` + `orchestrator._finish_tool_call` 抽取
- [ ] 单元测试：Skill only / MCP only / 合并 registry / 重名前缀（后续补）

**验收：** Dispatcher 独立测试通过；**尚未切换**生产路径。

---

### Phase 2 — ChatAgentOrchestrator（3~4 天）

- [x] 实现 `chat_agent_orchestrator.py`（合并两套 ReAct、parallel、summarize、SSE 事件）
- [x] 实现 `context_builder.py`、`hybrid_agent_policy.py`
- [x] 删除 on_demand 相关代码路径
- [x] `stream_response` 走 ChatAgentOrchestrator
- [x] `skill_agent_stream` delegate 到新 Orchestrator（chat 模式）

**验收：**

- chat Skill only / MCP only / **Skill + MCP** / KB+RAG
- 无关问题不调工具（LLM 行为，非关键词门控）
- process_trace 含 skill + mcp 步骤
- cancel / audit 正常

---

### Phase 3 — 解除互斥 + 前端（1 天）

- [x] 删除 `_resolve_and_validate_bindings` 互斥
- [x] `chat/index.vue`：删 Skill/MCP 互斥 watcher 与 `buildBindingPayload` 清空逻辑
- [x] picker 文案：Skill 与 MCP 可同时启用

**验收：** 同时绑定保存成功；E2E 组合场景通过。

---

### Phase 4 — 路由收紧与清理（2 天）

- [x] `stream_response` 始终 ChatAgentOrchestrator（无 feature flag）
- [x] `rag_stream`：thin wrapper → Orchestrator；无关问题短路在 Orchestrator
- [x] `McpAgentOrchestrator` 保留 re-export 别名；删除重复 ReAct 实现
- [x] Run 接 ToolDispatcher（`_skill_agent_loop` chat 分支已移除）
- [x] 更新 `CHAT_EXECUTION_FLOWS.md`、`MCP_INTEGRATION.md`、`TEST_SKILLS.md`

**验收：** 全量回归 §8；无 dead code（on_demand、trigger patterns）。

---

### Phase 5 — Skill Run 对齐（可选，1~2 天）

- [x] Run 模式 tool 执行统一 `ToolDispatcher`
- [x] audit context 带 `skill_run_id`
- [x] 不改变 Run 工作区语义

---

## 7. 前端与 API 契约

### 7.1 会话绑定（不变字段，变语义）

`PUT /history/{id}/bindings` / `ChatRequest`：

```json
{
  "knowledge_base_ids": ["..."],
  "skill_ids": ["chat-skill-id"],
  "mcp_ids": ["mcp-a", "mcp-b"],
  "model_config_id": "...",
  "enable_thinking": false
}
```

- `skill_ids`：chat 模式仍 **最多 1 个** 参与 stream；wizard id 仍可存会话但不与 stream ReAct 混用
- `mcp_ids`：多个；与 Skill 内嵌 MCP 后端去重

### 7.2 SSE 事件（不变）

`token` / `reasoning` / `process` / `done` / `error` — 保持现有前端解析。

### 7.3 process_trace step 类型

仍为 `reasoning` | `skill` | `mcp`；同一轮可同时出现 skill 与 mcp 步骤。

---

## 8. E2E 验收矩阵

| ID | KB | chat Skill | 会话 MCP | Skill 内嵌 MCP | 预期 |
|----|----|------------|----------|----------------|------|
| H1 | — | — | — | — | 纯流式（+ 可选 RAG 空） |
| H2 | ✓ | — | — | — | RAG 注入，无 tool step |
| H3 | ✓ | — | ✓ | — | MCP 按需 call |
| H4 | ✓ | ✓ | — | — | Skill 指令生效；按需 skill_read |
| H5 | ✓ | ✓ | ✓ | — | **组合**；两种 tool 均可出现 |
| H6 | ✓ | ✓ | ✓ | ✓ | server 去重；不双 initialize |
| H7 | ✓ | ✓ | ✓ | — | 闲聊不调任何 tool |
| H8 | — | ✓ | ✓ | — | SSE Abort → MCP cancel |
| H9 | — | wizard | ✓ | — | intake 路径不受影响 |
| H10 | — | ✓ | — | — | 无 on_demand：绑 Skill 即注册 skill 工具 |

---

## 9. 风险与缓解

| 风险 | 缓解 |
|------|------|
| System prompt 过长 | 分段截断 metadata；policy 限制 resource 注入 |
| 工具过多超 context | policy `max_tools_per_request`（后续）；首期监控 token |
| 行为回归（on_demand 移除） | Phase 2 flag；H7/H10 专门回归 |
| 并行 Skill+MCP 混调 | Phase 2 默认 **串行** dispatch；稳定后再 parallel |
| 内嵌 MCP + 会话 MCP 重复 | `binding_resolver` 按 `server.id` 去重 |
| 文档与现网不一致 | Phase 4 统一更新三份 md |

---

## 10. 工期估算

| Phase | 内容 | 人日 |
|-------|------|------|
| 0 | 基线 | 1 |
| 1 | Dispatcher + Resolver | 2~3 |
| 2 | ChatAgentOrchestrator | 3~4 |
| 3 | 去互斥 + 前端 | 1 |
| 4 | 清理 + 文档 | 2 |
| 5 | Skill Run 对齐（可选） | 1~2 |
| **合计** | | **9~13** |

---

## 11. 实施顺序（推荐）

```text
Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5
```

**首个可演示里程碑：** Phase 2 完成 → **1 Skill + N MCP** 同会话聊天。

**企业级稳定态里程碑：** Phase 4 完成 → 单 Runtime、无 on_demand、无互斥、文档一致（**已达成**）。

---

## 12. 附录：删除清单

| 删除/废弃 | 位置 |
|-----------|------|
| `chat_tools` / `on_demand` / `always` | `skill.input_schema` 约定、`TEST_SKILLS.md` |
| `_CHAT_TOOL_TRIGGER_PATTERNS` | `skill_agent.py` |
| `_question_needs_skill_tools` | `skill_agent.py` |
| `_resolve_chat_tools_policy` | `skill_agent.py` |
| `use_tools` 三分支（chat 无工具短路） | `skill_agent_stream` / loop |
| Skill∩MCP `ParameterException` | `conversation_crud.py` |
| 前端 Skill/MCP 互斥 watcher | `chat/index.vue` |
| 独立 `McpAgentOrchestrator` 第二套 ReAct | `mcp/orchestrator.py`（迁移后删重复） |

---

## 13. 附录：统一调用链（目标态）

```text
用户打开会话，绑定 KB / chat Skill / MCP
  ↓
POST /chat/stream
  ↓
conversation_crud.prepare_chat_stream
  → ResolvedChatBinding（无 Skill∩MCP 互斥）
  ↓
conversation_crud.stream_response
  ↓
ChatAgentOrchestrator.stream
  → context_builder（RAG + Skill + MCP metadata）
  → McpSessionManager.open_servers（若有 MCP）
  → ReAct: llm.chat_with_tools
       → ToolDispatcher → skill_file_tools | mcp.call_tool
  → SSE: token | reasoning | process | done
  ↓
message 持久化 process_trace
```

---

*文档维护：实施过程中每完成 Phase 更新对应 checkbox 与「状态」字段。*
