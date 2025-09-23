import streamlit as st
import tempfile
import os
import pandas as pd
import io
from typing import List, Dict, Any
from .rag_manager import RAGManager
from .simple_feedback_manager import simple_feedback_manager


class FileHandler:
    def __init__(self):
        self.rag_manager = RAGManager()
        self.supported_extensions = {
            "txt": "text/plain",
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "html": "text/html",
            "csv": "text/csv",
        }

    def get_file_type(self, filename: str) -> str:
        return filename.split(".")[-1].lower() if "." in filename else ""

    def is_supported_file(self, filename: str) -> bool:
        file_type = self.get_file_type(filename)
        return file_type in self.supported_extensions

    def create_template_csv(self) -> bytes:
        """Q&A形式のテンプレートCSVを作成"""
        template_data = {
            "質問": [
                "製品の価格はいくらですか？",
                "製品の主な機能は何ですか？",
                "導入にはどのくらい時間がかかりますか？",
                "サポート体制について教えてください",
                "他社製品との違いは何ですか？",
            ],
            "回答": [
                "基本プランは月額10,000円から、エンタープライズプランは月額50,000円からとなっております。詳細な料金体系については営業担当までお問い合わせください。",
                "主な機能として、データ分析、レポート生成、ダッシュボード作成、API連携などがあります。すべての機能はクラウドベースで提供されます。",
                "通常の導入期間は1-2週間程度です。データ移行やカスタマイズが必要な場合は追加で1-2週間かかる場合があります。",
                "24時間365日のサポート体制を整えており、メール、電話、チャットでのサポートを提供しています。専任の技術者が対応いたします。",
                "当社の製品は高度なAI機能と使いやすいUIが特徴で、導入コストも他社と比較して30%削減可能です。",
            ],
            "参考文献": [
                "https://example.com/pricing",
                "https://example.com/features",
                "https://example.com/implementation-guide",
                "https://example.com/support",
                "https://example.com/comparison",
            ],
        }

        df = pd.DataFrame(template_data)

        # CSVとしてメモリ上に作成
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
        return csv_buffer.getvalue().encode("utf-8-sig")

    def upload_files_interface(self, product_name: str):
        st.subheader(f"📁 {product_name} 用ファイルアップロード")

        # テンプレートCSVダウンロードボタンを追加
        col1, col2 = st.columns([3, 1])

        with col1:
            st.write("**サポートファイル形式**: TXT, PDF, DOCX, PPTX, HTML, CSV")

        with col2:
            template_csv = self.create_template_csv()
            st.download_button(
                label="📥 Q&Aテンプレート CSV",
                data=template_csv,
                file_name=f"{product_name}_qa_template.csv",
                mime="text/csv",
                help="質問と回答の形式でCSVファイルを作成する際のテンプレートです",
            )

        st.markdown("---")

        # CSV形式の説明を追加
        with st.expander("📋 CSVファイルの使用方法", expanded=False):
            st.markdown(
                """
            **CSVファイルは質疑応答形式で処理されます:**

            1. **1列目**: 質問内容（必須）
            2. **2列目**: 回答内容（必須）
            3. **3列目**: 参考文献・リンク（任意）

            **推奨カラム名:**
            ```
            質問,回答,参考文献
            ```

            **使用例:**
            ```
            質問,回答,参考文献
            "製品の価格は？","基本プラン月額10,000円から","https://example.com/pricing"
            "サポート時間は？","平日9-18時、土日祝日は休業","https://example.com/support"
            ```

            **注意事項:**
            - カラム名は「質問」「回答」「参考文献」を推奨（位置での判定も可能）
            - 質問と回答は具体的に記載してください
            - 参考文献列は省略可能です
            - 空白行は自動的にスキップされます
            - 上記テンプレートをダウンロードして参考にしてください
            """
            )

        uploaded_files = st.file_uploader(
            "ファイルを選択してください",
            type=list(self.supported_extensions.keys()),
            accept_multiple_files=True,
            key=f"uploader_{product_name}",
        )

        if uploaded_files:
            for uploaded_file in uploaded_files:
                if self.is_supported_file(uploaded_file.name):
                    file_type = self.get_file_type(uploaded_file.name)

                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"📄 {uploaded_file.name} ({file_type.upper()})")

                    with col2:
                        # CSVファイルの場合は特別な処理オプションを提供
                        if file_type == "csv":
                            csv_process_type = st.selectbox(
                                "CSV処理方法:",
                                ["Q&Aペア形式", "通常のテキスト形式"],
                                key=f"csv_type_{uploaded_file.name}_{product_name}",
                                help="Q&Aペア形式: 各行を質問-回答ペアとして個別処理\n通常のテキスト形式: CSV全体を1つの文書として処理",
                            )

                        if st.button(f"追加", key=f"add_{uploaded_file.name}_{product_name}"):
                            with st.spinner("ファイルを処理中..."):
                                # CSVファイルでQ&Aペア形式が選択された場合
                                if file_type == "csv" and csv_process_type == "Q&Aペア形式":
                                    success = self.rag_manager.add_csv_as_qa_pairs(
                                        product_name, uploaded_file.name, uploaded_file.read()
                                    )
                                else:
                                    success = self.rag_manager.add_document(
                                        product_name, uploaded_file.name, uploaded_file.read(), file_type
                                    )

                                if success:
                                    st.success(f"✅ {uploaded_file.name} が追加されました")
                                    # ファイル追加時の自動バックアップ
                                    simple_feedback_manager.trigger_file_backup()
                                else:
                                    st.error(f"❌ {uploaded_file.name} の追加に失敗しました")
                else:
                    st.warning(f"⚠️ {uploaded_file.name} はサポートされていないファイル形式です")

    def manage_existing_files(self, product_name: str):
        st.subheader(f"📋 {product_name} の登録済みファイル")

        documents = self.rag_manager.list_documents(product_name)

        if not documents:
            st.info("登録されたファイルはありません")
            return

        for doc_name in documents:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"📄 {doc_name}")

            with col2:
                if st.button(f"削除", key=f"delete_{doc_name}_{product_name}"):
                    if st.session_state.get(f"confirm_delete_{doc_name}_{product_name}", False):
                        with st.spinner("ファイルを削除中..."):
                            success = self.rag_manager.remove_document(product_name, doc_name)

                            if success:
                                st.success(f"✅ {doc_name} が削除されました")
                                st.rerun()
                            else:
                                st.error(f"❌ {doc_name} の削除に失敗しました")

                        st.session_state[f"confirm_delete_{doc_name}_{product_name}"] = False
                    else:
                        st.session_state[f"confirm_delete_{doc_name}_{product_name}"] = True
                        st.warning("⚠️ もう一度「削除」ボタンを押して確認してください")

    def product_management_interface(self):
        st.title("🛠️ RAG データベース管理")

        # 商材選択または新規作成
        col1, col2 = st.columns([2, 1])

        with col1:
            existing_products = self.rag_manager.list_products()
            if existing_products:
                selected_product = st.selectbox("既存の商材を選択", ["新規作成"] + existing_products)
            else:
                selected_product = "新規作成"

        with col2:
            if selected_product == "新規作成":
                new_product = st.text_input("新しい商材名を入力")
                if new_product:
                    selected_product = new_product

        if selected_product and selected_product != "新規作成":
            st.divider()

            # ファイルアップロード
            self.upload_files_interface(selected_product)

            st.divider()

            # 既存ファイル管理
            self.manage_existing_files(selected_product)

        elif selected_product == "新規作成":
            st.info("👆 新しい商材名を入力してください")

    def get_supported_formats_info(self):
        return {
            "txt": "テキストファイル",
            "pdf": "PDFドキュメント",
            "docx": "Word文書",
            "html": "HTMLファイル",
            "csv": "CSVファイル",
        }


    def save_uploaded_file(self, uploaded_file, product_name: str):
        """🛡️ 永続化対応アップロードファイル保存"""
        # 永続化システムを読み込み
        from config.persistent_storage import persistent_storage
    
        # ステップ1: ファイルを永続化保存
        saved_path = persistent_storage.save_uploaded_file(uploaded_file, product_name)
    
        if saved_path:
            # ステップ2: RAGシステムに登録（検索できるようにする）
            success = self.rag_manager.add_document(
                file_path=saved_path,
                product_name=product_name
            )
    
            if success:
                st.success(f"✅ {uploaded_file.name} を永続化しました！")
                st.info(f"📁 保存場所: {saved_path}")
                return True
    
        st.error("❌ ファイルの永続化に失敗しました")
        return False
