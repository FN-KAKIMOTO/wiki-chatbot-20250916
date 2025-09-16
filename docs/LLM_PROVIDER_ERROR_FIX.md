# 🚨 LLMプロバイダーエラー修正ガイド

## 🔍 問題の分析

**エラーメッセージ:**
```
回答生成中にエラーが発生しました: プロバイダーが設定されていません
```

**原因:**
1. OpenAI API Key が Streamlit Secrets で正しく設定されていない
2. LLMManagerの初期化時にプロバイダーが認識されていない
3. API Key の取得処理でエラーが発生している

## 🔧 実装した修正

### 1. デバッグ情報の追加

LLMManagerにデバッグログを追加して、問題の原因を特定できるようにしました：

```python
# 初期化時のデバッグ情報
print(f"[LLMManager] 利用可能なプロバイダー: {list(self.providers.keys())}")
print(f"[LLMManager] 現在のプロバイダー: {self.current_provider}")

# API Key確認のデバッグ
api_key = settings.get_api_key("openai")
print(f"[LLMManager] OpenAI API Key 確認: {'有り' if api_key else '無し'}")
```

### 2. エラーハンドリングの改善

より詳細なエラーメッセージを提供するように修正：

```python
def generate_response(self, messages: List[Dict[str, str]], **kwargs):
    if not self.current_provider:
        raise ValueError("プロバイダーが選択されていません。設定画面でLLMプロバイダーを選択してください。")

    if self.current_provider not in self.providers:
        available_providers = list(self.providers.keys())
        if available_providers:
            error_msg = f"プロバイダー '{self.current_provider}' が利用できません。利用可能: {available_providers}"
        else:
            error_msg = "利用可能なプロバイダーがありません。API Keyが正しく設定されているか確認してください。"
        raise ValueError(error_msg)
```

### 3. フォールバック機能の強化

プロバイダーが利用できない場合の処理を改善：

```python
def _load_current_settings(self):
    # デフォルトプロバイダーが利用不可の場合
    if self.providers:
        # 利用可能な最初のプロバイダーを使用
        first_provider = list(self.providers.keys())[0]
        # ... フォールバック処理
    else:
        # 完全にプロバイダーが無い場合の緊急処理
        print(f"[LLMManager] 警告: 利用可能なプロバイダーがありません")
```

## 🔧 トラブルシューティング手順

### Step 1: Streamlit Cloud Secrets確認

1. **Streamlit Cloud管理画面**
   - アプリ → Settings → Secrets

2. **必須設定の確認**
   ```toml
   # 以下が正しく設定されているか確認
   OPENAI_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxx"
   GITHUB_SYNC_ENABLED = true
   GITHUB_DATA_REPO = "https://github.com/username/repo.git"
   GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"
   ```

3. **よくある間違い**
   - API Keyの先頭・末尾にスペースが入っている
   - クォート忘れ（`""`で囲む必要あり）
   - 環境変数名の間違い（`OPENAI_API_KEY`が正確）

### Step 2: デバッグログ確認

アプリを起動して、ターミナルまたはStreamlit Cloudのログで以下を確認：

```
[LLMManager] OpenAI API Key 確認: 有り
[LLMManager] OpenAI プロバイダー初期化成功
[LLMManager] 利用可能なプロバイダー: ['openai']
[LLMManager] 現在のプロバイダー: openai
```

**問題のある場合の表示例:**
```
[LLMManager] OpenAI API Key 確認: 無し
[LLMManager] 利用可能なプロバイダー: []
[LLMManager] 現在のプロバイダー: None
```

### Step 3: ローカル環境での確認

```bash
# ローカルで確認
cd wiki_chatbot
streamlit run app.py

# ターミナルでデバッグログを確認
```

**ローカルでの設定ファイル:**
```toml
# .streamlit/secrets.toml
OPENAI_API_KEY = "sk-your-actual-key-here"
```

### Step 4: API Key有効性確認

```python
# API Keyが正しく動作するかテスト
import openai
import streamlit as st

client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Hello"}],
    max_tokens=10
)
print(response.choices[0].message.content)
```

## 🚀 解決後の確認事項

### 1. 正常動作の確認

- ✅ アプリが正常に起動する
- ✅ チャット画面でメッセージを送信できる
- ✅ RAGデータからの情報取得ができる
- ✅ LLMによる回答生成ができる

### 2. ログ出力の確認

```
[LLMManager] 利用可能なプロバイダー: ['openai']
[LLMManager] 現在のプロバイダー: openai
[LLMManager] 現在のモデル: gpt-3.5-turbo
[LLMManager] generate_response 呼び出し
```

### 3. エラーメッセージの改善

修正前:
```
回答生成中にエラーが発生しました: プロバイダーが設定されていません
```

修正後:
```
利用可能なプロバイダーがありません。API Keyが正しく設定されているか確認してください。
```

## 📝 追加の推奨事項

### 1. 本番環境での監視

```python
# アプリ起動時にAPI Key設定状況を表示
def check_llm_provider_status():
    """LLMプロバイダーの設定状況を確認"""
    manager = LLMManager()
    if not manager.providers:
        st.error("❌ LLMプロバイダーが設定されていません")
        st.info("💡 設定画面でOpenAI API Keyを確認してください")
    else:
        st.success(f"✅ 利用可能なプロバイダー: {list(manager.providers.keys())}")
```

### 2. ユーザー向けエラーメッセージ

```python
def user_friendly_error_handler(error):
    """ユーザーフレンドリーなエラーメッセージ"""
    if "プロバイダーが設定されていません" in str(error):
        return """
        🚨 **LLM設定エラー**

        OpenAI API Keyが正しく設定されていない可能性があります。

        **解決方法:**
        1. OpenAI API Keyが有効であることを確認
        2. Streamlit Secrets設定を確認
        3. アプリを再起動

        **サポートが必要な場合は管理者にお問い合わせください。**
        """
    return str(error)
```

### 3. 定期的なヘルスチェック

```python
def llm_health_check():
    """LLMプロバイダーのヘルスチェック"""
    try:
        manager = LLMManager()
        if manager.current_provider:
            # 簡単なテストメッセージで動作確認
            response = manager.generate_response([
                {"role": "user", "content": "Hello"}
            ])
            return True, "LLMプロバイダー正常"
    except Exception as e:
        return False, f"LLMプロバイダーエラー: {e}"

    return False, "LLMプロバイダー未設定"
```

---

**この修正により、「プロバイダーが設定されていません」エラーの原因特定と解決が容易になります。** 🎉