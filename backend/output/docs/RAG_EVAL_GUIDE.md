# RAG 离线评测指南

> 检索召回与引用率审计脚本位于 `backend/services/recall_test/`（运维/开发 CLI，**不参与** FastAPI 业务运行时）。  
> 评测集模板 50 条：`backend/output/eval/questions.template.jsonl`。

---

## 1. 目录与文件

### 1.1 数据文件

| 路径 | 说明 |
|------|------|
| `backend/output/eval/questions.template.jsonl` | **模板**（50 条样例，可提交 git） |
| `backend/output/eval/questions.jsonl` | **召回跑批用**（从 template 复制后微调） |
| `backend/output/eval/results/recall_<timestamp>.json` | 召回评测结果 |
| `backend/output/eval/results/citation_<timestamp>.json` | 引用率审计结果 |

### 1.2 评测代码（`backend/services/recall_test/`）

| 文件 | 职责 |
|------|------|
| `run_recall_test.py` | **召回 CLI** |
| `run_citation_audit.py` | **引用率 CLI**（P2-3） |
| `runner.py` | 召回编排 → `retriever.retrieve()`（含 KB 名解析） |
| `citation_audit.py` | 扫描 DB 助手消息 → `answer_consistency` |
| `dataset.py` | JSONL 加载、多轮 history |
| `db.py` | CLI 数据库会话 |
| `metrics.py` | 召回指标聚合 |
| `paths.py` | 默认路径 |

### 1.3 被测业务代码

| 能力 | 落点 |
|------|------|
| 统一检索 | `retriever.retrieve()` |
| 多 query 融合 | `query_enhancer.build_fusion_queries` + `retriever.vector_fetch_fusion` |
| Query 增强 / 空召回重试 | `query_enhancer.py` |
| 场景预设 | `retrieval_presets.py` |
| 一致性检查 | `answer_consistency.py`（线上日志 + 审计脚本） |

---

## 2. 评测集字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `question` | 是 | 用户问题 |
| `kb_names` | 是 | 与 `knowledge_name` 一致 |
| `expected_keywords` | 否 | Hit@k：snippet 含任一关键词 |
| `expect_empty` | 否 | 期望空召回 |
| `expect_multi_kb` | 否 | 多库 sources 覆盖每个 kb_id |
| `followup` / `prior_user` | 否 | 多轮样例 |
| `tags` | 否 | 分组 / `--tag` 过滤 |

---

## 3. 指标口径

### 3.1 召回（`run_recall_test`）

| 指标 | 计算 |
|------|------|
| **recall_rate** | 应命中样本中 `retrieval_empty=false` 比例 |
| **Hit@k** | 非空且有关键词样本中 snippet 命中比例 |
| **empty_accuracy** | `expect_empty=true` 中实际 empty 比例 |
| **multi_kb_coverage_rate** | 多库样本中 sources 覆盖全部 kb 比例 |
| **latency p50/p95** | 单条 `retrieve()` 耗时 |

### 3.2 引用（`run_citation_audit`）

| 指标 | 计算 |
|------|------|
| **citation_rate** | 有 sources 的助手消息中，回答含**文件名或页码**的比例 |
| **citation_file_and_page_rate** | 同时含文件名**与**页码 |
| **orphan_digits_rate** | 回答出现 snippet 外数字的比例 |

---

## 4. 环境准备

1. `backend/.env`：DB、Embedding、可选 Rerank 已配置。  
2. 知识库已入库且 Chroma 向量可用。  
3. 复制评测集：

```bash
cp backend/output/eval/questions.template.jsonl backend/output/eval/questions.jsonl
```

可选 `.env`（Round 4）：

```env
RETRIEVAL_MULTI_QUERY_FUSION_ENABLED=false   # 对比实验时再开
RETRIEVAL_MULTI_QUERY_MAX=3
```

---

## 5. 执行命令

在 **项目根目录** `KeenRobot/` 下（以下用 `PY=backend/.venv/bin/python`，或本机 Python + 已装依赖）：

### 5.1 召回全量基线

```bash
PYTHONPATH=. $PY -m backend.services.recall_test.run_recall_test
```

### 5.2 召回子集 / 场景

```bash
PYTHONPATH=. $PY -m backend.services.recall_test.run_recall_test --tag 多轮
PYTHONPATH=. $PY -m backend.services.recall_test.run_recall_test --tag 多库
PYTHONPATH=. $PY -m backend.services.recall_test.run_recall_test --scenario recall
```

### 5.3 多 query 融合对比（P2-2）

```bash
# .env 设 RETRIEVAL_MULTI_QUERY_FUSION_ENABLED=true 后重跑
PYTHONPATH=. $PY -m backend.services.recall_test.run_recall_test --output backend/output/eval/results/recall_fusion_on.json
```

### 5.4 引用率审计（P2-3）

需已有带 `sources_json` 的聊天落库记录：

```bash
PYTHONPATH=. $PY -m backend.services.recall_test.run_citation_audit
PYTHONPATH=. $PY -m backend.services.recall_test.run_citation_audit --limit 500 --days 30
```

### 5.5 指定路径

```bash
PYTHONPATH=. $PY -m backend.services.recall_test.run_recall_test \
  --questions backend/output/eval/questions.jsonl \
  --output backend/output/eval/results/recall_baseline.json
```

---

## 6. 推荐验收批次

1. **P0 召回基线**：全量 50 条 → `recall_*.json`  
2. **P0 多库 / 多轮 / 空召回**：`--tag` 子集  
3. **P1 场景**：`--scenario balanced|precision|recall`  
4. **P2 融合**：开关 `RETRIEVAL_MULTI_QUERY_FUSION_ENABLED` 前后对比 Hit@k / latency  
5. **P2 引用**：线上聊若干有源问题 → `run_citation_audit` 看 `citation_rate`

---

## 7. 运维确认

- [x] 评测集模板 50 条  
- [x] 召回 + 引用审计 CLI  
- [ ] `questions.jsonl` 按线上库名微调  
- [ ] 定期跑批归档至 `output/eval/results/`
