# -*- coding: utf-8
"""M2 显式记忆：解析「记住…」指令与敏感内容校验。"""
from __future__ import annotations

import re
from typing import Optional

EXPLICIT_MEMORY_PATTERNS = (
    re.compile(r"^(?:请)?(?:帮我)?记住[：:，,\s]+(.+)$", re.IGNORECASE),
    re.compile(r"^(?:请)?(?:帮我)?记一下[：:，,\s]+(.+)$", re.IGNORECASE),
    re.compile(r"^remember[：:\s]+(.+)$", re.IGNORECASE),
)

SENSITIVE_CONTENT_PATTERNS = (
    re.compile(r"密码|password|passwd", re.IGNORECASE),
    re.compile(r"身份证|id\s*card|ssn", re.IGNORECASE),
    re.compile(r"银行卡|bank\s*card|credit\s*card", re.IGNORECASE),
    re.compile(r"api[_\s-]?key|secret[_\s-]?key|access[_\s-]?token", re.IGNORECASE),
)

BLOCKED_MEMORY_KEYS = frozenset({
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "id_card",
    "ssn",
    "bank_card",
})


def parse_explicit_memory_request(question: str) -> Optional[str]:
    text = (question or "").strip()
    if not text:
        return None
    for pattern in EXPLICIT_MEMORY_PATTERNS:
        match = pattern.match(text)
        if match:
            content = (match.group(1) or "").strip()
            if content:
                return content
    return None


def is_sensitive_memory_content(content: str) -> bool:
    text = (content or "").strip()
    if not text:
        return True
    return any(pattern.search(text) for pattern in SENSITIVE_CONTENT_PATTERNS)


def infer_memory_key(content: str) -> Optional[str]:
    text = (content or "").strip()
    if not text:
        return None
    if any(k in text for k in ("部门", "科室", "团队")):
        return "department"
    if any(k in text for k in ("偏好", "喜欢", "习惯", "常用")):
        return "preference"
    if any(k in text for k in ("称呼", "叫我", "名字是")):
        return "identity"
    return None


def normalize_memory_key(memory_key: Optional[str]) -> Optional[str]:
    if not memory_key:
        return None
    key = memory_key.strip().lower().replace(" ", "_")
    if not key or key in BLOCKED_MEMORY_KEYS:
        return None
    return key[:64]
