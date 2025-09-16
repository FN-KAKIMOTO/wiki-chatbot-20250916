# 🚀 GitHub + Git LFS永続化実装ガイド

このガイドでは、Wiki ChatbotにGitHub + Git LFSによるデータ永続化機能を実装する詳細な手順を説明します。

## 📋 目次

1. [前提条件](#前提条件)
2. [GitHub設定](#github設定)
3. [コード実装](#コード実装)
4. [Streamlit Cloud設定](#streamlit-cloud設定)
5. [テストと確認](#テストと確認)
6. [運用](#運用)

## 🎯 前提条件

### 必要なアカウント
- ✅ GitHubアカウント（無料）
- ✅ Streamlit Cloudアカウント（無料）

### 必要なソフトウェア
```bash
# インストール確認
git --version          # Git 2.0+
git lfs version       # Git LFS 2.0+
python --version      # Python 3.8+
```

### 技術的前提知識
- 基本的なGit操作
- Python/Streamlit基礎
- GitHub基本操作

## 🏗️ GitHub設定

### Step 1: データ保存用リポジトリ作成

1. **新しいリポジトリ作成**
   ```
   Repository name: wiki-chatbot-data
   Description: Persistent data storage for Wiki Chatbot
   Visibility: 🔒 Private （重要：必ずPrivate）
   Initialize: ☑️ Add a README file
   ```

2. **ローカルにクローン**
   ```bash
   cd ~/Desktop
   git clone https://github.com/USERNAME/wiki-chatbot-data.git
   cd wiki-chatbot-data
   ```

### Step 2: Git LFS設定

1. **Git LFS初期化**
   ```bash
   git lfs install
   ```

2. **ディレクトリ構造作成**
   ```bash
   mkdir -p data/chroma_db
   mkdir -p data/sqlite_db
   mkdir -p config
   mkdir -p logs
   ```

3. **.gitattributes設定**
   ```bash
   cat > .gitattributes << 'EOF'
   # データベースファイルをGit LFSで管理
   *.sqlite3 filter=lfs diff=lfs merge=lfs -text
   *.db filter=lfs diff=lfs merge=lfs -text

   # ChromaDBディレクトリ全体
   data/chroma_db/* filter=lfs diff=lfs merge=lfs -text

   # その他大容量ファイル
   *.parquet filter=lfs diff=lfs merge=lfs -text
   *.pkl filter=lfs diff=lfs merge=lfs -text
   *.bak filter=lfs diff=lfs merge=lfs -text
   data/*.csv filter=lfs diff=lfs merge=lfs -text
   EOF
   ```

4. **初期コミット**
   ```bash
   git add .
   git commit -m "Initial setup with Git LFS configuration"
   git push origin main
   ```

### Step 3: Personal Access Token作成

1. **GitHub設定画面**
   - GitHub → Settings → Developer settings → Personal access tokens
   - Tokens (classic) → Generate new token

2. **トークン設定**
   ```
   Note: wiki-chatbot-data-access
   Expiration: No expiration

   Scopes:
   ☑️ repo (Full control of private repositories)
   ☑️ workflow (Update GitHub Action workflows)
   ```

3. **トークン保存**
   ```bash
   # 安全な場所に保存（例）
   echo "ghp_xxxxxxxxxxxxxxxxxxxx" > ~/.github-token
   chmod 600 ~/.github-token
   ```

## 💻 コード実装

### Step 1: 新規ファイル作成

#### A. GitHub同期機能 (`utils/github_sync.py`)

```python
"""
GitHub + Git LFS による永続データ同期管理

主な機能:
- GitHubからのデータダウンロード（復元）
- GitHubへのデータアップロード（バックアップ）
- 起動時の自動同期
- 定期的な自動バックアップ
"""

import os
import shutil
import subprocess
import tempfile
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


class GitHubDataSync:
    """GitHub + Git LFS による永続データ同期管理クラス"""

    def __init__(self,
                 repo_url: str,
                 token: str,
                 local_data_dir: str = "data",
                 branch: str = "main"):
        self.repo_url = repo_url
        self.token = token
        self.local_data_dir = Path(local_data_dir)
        self.branch = branch
        self.temp_dir = None
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """ログ設定"""
        logger = logging.getLogger("github_sync")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def _run_git_command(self, command: list, cwd: str) -> bool:
        """Git コマンド実行"""
        try:
            # 認証URL作成
            if self.token and "clone" in command and len(command) > 2:
                auth_url = self.repo_url.replace(
                    "https://", f"https://{self.token}@"
                )
                command[2] = auth_url

            result = subprocess.run(
                command, cwd=cwd, capture_output=True,
                text=True, timeout=300
            )

            if result.returncode != 0:
                self.logger.error(f"Git command failed: {result.stderr}")
                return False

            self.logger.info(f"Git command success: {' '.join(command[:2])}")
            return True

        except Exception as e:
            self.logger.error(f"Git command error: {e}")
            return False

    def download_data(self) -> bool:
        """GitHubからデータをダウンロード"""
        try:
            self.logger.info("Starting data download from GitHub...")
            self.temp_dir = tempfile.mkdtemp()

            # リポジトリクローン
            if not self._run_git_command([
                "git", "clone", self.repo_url, self.temp_dir
            ], "."):
                return False

            # Git LFS ファイル取得
            self._run_git_command(["git", "lfs", "pull"], self.temp_dir)

            # データコピー
            self.local_data_dir.mkdir(exist_ok=True)
            source_data = Path(self.temp_dir) / "data"

            if source_data.exists():
                shutil.copytree(source_data, self.local_data_dir, dirs_exist_ok=True)
                self.logger.info("Data download completed")
            else:
                self.logger.info("No existing data found, starting fresh")

            return True

        except Exception as e:
            self.logger.error(f"Data download failed: {e}")
            return False
        finally:
            if self.temp_dir and Path(self.temp_dir).exists():
                shutil.rmtree(self.temp_dir)

    def upload_data(self, commit_message: str = None) -> bool:
        """データをGitHubにアップロード"""
        try:
            if not commit_message:
                commit_message = f"Auto backup - {datetime.now().isoformat()}"

            self.logger.info("Starting data upload to GitHub...")
            self.temp_dir = tempfile.mkdtemp()

            # クローン
            if not self._run_git_command([
                "git", "clone", self.repo_url, self.temp_dir
            ], "."):
                return False

            # データコピー
            dest_data = Path(self.temp_dir) / "data"
            if dest_data.exists():
                shutil.rmtree(dest_data)

            if self.local_data_dir.exists():
                shutil.copytree(self.local_data_dir, dest_data)

            # Git設定
            for cmd in [
                ["git", "config", "user.email", "streamlit-bot@example.com"],
                ["git", "config", "user.name", "Streamlit Bot"]
            ]:
                self._run_git_command(cmd, self.temp_dir)

            # コミット・プッシュ
            for cmd in [
                ["git", "add", "."],
                ["git", "commit", "-m", commit_message],
                ["git", "push", "origin", self.branch]
            ]:
                if not self._run_git_command(cmd, self.temp_dir):
                    if "commit" in cmd:
                        self.logger.info("No changes to commit")
                        return True
                    return False

            self.logger.info("Data upload completed")
            return True

        except Exception as e:
            self.logger.error(f"Data upload failed: {e}")
            return False
        finally:
            if self.temp_dir and Path(self.temp_dir).exists():
                shutil.rmtree(self.temp_dir)

    def sync_on_startup(self) -> bool:
        """起動時同期（既存データがない場合のみダウンロード）"""
        self.logger.info("Performing startup data sync...")

        chroma_db = self.local_data_dir / "chroma_db" / "chroma.sqlite3"
        sqlite_db = self.local_data_dir / "chatbot.db"

        if not chroma_db.exists() or not sqlite_db.exists():
            self.logger.info("Local data missing, downloading from GitHub...")
            return self.download_data()

        self.logger.info("Local data exists, skipping download")
        return True

    def get_sync_status(self) -> Dict[str, Any]:
        """同期状況の取得"""
        chroma_db = self.local_data_dir / "chroma_db" / "chroma.sqlite3"
        sqlite_db = self.local_data_dir / "chatbot.db"

        return {
            "chroma_db_exists": chroma_db.exists(),
            "sqlite_db_exists": sqlite_db.exists(),
            "chroma_db_size": chroma_db.stat().st_size if chroma_db.exists() else 0,
            "sqlite_db_size": sqlite_db.stat().st_size if sqlite_db.exists() else 0,
            "last_modified": {
                "chroma_db": datetime.fromtimestamp(
                    chroma_db.stat().st_mtime
                ).isoformat() if chroma_db.exists() else None,
                "sqlite_db": datetime.fromtimestamp(
                    sqlite_db.stat().st_mtime
                ).isoformat() if sqlite_db.exists() else None
            }
        }
```

#### B. GitHub設定管理 (`config/github_settings.py`)

```python
"""GitHub 同期設定管理"""

import streamlit as st
from typing import Dict, Any


class GitHubConfig:
    """GitHub 同期設定管理クラス"""

    @staticmethod
    def get_config() -> Dict[str, Any]:
        """GitHub同期設定を取得"""
        return {
            "enabled": st.secrets.get("GITHUB_SYNC_ENABLED", False),
            "repo_url": st.secrets.get("GITHUB_DATA_REPO"),
            "token": st.secrets.get("GITHUB_TOKEN"),
            "branch": "main",
            "auto_backup_interval": 30,  # 分
            "max_file_size": 100_000_000  # 100MB
        }

    @staticmethod
    def is_configured() -> bool:
        """設定が完了しているかチェック"""
        config = GitHubConfig.get_config()
        return all([
            config["enabled"],
            config["repo_url"],
            config["token"]
        ])

    @staticmethod
    def get_display_config() -> Dict[str, str]:
        """表示用設定情報（トークンマスク済み）"""
        config = GitHubConfig.get_config()

        masked_token = None
        if config["token"]:
            token = config["token"]
            masked_token = f"{token[:8]}{'*' * (len(token) - 12)}{token[-4:]}"

        return {
            "enabled": "✅ 有効" if config["enabled"] else "❌ 無効",
            "repo_url": config["repo_url"] or "未設定",
            "token": masked_token or "未設定",
            "branch": config["branch"],
            "backup_interval": f"{config['auto_backup_interval']}分"
        }
```

### Step 2: 既存ファイル修正

#### A. app.py修正

```python
# インポート追加
from config.github_settings import GitHubConfig
from utils.github_sync import GitHubDataSync

# main()関数内に追加（セッション初期化後）
def main():
    # ... 既存コード ...

    # GitHub 同期初期化（認証前に実行）
    github_sync = None
    if GitHubConfig.is_configured():
        config = GitHubConfig.get_config()
        github_sync = GitHubDataSync(
            repo_url=config["repo_url"],
            token=config["token"]
        )

        # 起動時同期（初回のみ）
        if "github_synced" not in st.session_state:
            with st.spinner("データを同期中..."):
                success = github_sync.sync_on_startup()
                if success:
                    st.session_state.github_synced = True
                    st.sidebar.success("✅ データ同期完了")
                else:
                    st.sidebar.warning("⚠️ データ同期に失敗しました")

    # ... 既存の認証処理 ...

    # サイドバーに同期UI追加（最後に追加）
    if github_sync and GitHubConfig.is_configured():
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔄 データ同期")

        # 同期状況表示
        sync_status = github_sync.get_sync_status()
        if sync_status["chroma_db_exists"] and sync_status["sqlite_db_exists"]:
            st.sidebar.success("✅ データファイル確認済み")
        else:
            st.sidebar.warning("⚠️ データファイルが見つかりません")

        # 手動操作ボタン
        if st.sidebar.button("📤 手動バックアップ"):
            with st.spinner("バックアップ中..."):
                success = github_sync.upload_data("Manual backup from Streamlit")
                if success:
                    st.sidebar.success("✅ バックアップ完了")
                else:
                    st.sidebar.error("❌ バックアップ失敗")

        if st.sidebar.button("📥 データ復元"):
            with st.spinner("復元中..."):
                success = github_sync.download_data()
                if success:
                    st.sidebar.success("✅ 復元完了")
                    st.rerun()
                else:
                    st.sidebar.error("❌ 復元失敗")
```

#### B. requirements.txt修正

```txt
# 既存の依存関係に追加
GitPython>=3.1.40
```

## ☁️ Streamlit Cloud設定

### Step 1: アプリデプロイ

1. **コードプッシュ**
   ```bash
   git add .
   git commit -m "Add GitHub sync functionality"
   git push origin main
   ```

2. **Streamlit Cloudでアプリ作成**
   - https://share.streamlit.io/ にアクセス
   - New app → GitHub repository選択
   - `wiki_chatbot/app.py` を指定

### Step 2: Secrets設定

Streamlit Cloud管理画面で **Settings → Secrets** に以下を設定：

```toml
# GitHub同期設定
GITHUB_SYNC_ENABLED = true
GITHUB_DATA_REPO = "https://github.com/USERNAME/wiki-chatbot-data.git"
GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"

# 既存設定
OPENAI_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxx"
SHARED_PASSWORD = "your-password"
```

## 🧪 テストと確認

### ローカルテスト

1. **環境設定**
   ```bash
   # .streamlit/secrets.toml 作成
   mkdir -p .streamlit
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   # secrets.tomlを編集
   ```

2. **動作確認**
   ```bash
   streamlit run app.py
   ```

3. **確認項目**
   - ✅ アプリが正常起動
   - ✅ サイドバーに同期セクション表示
   - ✅ バックアップボタンが機能
   - ✅ GitHubにデータが保存される

### Streamlit Cloudテスト

1. **デプロイ確認**
   - 管理画面でログを確認
   - エラーがないことを確認

2. **機能確認**
   - チャットボット動作
   - データ同期機能
   - バックアップ・復元機能

## 📊 運用

### 日常的な運用

1. **定期バックアップ**
   - 重要な変更後は手動バックアップを実行
   - 週1回程度の定期確認

2. **容量監視**
   - GitHub LFS使用量を月次確認
   - 無料枠：1GB/月まで

3. **パフォーマンス監視**
   - アプリ起動時間の確認
   - メモリ使用量の監視

### メンテナンス

1. **データクリーンアップ**
   ```python
   # 古いデータの削除（90日以上）
   from config.database import persistent_db
   persistent_db.cleanup_old_data(days_old=90)
   ```

2. **トークン更新**
   - Personal Access Tokenの定期更新
   - Streamlit Secretsの更新

### 監視指標

- **データサイズ**: 通常100-500MB
- **同期時間**: 通常30秒以内
- **成功率**: 95%以上を目標

## 🔍 トラブルシューティング

詳細は [TROUBLESHOOTING.md](TROUBLESHOOTING.md) を参照してください。

### よくある問題

1. **Git LFS容量超過**
   ```bash
   # 使用量確認
   git lfs ls-files
   # 不要ファイル削除
   git lfs prune
   ```

2. **認証エラー**
   - Personal Access Tokenの権限確認
   - リポジトリのアクセス権確認

3. **同期失敗**
   - ネットワーク接続確認
   - GitHubサービス状況確認

## 📈 今後の改善案

1. **自動化強化**
   - GitHub Actionsによる定期バックアップ
   - Webhookによるリアルタイム同期

2. **監視機能**
   - データサイズ警告
   - 同期失敗通知

3. **ユーザビリティ**
   - バックアップ履歴表示
   - 復元ポイント選択

---

**実装完了！** 🎉

これでGitHub + Git LFSによる永続化機能が実装されました。データはStreamlit Cloud再起動後も保持され、手動でのバックアップ・復元も可能になります。