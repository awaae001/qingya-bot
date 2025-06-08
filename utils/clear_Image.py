# clearImage.py
import os
import time
import logging
import threading
import schedule
from datetime import datetime, timedelta

# 设置日志
logger = logging.getLogger(__name__)

class ImageCleaner:
    def __init__(self, 
                 image_dir="./data/image/",
                 cleanup_interval_hours=6,
                 max_image_age_hours=24):
        self.IMAGE_DIR = image_dir
        self.CLEANUP_INTERVAL_HOURS = cleanup_interval_hours
        self.MAX_IMAGE_AGE_HOURS = max_image_age_hours

    def cleanup_old_images(self):
        """清理指定目录中超过指定时长的旧图片文件"""
        now = datetime.now()
        cutoff_time = now - timedelta(hours=self.MAX_IMAGE_AGE_HOURS)
        logger.info(f"开始清理目录 '{self.IMAGE_DIR}' 中早于 {cutoff_time} 的图片...")
        
        try:
            if not os.path.exists(self.IMAGE_DIR):
                logger.warning(f"图片目录 '{self.IMAGE_DIR}' 不存在，跳过清理。")
                return
                
            cleaned_count = 0
            for filename in os.listdir(self.IMAGE_DIR):
                file_path = os.path.join(self.IMAGE_DIR, filename)
                if os.path.isfile(file_path):
                    try:
                        file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                        if file_mod_time < cutoff_time:
                            os.remove(file_path)
                            logger.info(f"已删除旧图片: {file_path} (修改时间: {file_mod_time})")
                            cleaned_count += 1
                    except Exception as e:
                        logger.error(f"处理文件 {file_path} 时出错: {e}")
                        
            logger.info(f"图片清理完成，共删除 {cleaned_count} 个文件。")
            
        except Exception as e:
            logger.error(f"执行图片清理时出错: {e}")

    def run_scheduler(self):
        """运行定时任务调度器"""
        logger.info(f"图片清理任务已启动，每 {self.CLEANUP_INTERVAL_HOURS} 小时执行一次。")
        # 立即执行一次清理
        self.cleanup_old_images()
        
        # 设置定时任务
        schedule.every(self.CLEANUP_INTERVAL_HOURS).hours.do(self.cleanup_old_images)
        
        while True:
            schedule.run_pending()
            time.sleep(60)

    def start_cleaner_thread(self):
        """启动清理线程"""
        thread = threading.Thread(target=self.run_scheduler, daemon=True)
        thread.start()
        return thread