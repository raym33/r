"""
Git Skill for R CLI.

Common Git operations:
- Repository status
- Commits and history
- Branches
- Diffs
"""

import subprocess
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class GitSkill(Skill):
    """Skill for Git operations."""

    name = "git"
    description = "Git operations: status, log, diff, branches, commits"

    # Timeout for git commands
    TIMEOUT = 30

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="git_status",
                description="Show Git repository status",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Repository path (default: current directory)",
                        },
                    },
                },
                handler=self.git_status,
            ),
            Tool(
                name="git_log",
                description="Show commit history",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Repository path",
                        },
                        "count": {
                            "type": "integer",
                            "description": "Number of commits to show (default: 10)",
                        },
                        "oneline": {
                            "type": "boolean",
                            "description": "Compact one-line format",
                        },
                    },
                },
                handler=self.git_log,
            ),
            Tool(
                name="git_diff",
                description="Show pending changes or diff between commits",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Repository path",
                        },
                        "staged": {
                            "type": "boolean",
                            "description": "Show only staged changes",
                        },
                        "file": {
                            "type": "string",
                            "description": "Specific file to diff",
                        },
                    },
                },
                handler=self.git_diff,
            ),
            Tool(
                name="git_branches",
                description="List repository branches",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Repository path",
                        },
                        "all": {
                            "type": "boolean",
                            "description": "Include remote branches",
                        },
                    },
                },
                handler=self.git_branches,
            ),
            Tool(
                name="git_commit",
                description="Create a commit with staged changes",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Repository path",
                        },
                        "message": {
                            "type": "string",
                            "description": "Commit message",
                        },
                        "add_all": {
                            "type": "boolean",
                            "description": "Add all modified files before commit",
                        },
                    },
                    "required": ["message"],
                },
                handler=self.git_commit,
            ),
            Tool(
                name="git_add",
                description="Add files to staging area",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Repository path",
                        },
                        "files": {
                            "type": "string",
                            "description": "Files to add (space-separated, or '.' for all)",
                        },
                    },
                    "required": ["files"],
                },
                handler=self.git_add,
            ),
            Tool(
                name="git_info",
                description="Show general repository information",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Repository path",
                        },
                    },
                },
                handler=self.git_info,
            ),
        ]

    def _run_git(self, args: list[str], cwd: Optional[Path] = None) -> tuple[bool, str]:
        """Execute a git command safely."""
        try:
            # Base git command
            cmd = ["git"] + args

            # Execute
            result = subprocess.run(
                cmd,
                check=False,
                cwd=cwd or Path.cwd(),
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT,
            )

            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip() or "Unknown error"

        except subprocess.TimeoutExpired:
            return False, "Timeout: command took too long"
        except FileNotFoundError:
            return False, "Git is not installed or not in PATH"
        except Exception as e:
            return False, f"Error executing git: {e}"

    def _get_repo_path(self, path: Optional[str]) -> Path:
        """Get repository path."""
        if path:
            return Path(path).expanduser().resolve()
        return Path.cwd()

    def _is_git_repo(self, path: Path) -> bool:
        """Check if path is a Git repository."""
        success, _ = self._run_git(["rev-parse", "--git-dir"], cwd=path)
        return success

    def git_status(self, path: Optional[str] = None) -> str:
        """Show repository status."""
        repo_path = self._get_repo_path(path)

        if not self._is_git_repo(repo_path):
            return f"Error: {repo_path} is not a Git repository"

        success, output = self._run_git(["status", "-sb"], cwd=repo_path)

        if success:
            return f"Status of {repo_path}:\n\n{output}"
        return f"Error: {output}"

    def git_log(
        self,
        path: Optional[str] = None,
        count: int = 10,
        oneline: bool = True,
    ) -> str:
        """Show commit history."""
        repo_path = self._get_repo_path(path)

        if not self._is_git_repo(repo_path):
            return f"Error: {repo_path} is not a Git repository"

        # Build arguments
        args = ["log", f"-{count}"]
        if oneline:
            args.append("--oneline")
        else:
            args.extend(["--format=%h | %an | %ar | %s"])

        success, output = self._run_git(args, cwd=repo_path)

        if success:
            return f"Last {count} commits:\n\n{output}"
        return f"Error: {output}"

    def git_diff(
        self,
        path: Optional[str] = None,
        staged: bool = False,
        file: Optional[str] = None,
    ) -> str:
        """Show pending changes."""
        repo_path = self._get_repo_path(path)

        if not self._is_git_repo(repo_path):
            return f"Error: {repo_path} is not a Git repository"

        # Build arguments
        args = ["diff", "--stat"]
        if staged:
            args.append("--staged")
        if file:
            args.append("--")
            args.append(file)

        success, output = self._run_git(args, cwd=repo_path)

        if success:
            if not output:
                return "No pending changes."

            # Also get detailed diff (limited)
            detail_args = ["diff"]
            if staged:
                detail_args.append("--staged")
            if file:
                detail_args.append("--")
                detail_args.append(file)

            _, detail = self._run_git(detail_args, cwd=repo_path)

            # Limit diff size
            if len(detail) > 5000:
                detail = detail[:5000] + "\n\n... (diff truncated)"

            return f"Changes summary:\n{output}\n\nDetails:\n{detail}"
        return f"Error: {output}"

    def git_branches(self, path: Optional[str] = None, all: bool = False) -> str:
        """List repository branches."""
        repo_path = self._get_repo_path(path)

        if not self._is_git_repo(repo_path):
            return f"Error: {repo_path} is not a Git repository"

        args = ["branch", "-v"]
        if all:
            args.append("-a")

        success, output = self._run_git(args, cwd=repo_path)

        if success:
            return f"Branches:\n\n{output}"
        return f"Error: {output}"

    def git_commit(
        self,
        message: str,
        path: Optional[str] = None,
        add_all: bool = False,
    ) -> str:
        """Create a commit."""
        repo_path = self._get_repo_path(path)

        if not self._is_git_repo(repo_path):
            return f"Error: {repo_path} is not a Git repository"

        # If add_all, first add all changes
        if add_all:
            success, output = self._run_git(["add", "-A"], cwd=repo_path)
            if not success:
                return f"Error adding files: {output}"

        # Check there's something to commit
        success, status = self._run_git(["diff", "--staged", "--stat"], cwd=repo_path)
        if success and not status:
            return "No staged changes to commit. Use git_add first."

        # Create commit
        success, output = self._run_git(["commit", "-m", message], cwd=repo_path)

        if success:
            return f"Commit created:\n\n{output}"
        return f"Error creating commit: {output}"

    def git_add(self, files: str, path: Optional[str] = None) -> str:
        """Add files to staging."""
        repo_path = self._get_repo_path(path)

        if not self._is_git_repo(repo_path):
            return f"Error: {repo_path} is not a Git repository"

        # Parse files
        file_list = files.split()

        success, output = self._run_git(["add"] + file_list, cwd=repo_path)

        if success:
            # Show what was added
            _, status = self._run_git(["status", "-s"], cwd=repo_path)
            return f"Files added to staging:\n\n{status}"
        return f"Error: {output}"

    def git_info(self, path: Optional[str] = None) -> str:
        """Show general repository information."""
        repo_path = self._get_repo_path(path)

        if not self._is_git_repo(repo_path):
            return f"Error: {repo_path} is not a Git repository"

        info = [f"Repository: {repo_path}\n"]

        # Current branch
        success, branch = self._run_git(["branch", "--show-current"], cwd=repo_path)
        if success:
            info.append(f"Current branch: {branch}")

        # Remote
        success, remote = self._run_git(["remote", "-v"], cwd=repo_path)
        if success and remote:
            info.append(f"\nRemotes:\n{remote}")

        # Last commit
        success, last_commit = self._run_git(
            ["log", "-1", "--format=%h - %s (%ar)"],
            cwd=repo_path,
        )
        if success:
            info.append(f"\nLast commit: {last_commit}")

        # Statistics
        success, stats = self._run_git(["rev-list", "--count", "HEAD"], cwd=repo_path)
        if success:
            info.append(f"Total commits: {stats}")

        # Untracked files
        success, untracked = self._run_git(
            ["status", "--porcelain", "-u"],
            cwd=repo_path,
        )
        if success:
            lines = untracked.split("\n") if untracked else []
            modified = len([l for l in lines if l.startswith(" M") or l.startswith("M ")])
            added = len([l for l in lines if l.startswith("??")])
            staged = len([l for l in lines if l.startswith("A ") or l.startswith("M ")])

            if modified or added or staged:
                info.append("\nPending changes:")
                if modified:
                    info.append(f"   Modified: {modified}")
                if staged:
                    info.append(f"   Staged: {staged}")
                if added:
                    info.append(f"   Untracked: {added}")

        return "\n".join(info)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "status")
        path = kwargs.get("path")

        if action == "status":
            return self.git_status(path)
        elif action == "log":
            return self.git_log(path, kwargs.get("count", 10))
        elif action == "diff":
            return self.git_diff(path, kwargs.get("staged", False))
        elif action == "branches":
            return self.git_branches(path, kwargs.get("all", False))
        elif action == "info":
            return self.git_info(path)
        elif action == "add":
            return self.git_add(kwargs.get("files", "."), path)
        elif action == "commit":
            message = kwargs.get("message", "")
            if not message:
                return "Error: message is required for commit"
            return self.git_commit(message, path, kwargs.get("add_all", False))
        else:
            return f"Unrecognized action: {action}"
