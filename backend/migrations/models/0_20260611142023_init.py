from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `keenrobot_example_category` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `state` SMALLINT NOT NULL  COMMENT '状态(0:启用, 1:禁用)' DEFAULT 0,
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `created_user` VARCHAR(16)   COMMENT '创建人员',
    `updated_user` VARCHAR(16)   COMMENT '更新人员',
    `name` VARCHAR(64) NOT NULL  COMMENT '分类名称',
    `code` VARCHAR(32) NOT NULL UNIQUE COMMENT '分类编码',
    `description` LONGTEXT   COMMENT '分类描述',
    `sort_order` INT NOT NULL  COMMENT '排序序号' DEFAULT 0,
    `parent_id` BIGINT   COMMENT '父分类ID',
    KEY `idx_keenrobot_e_state_31cda1` (`state`)
) CHARACTER SET utf8mb4 COMMENT='商品分类模型';
CREATE TABLE IF NOT EXISTS `keenrobot_example_product` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `state` SMALLINT NOT NULL  COMMENT '状态(0:启用, 1:禁用)' DEFAULT 0,
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `created_user` VARCHAR(16)   COMMENT '创建人员',
    `updated_user` VARCHAR(16)   COMMENT '更新人员',
    `uid` CHAR(36)  UNIQUE COMMENT '唯一标识符',
    `name` VARCHAR(128) NOT NULL  COMMENT '商品名称',
    `code` VARCHAR(32) NOT NULL UNIQUE COMMENT '商品编码',
    `description` LONGTEXT   COMMENT '商品描述',
    `price` DECIMAL(10,2) NOT NULL  COMMENT '商品价格',
    `stock` INT NOT NULL  COMMENT '库存数量' DEFAULT 0,
    `category_id` BIGINT NOT NULL  COMMENT '分类ID',
    `is_featured` BOOL NOT NULL  COMMENT '是否推荐' DEFAULT 0,
    `tags` JSON NOT NULL  COMMENT '商品标签',
    KEY `idx_keenrobot_e_state_5b8f6c` (`state`),
    KEY `idx_keenrobot_e_categor_ae628a` (`category_id`)
) CHARACTER SET utf8mb4 COMMENT='商品模型';
CREATE TABLE IF NOT EXISTS `keenrobot_user` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `state` SMALLINT NOT NULL  COMMENT '状态(0:启用, 1:禁用)' DEFAULT 0,
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `created_user` VARCHAR(16)   COMMENT '创建人员',
    `updated_user` VARCHAR(16)   COMMENT '更新人员',
    `username` VARCHAR(32) NOT NULL UNIQUE COMMENT '用户账号',
    `password` VARCHAR(255) NOT NULL  COMMENT '用户密码',
    `alias` VARCHAR(64) NOT NULL  COMMENT '用户姓名',
    `email` VARCHAR(64) NOT NULL  COMMENT '用户邮箱',
    `phone` VARCHAR(20)   COMMENT '用户电话',
    `motto` VARCHAR(255)   COMMENT '用户签名',
    `avatar` VARCHAR(255)   COMMENT '用户头像',
    `is_active` BOOL NOT NULL  COMMENT '是否激活' DEFAULT 1,
    `is_superuser` BOOL NOT NULL  COMMENT '是否为超级管理员' DEFAULT 0,
    `last_login` DATETIME(6)   COMMENT '最后一次登陆时间',
    `token_version` INT NOT NULL  COMMENT 'Token版本号，用于吊销用户所有Token' DEFAULT 0,
    `address` VARCHAR(255)   COMMENT '用户住址',
    `gender` SMALLINT NOT NULL  COMMENT '用户性别: 0未知 1男 2女' DEFAULT 0,
    `user_type` SMALLINT NOT NULL  COMMENT '用户类型：0xx 1xx 2xx' DEFAULT 0,
    `emergency_name` VARCHAR(32)   COMMENT '紧急联系人',
    `emergency_phone` VARCHAR(20)   COMMENT '紧急联系电话',
    UNIQUE KEY `uid_keenrobot_u_alias_ac1839` (`alias`, `email`),
    KEY `idx_keenrobot_u_state_aefb13` (`state`),
    KEY `idx_keenrobot_u_is_acti_f5a960` (`is_active`),
    KEY `idx_keenrobot_u_is_supe_8cdf9e` (`is_superuser`),
    KEY `idx_keenrobot_u_last_lo_44d475` (`last_login`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `keenrobot_model_configs` (
    `id` VARCHAR(64) NOT NULL  PRIMARY KEY COMMENT '配置ID',
    `state` SMALLINT NOT NULL  COMMENT '状态(0:启用, 1:禁用)' DEFAULT 0,
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `created_user` VARCHAR(16)   COMMENT '创建人员',
    `updated_user` VARCHAR(16)   COMMENT '更新人员',
    `name` VARCHAR(64) NOT NULL  COMMENT '配置名称' DEFAULT '默认配置',
    `description` VARCHAR(255)   COMMENT '配置说明',
    `model_name` VARCHAR(64) NOT NULL  COMMENT '模型名称' DEFAULT 'deepseek-chat',
    `temperature` DOUBLE NOT NULL  COMMENT '温度(控制AI回答随机性)' DEFAULT 0.7,
    `max_tokens` INT NOT NULL  COMMENT '限制单次回答的最大输出Token数' DEFAULT 4096,
    `top_p` DOUBLE NOT NULL  COMMENT 'Top P(核采样参数)' DEFAULT 0.95,
    `top_k` INT NOT NULL  COMMENT 'Top K(知识库检索条数)' DEFAULT 5,
    `max_history_rounds` INT NOT NULL  COMMENT '保留历史对话轮数' DEFAULT 10,
    `score_threshold` DOUBLE NOT NULL  COMMENT '检索相似度阈值(0-1)' DEFAULT 0,
    `system_prompt` LONGTEXT   COMMENT '系统提示词，支持{context}占位符',
    `is_default` BOOL NOT NULL  COMMENT '是否默认配置' DEFAULT 1,
    `user_id` BIGINT NOT NULL COMMENT '所属用户',
    CONSTRAINT `fk_keenrobo_keenrobo_be3d5f5e` FOREIGN KEY (`user_id`) REFERENCES `keenrobot_user` (`id`) ON DELETE CASCADE,
    KEY `idx_keenrobot_m_state_9f382d` (`state`)
) CHARACTER SET utf8mb4 COMMENT='模型配置';
CREATE TABLE IF NOT EXISTS `keenrobot_knowledge_bases` (
    `id` VARCHAR(64) NOT NULL  PRIMARY KEY COMMENT '知识库ID',
    `state` SMALLINT NOT NULL  COMMENT '状态(0:启用, 1:禁用)' DEFAULT 0,
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `created_user` VARCHAR(16)   COMMENT '创建人员',
    `updated_user` VARCHAR(16)   COMMENT '更新人员',
    `name` VARCHAR(128) NOT NULL  COMMENT '知识库名称',
    `description` LONGTEXT   COMMENT '知识库描述',
    `is_public` BOOL NOT NULL  COMMENT '是否公开' DEFAULT 0,
    `owner_id` BIGINT NOT NULL COMMENT '所属用户',
    CONSTRAINT `fk_keenrobo_keenrobo_50457b45` FOREIGN KEY (`owner_id`) REFERENCES `keenrobot_user` (`id`) ON DELETE CASCADE,
    KEY `idx_keenrobot_k_state_aa0f13` (`state`)
) CHARACTER SET utf8mb4 COMMENT='知识库模型';
CREATE TABLE IF NOT EXISTS `keenrobot_documents` (
    `id` VARCHAR(64) NOT NULL  PRIMARY KEY COMMENT '文档ID',
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `filename` VARCHAR(255) NOT NULL  COMMENT '文件名',
    `file_path` VARCHAR(512) NOT NULL  COMMENT '文件路径',
    `file_size` INT NOT NULL  COMMENT '文件大小(字节)',
    `chunk_count` INT NOT NULL  COMMENT '分块数量' DEFAULT 0,
    `status` VARCHAR(32) NOT NULL  COMMENT '处理状态' DEFAULT 'processing',
    `error_msg` LONGTEXT   COMMENT '错误信息',
    `kb_id` VARCHAR(64) NOT NULL COMMENT '所属知识库',
    CONSTRAINT `fk_keenrobo_keenrobo_375cb9b7` FOREIGN KEY (`kb_id`) REFERENCES `keenrobot_knowledge_bases` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4 COMMENT='文档模型';
CREATE TABLE IF NOT EXISTS `keenrobot_document_chunks` (
    `id` VARCHAR(64) NOT NULL  PRIMARY KEY COMMENT '分块ID',
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `content` LONGTEXT NOT NULL  COMMENT '分块内容',
    `chunk_index` INT NOT NULL  COMMENT '分块序号',
    `chroma_id` VARCHAR(128)   COMMENT 'Chroma向量ID',
    `doc_id` VARCHAR(64) NOT NULL COMMENT '所属文档',
    CONSTRAINT `fk_keenrobo_keenrobo_d488c022` FOREIGN KEY (`doc_id`) REFERENCES `keenrobot_documents` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4 COMMENT='文档分块模型';
CREATE TABLE IF NOT EXISTS `keenrobot_audit` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `created_user` VARCHAR(16)   COMMENT '创建人员',
    `updated_user` VARCHAR(16)   COMMENT '更新人员',
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `user_id` BIGINT NOT NULL  COMMENT '用户ID',
    `username` VARCHAR(32) NOT NULL  COMMENT '用户名称',
    `request_time` DATETIME(6) NOT NULL  COMMENT '请求时间',
    `request_tags` VARCHAR(255)   COMMENT '请求模块' DEFAULT '',
    `request_summary` VARCHAR(255)   COMMENT '请求接口' DEFAULT '',
    `request_method` VARCHAR(7) NOT NULL  COMMENT '请求方式',
    `request_router` VARCHAR(255) NOT NULL  COMMENT '请求路由',
    `request_client` VARCHAR(16)   COMMENT '请求来源' DEFAULT '',
    `request_header` JSON   COMMENT '请求头部',
    `request_params` LONGTEXT   COMMENT '请求参数',
    `response_time` DATETIME(6) NOT NULL  COMMENT '响应时间',
    `response_header` JSON   COMMENT '响应头部',
    `response_code` VARCHAR(16)   COMMENT '响应代码' DEFAULT '',
    `response_message` VARCHAR(512)   COMMENT '响应消息' DEFAULT '',
    `response_params` LONGTEXT   COMMENT '响应参数',
    `response_elapsed` VARCHAR(16) NOT NULL  COMMENT '响应耗时',
    `audit_error` LONGTEXT   COMMENT '审计入库异常信息',
    KEY `idx_keenrobot_a_user_id_e9a9dc` (`user_id`),
    KEY `idx_keenrobot_a_usernam_000393` (`username`),
    KEY `idx_keenrobot_a_request_490048` (`request_time`),
    KEY `idx_keenrobot_a_request_87e1d4` (`request_tags`),
    KEY `idx_keenrobot_a_request_63147a` (`request_summary`),
    KEY `idx_keenrobot_a_request_a8c79b` (`request_method`),
    KEY `idx_keenrobot_a_request_f2eab5` (`request_router`),
    KEY `idx_keenrobot_a_respons_f7510c` (`response_time`),
    KEY `idx_keenrobot_a_respons_79f8ce` (`response_code`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `keenrobot_test_case_task` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `created_user` VARCHAR(16)   COMMENT '创建人员',
    `updated_user` VARCHAR(16)   COMMENT '更新人员',
    `folder_path` VARCHAR(500) NOT NULL  COMMENT '输出文件夹路径' DEFAULT '',
    `app_system` VARCHAR(50) NOT NULL  COMMENT '应用系统' DEFAULT '',
    `requirement_name` VARCHAR(200) NOT NULL  COMMENT '需求名称' DEFAULT '',
    `status` VARCHAR(20) NOT NULL  COMMENT '任务状态' DEFAULT 'generating',
    `error_reason` VARCHAR(500)   COMMENT '错误原因' DEFAULT ''
) CHARACTER SET utf8mb4 COMMENT='测试用例生成任务模型';
CREATE TABLE IF NOT EXISTS `keenrobot_conversations` (
    `id` VARCHAR(64) NOT NULL  PRIMARY KEY COMMENT '对话ID',
    `state` SMALLINT NOT NULL  COMMENT '状态(0:启用, 1:禁用)' DEFAULT 0,
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `created_user` VARCHAR(16)   COMMENT '创建人员',
    `updated_user` VARCHAR(16)   COMMENT '更新人员',
    `title` VARCHAR(255) NOT NULL  COMMENT '对话标题' DEFAULT '新对话',
    `knowledge_ids` LONGTEXT   COMMENT '所属知识库',
    `model_config_id` VARCHAR(64) COMMENT '所属模型配置',
    `user_id` BIGINT NOT NULL COMMENT '所属用户',
    CONSTRAINT `fk_keenrobo_keenrobo_7946670a` FOREIGN KEY (`model_config_id`) REFERENCES `keenrobot_model_configs` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_keenrobo_keenrobo_fe85a5a4` FOREIGN KEY (`user_id`) REFERENCES `keenrobot_user` (`id`) ON DELETE CASCADE,
    KEY `idx_keenrobot_c_state_6cebe7` (`state`)
) CHARACTER SET utf8mb4 COMMENT='对话会话模型';
CREATE TABLE IF NOT EXISTS `keenrobot_messages` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT COMMENT '消息ID',
    `state` SMALLINT NOT NULL  COMMENT '状态(0:启用, 1:禁用)' DEFAULT 0,
    `created_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `updated_time` DATETIME(6) NOT NULL  COMMENT '更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `created_user` VARCHAR(16)   COMMENT '创建人员',
    `updated_user` VARCHAR(16)   COMMENT '更新人员',
    `role` VARCHAR(20) NOT NULL  COMMENT '消息角色',
    `content` LONGTEXT NOT NULL  COMMENT '消息内容',
    `conversation_id` VARCHAR(64) NOT NULL COMMENT '所属对话',
    CONSTRAINT `fk_keenrobo_keenrobo_caaa6119` FOREIGN KEY (`conversation_id`) REFERENCES `keenrobot_conversations` (`id`) ON DELETE CASCADE,
    KEY `idx_keenrobot_m_state_5bb882` (`state`)
) CHARACTER SET utf8mb4 COMMENT='聊天消息模型';
CREATE TABLE IF NOT EXISTS `aerich` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `version` VARCHAR(255) NOT NULL,
    `app` VARCHAR(100) NOT NULL,
    `content` JSON NOT NULL
) CHARACTER SET utf8mb4;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
)
