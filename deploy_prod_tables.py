import pymysql
import sys

# 生产环境数据库配置
config = {
    "host": "81.68.235.167",
    "user": "pillow",
    "password": "1234QWERasdf!@#$",
    "database": "pillow_customer_prod"
}

# 建表 SQL 语句列表
TABLES = [
    # 1. COC游戏状态表
    """
    CREATE TABLE IF NOT EXISTS `t_coc_game_state` (
      `id` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
      `user_id` INT UNSIGNED NOT NULL COMMENT '用户id',
      `session_id` CHAR(16) NOT NULL COMMENT '会话id',
      `gm_id` VARCHAR(16) DEFAULT NULL COMMENT 'GM ID',
      `gm_gender` VARCHAR(8) DEFAULT NULL COMMENT 'GM性别偏好: male/female',
      `game_status` VARCHAR(32) NOT NULL DEFAULT 'gm_select' 
        COMMENT '游戏状态: gm_select/step1_attributes/step2_secondary/step3_profession/step4_background/step5_summary/playing/ended',
      `investigator_card` JSON DEFAULT NULL COMMENT '调查员人物卡JSON',
      `round_number` INT NOT NULL DEFAULT 1 COMMENT '回合数(天数)',
      `turn_number` INT NOT NULL DEFAULT 0 COMMENT '对话/行动轮数',
      `save_count` INT NOT NULL DEFAULT 0 COMMENT '存档计数',
      `temp_data` JSON DEFAULT NULL COMMENT '临时数据JSON(步骤间传递)',
      `dialogue_summary` TEXT DEFAULT NULL COMMENT '对话历史总结(滚动更新)',
      `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
      `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
      `del` SMALLINT NOT NULL DEFAULT 0 COMMENT '是否删除',
      PRIMARY KEY (`id`),
      UNIQUE KEY `uk_session_id` (`session_id`),
      KEY `idx_user_id` (`user_id`),
      KEY `idx_game_status` (`game_status`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='克苏鲁跑团游戏状态表';
    """,
    
    # 2. COC存档表
    """
    CREATE TABLE IF NOT EXISTS `t_coc_save_slot` (
      `id` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
      `save_id` VARCHAR(32) NOT NULL COMMENT '存档ID',
      `session_id` CHAR(16) NOT NULL COMMENT '关联会话ID',
      `user_id` INT UNSIGNED NOT NULL COMMENT '用户ID',
      `gm_id` VARCHAR(16) DEFAULT NULL COMMENT 'GM ID',
      `game_status` VARCHAR(32) NOT NULL COMMENT '存档时的游戏状态',
      `investigator_card` JSON DEFAULT NULL COMMENT '人物卡快照',
      `round_number` INT NOT NULL DEFAULT 1 COMMENT '回合数',
      `turn_number` INT NOT NULL DEFAULT 0 COMMENT '轮数',
      `temp_data` JSON DEFAULT NULL COMMENT 'GM信息等临时数据',
      `create_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
      `del` SMALLINT NOT NULL DEFAULT 0 COMMENT '是否删除',
      PRIMARY KEY (`id`),
      UNIQUE KEY `uk_save_id` (`save_id`),
      KEY `idx_session_id` (`session_id`),
      KEY `idx_user_id` (`user_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='克苏鲁跑团存档槽表';
    """,
    
    # 3. 副本世界游戏状态表
    """
    CREATE TABLE IF NOT EXISTS `t_freak_world_game_state` (
      `id` int(11) unsigned NOT NULL AUTO_INCREMENT COMMENT '主键',
      `freak_world_id` int(11) unsigned NOT NULL COMMENT '异世界id',
      `user_id` int(32) unsigned NOT NULL COMMENT '用户id',
      `session_id` char(16) NOT NULL COMMENT '会话id',
      `gm_id` varchar(16) NOT NULL DEFAULT '01' COMMENT '引导者ID',
      `game_status` varchar(32) NOT NULL DEFAULT 'gm_intro' COMMENT '游戏状态: gm_intro/world_intro/character_select/playing/ended/death',
      `gender_preference` varchar(8) DEFAULT NULL COMMENT '原住民性别偏好: male/female',
      `current_character_id` varchar(64) DEFAULT NULL COMMENT '当前交谈角色ID',
      `random_seed` bigint DEFAULT NULL COMMENT '随机种子',
      `characters` json DEFAULT NULL COMMENT '已生成的角色列表JSON',
      `dialogue_summary` TEXT DEFAULT NULL COMMENT '对话历史总结(滚动更新)',
      `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
      `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
      `del` SMALLINT NOT NULL DEFAULT 0 COMMENT '是否删除',
      PRIMARY KEY (`id`),
      UNIQUE KEY `uk_session_id` (`session_id`),
      KEY `idx_user_id` (`user_id`),
      KEY `idx_freak_world_id` (`freak_world_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='异世界游戏状态表';
    """,
    
    # 4. Prompt配置统一表
    """
    CREATE TABLE IF NOT EXISTS `t_prompt_config` (
      `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增ID',
      `config_id` VARCHAR(64) NOT NULL COMMENT '配置ID (如 gm_01, c1s1c1_0001, world_01)',
      `type` VARCHAR(16) NOT NULL COMMENT '类型: gm/character/world',
      `name` VARCHAR(128) NOT NULL COMMENT '名称',
      `gender` VARCHAR(8) DEFAULT NULL COMMENT '性别 (GM/人物适用)',
      `traits` VARCHAR(1024) DEFAULT NULL COMMENT '特质描述',
      `prompt` MEDIUMTEXT COMMENT '主 prompt 内容',
      `config` JSON COMMENT '类型特有配置 JSON',
      `status` TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 1=启用, 0=禁用',
      `sort_order` INT DEFAULT 0 COMMENT '排序权重',
      `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
      `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
      PRIMARY KEY (`id`),
      UNIQUE KEY `uk_config_id` (`config_id`),
      KEY `idx_type` (`type`),
      KEY `idx_status` (`status`),
      KEY `idx_type_status` (`type`, `status`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Prompt配置统一表(GM/人物/世界)';
    """,
    
    # 5. 聊天记忆表
    """
    CREATE TABLE IF NOT EXISTS `chat_memory` (
      `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
      `user_id` VARCHAR(255) NOT NULL COMMENT '用户ID',
      `robot_id` VARCHAR(255) NOT NULL COMMENT '机器人ID/角色ID',
      `short_term_memory` TEXT COMMENT '短期记忆(文字短)',
      `long_term_memory` TEXT COMMENT '长期记忆(文字多)',
      `conversation_count` INT DEFAULT 0 COMMENT '对话轮次计数(每10轮更新短期记忆)',
      `last_daily_update` DATETIME DEFAULT '1970-01-01 00:00:00' COMMENT '上次每日更新时间',
      `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
      `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
      PRIMARY KEY (`id`),
      KEY `idx_user_id` (`user_id`),
      KEY `idx_robot_id` (`robot_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='聊天记忆表';
    """
]

def main():
    try:
        # 1. 连接数据库
        print(f"Connecting to {config['host']}...")
        connection = pymysql.connect(
            host=config['host'],
            user=config['user'],
            password=config['password']
        )
        
        with connection.cursor() as cursor:
            # 2. 创建数据库
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {config['database']} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print(f"✅ Database {config['database']} created/verified")
            
            # 3. 切换到目标数据库
            cursor.execute(f"USE {config['database']}")
            
            # 4. 执行建表语句
            for i, sql in enumerate(TABLES, 1):
                try:
                    # 简单提取表名用于打印
                    import re
                    match = re.search(r'`(.+?)`', sql)
                    table_name = match.group(1) if match else f"Table {i}"
                    print(f"Creating {table_name}...")
                    cursor.execute(sql)
                    print(f"✅ {table_name} created/verified")
                except Exception as e:
                    print(f"❌ Error creating table {i}: {e}")
            
            connection.commit()
            print("\n🎉 All production tables created successfully!")
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
    finally:
        if 'connection' in locals() and connection:
            connection.close()
            print("Database connection closed.")

if __name__ == "__main__":
    main()
