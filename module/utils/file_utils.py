"""文件处理工具函数"""
import os
import uuid
import discord
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

async def save_uploaded_file(attachment: discord.Attachment, save_dir: str) -> Tuple[Optional[str], Optional[discord.File]]:
    """
    保存上传的文件并创建 Discord File 对象
    
    参数:
        attachment: Discord 附件对象
        save_dir: 保存目录路径
        
    返回:
        tuple: (local_path, discord_file)
            local_path: 本地保存路径
            discord_file: Discord File 对象
    """
    os.makedirs(save_dir, exist_ok=True)
    file_ext = os.path.splitext(attachment.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    local_path = os.path.join(save_dir, unique_filename)
    
    try:
        await attachment.save(local_path)
        logger.info(f"文件已保存到本地: {local_path}")
        discord_file = discord.File(local_path, filename=attachment.filename)
        return local_path, discord_file
    except Exception as e:
        logger.error(f"处理上传文件时失败: {e}")
        return None, None
