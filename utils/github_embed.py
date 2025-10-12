import discord
import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class BranchColorMapper:
    """分支颜色映射器"""
    
    # 分支颜色映射
    COLORS = {
        'main': 0x28a745,      # 绿色
        'master': 0x28a745,    # 绿色
        'develop': 0x0366d6,   # 蓝色
        'dev': 0x0366d6,       # 蓝色
        'feature': 0x6f42c1,   # 紫色
        'hotfix': 0xd73a49,    # 红色
        'bugfix': 0xffa500,    # 橙色
        'release': 0x00d4aa,   # 青色
        'default': 0x6a737d    # 灰色
    }
    
    @classmethod
    def get_color(cls, branch_name: str) -> int:
        """
        根据分支名称获取对应的颜色
        
        Args:
            branch_name: 分支名称
            
        Returns:
            颜色代码（十六进制整数）
        """
        branch_lower = branch_name.lower()
        
        # 精确匹配
        if branch_lower in cls.COLORS:
            return cls.COLORS[branch_lower]
        
        # 前缀匹配
        for prefix, color in cls.COLORS.items():
            if prefix != 'default' and branch_lower.startswith(prefix):
                return color
        
        # 默认颜色
        return cls.COLORS['default']
    
    @classmethod
    def get_branch_emoji(cls, branch_name: str) -> str:
        """
        根据分支名称获取对应的 emoji
        
        Args:
            branch_name: 分支名称
            
        Returns:
            emoji 字符串
        """
        branch_lower = branch_name.lower()
        
        if branch_lower in ['main', 'master']:
            return '🌳'
        elif branch_lower in ['develop', 'dev']:
            return '🔧'
        elif branch_lower.startswith('feature'):
            return '✨'
        elif branch_lower.startswith('hotfix'):
            return '🔥'
        elif branch_lower.startswith('bugfix'):
            return '🐛'
        elif branch_lower.startswith('release'):
            return '🚀'
        else:
            return '📝'


def create_commit_embed(
    commit_info: Dict,
    repo_name: str,
    branch_name: str,
    repo_url: str
) -> discord.Embed:
    """
    创建 GitHub 提交的 Discord Embed 消息
    
    Args:
        commit_info: 提交信息字典
        repo_name: 仓库名称（格式: owner/repo）
        branch_name: 分支名称
        repo_url: 仓库 URL
        
    Returns:
        Discord Embed 对象
    """
    try:
        # 获取分支颜色和 emoji
        color = BranchColorMapper.get_color(branch_name)
        branch_emoji = BranchColorMapper.get_branch_emoji(branch_name)
        
        # 创建 Embed
        embed = discord.Embed(
            color=color,
            timestamp=commit_info.get('date', datetime.now())
        )
        
        # 设置标题
        title = f"{branch_emoji} {repo_name} [{branch_name}]"
        embed.title = title
        embed.url = commit_info.get('url', repo_url)
        
        # 设置作者信息
        author_name = commit_info.get('author_name', 'Unknown')
        author_login = commit_info.get('author_login')
        if author_login:
            author_name = f"{author_name} (@{author_login})"
        
        author_avatar = commit_info.get('author_avatar')
        if author_avatar:
            embed.set_author(name=author_name, icon_url=author_avatar)
        else:
            embed.set_author(name=author_name)
        
        # 提交消息（限制 512 字符）
        commit_message = commit_info.get('message', 'No commit message')
        if len(commit_message) > 512:
            commit_message = commit_message[:509] + '...'
        
        # 分割提交消息为标题和描述
        message_lines = commit_message.split('\n', 1)
        commit_title = message_lines[0]
        commit_description = message_lines[1] if len(message_lines) > 1 else ''
        
        # 设置描述
        description = f"**{commit_title}**"
        if commit_description.strip():
            description += f"\n{commit_description.strip()}"
        embed.description = description
        
        # 添加提交信息字段
        short_sha = commit_info.get('short_sha', commit_info.get('sha', '')[:7])
        embed.add_field(
            name="📌 提交",
            value=f"[`{short_sha}`]({commit_info.get('url', '')})",
            inline=True
        )
        
        # 添加文件变更统计
        files_changed = commit_info.get('files_changed', 0)
        additions = commit_info.get('additions', 0)
        deletions = commit_info.get('deletions', 0)
        
        changes_text = f"📁 {files_changed} 个文件"
        if additions > 0 or deletions > 0:
            changes_text += f"\n🟢 +{additions} 🔴 -{deletions}"
        
        embed.add_field(
            name="📊 变更",
            value=changes_text,
            inline=True
        )
        
        # 添加分支信息
        embed.add_field(
            name="🌿 分支",
            value=f"`{branch_name}`",
            inline=True
        )
        
        # 设置页脚
        embed.set_footer(
            text=f"GitHub • {repo_name}",
            icon_url="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"
        )
        
        logger.debug(f"创建 Embed: {repo_name} [{branch_name}] {short_sha}")
        return embed
        
    except Exception as e:
        logger.error(f"创建 Embed 时出错: {e}")
        # 返回一个简单的错误 Embed
        error_embed = discord.Embed(
            title="❌ 创建提交通知失败",
            description=f"处理提交信息时出错: {str(e)}",
            color=0xff0000
        )
        return error_embed


def create_error_embed(error_message: str, repo_name: str = None) -> discord.Embed:
    """
    创建错误信息的 Embed
    
    Args:
        error_message: 错误消息
        repo_name: 仓库名称（可选）
        
    Returns:
        Discord Embed 对象
    """
    embed = discord.Embed(
        title="⚠️ GitHub 监听错误",
        description=error_message,
        color=0xff6b6b,
        timestamp=datetime.now()
    )
    
    if repo_name:
        embed.add_field(name="仓库", value=repo_name, inline=False)
    
    return embed


def create_rate_limit_embed(remaining: int, reset_time: int) -> discord.Embed:
    """
    创建速率限制警告的 Embed
    
    Args:
        remaining: 剩余请求数
        reset_time: 重置时间戳
        
    Returns:
        Discord Embed 对象
    """
    reset_dt = datetime.fromtimestamp(reset_time)
    
    embed = discord.Embed(
        title="⏱️ GitHub API 速率限制警告",
        description=f"剩余请求数: {remaining}\n重置时间: {reset_dt.strftime('%Y-%m-%d %H:%M:%S')}",
        color=0xffa500,
        timestamp=datetime.now()
    )
    
    return embed