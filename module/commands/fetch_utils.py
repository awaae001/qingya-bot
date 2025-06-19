import os
import random
import discord
import logging
import json
from utils.channel_logger import ChannelLogger

logger = logging.getLogger(__name__)
async def fetch_images(interaction: discord.Interaction, filename: str = None, message_link: str = None):
    """扫描data/fetch目录并发送指定或随机图片到当前频道或回复指定消息"""
    image_dir = "data/fetch"
    if not os.path.exists(image_dir):
        await interaction.response.send_message("图片目录不存在", ephemeral=True)
        return

    images = []
    for root, _, files in os.walk(image_dir):
        for f in files:
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                images.append(os.path.join(root, f))
    
    if not images:
        await interaction.response.send_message("目录中没有图片", ephemeral=True)
        return

    if filename:
        # 只比较文件名部分，忽略路径
        selected = next((f for f in images if os.path.basename(f).lower() == os.path.basename(filename).lower()), None)
        if not selected:
            await interaction.response.send_message(f"未找到文件: {filename}", ephemeral=True)
            return
    else:
        selected = random.choice(images)

    # 检查图片服务器权限
    metadata_path = os.path.join("data/fetch", "metadata.json")
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata_list = json.load(f)
        
        image_meta = next((m for m in metadata_list if m['saved_filename'] == os.path.basename(selected)), None)
        if image_meta:
            current_guild = str(interaction.guild.id) if interaction.guild else None
            if current_guild and image_meta['guild_id'] != current_guild:
                await interaction.response.send_message("❌ 无权调取其他服务器的图片", ephemeral=True)
                return

    with open(selected, 'rb') as f:
        picture = discord.File(f)
        
        if message_link:
            try:
                parts = message_link.split('/')
                if len(parts) < 7:
                    raise ValueError("Invalid message link format")
                
                channel_id = int(parts[-2])
                message_id = int(parts[-1])
                
                channel = interaction.client.get_channel(channel_id)
                if not channel:
                    raise ValueError("频道未找到")
                
                logger.info(f"用户 {interaction.user.name} 使用了命令，回复了消息 {message_id} ")
                
                if hasattr(interaction.client, 'channel_lohher'):
                    await interaction.client.channel_logger.send_to_channel(
                        source="调取小助手",
                        module="fetch_images",
                        description=f"用户 {interaction.user.name} 回复了消息 {message_id} 的图片: {os.path.basename(selected)}",
                        additional_info=f"图片路径: {selected} \n \n 频道: <#{interaction.channel.id}> \n 用户id: <@{interaction.user.id}>",
                    )
                
                message = await channel.fetch_message(message_id)
                if isinstance(channel, discord.Thread):
                    await channel.send(file=picture, reference=message)
                else:
                    await message.reply(file=picture)
                await interaction.response.send_message("已回复指定消息", ephemeral=True)
                logger.info(f"已回复消息 {message_id}")
            except Exception as e:
                await interaction.response.send_message(f"回复消息失败: {str(e)}", ephemeral=True)
                logger.error(f"回复消息失败: {e}")
        else:
            await interaction.response.send_message(file=picture)
            if hasattr(interaction.client, 'channel_logger'):
                await interaction.client.channel_logger.send_to_channel(
                    source="调取小助手",
                    module="fetch_images",
                    description=f"用户 {interaction.user.name} 发送了图片: {os.path.basename(selected)}",
                    additional_info=f"图片路径: {selected} \n 频道: <#{interaction.channel.id}> \n 用户id: <@{interaction.user.id}>",
                )
            else:
                logger.info(f"用户 {interaction.user.name} 发送了图片: {os.path.basename(selected)} (未发送到频道，未找到channel_logger)")
