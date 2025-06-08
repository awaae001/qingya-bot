import discord
import logging
import config
from datetime import datetime

logger = logging.getLogger(__name__)

async def send_to_discord(channels: dict, message: str, channel_id=None):
    """发送消息到 Discord 频道，使用Embed卡片格式
    Args:
        channels (dict): 包含 {channel_id: channel_object} 的字典
        message (str): 要发送的消息内容
        channel_id: 指定发送到哪个频道，None表示发送到配置的默认频道(特殊频道优先)
    """
    if not channels:
        logger.error("没有可用的 Discord 频道，无法发送消息")
        return

    target_channels = []
    if channel_id:
        # 发送到指定频道
        target_channel = channels.get(channel_id)
        if target_channel:
            target_channels.append(target_channel)
        else:
            logger.error(f"指定的频道ID {channel_id} 未在机器人配置中找到")
            return
    else:
        # 发送到默认频道 (优先特殊频道)
        special_channels = [
            channels[channel_id] 
            for channel_id in config.SPECIAL_CHANNELS 
            if channel_id in channels
        ]
        if special_channels:
            target_channels = special_channels
            logger.info(f"来自Telegram的消息将发送到特殊频道: {', '.join(str(c.id) for c in special_channels)}")
        else:
            # 如果未设置特殊频道或无效，则发送到所有频道 (按原逻辑)
            target_channels = list(channels.values())
            logger.info("未设置特殊频道或特殊频道无效，Telegram消息将发送到所有频道")

    if not target_channels:
         logger.error("计算后没有目标 Discord 频道，无法发送消息")
         return

    try:
        # 检查是否是自动转发的消息 (来自Telegram Bot的标记)
        is_forwarded = message.startswith("[自动转发]")
        clean_message = message.replace("[自动转发]", "").strip() if is_forwarded else message

        # 创建Embed卡片
        embed = discord.Embed(
            title="来自Telegram的消息" if is_forwarded else "消息", # 区分标题
            description=clean_message,
            color=discord.Color.blue()
        )

        # 解析消息中的链接 (简化处理，假设格式固定)
        image_url = None
        video_url = None
        file_info = None

        parts = clean_message.split("](")
        if len(parts) > 1:
            link_part = parts[0]
            url_part = parts[1].split(")")[0]
            if "[图片" in link_part:
                image_url = url_part
            elif "[视频" in link_part:
                video_url = url_part
            elif "[文件:" in link_part:
                file_name = link_part.split("[文件:")[1]
                file_info = {"name": file_name, "url": url_part}

        # 设置Embed内容
        if image_url:
            embed.set_image(url=image_url)
            # 从描述中移除图片标记文本，避免重复
            embed.description = embed.description.split("[图片](")[0].strip()
        if video_url:
            embed.add_field(name="视频", value=f"[点击查看]({video_url})", inline=False)
            embed.description = embed.description.split("[视频](")[0].strip()
        if file_info:
            embed.add_field(name="文件", value=f"[{file_info['name']}]({file_info['url']})", inline=False)
            embed.description = embed.description.split("[文件:")[0].strip()


        # 添加时间戳和来源
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        footer_text = f"{config.BOT_NAME} ·自动转发系统 | {timestamp}" if is_forwarded else f"{config.BOT_NAME} · 转发系统 | {timestamp}"
        embed.set_footer(text=footer_text)

        # 发送Embed卡片到所有目标频道
        sent_count = 0
        fail_count = 0
        for channel in target_channels:
            try:
                await channel.send(embed=embed)
                logger.info(f"Embed卡片已发送到 Discord 频道 {channel.name} ({channel.id})")
                sent_count += 1
            except Exception as e:
                logger.error(f"发送Embed到 Discord 频道 {channel.name} ({channel.id}) 失败: {e}")
                fail_count += 1
                # 如果Embed失败，尝试发送原始文本作为后备
                try:
                    fallback_message = f"**(Embed发送失败)**\n{message}"
                    await channel.send(fallback_message)
                    logger.warning(f"已回退到文本格式发送到频道 {channel.name} ({channel.id})")
                except Exception as fallback_e:
                    logger.error(f"文本格式回退发送到频道 {channel.name} ({channel.id}) 也失败: {fallback_e}")

        if fail_count > 0:
             logger.warning(f"有 {fail_count} 个频道发送失败")

    except Exception as e:
        logger.error(f"处理并发送消息到 Discord 时发生意外错误: {e}")
        # 尝试发送原始文本到第一个目标频道作为最终后备
        if target_channels:
            try:
                await target_channels[0].send(f"**(处理消息时出错，发送原始消息)**\n{message}")
                logger.warning(f"因处理错误，已发送原始消息到频道 {target_channels[0].name} ({target_channels[0].id})")
            except Exception as final_fallback_e:
                 logger.error(f"最终后备发送原始消息也失败: {final_fallback_e}")
