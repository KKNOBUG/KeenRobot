# RAG 检索质量与记忆能力方案

> 状态：**已确认 — 企业标准方案（阶段 1 + 阶段 2 + 方案 A 均已落地）**  
> 更新：2026-06-22（已移除离线评测脚本与 `backend/eval/`；参数标定保留 `RETRIEVAL_SCORE_THRESHOLD=0.45` + 迁移 `32_*`）  
> 关联：`CHAT_KB_SELECTION.md`（知识库范围）、`CHAT_EXECUTION_FLOWS.md`（聊天编排）、`PROJECT_GUIDE.md` §7.2（路线图摘要）

### 落地进度一览

| 模块 | 状态 | 说明 |
|------|------|------|
| F Rerank + 统一检索 | ✅ | `retriever.retrieve()` + `reranker.apply_rerank()` |
| G 溯源 SSE + 落库 + 前端 | ✅ | `sources` / `retrieval_empty`；`MessageBubble.vue` |
| M0 短程记忆 | ✅ | `trim_chat_history` + `build_query` |
| I 离线评测 | — | 开发期脚本已移出代码库（非业务运行时）；回归见 §11 手工验收 |
| H 向量重建 | ✅ | `POST /knowledge-bases/{id}/reindex` + 管理端「重建向量」 |
| B 结构分块 | ✅ | `structure_chunker`；**仅新上传**文档生效 |
| C 父块扩展 | ✅ | `structure_parent_index_pages` + `expand_context()`；**须重新上传**才建 parent/child |
| A 参数标定 | ✅ | 默认 `score_threshold=0.45`；迁移 `32_*calibrate_score_threshold` |
| M1 滚动摘要 | ✅ | `chat_context_service` + `Conversation.summary`；SSE 后异步合并 |
| M2 显式记忆 | ✅ | `user_memories`；「记住…」写入；`/chat/memories` + 个人中心 |

---

## 一、已确认方案范围

### 1.1 RAG 企业标准

**A（调参，贯穿始终）+ B（结构分块）+ C（父块扩展）+ F（Rerank）+ G（溯源）+ H（重建）**（原方案 I 离线评测脚本已移出代码库）

目标链路：

```
用户问题 (+ M0 最近 1～2 轮上下文)
  │
  ▼
向量召回 fetch_top_k=25～30（Chroma + Embedding）     ← 扩召回
  │
  ▼
Rerank → top_k=5～8（仅当 RERANK_API_KEY 已配置）      ← F，可选
  │  未配置 RERANK → 取向量候选前 top_k（降级，不阻断部署）
  ▼
父块 expand → 拼 Prompt                                  ← C ✅
  │
  ▼
SSE sources / retrieval_empty → LLM                      ← G ✅
  │
  ▼
（M1）滚动摘要注入 system ## 对话摘要                      ← M1 ✅
```

**当前实际链路（2026-06-30）**：M0 → `retrieve()`（F 可选）→ `expand_context()`（C）→ G → **M1 摘要段** → LLM。

**不在本方案范围**：原 **方案 E（Meilisearch / BM25 混合检索）**、查询改写/多查询（HyDE）、Graph RAG、ColBERT、Agentic 多轮检索循环、**Embedding 语义切块（Semantic Chunking / B6）**、LLM 分块。

> **剔除 E 的补偿**：结构分块 B（条款号/标题写入 chunk 正文）、提高 `fetch_top_k`、F Rerank、C 父块扩展；精确编号类问法依赖线上抽检，必要时再单独立项 E。

### 1.2 记忆企业标准

**M0 + M1 + M2（仅显式写入）**

| 层级 | 方案 | 说明 |
|------|------|------|
| L1 | M0 | token 预算截断 + 检索 query 带最近上下文 | ✅ 已落地 |
| L2 | M1 | **滚动摘要**：窗口外历史合并进 `Conversation.summary` | ✅ 已落地 |
| L3 | M2 | 用户说「记住…」才写入；可查看、可删除 | ✅ 已落地 |

**不在本方案范围**：M3 语义 episodic 记忆（全量 Q&A 向量化）；M2 自动抽取用户画像。

### 1.3 RAG 与记忆分工

| 维度 | RAG | 记忆 |
|------|-----|------|
| 数据来源 | 企业知识库文档（PDF 等） | 用户对话、显式偏好、会话摘要 |
| 存储 | Chroma + `DocumentChunk` | MySQL `Message` / `Conversation.summary` / `user_memories` |
| 检索方式 | 向量召回 + Rerank（可选） | 最近 N 轮 + 摘要 + 用户 fact 查表 |
| 注入位置 | system prompt `{context}` | system：**滚动摘要** + 用户 fact；messages：**最近 R 轮原文** |
| 与 Skill | 并行绑定，Orchestrator 合并 | 不与 KB 混库；Run 结果走 `skill_run_ref` |

---

## 二、当前基线（已实现）

### 2.0 已落地能力摘要（截至 2026-06-30）

| 能力 | 状态 | 落点 |
|------|------|------|
| 统一检索链 | ✅ | `retriever.retrieve()`：扩召回 → 阈值 → Rerank 降级 → context |
| Rerank（F） | ✅ | `reranker.apply_rerank()`；DashScope `/reranks`；无 Key 或失败降级 |
| 溯源 SSE（G） | ✅ | `sources` / `retrieval_empty`；`format_sources_payload` |
| 溯源持久化 | ✅ | `Message.sources_json`、`retrieval_empty`；刷新对话可恢复 |
| 空召回 Prompt | ✅ | `CHAT_SYSTEM_PROMPT_KB_EMPTY_RETRIEVAL`（§4.5.1，`rag_config.py`） |
| 默认 `top_k` | ✅ | ModelConfig 默认 **6**；migration 28 将历史 `top_k=20` 行修正为 6 |
| M0 短程原文 | ✅ | `trim_chat_history` 轮数+token 双限；`build_query` 检索带最近 2 轮 |
| 向量重建（H） | ✅ | `POST /knowledge-bases/{id}/reindex`；`_reembed_document` 分批 re-embed |
| 结构分块（B） | ✅ | `structure_chunker.structure_chunk_pages`；B1～B5；接入 `_process_document` |
| 父块扩展（C） | ✅ | `expand_context()` + parent/child 双写；须重新上传生效 |
| M1 滚动摘要 | ✅ | `chat_context_service`；`Conversation.summary`；`chat_view` SSE 后异步触发 |

**仍待后续**：无（企业标准记忆 M0+M1+M2 已齐）；**A 参数标定**可按 `.env` / ModelConfig 与 §11 抽检微调。

**运维提示**：

- **换 Embedding 模型**：管理端「重建向量」或 `POST .../reindex`（按已有分块 re-embed，约 1～20 min/库，视块数而定）。
- **应用 B 结构分块到旧文档**：须 **重新上传 PDF**（reindex 不会重新分块）。

### 2.1 RAG

```
用户问题 (+ build_query 最近 2 轮，M0.2)
  │
  ▼
trim_chat_history(R, max_history_tokens)                  ← M0.1
  │
  ▼
retriever.retrieve()
  ├─ is_embedding_configured() 未配置 → 跳过检索
  ├─ vector_fetch：get_single_embedding → chroma_store.search(fetch_top_k)
  ├─ _filter_embedding_model_consistency()
  ├─ score_threshold 过滤（ModelConfig）
  ├─ apply_rerank() → top_k（F；RERANK_API_KEY 未配则向量序降级）
  └─ format_context_from_results()
  │
  ▼
ChatAgentOrchestrator._stream_impl()
  ├─ extra_system ← chat_context_service.build_memory_system_section（M1+M2）
  ├─ yield sources / retrieval_empty（G）
  ├─ resolve_chat_system_prompt（空召回 → CHAT_SYSTEM_PROMPT_KB_EMPTY_RETRIEVAL）
  ├─ build_hybrid_system_prompt(rag + Skill/MCP)
  ├─ format_messages(chat_history, max_history_rounds)
  └─ llm.stream_chat() / chat_with_tools()
  │
  ▼
chat_view → Message.sources_json / retrieval_empty 落库
  └─ asyncio.create_task(run_conversation_summary)   ← M1 异步摘要
```

**入库（B）**：`structure_chunker.structure_chunk_pages()` → `DocumentChunk` → Chroma；默认全局 `CHUNK_SIZE=500`（知识库可覆盖）；B3 overlap 取 `max(kb配置, min(200, chunk_size×0.25))`。

**缺口（相对企业标准）**：无（RAG B/C/F/G/H + 记忆 M0/M1/M2 均已落地）。

### 2.2 记忆

**已有**：`Message` 持久化 + `max_history_rounds` + **`max_history_tokens` 双限截断**（M0.1）；RAG 检索 query 带最近 2 轮（M0.2 / `build_query`）；**M1 滚动摘要**（`Conversation.summary` + `chat_context_service`）。

**缺口**：无（M2 API + 个人中心 UI 已提供删除）。

### 2.3 相对企业标准的提升（当前 vs 目标）

| 维度 | 改造前 | 当前（已落地） | 企业标准后（未全完成） |
|------|--------|----------------|------------------------|
| 精确词/编号召回 | 弱（纯向量） | B 标题/节级入正文 + fetch_top_k + F | + C 父块完整度 |
| 排序质量 | Chroma 距离序 | F Rerank（可选）或向量序降级 | 同左 |
| 答案完整度 | 500 字硬切 | B 节级/段落 + B3 overlap | + C parent expand |
| 可信度 | 来源仅在 Prompt | G SSE + 前端引用 + 落库 | 同左 |
| 运维 | 换 embedding silent 失效 | H 重建 API + 管理端按钮 | 可选 Celery 异步 |
| 迭代 | 凭感觉调参 | A 已标定 `score_threshold=0.45` | 线上抽检 |
| 多轮追问 | 检索不看历史 | M0 query 上下文化 | 同左 |
| 长会话 | 超轮数失忆 | M0 双限截断 | + M1 滚动摘要 ✅ |
| 跨会话 | 每次从零 | 仍从零 | + M2 显式记忆 ✅ |

---

## 三、质量短板与改造状态

> 本节对照 **改造前** 与 **当前**；✅ 已解决，🔄 部分解决，❌ 待做。

### 3.1 RAG

| 环节 | 改造前 | 当前 | 方案 |
|------|--------|------|------|
| 分块 | 固定 500 字窗口 | ✅ B 结构/节级（新上传） | B + C |
| 索引 | 仅 dense vector | ✅ 同左 | 保持单向量 |
| 检索 | top_k 直进 Prompt | ✅ fetch_top_k + F Rerank | F |
| 上下文 | 命中 chunk 即全文 | ✅ C 父块 expand | C 父块 |
| 溯源 | 无 API 回传 | ✅ G SSE + 落库 + 前端 | G |
| 空召回 | GENERAL 易 silent 泛答 | ✅ retrieval_empty + 专用 Prompt | G |
| 模型切换 | 无重建 | ✅ H reindex API | H |
| 评估 | 无评测集 | A 已标定；离线脚本已移除 | 线上抽检 |
| 参数 | 默认值未标定 | ✅ A：`score_threshold=0.45` | 按需调 `.env` / ModelConfig |

### 3.2 记忆

| 环节 | 改造前 | 当前 | 方案 |
|------|--------|------|------|
| 截断 | 仅按轮数 | ✅ M0 轮数 + token 双限 | M0 |
| RAG query | 不含历史 | ✅ build_query 最近 2 轮 | M0.2 |
| 长会话 | 无摘要 | ✅ M1 滚动摘要 | M1 |
| 跨会话 | 无用户记忆 | ✅ M2 显式写入 | M2 |
| 合规 | 无删除能力 | ✅ 软删 API + 个人中心 | M2 |

---

## 四、方案详述

### 4.1 方案 A：调参基线 ✅ 已标定（2026-06-30）

**当前定稿默认值**（迁移 `32_*calibrate_score_threshold` + `.env` `RETRIEVAL_SCORE_THRESHOLD`）：

| 项 | 定稿默认 | 说明 |
|----|----------|------|
| `score_threshold` | **0.45** | `.env` `RETRIEVAL_SCORE_THRESHOLD`；ModelConfig=0 时回退；修复空召回误命中 |
| `fetch_top_k` | **30** | `.env` `RETRIEVAL_FETCH_TOP_K` |
| `top_k` | **6** | ModelConfig 默认 |
| `chunk_size` | 900～1200（制度类） | 知识库级配置；全局默认 500 |
| child chunk（C） | **350** | `INDEX_CHUNK_SIZE` |
| parent Prompt（C） | **1500** | `PARENT_CONTEXT_MAX_CHARS` |
| `max_history_rounds` | **8** | 有 M1 时 6～10 |

**标定依据**：开发期手工抽检 + 空召回样例验证；`score_threshold=0.45` 将空召回误命中率从 0.5 降至 0。

**验收**：空召回误命中已通过阈值标定修复；后续调整见 §11 手工检查清单。

---

### 4.2 方案 B：结构分块 ✅ 已落地（2026-06-30）

> **说明**：方案 B 为 **结构/段落/节级边界分块**（规则切分）。**不包含** Embedding 语义切块、LLM 分块。

**落点**：`backend/applications/knowledge_base/services/structure_chunker.py` → `knowledge_base_crud._process_document()`。

| 策略 | 做法 | 落地说明 |
|------|------|----------|
| B1 结构感知 | 「第 X 章/条」等 **行级**标题切段 | 标题拼入 **每块**正文；正文行长句「第 N 条…」不误切（行级 + 长度约束） |
| B2 段落优先 | 无结构标题时按 `\n\n` 成节 | 节长 ≤ chunk_size 不二次切 |
| B3 重叠加大 | `overlap = min(200, chunk_size × 0.25)` | 与 kb 配置取 max，且 ≤ chunk_size/2 |
| B4 表格 | Markdown `\|...\|` 整表成块 | 前缀 `【表格】`；≤8000 字不切 |
| B5 节级上限 | 单节 ≤ chunk_size 整节一块 | 超长节句边界二次切，**每子块仍带节标题** |

**验收**：B 重新上传后按 §11 抽检结构分块与召回效果。

#### 跨块漏召的对策（本方案内）

```
问题：完整答案 = 块 A（条件） + 块 B（结论），检索可能只命中其一

对策（按优先级，均在本方案范围内）：
  1. B1+B5：同一「条/节」尽量一块入库
  2. C：索引用 child、Prompt 用 parent（同节 800～1500 字）
  3. B3：overlap 使边界内容重复
  4. F：Rerank 提高相关块排名；A 提高 fetch_top_k 扩大向量候选
  5. B1：入库时将章节/条款标题拼入 chunk 正文，辅助编号类向量召回
```

无清晰章节结构的文档：仍走 B2 段落优先 + B3 + C；若效果不足，通过 **A 调参** 或 **加大 parent 窗口** 优化，**不引入语义切块**。

**生效范围**：

- **新上传** PDF：立即走 `structure_chunk_pages`。
- **已有文档**：向量仍在 Chroma 中为旧分块；须 **重新上传** 才应用 B（「重建向量」仅 re-embed，**不会**重新分块）。

---

### 4.3 方案 C：父块 + 子块 ✅ 已落地

```
索引：child chunk (INDEX_CHUNK_SIZE≈350 字) → Chroma
存储：parent (is_index=False) + child (is_index=True) → MySQL DocumentChunk
      parent_chunk_id / section_id 关联同节
检索：命中 child → expand_context() → parent 进 Prompt（PARENT_CONTEXT_MAX_CHARS 上限）
溯源：SSE sources 仍展示 child snippet（G）
```

**改动**：迁移 `27_*parent_index_chunks`（`parent_chunk_id` / `section_id` / `is_index`）；`structure_parent_index_pages()`；`_process_document` 双行写入；`retriever.expand_context()`；`chat_agent_orchestrator` 在 `retrieve()` 后扩展上下文。

- **已有文档**：旧分块无 parent；`expand_context` 降级为 child 原文。**须重新上传**才应用 B+C（「重建向量」仅 re-embed 索引 child，**不会**重建 parent/child 结构）。

---

### 4.4 方案 F：Rerank（可选增强）✅ 已落地

```
candidates = chroma_store.search(k=fetch_top_k)   # 单向量扩召回

if is_rerank_configured() and model_config.rerank_enabled:
    final = rerank_api(question, candidates)[:top_k]
else:
    final = candidates[:top_k]   # 向量距离序，降级模式
```

**启用条件**（须同时满足）：

1. `.env` 中 **`RERANK_API_KEY` 非空**（**唯一硬开关**；未配置则 **视为未启用 Rerank**）
2. `ModelConfig.rerank_enabled == true`（仅在有 Key 时生效；无 Key 时忽略）

**模型**：与 Embedding **独立配置**，可不同平台。示例：百炼 `qwen3-rerank`、硅基 `BAAI/bge-reranker-v2-m3` 等。

**三套独立 `.env` 参数**（互不共用 Key、**禁止**用 `EMBEDDING_API_KEY` 回退 Rerank）：

| 用途 | 变量 | 说明 |
|------|------|------|
| 对话 / M1 摘要 | `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL_NAME` | 已有 |
| 向量入库与检索 | `EMBEDDING_API_KEY` / `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL_NAME` | 已有 |
| Rerank 精排 | `RERANK_API_KEY` / `RERANK_BASE_URL` / `RERANK_MODEL` | **可选**；缺 Key 即降级 |

**降级行为**（新人部署 / 无 Rerank 额度）：

- 启动日志：`[rag] RERANK_API_KEY 未配置，跳过 Rerank，使用向量检索顺序`
- 检索仍可用；建议 **`fetch_top_k` 略减小或依赖 B/C** 补偿排序质量
- 不阻塞上传文档与聊天

**改动**：`reranker.py` 实现 `is_rerank_configured()`、`apply_rerank()`（OpenAI 兼容 `/reranks` + DashScope 原生）；`retriever.retrieve()` 内调用；`ModelConfig.rerank_enabled` / `rerank_model` 为 secondary 开关。

**验证（2026-06-29）**：`.env` 配置 `RERANK_API_KEY`（DashScope，与 Embedding 同 Key 不同变量）后，日志不再出现降级提示；SSE `sources` 条数 ≤ `ModelConfig.top_k`（默认 6）。

---

### 4.5 方案 G：溯源（SSE + 前端）✅ 已落地

流式开始前 yield：

```json
{
  "type": "sources",
  "items": [
    {
      "index": 1,
      "score": 0.82,
      "filename": "员工手册.pdf",
      "page_number": 12,
      "chunk_id": "...",
      "snippet": "年假天数按工龄..."
    }
  ]
}
```

空召回时：`{"type": "retrieval_empty", "message": "未在知识库中找到相关内容"}`。

**改动**：

- `ChatAgentOrchestrator._stream_impl` yield sources / retrieval_empty
- `Message.sources_json`、`Message.retrieval_empty` 持久化（`chat_view` → `add_message`）
- 前端 `MessageBubble.vue`「参考来源」折叠区 + 空召回横幅；`mapMessageFromServer` 恢复历史

#### 4.5.1 空召回 LLM 行为（产品定稿）

**原则**：未命中知识库须 **显式告知**；可基于 **相关常识** 做 **谨慎补充**，但不得伪装成官方制度或编造具体条款/数字。

| 层 | 行为 |
|----|------|
| **SSE / 前端** | 流式开始前 yield `retrieval_empty`；UI 展示「未在知识库中找到相关内容」 |
| **System Prompt** | `has_context=False` 时使用 **`EMPTY_RETRIEVAL_SYSTEM_PROMPT`**（替代现有 `GENERAL_SYSTEM_PROMPT`） |
| **LLM 回答** | ① 开头说明未命中知识库；② 若问题仍属可答范围，可给通用/常识性参考；③ 明确标注「非官方资料」；④ 建议查阅公司正式文件；⑤ **禁止** 编造具体制度条款、流程步骤、福利数字 |

**触发条件**（满足任一即视为空召回）：

- 向量检索 0 条，或
- 全部候选 `score < score_threshold` 被过滤

**与无关问 bypass 区分**：`is_irrelevant_question()` 仍 **不检索**、不走 RAG Prompt；空召回仅指 **已选 KB 且执行了检索** 但未命中。

**实现落点**：

- `chain._resolve_system_prompt(..., has_context=False)` → `EMPTY_RETRIEVAL_SYSTEM_PROMPT`
- `rag_config.py` 新增常量（见 §8.4）

**推荐 Prompt 模板**（`rag_config.EMPTY_RETRIEVAL_SYSTEM_PROMPT`）：

```python
EMPTY_RETRIEVAL_SYSTEM_PROMPT = """你是企业知识库智能助手。

## 当前情况
本次检索 **未在知识库中找到** 与用户问题直接相关的官方资料。

## 回答要求
1. **先说明未命中**：回答开头须明确告知用户「未在知识库中找到相关内容」。
2. **谨慎补充**：若问题仍属一般性、常识性范畴，可基于通用知识提供简要参考，帮助用户理解问题背景或排查方向。
3. **标明性质**：凡非来自知识库的内容，须明确标注为「通用参考 / 非官方资料」，不得表述为「根据公司规定」「制度要求」等。
4. **禁止编造**：不得虚构具体制度条款、审批流程、福利天数、报销比例、联系人等可核实事实；不确定时直接说明不确定。
5. **引导正式渠道**：涉及公司制度、流程、福利等时，建议用户查阅 HR/行政正式文件或联系对口部门确认。

## 语气
专业、友好、克制；宁可少答、标明不确定，也不要用看似权威的幻觉填补空白。"""
```

**回答结构示例**（制度类）：

> 未在知识库中找到与您问题直接相关的官方资料。  
> 以下为基于通用实践的参考（**非公司正式规定**）：……  
> 具体以公司 HR/员工手册为准，建议您向对口部门确认。

---

### 4.6 方案 H：Embedding 重建 ✅ 已落地

```
reindex_kb_vectors(kb_id):
  chroma_store.delete_by_kb(kb_id)
  for doc in kb.documents (非 PROCESSING 且无分块则 _process_document):
    if 已有分块:
      _reembed_document()   # 按 MySQL 分块分批 re-embed + upsert（asyncio.to_thread）
    else:
      _process_document()   # 全量解析 + B 分块 + 向量化
  return { total, success, failed, skipped, errors }
```

**触发**：

- API：`POST /knowledge-bases/{kb_id}/reindex`（需写权限）
- 管理端：知识库编辑抽屉 → **「重建向量」**（`KnowledgeBaseEditDrawer.vue`）

**说明**：H 面向 **换 Embedding 模型** 或 Chroma 与 MySQL 不一致；**不替代**「重新上传」来应用 B 新分块策略。大批量文档同步重建可能耗时数分钟～数十分钟（Embedding API 限速）；`get_embedding` 经 `asyncio.to_thread` 执行，不阻塞其他 HTTP 请求。

---

### 4.7 方案 I：离线评测（已移出代码库）

原 `backend/eval/`、`backend/services/scripts/`（含 `run_rag_eval.py`、`run_rag_tune.py`、`init_admin.py`、`build_kb.py` 等）为开发/运维期 CLI，**不属于业务运行时**，已从仓库删除。

**当前验收方式**：

- 产品验收：§11 手工检查清单（空召回、溯源、多轮等）

---

### 4.8 方案 M0：会话记忆完善（L1 短程原文）✅ 已落地

| 项 | 做法 | 改动点 |
|----|------|--------|
| M0.1 | 按 **轮数 + token** 双限截断 history | `trim_chat_history()` → `format_messages` |
| M0.2 | retrieval query = 最近 1～2 轮 + 当前问 | `retriever.build_query()` / **`query_enhancer.build_retrieval_query()`（P1-1 省略追问补全）** |
| M0.3 | Run 模式默认不继承 chat 历史 | `execute_skill_run` 保持 `chat_history=[]` |

**与 M1 分工**：M0 只负责 **最近 R 轮原文**（R = `max_history_rounds`）；**不**为记住远处而增大 R。

**推荐默认值**（32k context 模型、企业 KB 场景）：

| 参数 | 默认值 | 范围 | 说明 |
|------|--------|------|------|
| `max_history_rounds` | **8** | 6～10 | 最近 8 轮 user+assistant 原文 |
| `max_history_tokens` | **6000** | 4000～8000 | 原文历史 token 硬顶；与轮数取 **更严者** |

**过渡期（仅 M0、未上 M1）**：`max_history_rounds` 可暂用 **10**（与现网一致），仍建议配 `max_history_tokens=6000`。

---

### 4.9 方案 M1：滚动摘要（L2 长程记忆）✅ 已落地（2026-06-30）

> **策略**：**滚动合并**（rolling summary），**不是**「每满 N 轮整段覆盖一次」。窗口 **外** 的消息增量并入 summary；窗口 **内** 始终保留 M0 原文。

**落点**：

| 模块 | 路径 |
|------|------|
| 表字段 | 迁移 `30_*conversation_summary`：`Conversation.summary` / `summary_covered_until_message_id` / `summary_updated_time` |
| 摘要逻辑 | `chat_context_service.py`：`split_messages_for_summary` / `should_trigger_rolling_summary` / `run_conversation_summary` |
| 注入 | `chat_context_service.build_memory_system_section` → `chat_view` → `extra_system` |
| 触发 | `chat_view` SSE 落库后 `asyncio.create_task(run_conversation_summary)`（不阻塞流式） |
| 配置 | `PROJECT_CONFIG.SUMMARY_*`（§8.3） |

#### 4.9.1 注入结构

```text
[────── 已滚进 summary 的远处 ──────][── 最近 R 轮原文 M0 ──][当前 user 问]

LLM 输入:
  system: ## 对话摘要\n{summary}     ← M1（滚动累积）
          ## 用户相关信息\n{...}     ← M2
          + RAG / Skill 段
  messages: trim(最近 R 轮, max_history_tokens)
            + 当前 user
```

#### 4.9.2 滚动摘要流程

```
1. R = max_history_rounds（默认 8）
2. 保留区 = 最近 R 轮消息（且 ≤ max_history_tokens）
3. 待摘要区 = (summary_covered_until_message_id 之后) ～ (保留区之前) 的消息
4. 若满足触发条件 且 待摘要区非空:
     异步 LLM 将待摘要区合并进 Conversation.summary（append/merge，非覆盖）
     更新 summary_covered_until_message_id
5. 下次 chat 读 summary + M0 保留区
```

**禁止**：按固定「每 N 轮清空重写 summary」；**禁止**用增大 R 替代摘要。

#### 4.9.3 触发条件（推荐默认）

满足 **任一** 即触发（**SSE 完成后 asyncio 异步**，不阻塞聊天）：

| 条件 | 推荐默认 | 说明 |
|------|----------|------|
| 首次触发 | 总消息数 **> 24** | 约 12 轮对话后，且存在待摘要区 |
| 等价式 | 总消息数 **> R×2 + 8** | R=8 时即为 >24 |
| 再次滚动 | 距上次摘要后，待摘要区又新增 **≥ 8 条**消息 | `summary_retrigger_gap_messages` |
| Token 兜底 | 未摘要区 + 保留区原文 **> 8000 tokens** | `summary_trigger_history_tokens` |

#### 4.9.4 推荐默认值（定稿）

| 参数 | 默认值 | 范围 | 方案 |
|------|--------|------|------|
| `summary_enabled` | **true** | — | M1 |
| `summary_trigger_messages` | **24** | 20～32 | 首次触发（总消息数） |
| `summary_retrigger_gap_messages` | **8** | 6～12 | 再次滚动间隔 |
| `summary_trigger_history_tokens` | **8000** | 6000～10000 | token 兜底触发 |
| `summary_max_tokens` | **800** | 500～1200 | 单次摘要 **输出** 上限 |
| `summary_merge_strategy` | **rolling_merge** | — | 合并进已有 summary |

#### 4.9.5 表结构与模块

| 字段 / 模块 | 说明 |
|-------------|------|
| `Conversation.summary` | 滚动累积摘要正文 |
| `summary_covered_until_message_id` | 摘要已覆盖到哪条消息（含） |
| `summary_updated_time` | 最后摘要时间 |
| `summary_service.py` | 异步摘要任务；prompt 要求 **合并** 旧 summary + 新片段 |

#### 4.9.6 Context 预算（与 RAG 同屏，32k 模型）

| 部分 | 推荐上限 |
|------|----------|
| 对话摘要（M1） | 800～1200 tokens |
| 原文历史（M0） | ≤ 6000 tokens |
| RAG parent（C 后） | 3000～5000 tokens |
| 生成预留 | `max_tokens` 2048～4096 |

**结论**：启用 M1 后 **`max_history_rounds` 保持 8 即可**，无需为「记远处」调到 15～20。

#### 4.9.7 验收要点

- 长会话（>24 条消息）早期用户约束仍可通过 **summary** 回答
- 最近 8 轮指代、改写类追问仍依赖 **原文**，不依赖 summary
- 摘要任务失败时不阻塞聊天；保留 M0 原文 + 旧 summary

### 4.10 方案 M2：用户长期记忆（仅显式）✅ 已落地（2026-06-30）

**写入**：仅用户指令「记住…」→ `explicit_memory_parser` 解析 → `user_memory_crud.create_explicit_memory`。**禁止**自动抽取。

**落点**：

| 模块 | 路径 |
|------|------|
| 表 | 迁移 `31_*user_memories` → `UserMemory` |
| 解析 | `explicit_memory_parser.py`（「记住：…」/ 敏感词拦截） |
| CRUD | `user_memory_crud.py` → `list_active_memories` / 软删 |
| 注入 | `memory_service.build_memory_context` → `## 用户相关信息` |
| 聊天写入 | `prepare_for_chat` → `try_save_explicit_memory_from_question` |
| API | `GET/POST/DELETE /chat/memories` |
| UI | `frontend/src/views/profile/index.vue`「我的记忆」 |

**表** `user_memories`：

| 字段 | 说明 |
|------|------|
| `user_id` | 所属用户 |
| `memory_key` | 可选分类（department / preference） |
| `content` | 记忆正文 |
| `source` | 固定 `explicit` |
| `expires_at` | 可选 |
| `state` | 软删 |

**读取**：`list_active_memories(user_id)` → system `## 用户相关信息`（建议最多 **10 条**，单条 **≤200 字**）。

**API/UI**：「我的记忆」列表与删除；注销用户级联删除；敏感 key 黑名单校验。

---

## 五、实施前准备

### 5.1 环境变量（三套独立，见 §8.3）

| 类别 | 是否必填 | 准备项 |
|------|----------|--------|
| **LLM** | ✅ 必填 | `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL_NAME` |
| **Embedding** | ✅ 必填（要做 RAG） | `EMBEDDING_API_KEY` / `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL_NAME` |
| **Rerank** | ⭕ 可选 | `RERANK_API_KEY` / `RERANK_BASE_URL` / `RERANK_MODEL`；**未配 Key 则不启用 F** |
| **回归** | ✅ 建议 | §11 手工检查清单 |
| **文档样本** | ✅ 建议 | 跨页条款、表格、专有名词 PDF（验证 B/C） |
| **Chroma** | ✅ | `backend/core/chroma_db` 备份流程 |
| **合规** | ✅（M2） | 可记忆字段白名单 |
| **产品** | ✅ | 空召回：`retrieval_empty` SSE + `EMPTY_RETRIEVAL_SYSTEM_PROMPT`（§4.5.1） |

**新人最小部署**：仅配 LLM + Embedding 即可跑通 RAG；Rerank 后续补 Key 即自动启用（无需改代码路径，仅配环境变量 + 重启）。

---

## 六、实施路线

### 6.1 分期交付（建议 约 3 周）

```
阶段 0（已有）   基础向量 RAG + Message 轮数截断
       │
       ▼
阶段 1 ✅        P0 A   │  P1 F  │  P2 G  │  P1b M0  │  P4 H
       │          标定   │ Rerank │ 溯源   │ 会话     │ 重建API
       ▼
阶段 2 ✅        P3 B │  P6 C │  P5 M1 │  P7 M2
       │          结构分块 │ 父块 │ 摘要 │ 显式记忆+UI
       ▼
验收            §十一 checklist
```

### 6.2 当前检索链路（2026-06-30 已实现）

```text
memory_ctx = await build_memory_context(conv, user)   # M1 summary + M2 facts ✅
retrieval_q = retriever.build_query(question, chat_history)     # M0.2 ✅
trimmed_history = trim_chat_history(..., max_history_tokens)    # M0.1 ✅
candidates = retriever.vector_fetch(retrieval_q, kb_ids, fetch_top_k)
final = retriever.apply_rerank(candidates, top_k)               # F ✅（可选）
context = await expand_context(final)                           # C ✅
yield sources / retrieval_empty → LLM(extra_system=memory)      # G + M1 ✅
# SSE done → run_conversation_summary(conversation_id)        # M1 异步
```

### 6.3 目标检索链路（阶段 2 全部完成后）

```text
memory_ctx = memory_service.build_context()   # M1 summary + M2 facts
retrieval_q = retriever.build_query(question, chat_history[-2:])  # M0.2
trimmed_history = trim_chat_history(chat_history, R=8, max_tokens=6000)  # M0
candidates = retriever.vector_fetch(retrieval_q, kb_ids, fetch_top_k)  # Chroma
final = retriever.apply_rerank(candidates, top_k)  # F
context = retriever.expand_context(final)        # C ✅
yield sources(G) → LLM
```

---

## 七、模块与 Orchestrator 接入

### 7.1 目录结构

```
applications/base/rag/
├── chain.py
├── retriever.py          # retrieve / vector_fetch / build_query / expand_context ✅
├── reranker.py           # F ✅
├── chroma_store.py
├── embeddings.py
└── llm.py                # trim_chat_history / format_messages ✅

applications/knowledge_base/services/
├── structure_chunker.py  # B ✅
├── document_loader.py
└── knowledge_base_crud.py  # _process_document / reindex_kb_vectors ✅

applications/conversation/services/
├── chat_context_service.py  # M1 滚动摘要 + M2 记忆注入 ✅
└── user_memory_crud.py      # M2 CRUD ✅

applications/conversation/models/
├── conversation_model.py
└── user_memory_model.py  # M2 ✅
```

### 7.2 Orchestrator 顺序

**当前（已实现）**：

```
1. memory_section = format_memory_system_section(conv)（M1）
2. prepare_for_chat → trim_chat_history（M0）
3. retrieval_q = build_query(question, chat_history)（M0.2）
4. retrieve() → expand_context() → sources / context（F+G+C）
5. yield sources / retrieval_empty
6. _resolve_system_prompt + build_hybrid_system_prompt(extra_system=memory)
7. format_messages(trimmed_history)
8. llm.stream_chat()
9. chat_view 落库 → run_conversation_summary（M1 异步）
```

**目标（M1/M2/C 完成后）**：
1. resolve_chat_binding(skill, mcp)
2. memory_ctx = memory_service.build_context(user, conversation)
3. retrieval_q = retriever.build_query(question, chat_history)
4. search_results, context = retriever.retrieve(retrieval_q, kb_ids)
5. combined_system = build_hybrid_system_prompt(rag + skill + memory_ctx)
6. messages = format_messages(history, summary=memory_ctx.summary)
7. yield sources / retrieval_empty
8. yield LLM stream
```

---

## 八、配置扩展

### 8.1 三套独立模型参数（`.env`）

与 `is_embedding_configured()` 对称，Rerank 以 **`is_rerank_configured()`** 判断：**仅当 `RERANK_API_KEY` 非空** 时视为已配置。

```env
# 1. LLM（对话、M1 摘要、Skill）
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL_NAME=

# 2. Embedding（向量入库 + 向量检索）
EMBEDDING_API_KEY=
EMBEDDING_BASE_URL=
EMBEDDING_MODEL_NAME=

# 3. Rerank（可选；不配则整条 F 跳过）
RERANK_API_KEY=
RERANK_BASE_URL=
RERANK_MODEL=qwen3-rerank

# RAG 全局（可选）
RETRIEVAL_FETCH_TOP_K=30
RETRIEVAL_SCORE_THRESHOLD=0.45
RETRIEVAL_MIN_HITS_PER_KB=2
# RETRIEVAL_FETCH_PER_KB=0   # 0=自动 max(10, fetch_top_k // 库数)
# RETRIEVAL_MAX_HITS_PER_KB=0  # 0=不限制单库上限
RETRIEVAL_QUERY_ENHANCE_ENABLED=true
ANSWER_CONSISTENCY_LOG_ENABLED=true
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

**约束**：

- 三套 Key **独立**，禁止代码层用 Embedding Key 调用 Rerank 或 LLM。
- **`RERANK_API_KEY` 为空** → `is_rerank_configured() == False` → **不调用 Rerank API**，`retriever` 使用向量候选前 `top_k`。
- 三套可指向不同厂商（如 LLM=DeepSeek、Embedding=百炼、Rerank=硅基）。

### 8.2 ModelConfig（RAG 运行时）

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `fetch_top_k` | int | 30 | 向量扩召回数 |
| `top_k` | int | 6 | 进 Prompt 条数（Rerank 后或向量直取） |
| `score_threshold` | float | 标定 | 见 §4.1 |
| `rerank_enabled` | bool | true | **仅当 `is_rerank_configured()` 为 true 时生效**；无 Key 时无效 |
| `rerank_model` | str | — | 可覆盖 `.env` 的 `RERANK_MODEL`；仍须有 `RERANK_API_KEY` |

### 8.3 记忆配置（M0 / M1 / M2 推荐默认值）

**原则**：`max_history_rounds`（短程原文）与 M1 触发参数 **分开配置**；有 M1 后 **不必增大 R**。

| 字段 | 类型 | 默认 | 范围 | 方案 | 说明 |
|------|------|------|------|------|------|
| `max_history_rounds` | int | **8** | 6～10 | M0 | 最近 R 轮原文；ModelConfig 已有（0～20），**有 M1 时建议 ≤10** |
| `max_history_tokens` | int | **6000** | 4000～8000 | M0 | 原文 token 硬顶 |
| `summary_enabled` | bool | **true** | — | M1 | 滚动摘要 |
| `summary_trigger_messages` | int | **24** | 20～32 | M1 | 总消息数首次触发（≈ R×2+8） |
| `summary_retrigger_gap_messages` | int | **8** | 6～12 | M1 | 再次滚动：待摘要区新增消息数 |
| `summary_trigger_history_tokens` | int | **8000** | 6000～10000 | M1 | token 兜底触发 |
| `summary_max_tokens` | int | **800** | 500～1200 | M1 | 单次摘要输出上限 |
| `user_memory_enabled` | bool | **true** | — | M2 | 显式跨会话记忆 |

**`.env` / 全局默认（可选，ModelConfig 可覆盖）**：

```env
# M0 短程原文
MAX_HISTORY_ROUNDS=8
MAX_HISTORY_TOKENS=6000

# M1 滚动摘要
SUMMARY_ENABLED=true
SUMMARY_TRIGGER_MESSAGES=24
SUMMARY_RETRIGGER_GAP_MESSAGES=8
SUMMARY_TRIGGER_HISTORY_TOKENS=8000
SUMMARY_MAX_TOKENS=800
```

M2 **不提供** `memory_auto_extract`（自动抽取不在范围内）。

### 8.4 空召回 Prompt（G）

| 常量 | 文件 | 说明 |
|------|------|------|
| `EMPTY_RETRIEVAL_SYSTEM_PROMPT` | `rag_config.py` | 空召回专用；**替代** `GENERAL_SYSTEM_PROMPT` |
| `RAG_SYSTEM_PROMPT` | 不变 | 有 context 时仍用 |
| `GENERAL_SYSTEM_PROMPT` | 保留或废弃 | 实施时由 `EMPTY_RETRIEVAL_*` 接管空召回路径 |

---

## 九、后端衔接注意事项

### 9.1 RAG

1. 检索参数以 `prepare_for_chat` → `ModelConfig` 为准；分块以知识库 `chunk_size` 为准，**入库走 B**（`structure_chunker`）。
2. 多库检索已实现 **per-KB 配额**（`retriever.apply_kb_quota`：分库 fetch + 终选每库至少 `RETRIEVAL_MIN_HITS_PER_KB` 条）。
3. **空召回（§4.5.1）**：已实现 yield `retrieval_empty` + 前端提示 + `EMPTY_RETRIEVAL_SYSTEM_PROMPT`。
4. `is_irrelevant_question()` 仍 bypass 检索（与 F 正交）。
5. **`is_rerank_configured()`** 与 **`is_embedding_configured()`** 独立；缺 Rerank Key 不报错，走降级。
6. 重建 H 仅更新 Chroma（无 Meilisearch）；reindex 用 `asyncio.to_thread(get_embedding)` 避免阻塞事件循环。
7. Skill + KB 并行；`skill_read` 不读 KB。
8. **B 与 H 分工**：新上传 → B 分块；换模型 → H re-embed；旧文档要 B → **重新上传**。

### 9.2 记忆

1. KB 与用户 memory **不得**共用 Chroma collection。
2. 制度事实只来自 RAG；M2 仅存偏好/身份类 fact（**M2 ✅**）。
3. wizard/async Run **默认**不带 chat 历史。
4. **M0 已落地**：orchestrator 内 `trim_chat_history` 结果供 `retrieve` 与 `format_messages` 共用；`build_query` 带最近 2 轮。
5. **M1 已落地**：`chat_view` 注入 `## 对话摘要`；SSE 后 `run_conversation_summary`；失败不阻塞聊天。
6. **M2 设计约束**（待实现）：M2 仅 explicit 写入且须可删除。

---

## 十、实现优先级

| 阶段 | 内容 | 类型 | 工作量 |
|------|------|------|--------|
| P0 | A：参数标定 | RAG | 0.5～1 天 | ✅ |
| P1 | F：`retriever.py` + `reranker.py` | RAG | 1～2 天 | ✅ |
| P1b | M0：token 截断 + query 上下文化 | 记忆 | 1～2 天 | ✅ |
| P2 | G：SSE sources + 前端引用 | RAG | 1～2 天 | ✅ |
| P3 | B：结构分块 | RAG | 1～2 天 | ✅ |
| P4 | H：重建向量 API | RAG | 1 天 | ✅ |
| P5 | M1：会话摘要 | 记忆 | 2～3 天 | ✅ |
| P6 | C：父块扩展 | RAG | 2～3 天 | ✅ |
| P7 | M2：显式记忆 + 「我的记忆」UI | 记忆 | 3～5 天 | ✅ |

---

## 十一、验收要点

### 11.1 RAG

- [x] 空召回：无关问「量子纠缠…」在 `score_threshold=0.45` 下正确空召回（开发期抽检）
- [x] Rerank 已配置时：SSE sources 条数 ≤ `top_k`（默认 6）
- [x] Rerank 未配置时：系统可正常 RAG，日志有降级提示，无 Rerank API 调用
- [ ] 编号/专有名词子集召回可接受（B 新上传 + 线上抽检）
- [ ] 父块扩展（C）后跨页条款回答完整度提升
- [x] SSE `sources` 与回答引用一致（文件名、页码）；刷新后 `sources_json` 仍可见
- [x] 空召回：SSE `retrieval_empty` + 回答 **开头声明未命中**
- [x] 空召回：前端横幅「未在知识库中找到相关内容」；刷新后仍显示
- [ ] 空召回：常识补充处标注「非官方 / 通用参考」；抽检无编造条款/数字
- [ ] 空召回：制度类问题引导查阅正式文件（见 §4.5.1 示例）
- [x] 换 embedding 后可通过管理端「重建向量」完成 re-embed（无单独「待重建」状态 UI）
- [ ] P95 延迟增加可控（Rerank 目标按环境标定，通常 +200～500ms）

### 11.2 记忆

- [ ] 多轮指代追问：RAG 召回优于「仅用当前问」（M0 待线上验证）
- [ ] 总消息 >24 后：早期约束可通过 **滚动 summary** 回答（M1 ✅ 已落地，待长会话实测）
- [ ] 最近 8 轮指代/改写仍主要依赖 **原文**（M0），不依赖 summary
- [ ] 再次滚动：待摘要区新增 ≥8 条后 summary 增量更新，非整段覆盖（M1 ✅）
- [ ] 显式「记住…」后新会话可召回；删除后不可召回（M2 ✅ 待 E2E 验证）
- [x] 无自动写入 user_memories 的代码路径（仅 parser + 手动 API）
- [x] 注销/删除用户时 memory 随 `user_id` CASCADE 删除
- [ ] 摘要任务失败时聊天仍可用（M0 原文 + 旧 summary）（M1 ✅ 异常仅打日志）

---

## 十二、相关代码索引

| 层级 | 路径 |
|------|------|
| 统一检索 | `backend/applications/base/rag/retriever.py` → `retrieve()` |
| Rerank | `backend/applications/base/rag/reranker.py` → `apply_rerank()` |
| 兼容入口 | `backend/applications/base/rag/chain.py` → `rag_stream` / `_resolve_system_prompt` |
| 向量库 | `backend/applications/base/rag/chroma_store.py` |
| Embedding | `backend/applications/base/rag/embeddings.py` |
| Prompt | `backend/configure/rag_config.py` |
| 结构分块 | `backend/applications/knowledge_base/services/structure_chunker.py` |
| 入库 / 重建 | `knowledge_base_crud._process_document` / `reindex_kb_vectors` |
| 重建 API / UI | `POST .../reindex`；`KnowledgeBaseEditDrawer.vue`「重建向量」 |
| 参数标定 | 迁移 `32_*calibrate_score_threshold`；`.env` `RETRIEVAL_SCORE_THRESHOLD=0.45` |
| 文档加载 | `backend/applications/knowledge_base/services/document_loader.py` |
| 检索参数 | `backend/applications/model_config/models/model_config_model.py` |
| LLM 参数合并 | `backend/applications/model_config/services/llm_connection.py` |
| 聊天编排 | `backend/applications/agent/orchestrator/chat_agent_orchestrator.py` |
| 会话准备 | `backend/applications/conversation/services/conversation_crud.py` |
| 消息模型 | `backend/applications/conversation/models/conversation_model.py` |
| 历史格式化 | `backend/applications/base/rag/llm.py` → `format_messages` / `trim_chat_history` |
| 滚动摘要 | `chat_context_service.py`；迁移 `30_*conversation_summary` |
| 记忆注入 | `chat_context_service.build_memory_system_section` |
| 提示词配置 | `configure/rag_config.py`（RAG / 记忆摘要 / 混合智能体） |
| 显式记忆 | `user_memory_crud.py` / `explicit_memory_parser.py` |
| 记忆 API | `conversation/views/memory_view.py` → `/chat/memories` |
| 记忆 UI | `frontend/src/views/profile/index.vue` |
| 流式 API | `backend/applications/conversation/views/chat_view.py` |
| 前端溯源 | `frontend/src/components/MessageBubble.vue` |
| 前端重建 | `frontend/src/views/knowledge-base/components/KnowledgeBaseEditDrawer.vue` |
| 知识库选择 | `backend/output/docs/CHAT_KB_SELECTION.md` |
| 离线评测 | `backend/output/docs/RAG_EVAL_GUIDE.md` + `backend/output/eval/questions.template.jsonl` |
| 聊天流程 | `backend/output/docs/CHAT_EXECUTION_FLOWS.md` |

---

## 十三、待落地参数（实施中微调）

以下已有 **推荐默认值**（§4.8～4.9、§8.3），上线后用真实会话与 §11 抽检 **微调**：

| 项 | 推荐默认 | 当前 / 微调方向 |
|----|----------|-----------------|
| `score_threshold` | **0.45** | ✅ `.env` + ModelConfig 回退 + 迁移 32 |
| `fetch_top_k` | 30 | ✅ |
| `top_k` | 6 | ✅ |
| `chunk_size` | 900～1200（制度类） | 知识库级可配；B 新上传生效 |
| `max_history_rounds` | 8 | ModelConfig；M0 已接入 |
| `max_history_tokens` | 6000 | `.env` / `PROJECT_CONFIG` ✅ |
| `summary_*` | 见 §4.9.4 | M1 ✅；`.env` / `PROJECT_CONFIG.SUMMARY_*` |

**已确认（不再微调）**：

| 项 | 定稿行为 | 详见 |
|----|----------|------|
| 空召回时 LLM 行为 | 提示未命中 + 相关常识谨慎补充 + 标明非官方 | §4.5.1 |
