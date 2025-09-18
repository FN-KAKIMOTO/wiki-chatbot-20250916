# -*- coding: utf-8 -*-
"""管理画面モジュール。

このモジュールは、WikiチャットボットアプリケーションのStreamlitベース
管理インターフェースを提供します。ファイル管理、チャット分析、
データエクスポート機能を統合的に管理し、運用担当者が効率的に
システムの管理・監視を行えるツールを実装しています。

主要機能:
    1. ファイル管理:
        - 商材別ファイルの登録・削除
        - 複数ファイル形式のサポート
        - RAGデータベースの直接管理
        - ファイル状況の可視化

    2. チャット利用分析:
        - 商材別の利用統計
        - 満足度・評価の分析
        - トレンド分析とKPI表示
        - 詳細フィードバックの確認

    3. データエクスポート:
        - チャット履歴の一括出力
        - フィードバックデータの抽出
        - CSV/JSON形式での出力
        - 分析用データの提供

技術仕様:
    - StreamlitのマルチページUI
    - リアルタイムデータ可視化
    - 安全なファイル操作（確認付き削除）
    - エラーハンドリング付きの堅牢な処理

設計思想:
    運用担当者の日常業務を効率化するため、直感的で分かりやすい
    インターフェースを提供し、複雑な管理作業を簡単な操作で
    実行できるよう設計されています。

使用例:
    このモジュールはStreamlitページとして動作し、
    ブラウザから直接アクセスして使用します:
    ```
    streamlit run pages/admin.py
    ```

セキュリティ考慮事項:
    - 管理機能への適切なアクセス制限
    - ファイル削除の確認プロセス
    - データエクスポート時の個人情報保護
"""

import streamlit as st
import sys
import os

# パスを追加（utilsモジュールをインポートするため）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.file_handler import FileHandler
from utils.feedback_manager import feedback_manager
from utils.session_manager import SessionManager



def main():
    """管理画面のメイン関数。

    Streamlitベースの管理画面を初期化し、メイン機能を提供します。
    サイドバーによるナビゲーションと、選択された機能に応じた
    メイン画面の動的切り替えを管理します。

    画面構成:
        1. サイドバー:
            - 機能選択メニュー
            - サポートファイル形式の情報
            - 使い方ガイド

        2. メイン画面:
            - 選択された管理機能の実行
            - ファイル管理/チャット分析/データエクスポート

    初期化処理:
        - Streamlitページ設定の適用
        - FileHandlerの初期化
        - UI要素の配置

    Note:
        この関数は管理画面全体の制御フローを管理し、
        各個別機能は専用の関数に委譲されます。
    """
    # セッション管理初期化
    SessionManager.initialize_session()
    # 認証チェック
    if not SessionManager.check_authentication():
        if not SessionManager.authenticate_user():
            return
    st.set_page_config(page_title="管理画面 - Wiki Chatbot", page_icon="🛠️", layout="wide")

    # サイドバーの構築
    st.sidebar.title("🛠️ 管理画面")
    st.sidebar.markdown("---")

    # 管理メニューの選択インターフェース
    admin_mode = st.sidebar.selectbox(
        "管理機能を選択", ["📁 ファイル管理", "📊 チャット分析", "📥 データエクスポート"]
    )

    # ファイルハンドラーの初期化（ファイル処理とRAG管理に使用）
    file_handler = FileHandler()

    # サポートファイル形式の情報表示（ユーザビリティ向上）
    st.sidebar.subheader("📋 サポートファイル形式")
    formats = file_handler.get_supported_formats_info()
    for ext, desc in formats.items():
        st.sidebar.write(f"• **{ext.upper()}**: {desc}")

    # メイン画面での機能実行（選択に基づく動的切り替え）
    if admin_mode == "📁 ファイル管理":
        file_handler.product_management_interface()
    elif admin_mode == "📊 チャット分析":
        show_chat_analytics()
    elif admin_mode == "📥 データエクスポート":
        show_data_export()

    # 使い方ガイドの表示（操作支援）
    st.sidebar.markdown("---")
    st.sidebar.subheader("📖 使い方")
    st.sidebar.write(
        """
    1. **商材を選択または新規作成**
    2. **ファイルをアップロード**
       - 複数ファイル同時アップロード可能
       - サポート形式: TXT, PDF, DOCX, HTML, CSV
    3. **不要なファイルを削除**
       - 削除は確認が必要（2回クリック）
    4. **チャット画面で動作確認**
    """
    )


def show_chat_analytics():
    """チャット利用分析画面を表示する。

    チャットボットの利用状況、ユーザーフィードバック、満足度などの
    統計情報を可視化・分析するダッシュボードを提供します。

    主要機能:
        1. KPI表示:
            - 総セッション数
            - 満足度率
            - 平均評価スコア
            - 利用頻度分析

        2. 商材別分析:
            - 個別商材の利用統計
            - 商材間の比較分析
            - フィルタリング機能

        3. トレンド分析:
            - 時系列での利用傾向
            - 満足度の推移
            - パフォーマンス指標

        4. 詳細データ:
            - 具体的なフィードバック内容
            - エラー・改善点の特定
            - データドリルダウン機能

    データ処理:
        - FeedbackManagerからの統計データ取得
        - リアルタイム分析結果の表示
        - エラーハンドリング付きの安全なデータ操作
    """
    st.title("📊 チャット利用分析")

    # ファイルハンドラーから商材一覧を取得
    file_handler = FileHandler()
    existing_products = file_handler.rag_manager.list_products()

    if not existing_products:
        st.info("分析対象の商材がありません。先にファイル管理から商材を登録してください。")
        return

    # 商材選択
    selected_products = st.multiselect("分析対象の商材を選択", ["全商材"] + existing_products, default=["全商材"])

    if "全商材" in selected_products:
        product_filter = None
        analysis_title = "全商材"
    else:
        product_filter = selected_products[0] if selected_products else None
        analysis_title = product_filter or "商材未選択"

    if product_filter or "全商材" in selected_products:
        st.subheader(f"📈 {analysis_title} の利用統計")

        # フィードバック統計取得
        feedback_summary = feedback_manager.get_feedback_summary(product_filter)

        if feedback_summary:
            # KPI表示
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("総セッション数", feedback_summary.get("total_sessions", 0))

            with col2:
                satisfaction_rate = feedback_summary.get("satisfaction_rate", 0)
                st.metric(
                    "満足度",
                    f"{satisfaction_rate:.1f}%",
                    delta=f"{satisfaction_rate - 70:.1f}%" if satisfaction_rate > 0 else None,
                )

            with col3:
                avg_messages = feedback_summary.get("avg_messages_per_session", 0)
                st.metric(
                    "平均メッセージ数/セッション",
                    f"{avg_messages:.1f}",
                    delta=f"{avg_messages - 5:.1f}" if avg_messages > 0 else None,
                )

            with col4:
                avg_duration = feedback_summary.get("avg_session_duration", 0)
                st.metric("平均セッション時間", f"{avg_duration:.1f}分")

            st.divider()

            # 詳細分析
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("😊 満足度の内訳")
                satisfied = feedback_summary.get("satisfied_count", 0)
                dissatisfied = feedback_summary.get("dissatisfied_count", 0)

                if satisfied + dissatisfied > 0:
                    import pandas as pd

                    satisfaction_data = pd.DataFrame({"評価": ["満足", "不満足"], "件数": [satisfied, dissatisfied]})
                    st.bar_chart(satisfaction_data.set_index("評価"))
                else:
                    st.info("フィードバックデータがありません")

            with col2:
                st.subheader("📋 改善提案")
                if satisfaction_rate < 70:
                    st.warning("⚠️ 満足度が70%を下回っています")
                    st.write("**改善案:**")
                    st.write("• プロンプトスタイルの見直し")
                    st.write("• 文書の品質確認")
                    st.write("• RAG設定の調整")
                elif satisfaction_rate > 85:
                    st.success("✅ 高い満足度を維持しています")
                    st.write("**継続的改善:**")
                    st.write("• 現在の設定を維持")
                    st.write("• 定期的な文書更新")
                else:
                    st.info("💡 満足度は標準的です")
                    st.write("**向上案:**")
                    st.write("• ユーザーフィードバックの詳細分析")
                    st.write("• より具体的な文書の追加")

        # 不満足の理由分析を追加
        st.divider()
        st.subheader("📝 不満足の理由（詳細分析）")

        dissatisfaction_reasons = feedback_manager.get_dissatisfaction_reasons(product_filter)

        if dissatisfaction_reasons:
            st.write(f"**不満足フィードバック: {len(dissatisfaction_reasons)}件**")

            # 不満足理由を表として表示
            import pandas as pd
            reasons_df = pd.DataFrame(dissatisfaction_reasons)

            # タイムスタンプでソート（最新順）
            if 'timestamp' in reasons_df.columns:
                reasons_df = reasons_df.sort_values('timestamp', ascending=False)

            # 表示用に列を選択・整理
            display_columns = ['timestamp', 'product_name', 'feedback_reason', 'prompt_style', 'total_messages']
            available_columns = [col for col in display_columns if col in reasons_df.columns]

            if available_columns:
                display_df = reasons_df[available_columns].copy()

                # 列名を日本語に変更
                column_mapping = {
                    'timestamp': '日時',
                    'product_name': '商材',
                    'feedback_reason': '不満足の理由',
                    'prompt_style': 'プロンプトスタイル',
                    'total_messages': 'メッセージ数'
                }

                display_df = display_df.rename(columns=column_mapping)

                # インデックスを1から開始
                display_df.index = range(1, len(display_df) + 1)

                st.dataframe(display_df, use_container_width=True)

                # フィードバック理由の要約
                if 'feedback_reason' in reasons_df.columns:
                    reasons_with_text = reasons_df[
                        (reasons_df['feedback_reason'].notna()) &
                        (reasons_df['feedback_reason'].str.strip() != '') &
                        (reasons_df['feedback_reason'].str.strip() != '（理由未記録）')
                    ]

                    if len(reasons_with_text) > 0:
                        with st.expander(f"💬 具体的な改善提案 ({len(reasons_with_text)}件)", expanded=False):
                            for idx, reason_row in reasons_with_text.iterrows():
                                st.write(f"**{reason_row.get('timestamp', '')}** - {reason_row.get('product_name', '')}:")
                                st.quote(reason_row['feedback_reason'])
                                st.write(f"*使用スタイル: {reason_row.get('prompt_style', 'N/A')}, メッセージ数: {reason_row.get('total_messages', 'N/A')}*")
                                st.divider()
        else:
            st.info("不満足のフィードバックはありません。")

    else:
        st.info("まだ分析データがありません。チャット利用後に分析結果が表示されます。")


def show_data_export():
    """データエクスポート画面"""
    st.title("📥 データエクスポート")

    # ファイルハンドラーから商材一覧を取得
    file_handler = FileHandler()
    existing_products = file_handler.rag_manager.list_products()

    if not existing_products:
        st.info("エクスポート対象の商材がありません。")
        return

    st.subheader("🗂️ データエクスポート")

    # 統合エクスポートの説明
    with st.expander("💡 エクスポート機能について"):
        st.write("""
        **チャット履歴のみ**:
        - ユーザーメッセージ、Bot回答、参考資料、セッション情報
        - チャット内容の詳細分析に適している

        **統合データ（履歴+フィードバック）**:
        - チャット履歴 + ユーザーフィードバック（満足度、不満足理由等）
        - セッションIDで関連付けられた統合データ
        - 満足度分析や改善点の特定に適している

        **フィードバックデータのみ**:
        - ユーザー満足度、セッション時間、不満足理由
        - 満足度推移の分析に適している
        """)

    # エクスポート対象の選択
    export_products = st.multiselect("エクスポート対象商材", ["全商材"] + existing_products, default=["全商材"])

    st.write("**エクスポートしたいデータを選択してください：**")

    # エクスポートボタンを3つに分ける
    col_btn1, col_btn2, col_btn3 = st.columns(3)

    with col_btn1:
        if st.button("📄 チャット履歴のみ", use_container_width=True):
            _export_data(export_products, existing_products, "chat_only")

    with col_btn2:
        if st.button("📊 統合データ（履歴+フィードバック）", use_container_width=True):
            _export_data(export_products, existing_products, "combined")

    with col_btn3:
        if st.button("📋 フィードバックデータのみ", use_container_width=True):
            _export_feedback_only()

def _export_data(export_products, existing_products, export_type):
    """エクスポート実行の共通処理"""
    if "全商材" in export_products:
        # 全商材のエクスポート
        if export_type == "combined":
            export_path = feedback_manager.export_combined_data()
            export_name = "全商材統合データ"
        else:
            export_path = feedback_manager.export_chat_history()
            export_name = "全商材チャット履歴"
    else:
        # 個別商材のエクスポート
        product_name = export_products[0] if export_products else None
        if product_name:
            if export_type == "combined":
                export_path = feedback_manager.export_combined_data(product_name)
                export_name = f"{product_name}統合データ"
            else:
                export_path = feedback_manager.export_chat_history(product_name)
                export_name = f"{product_name}チャット履歴"
        else:
            st.warning("エクスポート対象を選択してください")
            return

    if export_path and os.path.exists(export_path):
        st.success(f"✅ {export_name}のエクスポートが完了しました")

        # ダウンロードボタン
        with open(export_path, "rb") as f:
            st.download_button(
                label=f"📁 {os.path.basename(export_path)} をダウンロード",
                data=f.read(),
                file_name=os.path.basename(export_path),
                mime="text/csv",
                use_container_width=True,
            )

        # ファイル情報表示
        file_size = os.path.getsize(export_path)
        st.info(f"📊 ファイルサイズ: {file_size:,} bytes")
    else:
        st.warning("エクスポートするデータがありません")

def _export_feedback_only():
    """フィードバックデータのみをエクスポート"""
    if os.path.exists(feedback_manager.feedback_file):
        with open(feedback_manager.feedback_file, "rb") as f:
            st.download_button(
                label="📁 user_feedback.csv をダウンロード",
                data=f.read(),
                file_name="user_feedback.csv",
                mime="text/csv",
                use_container_width=True,
            )
        st.success("✅ フィードバックデータの準備完了")

        # ファイル情報表示
        file_size = os.path.getsize(feedback_manager.feedback_file)
        st.info(f"📊 ファイルサイズ: {file_size:,} bytes")
    else:
        st.warning("まだフィードバックデータがありません")


if __name__ == "__main__":
    main()
