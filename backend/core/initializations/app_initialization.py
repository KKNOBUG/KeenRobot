# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : app_initialization.py
@DateTime: 2025/1/17 21:55
"""
import os
import sys
import traceback
from typing import Dict, Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from tortoise import Tortoise
from tortoise.exceptions import DoesNotExist

from backend.configure import PROJECT_CONFIG, LOGGER
from backend.core.exceptions.http_exceptions import (
    request_validation_exception_handler,
    response_validation_exception_handler,
    http_exception_handler,
    null_point_exception_handler,
    app_exception_handler,
)
from backend.core.middlewares.app_middleware import logging_middleware
from backend.core.middlewares.auth_middleware import auth_middleware
from backend.core.middlewares.request_context_middleware import request_context_middleware
from backend.services import DependAuth


def build_tortoise_config() -> Dict[str, Any]:
    return {
        "connections": PROJECT_CONFIG.DATABASE_CONNECTIONS,
        "apps": {
            "models": {
                "models": PROJECT_CONFIG.APPLICATIONS_MODELS,
                "default_connection": "default",
            }
        },
        "use_tz": False,
        "timezone": "Asia/Shanghai",
    }


async def register_database(app: FastAPI) -> None:
    """注册数据库并执行迁移。"""
    config = build_tortoise_config()

    migration_path = os.path.join(PROJECT_CONFIG.MIGRATION_DIR, "models")
    if not os.path.exists(migration_path):
        os.makedirs(migration_path)
        open(os.path.join(migration_path, "__init__.py"), "a").close()

    if not Tortoise._inited:
        await Tortoise.init(
            config=config,
            _enable_global_fallback=True,
        )

    if not PROJECT_CONFIG.DATABASE_AUTO_MIGRATION:
        LOGGER.warning(
            "跳过数据库迁移: \n"
            f"操作系统: {PROJECT_CONFIG.SERVER_SYSTEM}, \n"
            f"调试开关: {PROJECT_CONFIG.SERVER_DEBUG}, \n"
            f"迁移开关: {PROJECT_CONFIG.DATABASE_AUTO_MIGRATION}, \n"
            f"生产环境始终执行迁移, 开发环境可关闭。"
        )
        return

    try:
        LOGGER.info("执行数据库迁移...")
        from tortoise.connection import get_connection
        from tortoise.migrations.executor import MigrationExecutor
        
        config_dict = config if isinstance(config, dict) else config.to_dict()
        configured_apps = config_dict.get("apps", {})
        selected_apps = ["models"]
        
        apps_config = {label: configured_apps[label] for label in selected_apps if label in configured_apps}
        apps_by_connection: dict[str, dict[str, dict[str, Any]]] = {}
        for label, app_config in apps_config.items():
            connection_name = app_config.get("default_connection", "default")
            apps_by_connection.setdefault(connection_name, {})[label] = app_config
        
        for connection_name, subset in apps_by_connection.items():
            connection = get_connection(connection_name)
            executor = MigrationExecutor(connection, subset)
            await executor.migrate(None)
        
        LOGGER.info("数据库迁移完成")
    except Exception as e:
        LOGGER.error(f"迁移过程出错: {e}\n错误回溯: {traceback.format_exc()}")
        LOGGER.info("尝试生成数据库表结构...")
        try:
            await Tortoise.generate_schemas(safe=True)
            LOGGER.info("数据库表结构生成完成")
        except Exception as schema_error:
            LOGGER.error(f"生成表结构失败: {schema_error}")
            raise RuntimeError(f"数据库初始化失败: {e}")


# 注册异常处理器
def register_exceptions(app: FastAPI) -> None:
    # 当 FastAPI 在解析和验证请求数据时发现问题，会触发 RequestValidationError 异常
    app.add_exception_handler(
        exc_class_or_status_code=RequestValidationError,
        handler=request_validation_exception_handler
    )
    # 当 FastAPI 在解析和验证响应数据时发现问题，会触发 ResponseValidationError 异常
    app.add_exception_handler(
        exc_class_or_status_code=ResponseValidationError,
        handler=response_validation_exception_handler
    )
    # 当发生 HTTP 相关的异常时，如 403 禁止访问、404 未找到等，会触发 HTTPException 异常
    app.add_exception_handler(
        exc_class_or_status_code=HTTPException,
        handler=http_exception_handler
    )
    # 当使用 Tortoise ORM 进行数据库查询时，如果查询结果为空，会触发 DoesNotExist 异常
    app.add_exception_handler(
        exc_class_or_status_code=DoesNotExist,
        handler=null_point_exception_handler
    )
    # 当发生未被其他特定异常处理器处理的异常时，会触发此函数
    app.add_exception_handler(IOError, app_exception_handler)
    app.add_exception_handler(OSError, app_exception_handler)
    app.add_exception_handler(KeyError, app_exception_handler)
    app.add_exception_handler(ValueError, app_exception_handler)
    app.add_exception_handler(IndexError, app_exception_handler)
    app.add_exception_handler(TypeError, app_exception_handler)
    app.add_exception_handler(MemoryError, app_exception_handler)
    app.add_exception_handler(ImportError, app_exception_handler)
    app.add_exception_handler(TimeoutError, app_exception_handler)
    app.add_exception_handler(RuntimeError, app_exception_handler)
    app.add_exception_handler(AttributeError, app_exception_handler)
    app.add_exception_handler(FileExistsError, app_exception_handler)
    app.add_exception_handler(FileNotFoundError, app_exception_handler)
    app.add_exception_handler(NotADirectoryError, app_exception_handler)
    app.add_exception_handler(DoesNotExist, app_exception_handler)
    app.add_exception_handler(
        exc_class_or_status_code=Exception,
        handler=app_exception_handler
    )


def register_middlewares(app: FastAPI):
    # 注册 CORS 中间件，CORS（跨域资源共享）中间件用于处理跨域请求，允许不同域名的客户端访问服务器资源
    app.add_middleware(
        CORSMiddleware,
        allow_origins=PROJECT_CONFIG.CORS_ORIGINS,
        allow_credentials=PROJECT_CONFIG.CORS_ALLOW_CREDENTIALS,
        allow_methods=PROJECT_CONFIG.CORS_ALLOW_METHODS,
        allow_headers=PROJECT_CONFIG.CORS_ALLOW_HEADERS,
        expose_headers=PROJECT_CONFIG.CORS_EXPOSE_METHODS,
        max_age=PROJECT_CONFIG.CORS_MAX_AGE,
    )
    # 注册 HTTP 请求中间件
    app.middleware('http')(auth_middleware)
    # 先做认证拦截，再做审计日志记录
    app.middleware('http')(logging_middleware)
    # 后做日志追溯链
    app.middleware('http')(request_context_middleware)


def register_routers(app: FastAPI) -> None:
    # 挂载静态文件
    app.mount("/static", StaticFiles(directory=PROJECT_CONFIG.STATIC_DIR), name="static")
    app.openapi_version = PROJECT_CONFIG.APP_OPENAPI_VERSION
    swagger_modules = sys.modules["fastapi.openapi.docs"].get_swagger_ui_html.__kwdefaults__
    swagger_modules["swagger_js_url"] = PROJECT_CONFIG.APP_OPENAPI_JS_URL
    swagger_modules["swagger_css_url"] = PROJECT_CONFIG.APP_OPENAPI_CSS_URL
    swagger_modules["swagger_favicon_url"] = PROJECT_CONFIG.APP_OPENAPI_FAVICON_URL
    redoc_modules = sys.modules["fastapi.openapi.docs"].get_redoc_html.__kwdefaults__
    redoc_modules["redoc_js_url"] = "/static/redoc/bundles/redoc.standalone.js"
    redoc_modules["redoc_favicon_url"] = "/static/redoc/favicon.png"

    # 导入路由蓝图
    from backend.applications.base.views import base_public, base_secure, router_secure, audit_secure
    from backend.applications.user.views import user_public_router, user_secure_router
    from backend.applications.example.views import example_category_router, example_product_router

    # 挂在路由蓝图
    app.include_router(router=base_public, prefix="/base", tags=["基础服务"])
    app.include_router(router=base_secure, prefix="/base", tags=["基础服务"], dependencies=[DependAuth])
    app.include_router(router=audit_secure, prefix="/base", tags=["基础服务-审计模块"], dependencies=[DependAuth])
    app.include_router(router=router_secure, prefix="/base", tags=["基础服务-路由模块"], dependencies=[DependAuth])
    app.include_router(router=user_public_router, prefix="/user", tags=["用户服务"])
    app.include_router(router=user_secure_router, prefix="/user", tags=["用户服务"], dependencies=[DependAuth])
    app.include_router(router=example_category_router, prefix="/example", tags=["示例服务-商品分类"], dependencies=[DependAuth])
    app.include_router(router=example_product_router, prefix="/example", tags=["示例服务-商品模型"], dependencies=[DependAuth])

    from backend.applications.conversation.views import chat_router, history_router
    from backend.applications.knowledge_base.views import knowledge_router
    from backend.applications.model_config.views import model_router

    app.include_router(router=chat_router, prefix="/chat", tags=["RAG-对话"], dependencies=[DependAuth])
    app.include_router(router=history_router, prefix="/conversations", tags=["RAG-对话历史"], dependencies=[DependAuth])
    app.include_router(router=knowledge_router, prefix="/knowledge-bases", tags=["RAG-知识库"], dependencies=[DependAuth])
    app.include_router(router=model_router, prefix="/model-configs", tags=["RAG-模型配置"], dependencies=[DependAuth])
