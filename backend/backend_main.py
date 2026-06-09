# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : backend_main.py
@DateTime: 2025/1/12 19:41
"""
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
        reload=PROJECT_CONFIG.SERVER_DEBUG,
        reload_delay=PROJECT_CONFIG.SERVER_DELAY,
        log_config=None,
        log_level=None,
    )

    # Tortoise-ORM 1.x 迁移命令参考（通过 tortoise CLI 执行）
    # =====================================================
    # 前置条件：在项目根目录执行，并设置 PYTHONPATH
    #   export PYTHONPATH=./backend:.
    #
    # 完整命令格式：
    #   PYTHONPATH=./backend:. python -m tortoise -c backend.configure.project_config.TORTOISE_ORM <command>
    #
    # 常用命令：
    #   init models                    # 初始化迁移目录（每个 app 只需执行一次）
    #   makemigrations models          # 根据模型变更生成迁移文件
    #   migrate models                 # 应用所有待执行的迁移到数据库
    #   migrate models --fake          # 标记迁移已执行，但不实际运行 SQL（用于已存在的表）
    #   downgrade models <migration>   # 回滚到指定迁移版本
    #   history models                 # 查看已应用的迁移历史
    #   heads models                   # 查看待执行的迁移文件
    #   sqlmigrate models <migration>  # 预览指定迁移的 SQL（不执行）
    #
    # 迁移文件位置：
    #   backend/applications/<app>/models/migrations/
    #
    # 重要限制：
    #   模型字段的 default 参数不能使用 lambda，必须使用模块级函数。
    #   错误示例：default=lambda: str(uuid.uuid4())
    #   正确示例：定义 def _uuid_str(): return str(uuid.uuid4())，然后使用 default=_uuid_str

