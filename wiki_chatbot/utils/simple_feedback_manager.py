"""
簡素化されたフィードバック管理システム

必要最低限の機能のみを提供：
- フィードバック保存・読み込み
- 満足度調査UI表示
- CSVエクスポート機能
- シンプルな自動バックアップ（メッセージ間隔のみ）
"""

import os
import json
import sqlite3
import csv
import pandas as pd
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
        self.feedback_file = self.data_dir / "user_feedback.csv"
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
        self._init_csv_file()

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

    def _init_csv_file(self):
        """CSVファイルの初期化"""
        try:
            if not self.feedback_file.exists():
                with open(self.feedback_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "timestamp", "product_name", "session_id", "chat_id",
                        "message_sequence", "satisfaction", "user_message",
                        "bot_response", "prompt_style", "feedback_reason"
                    ])
        except Exception as e:
            if st.secrets.get("DEBUG_MODE", False):
                st.error(f"CSV initialization error: {e}")

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

            # CSVファイルにも保存
            with open(self.feedback_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    feedback.timestamp, feedback.product_name, feedback.session_id,
                    feedback.chat_id, feedback.message_sequence, feedback.satisfaction,
                    feedback.user_message, feedback.bot_response, feedback.prompt_style,
                    feedback.feedback_reason
                ])

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

    def get_session_id(self, product_name: str) -> str:
        """セッションIDを取得または生成"""
        session_key = f"session_id_{product_name}"

        if session_key not in st.session_state:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.session_state[session_key] = f"{product_name}_{timestamp}"
            st.session_state[f"session_start_{product_name}"] = datetime.now()

        return st.session_state[session_key]

    def generate_chat_id(self, session_id: str, sequence: int) -> str:
        """チャットIDを生成"""
        return f"{session_id}_msg_{sequence:03d}"

    def get_next_message_sequence(self, product_name: str) -> int:
        """次のメッセージ順序番号を取得"""
        session_id = self.get_session_id(product_name)
        sequence_key = f"message_sequence_{session_id}"

        if sequence_key not in st.session_state:
            st.session_state[sequence_key] = 0

        st.session_state[sequence_key] += 1
        return st.session_state[sequence_key]

    def save_chat_message(self, *args, **kwargs):
        """チャットメッセージ保存（メッセージ間隔バックアップをトリガー）"""
        # メッセージ間隔での自動バックアップチェック
        self._check_auto_backup("message")

    def show_satisfaction_survey(self, product_name: str, prompt_style: str):
        """満足度調査UIを表示"""

        # 最新のチャット情報を取得
        messages = st.session_state.get(f"messages_{product_name}", [])
        if len(messages) < 2:
            return  # まだチャットがない場合は表示しない

        # 最新のチャット交換を取得
        latest_user_msg = None
        latest_bot_msg = None

        # メッセージリストから最新のuser-assistant ペアを探す
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "assistant" and latest_bot_msg is None:
                latest_bot_msg = messages[i]["content"]
            elif messages[i]["role"] == "user" and latest_user_msg is None and latest_bot_msg is not None:
                latest_user_msg = messages[i]["content"]
                break

        if not latest_user_msg or not latest_bot_msg:
            return  # 完全なQ&Aペアがない場合は表示しない

        # セッション情報を取得
        session_id = self.get_session_id(product_name)
        message_sequence = st.session_state.get(f"message_sequence_{session_id}", 0)
        chat_id = self.generate_chat_id(session_id, message_sequence)

        # このチャットに対してフィードバック済みかチェック
        feedback_key = f"feedback_given_{chat_id}"
        dissatisfied_key = f"dissatisfied_selected_{chat_id}"

        # まだフィードバックを送信していない場合のみ表示
        if not st.session_state.get(feedback_key, False):
            with st.container():
                st.divider()
                st.subheader("📝 この回答について")
                st.write("**この回答はお役に立ちましたか？**")

                # 評価対象のQ&Aペアを表示
                with st.expander("📋 評価対象のやり取り", expanded=False):
                    st.write(f"**質問:** {latest_user_msg[:100]}{'...' if len(latest_user_msg) > 100 else ''}")
                    st.write(f"**回答:** {latest_bot_msg[:150]}{'...' if len(latest_bot_msg) > 150 else ''}")

                st.caption("皆様のフィードバックはサービス改善のために活用させていただきます。")

                col1, col2, col3 = st.columns([1, 1, 2])

                with col1:
                    if st.button(
                        "😊 満足", key=f"satisfied_{chat_id}", help="回答が役に立った", use_container_width=True
                    ):
                        feedback = UserFeedback(
                            timestamp=datetime.now().isoformat(),
                            product_name=product_name,
                            session_id=session_id,
                            chat_id=chat_id,
                            message_sequence=message_sequence,
                            satisfaction="満足",
                            user_message=latest_user_msg,
                            bot_response=latest_bot_msg,
                            prompt_style=prompt_style,
                            feedback_reason=""
                        )
                        success = self.save_feedback(feedback)
                        if success:
                            st.session_state[feedback_key] = True
                            st.success("✅ フィードバックありがとうございます！")
                            st.rerun()

                with col2:
                    if st.button(
                        "😔 不満足",
                        key=f"dissatisfied_{chat_id}",
                        help="期待した回答が得られなかった",
                        use_container_width=True,
                    ):
                        # 不満足ボタンが押された場合、理由入力フォームを表示
                        st.session_state[dissatisfied_key] = True
                        st.rerun()

                with col3:
                    if st.button("⏭️ スキップ", key=f"skip_{chat_id}", help="フィードバックを送信しない"):
                        st.session_state[feedback_key] = True
                        st.rerun()

                # 不満足が選択された場合、理由入力フォームを表示
                if st.session_state.get(dissatisfied_key, False):
                    st.write("")  # スペース
                    st.write("**不満足の理由をお聞かせください（任意）：**")

                    feedback_reason = st.text_area(
                        "改善のためのご意見をお聞かせください",
                        placeholder="例：回答が不正確だった、情報が古かった、期待していた内容と違った など",
                        key=f"feedback_reason_{chat_id}",
                        height=80
                    )

                    col_submit, col_skip_reason = st.columns([1, 1])

                    with col_submit:
                        if st.button("📤 送信", key=f"submit_feedback_{chat_id}", use_container_width=True):
                            feedback = UserFeedback(
                                timestamp=datetime.now().isoformat(),
                                product_name=product_name,
                                session_id=session_id,
                                chat_id=chat_id,
                                message_sequence=message_sequence,
                                satisfaction="不満足",
                                user_message=latest_user_msg,
                                bot_response=latest_bot_msg,
                                prompt_style=prompt_style,
                                feedback_reason=feedback_reason.strip()
                            )
                            success = self.save_feedback(feedback)
                            if success:
                                st.session_state[feedback_key] = True
                                st.session_state[dissatisfied_key] = False
                                st.info("📋 フィードバックありがとうございます。改善に努めます。")
                                st.rerun()

                    with col_skip_reason:
                        if st.button("理由を入力せずに送信", key=f"skip_reason_{chat_id}", use_container_width=True):
                            feedback = UserFeedback(
                                timestamp=datetime.now().isoformat(),
                                product_name=product_name,
                                session_id=session_id,
                                chat_id=chat_id,
                                message_sequence=message_sequence,
                                satisfaction="不満足",
                                user_message=latest_user_msg,
                                bot_response=latest_bot_msg,
                                prompt_style=prompt_style,
                                feedback_reason=""
                            )
                            success = self.save_feedback(feedback)
                            if success:
                                st.session_state[feedback_key] = True
                                st.session_state[dissatisfied_key] = False
                                st.info("📋 フィードバックありがとうございます。改善に努めます。")
                                st.rerun()

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

    def export_feedback_csv(self, product_name: str = None) -> Optional[str]:
        """フィードバックをCSVエクスポート"""
        try:
            if not self.feedback_file.exists():
                return None

            df = pd.read_csv(self.feedback_file, encoding="utf-8")

            if product_name:
                df = df[df["product_name"] == product_name]

            if df.empty:
                return None

            # エクスポートファイル名生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_filename = f"feedback_export_{product_name or 'all'}_{timestamp}.csv"
            export_path = self.data_dir / export_filename

            # CSVエクスポート
            df.to_csv(export_path, index=False, encoding="utf-8-sig")

            return str(export_path)

        except Exception as e:
            if st.secrets.get("DEBUG_MODE", False):
                st.error(f"CSV export error: {e}")
            return None

    def get_dissatisfaction_reasons(self, product_name: str = None) -> List[Dict[str, Any]]:
        """不満足理由一覧を取得"""
        try:
            if not self.feedback_file.exists():
                return []

            df = pd.read_csv(self.feedback_file, encoding="utf-8")

            if product_name:
                df = df[df["product_name"] == product_name]

            # 不満足のフィードバックを抽出
            dissatisfied_df = df[df["satisfaction"] == "不満足"]

            reasons = []
            for _, row in dissatisfied_df.iterrows():
                reasons.append({
                    "timestamp": row["timestamp"],
                    "product_name": row["product_name"],
                    "feedback_reason": row["feedback_reason"],
                    "user_message": row["user_message"][:100] + "..." if len(row["user_message"]) > 100 else row["user_message"],
                    "bot_response": row["bot_response"][:100] + "..." if len(row["bot_response"]) > 100 else row["bot_response"]
                })

            return reasons

        except Exception as e:
            if st.secrets.get("DEBUG_MODE", False):
                st.error(f"Dissatisfaction reasons retrieval error: {e}")
            return []


# シングルトンインスタンス
simple_feedback_manager = SimpleFeedbackManager()