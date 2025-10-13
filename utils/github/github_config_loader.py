import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class GitHubRepoConfig:
    """GitHub 仓库配置类"""
    
    def __init__(self, config_dict: dict):
        self.id = config_dict.get("id")
        self.repo_path = config_dict.get("github_setting", {}).get("repo_path", "")
        self.repo_branch = config_dict.get("github_setting", {}).get("repo_branch", "")
        self.github_token = config_dict.get("github_setting", {}).get("github_token", "")
        self.guild_id = int(config_dict.get("guild_id", 0))
        self.channel_id = int(config_dict.get("channel_id", 0))
        self.enabled = config_dict.get("enabled", True)
        self.check_interval = config_dict.get("check_interval")
        
    def is_valid(self) -> bool:
        """验证配置是否有效"""
        if not self.repo_path:
            logger.error(f"仓库 ID {self.id}: repo_path 不能为空")
            return False
        if not self.github_token:
            logger.error(f"仓库 ID {self.id}: github_token 不能为空")
            return False
        if not self.channel_id:
            logger.error(f"仓库 ID {self.id}: channel_id 不能为空")
            return False
        return True
    
    def get_repo_info(self) -> tuple:
        """从 repo_path 提取 owner 和 repo 名称"""
        # 支持格式: https://github.com/owner/repo.git 或 https://github.com/owner/repo
        path = self.repo_path.rstrip('.git').rstrip('/')
        parts = path.split('/')
        if len(parts) >= 2:
            return parts[-2], parts[-1]
        return None, None
    
    def __repr__(self):
        owner, repo = self.get_repo_info()
        return f"GitHubRepoConfig(id={self.id}, repo={owner}/{repo}, channel={self.channel_id})"


def load_github_repos(config_path: str) -> List[GitHubRepoConfig]:
    """
    加载 GitHub 仓库配置
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        GitHubRepoConfig 对象列表
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        logger.warning(f"GitHub 配置文件不存在: {config_path}")
        return []
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        repos = []
        for key, value in config_data.items():
            try:
                repo_config = GitHubRepoConfig(value)
                
                # 只添加启用且有效的配置
                if repo_config.enabled and repo_config.is_valid():
                    repos.append(repo_config)
                    owner, repo = repo_config.get_repo_info()
                    logger.info(f"已加载仓库配置: {owner}/{repo} -> 频道 {repo_config.channel_id}")
                elif not repo_config.enabled:
                    logger.info(f"仓库 ID {repo_config.id} 已禁用，跳过")
                    
            except Exception as e:
                logger.error(f"解析仓库配置 {key} 时出错: {e}")
                continue
        
        logger.info(f"成功加载 {len(repos)} 个 GitHub 仓库配置")
        return repos
        
    except json.JSONDecodeError as e:
        logger.error(f"解析 GitHub 配置文件失败: {e}")
        return []
    except Exception as e:
        logger.error(f"加载 GitHub 配置文件时出错: {e}")
        return []


def reload_github_repos(config_path: str) -> List[GitHubRepoConfig]:
    """
    重新加载 GitHub 仓库配置（用于热重载）
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        GitHubRepoConfig 对象列表
    """
    logger.info("重新加载 GitHub 仓库配置...")
    return load_github_repos(config_path)