"""システム設定管理画面モジュール。

このモジュールは、WikiチャットボットアプリケーションのStreamlitベース
設定管理インターフェースを提供します。LLMプロバイダー、RAG設定、
プロンプト設定、システム設定、API Key管理を統合的に管理できる
包括的な設定画面を実装しています。

主要機能:
    1. LLMプロバイダー設定:
        - 利用可能なプロバイダーの状態表示
        - プロバイダー・モデルの選択と変更
        - 現在のモデル情報の詳細表示
        - コスト情報の確認

    2. RAG（検索）設定:
        - プリセット設定の選択・適用
        - カスタム設定の詳細調整
        - 設定変更前後の比較表示
        - 文書タイプ別最適化

    3. プロンプト設定:
        - 用途別プロンプトスタイルの選択
        - プロンプトのプレビュー機能
        - 動的なプロンプト変更

    4. システム設定:
        - アプリケーション基本設定の確認
        - ファイル処理設定の表示
        - デバッグ・ログ設定の管理

    5. API Key管理:
        - プロバイダー別API Key設定状況の確認
        - 設定方法のガイダンス表示
        - 外部リンクによる取得支援

技術仕様:
    - StreamlitのタブUIによる機能分割
    - 動的な設定検証機能
    - リアルタイム設定反映
    - エラーハンドリング付きの安全な設定変更

設計思想:
    運用担当者が直感的に操作できるUI設計を重視し、
    技術的な詳細を隠蔽しつつ、必要な情報は確実に提供する
    バランスの取れたインターフェースを目指しています。

使用例:
    このモジュールはStreamlitページとして動作し、
    ブラウザから直接アクセスして使用します:
    ```
    streamlit run pages/settings.py
    ```
"""

import streamlit as st
import sys
import os
import json
from typing import Dict, Any

# パスを追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings, update_session_settings
from utils.session_manager import SessionManager
from utils.llm_manager import llm_manager


def show_llm_settings():
    """LLM設定画面を表示する。

    利用可能なLLMプロバイダーの状態確認から、プロバイダー・モデルの選択、
    詳細情報の表示までを統合的に管理する画面を表示します。

    画面構成:
        1. プロバイダー状態表示:
            - 利用可能性（API Key設定状況）
            - 現在の選択状況
            - API Keyの設定確認

        2. 現在のモデル情報:
            - 選択中のプロバイダー・モデル
            - コスト情報（入力・出力単価）
            - コンテキスト窓・最大トークン数

        3. プロバイダー・モデル選択:
            - 利用可能プロバイダーからの選択
            - 選択プロバイダー内のモデル選択
            - 設定の即時適用

        4. 選択モデルの詳細情報:
            - パフォーマンス指標
            - コスト詳細
            - 技術仕様

    機能:
        - 優先順位に従った自動プロバイダー選択
        - リアルタイム設定変更
        - エラーハンドリング付きの安全な設定更新
    """
    st.header("🤖 LLM プロバイダー設定")

    # プロバイダー状態の表示
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("利用可能プロバイダー")
        provider_status = llm_manager.get_provider_status()

        # プロバイダーごとの状態表示（詳細な状態管理）
        for provider_id, status in provider_status.items():
            with st.container():
                col_name, col_status, col_key = st.columns([2, 1, 2])

                with col_name:
                    # 状態に応じたアイコン表示
                    icon = "✅" if status["available"] else "⚠️" if status["api_key_configured"] else "❌"
                    current_mark = " 🔹 **使用中**" if status["current"] else ""
                    st.write(f"{icon} **{status['name']}**{current_mark}")

                with col_status:
                    # 利用可能性の詳細状態表示
                    if status["available"]:
                        st.success("利用可能")
                    elif status["api_key_configured"]:
                        # パッケージインストール状況も表示
                        if status.get("package_installed", False):
                            st.warning("設定エラー")  # パッケージはあるがプロバイダー初期化失敗
                        else:
                            st.warning("未インストール")  # パッケージ未インストール
                    else:
                        st.error("未設定")  # API Key未設定

                with col_key:
                    # API Key設定状況の表示（セキュリティのため末尾4文字のみ）
                    if status["api_key_configured"]:
                        st.write(f"🔑 ...{status['api_key_partial']}")
                    else:
                        st.write("🔑 未設定")

    with col2:
        st.subheader("現在のモデル情報")
        # LLMマネージャーを再初期化して最新の設定を反映
        llm_manager._load_current_settings()
        model_info = llm_manager.get_model_info()

        if model_info:
            # model_infoの'provider'キーは既に表示名が入っている
            st.write(f"**プロバイダー**: {model_info.get('provider', 'N/A')}")
            st.write(f"**モデル**: {model_info.get('model', 'N/A')}")
            st.write(f"**最大トークン**: {model_info.get('max_tokens', 'N/A'):,}" if isinstance(model_info.get('max_tokens'), (int, float)) else f"**最大トークン**: {model_info.get('max_tokens', 'N/A')}")
            st.write(f"**コンテキスト**: {model_info.get('context_window', 'N/A'):,}" if isinstance(model_info.get('context_window'), (int, float)) else f"**コンテキスト**: {model_info.get('context_window', 'N/A')}")
            st.write(f"**入力単価**: ${model_info.get('cost_per_1k_input', 0):.4f}/1K")
            st.write(f"**出力単価**: ${model_info.get('cost_per_1k_output', 0):.4f}/1K")

            # 優先順位に従って選択されたプロバイダーの表示
            default_provider = settings.get_default_provider()
            current_provider_id = llm_manager.current_provider
            if current_provider_id == default_provider:
                provider_display_name = model_info.get('provider', 'N/A')
                st.success(f"✅ 優先順位に従って {provider_display_name} が選択されています")
        else:
            st.info("利用可能なプロバイダーがありません。API Keyを設定してください。")

    st.divider()

    # プロバイダー・モデル選択
    st.subheader("プロバイダー・モデル選択")

    available_providers = llm_manager.get_available_providers()
    if not available_providers:
        st.error("利用可能なプロバイダーがありません。API Keyを設定してください。")
        return

    col1, col2 = st.columns(2)

    with col1:
        selected_provider = st.selectbox(
            "プロバイダーを選択",
            options=list(available_providers.keys()),
            format_func=lambda x: available_providers[x],
            index=(
                list(available_providers.keys()).index(llm_manager.current_provider)
                if llm_manager.current_provider in available_providers
                else 0
            ),
            key="provider_selector",
        )

    with col2:
        available_models = llm_manager.get_available_models(selected_provider)
        selected_model = st.selectbox(
            "モデルを選択",
            options=list(available_models.keys()),
            format_func=lambda x: available_models[x],
            index=(
                list(available_models.keys()).index(llm_manager.current_model)
                if llm_manager.current_model in available_models
                else 0
            ),
            key="model_selector",
        )

    # 設定変更ボタン
    col1, col2 = st.columns([2, 1])

    with col1:
        if st.button("設定を適用", type="primary"):
            try:
                llm_manager.set_current_provider(selected_provider, selected_model)
                st.success(
                    f"✅ {available_providers[selected_provider]} - {available_models[selected_model]} に変更しました"
                )
                st.rerun()
            except Exception as e:
                st.error(f"設定変更エラー: {str(e)}")

    with col2:
        if st.button("🔄 設定リセット", help="古いモデル名などの問題を解決します"):
            # 古いセッション状態をクリア
            keys_to_clear = []
            for key in st.session_state.keys():
                if key.startswith(('selected_model_', 'selected_provider')):
                    keys_to_clear.append(key)

            for key in keys_to_clear:
                del st.session_state[key]

            st.success("✅ 設定をリセットしました。ページを再読み込みしてください。")
            st.rerun()

    # モデル詳細情報
    if selected_provider and selected_model:
        st.subheader("選択モデルの詳細")
        model_config = settings.get_model_config(selected_provider, selected_model)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("最大トークン", f"{model_config.max_tokens:,}")
            st.metric("Temperature", model_config.temperature)
        with col2:
            st.metric("入力コスト/1K", f"${model_config.cost_per_1k_tokens_input:.4f}")
            st.metric("出力コスト/1K", f"${model_config.cost_per_1k_tokens_output:.4f}")
        with col3:
            st.metric("コンテキスト", f"{model_config.context_window:,}")
            st.metric("Top P", model_config.top_p)


def show_rag_settings():
    """RAG設定画面"""
    st.header("🔍 RAG (検索) 設定")

    # 現在の設定表示
    current_rag_config_name = settings.get_default_rag_config()
    current_rag_config = settings.get_rag_config(current_rag_config_name)

    st.subheader("現在のRAG設定")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("チャンクサイズ", current_rag_config.chunk_size)
        st.metric("オーバーラップ", current_rag_config.chunk_overlap)
    with col2:
        st.metric("検索結果数", current_rag_config.search_top_k)
        st.metric("類似度閾値", current_rag_config.similarity_threshold)
    with col3:
        st.metric("埋め込みモデル", current_rag_config.embedding_model.split("-")[-1].upper())
        st.metric("ベクトルDB", current_rag_config.vector_store_type.upper())

    st.divider()

    # プリセット選択
    st.subheader("RAG設定プリセット")

    preset_descriptions = {
        "general": "汎用設定 - バランスの取れた標準設定",
        "short_docs": "短文書用 - 商品紹介、FAQ等の短い文書に最適",
        "long_docs": "長文書用 - マニュアル、仕様書等の長い文書に最適",
        "technical": "技術文書用 - 技術仕様、設計書等の詳細文書に最適",
    }

    col1, col2 = st.columns([2, 1])

    with col1:
        selected_preset = st.selectbox(
            "プリセットを選択",
            options=list(settings.RAG_SETTINGS.keys()),
            format_func=lambda x: f"{x.replace('_', ' ').title()} - {preset_descriptions[x]}",
            index=list(settings.RAG_SETTINGS.keys()).index(current_rag_config_name),
            key="rag_preset_selector",
        )

    with col2:
        if st.button("プリセットを適用", type="primary"):
            update_session_settings(selected_rag_config=selected_preset)
            st.success(f"✅ RAG設定を '{selected_preset}' に変更しました")
            st.rerun()

    # 選択中プリセットの詳細
    if selected_preset:
        st.subheader("選択プリセットの詳細")
        preset_config = settings.get_rag_config(selected_preset)

        # 設定値を表形式で表示
        config_data = {
            "設定項目": ["チャンクサイズ", "チャンクオーバーラップ", "検索結果数", "類似度閾値", "埋め込みモデル"],
            "現在値": [
                current_rag_config.chunk_size,
                current_rag_config.chunk_overlap,
                current_rag_config.search_top_k,
                current_rag_config.similarity_threshold,
                current_rag_config.embedding_model,
            ],
            "変更後": [
                preset_config.chunk_size,
                preset_config.chunk_overlap,
                preset_config.search_top_k,
                preset_config.similarity_threshold,
                preset_config.embedding_model,
            ],
        }

        st.table(config_data)

    st.divider()

    # カスタム設定
    with st.expander("🔧 カスタム設定 (上級者向け)", expanded=False):
        st.warning("⚠️ これらの設定を変更すると検索精度に影響する可能性があります")

        col1, col2 = st.columns(2)
        with col1:
            custom_chunk_size = st.number_input(
                "チャンクサイズ",
                min_value=100,
                max_value=4000,
                value=current_rag_config.chunk_size,
                step=50,
                help="文書を分割する際の1チャンクあたりの文字数",
            )

            custom_chunk_overlap = st.number_input(
                "チャンクオーバーラップ",
                min_value=0,
                max_value=custom_chunk_size // 2,
                value=current_rag_config.chunk_overlap,
                step=10,
                help="隣接チャンク間で重複させる文字数",
            )

        with col2:
            custom_top_k = st.number_input(
                "検索結果数",
                min_value=1,
                max_value=20,
                value=current_rag_config.search_top_k,
                help="検索時に取得する関連文書の数",
            )

            custom_threshold = st.number_input(
                "類似度閾値",
                min_value=0.0,
                max_value=1.0,
                value=current_rag_config.similarity_threshold,
                step=0.05,
                help="検索結果に含める最低類似度",
            )

        if st.button("カスタム設定を適用"):
            # カスタム設定を一時的にセッションに保存
            st.session_state["custom_rag_config"] = {
                "chunk_size": custom_chunk_size,
                "chunk_overlap": custom_chunk_overlap,
                "search_top_k": custom_top_k,
                "similarity_threshold": custom_threshold,
            }
            st.success("✅ カスタム設定を適用しました")


def show_prompt_settings():
    """プロンプト設定画面"""
    st.header("💬 プロンプト設定")

    current_style = settings.get_default_prompt_style()

    # プロンプトスタイル選択
    style_descriptions = {
        "general": "汎用 - 一般的な問い合わせに対応",
        "business": "営業支援 - 営業担当者向けの実践的な情報提供",
        "technical": "技術サポート - エンジニア向けの技術的な回答",
        "compliance": "コンプライアンス - 法的・規制的観点を重視した慎重な回答",
    }

    # プロンプトマネージャーから利用可能なプロンプトを取得
    try:
        from utils.prompt_manager import prompt_manager
        available_prompts = prompt_manager.get_available_prompts()
        generic_prompts = available_prompts.get("generic", [])
        
        # フォールバック用にSYSTEM_PROMPTSからも取得
        if not generic_prompts:
            generic_prompts = list(settings.SYSTEM_PROMPTS.keys())
    except Exception:
        # エラー時はSYSTEM_PROMPTSを使用
        generic_prompts = list(settings.SYSTEM_PROMPTS.keys())

    col1, col2 = st.columns([2, 1])

    with col1:
        # current_styleが利用可能なプロンプト一覧にない場合のデフォルト処理
        if current_style not in generic_prompts and generic_prompts:
            current_style = generic_prompts[0]
            
        selected_style = st.selectbox(
            "プロンプトスタイルを選択",
            options=generic_prompts,
            format_func=lambda x: style_descriptions.get(x, x),
            index=generic_prompts.index(current_style) if current_style in generic_prompts else 0,
            key="prompt_style_selector",
        )

    with col2:
        if st.button("スタイルを適用", type="primary"):
            update_session_settings(selected_prompt_style=selected_style)
            st.success(f"✅ プロンプトスタイルを '{selected_style}' に変更しました")
            st.rerun()

    # 選択中スタイルのプレビュー
    if selected_style:
        st.subheader("プロンプトプレビュー")
        preview_prompt = settings.get_system_prompt(
            selected_style,
            product_name="商品A",
            company_name="ABC商事",
            context_text="[検索された文書内容がここに表示されます]",
        )

        st.code(preview_prompt, language="text")


def show_system_settings():
    """システム設定画面"""
    st.header("⚙️ システム設定")

    system_config = settings.get_system_config()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("アプリ設定")
        st.text_input("アプリタイトル", value=system_config.app_title, disabled=True)
        st.text_input("アプリアイコン", value=system_config.app_icon, disabled=True)
        st.number_input("ファイルサイズ制限 (MB)", value=system_config.max_file_size_mb, disabled=True)
        st.multiselect(
            "対応ファイル形式",
            options=system_config.supported_file_types,
            default=system_config.supported_file_types,
            disabled=True,
        )

    with col2:
        st.subheader("システム情報")
        st.text_input("ログレベル", value=system_config.log_level, disabled=True)
        st.checkbox("デバッグモード", value=system_config.enable_debug_mode, disabled=True)
        st.number_input("セッションタイムアウト (分)", value=system_config.session_timeout_minutes, disabled=True)

    st.info("💡 システム設定を変更するには、`config/settings.py` ファイルを編集してください。")


def show_api_keys_setup():
    """API Key設定画面"""
    st.header("🔑 API Key 設定")

    st.warning("⚠️ API Keyは機密情報です。他者と共有しないでください。")

    # 各プロバイダーのAPI Key設定
    for provider_id, provider_info in settings.LLM_PROVIDERS.items():
        st.subheader(f"{provider_info['name']} API Key")

        env_var = provider_info["api_key_env"]
        current_key = settings.get_api_key(provider_id)

        col1, col2 = st.columns([3, 1])

        with col1:
            if current_key:
                st.success(f"✅ 設定済み (...{current_key[-4:]})")
                st.info(f"環境変数 `{env_var}` または `.streamlit/secrets.toml` に設定されています")
            else:
                st.error("❌ 未設定")
                st.code(
                    f"""
# 設定方法1: 環境変数
export {env_var}="your-api-key-here"

# 設定方法2: .streamlit/secrets.toml
{env_var} = "your-api-key-here"
                """
                )

        with col2:
            if provider_id == "openai":
                st.link_button("取得", "https://platform.openai.com/api-keys")
            elif provider_id == "anthropic":
                st.link_button("取得", "https://console.anthropic.com/")
            elif provider_id == "google":
                st.link_button("取得", "https://ai.google.dev/")


def main():
    # セッション管理初期化
    SessionManager.initialize_session()

    # 認証チェック
    if not SessionManager.check_authentication():
        if not SessionManager.authenticate_user():
            return

    # 遅延バックアップのチェック（設定画面でも実行）
    try:
        from utils.feedback_manager import feedback_manager
        feedback_manager._check_delayed_backup()
    except Exception as e:
        if st.secrets.get("DEBUG_MODE", False):
            st.warning(f"遅延バックアップチェックエラー: {e}")

    """設定画面メイン"""
    st.set_page_config(page_title="設定 - Wiki Chatbot", page_icon="⚙️", layout="wide")

    st.title("⚙️ システム設定")

    # タブで設定項目を分割
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🤖 LLM設定", "🔍 RAG設定", "💬 プロンプト", "⚙️ システム", "🔑 API Keys"])

    with tab1:
        show_llm_settings()

    with tab2:
        show_rag_settings()

    with tab3:
        show_prompt_settings()

    with tab4:
        show_system_settings()

    with tab5:
        show_api_keys_setup()

    # 設定検証
    st.divider()
    if st.button("🔍 設定を検証"):
        issues = settings.validate_settings()

        if issues["errors"]:
            st.error("❌ エラーが見つかりました:")
            for error in issues["errors"]:
                st.error(f"• {error}")

        if issues["warnings"]:
            st.warning("⚠️ 警告:")
            for warning in issues["warnings"]:
                st.warning(f"• {warning}")

        if not issues["errors"] and not issues["warnings"]:
            st.success("✅ すべての設定が正常です!")


if __name__ == "__main__":
    main()
