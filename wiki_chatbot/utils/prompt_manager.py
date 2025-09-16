"""汎用および製品固有プロンプトの統合処理用プロンプト管理システム。

このモジュールは、Wikiチャットボットアプリケーションのプロンプトテンプレートシステムの
中核を担います。階層的な優先順位システムを通じて、柔軟で拡張可能なプロンプト管理を実現します。

主要機能:
    1. 階層的プロンプト管理:
        - 汎用プロンプト: 全製品で共通利用可能な基本プロンプト
        - 製品固有プロンプト: 特定製品向けにカスタマイズされたプロンプト
        - RAGプロンプト: Retrieval-Augmented Generation用の特殊プロンプト

    2. 動的優先順位システム:
        製品固有 > 汎用 > デフォルト の順序で適用
        製品固有プロンプトが存在する場合は汎用プロンプトより優先

    3. テンプレート変数展開:
        プロンプト内の{変数名}を動的に置換
        会社名、製品名、コンテキスト等の柔軟な展開をサポート

    4. YAML設定ファイル管理:
        - config/prompts/generic.yaml: 汎用プロンプト定義
        - config/prompts/products/*.yaml: 製品別プロンプト定義
        - config/prompts/rag_prompts.yaml: RAG用プロンプト定義

技術仕様:
    - YAMLベースの設定管理
    - ログベースのエラーハンドリング
    - フォールバック機能による堅牢性確保
    - プロンプト再読み込み機能

使用例:
    ```python
    from utils.prompt_manager import prompt_manager

    # 基本的なシステムプロンプト取得
    system_prompt = prompt_manager.get_system_prompt(
        "general",
        product_name="サンプル商品",
        context_text="参考情報"
    )

    # 製品固有プロンプト取得
    custom_prompt = prompt_manager.get_system_prompt(
        "custom_inquiry",
        product_name="商品A"
    )

    # RAGプロンプト取得
    rag_prompt = prompt_manager.get_rag_prompt(
        category="summarization",
        variant="detailed",
        context_text="要約対象テキスト"
    )
    ```

設計思想:
    このシステムは、多様な製品やサービスに対応できる柔軟なプロンプト管理を目指しています。
    単一のプロンプト管理システムで、汎用性と特殊性のバランスを取り、
    運用効率と回答品質の両立を実現します。
"""

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class PromptConfig:
    """プロンプト設定用設定データクラス。

    単一のプロンプトテンプレートの設定情報を格納するデータクラスです。
    システムプロンプトとユーザープロンプトの両方を管理し、
    メタデータ（名前、説明）も含めて統合的に管理します。

    Attributes:
        name: プロンプトの人間が読みやすい名前
              UIでの表示や設定管理で使用
        description: プロンプトの用途と目的の詳細説明
                    管理者がプロンプトの意図を理解するために使用
        system_prompt: LLMに送信されるシステムプロンプトテンプレート
                      {変数名}形式での変数展開をサポート
        user_prompt: ユーザー入力と組み合わせて使用されるプロンプトテンプレート
                    通常は空文字列で、特殊な用途でのみ使用

    使用例:
        一般的な問い合わせ用プロンプト:
        PromptConfig(
            name="一般的な問い合わせ対応",
            description="製品に関する基本的な質問への回答用",
            system_prompt="あなたは{product_name}の専門アシスタントです...",
            user_prompt=""
        )
    """

    name: str
    description: str = ""
    system_prompt: str = ""
    user_prompt: str = ""


class PromptManager:
    """階層優先システムでプロンプトテンプレートを管理するクラス。

    このクラスは、Wikiチャットボットシステムの中核となるプロンプト管理機能を提供します。
    複数の階層（汎用、製品固有、RAG特化）にわたるプロンプトを統合管理し、
    動的な優先順位システムを通じて最適なプロンプトを選択・適用します。

    主要責務:
        1. プロンプト設定の階層管理:
            - 汎用プロンプト: 全製品共通で使用可能な基本プロンプト
            - 製品固有プロンプト: 特定製品向けのカスタマイズプロンプト
            - RAGプロンプト: Retrieval-Augmented Generation用の特殊プロンプト

        2. 動的優先順位制御:
            製品固有 > 汎用 > デフォルト の優先順位で適用
            製品固有プロンプトが存在する場合は汎用プロンプトをオーバーライド

        3. テンプレート変数の動的展開:
            プロンプト内の{変数名}を実行時に動的置換
            製品名、会社名、コンテキスト情報等を柔軟に埋め込み

        4. エラーハンドリングとフォールバック:
            設定ファイル読み込みエラー時の安全なフォールバック
            変数不足時のデフォルト値自動補完

    技術的特徴:
        - YAMLベースの設定ファイルサポート
        - ログベースの詳細エラー追跡
        - プロンプト再読み込み機能（開発・運用時のメンテナンス性向上）
        - スレッドセーフな設計（将来の並行処理対応）

    データ構造:
        - generic_prompts: 汎用プロンプトの辞書（prompt_id -> PromptConfig）
        - product_prompts: 製品固有プロンプトの階層辞書
        - rag_prompts: RAG用プロンプトの分類別辞書

    使用パターン:
        基本的な使用では、get_system_prompt()メソッドを使用して
        製品名とプロンプトタイプを指定するだけで最適なプロンプトが取得されます。
        システムが自動的に優先順位を判定し、適切なプロンプトを選択・適用します。
    """

    def __init__(self, base_dir: Optional[str] = None) -> None:
        """PromptManagerを初期化する。

        プロンプト管理システムの初期化を行います。設定ファイルの読み込みから
        内部データ構造の構築まで、すべての初期化処理を自動実行します。

        Args:
            base_dir: プロンプト設定ファイルを含むベースディレクトリパス
                     Noneを指定した場合、このファイルからの相対パス
                     'config/prompts'をデフォルトとして使用

        初期化処理フロー:
            1. ベースディレクトリの設定・検証
            2. 内部データ構造の初期化
            3. ログシステムの初期化
            4. 設定ファイルの一括読み込み実行

        内部データ構造:
            - generic_prompts: 汎用プロンプトの格納辞書
            - product_prompts: 製品固有プロンプトの階層格納辞書
            - rag_prompts: RAG用プロンプトの分類別格納辞書
            - logger: エラー追跡・デバッグ用ログオブジェクト

        Note:
            初期化時に設定ファイルが見つからない場合でも、
            エラーは発生せず、空の設定で起動します。
            これにより、開発環境でのプロンプト設定前でも
            システムが動作することを保証します。
        """
        # ベースディレクトリの設定
        if base_dir is None:
            base_dir = os.path.join(os.path.dirname(__file__), "..", "config", "prompts")

        # インスタンス変数の初期化
        self.base_dir: str = base_dir                              # プロンプト設定ファイルのベースディレクトリ
        self.generic_prompts: Dict[str, PromptConfig] = {}         # 汎用プロンプト格納辞書
        self.product_prompts: Dict[str, Dict[str, Any]] = {}       # 製品固有プロンプト階層格納辞書
        self.rag_prompts: Dict[str, Dict[str, PromptConfig]] = {}  # RAG用プロンプト分類別格納辞書
        self.logger: logging.Logger = logging.getLogger(__name__) # ログ管理オブジェクト

        # プロンプト設定の一括読み込み実行
        self._load_all_prompts()

    def _load_all_prompts(self) -> None:
        """すべてのプロンプト設定ファイルを読み込む。

        以下の順序でプロンプトを読み込みます：
        1. generic.yamlからの汎用プロンプト
        2. products/ディレクトリからの製品固有プロンプト
        3. rag_prompts.yamlからのRAG固有プロンプト

        Raises:
            Exception: 重要なプロンプトファイルを読み込めない場合。
        """
        try:
            # Load generic prompts
            self._load_generic_prompts()

            # Load product-specific prompts
            self._load_product_prompts()

            # Load RAG-specific prompts
            self._load_rag_prompts()

            self.logger.info(
                f"Prompt loading completed: "
                f"generic={len(self.generic_prompts)}, "
                f"product={len(self.product_prompts)}, "
                f"rag={len(self.rag_prompts)}"
            )

        except Exception as e:
            self.logger.error(f"Prompt loading error: {str(e)}")
            raise

    def _load_generic_prompts(self):
        """汎用プロンプトの読み込み"""
        generic_file = os.path.join(self.base_dir, "generic.yaml")
        if os.path.exists(generic_file):
            with open(generic_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            for prompt_id, config in data.items():
                self.generic_prompts[prompt_id] = PromptConfig(
                    name=config.get("name", prompt_id),
                    description=config.get("description", ""),
                    system_prompt=config.get("system_prompt", ""),
                    user_prompt=config.get("user_prompt", ""),
                )

    def _load_product_prompts(self):
        """製品別プロンプトの読み込み"""
        products_dir = os.path.join(self.base_dir, "products")
        if not os.path.exists(products_dir):
            return

        for filename in os.listdir(products_dir):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                product_id = filename.replace(".yaml", "").replace(".yml", "")
                filepath = os.path.join(products_dir, filename)

                with open(filepath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                product_name = data.get("product_name", product_id)
                product_context = data.get("product_specific_context", "")

                self.product_prompts[product_id] = {
                    "product_name": product_name,
                    "product_context": product_context,
                    "prompts": {},
                }

                # 各プロンプトを処理
                for prompt_id, config in data.items():
                    if prompt_id not in ["product_name", "product_specific_context"]:
                        self.product_prompts[product_id]["prompts"][prompt_id] = PromptConfig(
                            name=config.get("name", prompt_id),
                            description=config.get("description", ""),
                            system_prompt=config.get("system_prompt", ""),
                            user_prompt=config.get("user_prompt", ""),
                        )

    def _load_rag_prompts(self):
        """RAG用プロンプトの読み込み"""
        rag_file = os.path.join(self.base_dir, "rag_prompts.yaml")
        if os.path.exists(rag_file):
            with open(rag_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            for category, prompts in data.items():
                self.rag_prompts[category] = {}
                for variant, config in prompts.items():
                    self.rag_prompts[category][variant] = PromptConfig(
                        name=config.get("name", f"{category}_{variant}"),
                        description=config.get("description", ""),
                        system_prompt=config.get("system_prompt", ""),
                        user_prompt=config.get("user_prompt", ""),
                    )

    def get_system_prompt(self, prompt_type: str, product_name: Optional[str] = None, **kwargs: Any) -> str:
        """製品固有優先でシステムプロンプトを取得する。

        階層アプローチを使用して適切なシステムプロンプトを取得します：
        1. 製品固有プロンプト（最高優先）
        2. 汎用プロンプト（フォールバック）
        3. デフォルトシステムプロンプト（最終フォールバック）

        Args:
            prompt_type: 取得するプロンプトのタイプ/ID。
            product_name: 製品固有プロンプト用の製品名。
            **kwargs: プロンプトテンプレート置換用の追加変数。
                     一般的な変数には以下が含まれます：
                     - context_text: プロンプト用のRAGコンテキスト
                     - company_name: パーソナライズ用の会社名

        Returns:
            変数が置換されたフォーマット済みシステムプロンプト文字列。
        """
        # 1. Check for product-specific prompt
        if product_name and self._has_product_prompt(product_name, prompt_type):
            product_id = self._get_product_id(product_name)
            product_prompt = self.product_prompts[product_id]["prompts"][prompt_type]

            # Add product-specific context
            product_context = self.product_prompts[product_id]["product_context"]
            if product_context:
                kwargs["product_specific_context"] = product_context

            return self._format_prompt(product_prompt.system_prompt, product_name=product_name, **kwargs)

        # 2. Use generic prompt
        if prompt_type in self.generic_prompts:
            generic_prompt = self.generic_prompts[prompt_type]
            return self._format_prompt(generic_prompt.system_prompt, product_name=product_name or "システム", **kwargs)

        # 3. Default prompt
        return self._get_default_system_prompt(product_name or "システム", **kwargs)

    def get_user_prompt(self, prompt_type: str, product_name: str = None, **kwargs) -> str:
        """ユーザープロンプトを取得（製品別優先）"""

        # 1. 製品別プロンプトを確認
        if product_name and self._has_product_prompt(product_name, prompt_type):
            product_id = self._get_product_id(product_name)
            product_prompt = self.product_prompts[product_id]["prompts"][prompt_type]
            if product_prompt.user_prompt:
                return self._format_prompt(product_prompt.user_prompt, product_name=product_name, **kwargs)

        # 2. 汎用プロンプトを使用
        if prompt_type in self.generic_prompts:
            generic_prompt = self.generic_prompts[prompt_type]
            if generic_prompt.user_prompt:
                return self._format_prompt(generic_prompt.user_prompt, product_name=product_name, **kwargs)

        return ""

    def get_rag_prompt(
        self, category: str, variant: str = "generic", prompt_part: str = "system_prompt", **kwargs
    ) -> str:
        """RAG用プロンプトを取得"""

        if category in self.rag_prompts and variant in self.rag_prompts[category]:
            prompt_config = self.rag_prompts[category][variant]
            prompt_text = getattr(prompt_config, prompt_part, "")
            return self._format_prompt(prompt_text, **kwargs)

        return ""

    def _has_product_prompt(self, product_name: str, prompt_type: str) -> bool:
        """製品別プロンプトが存在するかチェック"""
        product_id = self._get_product_id(product_name)
        return product_id in self.product_prompts and prompt_type in self.product_prompts[product_id]["prompts"]

    def _get_product_id(self, product_name: str) -> str:
        """製品名から製品IDを取得"""
        # 製品名が直接IDとして使用されている場合
        if product_name in self.product_prompts:
            return product_name

        # 製品名から対応するIDを検索
        for product_id, config in self.product_prompts.items():
            if config["product_name"] == product_name:
                return product_id

        # 見つからない場合は製品名をそのまま返す
        return product_name

    def _format_prompt(self, template: str, **kwargs) -> str:
        """プロンプトテンプレートに変数を代入"""
        try:
            # デフォルト値を設定
            default_values = {
                "product_name": kwargs.get("product_name", "システム"),
                "company_name": kwargs.get("company_name", "サンプル株式会社"),
                "context_text": kwargs.get("context_text", ""),
                "product_specific_context": kwargs.get("product_specific_context", ""),
            }
            # 引数の値で上書き
            default_values.update(kwargs)

            return template.format(**default_values)
        except KeyError as e:
            self.logger.warning(f"プロンプトテンプレート変数不足: {e}")
            # 不足変数をデフォルト値で補完して再試行
            missing_vars = {
                "product_name": "システム",
                "company_name": "サンプル株式会社",
                "context_text": "",
                "product_specific_context": "",
            }
            missing_vars.update(kwargs)
            try:
                return template.format(**missing_vars)
            except:
                return template
        except Exception as e:
            self.logger.error(f"プロンプトフォーマットエラー: {e}")
            return template

    def _get_default_system_prompt(self, product_name: str, **kwargs) -> str:
        """デフォルトのシステムプロンプト"""
        context_text = kwargs.get("context_text", "")
        return f"""あなたは{product_name}に関する社内Wiki検索アシスタントです。
提供された情報源を基に、正確で役立つ回答を提供してください。

回答時の注意点:
1. 提供された情報源の内容のみを使用してください
2. 情報が不足している場合は、素直にその旨を伝えてください
3. 日本語で丁寧に回答してください
4. 回答の最後に参考にした情報源を明記してください

情報源:
{context_text}"""

    def get_available_prompts(self, product_name: str = None) -> Dict[str, List[str]]:
        """利用可能なプロンプト一覧を取得"""
        result = {"generic": list(self.generic_prompts.keys()), "rag": list(self.rag_prompts.keys())}

        if product_name:
            product_id = self._get_product_id(product_name)
            if product_id in self.product_prompts:
                result["product_specific"] = list(self.product_prompts[product_id]["prompts"].keys())

        return result

    def get_prompt_info(self, prompt_type: str, product_name: str = None) -> Dict[str, str]:
        """プロンプト情報を取得"""
        # 製品別プロンプトを確認
        if product_name and self._has_product_prompt(product_name, prompt_type):
            product_id = self._get_product_id(product_name)
            prompt = self.product_prompts[product_id]["prompts"][prompt_type]
            return {
                "name": prompt.name,
                "description": prompt.description,
                "type": "product_specific",
                "product": product_name,
            }

        # 汎用プロンプトを確認
        if prompt_type in self.generic_prompts:
            prompt = self.generic_prompts[prompt_type]
            return {"name": prompt.name, "description": prompt.description, "type": "generic"}

        return {}

    def reload_prompts(self):
        """プロンプトを再読み込み"""
        self.generic_prompts.clear()
        self.product_prompts.clear()
        self.rag_prompts.clear()
        self._load_all_prompts()
        self.logger.info("プロンプトを再読み込みしました")

    def list_products(self) -> List[str]:
        """製品一覧を取得"""
        products = []
        for product_id, config in self.product_prompts.items():
            products.append(config["product_name"])
        return products


# グローバルインスタンス
prompt_manager = PromptManager()
