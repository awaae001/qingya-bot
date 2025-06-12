import discord
from discord import app_commands
import logging
import config
from datetime import datetime
from .commands import text_command_utils, send_card_utils, delet_command_utils, status_utils
from .feedback import FeedbackModal, FeedbackView

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
    async def rep_admin_command(interaction: discord.Interaction):
        """处理/rep_admin命令，创建管理员专用私聊按钮"""
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

    @tree.command(name="status", description="显示系统和机器人状态")
    async def status_command(interaction: discord.Interaction):
        """显示系统和机器人状态"""
        await status_utils.handle_status_command(interaction, bot_instance)
