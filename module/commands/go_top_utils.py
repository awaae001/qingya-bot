from typing import Tuple
import discord
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def _create_go_top_ui(top_link: str, description: str, BOT_NAME: str) -> Tuple[discord.Embed, discord.ui.View]:
    """创建回到顶部的 Embed 和 View 组件"""
    view = discord.ui.View()
    view.add_item(discord.ui.Button(
        label="点击回到顶部",
        url=top_link,
        style=discord.ButtonStyle.link,
        emoji="⬆️"
    ))
    
    embed = discord.Embed(
        title="⬆️ 回到顶部",
        description=description,
        color=discord.Color.green()
    )
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    embed.set_footer(text=f"{BOT_NAME} · 导航系统 | 发送时间: {timestamp}")
    
    return embed, view

async def handle_go_top_command(interaction: discord.Interaction, BOT_NAME: str):
    """处理/go_top命令，发送回到顶部消息"""
    channel = interaction.channel
    channel_id = channel.id
    channel_name = channel.name
    
    is_thread = isinstance(channel, discord.Thread)
    if is_thread:
        channel_name = f"子区 {channel.name}"
    
    top_link = f"discord://discord.com/channels/{interaction.guild_id}/{channel_id}/0"
    description = f"使用按钮可以快速回到{'子区' if is_thread else '频道'}最顶部"
    
    embed, view = _create_go_top_ui(top_link, description, BOT_NAME)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    logger.info(f"用户 {interaction.user} 在 {channel_name} 使用了回到顶部命令")

async def handle_go_top_context(interaction: discord.Interaction, message: discord.Message, BOT_NAME: str):
    """处理上下文菜单的回到顶部命令"""
    target_channel = message.channel
    top_link = None

    try:
        # 尝试获取频道历史中的第一条消息
        async for first_message in target_channel.history(limit=1, oldest_first=True):
            top_link = first_message.jump_url
            break
    except discord.Forbidden:
        logger.warning(f"无法访问频道 {target_channel.name} ({target_channel.id}) 的历史记录，将回退到备用链接")
    except Exception as e:
        logger.error(f"获取频道 {target_channel.name} ({target_channel.id}) 历史记录时发生未知错误: {e}")

    # 如果无法获取第一条消息，则使用备用链接方案
    if top_link is None:
        top_link = f"discord://discord.com/channels/{interaction.guild_id}/{target_channel.id}/0"

    description = f"使用按钮可以快速回到频道 **{target_channel.name}** 的最顶部"
    embed, view = _create_go_top_ui(top_link, description, BOT_NAME)

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    logger.info(f"用户 {interaction.user} 对消息 {message.id} 使用了回到顶部命令")
