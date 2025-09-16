# 🚨 トラブルシューティングガイド

このガイドでは、Wiki ChatbotのGitHub永続化機能で発生する可能性のある問題と解決方法を説明します。

## 📋 目次

1. [一般的な問題](#一般的な問題)
2. [Git/GitHub関連](#gitgithub関連)
3. [Streamlit Cloud関連](#streamlit-cloud関連)
4. [パフォーマンス問題](#パフォーマンス問題)
5. [デバッグ方法](#デバッグ方法)

## 🔴 一般的な問題

### 問題1: アプリが起動しない

**症状:**
- Streamlitアプリがクラッシュする
- インポートエラーが発生

**原因と解決方法:**

1. **依存関係の問題**
   ```bash
   # 依存関係の再インストール
   pip install -r requirements.txt --force-reinstall

   # 特定のパッケージ確認
   pip show GitPython
   pip show streamlit
   ```

2. **Python バージョン問題**
   ```bash
   # Python バージョン確認
   python --version  # 3.8+ が必要

   # 仮想環境の再作成
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **パス問題**
   ```python
   # app.py でパス設定確認
   import sys
   import os
   sys.path.append(os.path.dirname(os.path.abspath(__file__)))
   ```

### 問題2: データが保存されない

**症状:**
- チャットデータが消失
- ファイルアップロードが反映されない

**解決方法:**

1. **ディレクトリ権限確認**
   ```bash
   # データディレクトリの権限確認
   ls -la data/

   # 権限修正（必要に応じて）
   chmod 755 data/
   chmod 644 data/*.db
   ```

2. **データベース接続確認**
   ```python
   # デバッグコード
   from pathlib import Path

   data_dir = Path("data")
   print(f"Data directory exists: {data_dir.exists()}")

   db_file = data_dir / "chatbot.db"
   print(f"Database file exists: {db_file.exists()}")
   print(f"Database size: {db_file.stat().st_size if db_file.exists() else 0} bytes")
   ```

## 🔴 Git/GitHub関連

### 問題1: Git LFS容量超過

**エラーメッセージ:**
```
Git LFS: (0 of 1 files) 0 B / 50.0 MB
batch response: This repository is over its data quota
```

**解決方法:**

1. **使用量確認**
   ```bash
   # LFS ファイル一覧
   git lfs ls-files

   # ファイルサイズ確認
   git lfs ls-files | xargs ls -lh
   ```

2. **不要ファイル削除**
   ```bash
   # 古いLFSファイルをクリーンアップ
   git lfs prune

   # 特定ファイルをLFS管理から除外
   git lfs untrack "*.old"
   git add .gitattributes
   git commit -m "Remove old files from LFS tracking"
   ```

3. **データ圧縮**
   ```python
   # SQLiteデータベース最適化
   import sqlite3

   conn = sqlite3.connect("data/chatbot.db")
   conn.execute("VACUUM")
   conn.close()
   ```

### 問題2: 認証エラー

**エラーメッセージ:**
```
remote: Support for password authentication was removed
fatal: Authentication failed for 'https://github.com/...'
```

**解決方法:**

1. **Personal Access Token確認**
   ```bash
   # トークンの有効性テスト
   curl -H "Authorization: token ghp_xxxxxxxxxxxx" \
        https://api.github.com/user
   ```

2. **トークン権限確認**
   - GitHub → Settings → Developer settings → Personal access tokens
   - 必要なスコープ:
     - ✅ `repo` (Full control of private repositories)
     - ✅ `workflow` (Update GitHub Action workflows)

3. **Streamlit Secrets更新**
   ```toml
   # .streamlit/secrets.toml または Streamlit Cloud Secrets
   GITHUB_TOKEN = "ghp_新しいトークン"
   ```

### 問題3: Git コマンド失敗

**症状:**
- clone/push/pull が失敗する
- タイムアウトエラー

**解決方法:**

1. **ネットワーク確認**
   ```bash
   # GitHub接続テスト
   ping github.com

   # DNS確認
   nslookup github.com
   ```

2. **Git設定確認**
   ```bash
   # Git設定表示
   git config --list

   # タイムアウト設定
   git config --global http.timeout 300
   git config --global http.lowSpeedLimit 0
   git config --global http.lowSpeedTime 999999
   ```

3. **プロキシ設定（企業環境）**
   ```bash
   # プロキシ設定例
   git config --global http.proxy http://proxy.company.com:8080
   git config --global https.proxy https://proxy.company.com:8080
   ```

## 🔴 Streamlit Cloud関連

### 問題1: Secrets設定エラー

**症状:**
- 設定値が読み込まれない
- KeyError が発生

**解決方法:**

1. **Secrets形式確認**
   ```toml
   # 正しい形式
   GITHUB_SYNC_ENABLED = true
   GITHUB_DATA_REPO = "https://github.com/user/repo.git"
   GITHUB_TOKEN = "ghp_xxxxxxxxxxxx"

   # 間違った形式（クォート忘れ）
   GITHUB_DATA_REPO = https://github.com/user/repo.git  # ❌
   ```

2. **設定値のデバッグ**
   ```python
   import streamlit as st

   # デバッグ情報表示
   st.write("Available secrets:", list(st.secrets.keys()))

   # 個別確認
   st.write("GitHub enabled:", st.secrets.get("GITHUB_SYNC_ENABLED"))
   st.write("Repo URL:", st.secrets.get("GITHUB_DATA_REPO"))
   st.write("Token exists:", bool(st.secrets.get("GITHUB_TOKEN")))
   ```

### 問題2: デプロイエラー

**症状:**
- アプリがデプロイされない
- ビルドエラーが発生

**解決方法:**

1. **ログ確認**
   - Streamlit Cloud管理画面 → App → Logs
   - エラーメッセージを詳細に確認

2. **依存関係問題**
   ```txt
   # requirements.txt の確認
   streamlit>=1.28.0
   GitPython>=3.1.40
   # その他必要なパッケージ
   ```

3. **ファイルパス問題**
   ```python
   # 相対パス使用
   from pathlib import Path

   # 絶対パス回避
   base_dir = Path(__file__).parent
   config_path = base_dir / "config" / "settings.py"
   ```

## 🔴 パフォーマンス問題

### 問題1: 起動が遅い

**症状:**
- アプリ起動に30秒以上かかる
- データ同期が遅い

**解決方法:**

1. **データサイズ確認**
   ```python
   # ファイルサイズチェック
   from pathlib import Path

   def check_data_size():
       data_dir = Path("data")
       total_size = 0

       for file_path in data_dir.rglob("*"):
           if file_path.is_file():
               size = file_path.stat().st_size
               total_size += size
               print(f"{file_path}: {size / 1024 / 1024:.2f} MB")

       print(f"Total size: {total_size / 1024 / 1024:.2f} MB")
   ```

2. **データベース最適化**
   ```python
   # SQLite最適化
   import sqlite3

   def optimize_database():
       conn = sqlite3.connect("data/chatbot.db")

       # 統計情報更新
       conn.execute("ANALYZE")

       # 不要領域回収
       conn.execute("VACUUM")

       conn.close()
   ```

3. **キャッシュ設定**
   ```python
   import streamlit as st

   @st.cache_data(ttl=300)  # 5分キャッシュ
   def load_heavy_data():
       # 重い処理をキャッシュ
       pass
   ```

### 問題2: メモリ不足

**症状:**
- アプリが突然停止
- "Memory limit exceeded" エラー

**解決方法:**

1. **メモリ使用量監視**
   ```python
   import psutil
   import os

   def check_memory():
       process = psutil.Process(os.getpid())
       memory_mb = process.memory_info().rss / 1024 / 1024
       print(f"Memory usage: {memory_mb:.2f} MB")
       return memory_mb
   ```

2. **データ処理の最適化**
   ```python
   # 大量データを分割処理
   def process_large_data(data, chunk_size=1000):
       for i in range(0, len(data), chunk_size):
           chunk = data[i:i+chunk_size]
           process_chunk(chunk)

           # メモリ解放
           del chunk
   ```

## 🔍 デバッグ方法

### デバッグ情報収集

```python
def collect_debug_info():
    """包括的なデバッグ情報を収集"""
    import sys
    import subprocess
    import platform
    from pathlib import Path

    print("=== システム情報 ===")
    print(f"Python: {sys.version}")
    print(f"Platform: {platform.platform()}")
    print(f"Architecture: {platform.architecture()}")

    print("\n=== Git情報 ===")
    try:
        git_version = subprocess.run(
            ["git", "--version"],
            capture_output=True, text=True
        )
        print(f"Git: {git_version.stdout.strip()}")

        lfs_version = subprocess.run(
            ["git", "lfs", "version"],
            capture_output=True, text=True
        )
        print(f"Git LFS: {lfs_version.stdout.strip()}")
    except Exception as e:
        print(f"Git not available: {e}")

    print("\n=== ファイル情報 ===")
    data_dir = Path("data")
    if data_dir.exists():
        total_size = 0
        for file_path in data_dir.rglob("*"):
            if file_path.is_file():
                size = file_path.stat().st_size
                total_size += size
                print(f"{file_path}: {size / 1024 / 1024:.2f} MB")
        print(f"Total: {total_size / 1024 / 1024:.2f} MB")

    print("\n=== 環境変数 ===")
    important_vars = [
        "STREAMLIT_SERVER_PORT",
        "GITHUB_SYNC_ENABLED",
        "PATH"
    ]
    for var in important_vars:
        value = os.environ.get(var, "Not set")
        print(f"{var}: {value}")

    print("\n=== Python パッケージ ===")
    try:
        import pkg_resources
        packages = [
            "streamlit", "GitPython", "chromadb",
            "openai", "langchain"
        ]
        for package in packages:
            try:
                version = pkg_resources.get_distribution(package).version
                print(f"{package}: {version}")
            except pkg_resources.DistributionNotFound:
                print(f"{package}: Not installed")
    except ImportError:
        print("pkg_resources not available")
```

### ログ設定

```python
import logging

def setup_detailed_logging():
    """詳細なログ設定"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('debug.log'),
            logging.StreamHandler()
        ]
    )

    # 特定モジュールのログレベル調整
    logging.getLogger("github_sync").setLevel(logging.DEBUG)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
```

### 段階的デバッグ

1. **基本機能確認**
   ```python
   # 1. インポート確認
   try:
       from utils.github_sync import GitHubDataSync
       print("✅ GitHub sync import OK")
   except Exception as e:
       print(f"❌ Import error: {e}")

   # 2. 設定確認
   try:
       from config.github_settings import GitHubConfig
       config = GitHubConfig.get_config()
       print(f"✅ Config loaded: {config['enabled']}")
   except Exception as e:
       print(f"❌ Config error: {e}")
   ```

2. **接続テスト**
   ```python
   # GitHub接続テスト
   def test_github_connection():
       import requests

       try:
           response = requests.get("https://api.github.com", timeout=10)
           print(f"✅ GitHub API: {response.status_code}")
       except Exception as e:
           print(f"❌ GitHub connection: {e}")
   ```

3. **同期機能テスト**
   ```python
   # 同期機能の段階的テスト
   def test_sync_features():
       sync = GitHubDataSync(repo_url, token)

       # 1. ディレクトリ作成テスト
       sync.local_data_dir.mkdir(exist_ok=True)
       print("✅ Directory creation OK")

       # 2. Git コマンドテスト
       result = sync._run_git_command(["git", "--version"], ".")
       print(f"✅ Git command: {result}")

       # 3. 同期テスト
       result = sync.sync_on_startup()
       print(f"✅ Sync test: {result}")
   ```

## 📞 サポート

### 問題報告時の情報

問題を報告する際は、以下の情報を含めてください：

1. **環境情報**
   - OS (Windows/Mac/Linux)
   - Python バージョン
   - Streamlit バージョン

2. **エラー情報**
   - 完全なエラーメッセージ
   - スタックトレース
   - ログファイル

3. **再現手順**
   - 問題が発生する具体的な操作
   - 期待する動作
   - 実際の動作

4. **設定情報**
   - GitHub リポジトリ設定
   - Streamlit Secrets設定（トークンは除く）

### 連絡先

- **GitHub Issues**: プロジェクトリポジトリのIssuesタブ
- **ディスカッション**: GitHub Discussionsで質問
- **緊急時**: README記載の連絡先

---

**解決しない場合は、デバッグ情報を含めてIssueを作成してください。** 🔧