# Skill 集成方案

> 状态：**Phase 0–7 已实施**  
> 更新：2026-06-22（Phase 7 对话内收集流 + draft 清理 API）  
> 关联：`PROJECT_GUIDE.md`、`backend/workspace/.claude/skills/`、`process_step_schema.py`

---

## 1. 目标与定位

在 KeenRobot 现有 LLM 栈中增加 **通用 Skill 智能体层（Generic Skill Agent）**：磁盘 Skill 包（`SKILL.md` + 附属资源）负责 **Agent 怎么干活**；**Skills 表**负责 **平台怎么接入**（模式、Wizard、校验、调度）。**无需为单个 Skill 改框架代码**。

磁盘上现有 Skill 目录 **仅作联调样例**，架构 **Skill 无关（skill-agnostic）**。

**验收标准**：新增 Skill = 磁盘放置目录 → sync → **管理员配置 DB 集成字段** → 用户启用 → 执行；框架零改动。

---

## 2. 行业参照与 KeenRobot 策略

主流企业 Agent 产品采用 **分层组合**，而非 RAG / 工具 / Skill 三选一：

| 层 | 职责 | 行业参照 | KeenRobot |
|----|------|----------|-----------|
| **知识层** | 组织资料 grounding | Microsoft Copilot Knowledge + RAG | ✅ `rag_stream` + 知识库 |
| **连接层** | 外部系统/API | OpenAI Actions；Anthropic **MCP** | ✅ `mcp_agent_stream` |
| **流程层** | 领域 SOP、文件任务 | Anthropic **Agent Skills**；钉钉 DEAP 技能中心 | ✅ Skill Agent + Run（Phase 7 对话内收集待做） |

**KeenRobot 兼容原则**：

1. **不修改** `rag_stream`、`mcp_agent_stream` 内部实现，仅扩展路由。  
2. Skill 与 RAG、MCP **共用** `resolve_chat_llm_params` + `OpenAICompatibleLLM`。  
3. Skill 执行 **可选叠加** `knowledge_base_ids`。  
4. 结构化输入在 **Agent 外** 完成（Wizard + validate），不依赖模型自觉「请先上传」。  
5. **集成配置放 DB、管理页维护**，与 MCP 的 `config` 模式一致；**不使用** 磁盘 `skill.manifest.json`。

---

## 3. 双源职责（磁盘 vs DB）

| 来源 | 内容 | 维护者 | 用途 |
|------|------|--------|------|
| **磁盘** `.claude/skills/{skill_key}/` | `SKILL.md`、`rules/`、`templates/`、`scripts/` | 运维 / git | Agent 执行；Run 快照 |
| **DB** `keenrobot_skills` | `interaction_mode`、`input_schema`、`is_enabled` 等 | **管理员 / 用户**（管理页） | 路由、Wizard、validate、调度 |

```
磁盘 Skill 包（Agent 知识）
        │
        │  sync：仅同步内容元数据（name、description、skill_version）
        ▼
DB keenrobot_skills（平台集成配置）  ← 管理页编辑，sync 不覆盖
        │
        ▼
Wizard / validate / skill_agent_stream / Celery
```

**对齐 MCP**：MCP 的连接信息在 DB `config` 中由用户维护；Skill 的接入规则在 DB 字段中由管理员/用户维护。Skill **不在 Web 上编辑 `SKILL.md` 正文**，只编辑集成配置。

---

## 4. 现状与缺口

### 4.1 已有

| 模块 | 状态 |
|------|------|
| `workspace/.claude/skills/*` | 测试样例目录 |
| `keenrobot_skills` + CRUD + `/api/skills/` | 已实现（缺新字段） |
| 聊天 `skill_ids` 传递与会话持久化 | 已实现 |
| `SkillStep` schema | 已定义，未产出 |
| `rag_stream` / `mcp_agent_stream` | 已运行 |
| MCP 访问隔离（`user_id` + `check_access`） | 已实现 |

### 4.2 缺失（本轮实施）

| # | 缺口 |
|---|------|
| 1 | 磁盘 Skill 扫描、sync、`skill_key` 映射 |
| 2 | DB 迁移：`interaction_mode`、`input_schema`、`skill_key`、`skill_version` 等 |
| 3 | 管理页：集成配置编辑（非手填创建 Skill 包） |
| 4 | `SkillRun` + 工作区 + 输入校验 |
| 5 | **`skill_agent_stream`** + `stream_response` 路由 |
| 6 | schema 驱动 Wizard、执行记录、产物 API |

---

## 5. 总体架构

### 5.1 编排与路由

```
用户入口（聊天 / 管理页）
        │
        ▼
Orchestrator（鉴权、ModelConfig、conversation_id）
        │
   ┌────┼────────────┬─────────────┐
   ▼    ▼            ▼             ▼
 rag  mcp      skill (chat)    skill (wizard/async)
stream agent      │                  │
   │    │          │                  │
   └────┴──────────┴──────────────────┘
                    │
        OpenAICompatibleLLM（ModelConfig / .env）
                    │
        可选并行：knowledge_base_ids（RAG 上下文）
```

| 条件 | 路径 |
|------|------|
| 无 Skill、无 MCP | `rag_stream` |
| 有 MCP、无 Skill | `mcp_agent_stream` |
| 有 Skill、`interaction_mode=chat` | `skill_agent_stream`（`/chat/stream`） |
| 有 Skill、`wizard` / `async_job` | **Skill Run API** |

**首期规则**：聊天 **Skill 单选**；Skill 与 MCP **互斥**。

### 5.2 框架 vs Skill 包

| 框架（一次实现） | Skill 包 / DB 配置 |
|------------------|-------------------|
| Registry、sync、Run、Wizard 渲染 | 磁盘：`SKILL.md` 及附属资源 |
| ReAct + 文件工具 | DB：`input_schema.wizard_steps` 具体内容 |
| SSE / Celery、执行记录 | DB：`interaction_mode`、执行偏好 |

---

## 6. Skills 表（DB 集成配置）

### 6.1 字段（迁移）

在现有 `keenrobot_skills` 上扩展（`config` 保留作扩展，**集成主字段独立列**便于查询与校验）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `skill_key` | string | 对应磁盘目录名；与 `user_id` 联合唯一 |
| `source` | enum | `filesystem`（sync 创建）/ `custom`（预留） |
| `name` | string | sync 自 `SKILL.md` frontmatter，可展示 |
| `description` | text | 同上 |
| `skill_version` | string | sync 时 `SKILL.md`（及目录 hash）版本号 |
| `interaction_mode` | enum | `chat` / `wizard` / `async_job`；**管理页维护** |
| `input_schema` | JSON | Wizard 步骤、layout、校验规则；**管理页维护** |
| `execution` | JSON | 如 `prefer_async`、`estimated_duration`；**管理页维护** |
| `is_enabled` | bool | 用户/管理员；sync **不覆盖** |
| `user_id` | FK | 与 MCP 相同 per-user 记录 |

**运行时**：Wizard、validate、路由 **只读 DB**，不读磁盘 manifest，不做 `skill_key` 硬编码映射。

### 6.2 `interaction_mode` 语义

| 值 | 含义 | 执行 |
|----|------|------|
| `chat` | 无必填结构化输入 | 可直接聊天；`skill_agent_stream` |
| `wizard` | 需 Wizard | validate → start；run 级 SSE |
| `async_job` | 长耗时 | validate → Celery；202 + 记录页轮询 |

### 6.3 `input_schema` 结构（DB JSON 契约）

管理页保存至 `input_schema` 字段：

```json
{
  "wizard_steps": [
    { "type": "file", "key": "doc", "path": "input/doc.md", "label": "文档", "accept": [".md"], "required": true },
    { "type": "text", "key": "ref_id", "label": "业务编号", "required": false },
    { "type": "dir", "key": "coverage", "path": "input/coverage", "label": "覆盖率目录", "required": true },
    { "type": "choice", "key": "policy", "label": "策略", "options": [], "options_source": "spec/*.md", "required": true },
    { "type": "confirm", "key": "summary", "label": "确认摘要" }
  ],
  "layout": {
    "cwd": ".",
    "input_root": "input",
    "output_root": "output"
  }
}
```

| `wizard_steps[].type` | UI |
|-----------------------|-----|
| `file` / `dir` | 上传 |
| `text` | 输入框 |
| `choice` | 单选/多选（替代 Skill 内运行时 question） |
| `confirm` | 摘要确认 |

`execution` 示例（独立 JSON 列或并入 `config`）：

```json
{ "prefer_async": true, "estimated_duration": "long" }
```

### 6.4 管理页维护能力

| 能力 | 说明 |
|------|------|
| sync | 磁盘 → DB，仅更新内容元数据 |
| 预览 | 只读 `SKILL.md`、目录树（对照配置） |
| 编辑集成配置 | `interaction_mode`、`input_schema`、`execution` |
| 启用/禁用 | `is_enabled` |
| 不提供 | Web 编辑 `SKILL.md`；不提供「空建 Skill 包」（首期） |

**启用门禁**：`interaction_mode` 为 `wizard` / `async_job` 时，若 `input_schema.wizard_steps` 未配置或校验不通过，**禁止设为启用**。

**与 SKILL.md 对齐**：管理员配置 Wizard 时对照预览中的 `SKILL.md` 输入要求；二者不一致时由运维修正 DB 或磁盘，框架不做自动解析（后续可选「建议 schema」辅助，非首期）。

---

## 7. Sync 规则

触发：`POST /skills/sync` 或首次进入 Skills 管理页。

| 操作 | 行为 |
|------|------|
| 发现新目录 | Insert：`skill_key`、`name`、`description`、`skill_version`；`is_enabled=false`；`interaction_mode` 默认 `chat` 或 null；`input_schema` 为空 |
| 已存在 | 更新：`name`、`description`、`skill_version`（来自磁盘） |
| **不覆盖** | `is_enabled`、`interaction_mode`、`input_schema`、`execution` |
| 磁盘目录已删 | 删该用户 DB 记录（或软删） |
| 进行中 Run | 不受 sync 影响（使用快照） |

`skill_version` **仅**根据磁盘 `SKILL.md` 及 Skill 包文件计算，与 DB 集成配置无关。

---

## 8. 访问策略（与 MCP 对齐）

| 项 | 策略 |
|----|------|
| DB 记录 | 每用户一条（`list_by_user` + `check_access`） |
| 磁盘 Skill | 平台级；Web 只读预览 |
| 集成配置 | 记录所属用户可编辑（与 MCP 改 `config` 一致）；是否仅管理员可改 `input_schema` 可按角色扩展 |
| Run / 产物 | `runs/{user_id}/` + `check_access(run)` |
| 后续 | zip 解压到 skills 目录（Phase 5，非首期） |

---

## 9. 工作区与 Run 生命周期

```
backend/workspace/
├── .claude/skills/           # Skill 定义（平台，只读）
└── runs/{user_id}/{run_id}/
    ├── input/                # Wizard 上传（路径由 DB input_schema 约定）
    ├── output/               # 产物
    ├── meta.json             # skill_id, skill_version, conversation_id, model_config_id, status
    ├── .skill_snapshot/      # 创建 run 时复制磁盘 Skill 包
    └── session/
```

| 事件 | 行为 |
|------|------|
| 创建 run | 快照磁盘 Skill；绑定 `conversation_id`（从聊天发起时必填） |
| validate | 按 DB `input_schema` 检查 `input/` |
| 进行中 run | 只用快照；磁盘 SKILL 更新不影响 |
| 磁盘删 Skill | sync 删 DB；不中断已快照 run |

---

## 10. 输入门禁

| 层 | 机制 |
|----|------|
| 启用 | `wizard`/`async_job` 且 schema 未配齐 → 不可 `is_enabled=true` |
| 前端 | `mode≠chat` → 禁止直接 `chatStream`；打开 SkillWizard（读 DB schema） |
| API | `POST /skill-runs/{id}/validate` → `missing_fields[]` |
| 启动 | `POST /skill-runs/{id}/start` 再次 validate；失败 400 |

文件类 Skill **不通过** `/chat/stream` 启动。

---

## 11. 执行与连接

| mode | 提交 | 进度 | 聊天 |
|------|------|------|------|
| `chat` | `/chat/stream` | token SSE | 正常气泡 |
| `wizard` | `/skill-runs/{id}/start` | run SSE | `skill_run_ref` |
| `async_job` | `/skill-runs/{id}/start` → 202 | 执行记录轮询 | `skill_run_ref` |

### Skill 智能体（`skill_agent_stream`）

| 项 | 说明 |
|----|------|
| LLM | `OpenAICompatibleLLM` + `resolve_chat_llm_params` |
| Prompt | `.skill_snapshot/SKILL.md` + run `meta.json` |
| cwd | `runs/{user_id}/{run_id}` |
| 工具 | Read / Write / Glob / Bash（限制 run 内） |
| RAG | 可选 `knowledge_base_ids` |

---

## 12. API 清单

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/skills/sync` | 磁盘内容元数据 → DB |
| POST | `/skills/cleanup-stale-drafts` | 清理超过 N 天未 start 的 draft Run（默认 1 天） |
| GET | `/skills/{id}/preview` | SKILL.md + 目录树 |
| PUT | `/skills/{id}` | 更新 `interaction_mode`、`input_schema`、`execution`、`is_enabled` |
| POST | `/skill-runs` | 创建 run |
| POST | `/skill-runs/{id}/files` | 上传 |
| POST | `/skill-runs/{id}/validate` | 按 DB `input_schema` 校验 |
| POST | `/skill-runs/{id}/start` | 启动 |
| GET | `/skill-runs/{id}/stream` | run SSE |
| GET | `/skill-runs/search` | 执行记录 |
| GET | `/skill-runs/{id}` | 详情 |
| GET | `/skill-runs/{id}/outputs` | 产物列表 |
| GET | `/skill-runs/{id}/outputs/{path}` | 下载 |
| POST | `/skill-runs/{id}/cancel` | 取消 |
| POST | `/chat/stream` | RAG / MCP / skill chat |

---

## 13. 前端改造

| 页面 | 改造 |
|------|------|
| Skills 管理 | sync / 预览 / 启用；**编辑集成配置**；**清理无效 draft**（`POST /skills/cleanup-stale-drafts`） |
| 聊天 | Skill 单选；`mode≠chat` → **对话内 Skill Intake**（Phase 7，替换 SkillWizardModal） |
| ~~SkillWizardModal~~ | Phase 7 起 **移除**，由消息流内收集面板替代 |
| 执行记录 | 列表 + 详情 + 产物；**未 start 的 draft 默认不可见** |
| 聊天气泡 | `skill_run_ref.links`；`skill_intake` 收集面板消息 |

---

## 14. 实施阶段

### Phase 0 — Spike

- [x] `skill_agent_stream` 最小链路（SKILL 快照 + Read + DeepSeek）  
- [x] 在 DB 为测试 Skill 手工配 `interaction_mode` + `input_schema` 验证 Wizard 契约  

### Phase 1 — Registry + DB + 管理页

- [x] DB 迁移；`SkillRegistry` + `POST /skills/sync`  
- [x] `PUT /skills/{id}` 集成配置；启用门禁校验  
- [x] `GET /skills/{id}/preview`  
- [x] Skills 管理页：sync / 预览 / **集成配置编辑** / 启用  

### Phase 2 — Run + Workspace

- [x] `SkillRun`、`WorkspaceService`、validate / upload API  

### Phase 3 — Skill Agent + 调度

- [x] `skill_agent_stream`；Celery / run SSE；`stream_response` 路由  

### Phase 4 — 前端闭环

- [x] SkillWizard + 执行记录 + `skill_run_ref`（Wizard 将在 Phase 7 由对话内 Intake 替换）  

### Phase 5 — 加固

- [x] 取消、重试、runs 清理；zip 上传 Skill  
- [x] Skill 内嵌 MCP（`execution.mcp_ids`）  

### Phase 6 — 测试前补齐

- [x] `skill_run_ref` 持久化；执行记录 SSE；Celery Beat 终态清理  

### Phase 7 — 对话内 Skill Intake（待实施）

- [x] 聊天页 wizard/async：**结构化收集面板**（替换 SkillWizardModal）  
- [x] 收集期 **主输入框禁用**；schema 驱动 text/file/choice/confirm  
- [x] **单条可更新** assistant 消息承载面板；完成后折叠只读摘要  
- [x] draft Run：`start` 时再 `.skill_snapshot/`；未 start 不进执行记录  
- [x] 同一对话最多一个收集中 Run；同 Skill 再选 →「继续未完成 / 取消并新建」  
- [x] `start` 后恢复主输入框；**wizard 进度嵌在聊天气泡内（SSE）**  
- [x] Skills 管理页「清理无效记录」（`SKILL_DRAFT_STALE_DAYS` 默认 1 天）  

---

## 15. 已确认决策

| 决策 | 结论 |
|------|------|
| 集成配置存储 | **Skills 表**；管理页维护；**不用** `skill.manifest.json` |
| Agent 内容 | 磁盘 `SKILL.md` 包；Run 快照 |
| sync | 只更新内容元数据 + `skill_version`；**不覆盖**集成字段与 `is_enabled` |
| 新 Skill 默认 | `is_enabled=false`；集成配置需管理员配好后启用 |
| LLM | OpenAI 兼容；共用 ModelConfig |
| RAG / MCP | 保留；Skill 第三分支；首期 Skill⊥MCP |
| 聊天 Skill | 单选 |
| 长任务 | Celery；不占 chat SSE |
| conversation_id | 从聊天发起时必填 |
| 权限 | 与 MCP per-user 隔离 |
| Phase 7 收集 UI | **对话框内结构化面板**；不用 LLM 代替表单；**替换** SkillWizardModal |
| Phase 7 收集期聊天 | **禁止闲聊**；主输入框全程禁用 |
| Phase 7 draft | 未 start **不进执行记录**；找草稿 = 回到对应对话；**无用户侧空闲超时** |
| Phase 7 快照 | **start 时**复制 `.skill_snapshot/`；收集期仅 `input/` + schema |
| Phase 7 同 Skill 再选 | 提示「继续未完成 / 取消并新建」 |
| Phase 7 start 后 | **立即恢复**主输入框；wizard/async 执行进度仍可通过 SSE / 执行记录查看 |
| draft 管理员清理 | Skills 管理页「清理无效记录」；默认 **1 天**未 start（`SKILL_DRAFT_STALE_DAYS`） |

---

## 17. Phase 7 — 对话内 Skill Intake（详细设计）

### 17.1 目标

wizard / async_job 的前置数据收集 **在聊天消息流内** 完成：schema 驱动、可校验、可恢复；**不**用 LLM 多轮问答代替表单；**替换**现有 `SkillWizardModal`。

### 17.2 会话状态机

```
idle → collecting → confirming → running → idle
         ↑ cancel ──┘              ↑ 终态 / skill_run_ref
```

| 状态 | 主输入框 | API |
|------|----------|-----|
| idle | 可用 | `/chat/stream` 等 |
| collecting / confirming | **禁用** | `skill-runs` create/files/inputs/validate |
| running（已 start） | **恢复可用** | run SSE / Celery + 执行记录 |

### 17.3 收集面板：「单条可更新消息」

**含义（用户侧）**：

- 选中 wizard/async Skill 后，消息区出现 **一条** 系统/助手消息，内含 **Skill 收集面板**（步骤条 + 当前步表单）。
- 用户点「下一步 / 上传 / 选选项」时，**同一条消息的内容原地更新**（步骤 1→2→3），**不会**每步新增一条聊天消息刷屏。
- 全部填完 → 同一条消息变为 **摘要确认** 区；确认并 start 后 → 该消息 **折叠为只读摘要**（仍留在历史中，可回看填了什么）。
- 对比「每步一条消息」：历史里会有 4～5 条重复感很强的系统消息；单条更新更整洁，面板像「钉在对话里的一块表单」。

**持久化**：

- 消息 payload 含 `skill_intake`（`run_id`、`skill_id`、`step_index`、`phase` 等）。
- **Run 为事实来源**：`input_data`、已上传文件、validate 结果；刷新/重进对话 **100% 恢复**到上次步骤。

### 17.4 与 Run / 工作区

| 时机 | 工作区内容 |
|------|------------|
| 选 Skill → create draft | `input/` + `meta.json`（**不**复制 snapshot） |
| 用户取消 | `cancelled` + 删 workspace；执行记录不可见 |
| 用户 confirm → start | **此时** `copy_skill_snapshot`；进入执行态 |
| Skill 收集期间磁盘更新 | **以 start 时刻** Skill 版本为准 |

### 17.5 约束

- 同一对话 **同时最多一个** 收集中 Run；再选其他 Skill → 提示先取消或换对话。
- 同一对话 **再次选同一 Skill** →「继续未完成 / 取消并新建」。
- wizard / async_job **共用**收集 UI；start 后 wizard 走 SSE，async_job 走 Celery + 执行记录。
- 未 start 的 draft：**不进**执行记录默认列表。

### 17.6 draft 清理（管理员）

- 配置：`SKILL_DRAFT_STALE_DAYS`（默认 **1**）。
- API：`POST /skills/cleanup-stale-drafts`（`dry_run` 可预览）。
- UI：Skills 管理页「同步磁盘 Skill」右侧 **「清理无效记录」**。
- 对象：`pending` / `validated` 且 `created_time` 超过 N 天、从未 start 的 Run。
- **不**做用户侧自动超时；用户搁置草稿由会话保留，仅管理员主动清理。

### 17.7 待实现代码接点

| 路径 | 改动 |
|------|------|
| `frontend/src/views/chat/index.vue` | Intake 状态机；禁用 composer；移除 Modal 入口 |
| `frontend/src/components/MessageBubble.vue` | 渲染 `skill_intake` 面板 |
| `frontend/src/components/skill/SkillIntakePanel.vue` | 新建：schema 步骤 UI |
| `backend/.../workspace_service.py` | `init_workspace` 拆分：draft 不 snapshot；start 时 snapshot |
| `backend/.../conversation` | 消息类型 `skill_intake`；持久化 payload |
| `backend/.../skill_run_crud.py` | `list_draft_by_conversation`；start 时快照 |

---

## 16. 代码接点（Phase 0–6）

| 路径 | 改动 |
|------|------|
| `backend/applications/agent/models/agent_model.py` | 新字段 |
| `backend/applications/agent/views/agent_view.py` | sync、preview、PUT 集成配置 |
| `backend/applications/agent/schemas/agent_schema.py` | SkillUpdate 含 integration 字段 |
| `backend/applications/conversation/services/conversation_crud.py` | Skill 路由 |
| `backend/applications/base/rag/` 或 `agent/` | `skill_agent.py` |
| `frontend/src/views/ai-manage/skills/index.vue` | 集成配置编辑 UI |
| `frontend/src/views/chat/index.vue` | 单选 + Wizard |
| `frontend/src/api/index.js` | sync / skill-runs API |

---

*实施顺序：Phase 0–6 已完成；下一步 Phase 7（对话内 Intake）。对齐基准：**DB `input_schema` + Run 模型 + 消息 `skill_intake` payload**。*
