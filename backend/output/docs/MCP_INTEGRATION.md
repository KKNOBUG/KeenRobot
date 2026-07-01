# KeenRobot MCP 集成说明与维护指南

> 版本：2026-06-26  
> Client 选型：**FastMCP**（`fastmcp.Client`）  
> 关联代码：`applications/mcp/`、`agent/orchestrator/`  
> 聊天全链路摘要：见 `CHAT_EXECUTION_FLOWS.md` §0～§4  
> 架构决策：见 `HYBRID_AGENT_ORCHESTRATION.md`（Skill + MCP 可组合、单 Runtime）

---

## 0. 给维护者的小白导读

### 0.1 MCP 在本项目里做什么？

KeenRobot 是 MCP **Host（客户端）**：用户在「MCP 管理」配置外部 MCP Server（高德、12306、filesystem 等），聊天或 Skill 执行时由 LLM **按需调用**这些工具。

**不做的事：** 不自研 MCP 协议；不把 KeenRobot API 暴露成 MCP Server；**不实现 Elicitation**（人机回路用 Skill 向导或对话补齐）。

### 0.2 MCP 挂在哪条链路上？

```text
用户发消息 POST /chat/stream
  → ConversationCrud.stream_response
  → ChatAgentOrchestrator.stream
       → binding_resolver（会话 mcp_ids + Skill 内嵌 execution.mcp_ids，按 server.id 去重）
       → McpSessionManager.open_servers（本请求内复用 Client）
       → ReAct：llm.chat_with_tools → ToolDispatcher → mcp_session.call_tool
       → SSE process 步骤（McpStep）
  → Session 随 async with 结束关闭
```

**别名：** `McpAgentOrchestrator = ChatAgentOrchestrator`（`applications/mcp/orchestrator.py` 仅 re-export，**无第二套 ReAct**）。

### 0.3 维护速查

| 你想改… | 优先看 |
|---------|--------|
| MCP 管理页 CRUD / refresh / sync | `applications/agent/views/` MCP 路由、`agent_crud.py` |
| DB 配置 → FastMCP Client | `mcp/client_factory.py` |
| 请求内连接池、call_tool | `mcp/session_manager.py` |
| MCP Tool → OpenAI function 格式 | `mcp/adapters.py` · `build_openai_tool_specs` |
| 聊天里何时打开 MCP、ReAct 轮次 | `chat_agent_orchestrator.py` + `HybridAgentPolicy` |
| Skill 内嵌 MCP 与会话 MCP 去重 | `binding_resolver.py` · `merge_mcp_server_lists` |
| 审计落库 | `mcp/audit.py` + 表 `keenrobot_mcp_audit` |
| SSE 断开取消 in-flight tool | `mcp/cancel_scope.py` + `chat_view` CancelledError |
| sampling / progress / log 回调 | `mcp/callbacks.py` |
| 前端 MCP Picker | `views/chat/index.vue` · `selectedMcps`（wizard 收集中 UI 禁用） |

---

## 1. 职责边界

```text
┌─────────────────────────────────────────────────────────┐
│ KeenRobot Agent 层（自研）                               │
│   ChatAgentOrchestrator · RAG · ReAct · SSE · Skill     │
│                          │                               │
│ Host 集成层（自研 · 薄）                                  │
│   ORM→Client · SessionManager · adapters · audit/cancel  │
│                          │                               │
│ FastMCP Client（依赖 fastmcp）                           │
│   协议 · Transport · list_tools / call_tool              │
└──────────────────────────┼──────────────────────────────┘
                           │
              用户配置的外部 MCP Server
```

| 模块 | 负责方 | 职责 |
|------|--------|------|
| MCP 协议与传输 | **FastMCP** | `Client`、`StdioTransport`、`StreamableHttpTransport`、`SSETransport` |
| Host 集成 | **KeenRobot** `applications/mcp/` | 配置读取、Session 生命周期、OpenAI tools 适配、结果格式化 |
| Agent 编排 | **KeenRobot** `chat_agent_orchestrator.py` | 何时 open MCP、ReAct 循环、与 Skill 工具并行 dispatch |
| MCP Server | **用户 / 第三方** | 实际业务能力 |

### 1.1 与相邻模块

| 模块 | 关系 |
|------|------|
| **知识库 RAG** | Orchestrator 内 `_retrieve_context`；与 MCP 独立，可同时绑定 |
| **chat Skill** | 与会话 MCP **可组合**；`execution.mcp_ids` 与会话 `mcp_ids` **并集去重** |
| **wizard / async Skill Run** | 当前 `skill_run_agent_stream` 传 `mcp_server_ids=[]`（Run 不走会话 MCP）；扩展 Run 级 MCP 需改此处 + binding |
| **`McpServer` 表** | 唯一配置源；FastMCP 不读写 DB |

---

## 2. 包结构与调用关系

```
backend/applications/mcp/
├── client_factory.py       # transport 构建、open_client、list/sync/diagnose
├── session_manager.py      # 请求级 Client 池、call_tool、resource 注入
├── orchestrator.py         # re-export ChatAgentOrchestrator（兼容旧 import）
├── policies.py             # McpAgentPolicy = HybridAgentPolicy
├── callbacks.py            # sampling / progress / log（FastMCP handlers）
├── audit.py                # MCP 业务审计落库
├── cancel_scope.py         # SSE 取消 → 中断 call_tool
├── adapters.py             # normalize_tools、build_openai_tool_specs、format_tool_result
└── transports/
    └── streamable_http.py  # URL 尾斜杠等补丁

backend/applications/agent/orchestrator/
├── chat_agent_orchestrator.py   # ★ MCP ReAct 主逻辑
├── binding_resolver.py          # mcp_servers 解析、tools registry
└── tool_dispatcher.py           # McpStep 构建 + call_tool 委托
```

### 2.1 一次聊天请求的 MCP 生命周期

```text
1. resolve_chat_binding
     session_mcp ← 会话 mcp_ids
     embedded_mcp ← chat Skill execution.mcp_ids
     merge_mcp_server_lists（按 server.id 去重）

2. build_mcp_tool_registry → openai_tools + tool_registry

3. async with McpSessionManager():
     open_servers(servers)          # 每 server 一个 Client，本请求只 initialize 一次
     [可选] build_resource_context  # policy.inject_resource_contents
     ReAct 循环:
       llm.chat_with_tools
       ToolDispatcher.execute → session.call_tool
       yield process (McpStep)
     close（AsyncExitStack）

4. bind_mcp_audit_context / bind_mcp_cancel_scope 包裹整段 stream
```

### 2.2 多 Server 策略

每个 `McpServer` 记录 → **独立 FastMCP `Client`**。OpenAI 工具名在 `adapters.build_openai_tool_specs` 中全局唯一化；`tool_registry` 映射回 `(server, original_tool_name)`。

---

## 3. DB 配置 → FastMCP

表：`keenrobot_mcp_servers`

| DB 字段 | FastMCP |
|---------|---------|
| `transport=http` | `StreamableHttpTransport(url, headers=...)` |
| `transport=sse` | `SSETransport`（兼容旧服务） |
| `transport=stdio` | `StdioTransport(command, args, env, cwd)` |
| `config.url` | HTTP/SSE 地址（兼容 `endpoint` / `base_url`） |
| `config.headers` / `config.timeout` | 鉴权、超时 |
| `config.stdio` | stdio 启动参数；**env 须显式传入** |
| `config.tools` | `list_tools()` 缓存（管理页展示、离线预览） |
| `is_enabled` | 加载前跳过 disabled |

**管理 API（常用）：**

| API | 作用 |
|-----|------|
| `POST /mcp-servers/{id}/tools/refresh` | `list_tools` → 写 `config.tools` |
| `POST /mcp-servers/{id}/sync` | tools + resources + prompts + capabilities |
| `POST /mcp-servers/{id}/diagnose` | 连接诊断 |
| `POST /mcp-servers/audit/search` | 审计查询 |

**`config` 示例：**

```json
{
  "url": "https://mcp.example.com/mcp",
  "headers": { "Authorization": "Bearer ***" },
  "timeout": 60,
  "stdio": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/data"],
    "env": {}
  },
  "tools": [],
  "cached_at": "2026-06-26T12:00:00Z"
}
```

---

## 4. 入口与策略

### 4.1 谁调用 MCP？

| 入口 | MCP 来源 | 编排 |
|------|----------|------|
| `POST /chat/stream` | 会话 `mcp_ids` + chat Skill `execution.mcp_ids` | `ChatAgentOrchestrator.stream` |
| Skill Run（wizard/async） | 当前 **未** 传会话 MCP | 同上，`run_mode=True`，`mcp_server_ids=[]` |
| `POST .../tools/refresh` | 单 Server | `client_factory` · `list_tools` |
| 管理页 diagnose/sync | 单 Server | `client_factory` |

### 4.2 Orchestrator 接口（节选）

```python
class ChatAgentOrchestrator:
    async def stream(
        self, *,
        question, user,
        conversation_id=None,
        skill_ids=None,
        mcp_server_ids=None,      # 会话层 MCP
        knowledge_base_ids=None,
        chat_history=None,
        run_mode=False,           # Skill Run 时为 True
        skill_run_id=None,
        policy: HybridAgentPolicy = ...,
    ) -> AsyncIterator[dict]: ...
```

`HybridAgentPolicy`（`agent/policies/hybrid_agent_policy.py`，`McpAgentPolicy` 为其别名）默认值：

| 字段 | 默认 | 含义 |
|------|------|------|
| `max_tool_rounds` | 10 | ReAct 上限 |
| `parallel_tool_calls` | True | 同轮多 tool 并行 |
| `on_max_rounds` | `summarize` | 超轮让 LLM 总结 |
| `inject_resource_contents` | True | sync 过的 text resource 注入 system |
| `sampling_mode` | `llm` | MCP sampling 转发当前会话 LLM |
| `log_mcp_progress` | True | progress/log → LOGGER + McpStep.logs |
| `audit_enabled` | True | call_tool / sampling 写审计表 |
| `allow_skill_write` | False（chat）/ True（Run） | Skill 写文件工具 |

### 4.3 SSE 与取消

| 事件 | MCP 相关 |
|------|----------|
| `process` | `step.type === 'mcp'` → `McpStep`（server、tool、arguments、status、logs） |
| 用户 Abort / 断开 SSE | `asyncio.CancelledError` → `McpCancelScope.request_cancel()` → in-flight `call_tool` 中断，审计 `status=cancelled` |

前端：`chatStream` 使用 `AbortController`；新建对话时会 `abort()` 当前流。

---

## 5. 实施阶段（历史与现状）

| 阶段 | 状态 | 要点 |
|------|------|------|
| Phase 0 Spike | ✅ | FastMCP 对接现网 HTTP MCP |
| Phase 1 替换自研 Client | ✅ | `applications/mcp/`；删除自研 `McpHttpClient` |
| Phase 2 stdio + 编排 | ✅ | sync/diagnose；并行 tool_calls |
| Phase 3 进阶 | ✅ | prompts/resources 注入、sampling、progress、audit、cancel |
| Hybrid 统一 Runtime | ✅ | 单 `ChatAgentOrchestrator`；Skill∩MCP 互斥已移除 |
| Elicitation | ❌ 不做 | 用 Skill Intake 替代 |

---

## 6. 关键约束（维护时不要破）

| 项 | 约定 |
|----|------|
| **Session 生命周期** | 单次 `stream()` / Run 内 `async with McpSessionManager`；禁止每次 `call_tool` 新建 Client |
| **Refresh 前置** | `config.tools` 为空时，`load_mcp_servers` 报错提示先 refresh |
| **去重** | 会话 MCP 与 Skill 内嵌 MCP 按 `server.id` 去重，避免双 initialize |
| **工具注册** | 绑定了 Skill/MCP 即注册 OpenAI tools；**无** on_demand 关键词门控；是否调用由 LLM 决定 |
| **Run 与 MCP** | 当前 Run 路径未接会话 MCP；若产品要 Run+MCP，改 `skill_run_agent_stream` 与 intake 绑定 |
| **多 worker** | `SkillRunEventHub` 为进程内队列；MCP Session 亦 request-scoped，生产需 sticky 或外部总线 |
| **Elicitation** | 不支持；依赖 Elicitation 的 MCP Server 不在支持范围 |

---

## 7. 常见扩展场景

| 需求 | 建议改法 |
|------|----------|
| 新增 transport 类型 | `client_factory.py` 增加分支 + 管理页表单 |
| 调整 ReAct 轮次 / 并行 | `HybridAgentPolicy` 或 Orchestrator 构造 policy |
| Run 任务也要 MCP | `skill_run_agent_stream` 传入 `mcp_server_ids`；`begin_skill_run_reply` / intake 允许绑定 |
| 新 MCP 工具命名冲突 | `adapters.build_openai_tool_specs` 前缀策略 |
| 更严审计 / 脱敏 | `audit.py` · `audit_max_chars`、参数过滤 |
| 聊天 UI 禁止某组合 | 前端 `index.vue` Picker 规则 + 后端 `_resolve_and_validate_bindings` 双保险 |

---

## 8. 测试与验证

| 场景 | 建议 |
|------|------|
| 管理页 | diagnose → sync → refresh；stdio / HTTP 各测一例 |
| 纯 MCP 聊天 | 绑 MCP、问需外部数据的问题；`process_trace` 出现 `mcp` 步骤 |
| KB + MCP | 同时绑 nginx KB + 12306 MCP |
| Skill + MCP | `test_chat_skill` + 会话 MCP；内嵌与会话同 server 时只 initialize 一次（H6） |
| 取消 | 流式过程中 Abort；查审计 `cancelled`（弱验证见 E2E H8） |

测试 Skill 说明：见 `TEST_SKILLS.md`、`HYBRID_AGENT_ORCHESTRATION.md` §8 E2E 矩阵。

---

## 9. 参考

- [FastMCP Client](https://gofastmcp.com/clients/client)
- [FastMCP Transports](https://gofastmcp.com/clients/transports)
- 代码入口：`applications/mcp/session_manager.py`、`applications/agent/orchestrator/chat_agent_orchestrator.py`
