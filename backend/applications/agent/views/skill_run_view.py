# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : skill_run_view.py
"""
import json
import traceback

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from backend.applications.agent.dependencies import get_skill_run_crud
from backend.applications.agent.schemas.skill_run_schema import (
    SkillRunCleanupQuery,
    SkillRunCleanupResult,
    SkillRunCreate,
    SkillRunFileUploadResult,
    SkillRunInputsUpdate,
    SkillRunOut,
    SkillRunRetryResult,
    SkillRunStart,
    SkillRunStartResult,
    SkillRunValidateResult,
)
from backend.applications.agent.services.skill_run_crud import SkillRunCrud
from backend.applications.agent.services.skill_run_events import SkillRunEventHub
from backend.applications.agent.services.workspace_service import WorkspaceService
from backend.applications.user.models.user_model import User
from backend.configure import LOGGER
from backend.core.exceptions import NotFoundException, ParameterException
from backend.core.responses import FailureResponse, NotFoundResponse, SuccessResponse
from backend.services import DependAuth

skill_runs = APIRouter()


@skill_runs.post("/", summary="SkillRun-创建执行任务")
async def create_skill_run(
        data: SkillRunCreate,
        current_user: User = DependAuth,
        run_crud: SkillRunCrud = Depends(get_skill_run_crud),
):
    try:
        run = await run_crud.create_run(current_user, data)
        skill = await run_crud._get_skill(run)
        out = SkillRunOut.model_validate(run_crud.run_to_out(run, skill))
        return SuccessResponse(data=out.model_dump())
    except (NotFoundException, ParameterException) as e:
        return FailureResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"创建 Skill Run 失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"创建失败: {e}")


@skill_runs.get("/search", summary="SkillRun-执行记录列表")
async def search_skill_runs(
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=10, ge=1, le=100),
        skill_id: str = Query(default=None),
        status: str = Query(default=None),
        conversation_id: str = Query(default=None),
        current_user: User = DependAuth,
        run_crud: SkillRunCrud = Depends(get_skill_run_crud),
):
    try:
        total, items = await run_crud.list_runs(
            current_user,
            page=page,
            page_size=page_size,
            skill_id=skill_id,
            status=status,
            conversation_id=conversation_id,
        )
        data = [
            SkillRunOut.model_validate(run_crud.run_to_out(item)).model_dump()
            for item in items
        ]
        return SuccessResponse(data=data, total=total)
    except Exception as e:
        LOGGER.error(f"查询 Skill Run 列表失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败: {e}")


@skill_runs.post("/cleanup", summary="SkillRun-清理过期执行记录")
async def cleanup_skill_runs(
        data: SkillRunCleanupQuery,
        current_user: User = DependAuth,
        run_crud: SkillRunCrud = Depends(get_skill_run_crud),
):
    try:
        result = await run_crud.cleanup_runs(
            current_user,
            days=data.days,
            dry_run=data.dry_run,
        )
        out = SkillRunCleanupResult.model_validate(result)
        msg = (
            f"预览：{out.scanned} 条可清理"
            if out.dry_run
            else f"已清理 {out.deleted} 条（扫描 {out.scanned} 条）"
        )
        return SuccessResponse(data=out.model_dump(), message=msg)
    except Exception as e:
        LOGGER.error(f"清理 Skill Run 失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"清理失败: {e}")


@skill_runs.get("/{run_id}", summary="SkillRun-详情")
async def get_skill_run(
        run_id: str,
        current_user: User = DependAuth,
        run_crud: SkillRunCrud = Depends(get_skill_run_crud),
):
    try:
        run = await run_crud.get_run(run_id, current_user)
        skill = await run_crud._get_skill(run)
        out = SkillRunOut.model_validate(run_crud.run_to_out(run, skill))
        return SuccessResponse(data=out.model_dump())
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"查询 Skill Run 详情失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败: {e}")


@skill_runs.post("/{run_id}/inputs", summary="SkillRun-保存文本/选择类输入")
async def save_skill_run_inputs(
        run_id: str,
        data: SkillRunInputsUpdate,
        current_user: User = DependAuth,
        run_crud: SkillRunCrud = Depends(get_skill_run_crud),
):
    try:
        run = await run_crud.save_inputs(run_id, current_user, data.fields)
        skill = await run_crud._get_skill(run)
        out = SkillRunOut.model_validate(run_crud.run_to_out(run, skill))
        return SuccessResponse(data=out.model_dump())
    except (NotFoundException, ParameterException) as e:
        return FailureResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"保存 Skill Run 输入失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"保存失败: {e}")


@skill_runs.post("/{run_id}/files", summary="SkillRun-上传文件")
async def upload_skill_run_file(
        run_id: str,
        key: str = Form(..., description="wizard_steps 中的 key"),
        file: UploadFile = File(...),
        current_user: User = DependAuth,
        run_crud: SkillRunCrud = Depends(get_skill_run_crud),
):
    try:
        run, path, size = await run_crud.save_upload(run_id, current_user, key, file)
        result = SkillRunFileUploadResult(key=key, path=path, size=size)
        return SuccessResponse(data=result.model_dump())
    except (NotFoundException, ParameterException, ValueError) as e:
        return FailureResponse(message=str(getattr(e, "message", e)))
    except Exception as e:
        LOGGER.error(f"上传 Skill Run 文件失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"上传失败: {e}")


@skill_runs.post("/{run_id}/validate", summary="SkillRun-校验输入")
async def validate_skill_run(
        run_id: str,
        current_user: User = DependAuth,
        run_crud: SkillRunCrud = Depends(get_skill_run_crud),
):
    try:
        result = await run_crud.validate_run(run_id, current_user)
        out = SkillRunValidateResult.model_validate(result)
        return SuccessResponse(data=out.model_dump())
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"校验 Skill Run 失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"校验失败: {e}")


@skill_runs.post("/{run_id}/start", summary="SkillRun-启动执行")
async def start_skill_run(
        run_id: str,
        data: SkillRunStart | None = None,
        current_user: User = DependAuth,
        run_crud: SkillRunCrud = Depends(get_skill_run_crud),
):
    try:
        payload = data or SkillRunStart()
        run, mode, is_async = await run_crud.start_run(
            run_id, current_user, payload.question
        )
        result = SkillRunStartResult(
            run_id=run.id,
            status=run.status,
            mode=mode,
            async_execution=is_async,
        )
        message = "已提交异步任务" if is_async else "Run 已启动，请连接 stream 获取进度"
        return SuccessResponse(data=result.model_dump(), message=message)
    except (NotFoundException, ParameterException) as e:
        return FailureResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"启动 Skill Run 失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"启动失败: {e}")


@skill_runs.get("/{run_id}/stream", summary="SkillRun-执行进度 SSE")
async def stream_skill_run(
        run_id: str,
        current_user: User = DependAuth,
        run_crud: SkillRunCrud = Depends(get_skill_run_crud),
):
    try:
        run = await run_crud.get_run(run_id, current_user)
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)

    if (run.interaction_mode or "").lower() == "async_job":
        return FailureResponse(message="async_job 模式请轮询 Run 详情，不支持 SSE")

    async def event_generator():
        process_trace = []
        yield {
            "event": "meta",
            "data": json.dumps({"type": "meta", "run_id": run_id, "status": run.status}),
        }
        queue = SkillRunEventHub.get_queue(run_id)
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                if item.get("type") == "meta":
                    yield {"event": "meta", "data": json.dumps(item)}
                elif item.get("type") == "reasoning":
                    yield {
                        "event": "reasoning",
                        "data": json.dumps(item),
                    }
                elif item.get("type") == "content":
                    yield {
                        "event": "token",
                        "data": json.dumps({"type": "token", "content": item.get("content", "")}),
                    }
                elif item.get("type") == "process":
                    step = item.get("step") or {}
                    replaced = False
                    for idx, existing in enumerate(process_trace):
                        if (
                            existing.get("type") == "skill"
                            and existing.get("name") == step.get("name")
                            and existing.get("skill_id") == step.get("skill_id")
                        ):
                            process_trace[idx] = step
                            replaced = True
                            break
                    if not replaced:
                        process_trace.append(step)
                    yield {
                        "event": "process",
                        "data": json.dumps({
                            "type": "process",
                            "step": step,
                            "process_trace": process_trace,
                        }),
                    }
                elif item.get("type") == "process_trace":
                    process_trace = item.get("process_trace") or process_trace
                elif item.get("type") == "error":
                    yield {"event": "error", "data": json.dumps(item)}
                    return
                elif item.get("type") == "done":
                    yield {"event": "done", "data": json.dumps(item)}
                    return
                elif item.get("type") == "usage":
                    pass
        except Exception as e:
            LOGGER.error(f"Skill Run SSE 错误: {e}\n{traceback.format_exc()}")
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "message": str(e)}),
            }

    return EventSourceResponse(event_generator())


@skill_runs.post("/{run_id}/cancel", summary="SkillRun-取消执行")
async def cancel_skill_run(
        run_id: str,
        current_user: User = DependAuth,
        run_crud: SkillRunCrud = Depends(get_skill_run_crud),
):
    try:
        run = await run_crud.cancel_run(run_id, current_user)
        skill = await run_crud._get_skill(run)
        out = SkillRunOut.model_validate(run_crud.run_to_out(run, skill))
        return SuccessResponse(data=out.model_dump(), message="已取消")
    except (NotFoundException, ParameterException) as e:
        return FailureResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"取消 Skill Run 失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"取消失败: {e}")


@skill_runs.post("/{run_id}/retry", summary="SkillRun-重试（复制输入创建新 Run）")
async def retry_skill_run(
        run_id: str,
        current_user: User = DependAuth,
        run_crud: SkillRunCrud = Depends(get_skill_run_crud),
):
    try:
        new_run, valid = await run_crud.retry_run(run_id, current_user)
        skill = await run_crud._get_skill(new_run)
        out = SkillRunRetryResult(
            new_run_id=new_run.id,
            source_run_id=run_id,
            status=new_run.status,
            valid=valid,
        )
        run_out = SkillRunOut.model_validate(run_crud.run_to_out(new_run, skill))
        return SuccessResponse(
            data={**out.model_dump(), "run": run_out.model_dump()},
            message="已创建重试 Run" + ("，输入已通过校验" if valid else "，请补全输入后启动"),
        )
    except (NotFoundException, ParameterException) as e:
        return FailureResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"重试 Skill Run 失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"重试失败: {e}")


@skill_runs.delete("/{run_id}", summary="SkillRun-删除记录及工作区")
async def delete_skill_run(
        run_id: str,
        current_user: User = DependAuth,
        run_crud: SkillRunCrud = Depends(get_skill_run_crud),
):
    try:
        await run_crud.delete_run(run_id, current_user)
        return SuccessResponse(message="执行记录已删除")
    except (NotFoundException, ParameterException) as e:
        return FailureResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"删除 Skill Run 失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"删除失败: {e}")


@skill_runs.get("/{run_id}/outputs", summary="SkillRun-产物列表")
async def list_skill_run_outputs(
        run_id: str,
        current_user: User = DependAuth,
        run_crud: SkillRunCrud = Depends(get_skill_run_crud),
):
    try:
        outputs = await run_crud.get_outputs(run_id, current_user)
        return SuccessResponse(data=outputs, total=len(outputs))
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except Exception as e:
        LOGGER.error(f"查询 Skill Run 产物失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"查询失败: {e}")


@skill_runs.get("/{run_id}/outputs/{file_path:path}", summary="SkillRun-下载产物")
async def download_skill_run_output(
        run_id: str,
        file_path: str,
        current_user: User = DependAuth,
        run_crud: SkillRunCrud = Depends(get_skill_run_crud),
):
    try:
        run = await run_crud.get_run(run_id, current_user)
        skill = await run_crud._get_skill(run)
        workspace = WorkspaceService(run)
        _, output_root = workspace.layout_roots(skill.input_schema)
        target = workspace.resolve_safe_path(f"{output_root.rstrip('/')}/{file_path.lstrip('/')}")
        if not target.is_file():
            return NotFoundResponse(message="产物文件不存在")
        return FileResponse(path=str(target), filename=target.name)
    except NotFoundException as e:
        return NotFoundResponse(message=e.message)
    except (ParameterException, ValueError) as e:
        return FailureResponse(message=str(getattr(e, "message", e)))
    except Exception as e:
        LOGGER.error(f"下载 Skill Run 产物失败: {e}\n{traceback.format_exc()}")
        return FailureResponse(message=f"下载失败: {e}")
