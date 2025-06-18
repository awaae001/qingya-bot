import discord
from discord import app_commands
import json
import uuid
from datetime import datetime
from pathlib import Path
import logging
from ..feedback import FeedbackView, FeedbackReplyView, delete_feedback, save_feedback

logger = logging.getLogger(__name__)

async def handle_rep_admin_command(interaction: discord.Interaction, action: str, FEEDBACK_DATA_PATH: Path, LOG_CHANNELS: list, BOT_NAME: str):
    """处理/rep_admin命令，支持创建私聊按钮或重建未回复请求"""
    if action == "create":
        embed = discord.Embed(
            title="📢 管理员私聊",
            description="点击下方按钮提交您创建一个输入框，键入你要私聊的内容",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"{BOT_NAME} · 私聊系统（管理员）")
        
        view = FeedbackView()
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=False
        )
        logger.info(f"管理员 {interaction.user} 请求了私聊表单")
    elif action == "rebuild":
        try:
            # 加载所有反馈数据
            if not FEEDBACK_DATA_PATH.exists():
                await interaction.response.send_message(
                    "⚠️ 没有找到任何反馈数据文件",
                    ephemeral=True
                )
                return
            
            with open(FEEDBACK_DATA_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 筛选未回复请求（排除已处理记录）
            pending_requests = [
                fb for fb in data.values() 
                if "user_id" in fb and "timestamp" in fb and
                not any(k.startswith(("rejected_", "ignored_")) for k in data)
            ]
            
            if not pending_requests:
                await interaction.response.send_message(
                    "✅ 没有需要重建的未回复请求",
                    ephemeral=True
                )
                return
            
            # 获取反馈频道
            feedback_channel_id = LOG_CHANNELS[0] if LOG_CHANNELS else None
            if not feedback_channel_id:
                await interaction.response.send_message(
                    "⚠️ 未配置反馈频道(LOG_CHANNELS)",
                    ephemeral=True
                )
                return
            
            channel = interaction.client.get_channel(feedback_channel_id)
            if not channel:
                channel = await interaction.client.fetch_channel(feedback_channel_id)
            
            # 重建每个未回复请求
            count = 0
            for fb_id, fb_data in data.items():
                if "user_id" in fb_data and "timestamp" in fb_data:
                    # 创建新ID避免冲突
                    new_id = str(uuid.uuid4())
                    
                    embed = discord.Embed(
                        title="🔄 重建的私聊请求",
                        description=fb_data["content"],
                        color=discord.Color.orange()
                    )
                    embed.add_field(name="原始ID", value=fb_id, inline=False)
                    embed.add_field(name="新ID", value=new_id, inline=False)
                    embed.set_author(
                        name=f"用户ID: {fb_data['user_id']}",
                        icon_url=None
                    )
                    embed.set_footer(text=f"原始提交时间: {datetime.fromtimestamp(fb_data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    view = FeedbackReplyView(new_id)
                    await channel.send(embed=embed, view=view)
                    
                    # 保存新记录并删除原始数据
                    save_feedback(new_id, fb_data["user_id"], fb_data["content"])
                    delete_feedback(fb_id)
                    count += 1
            
            await interaction.response.send_message(
                f"✅ 已成功重建 {count} 个未回复请求",
                ephemeral=True
            )
            logger.info(f"管理员 {interaction.user} 重建了 {count} 个未回复私聊请求")
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 重建请求失败: {str(e)}",
                ephemeral=True
            )
            logger.error(f"重建未回复请求失败: {e}")
