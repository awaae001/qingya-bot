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
from .utils import channel_utils,file_utils

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
        channel_ids="要发送到的频道ID(多个用逗号分隔, 可选, 优先于转发模式)",
        content="消息内容",
        image_file="附加图片文件(可选)",
        forward_to_tg="是否转发到Telegram(默认否)",
        forward_mode="转发模式(当未指定频道ID时生效)"
    )
    @app_commands.choices(forward_mode=[
        app_commands.Choice(name="不转发到特殊频道", value=0),
        app_commands.Choice(name="转发到所有频道", value=1),
        app_commands.Choice(name="只转发到特殊频道", value=2)
    ])
    async def text_command(
        interaction: discord.Interaction,
        channel_ids: str = None, # 修改为字符串类型的 channel_ids
        content: str = None,
        image_file: discord.Attachment = None,
        forward_to_tg: bool = False,
        forward_mode: int = 0
    ):
        """处理/text命令，发送文本和可选图片到指定(ID)或所有频道和Telegram"""
        await interaction.response.send_message("正在处理请求...", ephemeral=True) # 初始响应

        target_channels, parse_errors = await channel_utils.parse_and_fetch_channels(bot_instance, channel_ids)


        local_image_path = None
        discord_file_to_send = None
        if image_file:
            local_image_path, discord_file_to_send = await file_utils.save_uploaded_file(
                image_file, 
                config.IMAGE_DIR
            )
            if not local_image_path:
                await interaction.edit_original_response(content="❌ 处理上传的图片时出错。")
                return

        sent_to_channels = 0
        failed_channels = 0
        sent_channel_mentions = []
        failed_channel_mentions = []

        # 如果指定了频道ID并找到了有效的频道
        if target_channels:
            logger.info(f"准备发送消息到 {len(target_channels)} 个指定频道")
            await interaction.edit_original_response(content=f"正在发送到 {len(target_channels)} 个指定频道...") # 更新状态
            for target_channel_obj in target_channels: # 避免覆盖外部变量名
                try:
                    file_to_send_this_time = None
                    if local_image_path:
                        # 每次发送都需要重新创建 File 对象
                        file_to_send_this_time = discord.File(local_image_path, filename=image_file.filename)

                    await target_channel_obj.send(content=content if content else None, file=file_to_send_this_time)
                    logger.info(f"消息成功发送到指定频道 {target_channel_obj.id} ({target_channel_obj.name})")
                    sent_to_channels += 1
                    sent_channel_mentions.append(target_channel_obj.mention)

                    if file_to_send_this_time:
                        file_to_send_this_time.close()
                except discord.Forbidden:
                    logger.error(f"无权发送消息到指定频道 {target_channel_obj.id} ({target_channel_obj.name})")
                    failed_channels += 1
                    failed_channel_mentions.append(f"{target_channel_obj.mention} (无权限)")
                    if 'file_to_send_this_time' in locals() and file_to_send_this_time:
                        file_to_send_this_time.close()
                except Exception as e:
                    logger.error(f"消息发送到指定频道 {target_channel_obj.id} ({target_channel_obj.name}) 失败: {e}")
                    failed_channels += 1
                    failed_channel_mentions.append(f"{target_channel_obj.mention} (发送失败)")
                    if 'file_to_send_this_time' in locals() and file_to_send_this_time:
                        file_to_send_this_time.close()
        elif not channel_ids: # 只有在未提供 channel_ids 时才执行 forward_mode 逻辑
            # 如果未指定频道ID，则按原有逻辑发送
            logger.info(f"未指定频道ID，准备按转发模式发送消息到 {len(bot_instance.channels)} 个Discord频道 (模式: {forward_mode})")
            await interaction.edit_original_response(content=f"正在按转发模式 `{forward_mode}` 发送...") # 更新状态
            for channel_id, current_channel in bot_instance.channels.items():
                should_send = False
                # 检查是否为特殊频道
                is_special = config.SPECIAL_CHANNELS and channel_id in config.SPECIAL_CHANNELS

                if is_special:
                    if forward_mode == 1 or forward_mode == 2: # 转发到所有或只转发到特殊
                        should_send = True
                    else: # forward_mode == 0 (不转发到特殊)
                        logger.debug(f"跳过特殊频道 {channel_id} ({current_channel.name})，因为 forward_mode=0")
                        continue
                elif forward_mode != 2: # 不是 "只转发到特殊频道" 模式，则发送到非特殊频道
                    should_send = True
                else: # forward_mode == 2 (只转发到特殊)，跳过非特殊频道
                    logger.debug(f"跳过非特殊频道 {channel_id} ({current_channel.name})，因为 forward_mode=2")
                    continue


                if should_send:
                    try:
                        file_to_send_this_time = None
                        if local_image_path:
                            # 每次循环都需要重新创建 File 对象
                            file_to_send_this_time = discord.File(local_image_path, filename=image_file.filename)

                        await current_channel.send(content=content if content else None, file=file_to_send_this_time)
                        logger.info(f"消息成功发送到频道 {channel_id} ({current_channel.name})")
                        sent_to_channels += 1

                        # 发送成功后关闭文件句柄
                        if file_to_send_this_time:
                            file_to_send_this_time.close()

                    except Exception as e:
                        logger.error(f"消息发送到频道 {channel_id} ({current_channel.name}) 失败: {e}")
                        failed_channels += 1
                        # 发送失败也要关闭文件句柄
                        if 'file_to_send_this_time' in locals() and file_to_send_this_time:
                            file_to_send_this_time.close()

        # 发送到Telegram(如果启用且配置允许)
        tg_sent_status = ""
        # 检查全局开关、命令参数和TG Token配置
        if config.FORWARD_DC_TO_TG and forward_to_tg and bot_instance.telegram_bot and config.TELEGRAM_BOT_TOKEN:
            try:
                await bot_instance.telegram_bot.send_to_telegram(
                    message=content,
                    image_path=local_image_path
                )
                tg_sent_status = " 和Telegram"
                logger.info("消息已转发到Telegram")
            except Exception as e:
                logger.error(f"转发到Telegram失败: {e}")
                tg_sent_status = " 但转发到Telegram失败"
        elif forward_to_tg: # 如果用户想转发但配置不允许或未配置TG
            if not config.FORWARD_DC_TO_TG:
                tg_sent_status = " (TG转发已禁用)"
                logger.warning("用户尝试转发到TG，但全局配置 FORWARD_DC_TO_TG 已禁用")
            elif not config.TELEGRAM_BOT_TOKEN:
                 tg_sent_status = " (TG未配置)"
                 logger.warning("用户尝试转发到TG，但Telegram Token未配置")


        # 构建最终响应消息
        content_type = "消息和图片" if image_file else "消息"
        final_response = channel_utils.build_response_message(
            content_type,
            sent_to_channels,
            failed_channels,
            sent_channel_mentions,
            failed_channel_mentions,
            parse_errors,
            channel_ids,
            forward_mode,
            tg_sent_status
        )

        await interaction.edit_original_response(content=final_response)


    @tree.command(name="send", description="发送Embed消息到指定频道(ID)或所有频道")
    @app_commands.check(check_auth)
    @app_commands.describe(
        channel_ids="要发送到的频道ID(多个用逗号分隔, 可选, 优先于转发模式)",
        title="消息标题 (默认为空)",
        content="消息内容（可选）",
        image_file="上传图片文件(可选)",
        forward_to_tg="是否转发到Telegram(默认否)",
        forward_mode="转发模式(当未指定频道ID时生效)"
    )
    @app_commands.choices(forward_mode=[
        app_commands.Choice(name="不转发到特殊频道", value=0),
        app_commands.Choice(name="转发到所有频道", value=1),
        app_commands.Choice(name="只转发到特殊频道", value=2)
    ])
    async def send_command(
        interaction: discord.Interaction,
        channel_ids: str = None, # 修改为字符串类型的 channel_ids
        title: str = "\u200b", # 默认零宽空格
        content: str = None,
        image_file: discord.Attachment = None,
        forward_to_tg: bool = False,
        forward_mode: int = 0
    ):
        """处理/send命令，发送Embed消息到指定(ID)或所有频道和Telegram"""
        await interaction.response.send_message("正在处理请求...", ephemeral=True) # 初始响应

        target_channels, parse_errors = await channel_utils.parse_and_fetch_channels(bot_instance, channel_ids)

        local_image_path = None
        image_url_for_embed = None 
        if image_file:
            local_image_path, _ = await file_utils.save_uploaded_file(
                image_file, 
                config.IMAGE_DIR
            )
            if not local_image_path:
                await interaction.edit_original_response(content="❌ 处理上传的图片时出错。")
                return
            image_url_for_embed = image_file.url

        embed = discord.Embed(
            title=title,
            color=discord.Color.green()
        )
        if content:
            embed.description = content
        if image_url_for_embed:
            embed.set_image(url=image_url_for_embed)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        embed.set_footer(text=f"{config.BOT_NAME} ·自动转发系统|发送时间: {timestamp}")

        sent_to_channels = 0
        failed_channels = 0
        sent_channel_mentions = []
        failed_channel_mentions = []

        target_channels, parse_errors = await channel_utils.parse_and_fetch_channels(bot_instance, channel_ids)

        # 如果指定了频道ID并找到了有效的频道
        if target_channels:
            logger.info(f"准备发送Embed到 {len(target_channels)} 个指定频道")
            await interaction.edit_original_response(content=f"正在发送Embed到 {len(target_channels)} 个指定频道...") # 更新状态
            for target_channel_obj in target_channels: # 避免覆盖外部变量名
                try:
                    await target_channel_obj.send(embed=embed)
                    logger.info(f"Embed成功发送到指定频道 {target_channel_obj.id} ({target_channel_obj.name})")
                    sent_to_channels += 1
                    sent_channel_mentions.append(target_channel_obj.mention)
                except discord.Forbidden:
                    logger.error(f"无权发送Embed到指定频道 {target_channel_obj.id} ({target_channel_obj.name})")
                    failed_channels += 1
                    failed_channel_mentions.append(f"{target_channel_obj.mention} (无权限)")
                except Exception as e:
                    logger.error(f"Embed发送到指定频道 {target_channel_obj.id} ({target_channel_obj.name}) 失败: {e}")
                    failed_channels += 1
                    failed_channel_mentions.append(f"{target_channel_obj.mention} (发送失败)")
        elif not channel_ids: # 只有在未提供 channel_ids 时才执行 forward_mode 逻辑
            # 如果未指定频道ID，则按原有逻辑发送
            logger.info(f"未指定频道ID，准备按转发模式发送Embed到 {len(bot_instance.channels)} 个Discord频道 (模式: {forward_mode})")
            await interaction.edit_original_response(content=f"正在按转发模式 `{forward_mode}` 发送Embed...") # 更新状态
            for channel_id, current_channel in bot_instance.channels.items():
                should_send = False
                # 检查是否为特殊频道
                is_special = config.SPECIAL_CHANNELS and channel_id in config.SPECIAL_CHANNELS

                if is_special:
                    if forward_mode == 1 or forward_mode == 2:
                        should_send = True
                    else: # forward_mode == 0 (不转发到特殊)
                        logger.debug(f"跳过特殊频道 {channel_id} ({current_channel.name})")
                        continue
                elif forward_mode != 2: # 不是 "只转发到特殊频道" 模式，则发送到非特殊频道
                    should_send = True
                else: # forward_mode == 2 (只转发到特殊)，跳过非特殊频道
                    logger.debug(f"跳过非特殊频道 {channel_id} ({current_channel.name})")
                    continue

                if should_send:
                    try:
                        await current_channel.send(embed=embed)
                        logger.info(f"Embed成功发送到频道 {channel_id} ({current_channel.name})")
                        sent_to_channels += 1
                    except Exception as e:
                        logger.error(f"Embed发送到频道 {channel_id} ({current_channel.name}) 失败: {e}")
                        failed_channels += 1

        # 发送到Telegram(如果启用且配置允许)
        tg_sent_status = ""
        # 检查全局开关、命令参数和TG Token配置
        if config.FORWARD_DC_TO_TG and forward_to_tg and bot_instance.telegram_bot and config.TELEGRAM_BOT_TOKEN:
            tg_caption = f"{title}\n{content}" if content else title
            if tg_caption == "\u200b":
                tg_caption = None # 如果只有默认标题，TG不发送文本

            try:
                await bot_instance.telegram_bot.send_to_telegram(
                    message=tg_caption,
                    image_path=local_image_path # 传递本地路径给TG
                )
                tg_sent_status = " 和Telegram"
                logger.info("Embed消息内容已转发到Telegram")
            except Exception as e:
                logger.error(f"转发Embed消息到Telegram失败: {e}")
                tg_sent_status = " 但转发到Telegram失败"
        elif forward_to_tg: # 如果用户想转发但配置不允许或未配置TG
            if not config.FORWARD_DC_TO_TG:
                tg_sent_status = " (TG转发已禁用)"
                logger.warning("用户尝试转发Embed到TG，但全局配置 FORWARD_DC_TO_TG 已禁用")
            elif not config.TELEGRAM_BOT_TOKEN:
                 tg_sent_status = " (TG未配置)"
                 logger.warning("用户尝试转发Embed到TG，但Telegram Token未配置")

        # 构建最终响应消息
        final_response = channel_utils.build_response_message(
            "Embed",
            sent_to_channels,
            failed_channels,
            sent_channel_mentions,
            failed_channel_mentions,
            parse_errors,
            channel_ids,
            forward_mode,
            tg_sent_status
        )

        await interaction.edit_original_response(content=final_response)


    @tree.command(name="del", description="（敏感）删除机器人发送的消息")
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

            if message.author.id != bot_instance.user.id:
                await interaction.response.send_message("❌ 只能删除机器人自己发送的消息", ephemeral=True)
                return

            await message.delete()
            await interaction.response.send_message("✅ 消息已成功删除", ephemeral=True)
            logger.info(f"用户 {interaction.user} 删除了消息 {message_id} 在频道 {channel_id}")

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
