#!/usr/bin/env python3
"""
GitHubにアップロードされているRAGファイルの詳細確認スクリプト
"""

import sys
import os
sys.path.append('.')

from utils.rag_manager import RAGManager

def check_uploaded_files():
    """アップロードされているファイルの詳細を確認"""
    rag = RAGManager()

    print("🔍 RAGデータベース内ファイル確認")
    print("=" * 50)

    if not rag.chroma_available:
        print("❌ ChromaDB が利用できません")
        return

    # 商材一覧取得
    products = rag.list_products()
    print(f"📁 登録商材数: {len(products)}")

    total_files = 0
    for product in products:
        print(f"\n📋 商材: {product}")
        documents = rag.list_documents(product)
        print(f"   ファイル数: {len(documents)}")

        for doc in documents:
            print(f"   - {doc}")
            total_files += 1

    print(f"\n✅ 総ファイル数: {total_files}")

    # ChromaDBファイル情報
    chroma_file = "data/chroma_db/chroma.sqlite3"
    if os.path.exists(chroma_file):
        file_size = os.path.getsize(chroma_file)
        print(f"💾 ChromaDBサイズ: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
    else:
        print("❌ ChromaDBファイルが見つかりません")

if __name__ == "__main__":
    check_uploaded_files()