import discord
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

async def handle_go_top_command(interaction: discord.Interaction, BOT_NAME: str):
    """处理/go_top命令，发送回到顶部消息"""
    view = discord.ui.View()
    channel_id = interaction.channel_id
    channel_name = interaction.channel.name
    
    # 如果是子区，使用 thread_id 代替 channel_id
    if hasattr(interaction.channel, 'thread') and interaction.channel.thread:
        channel_id = interaction.channel.thread.id
        channel_name = f"子区 {interaction.channel.thread.name}"
    
    top_link = f"discord://discord.com/channels/{interaction.guild_id}/{channel_id}/0"
    view.add_item(discord.ui.Button(
        label="点击回到顶部",
        url=top_link,
        style=discord.ButtonStyle.link,
        emoji="⬆️"
    ))
    
    embed = discord.Embed(
        title="⬆️ 回到顶部",
        description=f"使用按钮可以快速回到{'子区' if hasattr(interaction.channel, 'thread') and interaction.channel.thread else '频道'}最顶部",
        color=discord.Color.green()
    )
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    embed.set_footer(text=f"{BOT_NAME} · 导航系统 | 发送时间: {timestamp}")
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    logger.info(f"用户 {interaction.user} 在{channel_name} 使用了回到顶部命令")
