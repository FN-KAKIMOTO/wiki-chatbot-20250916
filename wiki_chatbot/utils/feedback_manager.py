# -*- coding: utf-8 -*-
"""チャット履歴保存とユーザーフィードバック管理システム。

このモジュールは以下の包括的な機能を提供します：
- CSVファイルへの自動チャットセッションログ記録
- ユーザー満足度フィードバック収集
- 継続的改善のための分析とレポート
- 詳細分析のためのデータエクスポート機能
"""

import csv
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

# 永続化データベースのインポート
try:
    from config.database import persistent_db
    PERSISTENT_DB_AVAILABLE = True
except ImportError:
    PERSISTENT_DB_AVAILABLE = False

# GitHub同期のインポート
try:
    from config.github_settings import GitHubConfig
    from utils.github_sync import GitHubDataSync
    GITHUB_SYNC_AVAILABLE = True
except ImportError:
    GITHUB_SYNC_AVAILABLE = False


@dataclass
class ChatMessage:
    """チャットメッセージレコード用データクラス。

    Attributes:
        timestamp: メッセージが送信された時刻。
        product_name: 討論されている製品/サービス。
        user_message: ユーザーの入力メッセージ。
        bot_response: システムの応答。
        sources_used: 使用された参考文書のリスト。
        prompt_style: 生成に使用されたプロンプトのタイプ。
        session_id: チャットセッションの一意識別子。
        user_name: ユーザー名（任意）。
        chat_id: 個別チャット交換の一意識別子。
        message_sequence: セッション内でのチャット順序番号。
    """

    timestamp: str
    product_name: str
    user_message: str
    bot_response: str
    sources_used: List[str]
    prompt_style: str
    session_id: str
    user_name: str = ""
    chat_id: str = ""
    message_sequence: int = 0


@dataclass
class UserFeedback:
    """ユーザーフィードバックレコード用データクラス。

    Attributes:
        timestamp: フィードバックが給された時刻。
        product_name: 評価されている製品/サービス。
        session_id: チャットセッションの一意識別子。
        chat_id: 個別チャット交換の一意識別子。
        message_sequence: セッション内でのチャット順序番号。
        satisfaction: ユーザー満足度（「満足」または「不満足」）。
        user_message: 評価対象のユーザー質問。
        bot_response: 評価対象のBot回答。
        prompt_style: 回答生成に使用されたプロンプトのタイプ。
        feedback_reason: 不満足の理由（自由回答、満足の場合は空文字）。
    """

    timestamp: str
    product_name: str
    session_id: str
    chat_id: str
    message_sequence: int
    satisfaction: str  # "満足" or "不満足"
    user_message: str
    bot_response: str
    prompt_style: str
    feedback_reason: str = ""  # 不満足の理由


class FeedbackManager:
    """チャット履歴とフィードバック管理クラス。

    チャットボットの利用履歴とユーザーフィードバックの永続化を担当します。
    データの保存、エクスポート、分析機能を提供し、システムの継続的改善を支援します。

    主要機能:
    - チャット会話履歴の自動保存
    - ユーザー満足度フィードバックの収集
    - CSVとSQLiteによる二重保存（データ堅牢性）
    - エクスポート機能（分析用データ出力）
    - 統計情報の生成

    データ保存先:
    - data/chat_history.csv: チャット履歴（CSV形式、互換性重視）
    - data/user_feedback.csv: フィードバック履歴（CSV形式）
    - data/chatbot.db: SQLiteデータベース（永続化・検索性能重視）

    Attributes:
        data_dir (str): データ保存ディレクトリパス
        chat_log_file (str): チャット履歴CSVファイルパス
        feedback_file (str): フィードバックCSVファイルパス

    設計原則:
    - 二重保存によるデータ堅牢性の確保
    - CSV形式による外部ツール連携のサポート
    - セッション管理とプライバシー保護
    """

    def __init__(self, data_dir: str = "data"):
        """FeedbackManagerを初期化する。

        データ保存用ディレクトリとファイルパスを設定し、
        必要なディレクトリとCSVファイルのヘッダーを作成します。

        Args:
            data_dir (str): データ保存用ディレクトリパス. Defaults to "data".

        Note:
            ディレクトリが存在しない場合は自動作成されます。
            CSVファイルが存在しない場合は適切なヘッダー行で初期化されます。
        """
        # データ保存パスの設定
        self.data_dir = data_dir
        self.chat_log_file = os.path.join(data_dir, "chat_history.csv")
        self.feedback_file = os.path.join(data_dir, "user_feedback.csv")

        # データディレクトリの作成（存在しない場合）
        os.makedirs(data_dir, exist_ok=True)

        # CSVファイルの初期化（ヘッダー行の作成）
        self._initialize_csv_files()

        # GitHub同期の初期化
        self.github_sync = None
        if GITHUB_SYNC_AVAILABLE and GitHubConfig.is_configured():
            try:
                config = GitHubConfig.get_config()
                self.github_sync = GitHubDataSync(
                    repo_url=config["repo_url"],
                    token=config["token"]
                )
                if st.secrets.get("DEBUG_MODE", False):
                    st.write("🔍 DEBUG: GitHub sync initialized successfully")
            except Exception as e:
                st.warning(f"GitHub同期初期化エラー: {e}")
        elif st.secrets.get("DEBUG_MODE", False):
            st.write(f"🔍 DEBUG: GitHub sync not available - GITHUB_SYNC_AVAILABLE: {GITHUB_SYNC_AVAILABLE}, is_configured: {GitHubConfig.is_configured() if GITHUB_SYNC_AVAILABLE else 'N/A'}")

        # 自動バックアップの設定
        self.auto_backup_enabled = st.secrets.get("AUTO_BACKUP_ENABLED", True)
        self.backup_interval = st.secrets.get("BACKUP_INTERVAL_MESSAGES", 5)  # メッセージ5件ごと
        self.message_count_since_backup = 0

        # 時刻ベースバックアップ設定（1日3回: 9時、15時、21時）
        scheduled_hours_str = st.secrets.get("SCHEDULED_BACKUP_HOURS", "9,15,21")
        try:
            self.scheduled_backup_hours = [int(h.strip()) for h in scheduled_hours_str.split(",")]
        except:
            self.scheduled_backup_hours = [9, 15, 21]  # デフォルト値
        self.last_scheduled_backup_date = None

    def _initialize_csv_files(self):
        """CSVファイルのヘッダーを初期化"""

        # チャット履歴ファイル
        if not os.path.exists(self.chat_log_file):
            chat_headers = [
                "timestamp",
                "product_name",
                "user_message",
                "bot_response",
                "sources_used",
                "prompt_style",
                "session_id",
                "user_name",
                "chat_id",
                "message_sequence",
                "message_length",
                "response_length",
                "sources_count",
            ]
            with open(self.chat_log_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(chat_headers)

        # フィードバックファイル
        if not os.path.exists(self.feedback_file):
            feedback_headers = [
                "timestamp",
                "product_name",
                "session_id",
                "chat_id",
                "message_sequence",
                "satisfaction",
                "user_message",
                "bot_response",
                "prompt_style",
                "feedback_reason",
            ]
            with open(self.feedback_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(feedback_headers)

    def get_session_id(self, product_name: str) -> str:
        """セッションIDを取得または生成"""
        session_key = f"session_id_{product_name}"

        if session_key not in st.session_state:
            # 新しいセッションIDを生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.session_state[session_key] = f"{product_name}_{timestamp}"
            st.session_state[f"session_start_{product_name}"] = datetime.now()

        return st.session_state[session_key]

    def get_next_message_sequence(self, product_name: str) -> int:
        """セッション内での次のメッセージ順序番号を取得"""
        session_id = self.get_session_id(product_name)
        sequence_key = f"message_sequence_{session_id}"

        if sequence_key not in st.session_state:
            st.session_state[sequence_key] = 0

        st.session_state[sequence_key] += 1
        return st.session_state[sequence_key]

    def generate_chat_id(self, session_id: str, sequence: int) -> str:
        """チャットIDを生成（session_id + sequence番号）"""
        return f"{session_id}_msg_{sequence:03d}"

    def _check_scheduled_backup(self):
        """時刻ベース定期バックアップのチェック（1日3回）"""
        if not self.auto_backup_enabled or not self.github_sync:
            return

        now = datetime.now()
        current_date = now.date()
        current_hour = now.hour

        # 今日まだバックアップしていない場合
        if self.last_scheduled_backup_date != current_date:
            # 設定時刻に達している場合
            if current_hour in self.scheduled_backup_hours:
                try:
                    success = self.github_sync.upload_data(f"Scheduled backup ({current_hour}:00) - {now.isoformat()}")
                    if success:
                        self.last_scheduled_backup_date = current_date
                        if st.secrets.get("DEBUG_MODE", False):
                            st.success(f"✅ 定期バックアップ完了 ({current_hour}時)")
                    else:
                        if st.secrets.get("DEBUG_MODE", False):
                            st.warning(f"⚠️ 定期バックアップ失敗 ({current_hour}時)")
                except Exception as e:
                    if st.secrets.get("DEBUG_MODE", False):
                        st.error(f"❌ 定期バックアップエラー: {e}")

    def _trigger_auto_backup(self, action: str = "Auto backup"):
        """自動バックアップをトリガーする"""
        # まず時刻ベースバックアップをチェック
        self._check_scheduled_backup()

        if not self.auto_backup_enabled or not self.github_sync:
            return

        self.message_count_since_backup += 1

        # 指定した間隔でバックアップを実行
        if self.message_count_since_backup >= self.backup_interval:
            try:
                success = self.github_sync.upload_data(f"{action} - {datetime.now().isoformat()}")
                if success:
                    self.message_count_since_backup = 0
                    if st.secrets.get("DEBUG_MODE", False):
                        st.success(f"✅ 自動バックアップ完了 ({action})")
                else:
                    if st.secrets.get("DEBUG_MODE", False):
                        st.warning(f"⚠️ 自動バックアップ失敗 ({action})")
            except Exception as e:
                if st.secrets.get("DEBUG_MODE", False):
                    st.error(f"❌ 自動バックアップエラー: {e}")

    def _simple_backup(self, action: str = "Backup"):
        """シンプルなバックアップ実行"""
        if not self.github_sync:
            if st.secrets.get("DEBUG_MODE", False):
                st.write("🔍 DEBUG: GitHub sync not configured, skipping backup")
            return

        if st.secrets.get("DEBUG_MODE", False):
            st.write(f"🔍 DEBUG: Starting backup with action: {action}")
        try:
            success = self.github_sync.upload_data(action)
            if success and st.secrets.get("DEBUG_MODE", False):
                st.success("✅ バックアップ完了")
            elif not success and st.secrets.get("DEBUG_MODE", False):
                st.warning("⚠️ バックアップ失敗")
        except Exception as e:
            if st.secrets.get("DEBUG_MODE", False):
                st.error(f"❌ バックアップエラー: {e}")
                st.write(f"🔍 DEBUG: Backup error details - {type(e).__name__}: {e}")

    def _schedule_delayed_backup(self, action: str = "Delayed backup", delay_seconds: int = 10):
        """遅延バックアップをスケジュール（複数ファイル処理時の重複回避）"""
        if not hasattr(st.session_state, 'pending_backup_action'):
            st.session_state.pending_backup_action = action
            st.session_state.pending_backup_time = datetime.now().timestamp() + delay_seconds

        # 既存のアクションを更新（最後の操作を記録）
        st.session_state.pending_backup_action = action
        st.session_state.pending_backup_time = datetime.now().timestamp() + delay_seconds

        # ユーザーへの通知
        if st.secrets.get("DEBUG_MODE", False):
            st.info(f"⏰ {delay_seconds}秒後にバックアップ実行予定: {action}")

    def _check_delayed_backup(self):
        """遅延バックアップの実行チェック"""
        if not hasattr(st.session_state, 'pending_backup_time'):
            return

        if datetime.now().timestamp() >= st.session_state.pending_backup_time:
            action = getattr(st.session_state, 'pending_backup_action', 'Delayed backup')
            self._simple_backup(action)

            # 処理済みフラグをクリア
            delattr(st.session_state, 'pending_backup_time')
            delattr(st.session_state, 'pending_backup_action')

    def save_chat_message(
        self, product_name: str, user_message: str, bot_response: str, sources_used: List[str], prompt_style: str, user_name: str = ""
    ):
        """チャットメッセージを保存（永続化データベース + CSV）"""

        try:
            session_id = self.get_session_id(product_name)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # チャットIDとシーケンス番号を生成
            message_sequence = self.get_next_message_sequence(product_name)
            chat_id = self.generate_chat_id(session_id, message_sequence)

            # ボットの回答から参考情報源部分を除去してクリーンな回答のみ抽出
            clean_response = bot_response.split("---\n### 📚 参考にした情報源")[0].strip()
            sources_string = "; ".join(sources_used)

            # 永続化データベースに保存（優先）
            if PERSISTENT_DB_AVAILABLE:
                try:
                    persistent_db.save_chat_message(
                        session_id=session_id,
                        product_name=product_name,
                        user_message=user_message,
                        bot_response=clean_response,
                        sources_used=sources_string,
                        prompt_style=prompt_style
                    )
                except Exception as db_error:
                    st.warning(f"データベース保存エラー: {db_error}")

            # CSVに追記（バックアップ・互換性のため）
            with open(self.chat_log_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        timestamp,
                        product_name,
                        user_message,
                        clean_response,
                        sources_string,
                        prompt_style,
                        session_id,
                        user_name,
                        chat_id,
                        message_sequence,
                        len(user_message),
                        len(clean_response),
                        len(sources_used),
                    ]
                )

            # 自動バックアップをトリガー
            self._trigger_auto_backup("Chat message saved")

            return True

        except Exception as e:
            st.error(f"チャット履歴保存エラー: {str(e)}")
            return False

    def save_feedback(self, product_name: str, chat_id: str, message_sequence: int, satisfaction: str,
                     user_message: str, bot_response: str, prompt_style: str, feedback_reason: str = ""):
        """ユーザーフィードバックを保存（個別チャット単位）"""

        # デバッグ情報
        if st.secrets.get("DEBUG_MODE", False):
            st.write(f"🔍 DEBUG: Attempting to save feedback - {satisfaction}, chat_id: {chat_id}")

        try:
            session_id = self.get_session_id(product_name)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 永続化データベースに保存（優先）
            if PERSISTENT_DB_AVAILABLE:
                try:
                    persistent_db.save_feedback(
                        session_id=session_id,
                        product_name=product_name,
                        satisfaction=satisfaction,
                        total_messages=message_sequence,  # メッセージ順序を使用
                        prompt_style=prompt_style,
                        session_duration="",  # 個別チャット評価では使用しない
                        feedback_text=feedback_reason
                    )
                except Exception as db_error:
                    st.warning(f"フィードバックDB保存エラー: {db_error}")

            # CSVに追記（新しい構造）
            if st.secrets.get("DEBUG_MODE", False):
                st.write(f"🔍 DEBUG: Attempting to write to CSV file: {self.feedback_file}")
            with open(self.feedback_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp,
                    product_name,
                    session_id,
                    chat_id,
                    message_sequence,
                    satisfaction,
                    user_message[:200],  # 長すぎる場合は切り詰め
                    bot_response[:200],   # 長すぎる場合は切り詰め
                    prompt_style,
                    feedback_reason
                ])

            # フィードバック保存時は即座にバックアップ（重要データのため）
            self._simple_backup("Feedback saved")

            # デバッグ情報
            if st.secrets.get("DEBUG_MODE", False):
                st.write(f"✅ DEBUG: Feedback saved successfully to CSV and triggered backup")

            return True

        except Exception as e:
            st.error(f"フィードバック保存エラー: {str(e)}")
            if st.secrets.get("DEBUG_MODE", False):
                st.write(f"🔍 DEBUG: Error details - {type(e).__name__}: {e}")
            return False

    def export_chat_history(self, product_name: str = None) -> Optional[str]:
        """チャット履歴をエクスポート"""

        try:
            if not os.path.exists(self.chat_log_file):
                return None

            df = pd.read_csv(self.chat_log_file, encoding="utf-8")

            # 製品フィルタリング
            if product_name:
                df = df[df["product_name"] == product_name]

            if df.empty:
                return None

            # エクスポートファイル名生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_filename = f"chat_export_{product_name or 'all'}_{timestamp}.csv"
            export_path = os.path.join(self.data_dir, export_filename)

            # CSVエクスポート
            df.to_csv(export_path, index=False, encoding="utf-8-sig")

            return export_path

        except FileNotFoundError:
            st.error("チャット履歴ファイルが見つかりません。まずチャットを実行してください。")
            return None
        except pd.errors.EmptyDataError:
            st.error("チャット履歴ファイルが空です。")
            return None
        except Exception as e:
            st.error(f"チャット履歴エクスポートエラー: {str(e)}")
            return None

    def export_conversation_format(self, product_name: str = None) -> Optional[str]:
        """会話形式でチャット履歴をエクスポート（Q&Aペア構造）"""

        try:
            if not os.path.exists(self.chat_log_file):
                return None

            df = pd.read_csv(self.chat_log_file, encoding="utf-8")

            # 必要な列の存在確認
            required_columns = ['chat_id', 'message_sequence', 'session_id', 'user_message', 'bot_response']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                st.error(f"チャット履歴に必要な列が不足しています: {missing_columns}")
                return None

            # 製品フィルタリング
            if product_name:
                df = df[df["product_name"] == product_name]

            if df.empty:
                return None

            # セッション毎にグループ化してソート
            df = df.sort_values(['session_id', 'message_sequence'])

            # 会話形式データの作成
            conversations = []
            for session_id, session_group in df.groupby('session_id'):
                for _, row in session_group.iterrows():
                    conversation_entry = {
                        'session_id': session_id,
                        'chat_id': row['chat_id'],
                        'message_sequence': row['message_sequence'],
                        'timestamp': row['timestamp'],
                        'product_name': row['product_name'],
                        'user_name': row.get('user_name', ''),
                        'user_question': row['user_message'],
                        'bot_answer': row['bot_response'],
                        'reference_sources': row['sources_used'],
                        'prompt_style': row['prompt_style'],
                        'question_length': row.get('message_length', len(row['user_message'])),
                        'answer_length': row.get('response_length', len(row['bot_response'])),
                        'sources_count': row.get('sources_count', 0)
                    }
                    conversations.append(conversation_entry)

            # DataFrameに変換
            conversation_df = pd.DataFrame(conversations)

            # エクスポートファイル名生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_filename = f"conversation_export_{product_name or 'all'}_{timestamp}.csv"
            export_path = os.path.join(self.data_dir, export_filename)

            # CSVエクスポート
            conversation_df.to_csv(export_path, index=False, encoding="utf-8-sig")

            return export_path

        except FileNotFoundError:
            st.error("チャット履歴ファイルが見つかりません。まずチャットを実行してください。")
            return None
        except pd.errors.EmptyDataError:
            st.error("チャット履歴ファイルが空です。")
            return None
        except KeyError as e:
            st.error(f"必要なデータ列が見つかりません: {str(e)}")
            return None
        except Exception as e:
            st.error(f"会話形式エクスポートエラー: {str(e)}")
            return None

    def export_combined_data(self, product_name: str = None) -> Optional[str]:
        """チャット履歴とフィードバックを統合してエクスポート"""

        try:
            # チャット履歴を読み込み
            if not os.path.exists(self.chat_log_file):
                st.error("チャット履歴ファイルが存在しません")
                return None

            chat_df = pd.read_csv(self.chat_log_file, encoding="utf-8")

            # 必要な列の存在確認
            required_chat_columns = ['chat_id', 'message_sequence', 'session_id', 'user_message', 'bot_response', 'timestamp', 'product_name']
            missing_chat_columns = [col for col in required_chat_columns if col not in chat_df.columns]
            if missing_chat_columns:
                st.error(f"チャット履歴に必要な列が不足しています: {missing_chat_columns}")
                return None

            # user_name列がない場合は空文字で補完
            if 'user_name' not in chat_df.columns:
                chat_df['user_name'] = ""

            # フィードバックデータを読み込み（存在する場合）
            feedback_df = None
            if os.path.exists(self.feedback_file):
                feedback_df = pd.read_csv(self.feedback_file, encoding="utf-8")

                # フィードバックデータの必要な列の確認
                required_feedback_columns = ['chat_id', 'satisfaction', 'product_name']
                missing_feedback_columns = [col for col in required_feedback_columns if col not in feedback_df.columns]
                if missing_feedback_columns:
                    st.warning(f"フィードバックデータに必要な列が不足しています: {missing_feedback_columns}")
                    feedback_df = None  # フィードバックデータを無効にする
                else:
                    # feedback_reason列がない場合は空文字で補完
                    if 'feedback_reason' not in feedback_df.columns:
                        feedback_df['feedback_reason'] = ""

            # 製品フィルタリング
            if product_name:
                chat_df = chat_df[chat_df["product_name"] == product_name]
                if feedback_df is not None:
                    feedback_df = feedback_df[feedback_df["product_name"] == product_name]

            if chat_df.empty:
                st.warning("エクスポート対象のデータがありません")
                return None

            # フィードバックデータがある場合、session_idでマージ
            if feedback_df is not None and not feedback_df.empty:
                # session_idのデータ型を統一（マージエラー対策）
                try:
                    chat_df['session_id'] = chat_df['session_id'].astype(str)
                    feedback_df['session_id'] = feedback_df['session_id'].astype(str)
                except Exception as e:
                    st.warning(f"session_id型変換エラー: {e}")
                    # 型変換に失敗した場合は文字列に強制変換
                    chat_df['session_id'] = chat_df['session_id'].apply(str)
                    feedback_df['session_id'] = feedback_df['session_id'].apply(str)

                # デバッグ情報（開発時のみ表示）
                if st.secrets.get("DEBUG_MODE", False):
                    st.write(f"🔍 マージ前データ確認:")
                    st.write(f"チャット履歴: {len(chat_df)}件")
                    st.write(f"フィードバック: {len(feedback_df)}件")
                    st.write(f"チャットsession_id型: {chat_df['session_id'].dtype}")
                    st.write(f"フィードバックsession_id型: {feedback_df['session_id'].dtype}")
                    st.write(f"共通session_id: {set(chat_df['session_id']) & set(feedback_df['session_id'])}")

                    # chat_idでフィードバック情報を結合
                feedback_columns = ['chat_id', 'satisfaction', 'feedback_reason']
                available_feedback_columns = [col for col in feedback_columns if col in feedback_df.columns]

                try:
                    combined_df = pd.merge(
                        chat_df,
                        feedback_df[available_feedback_columns],
                        on='chat_id',
                        how='left'
                    )
                except Exception as merge_error:
                    st.error(f"chat_idマージエラー: {merge_error}")
                    st.warning("フィードバックデータなしでエクスポートします")
                    combined_df = chat_df.copy()
                    combined_df['satisfaction'] = None
                    combined_df['feedback_reason'] = None

                # デバッグ情報（開発時のみ表示）
                if st.secrets.get("DEBUG_MODE", False):
                    st.write(f"マージ後: {len(combined_df)}件")
                    satisfaction_filled = combined_df['satisfaction'].notna().sum()
                    st.write(f"満足度データ有り: {satisfaction_filled}件")
            else:
                # フィードバックデータがない場合はチャット履歴のみ
                combined_df = chat_df.copy()
                combined_df['satisfaction'] = None
                combined_df['feedback_reason'] = None

            # 不足している列を補完
            expected_feedback_columns = ['satisfaction', 'feedback_reason']
            for col in expected_feedback_columns:
                if col not in combined_df.columns:
                    combined_df[col] = None

            # エクスポートファイル名生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_filename = f"combined_export_{product_name or 'all'}_chat_based_{timestamp}.csv"
            export_path = os.path.join(self.data_dir, export_filename)

            # 列の順序を整理
            column_order = [
                'timestamp', 'product_name', 'session_id', 'chat_id', 'message_sequence', 'user_name',
                'user_message', 'bot_response', 'sources_used', 'prompt_style', 'message_length',
                'response_length', 'sources_count', 'satisfaction', 'feedback_reason'
            ]

            # 存在する列のみ選択
            available_columns = [col for col in column_order if col in combined_df.columns]
            combined_df = combined_df[available_columns]

            # 最終デバッグ情報（開発時のみ表示）
            if st.secrets.get("DEBUG_MODE", False):
                st.write(f"📊 エクスポート最終データ:")
                st.write(f"総件数: {len(combined_df)}")
                st.write(f"列: {list(combined_df.columns)}")
                if 'satisfaction' in combined_df.columns:
                    satisfaction_counts = combined_df['satisfaction'].value_counts(dropna=False)
                    st.write(f"満足度分布: {satisfaction_counts.to_dict()}")

            # CSVエクスポート
            combined_df.to_csv(export_path, index=False, encoding="utf-8-sig")

            return export_path

        except FileNotFoundError:
            st.error("チャット履歴ファイルが見つかりません。まずチャットを実行してください。")
            return None
        except pd.errors.EmptyDataError:
            st.error("データファイルが空です。")
            return None
        except KeyError as e:
            st.error(f"必要なデータ列が見つかりません: {str(e)}")
            return None
        except Exception as e:
            st.error(f"統合エクスポートエラー: {str(e)}")
            return None

    def get_feedback_summary(self, product_name: str = None) -> Dict[str, Any]:
        """フィードバック集計結果を取得（個別チャット単位）"""

        try:
            if not os.path.exists(self.feedback_file):
                return {}

            # デバッグ情報（一時的に表示）
            if st.secrets.get("DEBUG_MODE", False):
                st.write(f"🔍 フィードバック分析対象ファイル: {self.feedback_file}")

            df = pd.read_csv(self.feedback_file, encoding="utf-8")

            # デバッグ情報（一時的に表示）
            if st.secrets.get("DEBUG_MODE", False):
                st.write(f"読み込んだデータ形状: {df.shape}")
                st.write(f"列名: {list(df.columns)}")
                if len(df) > 0:
                    st.write("先頭3行:")
                    st.dataframe(df.head(3))

            # 製品フィルタリング
            if product_name:
                df = df[df["product_name"] == product_name]

            if df.empty:
                return {}

            total_feedback = len(df)
            satisfied = len(df[df["satisfaction"] == "満足"])
            dissatisfied = len(df[df["satisfaction"] == "不満足"])

            # 個別チャット単位の集計
            summary = {
                "total_chats": total_feedback,
                "satisfied_count": satisfied,
                "dissatisfied_count": dissatisfied,
                "satisfaction_rate": (satisfied / total_feedback * 100) if total_feedback > 0 else 0,
                "format_type": "chat_based",
                "unique_sessions": df['session_id'].nunique() if 'session_id' in df.columns else 0,
            }

            # プロンプトスタイル別統計
            if 'prompt_style' in df.columns:
                prompt_stats = df['prompt_style'].value_counts().to_dict()
                summary['prompt_style_distribution'] = prompt_stats

            # 不満足理由の有無
            if 'feedback_reason' in df.columns:
                try:
                    # feedback_reason列を安全に文字列として処理
                    df_safe = df.copy()

                    # NaN値を先に空文字列に置換
                    df_safe['feedback_reason'] = df_safe['feedback_reason'].fillna('')

                    # 文字列型に変換
                    df_safe['feedback_reason'] = df_safe['feedback_reason'].astype(str)

                    # 意味のあるフィードバックを持つ不満足回答をカウント
                    def has_meaningful_reason(reason):
                        if pd.isna(reason):
                            return False
                        str_reason = str(reason).strip()
                        return (
                            str_reason != '' and
                            str_reason != 'nan' and
                            str_reason != '（理由なし）' and
                            len(str_reason) > 0
                        )

                    dissatisfied_with_reason = df_safe[
                        (df_safe['satisfaction'] == '不満足') &
                        df_safe['feedback_reason'].apply(has_meaningful_reason)
                    ]

                    reasons_provided = len(dissatisfied_with_reason)
                    summary['dissatisfied_with_reason'] = reasons_provided
                    summary['dissatisfied_without_reason'] = dissatisfied - reasons_provided
                except Exception as e:
                    # エラー時はフィードバック理由の統計を無効にする
                    if st.secrets.get("DEBUG_MODE", False):
                        st.warning(f"フィードバック理由の統計処理でエラー: {e}")
                    summary['dissatisfied_with_reason'] = 0
                    summary['dissatisfied_without_reason'] = dissatisfied

            return summary

        except Exception as e:
            # より詳細なエラー情報を表示
            st.error(f"集計エラー: {str(e)}")

            # デバッグ情報（エラー時のみ表示）
            if st.secrets.get("DEBUG_MODE", False):
                st.write("🔍 **エラーデバッグ情報**:")
                try:
                    st.write(f"ファイルパス: {self.feedback_file}")
                    if os.path.exists(self.feedback_file):
                        debug_df = pd.read_csv(self.feedback_file, encoding="utf-8")
                        st.write(f"データ行数: {len(debug_df)}")
                        st.write(f"列名: {list(debug_df.columns)}")

                        # 各列のデータ型確認
                        for col in debug_df.columns:
                            unique_values = debug_df[col].unique()[:5]  # 最初の5つのユニーク値
                            st.write(f"列 '{col}': {unique_values}")
                except Exception as debug_e:
                    st.write(f"デバッグ情報取得エラー: {debug_e}")

            return {}

    def get_dissatisfaction_reasons(self, product_name: str = None) -> List[Dict[str, str]]:
        """不満足の理由一覧を取得（個別チャット単位）"""

        try:
            if not os.path.exists(self.feedback_file):
                return []

            df = pd.read_csv(self.feedback_file, encoding="utf-8")

            # 製品フィルタリング
            if product_name:
                df = df[df["product_name"] == product_name]

            # 不満足のフィードバックを抽出
            dissatisfied_df = df[df["satisfaction"] == "不満足"]

            reasons = []
            for _, row in dissatisfied_df.iterrows():
                try:
                    # 各フィールドを安全に取得
                    user_message = str(row.get("user_message", "N/A"))
                    bot_response = str(row.get("bot_response", "N/A"))
                    feedback_reason = str(row.get("feedback_reason", "")).strip()

                    # 空の場合のデフォルト値
                    if not feedback_reason or feedback_reason == 'nan':
                        feedback_reason = "（理由なし）"

                    reasons.append({
                        "timestamp": str(row.get("timestamp", "")),
                        "product_name": str(row.get("product_name", "")),
                        "session_id": str(row.get("session_id", "")),
                        "chat_id": str(row.get("chat_id", "")),
                        "message_sequence": int(row.get("message_sequence", 0)) if pd.notna(row.get("message_sequence")) else 0,
                        "user_question": user_message[:100] + ("..." if len(user_message) > 100 else ""),
                        "bot_answer": bot_response[:100] + ("..." if len(bot_response) > 100 else ""),
                        "feedback_reason": feedback_reason,
                        "prompt_style": str(row.get("prompt_style", ""))
                    })
                except Exception as row_error:
                    # 個別行の処理でエラーが発生した場合はスキップ
                    if st.secrets.get("DEBUG_MODE", False):
                        st.warning(f"行の処理でエラー: {row_error}")
                    continue
            return reasons

        except Exception as e:
            st.error(f"不満足理由取得エラー: {str(e)}")
            return []

    def get_recent_chats(self, product_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """最近のチャット履歴を取得"""

        try:
            if not os.path.exists(self.chat_log_file):
                return []

            df = pd.read_csv(self.chat_log_file, encoding="utf-8")
            df = df[df["product_name"] == product_name]

            # 最新順にソート
            df = df.sort_values("timestamp", ascending=False).head(limit)

            return df.to_dict("records")

        except Exception as e:
            st.error(f"履歴取得エラー: {str(e)}")
            return []

    def show_satisfaction_survey(self, product_name: str, prompt_style: str):
        """満足度調査UIを表示（個別チャット単位）"""

        if st.secrets.get("DEBUG_MODE", False):
            st.write(f"🔍 DEBUG: show_satisfaction_survey called for {product_name}")

        # 最新のチャット情報を取得
        messages = st.session_state.get(f"messages_{product_name}", [])
        if st.secrets.get("DEBUG_MODE", False):
            st.write(f"🔍 DEBUG: Found {len(messages)} messages")
        if len(messages) < 2:
            if st.secrets.get("DEBUG_MODE", False):
                st.write("🔍 DEBUG: Not enough messages, skipping survey")
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
        # 現在のメッセージ数に基づいてsequenceを計算（メッセージペア数）
        message_sequence = len(messages) // 2  # user-assistantペアの数
        chat_id = self.generate_chat_id(session_id, message_sequence)

        if st.secrets.get("DEBUG_MODE", False):
            st.write(f"🔍 DEBUG: session_id: {session_id}, message_sequence: {message_sequence}, chat_id: {chat_id}")

        # このチャットに対してフィードバック済みかチェック
        feedback_key = f"feedback_given_{chat_id}"
        dissatisfied_key = f"dissatisfied_selected_{chat_id}"

        if st.secrets.get("DEBUG_MODE", False):
            st.write(f"🔍 DEBUG: feedback_key: {feedback_key}, already_given: {st.session_state.get(feedback_key, False)}")

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
                        success = self.save_feedback(
                            product_name=product_name,
                            chat_id=chat_id,
                            message_sequence=message_sequence,
                            satisfaction="満足",
                            user_message=latest_user_msg,
                            bot_response=latest_bot_msg,
                            prompt_style=prompt_style,
                            feedback_reason=""
                        )
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
                            success = self.save_feedback(
                                product_name=product_name,
                                chat_id=chat_id,
                                message_sequence=message_sequence,
                                satisfaction="不満足",
                                user_message=latest_user_msg,
                                bot_response=latest_bot_msg,
                                prompt_style=prompt_style,
                                feedback_reason=feedback_reason.strip()
                            )
                            if success:
                                st.session_state[feedback_key] = True
                                st.session_state[dissatisfied_key] = False
                                st.info("📋 フィードバックありがとうございます。改善に努めます。")
                                st.rerun()

                    with col_skip_reason:
                        if st.button("理由を入力せずに送信", key=f"skip_reason_{chat_id}", use_container_width=True):
                            success = self.save_feedback(
                                product_name=product_name,
                                chat_id=chat_id,
                                message_sequence=message_sequence,
                                satisfaction="不満足",
                                user_message=latest_user_msg,
                                bot_response=latest_bot_msg,
                                prompt_style=prompt_style,
                                feedback_reason=""
                            )
                            if success:
                                st.session_state[feedback_key] = True
                                st.session_state[dissatisfied_key] = False
                                st.info("📋 フィードバックありがとうございます。改善に努めます。")
                                st.rerun()

                st.caption("💡 **ヒント**: より良い回答を得るには、プロンプトスタイルを変更してみてください。")


# グローバルインスタンス
feedback_manager = FeedbackManager()
