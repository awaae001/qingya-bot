import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import config

# 设置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
# 禁用httpx的INFO级别日志
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, discord_bot=None):
        self.application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        self.discord_bot = discord_bot
        self.setup_handlers()
        
    def setup_handlers(self):
        # 命令处理器
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("send", self.send_command))
        
        # 消息处理器 - 同时处理频道消息和普通消息
        self.application.add_handler(MessageHandler(
            (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL) & ~filters.COMMAND,
            self.forward_to_discord
        ))
        
        # 错误处理
        self.application.add_error_handler(self.error_handler)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text('机器人已启动，正在同步 Telegram 和 Discord 消息。')
    
    async def send_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/send命令，手动发送消息和多媒体到Discord"""
        if not update.message:
            return
            
        # 检查用户权限
        if config.AUTHORIZED_USERS and str(update.effective_user.id) not in config.AUTHORIZED_USERS:
            # print({str(update.effective_user.id)}, config.AUTHORIZED_USERS)
            await update.message.reply_text("❌ 抱歉，你没有使用此命令的权限")
            return
            
        args = context.args
        message = " ".join(args) if args else ""
        
        if not message and not (update.message.photo or update.message.video or update.message.document):
            await update.message.reply_text("请提供要发送的消息或附件，例如: /send 你好")
            return
            
        if not self.discord_bot:
            await update.message.reply_text("Discord机器人未连接")
            return
            
        # 处理文本消息
        content = message if message else ""
        
        # 处理图片
        if update.message.photo:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            file_url = file.file_path
            content += f"\n[图片]({file_url})"
        
        # 处理文件
        if update.message.document:
            file = await context.bot.get_file(update.message.document.file_id)
            file_url = file.file_path
            content += f"\n[文件: {update.message.document.file_name}]({file_url})"
        
        # 处理视频
        if update.message.video:
            file = await context.bot.get_file(update.message.video.file_id)
            file_url = file.file_path
            content += f"\n[视频]({file_url})"
            
        # 调用新的转发方法
        await self.discord_bot.forward_message(content)
        if config.SYNC_DISCORD_TO_TG:
            await self.send_to_telegram(f"[自动转发] \n {content.strip()}")
        await update.message.reply_text("消息和附件已发送到Discord并自动转发回Telegram")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "这是一个 Telegram 和 Discord 消息同步机器人。\n\n"
            "机器人会自动同步指定 Telegram 频道和 Discord 频道的消息。\n\n"
            "命令列表:\n"
            "/start - 启动机器人\n"
            "/help - 显示帮助信息\n"
            "/send - 手动发送消息或附件(图片/视频/文件)到Discord"
        )
        await update.message.reply_text(help_text)

    async def forward_to_discord(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理来自 Telegram 的消息并同步到 Discord"""
        message = update.channel_post or update.message
        if not message:
            logger.warning("Received an update without a message or channel_post object.")
            return

        if not config.SYNC_TG_TO_DISCORD or self.discord_bot is None:
            return
            
        logger.info(f"收到 Telegram 消息 (from target chat {message.chat.id}): {message.text}")
        
        content = message.text or ""
        
        if message.photo:
            photo = message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            file_url = file.file_path
            content += f"\n[图片]({file_url})"
        
        if message.document:
            file = await context.bot.get_file(message.document.file_id)
            file_url = file.file_path
            content += f"\n[文件: {message.document.file_name}]({file_url})"
        
        if message.video:
            file = await context.bot.get_file(message.video.file_id)
            file_url = file.file_path
            content += f"\n[视频]({file_url})"
        
        # 调用新的转发方法
        await self.discord_bot.forward_message(content)
    
    async def send_to_telegram(self, message=None, embed=None, image_path=None):
        """发送消息、嵌入内容或本地图片到 Telegram 频道"""
        try:
            # 优先处理本地图片路径
            if image_path:
                try:
                    with open(image_path, 'rb') as photo_file:
                        await self.application.bot.send_photo(
                            chat_id=config.TELEGRAM_CHANNEL_ID,
                            photo=photo_file,
                            caption=f"{config.DISCORD_MESSAGE_PREFIX}{message}" if message else None
                        )
                    logger.info(f"本地图片已发送到 Telegram: {image_path}")
                except FileNotFoundError:
                    logger.error(f"Telegram 发送失败：找不到本地图片文件 {image_path}")
                    # 如果图片发送失败，尝试只发送文本（如果存在）
                    if message:
                        await self.application.bot.send_message(
                            chat_id=config.TELEGRAM_CHANNEL_ID,
                            text=f"{config.DISCORD_MESSAGE_PREFIX}{message} (图片发送失败)"
                        )
                        logger.info(f"图片发送失败后，消息已发送到 Telegram: {message}")
                except Exception as e:
                    logger.error(f"使用本地图片发送到 Telegram 失败: {e}")
                    # 同样尝试只发送文本
                    if message:
                        await self.application.bot.send_message(
                            chat_id=config.TELEGRAM_CHANNEL_ID,
                            text=f"{config.DISCORD_MESSAGE_PREFIX}{message} (图片发送失败: {e})"
                        )
                        logger.info(f"图片发送失败后，消息已发送到 Telegram: {message}")

            # 如果没有本地图片，检查是否有embed图片
            elif embed and embed.image:
                await self.application.bot.send_photo(
                    chat_id=config.TELEGRAM_CHANNEL_ID,
                    photo=embed.image.url, # 使用 embed 中的 URL
                    caption=f"{config.DISCORD_MESSAGE_PREFIX}{message}" if message else None
                )
                logger.info(f"Embed 图片已发送到 Telegram: {embed.image.url}")
                # 如果 embed 也有文本，并且没有和图片一起发送，则单独发送文本
                if message and not (f"{config.DISCORD_MESSAGE_PREFIX}{message}" if message else None):
                     await self.application.bot.send_message(
                        chat_id=config.TELEGRAM_CHANNEL_ID,
                        text=f"{config.DISCORD_MESSAGE_PREFIX}{message}"
                    )
                     logger.info(f"补充发送 Embed 消息文本到 Telegram: {message}")

            elif message:
                await self.application.bot.send_message(
                    chat_id=config.TELEGRAM_CHANNEL_ID,
                    text=f"{config.DISCORD_MESSAGE_PREFIX}{message}"
                )
                logger.info(f"消息已发送到 Telegram: {message}")
                
        except Exception as e:
            logger.error(f"发送消息到 Telegram 失败: {e}")
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """处理错误"""
        logger.error(f"更新 {update} 导致错误 {context.error}")
    
    async def start(self):
        """启动 Telegram 机器人"""
        try:
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
        except Exception as e:
            logger.error(f"无法连接 Telegram 服务器: {e}")
            raise
    
    async def stop(self):
        """停止 Telegram 机器人"""
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        logger.info("Telegram 机器人已停止")
