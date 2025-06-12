import discord
import logging
import os
import psutil
import time
import aiohttp
import asyncio
import config
from datetime import datetime
from typing import Tuple, Dict, Union

logger = logging.getLogger(__name__)

async def get_system_status() -> Dict[str, Union[str, int, float]]:
    return {
        'cpu_usage': psutil.cpu_percent(),
        'ram_usage': psutil.virtual_memory().percent
    }

async def get_image_dir_status() -> Tuple[Union[int, str], str]:
    image_count = 0
    image_dir_status = "OK"
    try:
        if os.path.exists(config.IMAGE_DIR):
            image_count = len([f for f in os.listdir(config.IMAGE_DIR) 
                             if os.path.isfile(os.path.join(config.IMAGE_DIR, f))])
        else:
            image_dir_status = "目录不存在"
            image_count = 0
    except Exception as e:
        logger.warning(f"无法读取图片目录 {config.IMAGE_DIR}: {e}")
        image_dir_status = f"读取错误 ({type(e).__name__})"
        image_count = "N/A"
    
    return image_count, image_dir_status

async def get_telegram_status(bot_instance) -> Tuple[str, str]:
    tg_latency_ms = "N/A"
    tg_status = "未配置"
    
    if config.TELEGRAM_BOT_TOKEN:
        tg_api_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getMe"
        try:
            async with aiohttp.ClientSession() as session:
                start_time = time.monotonic()
                async with session.get(tg_api_url, timeout=15) as response:
                    if response.status == 200:
                        await response.json()
                        end_time = time.monotonic()
                        tg_latency_ms = str(round((end_time - start_time) * 1000))
                        tg_status = "连接正常"
                    else:
                        logger.warning(f"测试Telegram API延迟失败: 状态码 {response.status}")
                        tg_latency_ms = f"错误 ({response.status})"
                        tg_status = f"API错误 ({response.status})"
        except aiohttp.ClientConnectorError as e:
            logger.warning(f"测试Telegram API延迟失败: 连接错误 {e}")
            tg_latency_ms = "连接错误"
            tg_status = "连接失败"
        except asyncio.TimeoutError:
            logger.warning("测试Telegram API延迟失败: 请求超时")
            tg_latency_ms = "超时"
            tg_status = "连接超时"
        except Exception as e:
            logger.warning(f"测试Telegram API延迟失败: {e}")
            tg_latency_ms = "未知错误"
            tg_status = f"测试出错 ({type(e).__name__})"
    else:
        tg_latency_ms = "未配置Token"
    
    return tg_latency_ms, tg_status

async def build_status_embed(bot_instance) -> discord.Embed:
    # 获取各项状态
    system_status = await get_system_status()
    image_count, image_dir_status = await get_image_dir_status()
    tg_latency_ms, tg_status = await get_telegram_status(bot_instance)
    
    # Discord延迟
    dc_latency = round(bot_instance.latency * 1000) if bot_instance.latency else "N/A"
    
    # 创建Embed
    embed = discord.Embed(
        title="📊 系统与机器人状态",
        color=discord.Color.blue()
    )
    
    # 添加字段
    embed.add_field(name="🖥️ 主机 CPU", value=f"{system_status['cpu_usage']}%", inline=True)
    embed.add_field(name="🧠 主机 RAM", value=f"{system_status['ram_usage']}%", inline=True)
    embed.add_field(name=" ", value=" ", inline=True)
    
    embed.add_field(name="<:logosdiscordicon:1381133861874044938> Discord 延迟", 
                   value=f"{dc_latency} ms" if isinstance(dc_latency, int) else dc_latency, 
                   inline=True)
    embed.add_field(name="<:logostelegram:1381134304729370634> Telegram 状态", 
                   value=tg_status, inline=True)
    embed.add_field(name="<:logostelegram:1381134304729370634> TG 延迟", 
                   value=f"{tg_latency_ms} ms" if isinstance(tg_latency_ms, str) and tg_latency_ms.isdigit() else tg_latency_ms, 
                   inline=True)
    
    embed.add_field(name="🖼️ 本地图片数", value=str(image_count), inline=True)
    embed.add_field(name="📂 图片目录状态", value=image_dir_status, inline=True)
    embed.add_field(name=" ", value=" ", inline=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
    embed.set_footer(text=f"{config.BOT_NAME} · 自动转发系统丨查询时间: {timestamp}")
    
    return embed

async def handle_status_command(interaction: discord.Interaction, bot_instance):
    await interaction.response.defer(ephemeral=False)
    
    try:
        embed = await build_status_embed(bot_instance)
        await interaction.followup.send(embed=embed)
        logger.info(f"用户 {interaction.user} 查询了状态")
    except Exception as e:
        logger.error(f"处理状态命令时出错: {e}")
        await interaction.followup.send("❌ 获取状态信息时出错", ephemeral=True)
