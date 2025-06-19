import discord
from discord import app_commands
import logging
import asyncio
import config
from utils.channel_logger import ChannelLogger

# 导入拆分出去的模块
import module.discord_commands as discord_commands
import module.discord_forwarder as discord_forwarder

# 设置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class DiscordBot(discord.Client):
    def __init__(self, telegram_bot=None):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.telegram_bot = telegram_bot
        self.channels = {}  # 存储多个频道 {channel_id: channel_object}
        self.channel_logger = ChannelLogger(__name__)
    
    async def on_ready(self):
        """当 Discord 机器人准备就绪时调用"""
        logger.info(f'Discord 机器人已登录为 {self.user}')
        await self.tree.sync()
        self.channel_logger.set_bot(self)  
        self.channel_logger.set_default_channel()  

        # 获取所有指定的服务器和频道
        try:
            if not config.DISCORD_SERVERS:
                logger.error("没有配置任何Discord服务器和频道")
                return
                
            for guild_id, channel_ids in config.DISCORD_SERVERS.items():
                guild = self.get_guild(guild_id)
                if not guild:
                    logger.error(f"无法找到 Discord 服务器 ID: {guild_id}")
                    continue
                    
                for channel_id in channel_ids:
                    channel = guild.get_channel(channel_id)
                    if channel:
                        self.channels[channel_id] = channel
                        logger.info(f"已连接到服务器 {guild.name} 的频道: {channel.name} (ID: {channel_id})")
                    else:
                        logger.error(f"在服务器 {guild.name} 中无法找到频道 ID: {channel_id}")
        except Exception as e:
            logger.error(f"设置 Discord 频道时出错: {e}")
    
    
    async def setup_hook(self):
        """设置斜 slash 命令"""
        # 从 discord_commands 模块注册命令
        discord_commands.register_commands(self.tree, self)
        logger.info("Discord 命令已注册")

    # send_to_discord 方法已移至 discord_forwarder.py
    # 保留一个调用转发器的方法
    async def forward_message(self, message, channel_id=None):
         """调用 discord_forwarder 来发送消息"""
         await discord_forwarder.send_to_discord(self.channels, message, channel_id)


    async def start_bot(self):
        """启动 Discord 机器人"""
        await self.start(config.DISCORD_BOT_TOKEN)
