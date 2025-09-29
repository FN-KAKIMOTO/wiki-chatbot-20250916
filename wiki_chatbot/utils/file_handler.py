import streamlit as st
import tempfile
import os
import pandas as pd
import io
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Any
from .rag_manager import RAGManager
from .feedback_manager import feedback_manager


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

    def fetch_html_body(self, url: str) -> str:
        """URLからHTMLを取得してbodyテキストを抽出"""
        try:
            # URLの正規化
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            # HTMLを取得
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            # BeautifulSoupでHTMLを解析
            soup = BeautifulSoup(response.content, 'html.parser')

            # 不要な要素を削除
            for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()

            # bodyタグから本文を抽出
            body = soup.find('body')
            if body:
                text = body.get_text(separator='\n', strip=True)
            else:
                text = soup.get_text(separator='\n', strip=True)

            # 空白行を整理
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            return '\n'.join(lines)

        except requests.RequestException as e:
            return f"URL取得エラー: {str(e)}"
        except Exception as e:
            return f"HTML解析エラー: {str(e)}"

    def process_url_csv(self, product_name: str, csv_content: bytes) -> Dict[str, Any]:
        """URLが記載されたCSVを処理してHTMLコンテンツをRAGに追加"""
        try:
            # CSVを読み込み
            df = pd.read_csv(io.BytesIO(csv_content), encoding='utf-8')

            # URLを含む列を特定
            url_columns = []
            for col in df.columns:
                if any(keyword in col.lower() for keyword in ['url', 'link', 'リンク', 'ページ', 'サイト']):
                    url_columns.append(col)

            if not url_columns:
                # URLっぽい値を含む列を自動検出
                for col in df.columns:
                    sample_values = df[col].dropna().astype(str).head(5)
                    if any('http' in str(val) or '.' in str(val) for val in sample_values):
                        url_columns.append(col)

            if not url_columns:
                return {"success": False, "error": "URL列が見つかりません"}

            results = {
                "success": True,
                "processed_urls": 0,
                "failed_urls": 0,
                "error_details": []
            }

            # 各URLを処理
            for idx, row in df.iterrows():
                for url_col in url_columns:
                    url = str(row[url_col]).strip()
                    if url and url != 'nan' and ('http' in url or '.' in url):
                        try:
                            # HTMLコンテンツを取得
                            html_content = self.fetch_html_body(url)

                            if "エラー" not in html_content:
                                # タイトル列があれば使用、なければURLから生成
                                title_cols = [col for col in df.columns if any(keyword in col.lower() for keyword in ['title', 'タイトル', '題名', '名前'])]
                                if title_cols:
                                    title = str(row[title_cols[0]])
                                else:
                                    title = f"Webページ: {urlparse(url).netloc}"

                                # RAGに追加
                                filename = f"{title}_{idx}.html"
                                success = self.rag_manager.add_document(
                                    product_name, filename, html_content.encode('utf-8')
                                )

                                if success:
                                    results["processed_urls"] += 1
                                else:
                                    results["failed_urls"] += 1
                                    results["error_details"].append(f"RAG追加失敗: {url}")
                            else:
                                results["failed_urls"] += 1
                                results["error_details"].append(f"{url}: {html_content}")

                        except Exception as e:
                            results["failed_urls"] += 1
                            results["error_details"].append(f"{url}: {str(e)}")

            return results

        except Exception as e:
            return {"success": False, "error": f"CSV処理エラー: {str(e)}"}

    def create_url_template_csv(self) -> bytes:
        """URL取得用のテンプレートCSVを作成"""
        template_data = {
            "タイトル": [
                "会社概要ページ",
                "製品紹介ページ",
                "料金プランページ",
                "サポートページ",
                "よくある質問",
            ],
            "URL": [
                "https://example.com/about",
                "https://example.com/products",
                "https://example.com/pricing",
                "https://example.com/support",
                "https://example.com/faq",
            ],
            "説明": [
                "会社の基本情報",
                "製品の詳細機能",
                "価格体系と料金プラン",
                "サポート体制",
                "よくある質問と回答",
            ],
        }

        df = pd.DataFrame(template_data)

        # CSVとしてメモリ上に作成
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
        return csv_buffer.getvalue().encode("utf-8-sig")

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
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            st.write("**サポートファイル形式**: TXT, PDF, DOCX, PPTX, HTML, CSV")

        with col2:
            template_csv = self.create_template_csv()
            st.download_button(
                label="📥 Q&Aテンプレート",
                data=template_csv,
                file_name=f"{product_name}_qa_template.csv",
                mime="text/csv",
                help="質問と回答の形式でCSVファイルを作成する際のテンプレートです",
            )

        with col3:
            url_template_csv = self.create_url_template_csv()
            st.download_button(
                label="🌐 URLテンプレート",
                data=url_template_csv,
                file_name=f"{product_name}_url_template.csv",
                mime="text/csv",
                help="WebページのURLを記載してHTMLコンテンツを取得する際のテンプレートです",
            )

        st.markdown("---")

        # CSV形式の説明を追加
        with st.expander("📋 CSVファイルの使用方法", expanded=False):
            st.markdown(
                """
            **CSVファイルには3つの処理方法があります:**

            ## 1. Q&Aペア形式
            質疑応答形式でデータを処理します：
            - **1列目**: 質問内容（必須）
            - **2列目**: 回答内容（必須）
            - **3列目**: 参考文献・リンク（任意）

            **推奨カラム名:**
            ```
            質問,回答,参考文献
            ```

            ## 2. URL一括取得 🌐 NEW!
            WebページのURLからHTMLコンテンツを自動取得します：
            - **URL列**: WebページのURL（必須）
            - **タイトル列**: ページのタイトル（推奨）
            - **説明列**: ページの説明（任意）

            **推奨カラム名:**
            ```
            タイトル,URL,説明
            ```

            **使用例:**
            ```
            タイトル,URL,説明
            "会社概要","https://example.com/about","会社の基本情報"
            "製品情報","https://example.com/products","製品の詳細機能"
            ```

            ## 3. 通常のテキスト形式
            CSV全体を1つの文書として処理します。

            **注意事項:**
            - URL一括取得では、各URLのHTMLのbodyタグ内容を自動的に抽出します
            - HTTPSとHTTP両方に対応しています
            - ページ取得に失敗したURLはスキップされます
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
                                ["Q&Aペア形式", "URL一括取得", "通常のテキスト形式"],
                                key=f"csv_type_{uploaded_file.name}_{product_name}",
                                help="Q&Aペア形式: 各行を質問-回答ペアとして個別処理\nURL一括取得: CSVのURLからHTMLコンテンツを取得\n通常のテキスト形式: CSV全体を1つの文書として処理",
                            )

                        if st.button(f"追加", key=f"add_{uploaded_file.name}_{product_name}"):
                            with st.spinner("ファイルを処理中..."):
                                # CSVファイルでQ&Aペア形式が選択された場合
                                if file_type == "csv" and csv_process_type == "Q&Aペア形式":
                                    success = self.rag_manager.add_csv_as_qa_pairs(
                                        product_name, uploaded_file.name, uploaded_file.read()
                                    )
                                # CSVファイルでURL一括取得が選択された場合
                                elif file_type == "csv" and csv_process_type == "URL一括取得":
                                    csv_content = uploaded_file.read()
                                    result = self.process_url_csv(product_name, csv_content)

                                    if result["success"]:
                                        st.success(f"✅ URL処理完了: {result['processed_urls']}件のURLからHTMLを取得しました")
                                        if result["failed_urls"] > 0:
                                            st.warning(f"⚠️ {result['failed_urls']}件のURLで取得に失敗しました")
                                            if result["error_details"]:
                                                with st.expander("エラー詳細", expanded=False):
                                                    for error in result["error_details"][:5]:  # 最大5件まで表示
                                                        st.write(f"• {error}")
                                        # ファイル追加時の自動バックアップ
                                        feedback_manager._trigger_auto_backup("URL content addition backup")
                                        success = True
                                    else:
                                        st.error(f"❌ URL処理エラー: {result['error']}")
                                        success = False
                                else:
                                    success = self.rag_manager.add_document(
                                        product_name, uploaded_file.name, uploaded_file.read(), file_type
                                    )

                                if success and csv_process_type != "URL一括取得":
                                    st.success(f"✅ {uploaded_file.name} が追加されました")
                                    # ファイル追加時の自動バックアップ
                                    feedback_manager._trigger_auto_backup("File addition backup")
                                elif not success and csv_process_type != "URL一括取得":
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
