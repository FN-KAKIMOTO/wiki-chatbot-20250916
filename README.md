# 📚 Wiki Chatbot with GitHub Persistence

Streamlit Cloud対応のRAGベースWikiチャットボットです。GitHub + Git LFSによるデータ永続化機能を搭載し、アプリ再起動後もRAGデータとチャット履歴が保持されます。

## 🌟 主な機能

- **RAG（Retrieval-Augmented Generation）**による高精度回答
- **複数商材対応**（商材ごとのRAGデータベース管理）
- **GitHub + Git LFS**による永続データ保存
- **多様なファイル形式**サポート（PDF, DOCX, TXT, CSV）
- **リアルタイムチャット**履歴管理
- **ユーザー認証**システム
- **手動バックアップ・復元**機能

## 🏗️ システム構成

```
├── wiki_chatbot/               # メインアプリケーション
│   ├── app.py                 # Streamlitエントリーポイント
│   ├── config/                # 設定管理
│   │   ├── web_settings.py    # Web設定
│   │   ├── database.py        # データベース設定
│   │   └── github_settings.py # GitHub同期設定
│   ├── utils/                 # ユーティリティ
│   │   ├── chatbot.py         # チャットボット機能
│   │   ├── rag_manager.py     # RAG管理
│   │   ├── session_manager.py # セッション管理
│   │   ├── github_sync.py     # GitHub同期機能
│   │   └── feedback_manager.py # フィードバック管理
│   ├── pages/                 # Streamlitページ
│   │   ├── admin.py           # 管理画面
│   │   └── settings.py        # 設定画面
│   ├── data/                  # データ保存（永続化対象）
│   │   ├── chroma_db/         # RAGベクトルデータベース
│   │   ├── chatbot.db         # チャット履歴SQLite
│   │   └── *.csv              # エクスポートデータ
│   └── requirements.txt       # Python依存関係
└── docs/                      # ドキュメント
    ├── IMPLEMENTATION_GUIDE.md # 実装ガイド
    └── TROUBLESHOOTING.md     # トラブルシューティング
```

## 🚀 クイックスタート

### 1. 前提条件

- Python 3.8+
- Git & Git LFS
- GitHubアカウント
- OpenAI APIキー

### 2. セットアップ

```bash
# リポジトリクローン
git clone https://github.com/your-username/wiki-chatbot-main.git
cd wiki-chatbot-main/wiki_chatbot

# 依存関係インストール
pip install -r requirements.txt

# 環境設定
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# secrets.tomlを編集（APIキー等を設定）

# アプリ起動
streamlit run app.py
```

### 3. GitHub永続化セットアップ

詳細な手順は [IMPLEMENTATION_GUIDE.md](docs/IMPLEMENTATION_GUIDE.md) を参照してください。

## ⚙️ 設定

### 必須環境変数（Streamlit Secrets）

```toml
# GitHub同期設定
GITHUB_SYNC_ENABLED = true
GITHUB_DATA_REPO = "https://github.com/username/wiki-chatbot-data.git"
GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"

# OpenAI設定
OPENAI_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxx"

# 認証設定
SHARED_PASSWORD = "your-shared-password"
```

## 📖 使用方法

### 基本的な流れ

1. **認証**：アプリアクセス時に認証
2. **商材選択**：対象商材を選択
3. **文書アップロード**：管理画面でPDF/DOCXファイルをアップロード
4. **チャット**：自然言語で質問
5. **自動バックアップ**：データは自動的にGitHubに同期

### データ管理

- **手動バックアップ**：サイドバーの「📤 手動バックアップ」ボタン
- **データ復元**：サイドバーの「📥 データ復元」ボタン
- **管理画面**：文書の追加・削除、統計表示

## 🔧 開発

### ローカル開発環境

```bash
# 開発用依存関係
pip install -r requirements-dev.txt

# テスト実行
pytest tests/

# コード品質チェック
flake8 wiki_chatbot/
black wiki_chatbot/
```

### ディレクトリ構造の説明

- `config/`: 設定ファイル群
- `utils/`: 共通ユーティリティ
- `pages/`: Streamlitマルチページ
- `data/`: 永続化データ（Git LFS管理）

## 🚨 トラブルシューティング

よくある問題と解決方法は [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) を参照してください。

### 主な問題

- **Git LFS容量超過**: GitHubの無料枠（1GB/月）を確認
- **認証エラー**: Personal Access Tokenの権限を確認
- **同期失敗**: ネットワーク接続とリポジトリアクセス権を確認

## 📈 パフォーマンス

### 推奨環境

- **メモリ**: 最小512MB、推奨1GB+
- **ストレージ**: 最小100MB、推奨500MB+
- **ネットワーク**: インターネット接続必須

### データサイズ目安

- ChromaDB: 商材あたり10-100MB
- SQLite: チャット履歴1万件で約10MB
- 合計: 通常100-500MB程度

## 🔐 セキュリティ

- **プライベートリポジトリ**: データは必ずプライベートリポジトリに保存
- **アクセストークン**: 最小権限のPersonal Access Tokenを使用
- **認証**: 社内メールドメイン制限対応
- **ログ**: 機密情報の非ログ化

## 🤝 コントリビューション

1. Forkを作成
2. フィーチャーブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add amazing feature'`)
4. ブランチにプッシュ (`git push origin feature/amazing-feature`)
5. Pull Requestを作成

## 📄 ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細は [LICENSE](LICENSE) ファイルを参照してください。

## 🙋‍♂️ サポート

- **イシュー**: [GitHub Issues](https://github.com/your-username/wiki-chatbot-main/issues)
- **ディスカッション**: [GitHub Discussions](https://github.com/your-username/wiki-chatbot-main/discussions)
- **ドキュメント**: [docs/](docs/) ディレクトリ

## 🔄 更新履歴

### v2.0.0 (2025-01-XX)
- GitHub + Git LFS永続化機能追加
- データ自動同期機能
- 手動バックアップ・復元UI

### v1.0.0 (2024-XX-XX)
- 初期リリース
- RAGベースチャットボット
- マルチ商材対応

---

**🚀 Streamlit Cloudで今すぐ試す**: [![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io)