import os
import discord
from discord import app_commands
import logging
import config
import json
from datetime import datetime
from typing import List
from .commands import text_command_utils, send_card_utils, delet_command_utils, status_utils
from .commands import rep_admin_utils, go_top_utils, fetch_utils, fetch_upd_utils, fetch_del_utils
from .feedback import FeedbackView, FeedbackReplyView, delete_feedback, FEEDBACK_DATA_PATH, save_feedback

logger = logging.getLogger(__name__)

async def check_role_auth(interaction: discord.Interaction, role_type: str = "basic"):
    """检查用户身份组权限
    role_type: 
      - "basic": 检查普通授权身份组
      - "upload": 检查上传权限身份组
    """
    if role_type == "basic":
        if not hasattr(config, 'BASIC_ROLES') or not config.BASIC_ROLES:
            return True
        role_list = config.BASIC_ROLES
        error_msg = "❌ 抱歉，你没有使用此命令的基本权限"
    elif role_type == "upload":
        if not hasattr(config, 'AUTHORIZED_ROLES') or not config.AUTHORIZED_ROLES:
            return True
        role_list = config.AUTHORIZED_ROLES
        error_msg = "❌ 抱歉，你没有上传/删除权限"
    else:
        return False
        
    user_roles = [role.id for role in interaction.user.roles]
    if not any(role_id in user_roles for role_id in role_list):
        logger.warning(f"无权限身份组用户 {interaction.user.name} ({interaction.user.id}) 尝试使用命令 /{interaction.command.name}")
        await interaction.response.send_message(error_msg, ephemeral=True)
        return False
    return True

async def check_command_auth(interaction: discord.Interaction):
    """检查特定命令权限"""
    command_name = interaction.command.name
    
    if command_name in ["fetch_upd", "fetch_del"]:
        return await check_role_auth(interaction, role_type="upload")
        
    # 管理员命令(无法通过身份组获得权限)
    if command_name in ["text", "send", "rep_admin", "del"]:
        if not config.AUTHORIZED_USERS or str(interaction.user.id) not in config.AUTHORIZED_USERS:
            logger.warning(f"非管理员用户 {interaction.user.name} ({interaction.user.id}) 尝试使用管理员命令 /{command_name}")
            await interaction.response.send_message("❌ 抱歉，此命令仅系统管理员可用", ephemeral=True)
            return False
        return True
        
    # 普通命令
    return True

async def check_auth(interaction: discord.Interaction):
    """检查用户权限"""
    # 管理员直接通过权限检查，但仍需检查特定命令权限
    if config.AUTHORIZED_USERS and str(interaction.user.id) in config.AUTHORIZED_USERS:
        return await check_command_auth(interaction)
    
    # 检查基本身份组权限
    if not await check_role_auth(interaction, role_type="basic"):
        logger.warning(f"未授权人员 {interaction.user.name} ({interaction.user.id}) 尝试使用命令 /{interaction.command.name}")
        return False
        
    # 检查特定命令权限
    return await check_command_auth(interaction)

async def check_upload_auth(interaction: discord.Interaction):
    """检查上传/删除图片权限"""
    # 系统管理员始终有权限
    if config.AUTHORIZED_USERS and str(interaction.user.id) in config.AUTHORIZED_USERS:
        return True
    return await check_role_auth(interaction, role_type="upload")


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
        await rep_admin_utils.handle_rep_admin_command(
            interaction=interaction,
            action=action,
            FEEDBACK_DATA_PATH=FEEDBACK_DATA_PATH,
            LOG_CHANNELS=config.LOG_CHANNELS,
            BOT_NAME=config.BOT_NAME
        )

    @tree.command(name="status", description="显示系统和机器人状态")
    async def status_command(interaction: discord.Interaction):
        """显示系统和机器人状态"""
        await status_utils.handle_status_command(interaction, bot_instance)

    @tree.command(name="回顶", description="创建回到顶部导航")
    async def go_top_command(interaction: discord.Interaction):
        """处理/go_top命令，发送回到顶部消息"""
        await go_top_utils.handle_go_top_command(
            interaction=interaction,
            BOT_NAME=config.BOT_NAME
        )
        
    # 图片文件名自动补全功能
    async def filename_autocomplete(
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        image_dir = "data/fetch"
        if not os.path.exists(image_dir):
            return []
            
        # 递归获取所有支持的图片文件
        images = []
        for root, _, files in os.walk(image_dir):
            for f in files:
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    rel_path = os.path.relpath(os.path.join(root, f), image_dir)
                    images.append(rel_path)

        metadata_path = os.path.join("data/fetch", "metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata_list = json.load(f)
            if not (config.AUTHORIZED_USERS and str(interaction.user.id) in config.AUTHORIZED_USERS):
                current_guild = str(interaction.guild.id) if interaction.guild else None
                if current_guild:
                    # 过滤出当前服务器的图片
                    server_images = []
                    for img_path in images:
                        img_name = os.path.basename(img_path)
                        img_meta = next((m for m in metadata_list if m['saved_filename'] == img_name), None)
                        if img_meta and img_meta['guild_id'] == current_guild:
                            server_images.append(img_path)
                    images = server_images
        
        return [
            app_commands.Choice(name=os.path.basename(f), value=f)
            for f in images 
            if current.lower() in f.lower()
        ][:25]  # 限制最多返回25个选项

    @tree.command(name="fetch", description="发送指定或随机图片到当前频道或回复指定消息")
    @app_commands.check(check_auth)
    @app_commands.describe(
        filename="指定图片文件名(可自动补全)",
        message_link="要回复的消息链接(可选)"
    )
    @app_commands.autocomplete(filename=filename_autocomplete)
    async def fetch_command(
        interaction: discord.Interaction, 
        filename: str = None,
        message_link: str = None
    ):
        """处理/fetch命令，发送指定或随机图片到当前频道或回复指定消息"""
        await fetch_utils.fetch_images(interaction, filename, message_link)

    @tree.command(name="fetch_upd", description="上传图片到指定目录")
    @app_commands.check(check_upload_auth)
    @app_commands.describe(
        sender="发送者标识",
        context="上下文标识",
        image_url="图片URL(可选)",
        image_file="图片文件附件(可选)"
    )
    async def fetch_upd_command(
        interaction: discord.Interaction,
        sender: str,
        context: str,
        image_url: str = None,
        image_file: discord.Attachment = None
    ):
        """处理/fetch_upd命令，上传图片到本地"""
        if image_url and image_file:
            await interaction.response.send_message("❌ 请只提供图片URL或文件附件中的一种", ephemeral=True)
            return
        if not image_url and not image_file:
            await interaction.response.send_message("❌ 请提供图片URL或文件附件", ephemeral=True)
            return
            
        await fetch_upd_utils.upload_image(interaction, context, image_url, sender, image_file)

    @tree.command(name="fetch_del", description="删除指定图片文件")
    @app_commands.check(check_upload_auth)
    @app_commands.describe(
        filename="要删除的图片文件名"
    )
    @app_commands.autocomplete(filename=filename_autocomplete)
    async def fetch_del_command(
        interaction: discord.Interaction,
        filename: str
    ):
        """处理/fetch_del命令，删除指定图片文件"""
        await fetch_del_utils.delete_image(interaction, filename)
