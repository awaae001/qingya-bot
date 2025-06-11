import discord
import asyncio
from discord import app_commands
import logging
import os
import uuid
import config
from datetime import datetime
import psutil
import time
import aiohttp
from .commands import text_command_utils,send_card_utils
from ..utils import file_utils,channel_utils
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
        """处理/del命令，删除机器人自己发送的消息"""
        try:
            parts = message_link.split('/')
            if len(parts) < 7 or parts[2] != 'discord.com' or parts[3] != 'channels':
                await interaction.response.send_message("❌ 无效的消息链接格式", ephemeral=True)
                return

            channel_id = int(parts[5])
            message_id = int(parts[6])

            # 尝试从缓存或API获取频道
            channel = bot_instance.get_channel(channel_id)
            if not channel:
                 try:
                     channel = await bot_instance.fetch_channel(channel_id)
                 except (discord.NotFound, discord.Forbidden):
                     await interaction.response.send_message("❌ 无法找到或访问该频道", ephemeral=True)
                     return

            if not isinstance(channel, discord.TextChannel):
                 await interaction.response.send_message("❌ 目标必须是文本频道", ephemeral=True)
                 return

            try:
                message = await channel.fetch_message(message_id)
            except discord.NotFound:
                await interaction.response.send_message("❌ 消息不存在或已被删除", ephemeral=True)
                return
            except discord.Forbidden:
                await interaction.response.send_message("❌ 没有权限访问该消息", ephemeral=True)
                return

            # 创建确认按钮
            confirm_button = discord.ui.Button(label="确认删除", style=discord.ButtonStyle.danger)
            cancel_button = discord.ui.Button(label="取消", style=discord.ButtonStyle.secondary)
            
            view = discord.ui.View()
            view.add_item(confirm_button)
            view.add_item(cancel_button)
            
            # 消息作者信息
            author_name = message.author.name
            
            # 定义按钮回调
            async def confirm_callback(interaction_confirm: discord.Interaction):
                try:
                    await message.delete()
                    await interaction_confirm.response.edit_message(content="✅ 消息已成功删除", view=None)
                    logger.info(f"用户 {interaction.user} 删除了消息 {message_id} 在频道 {channel_id}")
                except discord.Forbidden:
                    await interaction_confirm.response.edit_message(content="❌ 没有权限删除该消息", view=None)
                except Exception as e:
                    logger.error(f"删除消息时出错: {e}")
                    await interaction_confirm.response.edit_message(content=f"❌ 删除消息时出错: {e}", view=None)
            
            async def cancel_callback(interaction_cancel: discord.Interaction):
                await interaction_cancel.response.edit_message(content="❌ 已取消删除操作", view=None)
            
            # 设置回调
            confirm_button.callback = confirm_callback
            cancel_button.callback = cancel_callback
            
            # 创建嵌入式确认消息
            embed = discord.Embed(
                title="⚠️ 确认删除消息",
                description=f"您确定要删除来自 {author_name} 的消息吗？\n\n此操作无法撤销！",
                color=discord.Color.orange()
            )
            embed.set_footer(text=f"{config.BOT_NAME} ·自动转发系统丨消息ID: {message_id} | 频道ID: {channel_id}")
            
            # 发送嵌入式确认消息
            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True
            )

        except ValueError:
             await interaction.response.send_message("❌ 消息链接中的ID无效", ephemeral=True)
        except Exception as e:
            logger.error(f"删除消息时出错: {e}")
            await interaction.response.send_message(f"❌ 删除消息时出错: {e}", ephemeral=True)

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
        await interaction.response.defer(ephemeral=False)

        # 获取系统信息
        cpu_usage = psutil.cpu_percent()
        ram_usage = psutil.virtual_memory().percent

        # 获取本地图片数量
        image_count = 0
        image_dir_status = "OK"
        try:
            if os.path.exists(config.IMAGE_DIR):
                image_count = len([f for f in os.listdir(config.IMAGE_DIR) if os.path.isfile(os.path.join(config.IMAGE_DIR, f))])
            else:
                image_dir_status = "目录不存在"
                image_count = 0
        except Exception as e:
            logger.warning(f"无法读取图片目录 {config.IMAGE_DIR}: {e}")
            image_dir_status = f"读取错误 ({type(e).__name__})"
            image_count = "N/A"

        # 获取Discord延迟
        dc_latency = round(bot_instance.latency * 1000) if bot_instance.latency else "N/A" # 毫秒

        # 获取Telegram延迟 (通过直接HTTP GET)
        tg_latency_ms = "N/A"
        tg_status = "未配置"
        if config.TELEGRAM_BOT_TOKEN:
            tg_api_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getMe"
            try:
                async with aiohttp.ClientSession() as session:
                    start_time = time.monotonic()
                    # 增加超时时间
                    async with session.get(tg_api_url, timeout=15) as response:
                        # 检查状态码
                        if response.status == 200:
                             await response.json() # 确保读取响应体
                             end_time = time.monotonic()
                             tg_latency_ms = round((end_time - start_time) * 1000)
                             tg_status = "连接正常"
                        else:
                            logger.warning(f"测试Telegram API延迟失败: 状态码 {response.status}")
                            tg_latency_ms = f"错误 ({response.status})"
                            tg_status = f"API错误 ({response.status})"
            except aiohttp.ClientConnectorError as e:
                 logger.warning(f"测试Telegram API延迟失败: 连接错误 {e}")
                 tg_latency_ms = "连接错误"
                 tg_status = "连接失败"
            except asyncio.TimeoutError:
                 logger.warning("测试Telegram API延迟失败: 请求超时")
                 tg_latency_ms = "超时"
                 tg_status = "连接超时"
            except Exception as e:
                logger.warning(f"测试Telegram API延迟失败: {e}")
                tg_latency_ms = "未知错误"
                tg_status = f"测试出错 ({type(e).__name__})"
        else:
             tg_latency_ms = "未配置Token"


        # 创建Embed消息
        embed = discord.Embed(
            title="📊 系统与机器人状态",
            color=discord.Color.blue()
        )
        embed.add_field(name="🖥️ 主机 CPU", value=f"{cpu_usage}%", inline=True)
        embed.add_field(name="🧠 主机 RAM", value=f"{ram_usage}%", inline=True)
        embed.add_field(name=" ", value=" ", inline=True) # 占位符对齐

        embed.add_field(name="<:logosdiscordicon:1381133861874044938> Discord 延迟", value=f"{dc_latency} ms" if isinstance(dc_latency, int) else dc_latency, inline=True)
        embed.add_field(name="<:logostelegram:1381134304729370634> Telegram 状态", value=tg_status, inline=True)
        embed.add_field(name="<:logostelegram:1381134304729370634> TG 延迟", value=f"{tg_latency_ms} ms" if isinstance(tg_latency_ms, int) else tg_latency_ms, inline=True)

        embed.add_field(name="🖼️ 本地图片数", value=str(image_count), inline=True)
        embed.add_field(name="📂 图片目录状态", value=image_dir_status, inline=True)
        embed.add_field(name=" ", value=" ", inline=True) # 占位符对齐


        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z") # 添加时区信息
        embed.set_footer(text=f"{config.BOT_NAME} · 自动转发系统丨查询时间: {timestamp}")

        await interaction.followup.send(embed=embed)
        logger.info(f"用户 {interaction.user} 查询了状态")
