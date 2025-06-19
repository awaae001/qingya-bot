import os
import discord
import logging
import requests
from urllib.parse import urlparse
import json
from datetime import datetime

logger = logging.getLogger(__name__)

async def upload_image(interaction: discord.Interaction, context: str, image_url: str, sender: str, base_path: str = "data/fetch"):
    """处理图片上传并保存到本地
    Args:
        base_path: 基础存储路径，默认为"data/fetch"
    """
    # 按日期创建子目录 (YYYY-MM-DD)
    date_str = datetime.now().strftime("%Y-%m-%d")
    upload_dir = os.path.join(base_path, date_str)
    os.makedirs(upload_dir, exist_ok=True)  # 确保目录存在
    sender_id = str(interaction.user.id)
    
    # 验证URL有效性
    if not image_url.startswith(('http://', 'https://')):
        await interaction.response.send_message("❌ 无效的图片URL", ephemeral=True)
        return
    
    try:
        # 下载图片
        response = requests.get(image_url, stream=True)
        response.raise_for_status()
        
        # 获取文件扩展名
        parsed = urlparse(image_url)
        filename = os.path.basename(parsed.path)
        ext = os.path.splitext(filename)[1] or '.png'
        
        # 生成保存文件名
        save_filename = f"{sender}_{context}{ext}"
        save_path = os.path.join(upload_dir, save_filename)
        
        # 保存文件
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        
        # 保存元数据
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
            # 读取现有元数据或创建新文件
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
        # 使用bot实例中的channel_logger
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
