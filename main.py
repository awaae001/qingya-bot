import asyncio
import logging
from telegram_bot import TelegramBot
from discord_bot import DiscordBot
from utils.clear_Image import ImageCleaner
import config

# 设置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 主程序 ---
async def main():
    # 创建机器人实例
    discord_bot = DiscordBot()
    telegram_bot = None
    if config.FORWARD_DC_TO_TG and config.TELEGRAM_BOT_TOKEN: # 检查开关和Token
        logger.info("Telegram 机器人功能已启用 (FORWARD_DC_TO_TG=True 且 Token 已配置)，正在初始化...")
        telegram_bot = TelegramBot(discord_bot)
        # 设置相互引用
        discord_bot.telegram_bot = telegram_bot
    else:
        if not config.FORWARD_DC_TO_TG:
            logger.info("Telegram 机器人功能因 FORWARD_DC_TO_TG=False 而禁用，跳过初始化。")
        elif not config.TELEGRAM_BOT_TOKEN:
            logger.info("Telegram 机器人功能因 TELEGRAM_BOT_TOKEN 未配置而禁用，跳过初始化。")
        discord_bot.telegram_bot = None
    
    # 启动清理守护进程
    image_cleaner = ImageCleaner(
        image_dir= config.IMAGE_DIR,
        cleanup_interval_hours= config.CLEANUP_INTERVAL_HOURS,
        max_image_age_hours= config.MAX_IMAGE_AGE_HOURS
    )
    
    # 启动机器人
    try:
        tasks = []
        # 创建 Discord 任务
        discord_task = asyncio.create_task(discord_bot.start_bot())
        tasks.append(discord_task)
        
        # 创建任务
        if telegram_bot:
            telegram_task = asyncio.create_task(telegram_bot.start())
            tasks.append(telegram_task)
            logger.info("Discord 和 Telegram 机器人任务已创建")
        else:
            logger.info("仅创建 Discord 机器人任务")
            
        # 启动清理线程
        image_cleaner.start_cleaner_thread()
        
        logger.info("机器人服务已启动")
        
        # 等待所有创建的任务完成
        await asyncio.gather(*tasks)
        
    except KeyboardInterrupt:
        logger.info("接收到中断信号，正在关闭机器人...")
        if telegram_bot:
            await telegram_bot.stop()
        await discord_bot.close()
    except Exception as e:
        logger.error(f"运行时出错: {e}")
        if telegram_bot:
            await telegram_bot.stop()
        await discord_bot.close()

if __name__ == "__main__":
    # 运行主异步事件循环
    asyncio.run(main())
