# GitHub 仓库监听功能使用文档

## 功能概述

GitHub 仓库监听功能可以自动监听指定 GitHub 仓库的推送事件，并在 Discord 频道中发送精美的 Embed 消息通知。

## 主要特性

- ✅ 支持监听多个 GitHub 仓库
- ✅ 监听所有分支的推送事件
- ✅ 使用不同颜色区分不同类型的分支
- ✅ 显示详细的提交信息（作者、消息、文件变更等）
- ✅ 每个仓库可配置独立的 Discord 频道
- ✅ 自动缓存提交记录，避免重复通知
- ✅ 支持热重载配置

## 配置说明

### 1. 配置文件位置

配置文件位于：`config/github_repo.json`

### 2. 配置文件格式

```json
{
    "1": {
        "id": 1,
        "github_setting": {
            "repo_path": "https://github.com/owner/repo.git",
            "repo_branch": "",
            "github_token": "ghp_xxxxxxxxxxxx"
        },
        "channel_id": "1234567890123456789",
        "enabled": true,
        "check_interval": 300
    },
    "2": {
        "id": 2,
        "github_setting": {
            "repo_path": "https://github.com/another/repo.git",
            "repo_branch": "",
            "github_token": "ghp_xxxxxxxxxxxx"
        },
        "channel_id": "9876543210987654321",
        "enabled": true
    }
}
```

### 3. 配置字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `id` | 整数 | 是 | 仓库配置的唯一标识符 |
| `github_setting.repo_path` | 字符串 | 是 | GitHub 仓库 URL（支持 .git 后缀） |
| `github_setting.repo_branch` | 字符串 | 否 | 保留字段，当前监听所有分支 |
| `github_setting.github_token` | 字符串 | 是 | GitHub Personal Access Token |
| `channel_id` | 字符串 | 是 | Discord 频道 ID（接收通知的频道） |
| `enabled` | 布尔值 | 否 | 是否启用此仓库监听（默认 true） |
| `check_interval` | 整数 | 否 | 检查间隔（秒），覆盖全局设置 |

## 分支颜色映射

系统会根据分支名称自动选择不同的颜色：

| 分支类型 | 颜色 | Emoji |
|---------|------|-------|
| main / master | 🟢 绿色 | 🌳 |
| develop / dev | 🔵 蓝色 | 🔧 |
| feature/* | 🟣 紫色 | ✨ |
| hotfix/* | 🔴 红色 | 🔥 |
| bugfix/* | 🟠 橙色 | 🐛 |
| release/* | 🟦 青色 | 🚀 |
| 其他 | ⚫ 灰色 | 📝 |

## GitHub Token 获取

1. 登录 GitHub
2. 进入 Settings → Developer settings → Personal access tokens → Tokens (classic)
3. 点击 "Generate new token (classic)"
4. 设置 Token 名称和过期时间
5. 勾选权限：
   - `repo` (如果是私有仓库)
   - `public_repo` (如果只监听公共仓库)
6. 生成并复制 Token

**注意**：Token 只显示一次，请妥善保管！

## Discord 频道 ID 获取

1. 在 Discord 中启用开发者模式：
   - 用户设置 → 高级 → 开发者模式
2. 右键点击目标频道
3. 选择"复制频道 ID"

## 环境变量配置

在 `.env` 文件中可以配置以下参数：

```env
# GitHub 监听配置
GITHUB_REPO_CONFIG_PATH=./config/github_repo.json
GITHUB_COMMITS_CACHE_PATH=./data/github_commits_cache.json
GITHUB_CHECK_INTERVAL=300  # 检查间隔（秒），默认 5 分钟
```

## Embed 消息内容

每个提交通知包含以下信息：

- **标题**：仓库名称 + 分支名称（带 emoji）
- **作者**：提交者姓名、GitHub 用户名和头像
- **提交消息**：完整的提交消息（最多 512 字符）
- **提交 SHA**：短 SHA 值，可点击跳转到 GitHub
- **文件变更**：修改的文件数量、新增行数、删除行数
- **分支信息**：当前分支名称
- **时间戳**：提交时间

## 工作流程

```
1. Bot 启动 → 加载配置文件
2. 初始化 GitHub API 客户端
3. 启动定时任务（默认 5 分钟）
4. 检查所有配置的仓库
5. 获取每个分支的最新提交
6. 与缓存比对，发现新提交
7. 创建 Embed 消息
8. 发送到指定 Discord 频道
9. 更新缓存
10. 等待下次检查
```

## 首次运行

首次运行时，系统会：
1. 获取所有分支的当前最新提交
2. 保存到缓存文件
3. **不发送通知**（避免历史提交刷屏）

之后的运行才会发送新提交的通知。

## 缓存文件

缓存文件位于：`data/github_commits_cache.json`

格式：
```json
{
    "1": {
        "main": "abc123def456...",
        "develop": "789ghi012jkl..."
    },
    "2": {
        "master": "mno345pqr678..."
    }
}
```

**注意**：删除缓存文件会导致下次运行时重新初始化，不会发送历史通知。

## 常见问题

### 1. 为什么没有收到通知？

检查以下几点：
- 配置文件格式是否正确
- GitHub Token 是否有效
- Discord 频道 ID 是否正确
- Bot 是否有发送消息的权限
- 查看日志文件确认错误信息

### 2. 如何临时禁用某个仓库？

在配置文件中设置 `"enabled": false`：
```json
{
    "1": {
        "id": 1,
        "enabled": false,
        ...
    }
}
```

### 3. 如何调整检查频率？

方法一：修改全局配置（.env 文件）
```env
GITHUB_CHECK_INTERVAL=600  # 改为 10 分钟
```

方法二：为单个仓库设置（config/github_repo.json）
```json
{
    "1": {
        "id": 1,
        "check_interval": 600,
        ...
    }
}
```

### 4. GitHub API 速率限制

- 未认证：60 次/小时
- 已认证：5000 次/小时

建议：
- 使用 Token 认证
- 检查间隔不要太短（建议 ≥ 5 分钟）
- 监听的仓库数量不要太多

### 5. 如何监听私有仓库？

确保 GitHub Token 具有 `repo` 权限（而不仅仅是 `public_repo`）。

### 6. 提交消息被截断了？

提交消息最多显示 512 字符。如果需要查看完整消息，可以点击提交 SHA 跳转到 GitHub。

## 日志查看

系统会记录详细的运行日志，包括：
- 配置加载情况
- 仓库检查过程
- 新提交发现
- 消息发送状态
- 错误信息

日志级别：
- INFO：正常运行信息
- WARNING：警告信息
- ERROR：错误信息
- DEBUG：调试信息（需要修改日志级别）

## 最佳实践

1. **Token 安全**：
   - 不要将 Token 提交到版本控制
   - 定期更换 Token
   - 使用最小权限原则

2. **检查频率**：
   - 活跃仓库：5-10 分钟
   - 普通仓库：10-30 分钟
   - 低频仓库：30-60 分钟

3. **频道管理**：
   - 重要仓库使用独立频道
   - 相关仓库可共用频道
   - 设置合适的频道权限

4. **监控维护**：
   - 定期检查日志
   - 关注 API 速率限制
   - 及时更新失效的 Token

## 故障排除

### 问题：Bot 启动后没有监听任务

**解决方案**：
1. 检查配置文件是否存在
2. 检查配置文件格式是否正确
3. 查看日志中的错误信息

### 问题：提示 "找不到频道"

**解决方案**：
1. 确认频道 ID 是否正确
2. 确认 Bot 已加入该服务器
3. 确认频道在 DISCORD_SERVERS 配置中

### 问题：提示 "没有权限发送消息"

**解决方案**：
1. 检查 Bot 的角色权限
2. 检查频道的权限设置
3. 确保 Bot 有 "发送消息" 和 "嵌入链接" 权限

## 技术支持

如有问题，请查看：
1. 日志文件
2. GitHub Issues
3. 项目文档

---

**版本**：1.0.0  
**更新日期**：2025-10-12