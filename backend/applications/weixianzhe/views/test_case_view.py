# -*- coding: utf-8 -*-
"""
@Author  : weixianzhe
@Project : KeenRobot
@Module  : test_case_view.py
@DateTime: 2026/6/11
"""
import asyncio
import functools
import os
import uuid
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, BackgroundTasks, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse

from applications.weixianzhe.models.test_case_task_model import TestCaseTask
from applications.weixianzhe.schemas.test_case_schema import TaskInfo, TaskListResponse
from applications.weixianzhe.services.claude_generator import ClaudeTestCaseGenerator
from applications.weixianzhe.utils.xlsx_writer import md_to_xlsx
from common.file_converter import convert_file_to_md
from configure import LOGGER, PROJECT_CONFIG
from core.responses import FailureResponse, SuccessResponse

test_case_router = APIRouter()


# ---------- decorators ----------

def _task_logger(
    state_field: str = "status",
    start_state: str = "PROCESSING",
    success_state: str = "SUCCESS",
    failure_state: str = "FAILED",
    error_field: str | None = "error_reason",
    build_record: Callable[..., Any] | None = None,
    post_update: Callable[..., Any] | None = None,
    inject_record: str | None = None,
    background: bool = False,
    return_field: str = "id",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """通过 record.save() 管理任务生命周期，不包含文件夹等非 SQL 逻辑。"""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            call_kwargs = dict(kwargs)

            record = build_record(*args, **call_kwargs) if build_record else None
            if record is not None:
                setattr(record, state_field, start_state)
                await record.save()

            if inject_record is not None:
                call_kwargs[inject_record] = record

            async def run() -> Any:
                try:
                    if record is not None and getattr(record, state_field) != start_state:
                        setattr(record, state_field, start_state)
                        await record.save()

                    result = await func(*args, **call_kwargs)

                except Exception as exc:
                    LOGGER.exception("Task failed: %s", exc)
                    if record is not None:
                        setattr(record, state_field, failure_state)
                        if error_field is not None:
                            setattr(record, error_field, str(exc)[:500])
                        await record.save()
                    if background:
                        return None
                    raise

                if record is not None:
                    if success_state != getattr(record, state_field, None):
                        setattr(record, state_field, success_state)
                    if post_update is not None:
                        await post_update(record, result, *args, **call_kwargs)
                    await record.save()

                return result

            if background:
                if record is None:
                    raise RuntimeError("background task logger requires build_record")
                task_id = getattr(record, return_field, None)
                if task_id is None:
                    raise RuntimeError("任务创建失败")
                asyncio.create_task(run())
                return task_id

            return await run()

        return wrapper

    return decorator


def _create_task_folder(
    inject_folder_path: str = "folder_path",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """在 workspace/test_case 下创建任务文件夹并注入到函数参数中。"""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            base_dir = os.path.join(PROJECT_CONFIG.WORKSPACE_DIR, "test_case")
            folder_path = os.path.abspath(os.path.join(base_dir, uuid.uuid4().hex))
            os.makedirs(folder_path, exist_ok=True)
            kwargs[inject_folder_path] = folder_path
            return await func(*args, **kwargs)

        return wrapper

    return decorator


# ---------- routes ----------

@test_case_router.get("/health", summary="健康检查")
def health():
    return SuccessResponse(data={"status": "ok"})


@test_case_router.post("/generateTestCases", summary="生成测试用例")
async def generate_test_cases(
    request: Request,
    files: list[UploadFile] = File(...),
    app_system: str = Form(""),
    requirement_name: str = Form(""),
):
    if not files:
        return FailureResponse(message="请至少上传一个文件")

    files_data = []
    for file in files:
        if not file.filename or not file.filename.lower().endswith(".docx"):
            return FailureResponse(message=f"文件「{file.filename}」不是 .docx 格式")
        docx_bytes = await file.read()
        if not docx_bytes:
            return FailureResponse(message=f"文件「{file.filename}」为空")
        safe_filename = os.path.basename(file.filename)
        files_data.append((docx_bytes, safe_filename))

    creater_user = request.headers.get("x-real-ip") or "user"

    try:
        task_id = await _run_generation(
            files_data=files_data,
            app_system=app_system,
            requirement_name=requirement_name,
            creater_user=creater_user,
        )
    except Exception as exc:
        LOGGER.exception("任务创建失败: %s", exc)
        return FailureResponse(message=f"任务创建失败: {exc}")

    return SuccessResponse(data={"status": "accepted", "task_id": task_id})


@_create_task_folder(inject_folder_path="folder_path")
@_task_logger(
    state_field="status",
    start_state="generating",
    success_state="success",
    failure_state="failed",
    error_field="error_reason",
    build_record=lambda *args, **kw: TestCaseTask(),
    inject_record="record",
    background=True,
)
async def _run_generation(
    files_data: list[tuple[bytes, str]],
    app_system: str,
    requirement_name: str,
    creater_user: str,
    folder_path: str,
    record: TestCaseTask | None = None,
) -> None:
    """后台任务：保存所有源文件 → 调用 Agent 生成。"""
    if record is None:
        raise RuntimeError("任务记录不存在")

    record.folder_path = folder_path
    record.app_system = app_system
    record.requirement_name = requirement_name
    record.created_user = creater_user
    record.updated_user = creater_user
    await record.save()

    for docx_bytes, filename in files_data:
        source_path = os.path.join(folder_path, filename)
        with open(source_path, "wb") as f:
            f.write(docx_bytes)

        # 将 docx 转换为 md，转换成功后删除原文件
        try:
            convert_file_to_md(source_path)
        except Exception as exc:
            LOGGER.exception("文件转换失败: %s", exc)
            raise RuntimeError(f"文件「{filename}」转换失败: {exc}")
        os.remove(source_path)

    generator = ClaudeTestCaseGenerator()
    result = await generator.generate(folder_path, output_dir=folder_path)

    # 校验产物是否生成，防止 Agent 返回成功但文件未落盘
    md_path = os.path.join(folder_path, "02-功能测试用例.md")
    if not os.path.isfile(md_path):
        LOGGER.warning("Agent 执行完毕但未生成产物, result_text 前200字符: %s", result[:200])
        raise RuntimeError("Agent 执行完成但未生成 02-功能测试用例.md")


@test_case_router.get("/tasks", summary="任务列表")
async def list_tasks(
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(5, ge=1, le=100, description="每页条数"),
):
    offset = (page - 1) * limit

    try:
        total = await TestCaseTask.all().count()
        tasks = await TestCaseTask.all().order_by("-created_time").offset(offset).limit(limit)
    except Exception as exc:
        LOGGER.exception("查询任务列表失败: %s", exc)
        return FailureResponse(message=f"查询任务列表失败: {exc}")

    data = TaskListResponse(
        total=total,
        page=page,
        limit=limit,
        items=[TaskInfo.model_validate(task) for task in tasks],
    )
    return SuccessResponse(data=data.model_dump(by_alias=True))


@test_case_router.get("/testCasesContent", summary="获取测试用例内容")
async def get_test_cases_content(task_id: int = Query(..., alias="taskId")):
    """根据 task_id 读取 02-功能测试用例.md 内容，返回 markdown 字符串。"""
    try:
        task = await TestCaseTask.get_or_none(id=task_id)
    except Exception as exc:
        LOGGER.exception("查询任务失败: %s", exc)
        return FailureResponse(message=f"查询任务失败: {exc}")

    if not task:
        return FailureResponse(message="任务不存在")

    if task.status != "success":
        return FailureResponse(
            message=f"任务状态为「{task.status}」，无法获取测试用例内容",
        )

    folder_path = task.folder_path
    if not folder_path:
        return FailureResponse(message="任务输出路径为空")

    md_path = Path(folder_path) / "02-功能测试用例.md"
    if not md_path.exists():
        return FailureResponse(message="未找到功能测试用例文件")

    content = md_path.read_text(encoding="utf-8")
    return SuccessResponse(data={"content": content})


@test_case_router.get("/downloadMarkdown", summary="下载测试用例 Markdown")
async def download_test_cases_markdown(task_id: int = Query(..., alias="taskId")):
    """根据 task_id 下载 02-功能测试用例.md，文件名为：需求名称_功能测试用例.md"""
    try:
        task = await TestCaseTask.get_or_none(id=task_id)
    except Exception as exc:
        LOGGER.exception("查询任务失败: %s", exc)
        return FailureResponse(message=f"查询任务失败: {exc}")

    if not task:
        return FailureResponse(message="任务不存在")

    if task.status != "success":
        return FailureResponse(
            message=f"任务状态为「{task.status}」，无法下载测试用例",
        )

    folder_path = task.folder_path
    if not folder_path:
        return FailureResponse(message="任务输出路径为空")

    md_path = Path(folder_path) / "02-功能测试用例.md"
    if not md_path.exists():
        return FailureResponse(message="未找到功能测试用例文件")

    filename = f"{task.requirement_name}_功能测试用例.md" if task.requirement_name else "02-功能测试用例.md"

    return FileResponse(
        path=str(md_path),
        filename=filename,
        media_type="text/markdown; charset=utf-8",
    )


@test_case_router.get("/downloadXlsx", summary="下载测试用例 XLSX")
async def download_test_cases_xlsx(
    background_tasks: BackgroundTasks,
    task_id: int = Query(..., alias="taskId"),
):
    """根据 task_id 查询对应输出目录下的 02-功能测试用例.md，转换为 XLSX 后返回下载。"""
    try:
        task = await TestCaseTask.get_or_none(id=task_id)
    except Exception as exc:
        LOGGER.exception("查询任务失败: %s", exc)
        return FailureResponse(message=f"查询任务失败: {exc}")

    if not task:
        return FailureResponse(message="任务不存在")

    if task.status != "success":
        return FailureResponse(
            message=f"任务状态为「{task.status}」，无法下载测试用例",
        )

    folder_path = task.folder_path
    if not folder_path:
        return FailureResponse(message="任务输出路径为空")

    md_path = Path(folder_path) / "02-功能测试用例.md"
    if not md_path.exists():
        return FailureResponse(message="未找到功能测试用例文件")

    xlsx_path = md_path.with_suffix(".xlsx.tmp")
    try:
        md_to_xlsx(str(md_path), str(xlsx_path))
    except Exception as exc:
        LOGGER.exception("XLSX 转换失败: %s", exc)
        xlsx_path.unlink(missing_ok=True)
        return FailureResponse(message="xlsx文件转换失败，请下载原始markdown文件")

    background_tasks.add_task(xlsx_path.unlink)

    filename = f"{task.requirement_name}_功能测试用例.xlsx" if task.requirement_name else "测试用例.xlsx"

    return FileResponse(
        path=str(xlsx_path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
