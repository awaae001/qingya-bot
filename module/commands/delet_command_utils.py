import discord
import logging
import config

logger = logging.getLogger(__name__)


async def  handle_delete_command(
        interaction: discord.Interaction,
        message_link: str,
        bot_instance,
    ):
        """处理/del命令，删除机器人自己发送的消息"""
        try:
            parts = message_link.split('/')
            if len(parts) < 7 or parts[2] != 'discord.com' or parts[3] != 'channels':
                await interaction.response.send_message("❌ 无效的消息链接格式", ephemeral=True)
                return

            channel_id = int(parts[5])
            message_id = int(parts[6])

            # 尝试从缓存或API获取频道
            channel = bot_instance.get_channel(channel_id)
            if not channel:
                 try:
                     channel = await bot_instance.fetch_channel(channel_id)
                 except (discord.NotFound, discord.Forbidden):
                     await interaction.response.send_message("❌ 无法找到或访问该频道", ephemeral=True)
                     return

            if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                 await interaction.response.send_message("❌ 目标必须是文本频道或子区", ephemeral=True)
                 return

            try:
                message = await channel.fetch_message(message_id)
            except discord.NotFound:
                await interaction.response.send_message("❌ 消息不存在或已被删除", ephemeral=True)
                return
            except discord.Forbidden:
                await interaction.response.send_message("❌ 没有权限访问该消息", ephemeral=True)
                return

            # 创建确认按钮
            confirm_button = discord.ui.Button(label="确认删除", style=discord.ButtonStyle.danger)
            cancel_button = discord.ui.Button(label="取消", style=discord.ButtonStyle.secondary)
            
            view = discord.ui.View()
            view.add_item(confirm_button)
            view.add_item(cancel_button)
            
            # 消息作者信息
            author_name = message.author.name
            
            # 定义按钮回调
            async def confirm_callback(interaction_confirm: discord.Interaction):
                try:
                    await message.delete()
                    await interaction_confirm.response.edit_message(content="✅ 消息已成功删除", view=None)
                    logger.info(f"用户 {interaction.user} 删除了消息 {message_id} 在频道 {channel_id}")
                except discord.Forbidden:
                    await interaction_confirm.response.edit_message(content="❌ 没有权限删除该消息", view=None)
                except Exception as e:
                    logger.error(f"删除消息时出错: {e}")
                    await interaction_confirm.response.edit_message(content=f"❌ 删除消息时出错: {e}", view=None)
            
            async def cancel_callback(interaction_cancel: discord.Interaction):
                await interaction_cancel.response.edit_message(content="❌ 已取消删除操作", view=None)
            
            # 设置回调
            confirm_button.callback = confirm_callback
            cancel_button.callback = cancel_callback
            
            # 创建嵌入式确认消息
            embed = discord.Embed(
                title="⚠️ 确认删除消息",
                description=f"您确定要删除来自 {author_name} 的消息吗？\n\n此操作无法撤销！",
                color=discord.Color.orange()
            )
            embed.set_footer(text=f"{config.BOT_NAME} ·自动转发系统丨消息ID: {message_id} | 频道ID: {channel_id}")
            
            # 发送嵌入式确认消息
            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True
            )

        except ValueError:
             await interaction.response.send_message("❌ 消息链接中的ID无效", ephemeral=True)
        except Exception as e:
            logger.error(f"删除消息时出错: {e}")
            await interaction.response.send_message(f"❌ 删除消息时出错: {e}", ephemeral=True)
