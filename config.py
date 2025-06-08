import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=True)

# 机器人名称
BOT_NAME = os.getenv("BOT_NAME", "Telegram-Discord-Sync")

# Telegram 配置
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

# Discord 配置
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# 多服务器配置 (格式: "server1_id:channel1,channel2|server2_id:channel3,channel4")
DISCORD_SERVERS = {}
servers_config = os.getenv("DISCORD_SERVERS", "")
if servers_config:
    for server_part in servers_config.split("|"):
        if ":" in server_part:
            guild_id, channels = server_part.split(":", 1)
            guild_id = int(guild_id.strip())
            channel_ids = [
                int(channel_id.strip()) 
                for channel_id in channels.split(",") 
                if channel_id.strip()
            ]
            DISCORD_SERVERS[guild_id] = channel_ids

# 向后兼容: 如果使用旧配置方式
if not DISCORD_SERVERS and os.getenv("DISCORD_GUILD_ID"):
    guild_id = int(os.getenv("DISCORD_GUILD_ID", 0))
    channel_ids = [
        int(channel_id) for channel_id in 
        os.getenv("DISCORD_CHANNEL_IDS", "").split(",") 
        if channel_id.strip()
    ]
    if guild_id and channel_ids:
        DISCORD_SERVERS[guild_id] = channel_ids

# 同步配置
SYNC_TG_TO_DISCORD = os.getenv("SYNC_TG_TO_DISCORD", "true").lower() == "true"
SYNC_DISCORD_TO_TG = os.getenv("SYNC_DISCORD_TO_TG", "true").lower() == "true"
FORWARD_DC_TO_TG = os.getenv("FORWARD_DC_TO_TG", "true").lower() == "true" 

# 消息前缀配置
TG_MESSAGE_PREFIX = os.getenv("TG_MESSAGE_PREFIX", "[Telegram] ")
DISCORD_MESSAGE_PREFIX = os.getenv("DISCORD_MESSAGE_PREFIX", "[Discord] ")

# 授权用户配置 (支持从环境变量或直接配置)
# 格式: "userid1,userid2" 或 ["userid1", "userid2"]
AUTHORIZED_USERS = [
    user_id.strip() for user_id in 
    os.getenv("AUTHORIZED_USERS", "").split(",")
    if user_id.strip()
]

# 特殊频道配置 (用于TG转发和命令默认跳过)
SPECIAL_CHANNELS = [
    int(channel_id.strip())
    for channel_id in os.getenv("SPECIAL_CHANNELS", "").split(",")
    if channel_id.strip()
]  

# 定时清理器配置
IMAGE_DIR = os.getenv("IMAGE_DIR", "./data/image/") # 添加一个默认值以防未设置
CLEANUP_INTERVAL_HOURS = int(os.getenv("CLEANUP_INTERVAL_HOURS", 6)) 
MAX_IMAGE_AGE_HOURS = int(os.getenv("MAX_IMAGE_AGE_HOURS", 24))
