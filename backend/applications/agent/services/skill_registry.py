# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : skill_registry.py
"""
from __future__ import annotations

import hashlib
import io
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from backend.configure import PROJECT_CONFIG

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_SKILL_KEY_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


@dataclass
class DiskSkillMeta:
    skill_key: str
    name: str
    description: Optional[str]
    skill_version: str
    skill_md_path: Path
    root_path: Path


def get_skills_root() -> Path:
    return Path(PROJECT_CONFIG.SKILLS_DIR)


def parse_skill_md(skill_md_path: Path) -> tuple[Optional[Dict[str, Any]], str]:
    """解析 SKILL.md frontmatter 与正文。"""
    text = skill_md_path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None, text
    frontmatter = yaml.safe_load(match.group(1)) or {}
    body = text[match.end():]
    return frontmatter, body


def compute_skill_version(skill_dir: Path) -> str:
    """根据 Skill 包全部文件内容计算版本 hash。"""
    digest = hashlib.sha256()
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(skill_dir).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def list_disk_skills() -> List[DiskSkillMeta]:
    """扫描磁盘 Skill 目录。"""
    root = get_skills_root()
    if not root.is_dir():
        return []

    results: List[DiskSkillMeta] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.is_file():
            continue

        frontmatter, _ = parse_skill_md(skill_md)
        meta = frontmatter or {}
        skill_key = entry.name
        name = str(meta.get("name") or skill_key)
        description = meta.get("description")
        if isinstance(description, list):
            description = " ".join(str(x) for x in description)
        elif description is not None:
            description = str(description).strip() or None

        results.append(
            DiskSkillMeta(
                skill_key=skill_key,
                name=name[:128],
                description=description,
                skill_version=compute_skill_version(entry),
                skill_md_path=skill_md,
                root_path=entry,
            )
        )
    return results


def build_directory_tree(skill_dir: Path, *, max_depth: int = 6) -> List[Dict[str, Any]]:
    """构建 Skill 目录树（相对路径）。"""

    def collect_dir(dir_path: Path, depth: int) -> List[Dict[str, Any]]:
        if depth > max_depth:
            return []
        items: List[Dict[str, Any]] = []
        for sub in sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            sub_rel = sub.relative_to(skill_dir).as_posix()
            item: Dict[str, Any] = {
                "name": sub.name,
                "path": sub_rel,
                "type": "dir" if sub.is_dir() else "file",
            }
            if sub.is_dir():
                item["children"] = collect_dir(sub, depth + 1)
            items.append(item)
        return items

    if not skill_dir.is_dir():
        return []
    return collect_dir(skill_dir, 0)


def read_skill_preview(skill_key: str) -> Dict[str, Any]:
    """读取 Skill 预览信息。"""
    skill_dir = get_skills_root() / skill_key
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise FileNotFoundError(f"Skill 目录不存在或缺少 SKILL.md: {skill_key}")

    frontmatter, body = parse_skill_md(skill_md)
    return {
        "skill_key": skill_key,
        "skill_md": skill_md.read_text(encoding="utf-8"),
        "frontmatter": frontmatter or {},
        "body_preview": body[:4000],
        "directory_tree": build_directory_tree(skill_dir),
        "skill_version": compute_skill_version(skill_dir),
    }


def ensure_chat_snapshot(
        skill_key: str,
        user_id: int,
        conversation_id: str,
        *,
        force: bool = False,
) -> Path:
    """为聊天模式复制 Skill 快照，返回快照根目录。"""
    source = get_skills_root() / skill_key
    if not source.is_dir():
        raise FileNotFoundError(f"磁盘 Skill 不存在: {skill_key}")

    runs_root = Path(PROJECT_CONFIG.SKILL_RUNS_DIR) / str(user_id) / f"chat_{conversation_id}"
    snapshot = runs_root / ".skill_snapshot"
    version_file = runs_root / ".skill_version"
    current_version = compute_skill_version(source)

    if (
            not force
            and snapshot.is_dir()
            and version_file.is_file()
            and version_file.read_text(encoding="utf-8").strip() == current_version
    ):
        return snapshot

    if snapshot.exists():
        shutil.rmtree(snapshot)
    runs_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, snapshot)
    version_file.write_text(current_version, encoding="utf-8")
    return snapshot


def copy_skill_snapshot(skill_key: str, snapshot_dir: Path) -> str:
    """复制磁盘 Skill 包到指定快照目录，返回 skill_version。"""
    source = get_skills_root() / skill_key
    if not source.is_dir():
        raise FileNotFoundError(f"磁盘 Skill 不存在: {skill_key}")

    current_version = compute_skill_version(source)
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    snapshot_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, snapshot_dir)
    return current_version


def _safe_extract_zip(zf: zipfile.ZipFile, dest: Path) -> None:
    for member in zf.infolist():
        member_path = Path(member.filename)
        if member_path.is_absolute() or ".." in member_path.parts:
            raise ValueError(f"非法 zip 路径: {member.filename}")
    zf.extractall(dest)


def _find_skill_root(extract_dir: Path) -> tuple[Path, Optional[str]]:
    """在解压目录中定位含 SKILL.md 的 Skill 根目录。"""
    root_skill_md = extract_dir / "SKILL.md"
    if root_skill_md.is_file():
        return extract_dir, None

    candidates = [
        child
        for child in extract_dir.iterdir()
        if child.is_dir() and (child / "SKILL.md").is_file()
    ]
    if len(candidates) == 1:
        return candidates[0], candidates[0].name
    if len(candidates) > 1:
        raise ValueError("zip 包含多个 Skill 目录，请分别上传")
    raise ValueError("zip 中未找到 SKILL.md")


def install_skill_from_zip(
        content: bytes,
        *,
        skill_key: Optional[str] = None,
        overwrite: bool = False,
) -> DiskSkillMeta:
    """解压 zip 到 skills 目录并返回磁盘元数据。"""
    max_bytes = PROJECT_CONFIG.SKILL_ZIP_MAX_BYTES
    if len(content) > max_bytes:
        raise ValueError(f"zip 大小超过限制 ({max_bytes // 1024 // 1024}MB)")

    with tempfile.TemporaryDirectory(prefix="skill_zip_") as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            _safe_extract_zip(zf, tmp_path)

        skill_root, detected_key = _find_skill_root(tmp_path)
        final_key = (skill_key or detected_key or "").strip()
        if not final_key:
            raise ValueError(
                "无法确定 skill_key：请在表单指定 skill_key，"
                "或使用「目录名/SKILL.md」结构，或以目录名命名 zip 文件"
            )
        if not _SKILL_KEY_RE.match(final_key):
            raise ValueError(
                "skill_key 无效，须为字母数字开头，仅含字母数字、下划线、连字符"
            )

        target = get_skills_root() / final_key
        if target.exists() and not overwrite:
            raise ValueError(f"Skill 目录已存在: {final_key}，如需覆盖请启用 overwrite")

        get_skills_root().mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(skill_root, target)

    for meta in list_disk_skills():
        if meta.skill_key == final_key:
            return meta
    raise FileNotFoundError(f"安装后未找到 Skill: {final_key}")
