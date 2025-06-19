# Discord 命令权限装饰器说明

## 概述
本文档介绍 Discord 斜杠命令中使用的权限检查装饰器 `@app_commands.check()` 的实现原理和使用方法。

## 核心装饰器

### `@app_commands.check(check_auth)`
这是 Discord.py 提供的装饰器，用于在命令执行前进行权限验证。

```python
@tree.command(name="text", description="发送消息")
@app_commands.check(check_auth)  # 添加权限检查
async def text_command(interaction: discord.Interaction):
    # 命令逻辑
```

## 权限检查函数

### `check_auth(interaction)`
主权限检查函数，执行两级验证：

1. 首先检查用户ID是否在 `config.AUTHORIZED_USERS` 中
2. 如果不在，则调用 `check_role_auth` 检查身份组

```python
async def check_auth(interaction: discord.Interaction):
    if config.AUTHORIZED_USERS and str(interaction.user.id) not in config.AUTHORIZED_USERS:
        if not await check_role_auth(interaction):
            return False
        return True
    return True
```

### `check_role_auth(interaction)`
身份组权限检查函数：

1. 检查 `config.AUTHORIZED_ROLES` 是否存在且非空
2. 获取用户所有身份组ID
3. 检查是否有匹配的授权身份组

```python
async def check_role_auth(interaction: discord.Interaction):
    if not hasattr(config, 'AUTHORIZED_ROLES') or not config.AUTHORIZED_ROLES:
        return True
        
    user_roles = [role.id for role in interaction.user.roles]
    if not any(role_id in user_roles for role_id in config.AUTHORIZED_ROLES):
        await interaction.response.send_message("❌ 无权限", ephemeral=True)
        return False
    return True
```

## 配置要求

在 `config.py` 中需要定义以下变量：

```python
# 授权用户ID列表 (可选)
AUTHORIZED_USERS = ["123456789", "987654321"]  

# 授权身份组ID列表 (可选) 
AUTHORIZED_ROLES = [123456789, 987654321]  
```

