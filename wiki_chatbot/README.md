# Wiki Chatbot v3.0

企業向けRAG（Retrieval-Augmented Generation）チャットボットシステム。社内文書に基づく正確な質問応答を提供します。

## 🚀 主な機能

### 💬 インテリジェントチャット
- **複数LLMサポート**: OpenAI, Anthropic, Google AI対応
- **製品別データベース**: 商材ごとの独立した知識ベース
- **ユーザー選択式プロンプト**: 営業、技術、サポートなど用途別の回答スタイル
- **ソース表示**: 回答の根拠となった文書を詳細表示

### 📁 ファイル処理
- **多形式対応**: TXT, PDF, DOCX, PPTX, HTML, CSV
- **Q&Aペア処理**: CSVファイルから質問-回答ペアを自動抽出
- **テンプレート提供**: CSV用のフォーマット済みテンプレートダウンロード

### 🎯 プロンプト管理
- **外部設定ファイル**: YAMLベースの柔軟なプロンプト管理
- **階層式優先度**: 製品専用 → 汎用 → デフォルトの自動選択
- **リアルタイム編集**: コード変更なしでプロンプト更新

### 🌐 Web デプロイメント対応
- **認証システム**: セッション管理と制限機能
- **環境変数管理**: 本番環境用の設定システム
- **Docker対応**: コンテナベースデプロイメント
- **マルチクラウド**: Streamlit Cloud, AWS, GCP対応

## 📋 システム要件

### 必須要件
- Python 3.9+
- 8GB+ RAM推奨
- 少なくとも1つのLLM API Key

### 対応プラットフォーム
- Windows 10+
- macOS 10.15+
- Linux (Ubuntu 18.04+)

## ⚡ クイックスタート

### 1. 環境設定
```bash
git clone https://github.com/your-org/wiki-chatbot.git
cd wiki-chatbot
pip install -r requirements.txt
```

### 2. API Key設定
`.env.example`をコピーして`.env`を作成：
```bash
cp .env.example .env
```

必要なAPI Keyを設定：
```env
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
GOOGLE_API_KEY=your-google-ai-key
```

### 3. アプリケーション起動
```bash
streamlit run app.py
```

## 🎯 使用方法

### 基本フロー
1. **商材作成**: 管理画面で新しい商材を登録
2. **文書アップロード**: 各種ファイルをRAGデータベースに追加
3. **プロンプト選択**: 用途に応じた回答スタイルを選択
4. **チャット開始**: 自然言語で質問を投稿

### プロンプトスタイル一覧
- **🌐 汎用アシスタント**: 基本的な質問応答
- **🌐 営業サポート**: 営業現場向けの実践的回答
- **🌐 技術サポート**: エンジニア向けの詳細技術情報
- **🌐 コンプライアンス対応**: 法的観点からの慎重な回答
- **🌐 顧客サポート**: お客様向けの丁寧な説明
- **🌐 新人研修用**: 初心者向けの段階的説明
- **🎯 製品専用**: 各製品固有のカスタムプロンプト

## 🏗️ アーキテクチャ

### コアコンポーネント
```
├── app.py                    # メインアプリケーション
├── config/
│   ├── settings.py          # システム設定
│   ├── web_settings.py      # Web環境用設定
│   └── prompts/             # プロンプト設定
│       ├── generic.yaml     # 汎用プロンプト
│       ├── rag_prompts.yaml # RAG処理用プロンプト
│       └── products/        # 製品別プロンプト
├── utils/
│   ├── chatbot.py           # チャット機能
│   ├── rag_manager.py       # RAG処理
│   ├── llm_manager.py       # LLM統合管理
│   ├── prompt_manager.py    # プロンプト管理
│   └── session_manager.py   # セッション管理
└── pages/                   # UI画面
    ├── admin.py             # 管理画面
    ├── settings.py          # 設定画面
    └── prompt_settings.py   # プロンプト管理画面
```

### データフロー
```
User Query → Prompt Selection → RAG Search → LLM Processing → Response + Sources
```

## 🌐 デプロイメント

### Streamlit Cloud
1. GitHubリポジトリをStreamlit Cloudに接続
2. `secrets.toml`にAPI Keyを設定
3. 自動デプロイ完了

### Docker
```bash
# コンテナビルド
docker build -t wiki-chatbot .

# 起動
docker run -p 8501:8501 --env-file .env wiki-chatbot
```

### Docker Compose
```bash
docker-compose up -d
```

## 📚 ドキュメント

詳細なドキュメントは`docs/`フォルダを参照：

- [技術仕様書](docs/technical_specification.md)
- [実装ガイド](docs/implementation_guide.md)
- [プロンプト管理ガイド](docs/prompt_management_guide.md)
- [Web デプロイメントガイド](docs/web_deployment_guide.md)
- [ユーザーマニュアル](docs/user_manual.md)
- [トラブルシューティング](docs/troubleshooting.md)

## 🔧 カスタマイズ

### プロンプトのカスタマイズ
```yaml
# config/prompts/products/your_product.yaml
product_name: "Your Product"
product_specific_context: "製品固有の背景情報"

custom_support:
  name: "カスタムサポート"
  description: "製品専用のサポート対応"
  system_prompt: |
    あなたは{product_name}の専門サポート担当です...
```

### 新しいLLMプロバイダーの追加
`utils/llm_manager.py`の`LLMManager`クラスにプロバイダーを追加：
```python
def add_custom_provider(self, provider_config):
    # カスタムプロバイダーの実装
    pass
```

## 🛠️ 開発者向け

### 開発環境セットアップ
```bash
# 開発用依存関係インストール
pip install -r requirements-dev.txt

# テスト実行
pytest tests/

# 型チェック
mypy utils/
```

### コントリビューション
1. フォークを作成
2. フィーチャーブランチで開発
3. テストを追加
4. プルリクエスト提出

## 📞 サポート

### バグレポート・機能要望
GitHubのIssuesで報告してください。

### よくある質問
[トラブルシューティングガイド](docs/troubleshooting.md)を確認してください。

## 📜 ライセンス

MIT License - 詳細は[LICENSE](LICENSE)ファイルを参照。

## 🏷️ バージョン履歴

### v4.0.0 (2025-09-03) - **最新版**
- **🎯 ユーザー選択式プロンプト**: 営業・技術・サポートなど用途別回答スタイル
- **🔗 会話記憶機能**: 前の質問を踏まえた自然な追加質問
- **📊 包括的フィードバック収集**: チャット履歴・満足度の自動保存
- **📈 リアルタイム分析ダッシュボード**: 利用統計・改善提案の自動生成
- **📥 データエクスポート機能**: CSV形式での詳細分析対応
- **🌐 本格Web展開対応**: 認証・セッション管理・マルチクラウド対応

### v3.0.0 (2025-09-02)
- Web デプロイメント基盤
- PPTX ファイルサポート
- CSV Q&A ペア処理機能
- 認証・セッション管理機能

### v2.0.0 (2025-09-02)
- 外部プロンプト設定システム
- 拡張RAG機能
- 複数LLMプロバイダーサポート
- 製品別プロンプト優先度システム

### v1.0.0 (初期リリース)
- 基本RAGチャットボット機能
- ファイルアップロード・管理
- OpenAI GPT統合

---
**Wiki Chatbot** - Intelligent Enterprise RAG Solution