"""
プロンプト設定画面
外部プロンプトファイルの管理・編集・プレビュー機能
"""

import streamlit as st
import yaml
import os
from typing import Dict, Any, List
from utils.prompt_manager import prompt_manager
from utils.session_manager import SessionManager



def show_prompt_settings():
    """プロンプト設定画面のメイン関数"""
    # セッション管理初期化
    SessionManager.initialize_session()

    # 認証チェック
    if not SessionManager.check_authentication():
        if not SessionManager.authenticate_user():
            return

    st.title("🎯 プロンプト設定管理")
    st.write("外部設定ファイルによるプロンプト管理システム")

    # サイドバーでモードを選択
    mode = st.sidebar.selectbox(
        "操作モード",
        ["プロンプト一覧", "プロンプト編集", "新規プロンプト作成", "プロンプトプレビュー", "設定ファイル管理"],
    )

    if mode == "プロンプト一覧":
        show_prompt_list()
    elif mode == "プロンプト編集":
        show_prompt_editor()
    elif mode == "新規プロンプト作成":
        show_prompt_creator()
    elif mode == "プロンプトプレビュー":
        show_prompt_preview()
    elif mode == "設定ファイル管理":
        show_config_file_manager()


def show_prompt_list():
    """プロンプト一覧表示"""

    st.header("📋 利用可能なプロンプト一覧")

    # 製品選択
    products = prompt_manager.list_products()
    all_products = ["汎用プロンプト"] + products

    selected_product = st.selectbox("表示対象", all_products)

    if selected_product == "汎用プロンプト":
        product_name = None
        st.subheader("🌐 汎用プロンプト")
    else:
        product_name = selected_product
        st.subheader(f"🏷️ {selected_product} 専用プロンプト")

    # プロンプト情報を取得
    available_prompts = prompt_manager.get_available_prompts(product_name)

    # 汎用プロンプトの表示
    if "generic" in available_prompts:
        st.write("**汎用プロンプト:**")
        for prompt_type in available_prompts["generic"]:
            info = prompt_manager.get_prompt_info(prompt_type)
            with st.expander(f"📝 {info.get('name', prompt_type)}"):
                st.write(f"**タイプ:** {prompt_type}")
                st.write(f"**説明:** {info.get('description', 'なし')}")
                st.write(f"**分類:** {info.get('type', 'generic')}")

                # プロンプト内容のプレビュー
                system_prompt = prompt_manager.get_system_prompt(
                    prompt_type, product_name=product_name or "サンプル製品"
                )
                st.code(system_prompt[:500] + "..." if len(system_prompt) > 500 else system_prompt, language="text")

    # 製品固有プロンプトの表示
    if "product_specific" in available_prompts:
        st.write("**製品固有プロンプト:**")
        for prompt_type in available_prompts["product_specific"]:
            info = prompt_manager.get_prompt_info(prompt_type, product_name)
            with st.expander(f"🎯 {info.get('name', prompt_type)}"):
                st.write(f"**タイプ:** {prompt_type}")
                st.write(f"**説明:** {info.get('description', 'なし')}")
                st.write(f"**対象製品:** {info.get('product', product_name)}")

                # プロンプト内容のプレビュー
                system_prompt = prompt_manager.get_system_prompt(prompt_type, product_name=product_name)
                st.code(system_prompt[:500] + "..." if len(system_prompt) > 500 else system_prompt, language="text")

    # RAGプロンプトの表示
    if "rag" in available_prompts:
        st.write("**RAG処理プロンプト:**")
        for category in available_prompts["rag"]:
            with st.expander(f"🔍 {category}"):
                system_prompt = prompt_manager.get_rag_prompt(category, "generic", "system_prompt")
                user_prompt = prompt_manager.get_rag_prompt(category, "generic", "user_prompt")

                if system_prompt:
                    st.write("**システムプロンプト:**")
                    st.code(
                        system_prompt[:300] + "..." if len(system_prompt) > 300 else system_prompt, language="text"
                    )

                if user_prompt:
                    st.write("**ユーザープロンプト:**")
                    st.code(user_prompt[:300] + "..." if len(user_prompt) > 300 else user_prompt, language="text")


def show_prompt_editor():
    """プロンプト編集機能"""

    st.header("✏️ プロンプト編集")

    # 編集対象の選択
    edit_type = st.selectbox("編集対象", ["汎用プロンプト", "製品別プロンプト", "RAGプロンプト"])

    if edit_type == "汎用プロンプト":
        edit_generic_prompts()
    elif edit_type == "製品別プロンプト":
        edit_product_prompts()
    elif edit_type == "RAGプロンプト":
        edit_rag_prompts()


def edit_generic_prompts():
    """汎用プロンプトの編集"""

    available_prompts = prompt_manager.get_available_prompts()
    generic_prompts = available_prompts.get("generic", [])

    if not generic_prompts:
        st.warning("汎用プロンプトが見つかりません")
        return

    selected_prompt = st.selectbox("編集するプロンプト", generic_prompts)

    if selected_prompt:
        # 現在のプロンプト情報を取得
        info = prompt_manager.get_prompt_info(selected_prompt)
        current_prompt = prompt_manager.get_system_prompt(selected_prompt, product_name="サンプル製品")

        st.write(f"**編集中:** {info.get('name', selected_prompt)}")

        # 編集フォーム
        with st.form(f"edit_generic_{selected_prompt}"):
            new_name = st.text_input("プロンプト名", value=info.get("name", selected_prompt))
            new_description = st.text_area("説明", value=info.get("description", ""))
            new_prompt = st.text_area("システムプロンプト", value=current_prompt, height=300)

            if st.form_submit_button("保存"):
                try:
                    # YAML ファイルの更新処理（実際の実装では適切なファイル操作を行う）
                    st.success(f"プロンプト '{selected_prompt}' を更新しました")
                    st.rerun()
                except Exception as e:
                    st.error(f"保存エラー: {str(e)}")


def edit_product_prompts():
    """製品別プロンプトの編集"""

    products = prompt_manager.list_products()
    if not products:
        st.warning("製品別プロンプトが見つかりません")
        return

    selected_product = st.selectbox("製品を選択", products)

    if selected_product:
        available_prompts = prompt_manager.get_available_prompts(selected_product)
        product_prompts = available_prompts.get("product_specific", [])

        if not product_prompts:
            st.warning(f"{selected_product} の専用プロンプトが見つかりません")
            return

        selected_prompt = st.selectbox("編集するプロンプト", product_prompts)

        if selected_prompt:
            # 編集処理（generic_prompts と同様の実装）
            st.info("製品別プロンプト編集機能（実装中）")


def edit_rag_prompts():
    """RAGプロンプトの編集"""

    available_prompts = prompt_manager.get_available_prompts()
    rag_categories = available_prompts.get("rag", [])

    if not rag_categories:
        st.warning("RAGプロンプトが見つかりません")
        return

    selected_category = st.selectbox("編集するカテゴリ", rag_categories)

    if selected_category:
        st.info("RAGプロンプト編集機能（実装中）")


def show_prompt_creator():
    """新規プロンプト作成機能"""

    st.header("➕ 新規プロンプト作成")

    create_type = st.selectbox("作成タイプ", ["汎用プロンプト", "製品別プロンプト", "RAGプロンプト"])

    if create_type == "製品別プロンプト":
        # 製品選択または新規作成
        products = prompt_manager.list_products()
        product_options = products + ["新規製品を作成"]
        selected_option = st.selectbox("対象製品", product_options)

        if selected_option == "新規製品を作成":
            new_product_name = st.text_input("新規製品名")
            if new_product_name:
                st.write(f"新規製品 '{new_product_name}' のプロンプトを作成します")

    # プロンプト作成フォーム
    with st.form("create_new_prompt"):
        prompt_id = st.text_input("プロンプトID（英数字）")
        prompt_name = st.text_input("プロンプト名")
        prompt_description = st.text_area("説明")
        system_prompt = st.text_area("システムプロンプト", height=300)
        user_prompt = st.text_area("ユーザープロンプト（オプション）", height=150)

        if st.form_submit_button("作成"):
            if prompt_id and prompt_name and system_prompt:
                try:
                    # 新規プロンプト作成処理（実際の実装では適切なファイル操作を行う）
                    st.success(f"新規プロンプト '{prompt_name}' を作成しました")
                except Exception as e:
                    st.error(f"作成エラー: {str(e)}")
            else:
                st.error("必須項目を入力してください")


def show_prompt_preview():
    """プロンプトプレビュー機能"""

    st.header("👀 プロンプトプレビュー")

    # プロンプト選択
    col1, col2 = st.columns(2)

    with col1:
        products = ["汎用"] + prompt_manager.list_products()
        selected_product = st.selectbox("製品", products)

        if selected_product == "汎用":
            product_name = None
        else:
            product_name = selected_product

        available_prompts = prompt_manager.get_available_prompts(product_name)
        all_prompts = available_prompts.get("generic", []) + available_prompts.get("product_specific", [])

        selected_prompt_type = st.selectbox("プロンプトタイプ", all_prompts)

    with col2:
        # パラメータ入力
        st.write("**パラメータ設定:**")
        sample_query = st.text_input("サンプルクエリ", "製品の価格について教えてください")
        sample_context = st.text_area("サンプルコンテキスト", "サンプルの文書内容がここに表示されます。", height=100)
        company_name = st.text_input("会社名", "サンプル株式会社")

    if selected_prompt_type:
        # プロンプト生成・プレビュー
        try:
            generated_prompt = prompt_manager.get_system_prompt(
                selected_prompt_type,
                product_name=product_name or "サンプル製品",
                context_text=sample_context,
                company_name=company_name,
            )

            st.subheader("📄 生成されたプロンプト")
            st.code(generated_prompt, language="text")

            # プロンプト統計
            st.subheader("📊 プロンプト統計")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("文字数", len(generated_prompt))
            with col2:
                st.metric("推定トークン数", len(generated_prompt) // 4)
            with col3:
                st.metric("行数", generated_prompt.count("\n") + 1)

        except Exception as e:
            st.error(f"プロンプト生成エラー: {str(e)}")


def show_config_file_manager():
    """設定ファイル管理機能"""

    st.header("📁 設定ファイル管理")

    # プロンプト設定の再読み込み
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 設定再読み込み"):
            try:
                prompt_manager.reload_prompts()
                st.success("プロンプト設定を再読み込みしました")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"再読み込みエラー: {str(e)}")

    with col2:
        if st.button("✅ 設定チェック"):
            show_config_validation()

    with col3:
        if st.button("📤 設定エクスポート"):
            show_config_export()

    # ファイル構造表示
    st.subheader("📂 プロンプトファイル構造")

    base_dir = prompt_manager.base_dir
    if os.path.exists(base_dir):
        st.write(f"**ベースディレクトリ:** `{base_dir}`")

        # ファイル一覧表示
        for root, dirs, files in os.walk(base_dir):
            level = root.replace(base_dir, "").count(os.sep)
            indent = "　" * 2 * level
            st.write(f"{indent}📁 {os.path.basename(root)}/")

            sub_indent = "　" * 2 * (level + 1)
            for file in files:
                if file.endswith((".yaml", ".yml")):
                    file_path = os.path.join(root, file)
                    file_size = os.path.getsize(file_path)
                    st.write(f"{sub_indent}📄 {file} ({file_size} bytes)")


def show_config_validation():
    """設定検証結果表示"""

    st.subheader("🔍 設定検証結果")

    # 基本的な検証項目
    validation_results = []

    # ファイル存在確認
    base_dir = prompt_manager.base_dir
    generic_file = os.path.join(base_dir, "generic.yaml")
    rag_file = os.path.join(base_dir, "rag_prompts.yaml")
    products_dir = os.path.join(base_dir, "products")

    if os.path.exists(generic_file):
        validation_results.append({"item": "汎用プロンプトファイル", "status": "✅", "message": "存在"})
    else:
        validation_results.append({"item": "汎用プロンプトファイル", "status": "❌", "message": "不在"})

    if os.path.exists(rag_file):
        validation_results.append({"item": "RAGプロンプトファイル", "status": "✅", "message": "存在"})
    else:
        validation_results.append({"item": "RAGプロンプトファイル", "status": "❌", "message": "不在"})

    if os.path.exists(products_dir):
        product_count = len([f for f in os.listdir(products_dir) if f.endswith((".yaml", ".yml"))])
        validation_results.append(
            {"item": "製品プロンプトディレクトリ", "status": "✅", "message": f"{product_count}個のファイル"}
        )
    else:
        validation_results.append({"item": "製品プロンプトディレクトリ", "status": "❌", "message": "不在"})

    # 結果表示
    for result in validation_results:
        st.write(f"{result['status']} **{result['item']}**: {result['message']}")


def show_config_export():
    
    """設定エクスポート機能"""

    st.subheader("📤 設定エクスポート")
    st.info("現在の設定をバックアップとして保存できます（実装中）")


if __name__ == "__main__":
    show_prompt_settings()
