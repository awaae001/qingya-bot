import logging
from typing import Optional
from datetime import datetime
import discord
from discord import Embed
import config

class ChannelLogger:
    """统一频道日志记录器，支持标准日志和格式化频道消息"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.bot = None
        self.default_channel = None
        
    def set_bot(self, bot: discord.Client):
        """设置Discord bot实例"""
        self.bot = bot
        
    def set_default_channel(self):
        """设置默认日志频道"""
        if config.LOG_CHANNELS and len(config.LOG_CHANNELS) > 0:
            self.default_channel = config.LOG_CHANNELS[0]
            self.logger.info(f"已设置默认日志频道: {self.default_channel}")
        else:
            self.logger.error("未配置日志频道(LOG_CHANNELS)")
            self.default_channel = None
        
    async def send_to_channel(
        self,
        source: str,
        module: str,
        description: str,
        additional_info: Optional[str] = None,
        channel_id: Optional[int] = None
    ) -> bool:
        """
        发送格式化日志消息到指定频道
        
        参数:
            source: 操作来源
            module: 模块名称
            description: 操作说明
            additional_info: 附加信息(可选)
            channel_id: 目标频道ID(可选，默认使用self.default_channel)
            
        返回:
            bool: 是否发送成功
        """
        if not self.bot:
            self.logger.info("Discord bot实例未初始化，跳过频道消息发送")
            return True
            
        channel = channel_id or self.default_channel
        if not channel:
            self.logger.error("未指定日志频道且无默认频道设置")
            return False
            
        try:
            # 创建格式化消息
            embed = Embed(
                title="操作记录",
                color=0x3498db
            )
            embed.add_field(name="来源", value=source, inline=True)
            embed.add_field(name="模块", value=module, inline=True)
            embed.add_field(name="说明", value=description, inline=False)
            
            if additional_info:
                embed.add_field(name="附加信息", value=additional_info, inline=False)
                
            # 在页脚显示操作时间
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            embed.set_footer(text=f"操作时间: {current_time} | 青崖")
            
            # 获取频道并发送消息
            target_channel = await self.bot.fetch_channel(channel)
            await target_channel.send(embed=embed)
            
            self.logger.info(f"已发送日志消息到频道 {channel}: {description}")
            return True
            
        except Exception as e:
            self.logger.error(f"发送日志消息到频道失败: {e}")
            return False
            
    def info(self, msg: str, *args, **kwargs):
        """记录info级别日志"""
        self.logger.info(msg, *args, **kwargs)
        
    def warning(self, msg: str, *args, **kwargs):
        """记录warning级别日志"""
        self.logger.warning(msg, *args, **kwargs)
        
    def error(self, msg: str, *args, **kwargs):
        """记录error级别日志"""
        self.logger.error(msg, *args, **kwargs)
        
    def debug(self, msg: str, *args, **kwargs):
        """记录debug级别日志"""
        self.logger.debug(msg, *args, **kwargs)

# 全局默认日志记录器
channel_logger = ChannelLogger(__name__)
