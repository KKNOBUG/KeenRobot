# -*- coding: utf-8 -*-
from fastapi import FastAPI

from applications.example.services.init_data import init_example_data
from applications.model_config.services.init_data import init_model_configs
from applications.user.services.init_data import init_database_user


async def init_database_table(app: FastAPI):
    await init_database_user()
    await init_model_configs()
    await init_example_data()
