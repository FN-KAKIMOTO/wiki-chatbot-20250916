# 統合設定ファイル - 全パラメータを一括管理

import os
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import streamlit as st


@dataclass
class LLMModelConfig:
    """LLMモデル設定"""

    name: str
    max_tokens: int
    temperature: float
    top_p: float
    frequency_penalty: float
    presence_penalty: float
    cost_per_1k_tokens_input: float
    cost_per_1k_tokens_output: float
    context_window: int
    supports_function_calling: bool = False


@dataclass
class RAGConfig:
    """RAG処理設定"""

    chunk_size: int
    chunk_overlap: int
    search_top_k: int
    embedding_model: str
    vector_store_type: str
    similarity_threshold: float


@dataclass
class SystemConfig:
    """システム設定"""

    app_title: str
    app_icon: str
    max_file_size_mb: int
    supported_file_types: List[str]
    session_timeout_minutes: int
    log_level: str
    enable_debug_mode: bool


class Settings:
    """統合設定管理クラス"""

    # === LLMプロバイダー別設定 ===
    LLM_PROVIDERS = {
        "openai": {
            "name": "OpenAI",
            "api_key_env": "OPENAI_API_KEY",
            "models": {
                "gpt-3.5-turbo": LLMModelConfig(
                    name="GPT-3.5 Turbo",
                    max_tokens=4000,
                    temperature=0.3,
                    top_p=0.9,
                    frequency_penalty=0.0,
                    presence_penalty=0.0,
                    cost_per_1k_tokens_input=0.0015,
                    cost_per_1k_tokens_output=0.002,
                    context_window=16385,
                    supports_function_calling=True,
                ),
                "gpt-4": LLMModelConfig(
                    name="GPT-4",
                    max_tokens=8000,
                    temperature=0.2,
                    top_p=0.9,
                    frequency_penalty=0.0,
                    presence_penalty=0.0,
                    cost_per_1k_tokens_input=0.03,
                    cost_per_1k_tokens_output=0.06,
                    context_window=8192,
                    supports_function_calling=True,
                ),
                "gpt-4o": LLMModelConfig(
                    name="GPT-4o",
                    max_tokens=4000,
                    temperature=0.2,
                    top_p=0.9,
                    frequency_penalty=0.0,
                    presence_penalty=0.0,
                    cost_per_1k_tokens_input=0.005,
                    cost_per_1k_tokens_output=0.015,
                    context_window=128000,
                    supports_function_calling=True,
                ),
            },
        },
        "anthropic": {
            "name": "Anthropic (Claude)",
            "api_key_env": "ANTHROPIC_API_KEY",
            "models": {
                "claude-3-haiku": LLMModelConfig(
                    name="Claude 3 Haiku",
                    max_tokens=4000,
                    temperature=0.3,
                    top_p=0.9,
                    frequency_penalty=0.0,
                    presence_penalty=0.0,
                    cost_per_1k_tokens_input=0.00025,
                    cost_per_1k_tokens_output=0.00125,
                    context_window=200000,
                ),
                "claude-3-sonnet": LLMModelConfig(
                    name="Claude 3 Sonnet",
                    max_tokens=4000,
                    temperature=0.2,
                    top_p=0.9,
                    frequency_penalty=0.0,
                    presence_penalty=0.0,
                    cost_per_1k_tokens_input=0.003,
                    cost_per_1k_tokens_output=0.015,
                    context_window=200000,
                ),
                "claude-3-opus": LLMModelConfig(
                    name="Claude 3 Opus",
                    max_tokens=4000,
                    temperature=0.1,
                    top_p=0.9,
                    frequency_penalty=0.0,
                    presence_penalty=0.0,
                    cost_per_1k_tokens_input=0.015,
                    cost_per_1k_tokens_output=0.075,
                    context_window=200000,
                ),
            },
        },
        "google": {
            "name": "Google (Gemini)",
            "api_key_env": "GOOGLE_API_KEY",
            "models": {
                "gemini-1.5-flash": LLMModelConfig(
                    name="Gemini 1.5 Flash",
                    max_tokens=8192,
                    temperature=0.3,
                    top_p=0.95,
                    frequency_penalty=0.0,
                    presence_penalty=0.0,
                    cost_per_1k_tokens_input=0.000075,
                    cost_per_1k_tokens_output=0.0003,
                    context_window=1000000,
                ),
                "gemini-1.5-pro": LLMModelConfig(
                    name="Gemini 1.5 Pro",
                    max_tokens=8192,
                    temperature=0.2,
                    top_p=0.95,
                    frequency_penalty=0.0,
                    presence_penalty=0.0,
                    cost_per_1k_tokens_input=0.00125,
                    cost_per_1k_tokens_output=0.00375,
                    context_window=2000000,
                ),
            },
        },
    }

    # === RAG設定 ===
    RAG_SETTINGS = {
        "general": RAGConfig(
            chunk_size=1000,
            chunk_overlap=200,
            search_top_k=5,
            embedding_model="text-embedding-ada-002",
            vector_store_type="chromadb",
            similarity_threshold=0.7,
        ),
        "short_docs": RAGConfig(
            chunk_size=500,
            chunk_overlap=100,
            search_top_k=7,
            embedding_model="text-embedding-ada-002",
            vector_store_type="chromadb",
            similarity_threshold=0.75,
        ),
        "long_docs": RAGConfig(
            chunk_size=1500,
            chunk_overlap=300,
            search_top_k=3,
            embedding_model="text-embedding-ada-002",
            vector_store_type="chromadb",
            similarity_threshold=0.65,
        ),
        "technical": RAGConfig(
            chunk_size=2000,
            chunk_overlap=400,
            search_top_k=4,
            embedding_model="text-embedding-ada-002",
            vector_store_type="chromadb",
            similarity_threshold=0.6,
        ),
    }

    # === システム設定 ===
    SYSTEM_CONFIG = SystemConfig(
        app_title="社内Wiki検索チャットボット",
        app_icon="💬",
        max_file_size_mb=50,
        supported_file_types=["txt", "pdf", "docx", "html", "csv", "xlsx", "pptx", "json", "md"],
        session_timeout_minutes=60,
        log_level="INFO",
        enable_debug_mode=False,
    )

    # === プロンプトテンプレート（廃止予定） ===
    # 注意: 新しいプロンプトシステム（prompt_manager.py）を使用してください
    SYSTEM_PROMPTS = {
        # 互換性のために残していますが、新規実装では prompt_manager を使用
    }

    # === デフォルト設定取得メソッド ===
    @classmethod
    def get_default_provider(cls) -> str:
        """デフォルトのLLMプロバイダーを取得（優先順位: ChatGPT -> Anthropic -> Gemini）"""
        # セッション状態に保存された選択があれば優先
        if "selected_provider" in st.session_state:
            return st.session_state["selected_provider"]

        # 優先順位に従って利用可能なプロバイダーを選択
        priority_order = ["openai", "anthropic", "google"]

        for provider in priority_order:
            if cls.get_api_key(provider):
                return provider

        # フォールバック（API Key未設定でも最初のプロバイダーを返す）
        return "openai"

    @classmethod
    def get_default_model(cls, provider: str) -> str:
        """指定プロバイダーのデフォルトモデルを取得"""
        models = list(cls.LLM_PROVIDERS[provider]["models"].keys())
        session_key = f"selected_model_{provider}"

        # セッション状態から取得
        saved_model = st.session_state.get(session_key)

        # 保存されたモデルが現在のモデル一覧に存在するかチェック
        if saved_model and saved_model in models:
            return saved_model
        else:
            # 存在しない場合は最初のモデルを返し、セッション状態を更新
            default_model = models[0]
            st.session_state[session_key] = default_model
            return default_model

    @classmethod
    def get_default_rag_config(cls) -> str:
        """デフォルトのRAG設定を取得"""
        return st.session_state.get("selected_rag_config", "general")

    @classmethod
    def get_default_prompt_style(cls) -> str:
        """デフォルトのプロンプトスタイルを取得"""
        try:
            # 循環インポート回避のため、必要時のみインポート
            from utils.prompt_manager import prompt_manager

            available_prompts = prompt_manager.get_available_prompts()

            # まず汎用プロンプトから'general'を探す
            if "generic" in available_prompts and "general" in available_prompts["generic"]:
                return "general"

            # 'general'がない場合は最初の汎用プロンプトを使用
            if "generic" in available_prompts and available_prompts["generic"]:
                return available_prompts["generic"][0]
        except Exception:
            # エラー時は安全なデフォルト値を返す
            pass

        # 何もない場合はフォールバック
        return "general"

    @classmethod
    def get_company_name(cls) -> str:
        """会社名を取得"""
        return st.session_state.get("company_name", "サンプル株式会社")

    @classmethod
    def get_api_key(cls, provider: str) -> Optional[str]:
        """指定プロバイダーのAPI Keyを取得"""
        env_var = cls.LLM_PROVIDERS[provider]["api_key_env"]

        # 1. Streamlit Secretsから取得
        try:
            return st.secrets.get(env_var)
        except:
            pass

        # 2. 環境変数から取得
        return os.getenv(env_var)

    @classmethod
    def get_model_config(cls, provider: str, model: str) -> LLMModelConfig:
        """指定モデルの設定を取得"""
        return cls.LLM_PROVIDERS[provider]["models"][model]

    @classmethod
    def get_rag_config(cls, config_name: str) -> RAGConfig:
        """指定RAG設定を取得"""
        return cls.RAG_SETTINGS[config_name]

    @classmethod
    def get_system_config(cls) -> SystemConfig:
        """システム設定を取得"""
        return cls.SYSTEM_CONFIG

    @classmethod
    def get_system_prompt(cls, style: str, **kwargs) -> str:
        """システムプロンプトを取得（互換性のため残存、新規実装はprompt_managerを使用）"""
        # 互換性のためのフォールバック
        from utils.prompt_manager import prompt_manager

        return prompt_manager.get_system_prompt(style, **kwargs)

    @classmethod
    def calculate_cost(cls, provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
        """API使用料金を計算"""
        model_config = cls.get_model_config(provider, model)
        input_cost = (input_tokens / 1000) * model_config.cost_per_1k_tokens_input
        output_cost = (output_tokens / 1000) * model_config.cost_per_1k_tokens_output
        return input_cost + output_cost

    @classmethod
    def get_available_providers(cls) -> Dict[str, str]:
        """利用可能なプロバイダーを取得（API Key設定済みのもの、優先順位順）"""
        # 優先順位に従って順序付け
        priority_order = ["openai", "anthropic", "google"]
        available = {}

        # 優先順位順に追加
        for provider_id in priority_order:
            if provider_id in cls.LLM_PROVIDERS and cls.get_api_key(provider_id):
                available[provider_id] = cls.LLM_PROVIDERS[provider_id]["name"]

        # 優先順位にない他のプロバイダーも追加
        for provider_id, provider_info in cls.LLM_PROVIDERS.items():
            if provider_id not in priority_order and cls.get_api_key(provider_id):
                available[provider_id] = provider_info["name"]

        return available

    @classmethod
    def validate_settings(cls) -> Dict[str, List[str]]:
        """設定の妥当性を検証"""
        issues = {"errors": [], "warnings": []}

        # API Key確認
        for provider_id, provider_info in cls.LLM_PROVIDERS.items():
            api_key = cls.get_api_key(provider_id)
            if not api_key:
                issues["warnings"].append(f"{provider_info['name']} API Key が設定されていません")

        # ファイルサイズ確認
        if cls.SYSTEM_CONFIG.max_file_size_mb > 100:
            issues["warnings"].append("ファイルサイズ制限が100MBを超えています")

        # チャンクサイズ確認
        for config_name, config in cls.RAG_SETTINGS.items():
            if config.chunk_overlap >= config.chunk_size:
                issues["errors"].append(f"RAG設定 '{config_name}': chunk_overlapがchunk_size以上になっています")

        return issues


# 設定インスタンス（シングルトンパターン）
settings = Settings()


# 便利な関数群
def get_current_llm_config():
    """現在選択されているLLM設定を取得"""
    provider = settings.get_default_provider()
    model = settings.get_default_model(provider)
    return provider, model, settings.get_model_config(provider, model)


def get_current_rag_config():
    """現在選択されているRAG設定を取得"""
    config_name = settings.get_default_rag_config()
    return config_name, settings.get_rag_config(config_name)


def update_session_settings(**kwargs):
    """セッション設定を更新"""
    for key, value in kwargs.items():
        st.session_state[key] = value
