import discord
import time
import logging
import config
import uuid
import json
from pathlib import Path

logger = logging.getLogger(__name__)

FEEDBACK_DATA_PATH = Path(config.FEEDBACK_DATA_PATH)

def save_feedback(feedback_id, user_id, content):
    """保存反馈到本地JSON文件"""
    try:
        data = {}
        if FEEDBACK_DATA_PATH.exists():
            with open(FEEDBACK_DATA_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
        data[feedback_id] = {
            "user_id": user_id,
            "content": content,
            "timestamp": time.time(),
        }
        
        with open(FEEDBACK_DATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        logger.error(f"保存反馈失败: {e}")

def load_feedback(feedback_id):
    """从本地加载反馈数据"""
    try:
        if FEEDBACK_DATA_PATH.exists():
            with open(FEEDBACK_DATA_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get(feedback_id)
    except Exception as e:
        logger.error(f"加载反馈失败: {e}")
    return None

def delete_feedback(feedback_id):
    """删除本地数据"""
    try:
        if FEEDBACK_DATA_PATH.exists():
            with open(FEEDBACK_DATA_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if feedback_id in data:
                del data[feedback_id]
                
                with open(FEEDBACK_DATA_PATH, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"删除反馈数据失败: {e}")

class FeedbackModal(discord.ui.Modal, title='请求私聊'):
    """反馈表单模态框"""
    feedback = discord.ui.TextInput(
        label='您的内容',
        style=discord.TextStyle.long,
        placeholder='请输入你要和管理员说的事情...',
        required=True,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        """表单提交处理"""
        await interaction.response.send_message(
            '✅ 感谢您的请求！我们将在 7 天内回复',
            ephemeral=True
        )
        
        # 获取反馈频道
        feedback_channel_id = config.LOG_CHANNELS[0] if config.LOG_CHANNELS else None
        if not feedback_channel_id:
            logger.error("未配置反馈频道(LOG_CHANNELS)")
            return
            
        try:
            channel = interaction.client.get_channel(feedback_channel_id)
            if not channel:
                channel = await interaction.client.fetch_channel(feedback_channel_id)
                
            feedback_id = str(uuid.uuid4())
            save_feedback(feedback_id, interaction.user.id, self.feedback.value)
            
            embed = discord.Embed(
                title="📢 新私聊来了",
                description=self.feedback.value,
                color=discord.Color.orange()
            )
            embed.add_field(name="ID", value=feedback_id, inline=False)
            embed.set_author(
                name=f"{interaction.user.name}#{interaction.user.discriminator}",
                icon_url=interaction.user.avatar.url if interaction.user.avatar else None
            )
            guild_name = interaction.guild.name if interaction.guild else "未知服务器"
            embed.set_footer(text=f"服务器: {guild_name} | 用户ID: {interaction.user.id}")
            
            view = FeedbackReplyView(feedback_id)
            await channel.send(embed=embed, view=view)
            logger.info(f"已发送来自 {interaction.user} 的私聊到频道 {feedback_channel_id}")
        except Exception as e:
            logger.error(f"发送反馈到频道失败: {e}")

class FeedbackReplyView(discord.ui.View):
    """管理员回复视图"""
    def __init__(self, feedback_id):
        super().__init__(timeout=None)
        self.feedback_id = feedback_id
        
    @discord.ui.button(
        label="回复",
        style=discord.ButtonStyle.success,
        custom_id="reply_button"
    )
    async def reply_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        """回复按钮点击处理"""
        feedback_data = load_feedback(self.feedback_id)
        if not feedback_data:
            await interaction.response.send_message("⚠️ 找不到该记录", ephemeral=True)
            return
            
        await interaction.response.send_modal(ReplyModal(self.feedback_id, feedback_data["user_id"]))
        
    @discord.ui.button(
        label="拒绝",
        style=discord.ButtonStyle.danger,
        custom_id="reject_button"
    )
    async def reject_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        """拒绝按钮点击处理"""
        feedback_data = load_feedback(self.feedback_id)
        if not feedback_data:
            await interaction.response.send_message("⚠️ 找不到该记录", ephemeral=True)
            return
            
        # 记录被拒绝用户ID和当前时间
        try:
            data = {}
            if FEEDBACK_DATA_PATH.exists():
                with open(FEEDBACK_DATA_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            data[f"rejected_{feedback_data['user_id']}"] = {
                "timestamp": time.time()
            }
            
            with open(FEEDBACK_DATA_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"记录拒绝用户失败: {e}")

        # 删除反馈数据
        delete_feedback(self.feedback_id)
        
        try:
            # 更新原始消息状态
            message = await interaction.channel.fetch_message(interaction.message.id)
            new_embed = discord.Embed(
                title="❌ 已拒绝私聊",
                description=message.embeds[0].description,
                color=discord.Color.red()
            )
            for field in message.embeds[0].fields:
                new_embed.add_field(name=field.name, value=field.value, inline=field.inline)
            if message.embeds[0].author:
                new_embed.set_author(
                    name=message.embeds[0].author.name,
                    icon_url=message.embeds[0].author.icon_url
                )
            if message.embeds[0].footer:
                new_embed.set_footer(text=message.embeds[0].footer.text)
            
            await message.edit(embed=new_embed, view=None)
            
            await interaction.response.send_message(
                '✅ 已拒绝该私聊请求',
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"拒绝私聊处理失败: {e}")
            await interaction.response.send_message(
                '❌ 拒绝处理失败: ' + str(e),
                ephemeral=True
            )

class ReplyModal(discord.ui.Modal, title='回复'):
    """回复表单模态框"""
    def __init__(self, feedback_id, user_id):
        super().__init__()
        self.feedback_id = feedback_id
        self.user_id = user_id
        
    reply = discord.ui.TextInput(
        label='回复内容',
        style=discord.TextStyle.long,
        placeholder='请输入回复内容...',
        required=True,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        """表单提交处理"""
        # 先立即响应交互，避免超时
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        
        try:
            # 发送私信给用户
            user = await interaction.client.fetch_user(self.user_id)
            await user.send(
                f"📨 管理员回复了你的私聊 (ID: {self.feedback_id}):\n\n{self.reply.value} \n\n私信 bot 的话，管理员将无法收到你对 bot 的私信内容"
            )
            
            # 删除反馈数据
            delete_feedback(self.feedback_id)
            
            try:
                # 更新原始消息状态
                message = await interaction.channel.fetch_message(interaction.message.id)
                new_embed = discord.Embed(
                    title="✅ 已回复私聊",
                    description=message.embeds[0].description,
                    color=discord.Color.green()
                )
                for field in message.embeds[0].fields:
                    new_embed.add_field(name=field.name, value=field.value, inline=field.inline)
                if message.embeds[0].author:
                    new_embed.set_author(
                        name=message.embeds[0].author.name,
                        icon_url=message.embeds[0].author.icon_url
                    )
                if message.embeds[0].footer:
                    new_embed.set_footer(text=message.embeds[0].footer.text)
                
                await message.edit(embed=new_embed, view=None)
                
                # 发送成功通知
                await interaction.followup.send(
                    '✅ 回复已发送给用户',
                    ephemeral=True
                )
            except Exception as e:
                logger.error(f"更新消息失败: {e}")
                await interaction.followup.send(
                    '⚠️ 回复已发送但更新消息失败',
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"发送回复失败: {e}")
            await interaction.followup.send(
                '❌ 回复发送失败: ' + str(e),
                ephemeral=True
            )

class FeedbackView(discord.ui.View):
    """按钮视图"""
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(
        label="提交内容",
        style=discord.ButtonStyle.primary,
        custom_id="feedback_button"
    )
    async def feedback_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        """反馈按钮点击处理"""
        current_time = time.time()
        cooldown = config.REP_RATE
        
        # 检查冷却时间
        try:
            if FEEDBACK_DATA_PATH.exists():
                with open(FEEDBACK_DATA_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # 检查是否被拒绝过
                    rejected_key = f"rejected_{interaction.user.id}"
                    if rejected_key in data:
                        last_rejected = data[rejected_key]["timestamp"]
                        if current_time - last_rejected < config.REJECT_COOLDOWN:
                            remaining = int(config.REJECT_COOLDOWN - (current_time - last_rejected))
                            await interaction.response.send_message(
                                f"⛔ 您最近被拒绝过申请，请等待 {remaining}秒 后再试",
                                ephemeral=True
                            )
                            return
                    
                    # 查找用户最近的反馈
                    user_feedbacks = [
                        fb for fb in data.values() 
                        if "user_id" in fb and fb["user_id"] == interaction.user.id
                    ]
                    
                    if user_feedbacks:
                        last_used = max(fb["timestamp"] for fb in user_feedbacks)
                        if current_time - last_used < cooldown:
                            remaining = int(cooldown - (current_time - last_used))
                            await interaction.response.send_message(
                                f"⏳ 请稍后再试！反馈功能冷却时间 (剩余: {remaining}秒)",
                                ephemeral=True
                            )
                            return
                            
        except Exception as e:
            logger.error(f"检查冷却时间失败: {e}")
            
        await interaction.response.send_modal(FeedbackModal())
