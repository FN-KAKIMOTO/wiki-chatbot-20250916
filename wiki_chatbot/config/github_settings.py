"""
GitHub 同期設定管理

このモジュールは、GitHub同期機能の設定を管理します。
Streamlit Secretsから設定値を読み込み、同期機能の有効/無効を制御します。

使用例:
    from config.github_settings import GitHubConfig

    if GitHubConfig.is_configured():
        config = GitHubConfig.get_config()
        sync = GitHubDataSync(
            repo_url=config["repo_url"],
            token=config["token"]
        )
"""

import os
import streamlit as st
from typing import Dict, Any


class GitHubConfig:
    """GitHub 同期設定管理クラス"""

    @staticmethod
    def get_config() -> Dict[str, Any]:
        """
        GitHub同期設定を取得

        Returns:
            設定辞書
        """
        return {
            "enabled": st.secrets.get("GITHUB_SYNC_ENABLED", False),
            "repo_url": st.secrets.get("GITHUB_DATA_REPO"),
            "token": st.secrets.get("GITHUB_TOKEN"),
            "branch": "main",
            "auto_backup_interval": 30,  # 分
            "max_file_size": 100_000_000  # 100MB
        }

    @staticmethod
    def is_configured() -> bool:
        """
        GitHub同期が正しく設定されているかチェック

        Returns:
            設定が完了している場合True
        """
        config = GitHubConfig.get_config()
        return all([
            config["enabled"],
            config["repo_url"],
            config["token"]
        ])

    @staticmethod
    def get_display_config() -> Dict[str, str]:
        """
        表示用設定情報（トークンをマスク）

        Returns:
            表示用設定辞書
        """
        config = GitHubConfig.get_config()

        # トークンをマスク
        masked_token = None
        if config["token"]:
            token = config["token"]
            masked_token = f"{token[:8]}{'*' * (len(token) - 12)}{token[-4:]}"

        return {
            "enabled": "✅ 有効" if config["enabled"] else "❌ 無効",
            "repo_url": config["repo_url"] or "未設定",
            "token": masked_token or "未設定",
            "branch": config["branch"],
            "backup_interval": f"{config['auto_backup_interval']}分"
        }