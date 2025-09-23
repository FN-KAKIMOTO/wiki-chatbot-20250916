"""
GitHub + Git LFS による永続データ同期管理

このモジュールは、Streamlit CloudでのRAGデータとチャット履歴の永続化を
GitHub + Git LFSを使用して実現します。

主な機能:
- GitHubからのデータダウンロード（復元）
- GitHubへのデータアップロード（バックアップ）
- 起動時の自動同期
- 定期的な自動バックアップ

使用例:
    sync = GitHubDataSync(
        repo_url="https://github.com/username/wiki-chatbot-data.git",
        token="ghp_xxxxxxxxxxxx"
    )

    # 起動時同期
    sync.sync_on_startup()

    # データバックアップ
    sync.upload_data("Manual backup")
"""

import os
import json
import shutil
import subprocess
import tempfile
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import streamlit as st


class GitHubDataSync:
    """GitHub + Git LFS による永続データ同期管理クラス"""

    def __init__(self,
                 repo_url: str,
                 token: str,
                 local_data_dir: str = "data",
                 branch: str = "main"):
        """
        初期化

        Args:
            repo_url: GitHubリポジトリのURL
            token: GitHub Personal Access Token
            local_data_dir: ローカルデータディレクトリ
            branch: 使用するブランチ名
        """
        self.repo_url = repo_url
        self.token = token
        self.local_data_dir = Path(local_data_dir)
        self.branch = branch
        self.temp_dir = None
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """ログ設定"""
        logger = logging.getLogger("github_sync")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def _is_git_lfs_available(self) -> bool:
        """Git LFSが利用可能かチェック"""
        try:
            result = subprocess.run(
                ["git", "lfs", "version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def _fix_file_permissions(self, directory: Path):
        """ディレクトリ内のファイル権限を修正（readonly対策）"""
        try:
            for root, dirs, files in os.walk(directory):
                # ディレクトリの権限設定
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        os.chmod(dir_path, 0o755)
                    except Exception:
                        pass

                # ファイルの権限設定
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    try:
                        os.chmod(file_path, 0o644)
                    except Exception:
                        pass

            self.logger.info("File permissions fixed for downloaded data")
        except Exception as e:
            self.logger.warning(f"Failed to fix file permissions: {e}")


    def _push_with_retry(self, cwd: str, max_retries: int = 3) -> bool:
        """Git push with conflict resolution and retries"""
        for attempt in range(max_retries):
            # Try normal push
            success = self._run_git_command(["git", "push", "origin", self.branch], cwd)
            if success:
                self.logger.info(f"Push successful on attempt {attempt + 1}")
                return True

            self.logger.warning(f"Push attempt {attempt + 1} failed, trying pull and merge...")

            # Pull latest changes with strategy
            pull_success = self._run_git_command(["git", "pull", "origin", self.branch, "--no-edit", "--strategy=recursive", "-X", "ours"], cwd)
            if not pull_success:
                self.logger.error(f"Pull failed on attempt {attempt + 1}")
                continue

            # Try push again after pull
            push_success = self._run_git_command(["git", "push", "origin", self.branch], cwd)
            if push_success:
                self.logger.info(f"Push successful after pull on attempt {attempt + 1}")
                return True

        self.logger.error("Push failed after all retries")
        return False

    def _run_git_command(self, command: list, cwd: str) -> bool:
        """
        Git コマンド実行

        Args:
            command: 実行するGitコマンドのリスト
            cwd: 実行ディレクトリ

        Returns:
            成功時True、失敗時False
        """
        try:
            # GitHub トークンを含む認証URL作成
            if self.token and "clone" in command and len(command) > 2:
                auth_url = self.repo_url.replace(
                    "https://", f"https://{self.token}@"
                )
                command[2] = auth_url

            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                self.logger.error(f"Git command failed: {result.stderr}")
                return False

            self.logger.info(f"Git command success: {' '.join(command[:2])}")
            return True

        except subprocess.TimeoutExpired:
            self.logger.error("Git command timed out")
            return False
        except Exception as e:
            self.logger.error(f"Git command error: {e}")
            return False

    def download_data(self) -> bool:
        """
        GitHubからデータをダウンロード

        Returns:
            成功時True、失敗時False
        """
        try:
            self.logger.info("Starting data download from GitHub...")

            # 一時ディレクトリ作成
            self.temp_dir = tempfile.mkdtemp()

            # リポジトリクローン
            clone_success = self._run_git_command([
                "git", "clone", self.repo_url, self.temp_dir
            ], ".")

            if not clone_success:
                return False

            # Git LFS ファイル取得（利用可能な場合のみ）
            if self._is_git_lfs_available():
                lfs_success = self._run_git_command([
                    "git", "lfs", "pull"
                ], self.temp_dir)

                if not lfs_success:
                    self.logger.warning("LFS pull failed, continuing...")
            else:
                self.logger.info("Git LFS not available, skipping LFS pull")

            # データディレクトリ確保
            self.local_data_dir.mkdir(exist_ok=True)

            # データファイルコピー（安全性向上）
            source_data = Path(self.temp_dir) / "data"
            if source_data.exists():
                try:
                    # 既存データのバックアップ
                    if self.local_data_dir.exists() and any(self.local_data_dir.iterdir()):
                        backup_dir = self.local_data_dir.parent / f"data_backup_{int(time.time())}"
                        shutil.move(str(self.local_data_dir), str(backup_dir))
                        self.logger.info(f"Existing data backed up to: {backup_dir}")

                    # 新しいデータをコピー
                    shutil.copytree(
                        source_data,
                        self.local_data_dir,
                        dirs_exist_ok=True
                    )

                    # コピーしたファイルの権限を適切に設定（readonly対策）
                    self._fix_file_permissions(self.local_data_dir)

                    # ダウンロードしたChromeDBの整合性チェック
                    chroma_file = self.local_data_dir / "chroma_db" / "chroma.sqlite3"
                    if chroma_file.exists():
                        import sqlite3
                        try:
                            conn = sqlite3.connect(str(chroma_file), timeout=5.0)
                            conn.execute("SELECT COUNT(*) FROM sqlite_master")
                            conn.close()
                            self.logger.info("Downloaded ChromaDB integrity check passed")
                        except Exception as db_error:
                            self.logger.error(f"Downloaded ChromaDB is corrupted: {db_error}")
                            return False

                    self.logger.info("Data download completed")
                    return True
                except Exception as copy_error:
                    self.logger.error(f"Data copy during download failed: {copy_error}")
                    return False
            else:
                self.logger.info("No existing data found, starting fresh")
                return True

        except Exception as e:
            self.logger.error(f"Data download failed: {e}")
            return False
        finally:
            # 一時ディレクトリクリーンアップ
            if self.temp_dir and Path(self.temp_dir).exists():
                shutil.rmtree(self.temp_dir)

    def upload_data(self, commit_message: str = None) -> bool:
        """
        データをGitHubにアップロード

        Args:
            commit_message: コミットメッセージ

        Returns:
            成功時True、失敗時False
        """
        try:
            if not commit_message:
                commit_message = f"Auto backup - {datetime.now().isoformat()}"

            self.logger.info("Starting data upload to GitHub...")

            # 一時ディレクトリ作成
            self.temp_dir = tempfile.mkdtemp()

            # リポジトリクローン
            clone_success = self._run_git_command([
                "git", "clone", self.repo_url, self.temp_dir
            ], ".")

            if not clone_success:
                return False

            # データディレクトリコピー（安全性向上）
            dest_data = Path(self.temp_dir) / "data"
            try:
                if dest_data.exists():
                    shutil.rmtree(dest_data)

                if self.local_data_dir.exists():
                    # ChromaDBファイルの整合性確認
                    chroma_file = self.local_data_dir / "chroma_db" / "chroma.sqlite3"
                    if chroma_file.exists():
                        import sqlite3
                        try:
                            # データベースの簡単な整合性チェック
                            conn = sqlite3.connect(str(chroma_file), timeout=5.0)
                            conn.execute("SELECT COUNT(*) FROM sqlite_master")
                            conn.close()
                            self.logger.info("ChromaDB integrity check passed")
                        except Exception as db_error:
                            self.logger.warning(f"ChromaDB integrity check failed: {db_error}")

                    shutil.copytree(self.local_data_dir, dest_data)
                    self.logger.info(f"Data copied successfully: {len(list(dest_data.rglob('*')))} files")
                else:
                    self.logger.warning("Local data directory does not exist")
                    return False
            except Exception as copy_error:
                self.logger.error(f"Data copy failed: {copy_error}")
                return False

            # Git 設定
            config_commands = [
                ["git", "config", "user.email", "streamlit-bot@example.com"],
                ["git", "config", "user.name", "Streamlit Bot"]
            ]

            for cmd in config_commands:
                self._run_git_command(cmd, self.temp_dir)

            # Git LFS 設定は既存のリポジトリ設定を使用（初期化はスキップ）
            self.logger.info("Using existing Git LFS configuration from repository")

            # ファイル追加・コミット（競合対応版）
            git_commands = [
                ["git", "add", "."],
                ["git", "commit", "-m", commit_message]
            ]

            for cmd in git_commands:
                success = self._run_git_command(cmd, self.temp_dir)
                if not success and "commit" in cmd:
                    self.logger.info("No changes to commit")
                    return True
                elif not success:
                    return False

            # Push with conflict resolution
            push_success = self._push_with_retry(self.temp_dir)
            if not push_success:
                self.logger.error("Push failed after retries")
                return False

            self.logger.info("Data upload completed")
            return True

        except Exception as e:
            self.logger.error(f"Data upload failed: {e}")
            return False
        finally:
            # 一時ディレクトリクリーンアップ
            if self.temp_dir and Path(self.temp_dir).exists():
                shutil.rmtree(self.temp_dir)

    def sync_on_startup(self) -> bool:
        """
        アプリ起動時の同期

        既存データがない場合のみGitHubからダウンロードする

        Returns:
            成功時True、失敗時False
        """
        self.logger.info("Performing startup data sync...")

        # 既存データ確認
        chroma_db = self.local_data_dir / "chroma_db" / "chroma.sqlite3"
        sqlite_db = self.local_data_dir / "chatbot.db"

        if not chroma_db.exists() or not sqlite_db.exists():
            self.logger.info("Local data missing, downloading from GitHub...")
            return self.download_data()

        self.logger.info("Local data exists, skipping download")
        return True

    def get_sync_status(self) -> Dict[str, Any]:
        """
        同期状況の取得

        Returns:
            同期状況の辞書
        """
        chroma_db = self.local_data_dir / "chroma_db" / "chroma.sqlite3"
        sqlite_db = self.local_data_dir / "chatbot.db"

        # ChromaDBの整合性チェック
        chroma_integrity = False
        if chroma_db.exists():
            try:
                import sqlite3
                conn = sqlite3.connect(str(chroma_db), timeout=5.0)
                conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='databases'")
                result = conn.fetchone()
                chroma_integrity = result and result[0] > 0
                conn.close()
            except Exception:
                chroma_integrity = False

        return {
            "chroma_db_exists": chroma_db.exists(),
            "sqlite_db_exists": sqlite_db.exists(),
            "chroma_db_size": chroma_db.stat().st_size if chroma_db.exists() else 0,
            "sqlite_db_size": sqlite_db.stat().st_size if sqlite_db.exists() else 0,
            "chroma_db_integrity": chroma_integrity,
            "last_modified": {
                "chroma_db": datetime.fromtimestamp(chroma_db.stat().st_mtime).isoformat() if chroma_db.exists() else None,
                "sqlite_db": datetime.fromtimestamp(sqlite_db.stat().st_mtime).isoformat() if sqlite_db.exists() else None
            },
            "sync_status": "healthy" if chroma_db.exists() and sqlite_db.exists() and chroma_integrity else "needs_attention"
        }