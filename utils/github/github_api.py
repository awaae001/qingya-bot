import logging
from typing import Optional, Tuple, List, Dict
from github import Github, GithubException, RateLimitExceededException
from github.Repository import Repository
from github.Commit import Commit
import time

logger = logging.getLogger(__name__)


class GitHubAPIClient:
    """GitHub API 客户端封装"""
    
    def __init__(self, token: str):
        self.token = token
        self.client = Github(token)
        self._rate_limit_checked = False
    
    def parse_repo_url(self, repo_url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        从仓库 URL 解析 owner 和 repo 名称
        
        Args:
            repo_url: 仓库 URL，如 https://github.com/owner/repo.git
            
        Returns:
            (owner, repo) 元组，解析失败返回 (None, None)
        """
        try:
            # 移除 .git 后缀和尾部斜杠
            url = repo_url.rstrip('.git').rstrip('/')
            parts = url.split('/')
            
            if len(parts) >= 2:
                return parts[-2], parts[-1]
            
            logger.error(f"无法解析仓库 URL: {repo_url}")
            return None, None
        except Exception as e:
            logger.error(f"解析仓库 URL 时出错: {e}")
            return None, None
    
    def get_repository(self, owner: str, repo: str) -> Optional[Repository]:
        """
        获取仓库对象
        
        Args:
            owner: 仓库所有者
            repo: 仓库名称
            
        Returns:
            Repository 对象，失败返回 None
        """
        try:
            repository = self.client.get_repo(f"{owner}/{repo}")
            logger.debug(f"成功获取仓库: {owner}/{repo}")
            return repository
        except GithubException as e:
            logger.error(f"获取仓库 {owner}/{repo} 失败: {e.status} - {e.data.get('message', 'Unknown error')}")
            return None
        except Exception as e:
            logger.error(f"获取仓库时出错: {e}")
            return None
    
    def get_branches(self, repository: Repository) -> List[str]:
        """
        获取仓库的所有分支名称
        
        Args:
            repository: Repository 对象
            
        Returns:
            分支名称列表
        """
        try:
            branches = [branch.name for branch in repository.get_branches()]
            logger.debug(f"仓库 {repository.full_name} 有 {len(branches)} 个分支")
            return branches
        except GithubException as e:
            logger.error(f"获取分支列表失败: {e.status} - {e.data.get('message', 'Unknown error')}")
            return []
        except Exception as e:
            logger.error(f"获取分支列表时出错: {e}")
            return []
    
    def get_latest_commit(self, repository: Repository, branch: str) -> Optional[Commit]:
        """
        获取指定分支的最新提交
        
        Args:
            repository: Repository 对象
            branch: 分支名称
            
        Returns:
            Commit 对象，失败返回 None
        """
        try:
            commits = repository.get_commits(sha=branch)
            latest_commit = commits[0]
            logger.debug(f"获取到分支 {branch} 的最新提交: {latest_commit.sha[:7]}")
            return latest_commit
        except GithubException as e:
            if e.status == 404:
                logger.warning(f"分支 {branch} 不存在")
            else:
                logger.error(f"获取最新提交失败: {e.status} - {e.data.get('message', 'Unknown error')}")
            return None
        except Exception as e:
            logger.error(f"获取最新提交时出错: {e}")
            return None
    
    def get_commits_since(self, repository: Repository, branch: str, since_sha: str, max_commits: int = 10) -> List[Commit]:
        """
        获取指定 SHA 之后的所有提交
        
        Args:
            repository: Repository 对象
            branch: 分支名称
            since_sha: 起始提交 SHA
            max_commits: 最大返回提交数
            
        Returns:
            Commit 对象列表（从新到旧）
        """
        try:
            commits = repository.get_commits(sha=branch)
            new_commits = []
            
            for commit in commits:
                if commit.sha == since_sha:
                    break
                new_commits.append(commit)
                if len(new_commits) >= max_commits:
                    break
            
            logger.debug(f"找到 {len(new_commits)} 个新提交")
            return new_commits
        except GithubException as e:
            logger.error(f"获取提交历史失败: {e.status} - {e.data.get('message', 'Unknown error')}")
            return []
        except Exception as e:
            logger.error(f"获取提交历史时出错: {e}")
            return []

    def get_commit_by_sha(self, repository: Repository, sha: str) -> Optional[Commit]:
        """
        获取指定 SHA 的提交
        
        Args:
            repository: Repository 对象
            sha: 提交 SHA
            
        Returns:
            Commit 对象，失败返回 None
        """
        try:
            commit = repository.get_commit(sha=sha)
            logger.debug(f"成功获取提交: {sha}")
            return commit
        except GithubException as e:
            logger.error(f"获取提交 {sha} 失败: {e.status} - {e.data.get('message', 'Unknown error')}")
            return None
        except Exception as e:
            logger.error(f"获取提交时出错: {e}")
            return None
    
    def get_commit_info(self, commit: Commit) -> Dict:
        """
        提取提交的详细信息
        
        Args:
            commit: Commit 对象
            
        Returns:
            包含提交信息的字典
        """
        try:
            author = commit.commit.author
            stats = commit.stats
            
            # 获取父提交数量（用于判断是否为合并提交）
            parents = commit.parents if hasattr(commit, 'parents') else []
            parent_count = len(parents)
            is_merge = parent_count >= 2
            
            return {
                'sha': commit.sha,
                'short_sha': commit.sha[:7],
                'message': commit.commit.message,
                'author_name': author.name,
                'author_email': author.email,
                'author_avatar': commit.author.avatar_url if commit.author else None,
                'author_login': commit.author.login if commit.author else None,
                'date': author.date,
                'url': commit.html_url,
                'additions': stats.additions,
                'deletions': stats.deletions,
                'total_changes': stats.total,
                'files_changed': commit.files.totalCount,
                'parent_count': parent_count,
                'is_merge': is_merge
            }
        except Exception as e:
            logger.error(f"提取提交信息时出错: {e}")
            return {}
    
    def check_rate_limit(self) -> Tuple[int, int]:
        """
        检查 API 速率限制
        
        Returns:
            (剩余请求数, 限制重置时间戳) 元组
        """
        try:
            rate_limit = self.client.get_rate_limit()
            core = rate_limit.core
            logger.debug(f"API 速率限制: {core.remaining}/{core.limit}, 重置时间: {core.reset}")
            return core.remaining, int(core.reset.timestamp())
        except Exception as e:
            logger.error(f"检查速率限制时出错: {e}")
            return 0, 0
    
    def wait_for_rate_limit(self):
        """等待速率限制重置"""
        remaining, reset_time = self.check_rate_limit()
        if remaining < 10:
            wait_time = max(0, reset_time - int(time.time()))
            if wait_time > 0:
                logger.warning(f"API 速率限制即将耗尽，等待 {wait_time} 秒...")
                time.sleep(min(wait_time, 60))  # 最多等待 60 秒
    
    def close(self):
        """关闭客户端连接"""
        try:
            self.client.close()
        except:
            pass