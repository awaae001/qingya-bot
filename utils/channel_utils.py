"""Discord频道工具函数"""
import discord
import logging
from typing import Set, List, Tuple, Optional, Union

logger = logging.getLogger(__name__)

def parse_channel_ids(channel_ids_str: Optional[str]) -> Tuple[Set[int], List[str]]:
    """解析逗号分隔的频道ID字符串"""
    parsed_ids = set()
    parse_errors = []
    if not channel_ids_str:
        return parsed_ids, parse_errors

    id_list = [id_str.strip() for id_str in channel_ids_str.split(',') if id_str.strip()]
    logger.debug(f"解析频道ID列表: {id_list}")
    
    for channel_id_str in id_list:
        try:
            parsed_ids.add(int(channel_id_str))
        except ValueError:
            error_msg = f"🔢 无效的频道ID格式: `{channel_id_str}`"
            logger.warning(f"无效的频道ID格式: {channel_id_str}")
            parse_errors.append(error_msg)

    return parsed_ids, parse_errors

async def fetch_channels_from_ids(
    bot_instance, 
    channel_ids_set: Set[int]
) -> List[Union[discord.TextChannel, discord.Thread]]:
    """根据频道ID集合获取有效的频道对象"""
    target_channels = []
    if not channel_ids_set:
        return target_channels

    logger.debug(f"从 {len(channel_ids_set)} 个ID获取频道对象")
    
    for channel_id in channel_ids_set:
        try:
            channel = bot_instance.get_channel(channel_id)
            if not channel:
                channel = await bot_instance.fetch_channel(channel_id)
                logger.debug(f"从API获取频道: {channel.name} ({channel.id})")

            if isinstance(channel, (discord.TextChannel, discord.Thread)):
                target_channels.append(channel)
            else:
                logger.warning(f"频道ID {channel_id} 不是文本频道或子区")
                
        except (discord.NotFound, discord.Forbidden):
            logger.warning(f"无法访问频道ID: {channel_id}")
        except Exception as e:
            logger.error(f"处理频道ID {channel_id} 时出错: {e}")

    return target_channels

async def prepare_target_channels(
    bot_instance, 
    channel_ids, 
    channel_id_mode, 
    forward_mode, 
    config
):
    """准备目标频道集合"""
    # 获取特殊频道ID集合
    special_channel_ids = set()
    if isinstance(config.SPECIAL_CHANNELS, list):
        special_channel_ids = {int(id) for id in config.SPECIAL_CHANNELS}
    elif isinstance(config.SPECIAL_CHANNELS, str):
        special_channel_ids = {
            int(id_str.strip()) 
            for id_str in config.SPECIAL_CHANNELS.split(',') 
            if id_str.strip()
        }

    # 获取所有文本频道ID
    all_channel_ids = {
        id for id, ch in bot_instance.channels.items()
        if isinstance(ch, (discord.TextChannel, discord.Thread))
    }

    # 解析用户指定的频道ID
    parsed_target_ids, parse_errors = parse_channel_ids(channel_ids)

    # 根据转发模式确定基础频道集合
    if forward_mode == 0:  # 不转发到特殊频道
        base_channel_ids = all_channel_ids - special_channel_ids
    elif forward_mode == 1:  # 转发到所有频道
        base_channel_ids = all_channel_ids
    else:  # 只转发到特殊频道
        base_channel_ids = special_channel_ids

    # 根据频道ID模式确定最终目标
    if channel_id_mode == 'none':
        final_ids = parsed_target_ids if parsed_target_ids else base_channel_ids
    elif channel_id_mode == 'and':
        final_ids = base_channel_ids.union(parsed_target_ids)
    else:  # 'ban'模式
        final_ids = base_channel_ids.difference(parsed_target_ids)

    return await fetch_channels_from_ids(bot_instance, final_ids), parse_errors

async def build_response_message(
    bot_instance,
    content_type,
    sent_to_channels,
    failed_channels,
    sent_channel_mentions,
    failed_channel_mentions,
    parse_errors,
    channel_ids,
    forward_mode,
    tg_sent_status,
    channel_id_mode="none",
    config=None
):
    """构建响应消息"""
    response_parts = []
    
    # 模式描述
    mode_map = {
        'none': f"频道ID模式: none (仅指定ID)" if channel_ids 
                else f"转发模式: {forward_mode} (未指定ID)",
        'and': f"频道ID模式: and (转发模式 {forward_mode} + 指定ID)",
        'ban': f"频道ID模式: ban (转发模式 {forward_mode} - 指定ID)"
    }
    mode_description = mode_map.get(channel_id_mode, 
        f"指定频道模式 (IDs: {channel_ids})" if channel_ids 
        else f"转发模式: {forward_mode}")

    # 成功发送信息
    if sent_to_channels > 0:
        success_msg = f"✅ {content_type}已发送到 {sent_to_channels} 个频道 ({mode_description})"
        response_parts.append(success_msg)
        
        if sent_channel_mentions:
            display_count = min(10, len(sent_channel_mentions))
            mentions = ', '.join(sent_channel_mentions[:display_count])
            if len(sent_channel_mentions) > display_count:
                mentions += f", 等另外 {len(sent_channel_mentions)-display_count} 个"
            response_parts.append(f"   - 成功频道: {mentions}")

    # 失败信息
    if failed_channels > 0:
        fail_msg = f"❌ 发送到 {failed_channels} 个频道失败:"
        response_parts.append(fail_msg)
        
        if failed_channel_mentions:
            display_count = min(10, len(failed_channel_mentions))
            mentions = ', '.join(failed_channel_mentions[:display_count])
            if len(failed_channel_mentions) > display_count:
                mentions += f", 等另外 {len(failed_channel_mentions)-display_count} 个"
            response_parts.append(f"   - 失败详情: {mentions}")

    # 解析错误
    if parse_errors:
        error_count = min(5, len(parse_errors))
        errors = "\n- ".join(parse_errors[:error_count])
        if len(parse_errors) > error_count:
            errors += f"\n- ...等另外 {len(parse_errors)-error_count} 个错误"
        response_parts.append(f"⚠️ 解析错误:\n- {errors}")

    # Telegram状态
    if tg_sent_status and tg_sent_status.strip():
        response_parts.append(f"Telegram 状态: {tg_sent_status.strip()}")

    # 构建最终响应
    response = "\n".join(response_parts).strip()
    if not response:
        response = "ℹ️ 操作完成，无状态信息"
    elif len(response) > 2000:
        response = response[:1997] + "..."

    # 发送到日志频道
    if config and hasattr(config, 'LOG_CHANNELS') and config.LOG_CHANNELS:
        for channel_id in config.LOG_CHANNELS:
            try:
                channel = bot_instance.get_channel(channel_id)
                if not channel:
                    channel = await bot_instance.fetch_channel(channel_id)
                if isinstance(channel, (discord.TextChannel, discord.Thread)):
                    await channel.send(response)
            except Exception as e:
                logger.error(f"发送日志到频道 {channel_id} 失败: {e}")

    return response
