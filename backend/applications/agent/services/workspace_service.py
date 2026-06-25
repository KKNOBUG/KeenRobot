# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : workspace_service.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from backend.applications.agent.models.agent_model import SkillRun
from backend.applications.agent.services.skill_registry import copy_skill_snapshot
from backend.configure import PROJECT_CONFIG

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class WorkspaceService:
    """Skill Run 工作区：runs/{user_id}/{run_id}/"""

    def __init__(self, run: SkillRun):
        self.run = run
        self.root = Path(PROJECT_CONFIG.SKILL_RUNS_DIR) / str(run.user_id) / run.id

    @property
    def input_dir(self) -> Path:
        return self.root / "input"

    @property
    def output_dir(self) -> Path:
        return self.root / "output"

    @property
    def snapshot_dir(self) -> Path:
        return self.root / ".skill_snapshot"

    @property
    def session_dir(self) -> Path:
        return self.root / "session"

    @property
    def meta_path(self) -> Path:
        return self.root / "meta.json"

    def init_draft_workspace(self, *, skill_version: str = "") -> None:
        """创建 draft Run 工作区（不含 Skill 快照，start 时再复制）。"""
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.write_meta(
            {
                "run_id": self.run.id,
                "skill_id": self.run.skill_id,
                "skill_key": self.run.skill_key,
                "skill_version": skill_version or self.run.skill_version,
                "conversation_id": self.run.conversation_id,
                "model_config_id": self.run.model_config_id,
                "interaction_mode": self.run.interaction_mode,
                "status": self.run.status,
                "user_id": self.run.user_id,
                "snapshot_at_start": True,
            }
        )

    def init_workspace(self, *, skill_version: str) -> None:
        """创建 run 目录结构并复制 Skill 快照（重试等需立即快照的场景）。"""
        self.init_draft_workspace(skill_version=skill_version)
        copy_skill_snapshot(self.run.skill_key, self.snapshot_dir)

    def ensure_skill_snapshot(self, skill_key: str) -> str:
        """start 时复制 Skill 快照，返回快照版本号。"""
        if self.snapshot_dir.is_dir():
            meta = self.read_meta()
            if meta.get("snapshot_ready"):
                return meta.get("skill_version") or ""
        version = copy_skill_snapshot(skill_key, self.snapshot_dir)
        meta = self.read_meta()
        meta["skill_version"] = version
        meta["snapshot_ready"] = True
        self.write_meta(meta)
        return version

    def write_meta(self, data: Dict[str, Any]) -> None:
        self.meta_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def read_meta(self) -> Dict[str, Any]:
        if not self.meta_path.is_file():
            return {}
        return json.loads(self.meta_path.read_text(encoding="utf-8"))

    def update_meta_status(self, status: str) -> None:
        meta = self.read_meta()
        meta["status"] = status
        self.write_meta(meta)

    def resolve_safe_path(self, relative_path: str) -> Path:
        rel = (relative_path or "").strip().lstrip("/")
        if not rel or ".." in Path(rel).parts:
            raise ValueError("非法路径")
        target = (self.root / rel).resolve()
        root_resolved = self.root.resolve()
        if not str(target).startswith(str(root_resolved)):
            raise ValueError("路径超出 Run 工作区")
        return target

    def save_upload(self, relative_path: str, content: bytes) -> Path:
        if len(content) > MAX_UPLOAD_BYTES:
            raise ValueError(f"文件大小超过限制 ({MAX_UPLOAD_BYTES // 1024 // 1024}MB)")
        target = self.resolve_safe_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return target

    def layout_roots(self, input_schema: Optional[Dict[str, Any]]) -> tuple[str, str]:
        layout = (input_schema or {}).get("layout") or {}
        input_root = (layout.get("input_root") or "input").strip("/") or "input"
        output_root = (layout.get("output_root") or "output").strip("/") or "output"
        return input_root, output_root

    def step_target_path(
            self,
            step: Dict[str, Any],
            input_schema: Optional[Dict[str, Any]],
            *,
            filename: Optional[str] = None,
    ) -> str:
        """根据 wizard step 计算存储相对路径。"""
        step_type = step.get("type")
        configured = (step.get("path") or "").strip().lstrip("/")
        input_root, _ = self.layout_roots(input_schema)
        key = step.get("key") or "field"

        if step_type == "file":
            if configured:
                return configured
            return f"{input_root}/{key}"

        if step_type == "dir":
            if configured:
                if filename:
                    return f"{configured.rstrip('/')}/{filename}"
                return configured
            if filename:
                return f"{input_root}/{key}/{filename}"
            return f"{input_root}/{key}"

        raise ValueError(f"步骤 {key} 不支持文件上传")

    def remove_workspace(self) -> None:
        """删除整个 Run 工作区目录。"""
        if self.root.exists():
            shutil.rmtree(self.root)

    def copy_inputs_from(self, source: WorkspaceService, input_schema: Optional[Dict[str, Any]]) -> None:
        """从另一 Run 复制 input 目录内容（用于重试）。"""
        input_root, _ = self.layout_roots(input_schema)
        src = source.resolve_safe_path(input_root)
        if not src.exists():
            return
        dst = self.resolve_safe_path(input_root)
        if dst.exists():
            shutil.rmtree(dst)
        if src.is_dir():
            shutil.copytree(src, dst)
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
