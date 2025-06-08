"""频道相关工具函数"""
import discord
import logging

logger = logging.getLogger(__name__)

async def parse_and_fetch_channels(bot_instance, channel_ids: str = None):
    target_channels = []
    parse_errors = []  # 存储解析和查找频道时的错误信息

    if channel_ids:
        id_list = [id_str.strip() for id_str in channel_ids.split(',') if id_str.strip()]
        logger.info(f"收到指定频道ID列表: {id_list}")
        for channel_id_str in id_list:
            try:
                channel_id_int = int(channel_id_str)
                # 尝试从缓存获取
                channel = bot_instance.get_channel(channel_id_int)
                if not channel:
                    # 缓存未命中，尝试从API获取
                    try:
                        logger.debug(f"缓存未命中，尝试从API获取频道: {channel_id_int}")
                        channel = await bot_instance.fetch_channel(channel_id_int)
                        logger.debug(f"成功从API获取频道: {channel.name} ({channel.id})")
                    except discord.NotFound:
                        logger.warning(f"找不到频道ID: {channel_id_str}")
                        parse_errors.append(f"❓ 未找到频道ID: `{channel_id_str}`")
                        continue
                    except discord.Forbidden:
                        logger.warning(f"无权访问频道ID: {channel_id_str}")
                        parse_errors.append(f"🚫 无权访问频道ID: `{channel_id_str}`")
                        continue
                    except Exception as e:
                        logger.error(f"获取频道 {channel_id_str} 时发生未知错误: {e}")
                        parse_errors.append(f"⚠️ 获取频道 `{channel_id_str}` 时出错")
                        continue

                # 检查是否是文本频道
                if isinstance(channel, discord.TextChannel):
                    target_channels.append(channel)
                else:
                    logger.warning(f"频道ID {channel_id_str} 不是文本频道，跳过")
                    parse_errors.append(f"❌ `{channel_id_str}` 不是文本频道")
            except ValueError:
                logger.warning(f"无效的频道ID格式: {channel_id_str}")
                parse_errors.append(f"🔢 无效的频道ID格式: `{channel_id_str}`")

        if not target_channels and not parse_errors:  # 如果提供了ID但一个都没找到，且没有其他解析错误
            parse_errors.append("提供的所有频道ID均无效或无法访问。")
        elif not target_channels and parse_errors:  # 如果有错误导致没有目标频道
            logger.info("因频道ID解析错误，未找到有效的目标频道。")
        else:
            logger.info(f"已解析出 {len(target_channels)} 个有效的目标频道。")

    return target_channels, parse_errors

def build_response_message(content_type, sent_to_channels, failed_channels, 
                         sent_channel_mentions, failed_channel_mentions,
                         parse_errors, channel_ids, forward_mode, tg_sent_status):
    """构建统一的响应消息"""
    response_parts = []

    if channel_ids:  # 如果是指定频道模式
        if sent_to_channels > 0:
            response_parts.append(f"✅ {content_type}已成功发送到 {sent_to_channels} 个频道: {', '.join(sent_channel_mentions)}")
        if failed_channels > 0:
            response_parts.append(f"❌ 发送到 {failed_channels} 个频道失败: {', '.join(failed_channel_mentions)}")
        if parse_errors:
            response_parts.append(f"⚠️ 解析频道ID时遇到问题:\n- " + "\n- ".join(parse_errors))
        if not sent_channel_mentions and not failed_channel_mentions and not parse_errors:  # 输入了ID但都是无效的
            response_parts.append(f"❌ 未找到任何有效的频道进行发送。")

    else:  # 如果是转发模式
        response_parts.append(f"{content_type}已发送到 {sent_to_channels} 个频道 (模式: {forward_mode})")
        if failed_channels > 0:
            response_parts.append(f"发送到 {failed_channels} 个频道失败。")

    # 添加TG状态
    if tg_sent_status:
        response_parts.append(f"Telegram 状态: {tg_sent_status.strip()}")

    final_response = "\n".join(response_parts)
    if len(final_response) > 2000:  # Discord 消息长度限制
        final_response = final_response[:1997] + "..."

    return final_response
