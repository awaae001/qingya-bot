import os
import discord
import logging
import json
from datetime import datetime
from discord.ui import Button, View

logger = logging.getLogger(__name__)

class ConfirmDeleteView(View):
    def __init__(self, filename: str, item: dict, base_path: str):
        super().__init__(timeout=30)
        self.filename = filename
        self.item = item
        self.base_path = base_path
        self.confirmed = False

    @discord.ui.button(label="确认删除", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        self.confirmed = True
        await self.handle_delete(interaction)
        self.stop()

    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("❌ 已取消删除操作", ephemeral=True)
        self.stop()

    async def handle_delete(self, interaction: discord.Interaction):
        try:
            file_path = os.path.join(self.base_path, self.item['relative_path'])
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # 更新元数据文件
            metadata_path = os.path.join(self.base_path, 'metadata.json')
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata_list = json.load(f)
            
            updated_metadata = [item for item in metadata_list if item['relative_path'] != self.item['relative_path']]
            
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(updated_metadata, f, ensure_ascii=False, indent=2)
            
            logger.info(f"用户 {interaction.user.name} 删除了文件: {self.filename}")
            await interaction.response.send_message(
                f"✅ 文件已删除: {self.filename}", 
                ephemeral=True
            )
            
            # 记录到频道日志
            if hasattr(interaction.client, 'channel_logger'):
                await interaction.client.channel_logger.send_to_channel(
                    source="调取小助手", 
                    module="delete_image",
                    description=f"用户 <@{interaction.user.id}> 删除了文件: {self.filename}",
                    additional_info=f"文件名: {self.filename}\n原始条目: ``` {json.dumps(self.item, ensure_ascii=False, indent=2)} ```",
                )
                
        except Exception as e:
            logger.error(f"用户 {interaction.user.name} 删除文件失败 {str(e)}")
            await interaction.response.send_message(
                f"❌ 删除失败: {str(e)}", 
                ephemeral=True
            )

async def delete_image(interaction: discord.Interaction, filename: str, base_path: str = "data/fetch"):
    """删除指定图片文件
    Args:
        base_path: 基础存储路径，默认为"data/fetch"
    """
    try:
        metadata_path = os.path.join(base_path, 'metadata.json')
        
        # 读取元数据文件
        if not os.path.exists(metadata_path):
            await interaction.response.send_message("❌ 元数据文件不存在", ephemeral=True)
            return
            
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata_list = json.load(f)
            
        # 查找匹配的文件
        found_item = None
        for item in metadata_list:
            if item['relative_path'] == filename or item['saved_filename'] == filename:
                found_item = item
                break
                
        if not found_item:
            await interaction.response.send_message(f"❌ 未找到文件: {filename}", ephemeral=True)
            return
            
        # 显示确认对话框
        embed = discord.Embed(
            title="⚠️ 确认删除文件",
            description="请确认是否要删除以下文件",
            color=discord.Color.orange()
        )
        embed.add_field(name="文件名", value=found_item['saved_filename'], inline=False)
        embed.add_field(name="上传者", value=found_item['uploader_name'], inline=True)
        embed.add_field(name="上传时间", value=found_item['upload_time'], inline=True)
        embed.set_footer(text="此操作不可撤销，请谨慎操作")
        
        view = ConfirmDeleteView(filename, found_item, base_path)
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )
        await view.wait()
        if not view.confirmed:
            return
            
    except Exception as e:
        logger.error(f"用户 {interaction.user.name} 删除文件失败 {str(e)}")
        await interaction.response.send_message(
            f"❌ 删除失败: {str(e)}", 
            ephemeral=True
        )
