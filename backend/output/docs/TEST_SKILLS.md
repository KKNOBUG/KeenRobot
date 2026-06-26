# KeenRobot 测试 Skill 使用说明

磁盘目录：`backend/workspace/.claude/skills/`

| skill_key | 模式 | 用途 |
|-----------|------|------|
| `test_chat_skill` | chat | 普通对话 + Skill 工具（绑即注册，LLM 按需调用） |
| `test_wizard_skill` | wizard | 向导 → SSE → `report.md` + `metrics.json` |
| `test_async_job_skill` | async_job | 向导 → Celery → 三文件产物 |

## 1. 同步磁盘

Skills 管理页点击 **「同步磁盘 Skill」**，应出现上述 3 个 Skill（默认 **未启用**）。

## 2. 编辑集成配置（DB 管理页）

集成配置（`interaction_mode`、`input_schema`、`execution`、`is_enabled`）**仅保存在数据库**。

---

### test_chat_skill

**交互模式**: `chat`

**input_schema**:

```json
{
  "wizard_steps": [],
  "layout": {
    "cwd": ".",
    "input_root": "input",
    "output_root": "output"
  }
}
```

**说明**：chat 模式绑定 Skill 后，`skill_read` / `skill_glob` 始终注册给 LLM；是否调用由模型按问题判断（已移除 `chat_tools` / `on_demand`）。

**execution**:

```json
{
  "prefer_async": false,
  "estimated_duration": "short"
}
```

**实验场景**（详见磁盘 `scenarios.md`）：

| 场景 | 输入 | 期望 |
|------|------|------|
| A 普通对话 | 逻辑/应用题 | **无** tool 步骤，正常推理 |
| B ping | `ping` | 应触发 skill_read，含 `TEST_CHAT_OK` |
| C 读清单 | `读取 checklist` | skill_read + 概括清单 |
| D glob | `glob 扫描` | skill_glob 列出快照文件 |
| E help | `help` | 说明双模式，可不读文件 |

---

### test_wizard_skill

**交互模式**: `wizard`

**input_schema**: （与原先一致，四步向导）

**execution**:

```json
{
  "prefer_async": false,
  "estimated_duration": "medium"
}
```

**样例**：上传 `examples/sample-source.txt` 或 `minimal-source.txt`，项目名 `DemoProject`，风格 `简洁` 或 `详细`。

**预期产物**：
- `output/report.md`（含 HTML 注释元数据块）
- `output/metrics.json`（行数/字符数/quality_checks）
- 摘要含 `TEST_WIZARD_OK`

---

### test_async_job_skill

**交互模式**: `async_job`

**input_schema**: （三步向导：JSON 文件 + job_label + confirm）

**execution**:

```json
{
  "prefer_async": true,
  "estimated_duration": "long"
}
```

**样例**：
- `examples/sample-data.json` + 标签 `batch-full-001`
- `examples/sample-array.json` + 标签 `batch-array-001`（验证数组解析）

**预期产物**：
- `output/summary.json`
- `output/metrics.json`
- `output/status.txt`（含 `TEST_ASYNC_OK`）

**Celery**（项目根目录 `KeenRobot/`）：

```bash
celery -A backend.celery_scheduler.celery_worker worker -Q default --pool=solo -l INFO
```

---

## 3. 快速断言

| Skill | 断言 |
|-------|------|
| chat 普通题 | process **无** skill_read |
| chat ping | 含 `TEST_CHAT_OK` |
| wizard | 存在 `report.md` + `metrics.json`，摘要含 `TEST_WIZARD_OK` |
| async_job | `status.txt` 含 `TEST_ASYNC_OK`，且有三文件 |

## 4. 磁盘包结构（实验资源）

```
test_chat_skill/
  SKILL.md, checklist.md, scenarios.md, rules/demo.md
test_wizard_skill/
  SKILL.md, templates/report.md, examples/*.txt
test_async_job_skill/
  SKILL.md, templates/output-schema.md, examples/*.json
```
