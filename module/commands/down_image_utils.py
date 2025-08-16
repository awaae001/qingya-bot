import discord
import os
import re
import aiohttp
import zipfile
import logging
import shutil
from typing import Optional, Tuple

import config

logger = logging.getLogger(__name__)

def parse_message_link(link: str) -> Optional[Tuple[int, int, int]]:
    """解析 Discord 消息链接，返回 (guild_id, channel_id, message_id)"""
    match = re.match(r"https://discord.com/channels/(\d+)/(\d+)/(\d+)", link)
    if match:
        return int(match.group(1)), int(match.group(2)), int(match.group(3))
    return None

async def download_image(session: aiohttp.ClientSession, url: str, path: str):
    """下载单个图片"""
    try:
        async with session.get(url) as response:
            if response.status == 200:
                with open(path, 'wb') as f:
                    f.write(await response.read())
                return True
            else:
                logger.error(f"下载图片失败，状态码: {response.status}, URL: {url}")
                return False
    except Exception as e:
        logger.error(f"下载图片时发生错误: {e}")
        return False

async def handle_down_image_command(interaction: discord.Interaction, message_link: str, bot_instance):
    """处理 /down_image 命令"""
    await interaction.response.defer(ephemeral=True)

    link_data = parse_message_link(message_link)
    if not link_data:
        await interaction.followup.send("❌ 无效的消息链接格式", ephemeral=True)
        return

    guild_id, channel_id, message_id = link_data

    try:
        channel = await interaction.client.fetch_channel(channel_id)
        if not channel:
            await interaction.followup.send("❌ 无法找到指定的频道", ephemeral=True)
            return
            
        message = await channel.fetch_message(message_id)
    except discord.NotFound:
        await interaction.followup.send("❌ 无法找到指定的消息", ephemeral=True)
        return
    except discord.Forbidden:
        await interaction.followup.send("❌ 没有权限访问该消息", ephemeral=True)
        return
    except Exception as e:
        logger.error(f"获取消息时出错: {e}")
        await interaction.followup.send("❌ 获取消息时发生未知错误", ephemeral=True)
        return

    if not message.attachments:
        await interaction.followup.send("❌ 该消息不包含任何附件", ephemeral=True)
        return

    image_attachments = [
        att for att in message.attachments 
        if any(att.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp'])
    ]

    if not image_attachments:
        await interaction.followup.send("❌ 该消息不包含任何图片附件", ephemeral=True)
        return

    temp_dir = f"temp_images_{message_id}"
    os.makedirs(temp_dir, exist_ok=True)

    zip_path = f"{temp_dir}.zip"
    download_success_count = 0

    async with aiohttp.ClientSession() as session:
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for attachment in image_attachments:
                file_path = os.path.join(temp_dir, attachment.filename)
                if await download_image(session, attachment.url, file_path):
                    zf.write(file_path, attachment.filename)
                    download_success_count += 1
    
    if download_success_count == 0:
        await interaction.followup.send("❌ 所有图片都下载失败", ephemeral=True)
        # 清理空目录和zip文件
        if os.path.exists(zip_path):
            os.remove(zip_path)
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return

    log_channel_id = config.LOG_CHANNELS[0] if config.LOG_CHANNELS else None
    if not log_channel_id:
        await interaction.followup.send("❌ 未配置日志频道 (LOG_CHANNELS)，无法发送文件或链接", ephemeral=True)
    else:
        try:
            log_channel = await interaction.client.fetch_channel(log_channel_id)
            zip_file_size = os.path.getsize(zip_path)
            DISCORD_MAX_FILE_SIZE = 8 * 1024 * 1024  # 8 MB

            if zip_file_size > DISCORD_MAX_FILE_SIZE:
                TARGET_DIR = "/www/wwwroot/cloud.jiuci.top/file/00_temp"
                final_dir_name = f"images_{message_id}"
                final_path = os.path.join(TARGET_DIR, final_dir_name)
                
                os.makedirs(TARGET_DIR, exist_ok=True)
                if os.path.exists(final_path): # 如果目标已存在，先删除
                    shutil.rmtree(final_path)
                shutil.move(temp_dir, final_path)
                
                public_url = f"https://cloud.jiuci.top/00_temp/{final_dir_name}/"
                await bot_instance.channel_logger.send_to_channel(
                    source="Discord",
                    module="/down_image",
                    description="📦 图片集太大无法上传，已保存至服务器",
                    additional_info=(
                        f"🔗 **来源消息:** <{message_link}>\n"
                        f"🖼️ **图片数量:** {download_success_count}\n"
                        f"📁 **访问链接:** {public_url}"
                    )
                )
                await interaction.followup.send(f"✅ 图片集太大 ({zip_file_size / 1024 / 1024:.2f} MB)，已保存至服务器。", ephemeral=True)
            else:
                with open(zip_path, 'rb') as f:
                    zip_file = discord.File(f, filename=os.path.basename(zip_path))
                    await log_channel.send(f"打包图片来自消息: <{message_link}>", file=zip_file)
                await interaction.followup.send(f"✅ 成功下载并打包 {download_success_count} 张图片，已发送到日志频道。", ephemeral=True)
        except Exception as e:
            logger.error(f"处理文件或发送日志时出错: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 处理文件或发送日志时失败: {e}", ephemeral=True)

    # 清理
    try:
        if os.path.exists(zip_path):
            os.remove(zip_path)
        if os.path.exists(temp_dir): # 如果文件过大，temp_dir 已被移动，所以不存在
            shutil.rmtree(temp_dir)
        logger.info(f"已清理临时文件: {zip_path}")
    except Exception as e:
        logger.error(f"清理临时文件时出错: {e}")
