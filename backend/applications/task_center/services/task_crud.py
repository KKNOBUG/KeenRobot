# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : task_crud
"""
import traceback
from typing import Any, Dict, Optional

from tortoise.exceptions import DoesNotExist, FieldError, IntegrityError
from tortoise.expressions import Q

from backend.applications.task_center.models.task_center_model import TaskCenterInfo
from backend.applications.task_center.schemas.task_schema import TaskCenterCreate, TaskCenterUpdate
from backend.applications.base.services.scaffold import ScaffoldCrud
from backend.configure import LOGGER
from backend.core.exceptions import (
    DataAlreadyExistsException,
    DataBaseStorageException,
    NotFoundException,
    ParameterException,
)


class TaskCenterCrud(ScaffoldCrud[TaskCenterInfo, TaskCenterCreate, TaskCenterUpdate]):
    def __init__(self):
        super().__init__(model=TaskCenterInfo)

    async def get_by_id(self, task_id: int, on_error: bool = False, **kwargs) -> Optional[TaskCenterInfo]:
        if not task_id:
            raise ParameterException(message="查询任务失败, 参数 task_id 不允许为空")
        instance = await self.get_or_none(id=task_id, **kwargs)
        if not instance and on_error:
            raise NotFoundException(message=f"任务(id={task_id})不存在")
        return instance

    async def get_by_code(self, task_code: str, on_error: bool = False, **kwargs) -> Optional[TaskCenterInfo]:
        if not task_code:
            raise ParameterException(message="查询任务失败, 参数 task_code 不允许为空")
        instance = await self.model.filter(task_code=task_code, **kwargs).first()
        if not instance and on_error:
            raise NotFoundException(message=f"任务(code={task_code})不存在")
        return instance

    async def create_task(self, task_in: TaskCenterCreate) -> TaskCenterInfo:
        existing = await self.model.filter(task_name=task_in.task_name, state__not=1).first()
        if existing:
            raise DataAlreadyExistsException(message=f"任务名称已存在: {task_in.task_name}")
        try:
            task_dict: Dict[str, Any] = task_in.model_dump(exclude_none=True, exclude_unset=True)
            if "task_scheduler" in task_dict and task_dict["task_scheduler"] is not None:
                task_dict["task_scheduler"] = task_dict["task_scheduler"].value
            if "last_execute_state" in task_dict and task_dict["last_execute_state"] is not None:
                task_dict["last_execute_state"] = task_dict["last_execute_state"].value
            return await self.create(task_dict)
        except IntegrityError as e:
            LOGGER.error(f"新增任务失败: {e}\n{traceback.format_exc()}")
            raise DataBaseStorageException(message=f"新增任务失败: {e}") from e

    async def update_task(self, task_in: TaskCenterUpdate) -> TaskCenterInfo:
        task_id = task_in.task_id
        task_code = task_in.task_code
        if task_id:
            instance = await self.get_by_id(task_id=task_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(task_code=task_code, on_error=True, state__not=1)
            task_id = instance.id

        update_dict: Dict[str, Any] = task_in.model_dump(
            exclude_none=True,
            exclude_unset=True,
            exclude={"task_id", "task_code"},
        )
        if "task_scheduler" in update_dict and update_dict["task_scheduler"] is not None:
            update_dict["task_scheduler"] = update_dict["task_scheduler"].value
        if "last_execute_state" in update_dict and update_dict["last_execute_state"] is not None:
            update_dict["last_execute_state"] = update_dict["last_execute_state"].value

        task_name = update_dict.get("task_name", instance.task_name)
        existing = await self.model.filter(task_name=task_name, state__not=1).exclude(id=task_id).first()
        if existing:
            raise DataAlreadyExistsException(message=f"任务名称已存在: {task_name}")

        try:
            return await self.update(id=task_id, obj_in=update_dict)
        except DoesNotExist as e:
            raise NotFoundException(message=f"任务(id={task_id})不存在") from e
        except IntegrityError as e:
            raise DataBaseStorageException(message=f"更新任务失败: {e}") from e

    async def delete_task(self, task_id: Optional[int] = None, task_code: Optional[str] = None) -> TaskCenterInfo:
        if task_id:
            instance = await self.get_by_id(task_id=task_id, on_error=True, state__not=1)
        else:
            instance = await self.get_by_code(task_code=task_code, on_error=True, state__not=1)
        instance.state = 1
        instance.task_enabled = False
        await instance.save()
        return instance

    async def set_task_enabled(self, task_id: int, enabled: bool = True) -> TaskCenterInfo:
        instance = await self.get_by_id(task_id=task_id, on_error=True, state__not=1)
        instance.task_enabled = enabled
        await instance.save(update_fields=["task_enabled"])
        return instance

    async def select_tasks(self, search: Q, page: int, page_size: int, order: list) -> tuple:
        try:
            return await self.list(page=page, page_size=page_size, search=search, order=order)
        except FieldError as e:
            raise ParameterException(message=f"查询任务失败: {e}") from e
