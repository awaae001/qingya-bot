import json
import logging
from pathlib import Path
from typing import Dict, Optional, Set

logger = logging.getLogger(__name__)


class CommitCache:
    """GitHub 提交缓存管理器"""
    
    def __init__(self, cache_path: str):
        self.cache_path = Path(cache_path)
        self.cache: Dict[str, Dict[str, str]] = {}
        self._ensure_cache_file()
        self.load_cache()
    
    def _ensure_cache_file(self):
        """确保缓存文件和目录存在"""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.cache_path.exists():
            self.cache_path.write_text('{}', encoding='utf-8')
            logger.info(f"创建新的缓存文件: {self.cache_path}")
    
    def load_cache(self) -> Dict[str, Dict[str, str]]:
        """
        从文件加载缓存
        
        Returns:
            缓存字典，格式: {"repo_id": {"branch_name": "commit_sha"}}
        """
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                self.cache = json.load(f)
            logger.debug(f"已加载缓存，包含 {len(self.cache)} 个仓库")
            return self.cache
        except json.JSONDecodeError as e:
            logger.error(f"解析缓存文件失败: {e}，将使用空缓存")
            self.cache = {}
            return self.cache
        except Exception as e:
            logger.error(f"加载缓存文件时出错: {e}")
            self.cache = {}
            return self.cache
    
    def save_cache(self):
        """保存缓存到文件"""
        try:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
            logger.debug(f"缓存已保存到 {self.cache_path}")
        except Exception as e:
            logger.error(f"保存缓存文件时出错: {e}")
    
    def get_last_commit(self, repo_id: str, branch: str) -> Optional[str]:
        """
        获取指定仓库和分支的最后提交 SHA
        
        Args:
            repo_id: 仓库 ID
            branch: 分支名称
            
        Returns:
            提交 SHA，如果不存在则返回 None
        """
        return self.cache.get(str(repo_id), {}).get(branch)
    
    def update_commit(self, repo_id: str, branch: str, commit_sha: str):
        """
        更新指定仓库和分支的最后提交 SHA
        
        Args:
            repo_id: 仓库 ID
            branch: 分支名称
            commit_sha: 提交 SHA
        """
        repo_id_str = str(repo_id)
        if repo_id_str not in self.cache:
            self.cache[repo_id_str] = {}
        
        old_sha = self.cache[repo_id_str].get(branch)
        self.cache[repo_id_str][branch] = commit_sha
        
        if old_sha != commit_sha:
            logger.debug(f"更新缓存: 仓库 {repo_id}, 分支 {branch}: {old_sha} -> {commit_sha}")
            self.save_cache()
    
    def get_repo_branches(self, repo_id: str) -> Set[str]:
        """
        获取指定仓库的所有已缓存分支
        
        Args:
            repo_id: 仓库 ID
            
        Returns:
            分支名称集合
        """
        return set(self.cache.get(str(repo_id), {}).keys())
    
    def has_repo(self, repo_id: str) -> bool:
        """
        检查是否存在指定仓库的缓存
        
        Args:
            repo_id: 仓库 ID
            
        Returns:
            是否存在
        """
        return str(repo_id) in self.cache
    
    def clear_repo(self, repo_id: str):
        """
        清除指定仓库的所有缓存
        
        Args:
            repo_id: 仓库 ID
        """
        repo_id_str = str(repo_id)
        if repo_id_str in self.cache:
            del self.cache[repo_id_str]
            self.save_cache()
            logger.info(f"已清除仓库 {repo_id} 的缓存")
    
    def clear_all(self):
        """清除所有缓存"""
        self.cache = {}
        self.save_cache()
        logger.info("已清除所有缓存")