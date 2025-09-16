"""マルチLLMプロバイダー管理システム。

このモジュールはOpenAI、Anthropic (Claude)、Google (Gemini)を含む
複数のLLMプロバイダーの統合管理を提供します。

主要機能:
- 複数LLMプロバイダーの統合管理
- 自動フェイルオーバー機能
- API Key管理とプロバイダー選択
- レスポンス形式の統一
- コスト・使用量の追跡

サポートプロバイダー:
- OpenAI (GPT-3.5, GPT-4シリーズ)
- Anthropic (Claude 3シリーズ)
- Google (Geminiシリーズ)

優先順位:
1. OpenAI（最優先、日本語対応良好）
2. Anthropic（高品質、長文処理得意）
3. Google（コスト効率良好）

使用例:
    manager = LLMManager()
    response = manager.generate_response([
        {"role": "user", "content": "こんにちは"}
    ])
"""

import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

# 設定ファイルのインポート
# 親ディレクトリのconfigモジュールにアクセスするためパスを追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import get_current_llm_config, settings


class LLMManager:
    """マルチLLMプロバイダー統合管理クラス。

    複数のLLMプロバイダー（OpenAI、Anthropic、Google）の統合管理を行い、
    統一されたインターフェースでLLM機能を提供します。

    主な責務:
    - プロバイダー別APIクライアントの初期化と管理
    - 優先順位に基づくプロバイダー自動選択
    - API呼び出しの統一化と結果の正規化
    - エラーハンドリングとフェイルオーバー
    - 使用量・コスト追跡

    Attributes:
        providers (Dict): 利用可能なLLMプロバイダーのAPIクライアント辞書
        current_provider (str): 現在選択中のプロバイダー名
        current_model (str): 現在選択中のモデル名
        current_config (LLMModelConfig): 現在のモデル設定オブジェクト

    設計パターン:
        シングルトンパターンで実装され、アプリケーション全体で
        同一のインスタンスが使用されます。
    """

    def __init__(self) -> None:
        """LLMマネージャーを初期化する。

        以下の初期化処理を順次実行:
        1. インスタンス変数の初期化
        2. 利用可能なプロバイダーの検出と初期化
        3. デフォルト設定の読み込み

        Note:
            API Keyが設定されていないプロバイダーは自動的にスキップされ、
            利用可能なプロバイダーのみが初期化されます。
        """
        # インスタンス変数の初期化
        self.providers = {}              # プロバイダー別APIクライアント格納辞書
        self.current_provider = None     # 現在選択中のプロバイダー名
        self.current_model = None        # 現在選択中のモデル名
        self.current_config = None       # 現在のモデル設定オブジェクト

        # 初期化処理の実行
        self._initialize_providers()     # プロバイダーの検出と初期化
        self._load_current_settings()    # デフォルト設定の読み込み

        # デバッグ情報をログ出力
        print(f"[LLMManager] 利用可能なプロバイダー: {list(self.providers.keys())}")
        print(f"[LLMManager] 現在のプロバイダー: {self.current_provider}")
        print(f"[LLMManager] 現在のモデル: {self.current_model}")

    def _initialize_providers(self):
        """利用可能なプロバイダーを初期化"""
        # OpenAI
        try:
            import openai
            api_key = settings.get_api_key("openai")
            print(f"[LLMManager] OpenAI API Key 確認: {'有り' if api_key else '無し'}")

            if api_key:
                self.providers["openai"] = self._create_openai_client()
                print(f"[LLMManager] OpenAI プロバイダー初期化成功")
        except ImportError as e:
            print(f"[LLMManager] OpenAI インポートエラー: {e}")
            st.warning("OpenAI パッケージがインストールされていません")
        except Exception as e:
            print(f"[LLMManager] OpenAI 初期化エラー: {e}")

        # Anthropic (Claude)
        try:
            import anthropic

            if settings.get_api_key("anthropic"):
                self.providers["anthropic"] = self._create_anthropic_client()
        except ImportError:
            pass  # オプショナル

        # Google (Gemini)
        try:
            import google.generativeai as genai

            if settings.get_api_key("google"):
                self.providers["google"] = self._create_google_client()
        except ImportError:
            pass  # オプショナル

    def _create_openai_client(self):
        """OpenAI クライアントを作成"""
        import openai

        client = openai.OpenAI(api_key=settings.get_api_key("openai"))
        return {"client": client, "type": "openai"}

    def _create_anthropic_client(self):
        """Anthropic クライアントを作成"""
        import anthropic

        client = anthropic.Anthropic(api_key=settings.get_api_key("anthropic"))
        return {"client": client, "type": "anthropic"}

    def _create_google_client(self):
        """Google クライアントを作成"""
        import google.generativeai as genai

        genai.configure(api_key=settings.get_api_key("google"))
        return {"client": genai, "type": "google"}

    def _load_current_settings(self):
        """現在の設定を読み込み（優先順位に従って自動選択）"""
        print(f"[LLMManager] 設定読み込み開始")

        # 設定から優先順位に従ってプロバイダーを取得
        default_provider = settings.get_default_provider()
        print(f"[LLMManager] デフォルトプロバイダー: {default_provider}")

        # デフォルトプロバイダーが利用可能かチェック
        if default_provider in self.providers:
            default_model = settings.get_default_model(default_provider)
            self.current_provider = default_provider
            self.current_model = default_model
            self.current_config = settings.get_model_config(default_provider, default_model)
            print(f"[LLMManager] デフォルトプロバイダー設定完了: {default_provider}/{default_model}")
        else:
            # フォールバック: 利用可能な最初のプロバイダーを使用
            if self.providers:
                first_provider = list(self.providers.keys())[0]
                first_model = settings.get_default_model(first_provider)
                self.current_provider = first_provider
                self.current_model = first_model
                self.current_config = settings.get_model_config(first_provider, first_model)
                print(f"[LLMManager] フォールバックプロバイダー設定: {first_provider}/{first_model}")
            else:
                # プロバイダーが利用できない場合の処理
                print(f"[LLMManager] 警告: 利用可能なプロバイダーがありません")
                try:
                    self.current_provider, self.current_model, self.current_config = get_current_llm_config()
                    print(f"[LLMManager] 緊急フォールバック設定: {self.current_provider}/{self.current_model}")
                except Exception as e:
                    print(f"[LLMManager] 緊急フォールバック失敗: {e}")
                    self.current_provider = None
                    self.current_model = None
                    self.current_config = None

    def get_available_providers(self) -> Dict[str, str]:
        """利用可能なプロバイダー一覧を取得（優先順位順）"""
        return settings.get_available_providers()

    def get_available_models(self, provider: str) -> Dict[str, str]:
        """指定プロバイダーの利用可能なモデル一覧を取得"""
        if provider not in settings.LLM_PROVIDERS:
            return {}

        models = {}
        for model_id, model_config in settings.LLM_PROVIDERS[provider]["models"].items():
            models[model_id] = model_config.name
        return models

    def set_current_provider(self, provider: str, model: str):
        """現在のプロバイダーとモデルを設定"""
        if provider in self.providers:
            self.current_provider = provider
            self.current_model = model
            self.current_config = settings.get_model_config(provider, model)

            # セッション状態を更新
            st.session_state["selected_provider"] = provider
            st.session_state[f"selected_model_{provider}"] = model
        else:
            raise ValueError(f"プロバイダー '{provider}' は利用できません")

    def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> Tuple[str, Dict[str, Any]]:
        """統合レスポンス生成"""
        print(f"[LLMManager] generate_response 呼び出し")
        print(f"[LLMManager] current_provider: {self.current_provider}")
        print(f"[LLMManager] 利用可能なプロバイダー: {list(self.providers.keys())}")

        if not self.current_provider:
            raise ValueError("プロバイダーが選択されていません。設定画面でLLMプロバイダーを選択してください。")

        if self.current_provider not in self.providers:
            available_providers = list(self.providers.keys())
            if available_providers:
                error_msg = f"プロバイダー '{self.current_provider}' が利用できません。利用可能: {available_providers}"
            else:
                error_msg = "利用可能なプロバイダーがありません。API Keyが正しく設定されているか確認してください。"
            raise ValueError(error_msg)

        # プロバイダー別の処理を実行
        try:
            if self.current_provider == "openai":
                return self._generate_openai_response(messages, **kwargs)
            elif self.current_provider == "anthropic":
                return self._generate_anthropic_response(messages, **kwargs)
            elif self.current_provider == "google":
                return self._generate_google_response(messages, **kwargs)
        except Exception as e:
            print(f"[LLMManager] {self.current_provider} レスポンス生成エラー: {e}")
            raise
        else:
            raise ValueError(f"未対応のプロバイダー: {self.current_provider}")

    def _generate_openai_response(self, messages: List[Dict[str, str]], **kwargs) -> Tuple[str, Dict[str, Any]]:
        """OpenAI レスポンス生成"""
        try:
            client = self.providers["openai"]["client"]

            # デフォルトパラメータを設定から取得
            params = {
                "model": self.current_model,
                "messages": messages,
                "max_tokens": kwargs.get("max_tokens", self.current_config.max_tokens),
                "temperature": kwargs.get("temperature", self.current_config.temperature),
                "top_p": kwargs.get("top_p", self.current_config.top_p),
                "frequency_penalty": kwargs.get("frequency_penalty", self.current_config.frequency_penalty),
                "presence_penalty": kwargs.get("presence_penalty", self.current_config.presence_penalty),
            }

            response = client.chat.completions.create(**params)

            # 使用情報を抽出
            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
                "cost": settings.calculate_cost(
                    self.current_provider,
                    self.current_model,
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                ),
            }

            return response.choices[0].message.content, usage

        except Exception as e:
            st.error(f"OpenAI API エラー: {str(e)}")
            return f"❌ OpenAI API エラーが発生しました: {str(e)}", {"error": str(e)}

    def _generate_anthropic_response(self, messages: List[Dict[str, str]], **kwargs) -> Tuple[str, Dict[str, Any]]:
        """Anthropic (Claude) レスポンス生成"""
        try:
            client = self.providers["anthropic"]["client"]

            # Anthropic形式にメッセージを変換
            anthropic_messages = []
            system_message = ""

            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    anthropic_messages.append({"role": msg["role"], "content": msg["content"]})

            params = {
                "model": self.current_model,
                "messages": anthropic_messages,
                "max_tokens": kwargs.get("max_tokens", self.current_config.max_tokens),
                "temperature": kwargs.get("temperature", self.current_config.temperature),
                "top_p": kwargs.get("top_p", self.current_config.top_p),
            }

            if system_message:
                params["system"] = system_message

            response = client.messages.create(**params)

            # 使用情報を抽出
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                "cost": settings.calculate_cost(
                    self.current_provider,
                    self.current_model,
                    response.usage.input_tokens,
                    response.usage.output_tokens,
                ),
            }

            return response.content[0].text, usage

        except Exception as e:
            st.error(f"Anthropic API エラー: {str(e)}")
            return f"❌ Anthropic API エラーが発生しました: {str(e)}", {"error": str(e)}

    def _generate_google_response(self, messages: List[Dict[str, str]], **kwargs) -> Tuple[str, Dict[str, Any]]:
        """Google (Gemini) レスポンス生成"""
        try:
            genai = self.providers["google"]["client"]

            # Google Gemini形式に変換
            model = genai.GenerativeModel(self.current_model)

            # メッセージをGemini形式に変換
            conversation_text = ""
            for msg in messages:
                if msg["role"] == "system":
                    conversation_text += f"System: {msg['content']}\n\n"
                elif msg["role"] == "user":
                    conversation_text += f"User: {msg['content']}\n\n"
                elif msg["role"] == "assistant":
                    conversation_text += f"Assistant: {msg['content']}\n\n"

            # 生成設定
            generation_config = {
                "temperature": kwargs.get("temperature", self.current_config.temperature),
                "top_p": kwargs.get("top_p", self.current_config.top_p),
                "max_output_tokens": kwargs.get("max_tokens", self.current_config.max_tokens),
            }

            response = model.generate_content(conversation_text, generation_config=generation_config)

            # 使用情報（Geminiは詳細な使用情報が限定的）
            usage = {
                "input_tokens": len(conversation_text) // 4,  # 概算
                "output_tokens": len(response.text) // 4,  # 概算
                "total_tokens": (len(conversation_text) + len(response.text)) // 4,
                "cost": settings.calculate_cost(
                    self.current_provider, self.current_model, len(conversation_text) // 4, len(response.text) // 4
                ),
            }

            return response.text, usage

        except Exception as e:
            st.error(f"Google API エラー: {str(e)}")
            return f"❌ Google API エラーが発生しました: {str(e)}", {"error": str(e)}

    def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """プロバイダーの状態を取得"""
        status = {}

        for provider_id, provider_info in settings.LLM_PROVIDERS.items():
            api_key = settings.get_api_key(provider_id)
            is_available = provider_id in self.providers

            # パッケージのインストール状況も個別確認
            package_installed = self._check_package_installed(provider_id)
            print(f"[LLMManager] {provider_id} - API Key: {'有り' if api_key else '無し'}, パッケージ: {'インストール済み' if package_installed else '未インストール'}, 利用可能: {is_available}")

            status[provider_id] = {
                "name": provider_info["name"],
                "api_key_configured": bool(api_key),
                "api_key_partial": api_key[-4:] if api_key else None,
                "available": is_available,
                "package_installed": package_installed,
                "models_count": len(provider_info["models"]),
                "current": provider_id == self.current_provider,
            }

        return status

    def _check_package_installed(self, provider_id: str) -> bool:
        """指定プロバイダーのパッケージがインストールされているかチェック"""
        try:
            if provider_id == "openai":
                import openai
                return True
            elif provider_id == "anthropic":
                import anthropic
                return True
            elif provider_id == "google":
                import google.generativeai as genai
                return True
        except ImportError:
            return False
        return False

    def estimate_cost(self, text_length: int, response_length: int = None) -> float:
        """コスト見積もり"""
        if not self.current_config:
            return 0.0

        # トークン数の概算 (1トークン ≈ 4文字)
        input_tokens = text_length // 4
        output_tokens = (response_length or text_length) // 4

        return settings.calculate_cost(self.current_provider, self.current_model, input_tokens, output_tokens)

    def get_model_info(self) -> Dict[str, Any]:
        """現在のモデル情報を取得"""
        if not self.current_config:
            return {}

        return {
            "provider": settings.LLM_PROVIDERS[self.current_provider]["name"],
            "model": self.current_config.name,
            "context_window": self.current_config.context_window,
            "max_tokens": self.current_config.max_tokens,
            "cost_per_1k_input": self.current_config.cost_per_1k_tokens_input,
            "cost_per_1k_output": self.current_config.cost_per_1k_tokens_output,
            "supports_function_calling": getattr(self.current_config, "supports_function_calling", False),
        }


# グローバルインスタンス
llm_manager = LLMManager()
