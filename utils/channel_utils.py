"""频道相关工具函数"""
import discord
import logging
from typing import Set, List, Tuple, Optional

logger = logging.getLogger(__name__)

def parse_channel_ids(channel_ids_str: Optional[str]) -> Tuple[Set[int], List[str]]:
    """
    解析逗号分隔的频道ID字符串。

    Args:
        channel_ids_str: 逗号分隔的频道ID字符串，或None。

    Returns:
        一个包含有效频道ID整数的集合，以及一个包含解析错误信息的列表。
    """
    parsed_ids: Set[int] = set()
    parse_errors: List[str] = []
    if not channel_ids_str:
        return parsed_ids, parse_errors

    id_list = [id_str.strip() for id_str in channel_ids_str.split(',') if id_str.strip()]
    logger.info(f"收到待解析的频道ID列表: {id_list}")
    for channel_id_str in id_list:
        try:
            channel_id_int = int(channel_id_str)
            parsed_ids.add(channel_id_int)
        except ValueError:
            logger.warning(f"无效的频道ID格式: {channel_id_str}")
            parse_errors.append(f"🔢 无效的频道ID格式: `{channel_id_str}`")

    logger.info(f"解析出 {len(parsed_ids)} 个潜在有效的频道ID。")
    return parsed_ids, parse_errors

async def fetch_channels_from_ids(bot_instance, channel_ids_set: Set[int]) -> List[discord.TextChannel]:
    """
    根据提供的频道ID集合获取有效的TextChannel对象列表。

    Args:
        bot_instance: Discord 机器人实例。
        channel_ids_set: 包含频道ID整数的集合。

    Returns:
        一个包含有效discord.TextChannel对象的列表。
        (注意：此函数不返回查找错误，错误应在调用处处理或由 parse_channel_ids 返回)
    """
    target_channels: List[discord.TextChannel] = []
    if not channel_ids_set:
        return target_channels

    logger.info(f"准备从 {len(channel_ids_set)} 个ID获取频道对象。")
    for channel_id_int in channel_ids_set:
        channel = None
        try:
            # 尝试从缓存获取
            channel = bot_instance.get_channel(channel_id_int)
            if not channel:
                # 缓存未命中，尝试从API获取
                try:
                    logger.debug(f"缓存未命中，尝试从API获取频道: {channel_id_int}")
                    channel = await bot_instance.fetch_channel(channel_id_int)
                    logger.debug(f"成功从API获取频道: {channel.name} ({channel.id})")
                except (discord.NotFound, discord.Forbidden):
                    # 这些错误由 parse_and_fetch_channels 或调用者处理，这里仅记录日志
                    logger.warning(f"无法找到或访问频道ID: {channel_id_int} (可能已被删除或无权限)")
                    continue # 跳过这个ID
                except Exception as e:
                    logger.error(f"获取频道 {channel_id_int} 时发生未知错误: {e}")
                    continue # 跳过这个ID

            # 检查是否是文本频道
            if isinstance(channel, discord.TextChannel):
                target_channels.append(channel)
            else:
                logger.warning(f"频道ID {channel_id_int} ({getattr(channel, 'name', 'N/A')}) 不是文本频道，跳过")

        except Exception as e: # 捕获 get_channel 或 fetch_channel 之外的意外错误
             logger.error(f"处理频道ID {channel_id_int} 时发生意外错误: {e}")

    logger.info(f"成功获取了 {len(target_channels)} 个有效的文本频道对象。")
    return target_channels



async def prepare_target_channels(bot_instance, channel_ids, channel_id_mode, forward_mode, config):
    """
    准备目标频道集合，根据不同的模式和策略。
    
    Args:
        bot_instance: Discord机器人实例
        channel_ids: 用户指定的频道ID字符串（逗号分隔）
        channel_id_mode: 频道ID处理模式（'none', 'and', 'ban'）
        forward_mode: 转发模式（0=不转发到特殊频道, 1=转发到所有频道, 2=只转发到特殊频道）
        config: 配置对象，包含SPECIAL_CHANNELS等配置
        
    Returns:
        target_channels: 最终的目标频道对象列表
        parse_errors: 解析过程中的错误信息列表
    """
    # 1. 准备频道集合
    # 1.1 获取所有可用频道的集合
    all_channel_ids = set()
    special_channel_ids = set()
    
    # 解析特殊频道ID列表
    # SPECIAL_CHANNELS在config.py中定义为整数列表
    special_channel_ids = set()
    if config.SPECIAL_CHANNELS:
        if isinstance(config.SPECIAL_CHANNELS, list):
            # 记录每个特殊频道ID
            for channel_id in config.SPECIAL_CHANNELS:
                special_channel_ids.add(int(channel_id))
            logger.info(f"配置的特殊频道ID列表: {special_channel_ids}")
        elif isinstance(config.SPECIAL_CHANNELS, str):
            # 向后兼容字符串格式
            for id_str in config.SPECIAL_CHANNELS.split(','):
                if id_str.strip():
                    try:
                        special_channel_ids.add(int(id_str.strip()))
                    except ValueError:
                        logger.warning(f"无效的特殊频道ID格式: {id_str}")
            logger.info(f"从字符串解析的特殊频道ID: {special_channel_ids}")
        else:
            logger.warning(f"SPECIAL_CHANNELS格式不正确: {type(config.SPECIAL_CHANNELS)}")
    
    for channel_id_int, current_channel in bot_instance.channels.items():
        # 确保是 TextChannel
        if not isinstance(current_channel, discord.TextChannel):
            continue
        # 记录所有频道ID
        all_channel_ids.add(channel_id_int)
        # 检查是否是特殊频道（直接比较整数）
        if channel_id_int in special_channel_ids:
            logger.info(f"标记特殊频道: {channel_id_int} ({current_channel.name})")

    # 1.2 解析用户指定的频道ID
    parsed_target_ids, parse_errors = parse_channel_ids(channel_ids)

    # 2. 根据 forward_mode 计算基础频道ID集合
    forward_mode_channel_ids = set()
    if forward_mode == 0:  # 不转发到特殊频道
        forward_mode_channel_ids = all_channel_ids - special_channel_ids
        logger.info(f"转发模式0: 排除{len(special_channel_ids)}个特殊频道，剩余{len(forward_mode_channel_ids)}个频道")
    elif forward_mode == 1:  # 转发到所有频道
        forward_mode_channel_ids = all_channel_ids
        logger.info(f"转发模式1: 使用所有{len(all_channel_ids)}个频道")
    elif forward_mode == 2:  # 只转发到特殊频道
        forward_mode_channel_ids = special_channel_ids
        logger.info(f"转发模式2: 仅使用{len(special_channel_ids)}个特殊频道")

    # 3. 根据 channel_id_mode 确定最终目标频道ID集合
    final_target_channel_ids = set()
    if channel_id_mode == 'none':
        if parsed_target_ids:
            final_target_channel_ids = parsed_target_ids
            logger.info(f"模式 'none': 使用指定的 {len(parsed_target_ids)} 个频道 ID")
        else:
            final_target_channel_ids = forward_mode_channel_ids
            logger.info(f"模式 'none' 且未指定 channel_ids: 使用 forward_mode 的 {len(forward_mode_channel_ids)} 个频道")
    elif channel_id_mode == 'and':
        final_target_channel_ids = forward_mode_channel_ids.union(parsed_target_ids)
        logger.info(f"模式 'and': 合并 forward_mode ({len(forward_mode_channel_ids)}) 和指定 ID ({len(parsed_target_ids)})，共 {len(final_target_channel_ids)} 个频道")
    elif channel_id_mode == 'ban':
        final_target_channel_ids = forward_mode_channel_ids.difference(parsed_target_ids)
        logger.info(f"模式 'ban': 从 forward_mode ({len(forward_mode_channel_ids)}) 排除指定 ID ({len(parsed_target_ids)})，剩 {len(final_target_channel_ids)} 个频道")

    # 4. 获取最终的频道对象
    target_channels = await fetch_channels_from_ids(bot_instance, final_target_channel_ids)
    logger.info(f"最终将尝试发送到 {len(target_channels)} 个频道")
    
    return target_channels, parse_errors


def build_response_message(content_type, sent_to_channels, failed_channels,
                         sent_channel_mentions, failed_channel_mentions,
                         parse_errors, channel_ids, forward_mode, tg_sent_status,
                         channel_id_mode="none"): # 添加 channel_id_mode 参数
    """构建统一的响应消息"""
    response_parts = []

    # 描述发送模式
    mode_description = ""
    if channel_id_mode == 'none':
        if channel_ids:
            mode_description = f"频道ID模式: none (仅指定ID)"
        else:
            mode_description = f"转发模式: {forward_mode} (未指定ID)"
    elif channel_id_mode == 'and':
        mode_description = f"频道ID模式: and (转发模式 {forward_mode} + 指定ID)"
    elif channel_id_mode == 'ban':
        mode_description = f"频道ID模式: ban (转发模式 {forward_mode} - 指定ID)"
    else: # 未知模式或旧逻辑兼容
        if channel_ids:
             mode_description = f"指定频道模式 (IDs: {channel_ids})"
        else:
             mode_description = f"转发模式: {forward_mode}"


    # 描述发送结果
    if sent_to_channels > 0:
        response_parts.append(f"✅ {content_type}已成功发送到 {sent_to_channels} 个频道 ({mode_description})")
        if sent_channel_mentions: # 仅在有成功发送的频道时显示列表
             # 限制显示数量避免消息过长
             max_mentions_display = 10
             display_mentions = sent_channel_mentions[:max_mentions_display]
             mentions_str = ', '.join(display_mentions)
             if len(sent_channel_mentions) > max_mentions_display:
                 mentions_str += f", 等另外 {len(sent_channel_mentions) - max_mentions_display} 个"
             response_parts.append(f"   - 成功频道: {mentions_str}")
    else:
        # 如果没有成功发送，但有失败或解析错误，仍然显示模式
        if failed_channels > 0 or parse_errors:
             response_parts.append(f"ℹ️ 尝试发送 ({mode_description})，但未成功发送到任何频道。")
        else: # 没有成功，没有失败，没有解析错误 = 没有目标频道
             response_parts.append(f"⚠️ 未找到任何有效的目标频道进行发送 ({mode_description})。")


    if failed_channels > 0:
        response_parts.append(f"❌ 发送到 {failed_channels} 个频道失败:")
        if failed_channel_mentions:
             # 限制显示数量
             max_mentions_display = 10
             display_mentions = failed_channel_mentions[:max_mentions_display]
             mentions_str = ', '.join(display_mentions)
             if len(failed_channel_mentions) > max_mentions_display:
                 mentions_str += f", 等另外 {len(failed_channel_mentions) - max_mentions_display} 个"
             response_parts.append(f"   - 失败详情: {mentions_str}")
    if parse_errors:
        # 限制显示数量
        max_errors_display = 5
        display_errors = parse_errors[:max_errors_display]
        errors_str = "\n- ".join(display_errors)
        if len(parse_errors) > max_errors_display:
            errors_str += f"\n- ...等另外 {len(parse_errors) - max_errors_display} 个错误"
        response_parts.append(f"⚠️ 解析或获取频道ID时遇到问题:\n- {errors_str}")

    # 添加TG状态
    if tg_sent_status:
        # 确保TG状态不是空字符串或仅包含空格
        if tg_sent_status.strip():
             response_parts.append(f"Telegram 状态: {tg_sent_status.strip()}")

    final_response = "\n".join(response_parts).strip() # 去除末尾可能多余的换行符
    if len(final_response) > 2000:  # Discord 消息长度限制
        final_response = final_response[:1997] + "..."
    elif not final_response: # 如果没有任何信息，提供一个默认消息
        final_response = "ℹ️ 操作完成，但没有具体状态信息可报告。"


    return final_response
