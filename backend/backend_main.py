# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : backend_main.py
@DateTime: 2025/1/12 19:41
"""
import warnings


def _suppress_upstream_deprecation_warnings() -> None:
    """屏蔽 fastmcp/authlib 与 uvicorn/websockets 的上游弃用告警（非本项目代码）。"""
    try:
        # 先触发 authlib 的 always filter，再用 ignore 覆盖（见 authlib.deprecate）
        from authlib.deprecate import AuthlibDeprecationWarning

        warnings.filterwarnings("ignore", category=AuthlibDeprecationWarning)
    except ImportError:
        warnings.filterwarnings("ignore", message=r"authlib\.jose module is deprecated")

    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        module=r"websockets(\..*)?$",
    )
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        module=r"uvicorn\.protocols\.websockets",
    )


_suppress_upstream_deprecation_warnings()

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute
from tortoise import Tortoise
from tortoise.exceptions import DBConnectionError

from backend.core.initializations import (
    register_database,
    register_exceptions,
    register_middlewares,
    register_routers,
    init_database_table,
)
from backend.core.responses import SuccessResponse

try:
    from backend.configure import PROJECT_CONFIG, ROUTER_SUMMARY, ROUTER_TAGS
except ImportError:
    from backend.core.exceptions import NotImplementedException

    raise NotImplementedException(message="导入依赖配置失败,请检查 configure.project_config.py 文件")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await register_database(app)
    except DBConnectionError as e:
        raise RuntimeError(f"数据库连接失败, 请检查主机地址是否可达: {e}")
    await init_database_table(app)

    for route in app.routes:
        if isinstance(route, APIRoute):
            ROUTER_SUMMARY[route.path] = route.summary
            ROUTER_TAGS[route.path] = route.tags

    yield

    await Tortoise.close_connections()


app = FastAPI(
    title=PROJECT_CONFIG.APP_TITLE,
    description=PROJECT_CONFIG.APP_DESCRIPTION,
    version=PROJECT_CONFIG.APP_VERSION,
    docs_url=PROJECT_CONFIG.APP_DOCS_URL,
    redoc_url=PROJECT_CONFIG.APP_REDOC_URL,
    openapi_url=PROJECT_CONFIG.APP_OPENAPI_URL,
    debug=PROJECT_CONFIG.SERVER_DEBUG,
    lifespan=lifespan,
)

register_exceptions(app)
register_middlewares(app)
register_routers(app)
# fastmcp 等依赖会在 register_routers 中重置 DeprecationWarning 过滤器，需再覆盖一次
_suppress_upstream_deprecation_warnings()


@app.get("/", summary="root")
async def root():
    return SuccessResponse(message="KeenRobot FastAPI Started Successfully!")


@app.get("/health", summary="健康检查")
async def health_check():
    return {"status": "ok", "version": PROJECT_CONFIG.APP_VERSION, "orm": "tortoise-orm"}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        app=PROJECT_CONFIG.SERVER_APP,
        host=PROJECT_CONFIG.SERVER_HOST,
        port=PROJECT_CONFIG.SERVER_PORT,
        # reload=PROJECT_CONFIG.SERVER_DEBUG,
        # reload_delay=PROJECT_CONFIG.SERVER_DELAY,
        # reload_excludes=PROJECT_CONFIG.SERVER_RELOAD_EXCLUDES,
        log_config=None,
        log_level=None,
    )

    # ========== 启动命令（在项目根目录 Krun_副本_new 下执行，且保证 PYTHONPATH 含 backend 所在目录）==========
    # Worker（消费 default + autotest_queue）：
    #   Windows（单线程）：celery -A backend.celery_scheduler.celery_worker worker -Q default,autotest_queue --pool=solo -l INFO
    #   Linux：          celery -A backend.celery_scheduler.celery_worker worker -Q default,autotest_queue -c 4 -l INFO
    # Beat（定时下发 scan_and_dispatch_autotest_tasks，必须单独起一个进程）：
    #   celery -A backend.celery_scheduler.celery_worker beat -l INFO