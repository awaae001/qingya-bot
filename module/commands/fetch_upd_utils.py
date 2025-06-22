import os
import discord
import logging
import requests
from urllib.parse import urlparse
import json
from datetime import datetime

logger = logging.getLogger(__name__)

async def upload_image(interaction: discord.Interaction, context: str, image_url: str, sender: str, image_file=None, base_path: str = "data/fetch"):
    """处理图片上传并保存到本地
    Args:
        base_path: 基础存储路径，默认为"data/fetch"
        image_file: discord.Attachment 或 None
    """
    # 按日期创建子目录 (YYYY-MM-DD)
    date_str = datetime.now().strftime("%Y-%m-%d")
    upload_dir = os.path.join(base_path, date_str)
    os.makedirs(upload_dir, exist_ok=True)  # 确保目录存在
    sender_id = str(interaction.user.id)

    # 附件上传
    if image_file is not None:
        try:
            filename = image_file.filename
            ext = os.path.splitext(filename)[1] or '.png'
            save_filename = f"{sender}_{context}{ext}"
            save_path = os.path.join(upload_dir, save_filename)
            file_bytes = await image_file.read()
            with open(save_path, 'wb') as f:
                f.write(file_bytes)
            metadata = {
                'original_filename': filename,
                'uploader_id': sender_id,
                'uploader_name': interaction.user.name,
                'upload_time': datetime.now().isoformat(),
                'saved_filename': save_filename,
                'relative_path': os.path.join(date_str, save_filename),
                'guild_id': str(interaction.guild.id) if interaction.guild else None,
            }
            metadata_path = os.path.join(base_path, 'metadata.json')
            try:
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                else:
                    existing_data = []
                existing_data.append(metadata)
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(existing_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"无法保存元数据: {str(e)}")
            logger.info(f"用户 {interaction.user.name} 上传的图片已保存为: {save_filename}")
            await interaction.response.send_message(
                f"✅ 图片已保存为: {save_filename}",
                ephemeral=True
            )
            if hasattr(interaction.client, 'channel_logger'):
                await interaction.client.channel_logger.send_to_channel(
                    source="调取小助手",
                    module="upload_image",
                    description=f"用户 <@{interaction.user.id}> 上传的图片已保存为: {save_filename}",
                    additional_info=f"图片文件: {filename}",
                )
            else:
                logger.info(f"用户 {interaction.user.name} 上传的图片已保存为: {save_filename} (未发送到频道，未找到channel_logger)")
        except Exception as e:
            logger.error(f"用户 {interaction.user.name} 上传的图片保存失败 {str(e)}")
            await interaction.response.send_message(
                f"❌ 上传失败: {str(e)}",
                ephemeral=True
            )
        return

    # URL 上传
    if not image_url or not image_url.startswith(('http://', 'https://')):
        await interaction.response.send_message("❌ 无效的图片URL", ephemeral=True)
        return

    try:
        response = requests.get(image_url, stream=True)
        response.raise_for_status()
        parsed = urlparse(image_url)
        filename = os.path.basename(parsed.path)
        ext = os.path.splitext(filename)[1] or '.png'
        save_filename = f"{sender}_{context}{ext}"
        save_path = os.path.join(upload_dir, save_filename)
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        metadata = {
            'original_filename': filename,
            'uploader_id': sender_id,
            'uploader_name': interaction.user.name,
            'upload_time': datetime.now().isoformat(),
            'saved_filename': save_filename,
            'relative_path': os.path.join(date_str, save_filename),
            'guild_id': str(interaction.guild.id) if interaction.guild else None,
        }
        metadata_path = os.path.join(base_path, 'metadata.json')
        try:
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            else:
                existing_data = []
            existing_data.append(metadata)
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"无法保存元数据: {str(e)}")
        logger.info(f"用户 {interaction.user.name} 上传的图片已保存为: {save_filename}")
        await interaction.response.send_message(
            f"✅ 图片已保存为: {save_filename}",
            ephemeral=True
        )
        if hasattr(interaction.client, 'channel_logger'):
            await interaction.client.channel_logger.send_to_channel(
                source="调取小助手",
                module="upload_image",
                description=f"用户 <@{interaction.user.id}> 上传的图片已保存为: {save_filename}",
                additional_info=f"图片URL: {image_url}",
            )
        else:
            logger.info(f"用户 {interaction.user.name} 上传的图片已保存为: {save_filename} (未发送到频道，未找到channel_logger)")
    except Exception as e:
        logger.error(f"用户 {interaction.user.name} 上传的图片保存失败 {str(e)}")
        await interaction.response.send_message(
            f"❌ 上传失败: {str(e)}",
            ephemeral=True
        )
