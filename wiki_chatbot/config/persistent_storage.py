"""
永続化ストレージ管理システム
GitHub + Streamlit Cloud連携による自動データ保存
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
import streamlit as st


class PersistentStorage:
    """永続化ストレージ管理クラス"""

    def __init__(self):
        self.data_dir = Path("data")
        self.backup_dir = Path("data/backups")
        self.max_storage_mb = 100  # 最大100MB

        # ディレクトリ作成
        self.data_dir.mkdir(exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)

    def save_uploaded_file(self, uploaded_file, product_name: str):
        """アップロードファイルを永続化"""
        try:
            # 製品別フォルダ作成
            product_dir = self.data_dir / "products" / product_name
            product_dir.mkdir(parents=True, exist_ok=True)

            # ファイル保存
            file_path = product_dir / uploaded_file.name
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            # メタデータ保存
            self._save_metadata(file_path, uploaded_file)

            return str(file_path)

        except Exception as e:
            st.error(f"ファイル保存エラー: {e}")
            return None

    def _save_metadata(self, file_path: Path, uploaded_file):
        """ファイルメタデータを保存"""
        metadata = {
            "original_name": uploaded_file.name,
            "size": uploaded_file.size,
            "type": uploaded_file.type,
            "uploaded_at": datetime.now().isoformat(),
            "file_path": str(file_path)
        }

        metadata_path = file_path.with_suffix(f"{file_path.suffix}.meta")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def get_storage_usage(self):
        """ストレージ使用量を取得"""
        total_size = 0
        for file_path in self.data_dir.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size

        return total_size / (1024 * 1024)  # MB変換

    def cleanup_old_files(self, days_old: int = 30):
        """古いファイルを自動削除"""
        cutoff_time = datetime.now().timestamp() - (days_old * 24 * 3600)

        for file_path in self.data_dir.rglob("*"):
            if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                # バックアップに移動
                backup_path = self.backup_dir / file_path.name
                backup_path.parent.mkdir(exist_ok=True)
                shutil.move(str(file_path), str(backup_path))

    def create_backup(self):
        """データベース全体のバックアップ作成"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}"

        shutil.make_archive(
            str(self.backup_dir / backup_name),
            "zip",
            str(self.data_dir)
        )

    def get_file_list(self, product_name: str):
        """製品のファイル一覧を取得"""
        product_dir = self.data_dir / "products" / product_name
        if not product_dir.exists():
            return []

        files = []
        for file_path in product_dir.glob("*"):
            if file_path.is_file() and not file_path.suffix == ".meta":
                # メタデータを読み込み
                metadata_path = file_path.with_suffix(f"{file_path.suffix}.meta")
                if metadata_path.exists():
                    try:
                        with open(metadata_path, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                        files.append(metadata)
                    except:
                        # メタデータ読み込み失敗時の基本情報
                        files.append({
                            "original_name": file_path.name,
                            "file_path": str(file_path),
                            "uploaded_at": datetime.fromtimestamp(
                                file_path.stat().st_mtime
                            ).isoformat()
                        })

        return files

    def delete_file(self, file_path: str):
        """ファイルを削除"""
        try:
            path = Path(file_path)
            if path.exists():
                # メタデータも削除
                metadata_path = path.with_suffix(f"{path.suffix}.meta")
                if metadata_path.exists():
                    metadata_path.unlink()
                path.unlink()
                return True
        except Exception as e:
            st.error(f"ファイル削除エラー: {e}")
        return False

    def is_storage_full(self):
        """ストレージが満杯かチェック"""
        return self.get_storage_usage() >= self.max_storage_mb


# グローバルインスタンス
persistent_storage = PersistentStorage()