"""应用配置（pydantic-settings）"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote_plus

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self

_BACKEND_PROJECT_ROOT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_BACKEND_PROJECT_CONF: str = os.path.join(_BACKEND_PROJECT_ROOT, ".env")

RAG_SYSTEM_PROMPT = """你是企业知识库智能助手，致力于为员工提供专业、准确、友好的知识咨询服务。

## 回答原则
1. **准确性优先**：严格基于提供的参考资料回答，确保信息准确无误
2. **表达自然**：使用流畅、亲切的语言，避免机械式回复
3. **结构清晰**：适当使用分段、编号、加粗等格式，提升可读性
4. **专业友好**：既要保持专业性，又要让员工感到亲切温暖

## 回答要求
- 如果参考资料中有明确答案，请详细说明，并注明出处
- 如果资料不够完整，请基于常识补充，但需说明哪些是推断内容
- 如涉及具体流程或制度，请按步骤清晰说明
- 适当使用"建议您"、"请注意"、"温馨提示"等友好表达

## 参考资料
{context}"""

RAG_USER_PROMPT = "{question}"


class ProjectConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_PROJECT_CONF,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 项目描述
    APP_VERSION: str = "3.0.0"
    APP_TITLE: str = "企业级RAG问答系统"
    APP_DESCRIPTION: str = "支持多用户、知识库管理、模型配置的智能问答系统"

    # 安全认证配置
    AUTH_SECRET_KEY: str = Field(
        default=(
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        ),
        validation_alias=AliasChoices("AUTH_SECRET_KEY", "SECRET_KEY"),
        description="JWT 密钥，建议: openssl rand -hex 32",
    )
    AUTH_JWT_ALGORITHM: str = Field(
        default="HS256",
        validation_alias=AliasChoices("AUTH_JWT_ALGORITHM", "ALGORITHM"),
    )
    AUTH_JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        validation_alias=AliasChoices(
            "AUTH_JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
            "ACCESS_TOKEN_EXPIRE_MINUTES",
        ),
    )

    # 项目路径
    BACKEND_PROJECT_ROOT: str = _BACKEND_PROJECT_ROOT
    APPLICATIONS_DIR: str = os.path.abspath(
        os.path.join(_BACKEND_PROJECT_ROOT, "applications")
    )
    CONFIGURE_DIR: str = os.path.abspath(os.path.join(_BACKEND_PROJECT_ROOT, "configure"))
    CORE_DIR: str = os.path.abspath(os.path.join(_BACKEND_PROJECT_ROOT, "core"))
    OUTPUT_DIR: str = os.path.abspath(os.path.join(_BACKEND_PROJECT_ROOT, "output"))
    MIGRATION_DIR: str = os.path.abspath(os.path.join(_BACKEND_PROJECT_ROOT, "migrations"))
    SERVICES_DIR: str = os.path.abspath(os.path.join(_BACKEND_PROJECT_ROOT, "services"))
    UPLOAD_DIR: str = os.path.abspath(os.path.join(_BACKEND_PROJECT_ROOT, "uploads"))
    DATA_DIR: str = os.path.abspath(os.path.join(_BACKEND_PROJECT_ROOT, "output", "data"))
    CHROMA_DIR: str = os.path.abspath(os.path.join(_BACKEND_PROJECT_ROOT, "core", "chroma_db"))
    RAG_DB_DIR: str = os.path.abspath(os.path.join(_BACKEND_PROJECT_ROOT, "core", "rag_db"))

    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # 数据库
    DB_TYPE: str = Field(default="sqlite", description="sqlite 或 mysql")
    DATABASE_URL: str = Field(default="", description="数据库连接地址（自动生成）")
    DATABASE_CONNECTIONS: Dict[str, Any] = Field(default_factory=dict)
    DATABASE_HOST: str = Field(
        default="localhost",
        validation_alias=AliasChoices("DATABASE_HOST", "MYSQL_HOST"),
    )
    DATABASE_PORT: str = Field(
        default="3306",
        validation_alias=AliasChoices("DATABASE_PORT", "MYSQL_PORT"),
    )
    DATABASE_NAME: str = Field(
        default="rag_system",
        validation_alias=AliasChoices("DATABASE_NAME", "MYSQL_DATABASE"),
    )
    DATABASE_USERNAME: str = Field(
        default="rag_user",
        validation_alias=AliasChoices("DATABASE_USERNAME", "MYSQL_USER"),
    )
    DATABASE_PASSWORD: str = Field(
        default="password",
        validation_alias=AliasChoices("DATABASE_PASSWORD", "MYSQL_PASSWORD"),
    )

    # ChromaDB
    CHROMA_COLLECTION: str = "knowledge_base"

    # LLM
    LLM_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_API_KEY", "DASHSCOPE_API_KEY"),
    )
    LLM_BASE_URL: str = Field(
        default="https://api.deepseek.com/v1",
        validation_alias=AliasChoices("LLM_BASE_URL", "DASHSCOPE_BASE_URL"),
    )
    DEFAULT_LLM_MODEL: str = "deepseek-chat"

    # Embedding
    EMBEDDING_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("EMBEDDING_API_KEY", "SILICONFLOW_API_KEY"),
    )
    EMBEDDING_BASE_URL: str = Field(
        default="https://api.siliconflow.cn/v1",
        validation_alias=AliasChoices("EMBEDDING_BASE_URL", "SILICONFLOW_BASE_URL"),
    )
    DEFAULT_EMBEDDING_MODEL: str = "BAAI/bge-large-zh-v1.5"

    # RAG
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
    RETRIEVAL_TOP_K: int = 5

    # Tortoise ORM / Aerich（自动生成）
    TORTOISE_ORM: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_env_and_assemble(self) -> Self:
        if not self.AUTH_SECRET_KEY or len(self.AUTH_SECRET_KEY) < 64:
            raise ValueError("AUTH_SECRET_KEY 配置为空或长度少于64位，请检查 .env 文件或环境变量")

        if self.DB_TYPE == "mysql":
            for field_name in (
                "DATABASE_USERNAME",
                "DATABASE_HOST",
                "DATABASE_PORT",
                "DATABASE_NAME",
            ):
                if not getattr(self, field_name):
                    raise ValueError(f"{field_name} 配置为空，请检查 .env 文件或环境变量")

        Path(self.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.DATA_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.CHROMA_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.RAG_DB_DIR).mkdir(parents=True, exist_ok=True)

        return self.assemble_connection_urls()

    def assemble_connection_urls(self) -> Self:
        if self.DB_TYPE == "mysql":
            db_user = quote_plus(self.DATABASE_USERNAME)
            db_password = quote_plus(self.DATABASE_PASSWORD)
            self.DATABASE_URL = (
                f"mysql://{db_user}:{db_password}@{self.DATABASE_HOST}:"
                f"{self.DATABASE_PORT}/{self.DATABASE_NAME}"
            )
        else:
            db_path = Path(self.RAG_DB_DIR) / "rag_system.db"
            self.DATABASE_URL = f"sqlite://{db_path}"

        self.TORTOISE_ORM = {
            "connections": {"default": self.DATABASE_URL},
            "apps": {
                "models": {
                    "models": ["backend.applications.base.models", "aerich.models"],
                    "default_connection": "default",
                },
            },
            "use_tz": False,
            "timezone": "Asia/Shanghai",
        }
        return self

    @property
    def upload_path(self) -> Path:
        return Path(self.UPLOAD_DIR)

    @property
    def data_path(self) -> Path:
        return Path(self.DATA_DIR)

    @property
    def chroma_path(self) -> Path:
        return Path(self.CHROMA_DIR)


@lru_cache(maxsize=1)
def get_project_config() -> ProjectConfig:
    return ProjectConfig()


PROJECT_CONFIG = get_project_config()
TORTOISE_ORM = PROJECT_CONFIG.TORTOISE_ORM
