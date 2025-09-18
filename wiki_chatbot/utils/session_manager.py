# -*- coding: utf-8 -*-
"""セッション管理とWebアプリケーションユーティリティ。

このモジュールは、StreamlitベースのWikiチャットボットアプリケーションにおける
包括的なセッション管理機能を提供します。ユーザー認証、セッション制限、
データ永続化を統合的に管理し、Webアプリケーションのセキュリティと
ユーザビリティを両立します。

主要機能:
    1. セッション管理:
        - ユーザーセッションの初期化と状態管理
        - セッション有効期限の自動監視
        - 認証状態の永続化と検証

    2. 認証システム:
        - パスワードベースの認証機能
        - セッション単位での認証状態管理
        - 自動ログアウト機能

    3. 使用量制限:
        - セッション単位でのクエリ数制限
        - リアルタイム使用量追跡
        - 制限到達時の自動警告

    4. データ永続化:
        - チャット履歴の保存・読み込み
        - セッション間でのデータ維持
        - エクスポート機能

技術仕様:
    - StreamlitのSession Stateを活用した状態管理
    - 時間ベースのセッション有効期限管理
    - 設定ベースの柔軟なセキュリティパラメータ
    - 静的メソッドによる状態管理の一元化

使用例:
    ```python
    from utils.session_manager import SessionManager

    # セッション初期化（アプリ開始時）
    SessionManager.initialize_session()

    # 認証チェック（各ページで）
    if not SessionManager.check_authentication():
        if not SessionManager.authenticate_user():
            return

    # クエリ実行前の制限チェック
    if SessionManager.check_query_limit():
        # クエリ実行
        SessionManager.increment_query_count()
    ```

設計思想:
    このモジュールは、エンタープライズ環境でのWebアプリケーション運用を
    想定した包括的なセッション管理を提供します。セキュリティ、パフォーマンス、
    ユーザビリティのバランスを取り、運用しやすい設計を心がけています。
"""
import os
import time
from typing import Any, Dict

import streamlit as st

from config.web_settings import WebConfig

# GitHub同期のインポート
try:
    from config.github_settings import GitHubConfig
    from utils.github_sync import GitHubDataSync
    GITHUB_SYNC_AVAILABLE = True
except ImportError:
    GITHUB_SYNC_AVAILABLE = False


class SessionManager:
    """Webアプリケーション用セッション管理クラス。

    このクラスは、StreamlitベースのWikiチャットボットアプリケーションにおける
    包括的なセッション管理機能を提供します。静的メソッドのみで構成されており、
    アプリケーション全体で一貫したセッション状態管理を実現します。

    主要責務:
        1. セッション初期化と状態管理:
            - 新規セッションの初期化
            - セッション状態の一貫性維持
            - セッション有効期限の監視

        2. 認証・認可システム:
            - パスワードベースの認証機能
            - セッション単位での認証状態管理
            - 認証状態の永続化

        3. 使用量制限と監視:
            - セッション単位でのクエリ数制限
            - リアルタイム使用量追跡
            - 制限違反時の警告表示

        4. セッション情報管理:
            - 包括的なセッション情報の提供
            - ユーザビリティ向上のための状態表示
            - ログアウト機能

    設計パターン:
        静的メソッドのみで構成されたユーティリティクラスです。
        インスタンス化は不要で、すべてのメソッドは直接クラスから呼び出します。
        Streamlitのセッション状態を活用し、サーバー再起動まで状態を維持します。

    技術的特徴:
        - StreamlitのSession State APIを基盤とした状態管理
        - 時間ベースのセッション有効期限監視
        - 設定ファイルベースの柔軟なパラメータ管理
        - エラー処理とフォールバック機能内蔵
    """

    @staticmethod
    def initialize_session() -> None:
        """セッション状態をデフォルト値で初期化する。

        新規セッション開始時に必要な初期値をStreamlitのSession Stateに設定します。
        重複初期化を防ぐため、既に初期化されているセッションはスキップします。

        初期化される状態変数:
            - initialized: セッション初期化完了フラグ
            - authenticated: ユーザー認証状態（False: 未認証）
            - user_id: ユーザー識別子（None: 匿名ユーザー）
            - session_start_time: セッション開始時刻（UNIX時間）
            - query_count: 現在セッションでのクエリ実行回数
            - chat_history: チャット履歴リスト

        Note:
            このメソッドは冪等性を保証します。
            複数回呼び出されても、初回のみ実行され、
            既存のセッション状態は保護されます。

        使用例:
            アプリケーションの最初（通常はapp.pyのmain関数内）で呼び出し:
            ```python
            SessionManager.initialize_session()
            ```
        """
        # 重複初期化を防ぐためのガード条件
        if "initialized" not in st.session_state:
            st.session_state.initialized = True              # 初期化完了フラグ
            st.session_state.authenticated = False           # 認証状態（初期値: 未認証）
            st.session_state.user_id = None                  # ユーザーID（初期値: 匿名）
            st.session_state.session_start_time = time.time() # セッション開始時刻
            st.session_state.query_count = 0                # クエリ実行回数カウンタ
            st.session_state.chat_history = []              # チャット履歴リスト

    @staticmethod
    def check_authentication() -> bool:
        """現在の認証ステータスをチェックする。

        Returns:
            ユーザーが認証済みか認証が不要な場合はTrue、
            そうでなければFalse。
        """
        security_config = WebConfig.get_security_config()

        # 認証が不要な場合はTrue
        if not security_config["require_auth"]:
            return True

        # セッションタイムアウトチェック
        if SessionManager.is_session_expired():
            st.session_state.authenticated = False
            return False

        return st.session_state.get("authenticated", False)

    @staticmethod
    def authenticate_user() -> bool:
        """ユーザー認証プロセスを処理する。

        認証フォームを表示し、@farmnote.jpドメインのメールアドレスと
        共通パスワードでユーザーの資格情報を検証します。


        Returns:
            認証が成功または不要な場合はTrue、
            そうでなければFalse。
        """
        security_config = WebConfig.get_security_config()

        if not security_config["require_auth"]:
            return True

        st.title("🔐 認証が必要です")
        st.write("@farmnote.jpのメールアドレスでログインしてください")

        with st.form("auth_form"):
            email = st.text_input("メールアドレス", placeholder="your-name@farmnote.jp")
            password = st.text_input("パスワード", type="password")
            submitted = st.form_submit_button("ログイン")

            if submitted:
                # メールアドレスのドメインチェック
                if not email.endswith("@farmnote.jp"):
                    st.error("❌ @farmnote.jpのメールアドレスを入力してください")
                    return False
                    
                if password == os.getenv("SHARED_PASSWORD"):
                    st.session_state.authenticated = True
                    st.session_state.user_id = email.split("@")[0]  # メールアドレスの@より前の部分をユーザーIDとして使用
                    st.session_state.user_email = email  # 完全なメールアドレスも保存
                    st.session_state.session_start_time = time.time()

                    # 認証成功メッセージを表示
                    st.success("✅ 認証成功")

                    # ログイン時の自動データ復元を実行
                    SessionManager._perform_login_data_restore()

                    st.rerun()
                else:
                    st.error("❌ パスワードが正しくありません")
                    return False

        return False

    @staticmethod
    def is_session_expired() -> bool:
        """現在のセッションが期限切れかどうかをチェックする。

        Returns:
            セッションが設定されたタイムアウト時間を超えた場合はTrue、
            そうでなければFalse。
        """
        security_config = WebConfig.get_security_config()

        if "session_start_time" not in st.session_state:
            return True

        current_time = time.time()
        elapsed_time = current_time - st.session_state.session_start_time

        return elapsed_time > security_config["session_timeout"]

    @staticmethod
    def check_query_limit() -> bool:
        """ユーザーが現在のセッションでクエリ制限を超えたかどうかをチェックする。

        Returns:
            ユーザーがクエリ制限内の場合はTrue、そうでなければFalse。
        """
        app_config = WebConfig.get_app_config()
        max_queries = app_config["max_queries_per_session"]

        current_queries = st.session_state.get("query_count", 0)

        if current_queries >= max_queries:
            st.warning(f"⚠️ セッション当たりの最大クエリ数({max_queries})に達しました。")
            return False

        return True

    @staticmethod
    def increment_query_count() -> None:
        """現在のセッションのクエリ数をインクリメントする。

        セッション状態にクエリ数がまだ存在しない場合は初期化します。
        """
        if "query_count" not in st.session_state:
            st.session_state.query_count = 0

        st.session_state.query_count += 1

    @staticmethod
    def get_session_info() -> Dict[str, Any]:
        """包括的なセッション情報を取得する。

        Returns:
            ユーザー情報、認証ステータス、クエリ数、
            タイミング情報、セッションステータスを含む辞書。
        """
        if "session_start_time" not in st.session_state:
            return {}

        current_time = time.time()
        elapsed_time = current_time - st.session_state.session_start_time
        security_config = WebConfig.get_security_config()
        remaining_time = security_config["session_timeout"] - elapsed_time

        return {
            "user_id": st.session_state.get("user_id", "anonymous"),
            "authenticated": st.session_state.get("authenticated", False),
            "query_count": st.session_state.get("query_count", 0),
            "elapsed_time": elapsed_time,
            "remaining_time": max(0, remaining_time),
            "session_expired": remaining_time <= 0,
        }

    @staticmethod
    def logout() -> None:
        """ユーザーログアウト処理を処理する。

        認証ステータス、ユーザー情報、チャット履歴をクリアし、
        成功メッセージを表示してアプリケーションを再実行します。
        """
        st.session_state.authenticated = False
        st.session_state.user_id = None
        st.session_state.user_email = None
        st.session_state.chat_history = []
        st.success("✅ ログアウトしました")
        st.rerun()

    @staticmethod
    def display_session_status() -> None:
        """サイドバーにセッション状態情報を表示する。

        ユーザー認証ステータス、クエリ数、残りセッション時間を表示し、
        認証済みの場合はログアウト機能を提供します。
        """
        session_info = SessionManager.get_session_info()

        if not session_info:
            return

        with st.sidebar:
            st.divider()
            st.subheader("📊 セッション状態")

            # ユーザー情報
            if session_info["authenticated"]:
                user_email = st.session_state.get("user_email", f"{session_info['user_id']}@farmnote.jp")
                st.success(f"👤 ユーザー: {user_email}")
            else:
                st.info("👤 匿名ユーザー")

            # クエリ回数
            app_config = WebConfig.get_app_config()
            max_queries = app_config["max_queries_per_session"]
            st.info(f"🔢 クエリ数: {session_info['query_count']}/{max_queries}")

            # セッション時間
            if session_info["authenticated"]:
                remaining_minutes = int(session_info["remaining_time"] / 60)
                if remaining_minutes > 0:
                    st.info(f"⏰ 残り時間: {remaining_minutes}分")
                else:
                    st.warning("⏰ セッション期限切れ")

            # ログアウトボタン
            if session_info["authenticated"]:
                # データ復元状況の表示
                if GITHUB_SYNC_AVAILABLE and GitHubConfig.is_configured():
                    try:
                        config = GitHubConfig.get_config()
                        github_sync = GitHubDataSync(
                            repo_url=config["repo_url"],
                            token=config["token"]
                        )
                        sync_status = github_sync.get_sync_status()

                        if sync_status["chroma_db_exists"] or sync_status["sqlite_db_exists"]:
                            st.info("💾 データ同期済み")
                        else:
                            st.warning("📥 データ未同期")

                        # 復元状況のみ表示（手動復元ボタンはapp.pyのサイドバーに統合）

                    except Exception:
                        st.caption("📊 同期状況確認不可")

                if st.button("🚪 ログアウト"):
                    SessionManager.logout()

    @staticmethod
    def _perform_login_data_restore() -> None:
        """ログイン時の自動データ復元を実行する。

        GitHub同期が設定されている場合、ログイン認証成功時に
        自動的にデータ復元（ダウンロード）を実行します。

        処理内容:
            1. GitHub同期設定の確認
            2. GitHubDataSyncインスタンスの初期化
            3. データ復元の実行
            4. 結果の表示（成功/失敗メッセージ）

        Note:
            - エラーが発生しても認証プロセスは継続されます
            - デバッグモードでは詳細な処理状況を表示します
            - GitHub同期が無効な場合はスキップされます
        """
        # GitHub同期が利用可能かチェック
        if not GITHUB_SYNC_AVAILABLE:
            if st.secrets.get("DEBUG_MODE", False):
                st.info("🔄 GitHub同期機能が利用できません（スキップ）")
            return

        # GitHub設定の確認
        if not GitHubConfig.is_configured():
            if st.secrets.get("DEBUG_MODE", False):
                st.info("🔄 GitHub同期が設定されていません（スキップ）")
            return

        try:
            # GitHub同期の初期化
            config = GitHubConfig.get_config()
            github_sync = GitHubDataSync(
                repo_url=config["repo_url"],
                token=config["token"]
            )

            # 現在のデータ状況を確認
            sync_status = github_sync.get_sync_status()
            has_local_data = sync_status["chroma_db_exists"] or sync_status["sqlite_db_exists"]

            if has_local_data:
                # 既存データがある場合の処理
                if st.secrets.get("DEBUG_MODE", False):
                    st.info("📁 ローカルデータが存在します - GitHubとの同期を確認中...")

                # より新しいデータがあるかチェックして同期
                with st.spinner("🔄 データ同期確認中..."):
                    success = github_sync.download_data()

                if success:
                    st.success("✅ データ同期完了 - 最新データで開始します")
                else:
                    st.info("💾 既存のローカルデータで開始します")
            else:
                # ローカルデータがない場合の復元処理
                st.info("📥 初回ログイン - GitHubからデータを復元中...")

                with st.spinner("🔄 データ復元中..."):
                    success = github_sync.download_data()

                if success:
                    st.success("✅ データ復元完了 - GitHubから最新データを取得しました")
                else:
                    st.info("🆕 新規環境として開始します")

            # デバッグモードでの詳細表示
            if st.secrets.get("DEBUG_MODE", False):
                updated_sync_status = github_sync.get_sync_status()
                st.write("📊 **同期後の状況**:")
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**ChromaDB:**", "✅" if updated_sync_status["chroma_db_exists"] else "❌")
                    if updated_sync_status["chroma_db_exists"]:
                        st.caption(f"サイズ: {updated_sync_status['chroma_db_size']:,} bytes")
                with col2:
                    st.write("**SQLiteDB:**", "✅" if updated_sync_status["sqlite_db_exists"] else "❌")
                    if updated_sync_status["sqlite_db_exists"]:
                        st.caption(f"サイズ: {updated_sync_status['sqlite_db_size']:,} bytes")

        except Exception as e:
            # エラーが発生してもログインプロセスは継続
            st.warning(f"⚠️ ログイン時データ復元エラー: {str(e)}")
            if st.secrets.get("DEBUG_MODE", False):
                st.error(f"詳細エラー: {e}")

        # 処理完了メッセージ
        if st.secrets.get("DEBUG_MODE", False):
            st.info("🔄 ログイン時データ復元処理完了")


class DataPersistence:
    """データ永続化管理クラス。

    このクラスは、チャット履歴の永続化管理のための静的メソッドを提供し、
    データの保存、読み込み、クリア、エクスポート機能を含みます。
    """

    @staticmethod
    def save_chat_history() -> None:
        """チャット履歴をセッション状態に保存する。

        Note:
            現在はStreamlitセッション状態をストレージに使用しています。
            本番デプロイの場合は、データベースやS3の使用を検討してください。
        """
        # Streamlitのセッション状態を利用
        # 実際のWebデプロイでは、データベースやS3への保存を検討
        pass

    @staticmethod
    def load_chat_history() -> list:
        """セッション状態からチャット履歴を読み込む。

        Returns:
            チャット履歴交換のリスト、存在しない場合は空のリスト。
        """
        return st.session_state.get("chat_history", [])

    @staticmethod
    def clear_chat_history() -> None:
        """セッション状態からすべてのチャット履歴をクリアする。"""
        st.session_state.chat_history = []

    @staticmethod
    def export_chat_history() -> str:
        """チャット履歴をフォーマットされたテキストとしてエクスポートする。

        Returns:
            完全なチャット履歴を含むMarkdown形式の文字列、
            または履歴が存在しないことを示すメッセージ。
        """
        chat_history = DataPersistence.load_chat_history()

        if not chat_history:
            return "チャット履歴はありません。"

        export_text = "# チャット履歴\n\n"

        for i, exchange in enumerate(chat_history, 1):
            export_text += f"## 質問 {i}\n"
            export_text += f"{exchange.get('user_message', '')}\n\n"
            export_text += f"## 回答 {i}\n"
            export_text += f"{exchange.get('bot_response', '')}\n\n"
            export_text += "---\n\n"

        return export_text
