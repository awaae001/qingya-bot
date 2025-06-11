import discord
import logging
from typing import Tuple, List, Optional
from ...utils import channel_utils, file_utils
import config

logger = logging.getLogger(__name__)

async def handle_text_command(
    interaction: discord.Interaction,
    bot_instance,
    channel_ids: Optional[str],
    channel_id_mode: str,
    content: Optional[str],
    image_file: Optional[discord.Attachment],
    forward_to_tg: bool,
    forward_mode: int
) -> str:

    await interaction.response.send_message("正在处理请求...", ephemeral=True)

    # 准备目标频道
    target_channels, parse_errors = await channel_utils.prepare_target_channels(
        bot_instance, 
        channel_ids, 
        channel_id_mode, 
        forward_mode, 
        config
    )

    # 处理图片
    local_image_path = None
    if image_file:
        local_image_path, _ = await file_utils.save_uploaded_file(
            image_file,
            config.IMAGE_DIR
        )
        if not local_image_path:
            await interaction.edit_original_response(content="❌ 处理上传的图片时出错。")
            return "❌ 处理上传的图片时出错。"

    # 发送消息到目标频道
    sent_to_channels = 0
    failed_channels = 0
    sent_channel_mentions = []
    failed_channel_mentions = []

    if not target_channels:
        logger.warning("没有找到任何有效的目标频道来发送消息。")
        await interaction.edit_original_response(content="⚠️ 没有找到任何有效的目标频道。请检查频道ID或转发模式。")
        return "⚠️ 没有找到任何有效的目标频道。请检查频道ID或转发模式。"
    
    logger.info(f"准备发送消息到 {len(target_channels)} 个最终目标频道")
    await interaction.edit_original_response(content=f"正在发送到 {len(target_channels)} 个目标频道 (模式: {channel_id_mode})...")

    for target_channel_obj in target_channels:
        try:
            file_to_send_this_time = None
            if local_image_path:
                file_to_send_this_time = discord.File(local_image_path, filename=image_file.filename)

            await target_channel_obj.send(content=content if content else None, file=file_to_send_this_time)
            logger.info(f"消息成功发送到频道 {target_channel_obj.id} ({target_channel_obj.name})")
            sent_to_channels += 1
            sent_channel_mentions.append(target_channel_obj.mention)

            if file_to_send_this_time:
                file_to_send_this_time.close()
        except discord.Forbidden:
            logger.error(f"无权发送消息到频道 {target_channel_obj.id} ({target_channel_obj.name})")
            failed_channels += 1
            failed_channel_mentions.append(f"{target_channel_obj.mention} (无权限)")
            if 'file_to_send_this_time' in locals() and file_to_send_this_time:
                file_to_send_this_time.close()
        except Exception as e:
            logger.error(f"消息发送到频道 {target_channel_obj.id} ({target_channel_obj.name}) 失败: {e}")
            failed_channels += 1
            failed_channel_mentions.append(f"{target_channel_obj.mention} (发送失败)")
            if 'file_to_send_this_time' in locals() and file_to_send_this_time:
                file_to_send_this_time.close()

    # 发送到Telegram
    tg_sent_status = ""
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
    elif forward_to_tg:
        if not config.FORWARD_DC_TO_TG:
            tg_sent_status = " (TG转发已禁用)"
            logger.warning("用户尝试转发到TG，但全局配置 FORWARD_DC_TO_TG 已禁用")
        elif not config.TELEGRAM_BOT_TOKEN:
            tg_sent_status = " (TG未配置)"
            logger.warning("用户尝试转发到TG，但Telegram Token未配置")

    # 构建最终响应
    content_type = "消息和图片" if image_file else "消息"
    return channel_utils.build_response_message(
        content_type,
        sent_to_channels,
        failed_channels,
        sent_channel_mentions,
        failed_channel_mentions,
        parse_errors,
        channel_ids,
        forward_mode,
        tg_sent_status,
        channel_id_mode
    )
