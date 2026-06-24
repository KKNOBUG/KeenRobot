# -*- coding: utf-8 -*-
"""
@Author  : yangkai
@Email   : 807440781@qq.com
@Project : KeenRobot
@Module  : data_initialization.py
@DateTime: 2025/2/19 22:12
"""
from typing import List

from fastapi import FastAPI
from tortoise.expressions import Q

from backend.applications.base.models.menu_model import Menu
from backend.applications.base.models.role_model import Role
from backend.applications.base.models.router_model import Router
from backend.applications.base.schemas.menu_schema import MenuCreate
from backend.applications.base.schemas.role_schema import RoleCreate
from backend.applications.base.services.menu_crud import MenuCrud
from backend.applications.base.services.role_crud import RoleCrud
from backend.applications.base.services.router_crud import RouterCrud
from backend.applications.example.services.init_data import init_example_data
from backend.applications.user.schemas.user_schema import UserCreate
from backend.applications.user.services.user_crud import UserCrud
from backend.configure import LOGGER
from backend.enums import MenuType


async def init_database_menu():
    menu_crud = MenuCrud()
    menu_table = await menu_crud.model.exists()
    if menu_table:
        LOGGER.info("[菜单]数据表已存在，跳过初始化")
        return

    ai_parent_menu = await menu_crud.create_menu(
        MenuCreate(
            menu_type=MenuType.CATALOG,
            name="AI管理",
            path="/ai-manage",
            order=2,
            parent_id=0,
            icon="mdi:robot-outline",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/ai-manage/chat",
        )
    )
    ai_children_menu = [
        Menu(
            menu_type=MenuType.MENU,
            name="智能聊天",
            path="chat",
            order=1,
            parent_id=ai_parent_menu.id,
            icon="mdi:chat-outline",
            is_hidden=False,
            component="/chat",
            keepalive=True,
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="知识库管理",
            path="knowledge-base",
            order=2,
            parent_id=ai_parent_menu.id,
            icon="mdi:book-open-outline",
            is_hidden=False,
            component="/knowledge-base",
            keepalive=True,
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="模型管理",
            path="model",
            order=3,
            parent_id=ai_parent_menu.id,
            icon="mdi:brain",
            is_hidden=False,
            component="/ai-manage/model",
            keepalive=True,
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="MCP管理",
            path="mcp",
            order=4,
            parent_id=ai_parent_menu.id,
            icon="mdi:connection",
            is_hidden=False,
            component="/ai-manage/mcp",
            keepalive=True,
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="Skills管理",
            path="skills",
            order=5,
            parent_id=ai_parent_menu.id,
            icon="mdi:puzzle-outline",
            is_hidden=False,
            component="/ai-manage/skills",
            keepalive=True,
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="任务中心",
            path="task-center",
            order=6,
            parent_id=ai_parent_menu.id,
            icon="mdi:clock-outline",
            is_hidden=False,
            component="/ai-manage/task-center",
            keepalive=True,
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="执行记录",
            path="skill-runs",
            order=8,
            parent_id=ai_parent_menu.id,
            icon="mdi:square-wave",
            is_hidden=False,
            component="/ai-manage/skill-runs",
            keepalive=True,
        ),
    ]
    await Menu.bulk_create(ai_children_menu)
    LOGGER.info("创建[AI管理]目录及子菜单成功")

    system_parent_menu = await menu_crud.create_menu(
        MenuCreate(
            menu_type=MenuType.CATALOG,
            name="系统管理",
            path="/system",
            order=3,
            parent_id=0,
            icon="garden:gear-stroke-12",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/system/user",
        )
    )
    system_children_menu = [
        Menu(
            menu_type=MenuType.MENU,
            name="用户管理",
            path="user",
            order=1,
            parent_id=system_parent_menu.id,
            icon="tdesign:user-setting",
            is_hidden=False,
            component="/system/user",
            keepalive=False,
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="角色管理",
            path="role",
            order=2,
            parent_id=system_parent_menu.id,
            icon="tdesign:user-transmit",
            is_hidden=False,
            component="/system/role",
            keepalive=False,
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="菜单管理",
            path="menu",
            order=3,
            parent_id=system_parent_menu.id,
            icon="fluent:text-grammar-settings-24-filled",
            is_hidden=False,
            component="/system/menu",
            keepalive=False,
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="路由管理",
            path="router",
            order=4,
            parent_id=system_parent_menu.id,
            icon="carbon:data-vis-1",
            is_hidden=False,
            component="/system/router",
            keepalive=False,
        ),
        Menu(
            menu_type=MenuType.MENU,
            name="审计日志",
            path="auditlog",
            order=5,
            parent_id=system_parent_menu.id,
            icon="carbon:flow-logs-vpc",
            is_hidden=False,
            component="/system/auditlog",
            keepalive=False,
        ),
    ]
    await Menu.bulk_create(system_children_menu)
    LOGGER.info("创建[系统管理]目录及子菜单成功")


async def init_database_router(app: FastAPI):
    router_crud = RouterCrud()
    router_table = await router_crud.model.exists()
    if router_table:
        LOGGER.info("[路由]数据表已存在，跳过初始化")
        return
    await router_crud.refresh_router(app)


async def init_database_role():
    role_crud = RoleCrud()
    role_table = await role_crud.model.exists()
    if role_table:
        LOGGER.info("[角色]数据表已存在，跳过初始化")
        return

    admin_role = await role_crud.create_role(
        RoleCreate(
            code="ROLE-9999",
            name="超级用户",
            description="超级用户角色",
        )
    )
    normal_role = await role_crud.create_role(
        RoleCreate(
            code="ROLE-1001",
            name="普通用户",
            description="普通用户角色",
        )
    )
    LOGGER.info(f"创建[超级用户]角色成功: {admin_role.name} (id: {admin_role.id})")
    LOGGER.info(f"创建[普通用户]角色成功: {normal_role.name} (id: {normal_role.id})")

    all_routers = await Router.all()
    if all_routers:
        await admin_role.routers.add(*all_routers)
        LOGGER.info(f"角色[超级用户]绑定路由成功, 共计{len(all_routers)}个")

        basic_routers = await Router.filter(Q(method__in=["GET"]) | Q(tags__icontains="基础"))
        if basic_routers:
            await normal_role.routers.add(*basic_routers)
            LOGGER.info(f"角色[普通用户]绑定路由成功, 共计{len(basic_routers)}个")

    all_menus = await Menu.all()
    if all_menus:
        await admin_role.menus.add(*all_menus)
        await normal_role.menus.add(*all_menus)
        LOGGER.info(f"角色绑定菜单成功, 共计{len(all_menus)}个")


async def init_database_users_with_roles():
    user_crud = UserCrud()
    user_table = await user_crud.model.exists()
    if user_table:
        LOGGER.info("[用户]数据表已存在，跳过初始化")
        return

    user_data: List[UserCreate] = [
        UserCreate(
            username="admin",
            password="123456",
            alias="系统管理员",
            email="admin@test.com",
            phone="18888888888",
            avatar="/static/avatar/default/20250101010101.png",
            is_active=True,
            is_superuser=True,
            role_ids=[1],
        ),
        UserCreate(
            username="guest",
            password="123456",
            alias="访客用户",
            email="guest@test.com",
            phone="18888888889",
            avatar="/static/avatar/default/20250101010101.png",
            is_active=True,
            is_superuser=False,
            role_ids=[2],
        ),
    ]
    for user_in in user_data:
        try:
            user = await user_crud.create_user(user_in=user_in)
            LOGGER.info(f"创建用户成功: {user.alias} (id: {user.id}, username: {user.username})")
        except Exception as e:
            LOGGER.error(f"创建用户失败: {user_in.alias}, username: {user_in.username}: {e}")


async def init_database_table(app: FastAPI):
    await init_database_menu()
    await init_database_router(app)
    await init_database_role()
    await init_database_users_with_roles()
    await init_example_data()
