import streamlit as st
from typing import List, Dict, Any, Optional
import sys
import os

# パスを追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings, get_current_rag_config
from utils.rag_manager import RAGManager
from utils.enhanced_rag_manager import enhanced_rag_manager
from utils.llm_manager import llm_manager
from utils.prompt_manager import prompt_manager
from utils.feedback_manager import feedback_manager


class WikiChatbot:
    def __init__(self):
        self.rag_manager = RAGManager()
        self.enhanced_rag_manager = enhanced_rag_manager
        self.llm_manager = llm_manager
        self.cost_tracker = {"total_cost": 0.0, "session_queries": 0}

    def generate_response(self, query: str, context: List[Dict[str, Any]], product_name: str) -> str:
        # 利用可能なプロバイダーをチェック
        available_providers = self.llm_manager.get_available_providers()
        if not available_providers:
            return "⚠️ 利用可能なLLMプロバイダーがありません。設定画面でAPI Keyを設定してください。"

        try:
            # コンテキストを整理
            context_text = ""
            sources = []

            # デバッグ情報表示（検索結果の関連度確認）
            if st.secrets.get("DEBUG_MODE", False):
                st.write("🔍 **RAG検索結果の関連度確認**")
                for i, item in enumerate(context):
                    similarity = item.get('similarity_score', 'N/A')
                    distance = item.get('distance', 'N/A')
                    st.write(f"結果{i+1}: 類似度={similarity:.4f}, 距離={distance:.4f}")
                    st.write(f"内容: {item['content'][:100]}...")
                    if i >= 2:  # 上位3件まで表示
                        break
                st.divider()

            for i, item in enumerate(context, 1):
                context_text += f"[情報源 {i}]\n{item['content']}\n\n"
                if "metadata" in item and "file_name" in item["metadata"]:
                    sources.append(item["metadata"]["file_name"])

            # プロンプトスタイルを取得（セッション状態から）
            prompt_style = st.session_state.get(f"prompt_style_{product_name}", settings.get_default_prompt_style())
            system_prompt = prompt_manager.get_system_prompt(
                prompt_style,
                product_name=product_name,
                company_name=settings.get_company_name(),
                context_text=context_text,
            )

            # メッセージ形式を構築（会話履歴を含む）
            messages = [{"role": "system", "content": system_prompt}]

            # 過去の会話履歴を追加（最新5回まで）
            chat_history = st.session_state.get(f"messages_{product_name}", [])
            recent_history = chat_history[-10:]  # 最新5往復（10メッセージ）を取得

            for msg in recent_history:
                if msg["role"] == "user":
                    messages.append({"role": "user", "content": msg["content"]})
                elif msg["role"] == "assistant":
                    # アシスタントメッセージから参考情報源部分を除去
                    clean_content = msg["content"].split("---\n### 📚 参考にした情報源")[0].strip()
                    messages.append({"role": "assistant", "content": clean_content})

            # 現在の質問を追加
            messages.append({"role": "user", "content": query})

            # LLM APIを呼び出し
            response_text, usage_info = self.llm_manager.generate_response(messages)

            # コスト追跡
            if "cost" in usage_info:
                self.cost_tracker["total_cost"] += usage_info["cost"]
                self.cost_tracker["session_queries"] += 1

            # 情報源を追加（詳細版）
            if sources:
                unique_sources = list(set(sources))
                source_text = "\n\n---\n### 📚 参考にした情報源\n"

                # 各ソースファイルの詳細情報を追加
                source_details = []
                for i, item in enumerate(context, 1):
                    if "metadata" in item and "file_name" in item["metadata"]:
                        file_name = item["metadata"]["file_name"]
                        metadata = item["metadata"]

                        # 重複チェック
                        if file_name not in [detail["file"] for detail in source_details]:
                            detail = {
                                "file": file_name,
                                "content_preview": (
                                    item["content"][:150] + "..." if len(item["content"]) > 150 else item["content"]
                                ),
                                "reference": metadata.get("reference", ""),  # 参照データを取得
                                "type": metadata.get("type", "document"),
                                "question": metadata.get("question", ""),
                                "answer": metadata.get("answer", ""),
                                "chunk_index": metadata.get("chunk_index", ""),
                                "similarity_score": item.get("similarity_score", 0.0),
                            }
                            source_details.append(detail)

                # ソース情報をフォーマット
                for i, detail in enumerate(source_details, 1):
                    source_text += f"\n**{i}. {detail['file']}**\n"

                    # Q&Aペアの場合は特別な表示
                    if detail['type'] == 'qa_pair' and detail['question'] and detail['answer']:
                        source_text += f"**Q:** {detail['question']}\n"
                        source_text += f"**A:** {detail['answer']}\n"

                        # 参照データがある場合は表示
                        if detail['reference']:
                            # URLっぽい場合はリンク形式、そうでなければプレーンテキスト
                            if detail['reference'].startswith(('http://', 'https://')):
                                source_text += f"**📖 参照:** [{detail['reference']}]({detail['reference']})\n"
                            else:
                                source_text += f"**📖 参照:** {detail['reference']}\n"
                    else:
                        # 通常の文書の場合
                        file_name = detail['file']
                        file_extension = file_name.split('.')[-1].upper() if '.' in file_name else 'FILE'

                        # ファイル形式に応じたアイコン
                        file_icon = {
                            'PDF': '📄', 'TXT': '📝', 'DOCX': '📄', 'DOC': '📄',
                            'PPTX': '📊', 'PPT': '📊', 'HTML': '🌐', 'MD': '📝'
                        }.get(file_extension, '📄')

                        source_text += f"**{file_icon} ファイル形式:** {file_extension}\n"

                        # 類似度スコアがある場合は表示
                        if detail.get('similarity_score', 0) > 0:
                            similarity_percent = detail['similarity_score'] * 100
                            source_text += f"**🎯 関連度:** {similarity_percent:.1f}%\n"

                        # チャンク情報がある場合は表示
                        if detail.get('chunk_index', '') != '':
                            source_text += f"**📍 文書内位置:** セクション{detail['chunk_index'] + 1}\n"

                        source_text += f"**📖 参照内容:**\n"
                        source_text += f"```\n{detail['content_preview']}\n```\n"

                response_text += source_text

            # 使用情報をサイドバーに表示
            self._display_usage_info(usage_info)

            return response_text

        except Exception as e:
            return f"❌ 回答生成中にエラーが発生しました: {str(e)}"

    def chat_interface(self, product_name: str):
        st.title(f"💬 {product_name} Wiki チャット")

        # ログイン情報からユーザー名を取得
        user_name = self._get_current_user_info()

        # プロンプトスタイル選択UI
        self._show_prompt_style_selector(product_name)

        # チャット履歴の初期化
        if f"messages_{product_name}" not in st.session_state:
            st.session_state[f"messages_{product_name}"] = []

        # チャット履歴の表示
        for i, message in enumerate(st.session_state[f"messages_{product_name}"]):
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

                # アシスタントメッセージの場合、参考ファイル情報があれば表示
                if message["role"] == "assistant" and "source_files" in message and message["source_files"]:

                    with st.expander(f"📚 この回答の参考ファイル ({len(message['source_files'])}件)", expanded=False):
                        for j, source in enumerate(message["source_files"], 1):
                            st.write(f"**{j}. {source['file_name']}** (関連度: {source['score']:.3f})")
                            st.caption(source["preview"])
                            if j < len(message["source_files"]):
                                st.divider()

        # 会話継続のヒント表示
        if len(st.session_state[f"messages_{product_name}"]) > 0:
            st.info(
                "💡 **追加質問のコツ**: 「先ほどの回答について詳しく教えて」「他に何かありますか」など、前の会話を踏まえた質問もできます。"
            )

        # ユーザー入力
        if prompt := st.chat_input(f"{product_name}について何でもお聞きください（追加質問も可能）"):
            # ユーザーメッセージを追加
            st.session_state[f"messages_{product_name}"].append({"role": "user", "content": prompt})

            with st.chat_message("user"):
                st.markdown(prompt)

            # アシスタントの回答を生成
            with st.chat_message("assistant"):
                with st.spinner("回答を生成中..."):
                    # 拡張RAG検索を使用
                    try:
                        search_results = self.enhanced_rag_manager.enhanced_search(
                            product_name, prompt, top_k=5, use_query_expansion=True, use_result_ranking=True
                        )
                    except Exception as e:
                        # フォールバックで基本RAGを使用
                        st.warning("拡張RAG機能でエラーが発生しました。基本機能を使用します。")
                        search_results = self.rag_manager.search(product_name, prompt, top_k=5)

                    if not search_results:
                        response = f"申し訳ございませんが、{product_name}に関する情報が見つかりませんでした。管理画面から関連文書を追加してください。"
                    else:
                        # 回答生成
                        response = self.generate_response(prompt, search_results, product_name)

                    st.markdown(response)

                    # 参考ファイル詳細の表示
                    if search_results:
                        with st.expander("📋 参考ファイルの詳細を確認", expanded=False):
                            st.subheader("🔍 検索結果と参考ファイル")

                            # ファイルごとにグループ化
                            files_grouped = {}
                            for i, result in enumerate(search_results, 1):
                                file_name = result.get("metadata", {}).get("file_name", f"不明なファイル{i}")
                                if file_name not in files_grouped:
                                    files_grouped[file_name] = []
                                files_grouped[file_name].append(
                                    {
                                        "index": i,
                                        "content": result["content"],
                                        "score": result.get("distance", "N/A"),
                                        "metadata": result.get("metadata", {}),
                                    }
                                )

                            # ファイルごとに表示
                            for file_name, results in files_grouped.items():
                                with st.expander(f"📄 {file_name} ({len(results)}箇所)"):
                                    for result in results:
                                        st.markdown(
                                            f"**検索結果 {result['index']} (関連度スコア: {result['score']:.3f})**"
                                        )
                                        st.text_area(
                                            "内容:",
                                            result["content"],
                                            height=100,
                                            key=f"content_{result['index']}_{file_name}",
                                            disabled=True,
                                        )

                                        # メタデータがある場合は表示
                                        if result["metadata"]:
                                            with st.expander("📊 詳細情報", expanded=False):
                                                col1, col2 = st.columns(2)

                                                with col1:
                                                    st.write("**ファイル情報:**")
                                                    if "file_name" in result["metadata"]:
                                                        st.write(f"• ファイル名: {result['metadata']['file_name']}")
                                                    if "file_size" in result["metadata"]:
                                                        st.write(
                                                            f"• ファイルサイズ: {result['metadata']['file_size']}"
                                                        )
                                                    if "created_at" in result["metadata"]:
                                                        st.write(f"• 作成日時: {result['metadata']['created_at']}")

                                                with col2:
                                                    st.write("**検索情報:**")
                                                    if "original_query" in result["metadata"]:
                                                        st.write(f"• 元の質問: {result['metadata']['original_query']}")
                                                    if "expanded_query" in result["metadata"]:
                                                        st.write(
                                                            f"• 拡張クエリ: {result['metadata']['expanded_query']}"
                                                        )
                                                    if "search_method" in result["metadata"]:
                                                        st.write(f"• 検索方法: {result['metadata']['search_method']}")

                                                # その他のメタデータ
                                                other_metadata = {
                                                    k: v
                                                    for k, v in result["metadata"].items()
                                                    if k
                                                    not in [
                                                        "file_name",
                                                        "file_size",
                                                        "created_at",
                                                        "original_query",
                                                        "expanded_query",
                                                        "search_method",
                                                    ]
                                                }
                                                if other_metadata:
                                                    st.write("**その他の情報:**")
                                                    for key, value in other_metadata.items():
                                                        st.write(f"• {key}: {value}")
                                        st.divider()

            # アシスタントメッセージを追加（参考ファイル情報も保存）
            message_data = {"role": "assistant", "content": response}

            # 検索結果情報を保存（後から参照用）
            if search_results:
                source_files = []
                for result in search_results:
                    if "metadata" in result and "file_name" in result["metadata"]:
                        source_info = {
                            "file_name": result["metadata"]["file_name"],
                            "score": result.get("distance", "N/A"),
                            "preview": (
                                result["content"][:100] + "..." if len(result["content"]) > 100 else result["content"]
                            ),
                        }
                        # 重複チェック
                        if not any(sf["file_name"] == source_info["file_name"] for sf in source_files):
                            source_files.append(source_info)

                message_data["source_files"] = source_files
                message_data["search_metadata"] = {
                    "query": prompt,
                    "results_count": len(search_results),
                    "search_method": "enhanced_rag",
                }

            st.session_state[f"messages_{product_name}"].append(message_data)

            # チャット履歴をCSVに保存
            sources_list = []
            if search_results:
                for result in search_results:
                    if "metadata" in result and "file_name" in result["metadata"]:
                        sources_list.append(result["metadata"]["file_name"])

            # 現在のプロンプトスタイルを取得
            current_prompt_style = st.session_state.get(
                f"prompt_style_{product_name}", settings.get_default_prompt_style()
            )

            # チャット履歴を保存
            user_name = self._get_current_user_info()
            feedback_manager.save_chat_message(
                product_name=product_name,
                user_message=prompt,
                bot_response=response,
                sources_used=list(set(sources_list)),  # 重複除去
                prompt_style=current_prompt_style,
                user_name=user_name,
            )

        # 満足度調査を表示（会話がある程度進んだ場合）
        current_prompt_style = st.session_state.get(
            f"prompt_style_{product_name}", settings.get_default_prompt_style()
        )
        feedback_manager.show_satisfaction_survey(product_name, current_prompt_style)

    def product_selection_interface(self):
        st.title("🏢 社内Wiki検索チャットボット")
        st.write("問い合わせしたい商材を選択してください")

        # 利用可能な商材を取得
        products = self.rag_manager.list_products()

        if not products:
            st.warning("⚠️ 利用可能な商材がありません。管理画面から文書を追加してください。")
            st.info("👈 サイドバーの「管理画面」から文書を追加できます。")
            return None

        # 商材選択
        selected_product = st.selectbox("商材を選択してください:", products, key="product_selection")

        if selected_product:
            # 選択された商材の文書数を表示
            documents = self.rag_manager.list_documents(selected_product)
            st.info(f"📚 {selected_product}: {len(documents)}個の文書が登録されています")

            if st.button(f"💬 {selected_product} のチャットを開始"):
                st.session_state["selected_product"] = selected_product
                st.rerun()

        return selected_product

    def clear_chat_history(self, product_name: str):
        messages_count = len(st.session_state.get(f"messages_{product_name}", []))

        # チャット履歴クリア機能
        if messages_count > 0:
            if st.button(f"🗑️ {product_name} のチャット履歴をクリア", key=f"clear_{product_name}"):
                if f"messages_{product_name}" in st.session_state:
                    del st.session_state[f"messages_{product_name}"]
                    # セッション関連の状態もクリア
                    if f"feedback_given_{product_name}" in st.session_state:
                        del st.session_state[f"feedback_given_{product_name}"]
                    st.success("✅ チャット履歴をクリアしました\n💡 次回からは新しい会話として開始されます")
                    st.rerun()

        # 会話継続機能の説明
        if messages_count > 0:
            st.write(f"💬 **現在の会話**: {messages_count}件のメッセージ")
            st.caption("🔗 会話の記憶機能により、前の質問を踏まえた追加質問が可能です")

            # フィードバック統計の表示
            feedback_summary = feedback_manager.get_feedback_summary(product_name)
            if feedback_summary and feedback_summary.get("total_sessions", 0) > 0:
                with st.expander("📊 過去のフィードバック統計", expanded=False):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("総セッション数", feedback_summary.get("total_sessions", 0))
                    with col2:
                        st.metric("満足度", f"{feedback_summary.get('satisfaction_rate', 0):.1f}%")
                    with col3:
                        st.metric("平均メッセージ数", f"{feedback_summary.get('avg_messages_per_session', 0):.1f}")

    def _display_usage_info(self, usage_info: Dict[str, Any]):
        """使用情報をサイドバーに表示"""
        if "cost" in usage_info:
            st.sidebar.markdown("---")
            st.sidebar.subheader("💰 使用状況")
            st.sidebar.metric("今回のコスト", f"${usage_info['cost']:.4f}")
            st.sidebar.metric("セッション合計", f"${self.cost_tracker['total_cost']:.4f}")
            st.sidebar.metric("質問回数", self.cost_tracker["session_queries"])

            # 現在のモデル情報を表示
            model_info = self.llm_manager.get_model_info()
            if model_info:
                st.sidebar.write(f"**現在のモデル**: {model_info['model']}")
                st.sidebar.write(f"**プロバイダー**: {model_info['provider']}")

    def show_current_settings(self):
        """現在の設定をサイドバーに表示"""
        st.sidebar.markdown("---")
        st.sidebar.subheader("⚙️ 現在の設定")

        # LLM設定
        model_info = self.llm_manager.get_model_info()
        if model_info:
            st.sidebar.write(f"**LLM**: {model_info['provider']}")
            st.sidebar.write(f"**モデル**: {model_info['model']}")

        # RAG設定
        rag_config_name, rag_config = get_current_rag_config()
        st.sidebar.write(f"**RAG設定**: {rag_config_name}")
        st.sidebar.write(f"**チャンクサイズ**: {rag_config.chunk_size}")
        st.sidebar.write(f"**検索結果数**: {rag_config.search_top_k}")

        # プロンプトスタイル
        prompt_style = settings.get_default_prompt_style()
        st.sidebar.write(f"**プロンプト**: {prompt_style}")

        if st.sidebar.button("🔧 設定を変更"):
            st.session_state["show_settings"] = True

    def _show_prompt_style_selector(self, product_name: str):
        """プロンプトスタイル選択UI"""

        # 利用可能なプロンプトを取得
        available_prompts = prompt_manager.get_available_prompts(product_name)

        # 製品固有 + 汎用プロンプトを統合
        all_prompts = []
        prompt_options = {}

        # 汎用プロンプトを追加
        if "generic" in available_prompts:
            for prompt_type in available_prompts["generic"]:
                info = prompt_manager.get_prompt_info(prompt_type)
                display_name = f"🌐 {info.get('name', prompt_type)}"
                all_prompts.append(display_name)
                prompt_options[display_name] = prompt_type

        # 製品固有プロンプトを追加
        if "product_specific" in available_prompts:
            for prompt_type in available_prompts["product_specific"]:
                info = prompt_manager.get_prompt_info(prompt_type, product_name)
                display_name = f"🎯 {info.get('name', prompt_type)} (専用)"
                all_prompts.append(display_name)
                prompt_options[display_name] = prompt_type

        if not all_prompts:
            st.warning("利用可能なプロンプトがありません")
            return

        # 現在の選択を取得
        current_style = st.session_state.get(f"prompt_style_{product_name}", settings.get_default_prompt_style())

        # 現在の選択に対応する表示名を見つける
        current_display = None
        for display_name, prompt_type in prompt_options.items():
            if prompt_type == current_style:
                current_display = display_name
                break

        # 見つからない場合は最初のプロンプトまたはデフォルトの汎用アシスタントを使用
        if current_display is None:
            if all_prompts:
                current_display = all_prompts[0]
                # セッション状態も更新
                st.session_state[f"prompt_style_{product_name}"] = prompt_options[all_prompts[0]]
            else:
                # プロンプトが全く見つからない場合のフォールバック
                st.session_state[f"prompt_style_{product_name}"] = "general"

        # スタイル選択UI
        with st.expander("🎯 回答スタイルを選択", expanded=False):
            st.write("**回答の雰囲気を選択してください：**")

            try:
                default_index = all_prompts.index(current_display) if current_display in all_prompts else 0
            except (ValueError, IndexError):
                default_index = 0

            selected_display = st.selectbox(
                "プロンプトスタイル",
                options=all_prompts,
                index=default_index,
                key=f"prompt_selector_{product_name}",
                help="選択したスタイルに応じて回答の口調や詳細レベルが変わります",
            )

            # 選択されたプロンプトの説明を表示
            try:
                selected_prompt_type = prompt_options.get(selected_display, "general")
                prompt_info = prompt_manager.get_prompt_info(selected_prompt_type, product_name)
            except Exception as e:
                st.error(f"プロンプト情報取得エラー: {e}")
                selected_prompt_type = "general"
                prompt_info = {}

            if prompt_info.get("description"):
                st.info(f"📝 **説明**: {prompt_info['description']}")

            # セッション状態を更新
            st.session_state[f"prompt_style_{product_name}"] = selected_prompt_type

            # プレビューボタン
            col1, col2 = st.columns(2)
            with col1:
                if st.button("👀 プロンプトプレビュー", key=f"preview_{product_name}"):
                    st.session_state[f"show_prompt_preview_{product_name}"] = True

            with col2:
                if st.button("🔄 デフォルトに戻す", key=f"reset_{product_name}"):
                    st.session_state[f"prompt_style_{product_name}"] = settings.get_default_prompt_style()
                    st.success("デフォルトに戻しました")
                    st.rerun()

        # プロンプトプレビュー表示
        if st.session_state.get(f"show_prompt_preview_{product_name}", False):
            with st.expander("📄 プロンプトプレビュー", expanded=True):
                try:
                    sample_prompt = prompt_manager.get_system_prompt(
                        selected_prompt_type,
                        product_name=product_name,
                        company_name=settings.get_company_name() or "サンプル株式会社",
                        context_text="[サンプル情報源]\n製品の基本機能について説明した文書です。",
                    )

                    st.code(sample_prompt, language="text")

                    # 統計情報
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("文字数", len(sample_prompt))
                    with col2:
                        st.metric("推定トークン数", len(sample_prompt) // 4)
                    with col3:
                        st.metric("行数", sample_prompt.count("\n") + 1)

                    if st.button("プレビューを閉じる", key=f"close_preview_{product_name}"):
                        st.session_state[f"show_prompt_preview_{product_name}"] = False
                        st.rerun()

                except Exception as e:
                    st.error(f"プレビュー生成エラー: {str(e)}")

    def _get_current_user_info(self) -> str:
        """現在のログインユーザー情報を取得"""
        # 認証されている場合はユーザー情報を取得
        if st.session_state.get("authenticated", False):
            user_id = st.session_state.get("user_id", "")
            if user_id:
                # user_emailがあればそれを使用、なければuser_id@farmnote.jpを生成
                user_email = st.session_state.get("user_email", f"{user_id}@farmnote.jp")
                return user_email
        # 認証されていない場合は空文字列
        return ""
