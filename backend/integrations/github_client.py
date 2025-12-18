"""
GitHub Client - Handles PR creation and repository operations.

Uses PyGithub to interact with GitHub API for creating branches,
committing files, and opening pull requests.
"""

import base64
from typing import Dict, Optional
from datetime import datetime

from github import Github, GithubException
from github.Repository import Repository

from backend.config import get_settings


class GitHubClient:
    """
    Client for GitHub operations.
    
    Handles:
    - Creating feature branches
    - Committing code and test files
    - Opening pull requests
    """
    
    def __init__(self, owner: Optional[str] = None, repo: Optional[str] = None):
        """
        Initialize GitHub client.
        
        Args:
            owner: Repository owner (username or org). Falls back to env var.
            repo: Repository name. Falls back to env var.
        """
        self.settings = get_settings()
        
        if not self.settings.github_token:
            raise ValueError(
                "GitHub token not configured. Please set GITHUB_TOKEN environment variable."
            )
        
        self.github = Github(self.settings.github_token)
        self._owner = owner or self.settings.github_owner
        self._repo_name = repo or self.settings.github_repo
        self._repo: Optional[Repository] = None
    
    @property
    def repo(self) -> Repository:
        """Get the configured repository."""
        if self._repo is None:
            if not self._owner or not self._repo_name:
                raise ValueError(
                    "GitHub repository not configured. "
                    "Please provide github_repo_url when creating the task, "
                    "or set GITHUB_OWNER and GITHUB_REPO environment variables."
                )
            
            self._repo = self.github.get_repo(f"{self._owner}/{self._repo_name}")
        
        return self._repo
    
    def create_pull_request(
        self,
        title: str,
        body: str,
        code_files: Dict[str, str],
        test_files: Dict[str, str],
        base_branch: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Create a pull request with the given files.
        
        Args:
            title: PR title
            body: PR description
            code_files: Dict of {filename: content} for implementation files
            test_files: Dict of {filename: content} for test files
            base_branch: Base branch to merge into (default from settings)
            
        Returns:
            Dict with pr_url, branch_name, and pr_number
        """
        base_branch = base_branch or self.settings.github_base_branch
        
        # Generate unique branch name
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        branch_name = f"ai-tech-lead/{timestamp}"
        
        # Create the branch
        self._create_branch(branch_name, base_branch)
        
        # Commit all files
        all_files = {**code_files, **test_files}
        self._commit_files(branch_name, all_files, f"feat: {title}")
        
        # Create the pull request
        pr = self.repo.create_pull(
            title=title,
            body=body,
            head=branch_name,
            base=base_branch,
        )
        
        return {
            "pr_url": pr.html_url,
            "branch_name": branch_name,
            "pr_number": pr.number,
        }
    
    def _create_branch(self, branch_name: str, base_branch: str):
        """Create a new branch from the base branch."""
        # Get the SHA of the base branch
        base_ref = self.repo.get_git_ref(f"heads/{base_branch}")
        base_sha = base_ref.object.sha
        
        # Create the new branch
        self.repo.create_git_ref(
            ref=f"refs/heads/{branch_name}",
            sha=base_sha,
        )
    
    def _commit_files(
        self, 
        branch_name: str, 
        files: Dict[str, str], 
        commit_message: str
    ):
        """
        Commit multiple files to a branch.
        
        Uses the Git Data API for atomic multi-file commits.
        """
        # Get the current commit SHA
        branch_ref = self.repo.get_git_ref(f"heads/{branch_name}")
        base_sha = branch_ref.object.sha
        base_commit = self.repo.get_git_commit(base_sha)
        base_tree = base_commit.tree
        
        # Create blobs for each file
        tree_elements = []
        for filepath, content in files.items():
            blob = self.repo.create_git_blob(content, "utf-8")
            tree_elements.append({
                "path": filepath,
                "mode": "100644",  # Regular file
                "type": "blob",
                "sha": blob.sha,
            })
        
        # Create a new tree with the files
        new_tree = self.repo.create_git_tree(tree_elements, base_tree)
        
        # Create the commit
        new_commit = self.repo.create_git_commit(
            message=commit_message,
            tree=new_tree,
            parents=[base_commit],
        )
        
        # Update the branch reference
        branch_ref.edit(sha=new_commit.sha)
    
    def get_repository_info(self) -> Dict:
        """Get information about the configured repository."""
        return {
            "full_name": self.repo.full_name,
            "default_branch": self.repo.default_branch,
            "html_url": self.repo.html_url,
            "description": self.repo.description,
        }
    
    def list_branches(self, limit: int = 10) -> list:
        """List recent branches in the repository."""
        branches = list(self.repo.get_branches())[:limit]
        return [{"name": b.name, "protected": b.protected} for b in branches]
    
    def get_file_content(self, filepath: str, branch: Optional[str] = None) -> Optional[str]:
        """
        Get the content of a file from the repository.
        
        Args:
            filepath: Path to the file in the repository
            branch: Branch to read from (default: base branch)
            
        Returns:
            File content as string, or None if not found
        """
        branch = branch or self.settings.github_base_branch
        
        try:
            content = self.repo.get_contents(filepath, ref=branch)
            if isinstance(content, list):
                return None  # It's a directory
            return base64.b64decode(content.content).decode('utf-8')
        except GithubException:
            return None
    
    def check_connection(self) -> Dict:
        """
        Check the GitHub connection and permissions.
        
        Returns:
            Dict with connection status and user info
        """
        try:
            user = self.github.get_user()
            return {
                "connected": True,
                "user": user.login,
                "rate_limit": {
                    "remaining": self.github.rate_limiting[0],
                    "limit": self.github.rate_limiting[1],
                },
            }
        except GithubException as e:
            return {
                "connected": False,
                "error": str(e),
            }

