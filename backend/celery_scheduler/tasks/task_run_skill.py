# -*- coding: utf-8 -*-
"""
@Project : KeenRobot
@Module  : skill_run_task.py
"""
from backend.celery_scheduler.celery_worker import celery
from backend.configure import LOGGER


@celery.task(name="backend.celery_scheduler.tasks.skill_run_task.execute_skill_run_async")
def execute_skill_run_async(run_id: str, user_id: int, question: str = None):
    from backend.celery_scheduler.celery_base import run_async
    from backend.applications.agent.services.skill_run_executor import execute_skill_run

    LOGGER.info(f"【SkillRun】Celery 异步执行开始: run_id={run_id}")
    run_async(execute_skill_run(run_id, user_id, question, publish_events=False))
    LOGGER.info(f"【SkillRun】Celery 异步执行结束: run_id={run_id}")


@celery.task(name="backend.celery_scheduler.tasks.skill_run_task.cleanup_expired_skill_runs")
def cleanup_expired_skill_runs():
    """清理所有用户超过保留期的终态 Skill Run（可由 Celery Beat 定时触发）。"""
    from backend.celery_scheduler.celery_base import run_async
    from backend.applications.agent.services.skill_run_crud import SkillRunCrud
    from backend.applications.user.models.user_model import User
    from backend.configure import PROJECT_CONFIG

    async def _cleanup():
        crud = SkillRunCrud()
        users = await User.filter(state__not=1)
        total_scanned = 0
        total_deleted = 0
        for user in users:
            result = await crud.cleanup_runs(user, dry_run=False)
            total_scanned += result.get("scanned", 0)
            total_deleted += result.get("deleted", 0)
        return {
            "scanned": total_scanned,
            "deleted": total_deleted,
            "retention_days": PROJECT_CONFIG.SKILL_RUN_RETENTION_DAYS,
        }

    result = run_async(_cleanup())
    LOGGER.info(f"【SkillRun】定时清理完成: {result}")
    return result
