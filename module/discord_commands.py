import discord
from discord import app_commands
import logging
import config
import json
import uuid
from datetime import datetime
from .commands import text_command_utils, send_card_utils, delet_command_utils, status_utils
from .feedback import FeedbackView, FeedbackReplyView,delete_feedback, FEEDBACK_DATA_PATH, save_feedback

logger = logging.getLogger(__name__)

async def check_auth(interaction: discord.Interaction):
    """检查用户权限"""
    if config.AUTHORIZED_USERS and str(interaction.user.id) not in config.AUTHORIZED_USERS:
        logger.warning(f"未授权人员 {interaction.user.name} ({interaction.user.id}) 尝试使用命令 /{interaction.command.name}")
        await interaction.response.send_message("❌ 抱歉，你没有使用此命令的权限", ephemeral=True)
        return False
    return True

def register_commands(tree: app_commands.CommandTree, bot_instance):
    """注册所有斜杠命令"""

    @tree.command(name="text", description="发送消息到指定频道(ID)或所有频道(可选转发到Telegram)")
    @app_commands.check(check_auth)
    @app_commands.describe(
        content="消息内容",
        image_file="附加图片文件(可选)",
        forward_to_tg="是否转发到Telegram(默认否)",
        channel_ids="频道ID列表(多个用逗号分隔)",
        channel_id_mode="频道ID处理模式(默认'none')",
        forward_mode="转发模式(当'channel_id_mode'为'and'或'ban'时, 或'none'且未提供channel_ids时生效)"
    )
    @app_commands.choices(forward_mode=[
        app_commands.Choice(name="不转发到特殊频道", value=0),
        app_commands.Choice(name="转发到所有频道", value=1),
        app_commands.Choice(name="只转发到特殊频道", value=2)
    ])
    @app_commands.choices(channel_id_mode=[
        app_commands.Choice(name="仅发送到指定ID (默认)", value="none"),
        app_commands.Choice(name="在转发模式基础上增加指定ID", value="and"),
        app_commands.Choice(name="在转发模式基础上排除指定ID", value="ban")
    ])
    async def text_command(
        interaction: discord.Interaction,
        channel_ids: str = None,
        channel_id_mode: str = "none",
        content: str = None,
        image_file: discord.Attachment = None,
        forward_to_tg: bool = False,
        forward_mode: int = 0
    ):
        """处理/text命令，根据模式发送文本和可选图片到频道和Telegram"""
        final_response = await text_command_utils.handle_text_command(
            interaction=interaction,
            bot_instance=bot_instance,
            channel_ids=channel_ids,
            channel_id_mode=channel_id_mode,
            content=content,
            image_file=image_file,
            forward_to_tg=forward_to_tg,
            forward_mode=forward_mode
        )
        await interaction.edit_original_response(content=final_response)

    @tree.command(name="send", description="发送Embed消息到指定频道(ID)或所有频道")
    @app_commands.check(check_auth)
    @app_commands.describe(
        title="消息标题 (默认为空)",
        content="消息内容（可选）",
        image_file="上传图片文件(可选)",
        forward_to_tg="是否转发到Telegram(默认否)",
        channel_ids="频道ID列表(多个用逗号分隔)",
        channel_id_mode="频道ID处理模式(默认'none')",
        forward_mode="转发模式(当'channel_id_mode'为'and'或'ban'时, 或'none'且未提供channel_ids时生效)"
    )
    @app_commands.choices(forward_mode=[
        app_commands.Choice(name="不转发到特殊频道", value=0),
        app_commands.Choice(name="转发到所有频道", value=1),
        app_commands.Choice(name="只转发到特殊频道", value=2)
    ])
    @app_commands.choices(channel_id_mode=[
        app_commands.Choice(name="仅发送到指定ID (默认)", value="none"),
        app_commands.Choice(name="在转发模式基础上增加指定ID", value="and"),
        app_commands.Choice(name="在转发模式基础上排除指定ID", value="ban")
    ])
    async def send_command(
        interaction: discord.Interaction,
        channel_ids: str = None,
        channel_id_mode: str = "none", # 新增参数
        title: str = "\u200b", # 默认零宽空格
        content: str = None,
        image_file: discord.Attachment = None,
        forward_to_tg: bool = False,
        forward_mode: int = 0
    ):
        """处理/send命令，根据模式发送Embed消息到频道和Telegram"""
        final_response = await send_card_utils.handle_send_command(
        interaction=interaction,
        bot_instance=bot_instance,
        channel_ids=channel_ids,
        channel_id_mode=channel_id_mode,
        title=title,
        content=content,
        image_file=image_file,
        forward_to_tg=forward_to_tg,
        forward_mode=forward_mode
    )

        await interaction.edit_original_response(content=final_response)


    @tree.command(name="del", description="（敏感）删除Discord消息")
    @app_commands.check(check_auth)
    @app_commands.describe(
        message_link="要删除的消息链接"
    )
    async def delete_command(
        interaction: discord.Interaction,
        message_link: str
    ):
        await delet_command_utils.handle_delete_command(
            interaction=interaction,
            message_link=message_link,
            bot_instance=bot_instance
        )

    @tree.command(name="card", description="发送自定义消息卡片")
    @app_commands.describe(
        title="卡片标题",
        description="卡片内容",
        image_url="图片URL(可选)",
        color="颜色(可选)"
    )
    @app_commands.choices(color=[
        app_commands.Choice(name="黄色", value="yellow"),
        app_commands.Choice(name="蓝色", value="blue"),
        app_commands.Choice(name="红色", value="red"),
        app_commands.Choice(name="灰色", value="grey"),
        app_commands.Choice(name="紫色", value="purple"),
        app_commands.Choice(name="绿色", value="green"),
        app_commands.Choice(name="白色", value="white")
    ])

    async def card_command(
        interaction: discord.Interaction,
        title: str,
        description: str,
        image_url: str = None,
        color: str = None
    ):
        """发送自定义卡片消息"""
        embed_color = discord.Color.blue()
        if color:
            try:
                if color.startswith("#"):
                    embed_color = discord.Color.from_str(color)
                else:
                    color_attr = getattr(discord.Color, color.lower(), None)
                    if color_attr and callable(color_attr):
                        embed_color = color_attr()
            except:
                pass

        embed = discord.Embed(
            title=title,
            description=description,
            color=embed_color
        )

        if image_url:
            embed.set_image(url=image_url)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        embed.set_footer(text=f"{config.BOT_NAME} ·自动转发系统|发送时间: {timestamp}")

        logger.info("有用户发送了卡片")
        await interaction.response.send_message(embed=embed)

    @tree.command(name="rep", description="和管理员私聊")
    async def rep_command(interaction: discord.Interaction):
        """处理/rep命令，创建私聊按钮"""
        embed = discord.Embed(
            title="📢 请求私聊",
            description="点击下方按钮提交您创建一个输入框，键入你要私聊的内容 \n 控件将在 60 s 后删除",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"{config.BOT_NAME} · 私聊系统")
        
        view = FeedbackView()
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=False,
            delete_after=60
        )
        logger.info(f"用户 {interaction.user} 请求了私聊表单")

    @tree.command(name="rep_admin", description="管理员专用私聊控件（不会自动消失）")
    @app_commands.check(check_auth)
    @app_commands.describe(
        action="选择操作类型",
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="创建私聊按钮", value="create"),
        app_commands.Choice(name="重建未回复请求", value="rebuild")
    ])
    async def rep_admin_command(interaction: discord.Interaction, action: str = "create"):
        """处理/rep_admin命令，支持创建私聊按钮或重建未回复请求"""
        if action == "create":
            embed = discord.Embed(
                title="📢 管理员私聊",
                description="点击下方按钮提交您创建一个输入框，键入你要私聊的内容",
                color=discord.Color.gold()
            )
            embed.set_footer(text=f"{config.BOT_NAME} · 私聊系统（管理员）")
            
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
                feedback_channel_id = config.LOG_CHANNELS[0] if config.LOG_CHANNELS else None
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

    @tree.command(name="status", description="显示系统和机器人状态")
    async def status_command(interaction: discord.Interaction):
        """显示系统和机器人状态"""
        await status_utils.handle_status_command(interaction, bot_instance)

    @tree.command(name="回顶", description="发送回到顶部消息")
    async def go_top_command(interaction: discord.Interaction):
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
            title="⬆️ 回到顶部导航",
            description=f"使用按钮可以快速回到{'子区' if hasattr(interaction.channel, 'thread') and interaction.channel.thread else '频道'}最顶部",
            color=discord.Color.green()
        )
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        embed.set_footer(text=f"{config.BOT_NAME} · 导航系统 | 发送时间: {timestamp}")
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(f"用户 {interaction.user} 在{channel_name} 使用了回到顶部命令")
