# 設定優先度ガイド

## 必須設定（アプリが動作するために必要）

### 🔴 **最優先（必須）**
1. **LLM API Key**: 最低1つは必要
   - `OPENAI_API_KEY` (推奨)
   - `ANTHROPIC_API_KEY`
   - `GOOGLE_API_KEY`

2. **GitHub永続化**:
   - `GITHUB_REPO_URL`
   - `GITHUB_TOKEN`

### 🟡 **重要（推奨）**
3. **認証設定**:
   - `AUTH_PASSWORD`
   - `ALLOWED_EMAIL_DOMAIN`

### 🟢 **オプション（カスタマイズ）**
4. **自動バックアップ**:
   - `BACKUP_INTERVAL_MESSAGES = 10`

5. **システム設定**:
   - `DEBUG_MODE = true`
   - `APP_TITLE = "アプリ名"`

## 設定例

### 開発環境
```toml
# 基本設定
OPENAI_API_KEY = "sk-..."
GITHUB_REPO_URL = "https://github.com/user/repo.git"
GITHUB_TOKEN = "ghp_..."
AUTH_PASSWORD = "dev123"
ALLOWED_EMAIL_DOMAIN = "yourcompany.com"

# 開発用設定
DEBUG_MODE = true
BACKUP_INTERVAL_MESSAGES = 5  # 開発時は頻繁にバックアップ
```

### 本番環境
```toml
# 基本設定（同上）
OPENAI_API_KEY = "sk-..."
GITHUB_REPO_URL = "https://github.com/user/repo.git"
GITHUB_TOKEN = "ghp_..."
AUTH_PASSWORD = "secure_password_123"
ALLOWED_EMAIL_DOMAIN = "yourcompany.com"

# 本番用設定
DEBUG_MODE = false
BACKUP_INTERVAL_MESSAGES = 20  # 本番では適度な間隔
DAILY_QUERY_LIMIT = 200
```