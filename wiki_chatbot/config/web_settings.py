"""Web環境設定管理。

このモジュールは本番環境とStreamlit Cloudデプロイメント向けの
環境変数と設定管理を処理します。
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st


class WebConfig:
    """Web環境設定管理クラス。

    このクラスは、Webデプロイメント用のAPIキー、ストレージ設定、
    セキュリティ設定、アプリケーション設定を管理するための静的メソッドを提供します。
    """

    @staticmethod
    def get_api_key(provider: str) -> Optional[str]:
        """環境変数またはStreamlit secretsからAPIキーを取得する。

        Args:
            provider: APIプロバイダー名（例："OPENAI"、"ANTHROPIC"）。

        Returns:
            見つかった場合はAPIキー文字列、そうでなければNone。
        """
        key_name = f"{provider.upper()}_API_KEY"

        # 1. 環境変数から取得を試行
        key = os.getenv(key_name)
        if key:
            return key

        # 2. Streamlit secretsから取得を試行
        try:
            return st.secrets[key_name]
        except KeyError:
            return None
        except Exception:
            return None

    @staticmethod
    def get_all_providers_status() -> Dict[str, Dict[str, Any]]:
        """すべてのLLMプロバイダーの利用可能状態をチェックする。

        Returns:
            プロバイダー名をそのステータス情報にマッピングする辞書。
            利用可能性、キー長、プレビューを含みます。
        """
        providers = ["OPENAI", "ANTHROPIC", "GOOGLE"]
        status = {}

        for provider in providers:
            key = WebConfig.get_api_key(provider)
            status[provider] = {
                "available": bool(key),
                "key_length": len(key) if key else 0,
                "key_preview": f"{key[:8]}...{key[-4:]}" if key else None,
            }

        return status

    @staticmethod
    def get_storage_config() -> Dict[str, Any]:
        """ストレージ設定を取得する。

        Returns:
            S3とローカルストレージ設定を含む辞書。
        """
        return {
            "use_s3": os.getenv("USE_S3", "false").lower() == "true",
            "s3_bucket": os.getenv("S3_BUCKET_NAME", "wiki-chatbot-data"),
            "aws_access_key": WebConfig.get_api_key("AWS_ACCESS_KEY"),
            "aws_secret_key": WebConfig.get_api_key("AWS_SECRET_KEY"),
            "local_data_dir": os.getenv("DATA_DIR", "data"),
        }

    @staticmethod
    def get_environment() -> str:
        """現在のデプロイ環境を取得する。

        Returns:
            環境名（例："development"、"production"）。
        """
        return os.getenv("ENVIRONMENT", "development")

    @staticmethod
    def is_production() -> bool:
        """現在の環境が本番かどうかをチェックする。

        Returns:
            本番環境で実行中の場合はTrue、そうでなければFalse。
        """
        return WebConfig.get_environment().lower() == "production"

    @staticmethod
    def get_security_config() -> Dict[str, Any]:
        """セキュリティ設定を取得する。

        Returns:
            認証、セッション、セキュリティ設定を含む辞書。
        """
        return {
            "require_auth": os.getenv("REQUIRE_AUTH", "true").lower() == "true",
            "admin_password": WebConfig.get_api_key("ADMIN_PASSWORD"),
            "secret_key": WebConfig.get_api_key("SECRET_KEY") or "default-secret-key",
            "session_timeout": int(os.getenv("SESSION_TIMEOUT", "3600")),  # 1時間
            "max_file_size": int(os.getenv("MAX_FILE_SIZE", "10485760")),  # 10MB
        }

    @staticmethod
    def get_app_config() -> Dict[str, Any]:
        """アプリケーション設定を取得する。

        Returns:
            アプリタイトル、制限、機能フラグを含む辞書。
        """
        return {
            "app_title": os.getenv("APP_TITLE", "Wiki Chatbot"),
            "company_name": os.getenv("COMPANY_NAME", "Your Company"),
            "max_queries_per_session": int(os.getenv("MAX_QUERIES_PER_SESSION", "100")),
            "enable_analytics": os.getenv("ENABLE_ANALYTICS", "false").lower() == "true",
            "debug_mode": os.getenv("DEBUG_MODE", "false").lower() == "true",
        }

    @staticmethod
    def validate_configuration() -> Tuple[bool, List[str]]:
        """設定と要件を検証する。

        Returns:
            検証ステータスと見つかった設定エラーを示す
            (is_valid, list_of_errors)のタプル。
        """
        errors = []

        # API Key存在チェック
        providers_status = WebConfig.get_all_providers_status()
        available_providers = [p for p, s in providers_status.items() if s["available"]]

        if not available_providers:
            errors.append("少なくとも1つのLLMプロバイダーのAPI Keyが必要です")

        # 本番環境での必須設定チェック
        if WebConfig.is_production():
            security_config = WebConfig.get_security_config()

            if not security_config["admin_password"]:
                errors.append("本番環境ではADMIN_PASSWORDの設定が必須です")

            if security_config["secret_key"] == "default-secret-key":
                errors.append("本番環境ではSECRET_KEYの変更が必須です")

        # ストレージ設定チェック
        storage_config = WebConfig.get_storage_config()
        if storage_config["use_s3"]:
            if not storage_config["aws_access_key"] or not storage_config["aws_secret_key"]:
                errors.append("S3使用時はAWS認証情報が必要です")

        return len(errors) == 0, errors

    @staticmethod
    def setup_logging() -> logging.Logger:
        """アプリケーションのログ設定をセットアップする。

        Returns:
            現在のモジュールの設定済みロガーインスタンス。
        """
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()

        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(),
            ],
        )

        # 本番環境では詳細ログを制限
        if WebConfig.is_production():
            logging.getLogger("streamlit").setLevel(logging.WARNING)
            logging.getLogger("urllib3").setLevel(logging.WARNING)

        return logging.getLogger(__name__)


# Configuration initialization and validation
def initialize_web_config() -> Tuple[bool, List[str]]:
    """Web設定を初期化し、設定を検証する。

    Returns:
        初期化ステータスと見つかった設定エラーを示す
        (is_valid, list_of_errors)のタプル。
    """
    logger = WebConfig.setup_logging()

    # 設定バリデーション
    is_valid, errors = WebConfig.validate_configuration()

    if not is_valid:
        logger.error("設定エラーが検出されました:")
        for error in errors:
            logger.error(f"  - {error}")

    return is_valid, errors


# アプリ起動時の自動実行
if __name__ != "__main__":
    # モジュール読み込み時に設定初期化
    initialize_web_config()
