import discord
import logging
from datetime import datetime
from ...utils import channel_utils, file_utils
import config

logger = logging.getLogger(__name__)

async def handle_send_command(
    interaction: discord.Interaction,
    bot_instance, 
    channel_ids: str = None,
    channel_id_mode: str = "none",  # 新增参数
    title: str = "\u200b",  # 默认零宽空格
    content: str = None,
    image_file: discord.Attachment = None,
    forward_to_tg: bool = False,
    forward_mode: int = 0
):
    """处理/send命令，根据模式发送Embed消息到频道和Telegram"""
    await interaction.response.send_message("正在处理请求...", ephemeral=True)  # 初始响应

    # 准备目标频道
    target_channels, parse_errors = await channel_utils.prepare_target_channels(
        bot_instance, 
        channel_ids, 
        channel_id_mode, 
        forward_mode, 
        config
    )
    logger.info(f"最终将尝试发送Embed到 {len(target_channels)} 个频道")

    # 5. 处理图片和创建Embed
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
        # 使用 discord.Attachment.url 作为 Embed 图片 URL
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
    embed.set_footer(text=f"{config.BOT_NAME} ·自动转发系统 | 发送时间: {timestamp}")

    # 6. 发送Embed到目标频道
    sent_to_channels = 0
    failed_channels = 0
    sent_channel_mentions = []
    failed_channel_mentions = []

    if not target_channels:
        logger.warning("没有找到任何有效的目标频道来发送Embed。")
        await interaction.edit_original_response(content="⚠️ 没有找到任何有效的目标频道。请检查频道ID或转发模式。")
    else:
        logger.info(f"准备发送Embed到 {len(target_channels)} 个最终目标频道")
        await interaction.edit_original_response(
            content=f"正在发送Embed到 {len(target_channels)} 个目标频道 (模式: {channel_id_mode})..."
        )  # 更新状态

        for target_channel_obj in target_channels:
            try:
                await target_channel_obj.send(embed=embed)
                logger.info(
                    f"Embed成功发送到频道 {target_channel_obj.id} ({target_channel_obj.name})"
                )
                sent_to_channels += 1
                sent_channel_mentions.append(target_channel_obj.mention)
            except discord.Forbidden:
                logger.error(
                    f"无权发送Embed到频道 {target_channel_obj.id} ({target_channel_obj.name})"
                )
                failed_channels += 1
                failed_channel_mentions.append(f"{target_channel_obj.mention} (无权限)")
            except Exception as e:
                logger.error(
                    f"Embed发送到频道 {target_channel_obj.id} ({target_channel_obj.name}) 失败: {e}"
                )
                failed_channels += 1
                failed_channel_mentions.append(f"{target_channel_obj.mention} (发送失败)")

    # 7. 发送到Telegram(如果启用且配置允许)
    tg_sent_status = ""
    # 检查全局开关、命令参数和TG Token配置
    if config.FORWARD_DC_TO_TG and forward_to_tg and bot_instance.telegram_bot and config.TELEGRAM_BOT_TOKEN:
        tg_caption = f"{title}\n{content}" if content else title
        if tg_caption == "\u200b":  # 如果只有默认标题，TG不发送文本
            tg_caption = None

        try:
            await bot_instance.telegram_bot.send_to_telegram(
                message=tg_caption,
                image_path=local_image_path  # 传递本地路径给TG
            )
            tg_sent_status = " 和Telegram"
            logger.info("Embed消息内容已转发到Telegram")
        except Exception as e:
            logger.error(f"转发Embed消息到Telegram失败: {e}")
            tg_sent_status = " 但转发到Telegram失败"
    elif forward_to_tg:  # 如果用户想转发但配置不允许或未配置TG
        if not config.FORWARD_DC_TO_TG:
            tg_sent_status = " (TG转发已禁用)"
            logger.warning("用户尝试转发Embed到TG，但全局配置 FORWARD_DC_TO_TG 已禁用")
        elif not config.TELEGRAM_BOT_TOKEN:
            tg_sent_status = " (TG未配置)"
            logger.warning("用户尝试转发Embed到TG，但Telegram Token未配置")

    # 8. 构建最终响应消息
    final_response = channel_utils.build_response_message(
        "Embed",
        sent_to_channels,
        failed_channels,
        sent_channel_mentions,
        failed_channel_mentions,
        parse_errors,
        channel_ids,
        forward_mode,
        tg_sent_status,
        channel_id_mode  # 添加新参数
    )

    await interaction.edit_original_response(content=final_response)
