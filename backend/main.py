"""FastAPI 应用入口"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.configure.config import PROJECT_CONFIG
from backend.applications.base.database import init_db, close_db
from backend.applications.base.views.router_view import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title=PROJECT_CONFIG.APP_TITLE,
    description=PROJECT_CONFIG.APP_DESCRIPTION,
    version=PROJECT_CONFIG.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=PROJECT_CONFIG.CORS_ORIGINS,
    allow_credentials=PROJECT_CONFIG.CORS_ALLOW_CREDENTIALS,
    allow_methods=PROJECT_CONFIG.CORS_ALLOW_METHODS,
    allow_headers=PROJECT_CONFIG.CORS_ALLOW_HEADERS,
)

app.include_router(api_router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": PROJECT_CONFIG.APP_VERSION, "orm": "tortoise-orm"}


def start():
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    """
    # 1. 安装新依赖
    pip install -r requirements.txt
    
    # 2. 初始化 Aerich（首次）
    aerich init -t app.core.config.TORTOISE_ORM
    aerich init-db
    
    # 若已有 MySQL 表结构，可跳过 init-db，直接：
    # aerich migrate --name init
    # aerich upgrade
    
    # 3. 初始化数据
    python scripts/init_admin.py
    python scripts/init_model_configs.py
    
    # 4. 启动
    uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
    """
    start()
