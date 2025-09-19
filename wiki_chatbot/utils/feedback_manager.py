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
        satisfaction: ユーザー満足度（「満足」または「不満足」）。
        total_messages: セッション内のメッセージ総数。
        prompt_style: セッション中に使用されたプロンプトのタイプ。
        feedback_reason: 不満足の理由（自由回答、満足の場合は空文字）。
    """

    timestamp: str
    product_name: str
    session_id: str
    satisfaction: str  # "満足" or "不満足"
    total_messages: int
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
            except Exception as e:
                st.warning(f"GitHub同期初期化エラー: {e}")

        # 自動バックアップの設定
        self.auto_backup_enabled = st.secrets.get("AUTO_BACKUP_ENABLED", True)
        self.backup_interval = st.secrets.get("BACKUP_INTERVAL_MESSAGES", 5)  # メッセージ5件ごと
        self.message_count_since_backup = 0

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
                "satisfaction",
                "total_messages",
                "prompt_style",
                "session_duration",
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

    def _trigger_auto_backup(self, action: str = "Auto backup"):
        """自動バックアップをトリガーする"""
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

    def _force_backup(self, action: str = "Force backup"):
        """強制バックアップを実行する（ファイルアップロード時など）"""
        if not self.github_sync:
            return

        try:
            success = self.github_sync.upload_data(f"{action} - {datetime.now().isoformat()}")
            if success and st.secrets.get("DEBUG_MODE", False):
                st.success(f"✅ 強制バックアップ完了 ({action})")
        except Exception as e:
            if st.secrets.get("DEBUG_MODE", False):
                st.error(f"❌ 強制バックアップエラー: {e}")

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

    def save_feedback(self, product_name: str, satisfaction: str, prompt_style: str, feedback_reason: str = ""):
        """ユーザーフィードバックを保存（永続化データベース + CSV）"""

        try:
            session_id = self.get_session_id(product_name)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # セッション情報の取得
            messages_count = len(st.session_state.get(f"messages_{product_name}", []))

            # セッション継続時間の計算
            session_start = st.session_state.get(f"session_start_{product_name}")
            session_duration = ""
            if session_start:
                duration = datetime.now() - session_start
                session_duration = str(duration.seconds // 60)  # 分単位

            # 永続化データベースに保存（優先）
            if PERSISTENT_DB_AVAILABLE:
                try:
                    persistent_db.save_feedback(
                        session_id=session_id,
                        product_name=product_name,
                        satisfaction=satisfaction,
                        total_messages=messages_count,
                        prompt_style=prompt_style,
                        session_duration=session_duration,
                        feedback_text=feedback_reason
                    )
                except Exception as db_error:
                    st.warning(f"フィードバックDB保存エラー: {db_error}")

            # CSVに追記（バックアップ・互換性のため）
            with open(self.feedback_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [timestamp, product_name, session_id, satisfaction, messages_count, prompt_style, session_duration, feedback_reason]
                )

            # フィードバック保存時は即座にバックアップ（重要データのため）
            self._force_backup("Feedback saved")

            return True

        except Exception as e:
            st.error(f"フィードバック保存エラー: {str(e)}")
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

        except Exception as e:
            st.error(f"エクスポートエラー: {str(e)}")
            return None

    def export_conversation_format(self, product_name: str = None) -> Optional[str]:
        """会話形式でチャット履歴をエクスポート（Q&Aペア構造）"""

        try:
            if not os.path.exists(self.chat_log_file):
                return None

            df = pd.read_csv(self.chat_log_file, encoding="utf-8")

            # 後方互換性のための列補完
            if 'chat_id' not in df.columns:
                df['chat_id'] = df.apply(lambda row: f"{row.get('session_id', 'unknown')}_msg_{row.name+1:03d}", axis=1)
            if 'message_sequence' not in df.columns:
                df['message_sequence'] = df.groupby('session_id').cumcount() + 1

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

            # チャット履歴に不足している列を追加（後方互換性のため）
            if 'user_name' not in chat_df.columns:
                chat_df['user_name'] = ""
            if 'chat_id' not in chat_df.columns:
                # 既存データに対してchat_idを生成
                chat_df['chat_id'] = chat_df.apply(lambda row: f"{row.get('session_id', 'unknown')}_msg_{row.name+1:03d}", axis=1)
            if 'message_sequence' not in chat_df.columns:
                # セッション毎に連番を付与
                chat_df['message_sequence'] = chat_df.groupby('session_id').cumcount() + 1

            # フィードバックデータを読み込み（存在する場合）
            feedback_df = None
            if os.path.exists(self.feedback_file):
                feedback_df = pd.read_csv(self.feedback_file, encoding="utf-8")

                # フィードバックデータに不足している列を追加（後方互換性のため）
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

                # session_idでフィードバック情報を結合
                feedback_columns = ['session_id', 'satisfaction', 'session_duration', 'feedback_reason']
                # 存在する列のみを使用
                available_feedback_columns = [col for col in feedback_columns if col in feedback_df.columns]

                try:
                    combined_df = pd.merge(
                        chat_df,
                        feedback_df[available_feedback_columns],
                        on='session_id',
                        how='left'
                    )
                except Exception as merge_error:
                    st.error(f"マージエラー: {merge_error}")
                    st.warning("フィードバックデータなしでエクスポートします")
                    combined_df = chat_df.copy()
                    combined_df['satisfaction'] = None
                    combined_df['session_duration'] = None
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
                combined_df['session_duration'] = None
                combined_df['feedback_reason'] = None

            # 不足している列を補完（マージ後に欠けている可能性があるため）
            expected_feedback_columns = ['satisfaction', 'session_duration', 'feedback_reason']
            for col in expected_feedback_columns:
                if col not in combined_df.columns:
                    combined_df[col] = None

            # エクスポートファイル名生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_filename = f"combined_export_{product_name or 'all'}_{timestamp}.csv"
            export_path = os.path.join(self.data_dir, export_filename)

            # 列の順序を整理（新しいフィールドを含む）
            column_order = [
                'timestamp', 'product_name', 'session_id', 'chat_id', 'message_sequence', 'user_name',
                'user_message', 'bot_response', 'sources_used', 'prompt_style', 'message_length',
                'response_length', 'sources_count', 'satisfaction', 'session_duration', 'feedback_reason'
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

        except Exception as e:
            st.error(f"統合エクスポートエラー: {str(e)}")
            return None

    def get_feedback_summary(self, product_name: str = None) -> Dict[str, Any]:
        """フィードバック集計結果を取得"""

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

            # 数値列の安全な処理（数値変換エラーのハンドリング）
            try:
                # session_durationの処理
                numeric_duration = pd.to_numeric(df["session_duration"], errors='coerce')
                avg_duration = numeric_duration.mean() if total_feedback > 0 else 0
                if pd.isna(avg_duration):
                    avg_duration = 0
            except Exception:
                avg_duration = 0

            try:
                # total_messagesの処理
                numeric_messages = pd.to_numeric(df["total_messages"], errors='coerce')
                avg_messages = numeric_messages.mean() if total_feedback > 0 else 0
                if pd.isna(avg_messages):
                    avg_messages = 0
            except Exception:
                avg_messages = 0

            summary = {
                "total_sessions": total_feedback,
                "satisfied_count": satisfied,
                "dissatisfied_count": dissatisfied,
                "satisfaction_rate": (satisfied / total_feedback * 100) if total_feedback > 0 else 0,
                "avg_messages_per_session": avg_messages,
                "avg_session_duration": avg_duration,
            }

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
        """不満足の理由一覧を取得"""

        try:
            if not os.path.exists(self.feedback_file):
                return []

            df = pd.read_csv(self.feedback_file, encoding="utf-8")

            # 製品フィルタリング
            if product_name:
                df = df[df["product_name"] == product_name]

            # feedback_reason列が存在するかチェック
            if "feedback_reason" not in df.columns:
                # 古い形式のファイルの場合、不満足のデータのみ返す（理由なし）
                dissatisfied_df = df[df["satisfaction"] == "不満足"]
                reasons = []
                for _, row in dissatisfied_df.iterrows():
                    reasons.append({
                        "timestamp": row["timestamp"],
                        "product_name": row["product_name"],
                        "session_id": row["session_id"],
                        "feedback_reason": "（理由未記録）",
                        "prompt_style": row.get("prompt_style", ""),
                        "total_messages": row.get("total_messages", 0)
                    })
                return reasons

            # 不満足で理由が記入されているもののみ抽出
            dissatisfied_df = df[
                (df["satisfaction"] == "不満足") &
                (df["feedback_reason"].notna()) &
                (df["feedback_reason"].str.strip() != "")
            ]

            if dissatisfied_df.empty:
                return []

            # 結果を辞書のリストとして返す
            reasons = []
            for _, row in dissatisfied_df.iterrows():
                reasons.append({
                    "timestamp": row["timestamp"],
                    "product_name": row["product_name"],
                    "session_id": row["session_id"],
                    "feedback_reason": row["feedback_reason"],
                    "prompt_style": row.get("prompt_style", ""),
                    "total_messages": row.get("total_messages", 0)
                })

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
        """満足度調査UIを表示"""

        survey_key = f"show_satisfaction_{product_name}"
        feedback_key = f"feedback_given_{product_name}"
        dissatisfied_key = f"dissatisfied_selected_{product_name}"

        # まだフィードバックを送信していない場合のみ表示
        if len(st.session_state.get(f"messages_{product_name}", [])) >= 2 and not st.session_state.get(
            feedback_key, False
        ):

            with st.container():
                st.divider()
                st.subheader("📝 ご利用満足度について")
                st.write("**今回のチャットはお役に立ちましたか？**")
                st.caption("皆様のフィードバックはサービス改善のために活用させていただきます。")

                col1, col2, col3 = st.columns([1, 1, 2])

                with col1:
                    if st.button(
                        "😊 満足", key=f"satisfied_{product_name}", help="回答が役に立った", use_container_width=True
                    ):
                        self.save_feedback(product_name, "満足", prompt_style)
                        st.session_state[feedback_key] = True
                        st.success("✅ フィードバックありがとうございます！")
                        st.rerun()

                with col2:
                    if st.button(
                        "😔 不満足",
                        key=f"dissatisfied_{product_name}",
                        help="期待した回答が得られなかった",
                        use_container_width=True,
                    ):
                        # 不満足ボタンが押された場合、理由入力フォームを表示
                        st.session_state[dissatisfied_key] = True
                        st.rerun()

                with col3:
                    if st.button("⏭️ スキップ", key=f"skip_{product_name}", help="フィードバックを送信しない"):
                        st.session_state[feedback_key] = True
                        st.rerun()

                # 不満足が選択された場合、理由入力フォームを表示
                if st.session_state.get(dissatisfied_key, False):
                    st.write("")  # スペース
                    st.write("**不満足の理由をお聞かせください（任意）：**")

                    feedback_reason = st.text_area(
                        "改善のためのご意見をお聞かせください",
                        placeholder="例：回答が不正確だった、情報が古かった、期待していた内容と違った など",
                        key=f"feedback_reason_{product_name}",
                        height=80
                    )

                    col_submit, col_skip_reason = st.columns([1, 1])

                    with col_submit:
                        if st.button("📤 送信", key=f"submit_feedback_{product_name}", use_container_width=True):
                            self.save_feedback(product_name, "不満足", prompt_style, feedback_reason.strip())
                            st.session_state[feedback_key] = True
                            st.session_state[dissatisfied_key] = False
                            st.info("📋 フィードバックありがとうございます。改善に努めます。")
                            st.rerun()

                    with col_skip_reason:
                        if st.button("理由を入力せずに送信", key=f"skip_reason_{product_name}", use_container_width=True):
                            self.save_feedback(product_name, "不満足", prompt_style, "")
                            st.session_state[feedback_key] = True
                            st.session_state[dissatisfied_key] = False
                            st.info("📋 フィードバックありがとうございます。改善に努めます。")
                            st.rerun()

                st.caption("💡 **ヒント**: より良い回答を得るには、プロンプトスタイルを変更してみてください。")


# グローバルインスタンス
feedback_manager = FeedbackManager()
