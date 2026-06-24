# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : skill_run_events.py
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional


class SkillRunEventHub:
    """进程内 Run 事件队列（wizard 模式 SSE）。"""

    _queues: Dict[str, asyncio.Queue] = {}
    _cancel_flags: Dict[str, bool] = {}
    _running: Dict[str, bool] = {}

    @classmethod
    def get_queue(cls, run_id: str) -> asyncio.Queue:
        if run_id not in cls._queues:
            cls._queues[run_id] = asyncio.Queue()
        return cls._queues[run_id]

    @classmethod
    def mark_running(cls, run_id: str) -> None:
        cls._running[run_id] = True
        cls._cancel_flags[run_id] = False

    @classmethod
    def is_running(cls, run_id: str) -> bool:
        return cls._running.get(run_id, False)

    @classmethod
    def request_cancel(cls, run_id: str) -> None:
        cls._cancel_flags[run_id] = True

    @classmethod
    def is_cancelled(cls, run_id: str) -> bool:
        return cls._cancel_flags.get(run_id, False)

    @classmethod
    async def publish(cls, run_id: str, event: Dict[str, Any]) -> None:
        await cls.get_queue(run_id).put(event)

    @classmethod
    async def finish(cls, run_id: str) -> None:
        await cls.get_queue(run_id).put(None)
        cls._running.pop(run_id, None)
        cls._cancel_flags.pop(run_id, None)

    @classmethod
    def cleanup(cls, run_id: str) -> None:
        cls._queues.pop(run_id, None)
        cls._running.pop(run_id, None)
        cls._cancel_flags.pop(run_id, None)
