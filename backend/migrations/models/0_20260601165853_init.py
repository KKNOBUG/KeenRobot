from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "users" (
    "id" VARCHAR(36) NOT NULL PRIMARY KEY,
    "username" VARCHAR(50) NOT NULL UNIQUE,
    "email" VARCHAR(100) NOT NULL UNIQUE,
    "hashed_password" VARCHAR(255) NOT NULL,
    "is_active" INT NOT NULL DEFAULT 1,
    "is_admin" INT NOT NULL DEFAULT 0,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) /* 用户 */;
CREATE INDEX IF NOT EXISTS "idx_users_usernam_266d85" ON "users" ("username");
CREATE INDEX IF NOT EXISTS "idx_users_email_133a6f" ON "users" ("email");
CREATE TABLE IF NOT EXISTS "knowledge_bases" (
    "id" VARCHAR(36) NOT NULL PRIMARY KEY,
    "name" VARCHAR(100) NOT NULL,
    "description" TEXT,
    "is_public" INT NOT NULL DEFAULT 0,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "owner_id" VARCHAR(36) NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
) /* 知识库 */;
CREATE TABLE IF NOT EXISTS "documents" (
    "id" VARCHAR(36) NOT NULL PRIMARY KEY,
    "filename" VARCHAR(255) NOT NULL,
    "file_path" VARCHAR(500) NOT NULL,
    "file_size" INT NOT NULL,
    "chunk_count" INT NOT NULL DEFAULT 0,
    "status" VARCHAR(20) NOT NULL DEFAULT 'processing',
    "error_msg" TEXT,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "kb_id" VARCHAR(36) NOT NULL REFERENCES "knowledge_bases" ("id") ON DELETE CASCADE
) /* 文档 */;
CREATE TABLE IF NOT EXISTS "document_chunks" (
    "id" VARCHAR(36) NOT NULL PRIMARY KEY,
    "content" TEXT NOT NULL,
    "chunk_index" INT NOT NULL,
    "chroma_id" VARCHAR(100),
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "doc_id" VARCHAR(36) NOT NULL REFERENCES "documents" ("id") ON DELETE CASCADE
) /* 文档分块 */;
CREATE TABLE IF NOT EXISTS "model_configs" (
    "id" VARCHAR(36) NOT NULL PRIMARY KEY,
    "name" VARCHAR(50) NOT NULL DEFAULT '默认配置',
    "model_name" VARCHAR(50) NOT NULL DEFAULT 'deepseek-chat',
    "temperature" REAL NOT NULL DEFAULT 0.7,
    "max_tokens" INT NOT NULL DEFAULT 2048,
    "top_p" REAL NOT NULL DEFAULT 0.95,
    "is_default" INT NOT NULL DEFAULT 1,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" VARCHAR(36) NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
) /* 模型配置 */;
CREATE TABLE IF NOT EXISTS "conversations" (
    "id" VARCHAR(36) NOT NULL PRIMARY KEY,
    "title" VARCHAR(200) NOT NULL DEFAULT '新对话',
    "kb_ids" TEXT,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "model_config_id" VARCHAR(36) REFERENCES "model_configs" ("id") ON DELETE SET NULL,
    "user_id" VARCHAR(36) NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
) /* 对话会话 */;
CREATE TABLE IF NOT EXISTS "messages" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "role" VARCHAR(20) NOT NULL,
    "content" TEXT NOT NULL,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "conversation_id" VARCHAR(36) NOT NULL REFERENCES "conversations" ("id") ON DELETE CASCADE
) /* 聊天消息 */;
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSON NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
    "mHaIUWTW4eN/qxVRPA=="
)
