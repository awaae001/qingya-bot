import discord
import json
import logging
from pathlib import Path
from discord.ext import tasks

import config

logger = logging.getLogger(__name__)

# --- 数据存储逻辑 ---

KEEP_ALIVE_DATA_PATH = Path(config.KEEP_ALIVE_DATA_PATH)

def _load_guilds_data():
    """从JSON文件加载所有服务器的保活数据"""
    if not KEEP_ALIVE_DATA_PATH.exists():
        return {}
    try:
        with open(KEEP_ALIVE_DATA_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"读取保活频道文件失败: {e}")
        return {}

def _save_guilds_data(data):
    """将所有服务器的保活数据保存到JSON文件"""
    try:
        KEEP_ALIVE_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(KEEP_ALIVE_DATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except IOError as e:
        logger.error(f"写入保活频道文件失败: {e}")

def add_channel(guild_id: int, channel_id: int):
    """为指定服务器添加一个频道到保活列表"""
    data = _load_guilds_data()
    guild_id_str = str(guild_id)
    
    if guild_id_str not in data:
        data[guild_id_str] = []
        
    if channel_id not in data[guild_id_str]:
        data[guild_id_str].append(channel_id)
        _save_guilds_data(data)
        return True
    return False

def remove_channel(guild_id: int, channel_id: int):
    """从指定服务器的保活列表移除一个频道"""
    data = _load_guilds_data()
    guild_id_str = str(guild_id)

    if guild_id_str in data and channel_id in data[guild_id_str]:
        data[guild_id_str].remove(channel_id)
        # 如果服务器列表为空，则移除该服务器键
        if not data[guild_id_str]:
            del data[guild_id_str]
        _save_guilds_data(data)
        return True
    return False

def get_all_guilds_data():
    """获取所有服务器的保活数据"""
    return _load_guilds_data()

# --- 命令核心处理逻辑 ---

async def handle_keep_alive_command(interaction: discord.Interaction, action: str, channel_id_str: str = None):
    """处理/保活子区命令"""
    await interaction.response.defer(ephemeral=True)

    is_admin = config.AUTHORIZED_USERS and str(interaction.user.id) in config.AUTHORIZED_USERS

    if action == "list":
        guilds_data = get_all_guilds_data()
        if not guilds_data:
            await interaction.followup.send("目前没有保活任何子区。", ephemeral=True)
            return

        embed = discord.Embed(title="📢 保活子区列表", color=discord.Color.blue())
        
        for guild_id, channels in guilds_data.items():
            guild = interaction.client.get_guild(int(guild_id))
            guild_name = guild.name if guild else f"未知服务器 (ID: {guild_id})"
            
            if channels:
                channel_mentions = [f"<#{cid}> (`{cid}`)" for cid in channels]
                embed.add_field(name=f"服务器: {guild_name}", value="\n".join(channel_mentions), inline=False)
        
        if not embed.fields:
             await interaction.followup.send("目前没有保活任何子区。", ephemeral=True)
             return

        await interaction.followup.send(embed=embed, ephemeral=True)

    elif action in ["add", "remove"]:
        if not interaction.guild:
            await interaction.followup.send("❌ 此操作只能在服务器内使用。", ephemeral=True)
            return
            
        if not is_admin:
            await interaction.followup.send("❌ 抱歉，只有系统管理员才能执行此操作。", ephemeral=True)
            return

        if not channel_id_str:
            await interaction.followup.send("❌ 请提供一个有效的频道ID。", ephemeral=True)
            return
        
        try:
            channel_id = int(channel_id_str)
        except ValueError:
            await interaction.followup.send("❌ 频道ID必须是一个纯数字。", ephemeral=True)
            return

        guild_id = interaction.guild.id

        if action == "add":
            if add_channel(guild_id, channel_id):
                await interaction.followup.send(f"✅ 已成功添加频道 <#{channel_id}> 到本服务器的保活列表。", ephemeral=True)
            else:
                await interaction.followup.send(f"⚠️ 频道 <#{channel_id}> 已存在于本服务器的保活列表中。", ephemeral=True)
        
        elif action == "remove":
            if remove_channel(guild_id, channel_id):
                await interaction.followup.send(f"✅ 已成功从本服务器的保活列表移除频道 <#{channel_id}>。", ephemeral=True)
            else:
                await interaction.followup.send(f"⚠️ 频道 <#{channel_id}> 不在本服务器的保活列表中。", ephemeral=True)

# --- 定时保活任务 ---

@tasks.loop(hours=config.KEEP_ALIVE_INTERVAL_HOURS)
async def keep_alive_task(bot: discord.Client):
    """定时任务，用于保活频道"""
    logger.info("开始执行保活任务...")
    guilds_data = get_all_guilds_data()
    
    if not guilds_data:
        logger.info("没有需要保活的频道，任务结束。")
        return

    for guild_id_str, channel_ids in guilds_data.items():
        try:
            guild_id = int(guild_id_str)
            guild = bot.get_guild(guild_id)
            if not guild:
                logger.warning(f"找不到服务器ID: {guild_id}，跳过该服务器的保活任务。")
                continue

            for channel_id in channel_ids:
                try:
                    channel = guild.get_channel(channel_id)
                    if not channel:
                        # 如果缓存中没有，尝试从API获取
                        channel = await guild.fetch_channel(channel_id)
                    
                    if isinstance(channel, discord.TextChannel):
                        current_topic = channel.topic or ""
                        # 使用零宽空格来触发更新，对用户不可见
                        new_topic = current_topic.rstrip('\u200b') + '\u200b'
                        
                        await channel.edit(topic=new_topic, reason="自动保活任务")
                        logger.info(f"已成功保活服务器 '{guild.name}' 的频道: {channel.name} ({channel.id})")
                    else:
                        logger.warning(f"ID {channel_id} 在服务器 '{guild.name}' 中不是一个文本频道，无法保活。")

                except discord.errors.NotFound:
                    logger.warning(f"在服务器 '{guild.name}' 中无法找到频道ID: {channel_id}，可能已被删除。建议从保活列表中移除。")
                except discord.errors.Forbidden:
                    logger.error(f"没有权限编辑服务器 '{guild.name}' 的频道 {channel_id} 的 topic。请检查机器人权限。")
                except Exception as e:
                    logger.error(f"保活频道 {channel_id} 时发生未知错误: {e}")
        except Exception as e:
            logger.error(f"处理服务器 {guild_id_str} 的保活任务时发生错误: {e}")

@keep_alive_task.before_loop
async def before_keep_alive_task(bot: discord.Client):
    """在任务开始前等待机器人准备就绪"""
    await bot.wait_until_ready()
