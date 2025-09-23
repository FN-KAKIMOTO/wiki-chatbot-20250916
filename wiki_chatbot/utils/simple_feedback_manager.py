"""
簡素化されたフィードバック管理システム

必要最低限の機能のみを提供：
- フィードバック保存・読み込み
- シンプルな自動バックアップ（メッセージ間隔のみ）
"""

import os
import json
import sqlite3
import streamlit as st
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from pathlib import Path


@dataclass
class UserFeedback:
    timestamp: str
    product_name: str
    session_id: str
    chat_id: str
    message_sequence: int
    satisfaction: str
    user_message: str
    bot_response: str
    prompt_style: str
    feedback_reason: str = ""


class SimpleFeedbackManager:
    """簡素化されたフィードバック管理クラス"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.db_path = self.data_dir / "chatbot.db"
        self.data_dir.mkdir(exist_ok=True)

        # GitHubSync設定
        self.github_sync = None
        try:
            from utils.github_sync import GitHubDataSync
            from config.github_settings import GitHubConfig
            if GitHubConfig.is_configured():
                config = GitHubConfig.get_config()
                self.github_sync = GitHubDataSync(
                    repo_url=config["repo_url"],
                    token=config["token"]
                )
        except Exception:
            pass  # GitHub設定がない場合は無視

        # バックアップ設定
        self.backup_interval = st.secrets.get("BACKUP_INTERVAL_MESSAGES", 10)
        self.message_count_since_backup = 0

        self._init_database()

    def _init_database(self):
        """データベース初期化"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS feedback (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        product_name TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        chat_id TEXT NOT NULL,
                        message_sequence INTEGER NOT NULL,
                        satisfaction TEXT NOT NULL,
                        user_message TEXT NOT NULL,
                        bot_response TEXT NOT NULL,
                        prompt_style TEXT NOT NULL,
                        feedback_reason TEXT DEFAULT ''
                    )
                """)
        except Exception as e:
            if st.secrets.get("DEBUG_MODE", False):
                st.error(f"Database initialization error: {e}")

    def save_feedback(self, feedback: UserFeedback) -> bool:
        """フィードバックを保存"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO feedback
                    (timestamp, product_name, session_id, chat_id, message_sequence,
                     satisfaction, user_message, bot_response, prompt_style, feedback_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    feedback.timestamp, feedback.product_name, feedback.session_id,
                    feedback.chat_id, feedback.message_sequence, feedback.satisfaction,
                    feedback.user_message, feedback.bot_response, feedback.prompt_style,
                    feedback.feedback_reason
                ))

            # フィードバック入力時の自動バックアップ
            self.trigger_feedback_backup()
            return True

        except Exception as e:
            if st.secrets.get("DEBUG_MODE", False):
                st.error(f"Feedback save error: {e}")
            return False

    def get_feedback_by_product(self, product_name: str) -> List[Dict[str, Any]]:
        """商材別フィードバック取得"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM feedback
                    WHERE product_name = ?
                    ORDER BY timestamp DESC
                """, (product_name,))

                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

        except Exception as e:
            if st.secrets.get("DEBUG_MODE", False):
                st.error(f"Feedback retrieval error: {e}")
            return []

    def _check_auto_backup(self, trigger_type: str = "message"):
        """自動バックアップチェック（3つのタイミング）

        Args:
            trigger_type: "message" | "feedback" | "file"
        """
        if not self.github_sync:
            return

        should_backup = False
        backup_reason = ""

        if trigger_type == "message":
            # 1. メッセージ間隔でのバックアップ
            self.message_count_since_backup += 1
            if self.message_count_since_backup >= self.backup_interval:
                should_backup = True
                backup_reason = f"Message interval backup ({self.message_count_since_backup} messages)"

        elif trigger_type == "feedback":
            # 2. ユーザーフィードバック入力時のバックアップ
            should_backup = True
            backup_reason = "User feedback backup"

        elif trigger_type == "file":
            # 3. ファイル追加時のバックアップ
            should_backup = True
            backup_reason = "File addition backup"

        if should_backup:
            try:
                success = self.github_sync.upload_data(backup_reason)
                if success:
                    if trigger_type == "message":
                        self.message_count_since_backup = 0
                    if st.secrets.get("DEBUG_MODE", False):
                        st.success(f"✅ {backup_reason} 完了")
                else:
                    if st.secrets.get("DEBUG_MODE", False):
                        st.warning(f"⚠️ {backup_reason} 失敗")
            except Exception as e:
                if st.secrets.get("DEBUG_MODE", False):
                    st.error(f"❌ {backup_reason} エラー: {e}")

    def trigger_feedback_backup(self):
        """フィードバック入力時のバックアップをトリガー"""
        self._check_auto_backup("feedback")

    def trigger_file_backup(self):
        """ファイル追加時のバックアップをトリガー"""
        self._check_auto_backup("file")

    def save_chat_message(self, *args, **kwargs):
        """チャットメッセージ保存（メッセージ間隔バックアップをトリガー）"""
        # メッセージ間隔での自動バックアップチェック
        self._check_auto_backup("message")

    def show_satisfaction_survey(self, product_name: str, prompt_style: str):
        """満足度調査表示（既存のフィードバック機能との互換性）"""
        # 既存のフィードバック機能はそのまま残す
        pass

    def get_feedback_summary(self, product_name: str) -> Dict[str, Any]:
        """フィードバック概要取得"""
        feedbacks = self.get_feedback_by_product(product_name)
        if not feedbacks:
            return {"total": 0, "satisfied": 0, "dissatisfied": 0, "satisfaction_rate": 0}

        total = len(feedbacks)
        satisfied = len([f for f in feedbacks if f.get("satisfaction") == "satisfied"])
        dissatisfied = total - satisfied
        satisfaction_rate = (satisfied / total * 100) if total > 0 else 0

        return {
            "total": total,
            "satisfied": satisfied,
            "dissatisfied": dissatisfied,
            "satisfaction_rate": round(satisfaction_rate, 1)
        }


# シングルトンインスタンス
simple_feedback_manager = SimpleFeedbackManager()