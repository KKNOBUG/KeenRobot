# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : dependencies.py
@DateTime: 2025/6/7
"""
from backend.applications.base.services.audit_crud import AuditCrud
from backend.applications.base.services.menu_crud import MenuCrud
from backend.applications.base.services.role_crud import RoleCrud
from backend.applications.base.services.router_crud import RouterCrud


async def get_audit_crud() -> AuditCrud:
    """获取审计日志 CRUD 服务实例"""
    return AuditCrud()


async def get_menu_crud() -> MenuCrud:
    """获取菜单 CRUD 服务实例"""
    return MenuCrud()


async def get_role_crud() -> RoleCrud:
    """获取角色 CRUD 服务实例"""
    return RoleCrud()


async def get_router_crud() -> RouterCrud:
    """获取路由 CRUD 服务实例"""
    return RouterCrud()
