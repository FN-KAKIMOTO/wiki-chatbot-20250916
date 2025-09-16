import os
import json
import hashlib
from typing import List, Dict, Any, Optional
import pandas as pd
import chromadb
from chromadb.config import Settings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_openai import OpenAIEmbeddings
from docx import Document
import streamlit as st


class RAGManager:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.chroma_dir = os.path.join(data_dir, "chroma_db")
        os.makedirs(self.chroma_dir, exist_ok=True)

        self.client = chromadb.PersistentClient(path=self.chroma_dir)
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

        try:
            self.embeddings = OpenAIEmbeddings()
        except Exception as e:
            st.warning("OpenAI API key not set. Using default embeddings.")
            self.embeddings = None

    def get_or_create_collection(self, product_name: str):
        collection_name = f"product_{product_name.lower().replace(' ', '_')}"
        try:
            collection = self.client.get_collection(name=collection_name)
        except:
            collection = self.client.create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})
        return collection

    def get_file_hash(self, file_content: bytes) -> str:
        return hashlib.md5(file_content).hexdigest()

    def extract_text_from_file(self, file_path: str, file_type: str) -> str:
        try:
            if file_type == "txt":
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            elif file_type == "pdf":
                loader = PyPDFLoader(file_path)
                documents = loader.load()
                return "\n".join([doc.page_content for doc in documents])
            elif file_type == "docx":
                doc = Document(file_path)
                return "\n".join([paragraph.text for paragraph in doc.paragraphs])
            elif file_type == "pptx":
                from pptx import Presentation

                prs = Presentation(file_path)
                text_content = []

                for slide_num, slide in enumerate(prs.slides, 1):
                    slide_text = f"=== スライド {slide_num} ===\n"

                    for shape in slide.shapes:
                        if hasattr(shape, "text") and shape.text.strip():
                            slide_text += shape.text.strip() + "\n"

                        # 表がある場合の処理
                        if hasattr(shape, "table"):
                            table = shape.table
                            for row in table.rows:
                                row_text = " | ".join([cell.text.strip() for cell in row.cells])
                                slide_text += row_text + "\n"

                    text_content.append(slide_text)

                return "\n\n".join(text_content)
            elif file_type == "html":
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(content, "html.parser")
                return soup.get_text()
            elif file_type == "csv":
                df = pd.read_csv(file_path)

                # CSVの各行をQ&A形式として処理
                qa_pairs = []

                # 列数をチェック
                if len(df.columns) >= 2:
                    # 2列以上の場合、最初の列を質問、2番目の列を回答として処理
                    question_col = df.columns[0]
                    answer_col = df.columns[1]

                    for index, row in df.iterrows():
                        question = str(row[question_col]).strip()
                        answer = str(row[answer_col]).strip()

                        if question and answer and question != "nan" and answer != "nan":
                            qa_text = f"質問: {question}\n回答: {answer}"
                            qa_pairs.append(qa_text)
                else:
                    # 1列の場合は従来通りの処理
                    return df.to_string()

                return "\n\n".join(qa_pairs) if qa_pairs else df.to_string()
            else:
                return ""
        except Exception as e:
            st.error(f"Error reading file: {e}")
            return ""

    def add_csv_as_qa_pairs(self, product_name: str, file_name: str, file_content: bytes) -> bool:
        """CSVファイルの各行を個別のQ&Aペアとして処理"""
        try:
            collection = self.get_or_create_collection(product_name)
            file_hash = self.get_file_hash(file_content)

            temp_file_path = os.path.join(self.data_dir, f"temp_{file_hash}.csv")
            with open(temp_file_path, "wb") as f:
                f.write(file_content)

            df = pd.read_csv(temp_file_path)

            if len(df.columns) >= 2:
                question_col = df.columns[0]
                answer_col = df.columns[1]

                qa_count = 0
                for index, row in df.iterrows():
                    question = str(row[question_col]).strip()
                    answer = str(row[answer_col]).strip()

                    if question and answer and question != "nan" and answer != "nan":
                        qa_text = f"質問: {question}\n回答: {answer}"
                        doc_id = f"{file_hash}_qa_{index}"

                        collection.add(
                            documents=[qa_text],
                            metadatas=[
                                {
                                    "file_name": file_name,
                                    "file_hash": file_hash,
                                    "qa_index": index,
                                    "product": product_name,
                                    "question": question,
                                    "answer": answer,
                                    "type": "qa_pair",
                                }
                            ],
                            ids=[doc_id],
                        )
                        qa_count += 1

                os.remove(temp_file_path)
                st.success(f"✅ {qa_count}組のQ&Aペアを追加しました")
                return True
            else:
                st.error("CSVファイルには質問と回答の2列が必要です")
                os.remove(temp_file_path)
                return False

        except Exception as e:
            st.error(f"CSV処理エラー: {str(e)}")
            return False

    def add_document(self, product_name: str, file_name: str, file_content: bytes, file_type: str) -> bool:
        try:
            collection = self.get_or_create_collection(product_name)
            file_hash = self.get_file_hash(file_content)

            temp_file_path = os.path.join(self.data_dir, f"temp_{file_hash}.{file_type}")
            with open(temp_file_path, "wb") as f:
                f.write(file_content)

            text_content = self.extract_text_from_file(temp_file_path, file_type)

            if text_content:
                chunks = self.text_splitter.split_text(text_content)

                for i, chunk in enumerate(chunks):
                    doc_id = f"{file_hash}_{i}"
                    collection.add(
                        documents=[chunk],
                        metadatas=[
                            {"file_name": file_name, "file_hash": file_hash, "chunk_index": i, "product": product_name}
                        ],
                        ids=[doc_id],
                    )

            os.remove(temp_file_path)
            return True

        except Exception as e:
            st.error(f"Error adding document: {e}")
            return False

    def remove_document(self, product_name: str, file_name: str) -> bool:
        try:
            collection = self.get_or_create_collection(product_name)

            results = collection.get(where={"file_name": file_name})

            if results and results["ids"]:
                collection.delete(ids=results["ids"])
                return True
            return False

        except Exception as e:
            st.error(f"Error removing document: {e}")
            return False

    def search(self, product_name: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        try:
            collection = self.get_or_create_collection(product_name)

            results = collection.query(query_texts=[query], n_results=top_k)

            search_results = []
            if results["documents"] and results["documents"][0]:
                for i in range(len(results["documents"][0])):
                    search_results.append(
                        {
                            "content": results["documents"][0][i],
                            "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                            "distance": results["distances"][0][i] if results["distances"] else 0.0,
                        }
                    )

            return search_results

        except Exception as e:
            st.error(f"Error searching: {e}")
            return []

    def list_documents(self, product_name: str) -> List[str]:
        try:
            collection = self.get_or_create_collection(product_name)
            results = collection.get()

            if results and results["metadatas"]:
                file_names = set()
                for metadata in results["metadatas"]:
                    if "file_name" in metadata:
                        file_names.add(metadata["file_name"])
                return list(file_names)
            return []

        except Exception as e:
            st.error(f"Error listing documents: {e}")
            return []

    def list_products(self) -> List[str]:
        try:
            collections = self.client.list_collections()
            products = []
            for collection in collections:
                if collection.name.startswith("product_"):
                    product_name = collection.name.replace("product_", "").replace("_", " ").title()
                    products.append(product_name)
            return products
        except Exception as e:
            st.error(f"Error listing products: {e}")
            return []
