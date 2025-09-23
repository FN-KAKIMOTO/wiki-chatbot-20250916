"""
シンプルな永続化機能

現在のGitHub + Git LFS機能を補完する、より簡単な永続化オプション
"""

import os
import json
import shutil
import zipfile
import requests
import streamlit as st
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import tempfile


class SimplePersistence:
    """シンプルな永続化マネージャー"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.backup_filename = "chatbot_backup.zip"

    def create_backup_zip(self) -> Optional[bytes]:
        """データディレクトリをZIPファイルとして作成"""
        if not self.data_dir.exists():
            return None

        with tempfile.NamedTemporaryFile() as temp_file:
            with zipfile.ZipFile(temp_file.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(self.data_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, self.data_dir.parent)
                        zipf.write(file_path, arcname)

            with open(temp_file.name, 'rb') as f:
                return f.read()

    def restore_from_zip(self, zip_data: bytes) -> bool:
        """ZIPファイルからデータを復元"""
        try:
            # バックアップディレクトリ作成
            if self.data_dir.exists():
                backup_dir = self.data_dir.parent / f"data_backup_{int(datetime.now().timestamp())}"
                shutil.move(str(self.data_dir), str(backup_dir))

            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(zip_data)
                temp_file.flush()

                with zipfile.ZipFile(temp_file.name, 'r') as zipf:
                    zipf.extractall(self.data_dir.parent)

            return True
        except Exception as e:
            st.error(f"復元エラー: {e}")
            return False

    def get_backup_info(self) -> Dict[str, Any]:
        """バックアップ情報を取得"""
        if not self.data_dir.exists():
            return {"exists": False}

        total_size = 0
        file_count = 0
        for root, dirs, files in os.walk(self.data_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.exists(file_path):
                    total_size += os.path.getsize(file_path)
                    file_count += 1

        return {
            "exists": True,
            "total_size": total_size,
            "file_count": file_count,
            "size_mb": round(total_size / (1024 * 1024), 2),
            "last_modified": datetime.fromtimestamp(
                max(os.path.getmtime(os.path.join(root, file))
                    for root, dirs, files in os.walk(self.data_dir)
                    for file in files if os.path.exists(os.path.join(root, file)))
            ).isoformat() if file_count > 0 else None
        }

    def download_interface(self):
        """シンプルなダウンロードインターフェース"""
        st.subheader("📥 シンプルバックアップ（ZIPダウンロード）")

        backup_info = self.get_backup_info()

        if backup_info["exists"]:
            col1, col2 = st.columns([2, 1])

            with col1:
                st.write(f"**ファイル数**: {backup_info['file_count']}")
                st.write(f"**サイズ**: {backup_info['size_mb']} MB")
                if backup_info["last_modified"]:
                    st.write(f"**最終更新**: {backup_info['last_modified'][:19]}")

            with col2:
                if st.button("📦 ZIPダウンロード", key="simple_download"):
                    with st.spinner("ZIPファイル作成中..."):
                        zip_data = self.create_backup_zip()
                        if zip_data:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"chatbot_backup_{timestamp}.zip"

                            st.download_button(
                                label="💾 ダウンロード開始",
                                data=zip_data,
                                file_name=filename,
                                mime="application/zip",
                                key="download_zip"
                            )
                            st.success("✅ ZIPファイルが準備できました")
                        else:
                            st.error("❌ ZIPファイル作成に失敗しました")
        else:
            st.info("バックアップするデータがありません")

    def upload_interface(self):
        """シンプルなアップロードインターフェース"""
        st.subheader("📤 シンプル復元（ZIPアップロード）")

        uploaded_file = st.file_uploader(
            "バックアップZIPファイルを選択",
            type=['zip'],
            help="以前ダウンロードしたchatbot_backup_*.zipファイルをアップロードしてください"
        )

        if uploaded_file is not None:
            st.write(f"**ファイル名**: {uploaded_file.name}")
            st.write(f"**サイズ**: {round(len(uploaded_file.getvalue()) / (1024*1024), 2)} MB")

            if st.button("🔄 データ復元実行", key="simple_restore"):
                with st.spinner("データ復元中..."):
                    success = self.restore_from_zip(uploaded_file.getvalue())
                    if success:
                        st.success("✅ データ復元が完了しました")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("❌ データ復元に失敗しました")

    def combined_interface(self):
        """統合インターフェース"""
        st.subheader("🗂️ シンプル永続化")

        tab1, tab2 = st.tabs(["📥 バックアップ", "📤 復元"])

        with tab1:
            self.download_interface()

        with tab2:
            self.upload_interface()


# シングルトンインスタンス
simple_persistence = SimplePersistence()