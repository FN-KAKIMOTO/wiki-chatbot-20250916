# Streamlit Cloud設定ガイド

## 1. Streamlit Cloudでの設定手順

### 手順1: アプリをデプロイ
1. [share.streamlit.io](https://share.streamlit.io) にアクセス
2. GitHubリポジトリを連携
3. `wiki_chatbot/app.py` を指定してデプロイ

### 手順2: Secrets設定
1. Streamlit Cloudダッシュボードにアクセス
2. 該当アプリの「Settings」をクリック
3. 「Secrets」タブを選択
4. 以下の内容をコピー&ペーストして「Save」

```toml
# LLMプロバイダー API Keys（最低1つは必須）
OPENAI_API_KEY = "sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
ANTHROPIC_API_KEY = "sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
GOOGLE_API_KEY = "AIzaxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# GitHub永続化設定（必須）
GITHUB_REPO_URL = "https://github.com/yourusername/wiki-chatbot-data.git"
GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# 自動バックアップ設定
BACKUP_INTERVAL_MESSAGES = 10

# 認証設定
AUTH_PASSWORD = "your_secure_password"
ALLOWED_EMAIL_DOMAIN = "farmnote.jp"

# システム設定
DEBUG_MODE = true
APP_TITLE = "社内Wiki検索チャットボット"
```

## 2. 必須設定項目

### 🔑 **LLM API Key（最低1つ）**
- **OpenAI**: `OPENAI_API_KEY`
- **Anthropic**: `ANTHROPIC_API_KEY`
- **Google**: `GOOGLE_API_KEY`

### 📁 **GitHub設定（必須）**
- **リポジトリURL**: `GITHUB_REPO_URL`
- **アクセストークン**: `GITHUB_TOKEN`

### 🔐 **認証設定**
- **パスワード**: `AUTH_PASSWORD`
- **メールドメイン**: `ALLOWED_EMAIL_DOMAIN`

## 3. API Key取得方法

### OpenAI API Key
1. [OpenAI Platform](https://platform.openai.com/) にログイン
2. 「API Keys」→「Create new secret key」
3. 名前を入力して「Create secret key」
4. 表示されたキーをコピー（一度しか表示されません）

### Anthropic API Key
1. [Anthropic Console](https://console.anthropic.com/) にログイン
2. 「Get API Keys」→「Create Key」
3. 名前を入力して作成
4. 表示されたキーをコピー

### Google Gemini API Key
1. [Google AI Studio](https://ai.google.dev/) にアクセス
2. 「Get API key」→「Create API key」
3. プロジェクトを選択してキーを作成
4. 表示されたキーをコピー

### GitHub Personal Access Token
1. GitHub → 「Settings」→「Developer settings」
2. 「Personal access tokens」→「Tokens (classic)」
3. 「Generate new token」→「repo」権限を選択
4. 表示されたトークンをコピー

## 4. GitHub永続化リポジトリ設定

### データ用リポジトリを作成
1. GitHubで新しいプライベートリポジトリを作成
2. リポジトリ名例: `wiki-chatbot-data`
3. READMEとLFS設定ファイルを追加

### .gitattributes設定
```
*.db filter=lfs diff=lfs merge=lfs -text
*.sqlite filter=lfs diff=lfs merge=lfs -text
*.sqlite3 filter=lfs diff=lfs merge=lfs -text
```

## 5. トラブルシューティング

### よくあるエラー
- **API Key無効**: キーが正しく設定されているか確認
- **GitHub権限エラー**: トークンにrepo権限があるか確認
- **LFS無効**: packages.txtに`git-lfs`が記載されているか確認

### デバッグ設定
```toml
DEBUG_MODE = true  # エラー詳細を表示
```