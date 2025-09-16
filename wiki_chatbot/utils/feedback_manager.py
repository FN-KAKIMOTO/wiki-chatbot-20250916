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
    """

    timestamp: str
    product_name: str
    user_message: str
    bot_response: str
    sources_used: List[str]
    prompt_style: str
    session_id: str


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
    """

    timestamp: str
    product_name: str
    session_id: str
    satisfaction: str  # "満足" or "不満足"
    total_messages: int
    prompt_style: str


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

    def save_chat_message(
        self, product_name: str, user_message: str, bot_response: str, sources_used: List[str], prompt_style: str
    ):
        """チャットメッセージを保存（永続化データベース + CSV）"""

        try:
            session_id = self.get_session_id(product_name)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
                        len(user_message),
                        len(clean_response),
                        len(sources_used),
                    ]
                )

            return True

        except Exception as e:
            st.error(f"チャット履歴保存エラー: {str(e)}")
            return False

    def save_feedback(self, product_name: str, satisfaction: str, prompt_style: str):
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
                        session_duration=session_duration
                    )
                except Exception as db_error:
                    st.warning(f"フィードバックDB保存エラー: {db_error}")

            # CSVに追記（バックアップ・互換性のため）
            with open(self.feedback_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [timestamp, product_name, session_id, satisfaction, messages_count, prompt_style, session_duration]
                )

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

    def export_combined_data(self, product_name: str = None) -> Optional[str]:
        """チャット履歴とフィードバックを統合してエクスポート"""

        try:
            # チャット履歴を読み込み
            if not os.path.exists(self.chat_log_file):
                st.error("チャット履歴ファイルが存在しません")
                return None

            chat_df = pd.read_csv(self.chat_log_file, encoding="utf-8")

            # フィードバックデータを読み込み（存在する場合）
            feedback_df = None
            if os.path.exists(self.feedback_file):
                feedback_df = pd.read_csv(self.feedback_file, encoding="utf-8")

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
                # session_idでフィードバック情報を結合
                combined_df = pd.merge(
                    chat_df,
                    feedback_df[['session_id', 'satisfaction', 'session_duration']],
                    on='session_id',
                    how='left'
                )
            else:
                # フィードバックデータがない場合はチャット履歴のみ
                combined_df = chat_df.copy()
                combined_df['satisfaction'] = None
                combined_df['session_duration'] = None

            # エクスポートファイル名生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_filename = f"combined_export_{product_name or 'all'}_{timestamp}.csv"
            export_path = os.path.join(self.data_dir, export_filename)

            # 列の順序を整理
            column_order = [
                'timestamp', 'product_name', 'session_id', 'user_message', 'bot_response',
                'sources_used', 'prompt_style', 'message_length', 'response_length', 'sources_count',
                'satisfaction', 'session_duration'
            ]

            # 存在する列のみ選択
            available_columns = [col for col in column_order if col in combined_df.columns]
            combined_df = combined_df[available_columns]

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

            df = pd.read_csv(self.feedback_file, encoding="utf-8")

            # 製品フィルタリング
            if product_name:
                df = df[df["product_name"] == product_name]

            if df.empty:
                return {}

            total_feedback = len(df)
            satisfied = len(df[df["satisfaction"] == "満足"])
            dissatisfied = len(df[df["satisfaction"] == "不満足"])

            summary = {
                "total_sessions": total_feedback,
                "satisfied_count": satisfied,
                "dissatisfied_count": dissatisfied,
                "satisfaction_rate": (satisfied / total_feedback * 100) if total_feedback > 0 else 0,
                "avg_messages_per_session": df["total_messages"].mean() if total_feedback > 0 else 0,
                "avg_session_duration": df["session_duration"].astype(float).mean() if total_feedback > 0 else 0,
            }

            return summary

        except Exception as e:
            st.error(f"集計エラー: {str(e)}")
            return {}

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
                        self.save_feedback(product_name, "不満足", prompt_style)
                        st.session_state[feedback_key] = True
                        st.info("📋 フィードバックありがとうございます。改善に努めます。")
                        st.rerun()

                with col3:
                    if st.button("⏭️ スキップ", key=f"skip_{product_name}", help="フィードバックを送信しない"):
                        st.session_state[feedback_key] = True
                        st.rerun()

                st.caption("💡 **ヒント**: より良い回答を得るには、プロンプトスタイルを変更してみてください。")


# グローバルインスタンス
feedback_manager = FeedbackManager()
