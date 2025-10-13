import discord
import logging
import asyncio
from discord.ext import tasks
from typing import List, Dict, Optional, Tuple
import config
from utils.github.github_config_loader import load_github_repos, GitHubRepoConfig
from utils.github.github_api import GitHubAPIClient
from utils.github.commit_cache import CommitCache
from utils.github.github_embed import create_commit_embed, create_merge_commit_embed, create_error_embed

logger = logging.getLogger(__name__)


class GitHubMonitor:
    """GitHub 仓库监听器"""
    
    def __init__(self, discord_bot):
        self.bot = discord_bot
        self.repos: List[GitHubRepoConfig] = []
        self.cache = CommitCache(config.GITHUB_COMMITS_CACHE_PATH)
        self.api_clients: Dict[str, GitHubAPIClient] = {}
        self.is_first_run = True
        
    def load_repos(self):
        """加载仓库配置"""
        self.repos = load_github_repos(config.GITHUB_REPO_CONFIG_PATH)
        logger.info(f"已加载 {len(self.repos)} 个 GitHub 仓库配置")
        
        # 为每个仓库创建 API 客户端
        for repo_config in self.repos:
            if repo_config.github_token not in self.api_clients:
                self.api_clients[repo_config.github_token] = GitHubAPIClient(repo_config.github_token)
    
    async def check_repository(self, repo_config: GitHubRepoConfig):
        """
        检查单个仓库的更新
        
        Args:
            repo_config: 仓库配置对象
        """
        try:
            # 获取 API 客户端
            api_client = self.api_clients.get(repo_config.github_token)
            if not api_client:
                logger.error(f"仓库 {repo_config.id} 没有有效的 API 客户端")
                return
            
            # 解析仓库信息
            owner, repo = repo_config.get_repo_info()
            if not owner or not repo:
                logger.error(f"无法解析仓库 URL: {repo_config.repo_path}")
                return
            
            repo_name = f"{owner}/{repo}"
            logger.debug(f"检查仓库: {repo_name}")
            
            # 获取仓库对象
            repository = api_client.get_repository(owner, repo)
            if not repository:
                return
            
            # 获取所有分支
            branches = api_client.get_branches(repository)
            if not branches:
                logger.warning(f"仓库 {repo_name} 没有分支")
                return
            
            # 检查每个分支
            for branch in branches:
                await self.check_branch(repo_config, api_client, repository, branch, repo_name)
            
        except Exception as e:
            logger.error(f"检查仓库 {repo_config.id} 时出错: {e}", exc_info=True)
    
    async def check_branch(
        self,
        repo_config: GitHubRepoConfig,
        api_client: GitHubAPIClient,
        repository,
        branch: str,
        repo_name: str
    ):
        """
        检查单个分支的更新
        
        Args:
            repo_config: 仓库配置
            api_client: API 客户端
            repository: 仓库对象
            branch: 分支名称
            repo_name: 仓库名称
        """
        try:
            # 获取最新提交
            latest_commit = api_client.get_latest_commit(repository, branch)
            if not latest_commit:
                return
            
            latest_sha = latest_commit.sha
            
            # 获取缓存的最后提交
            cached_sha = self.cache.get_last_commit(str(repo_config.id), branch)
            
            # 如果没有缓存，则初始化缓存并跳过本次检查
            if not cached_sha:
                self.cache.update_commit(str(repo_config.id), branch, latest_sha)
                logger.info(f"初始化缓存: {repo_name} [{branch}] -> {latest_sha[:7]}")
                return

            # 如果是首次运行，则跳过通知，避免发送离线期间的提交
            if self.is_first_run:
                logger.debug(f"首次运行，跳过对 {repo_name} [{branch}] 的通知")
                return
            
            # 如果提交没有变化，跳过
            if cached_sha == latest_sha:
                logger.debug(f"分支 {branch} 没有新提交")
                return
            
            # 发现新提交，获取所有新提交
            logger.info(f"发现新提交: {repo_name} [{branch}] {cached_sha[:7]} -> {latest_sha[:7]}")
            new_commits = api_client.get_commits_since(repository, branch, cached_sha, max_commits=10)
            
            # 反转列表，从旧到新发送通知
            new_commits.reverse()
            
            # 检查是否有合并提交
            merge_commits = []
            regular_commits = []
            
            for commit in new_commits:
                commit_info = api_client.get_commit_info(commit)
                if commit_info.get('is_merge', False):
                    merge_commits.append(commit)
                else:
                    regular_commits.append(commit)
            
            # 如果存在合并提交，只发送合并提交的通知，跳过常规提交
            if merge_commits:
                logger.info(f"检测到 {len(merge_commits)} 个合并提交，跳过 {len(regular_commits)} 个常规提交")
                for commit in merge_commits:
                    await self.send_commit_notification(commit, repo_config, branch, repo_name, repository.html_url)
                    await asyncio.sleep(1)  # 避免发送过快
            else:
                # 没有合并提交，发送所有常规提交
                for commit in regular_commits:
                    await self.send_commit_notification(commit, repo_config, branch, repo_name, repository.html_url)
                    await asyncio.sleep(1)  # 避免发送过快
            
            # 更新缓存
            self.cache.update_commit(str(repo_config.id), branch, latest_sha)
            
        except Exception as e:
            logger.error(f"检查分支 {branch} 时出错: {e}", exc_info=True)
    
    async def send_commit_notification(
        self,
        commit,
        repo_config: GitHubRepoConfig,
        branch: str,
        repo_name: str,
        repo_url: str
    ):
        """
        发送提交通知到 Discord
        
        Args:
            commit: 提交对象
            repo_config: 仓库配置
            branch: 分支名称
            repo_name: 仓库名称
            repo_url: 仓库 URL
        """
        try:
            # 获取提交信息
            api_client = self.api_clients.get(repo_config.github_token)
            commit_info = api_client.get_commit_info(commit)
            
            if not commit_info:
                logger.error("无法获取提交信息")
                return
            
            # 根据是否为合并提交创建不同的 Embed
            if commit_info.get('is_merge', False):
                embed = create_merge_commit_embed(commit_info, repo_name, branch, repo_url)
            else:
                embed = create_commit_embed(commit_info, repo_name, branch, repo_url)
            
            # 检查服务器是否存在
            guild = self.bot.get_guild(repo_config.guild_id)
            if not guild:
                logger.error(f"找不到服务器 ID: {repo_config.guild_id}。请确保机器人已加入该服务器。")
                return

            # 获取目标频道
            channel = guild.get_channel(repo_config.channel_id)
            if not channel:
                logger.error(f"在服务器 '{guild.name}' 中找不到频道 ID: {repo_config.channel_id}。请检查频道 ID 是否正确以及机器人是否有权访问。")
                return
            
            # 发送消息
            await channel.send(embed=embed)
            logger.info(f"已发送提交通知: {repo_name} [{branch}] {commit_info['short_sha']} -> 频道 {repo_config.channel_id}")
            
        except discord.Forbidden:
            logger.error(f"没有权限发送消息到频道 {repo_config.channel_id}")
        except discord.HTTPException as e:
            logger.error(f"发送消息时出现 HTTP 错误: {e}")
        except Exception as e:
            logger.error(f"发送提交通知时出错: {e}", exc_info=True)

    async def send_notification_for_commit(self, repo_id: str, commit_sha: str) -> Tuple[Optional[int], Optional[str]]:
        """
        根据 commit SHA 手动发送提交通知

        Args:
            repo_id: 仓库配置 ID
            commit_sha: 提交的 SHA
            
        Returns:
            (channel_id, error_message) 元组。成功时 error_message 为 None。
        """
        try:
            # 查找仓库配置
            repo_config = next((r for r in self.repos if str(r.id) == str(repo_id)), None)
            if not repo_config:
                msg = f"找不到仓库配置 ID: {repo_id}"
                logger.error(msg)
                return None, msg

            # 获取 API 客户端
            api_client = self.api_clients.get(repo_config.github_token)
            if not api_client:
                msg = f"仓库 {repo_config.id} 没有有效的 API 客户端"
                logger.error(msg)
                return None, msg

            # 解析仓库信息
            owner, repo = repo_config.get_repo_info()
            if not owner or not repo:
                msg = f"无法解析仓库 URL: {repo_config.repo_path}"
                logger.error(msg)
                return None, msg
            
            repo_name = f"{owner}/{repo}"

            # 获取仓库对象
            repository = api_client.get_repository(owner, repo)
            if not repository:
                msg = f"无法获取仓库: {repo_name}"
                logger.error(msg)
                return None, msg

            # 获取提交对象
            commit = api_client.get_commit_by_sha(repository, commit_sha)
            if not commit:
                msg = f"在仓库 {repo_name} 中找不到提交: {commit_sha}"
                logger.warning(msg)
                return None, msg

            # 获取提交所在的分支
            # 注意：一个提交可能存在于多个分支中。这里我们简单地取第一个。
            branches = list(commit.get_branches_where_head())
            branch_name = branches[0].name if branches else "Unknown"

            # 发送通知
            await self.send_commit_notification(commit, repo_config, branch_name, repo_name, repository.html_url)
            
            return repo_config.channel_id, None

        except Exception as e:
            logger.error(f"为提交 {commit_sha} 发送通知时出错: {e}", exc_info=True)
            return None, f"处理请求时发生内部错误: {e}"
    
    async def check_all_repositories(self):
        """检查所有配置的仓库"""
        if not self.repos:
            logger.debug("没有配置任何仓库")
            return
        
        logger.info(f"开始检查 {len(self.repos)} 个仓库...")
        
        # 并发检查所有仓库
        tasks = [self.check_repository(repo) for repo in self.repos]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # 第一次运行后设置标志
        if self.is_first_run:
            self.is_first_run = False
            logger.info("首次运行完成，后续将发送新提交通知")
        
        logger.info("仓库检查完成")
    
    @tasks.loop(seconds=config.GITHUB_CHECK_INTERVAL)
    async def monitor_task(self):
        """定时监听任务"""
        try:
            await self.check_all_repositories()
        except Exception as e:
            logger.error(f"监听任务执行出错: {e}", exc_info=True)
    
    @monitor_task.before_loop
    async def before_monitor_task(self):
        """等待 bot 准备就绪"""
        await self.bot.wait_until_ready()
        logger.info("GitHub 监听器已准备就绪")
    
    def start(self):
        """启动监听器"""
        try:
            self.load_repos()
            if self.repos:
                self.monitor_task.start()
                logger.info(f"GitHub 监听器已启动，检查间隔: {config.GITHUB_CHECK_INTERVAL} 秒")
            else:
                logger.warning("没有配置任何 GitHub 仓库，监听器未启动")
        except Exception as e:
            logger.error(f"启动 GitHub 监听器时出错: {e}", exc_info=True)
    
    def stop(self):
        """停止监听器"""
        try:
            if self.monitor_task.is_running():
                self.monitor_task.cancel()
            
            # 关闭所有 API 客户端
            for client in self.api_clients.values():
                client.close()
            
            logger.info("GitHub 监听器已停止")
        except Exception as e:
            logger.error(f"停止 GitHub 监听器时出错: {e}")
    
    def reload_config(self):
        """重新加载配置"""
        try:
            logger.info("重新加载 GitHub 仓库配置...")
            self.load_repos()
            logger.info("配置重新加载完成")
        except Exception as e:
            logger.error(f"重新加载配置时出错: {e}")