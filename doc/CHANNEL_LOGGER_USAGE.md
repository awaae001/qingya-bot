# 频道日志组件使用指南

## 功能概述
本组件提供统一的格式化日志消息发送功能，支持：
- 标准日志记录（输出到控制台/文件）
- 格式化消息发送到Discord频道
- 自定义消息格式

## 初始化配置

1. 在bot主文件中初始化全局logger：
```python
from utils.channel_logger import channel_logger

# 设置Discord bot实例
channel_logger.set_bot(bot)

# 设置默认日志频道ID (可选)
channel_logger.set_default_channel(YOUR_LOG_CHANNEL_ID)

# 将logger附加到bot实例以便其他模块访问
bot.channel_logger = channel_logger
```

2. 在其他模块中获取logger：
```python
# 通过interaction获取
if hasattr(interaction.client, 'channel_logger'):
    await interaction.client.channel_logger.send_to_channel(...)

# 通过bot实例获取
if hasattr(bot, 'channel_logger'):
    await bot.channel_logger.send_to_channel(...)
```

## 发送日志消息

使用`send_to_channel`方法发送格式化日志消息：

```python
await channel_logger.send_to_channel(
    source="命令处理",  # 操作来源
    module="discord_commands",  # 模块名称
    description="用户执行了更新命令",  # 操作说明
    additional_info=f"用户ID: {user_id}\n参数: {params}",  # 附加信息(可选)
    channel_id=SPECIFIC_CHANNEL_ID  # 指定频道ID(可选，默认使用set_default_channel设置的频道)
)
```

## 标准日志记录

组件同时提供标准日志记录方法：

```python
# 记录不同级别日志
channel_logger.debug("调试信息")
channel_logger.info("一般信息")
channel_logger.warning("警告信息")
channel_logger.error("错误信息")
```

## 最佳实践

1. **不要**在各模块中创建新的ChannelLogger实例
2. 始终使用bot实例中的共享channel_logger
3. 发送消息前检查logger是否可用：
```python
if hasattr(interaction.client, 'channel_logger'):
    await interaction.client.channel_logger.send_to_channel(...)
else:
    logger.info("channel_logger不可用，记录到本地日志")
```

## 示例场景

### 1. 命令处理日志
```python
async def handle_command(ctx, params):
    try:
        # ...命令处理逻辑...
        await channel_logger.send_to_channel(
            source="命令处理",
            module="discord_commands",
            description=f"用户 {ctx.author} 执行了 {ctx.command} 命令",
            additional_info=f"完整参数: {params}"
        )
    except Exception as e:
        channel_logger.error(f"命令处理失败: {e}")
```

### 2. 系统事件通知
```python
async def on_ready():
    channel_logger.info("Bot已启动")
    await channel_logger.send_to_channel(
        source="系统",
        module="核心",
        description="Bot启动完成",
        additional_info=f"登录账号: {bot.user}"
    )
```

## 消息格式说明

发送到频道的消息将按以下格式显示：

```
操作记录
---------
来源：XXXX
模块：XXXX
说明：XXXX
附加信息：XXXX
```
