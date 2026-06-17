# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : __init__.py
@DateTime: 2025/1/12 19:42
"""
from fastapi import APIRouter

from .audit_view import audit
from .auth_view import auth_public, auth_secure
from .menu_view import menu
from .role_view import role
from .router_view import router

base_public = APIRouter()
base_secure = APIRouter()
router_secure = APIRouter()
menu_secure = APIRouter()
role_secure = APIRouter()
audit_secure = APIRouter()

base_public.include_router(auth_public, prefix="/auth")
base_secure.include_router(auth_secure, prefix="/auth")
router_secure.include_router(router, prefix="/router")
menu_secure.include_router(menu, prefix="/menu")
role_secure.include_router(role, prefix="/role")
audit_secure.include_router(audit, prefix="/audit")
