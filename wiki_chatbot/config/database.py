"""
永続化データベース管理
SQLiteによる軽量データベースシステム
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple


class PersistentDatabase:
    """永続化データベース管理"""

    def __init__(self):
        self.db_path = Path("data/chatbot.db")
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_database()

    def _init_database(self):
        """データベース初期化"""
        with sqlite3.connect(self.db_path) as conn:
            # チャット履歴テーブル
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    user_message TEXT NOT NULL,
                    bot_response TEXT NOT NULL,
                    sources_used TEXT,
                    prompt_style TEXT,
                    satisfaction TEXT,
                    message_length INTEGER,
                    response_length INTEGER,
                    sources_count INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # ユーザーフィードバックテーブル
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    satisfaction TEXT NOT NULL,
                    total_messages INTEGER,
                    prompt_style TEXT,
                    session_duration TEXT,
                    feedback_text TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 互換性のためのfeedbackテーブル（user_feedbackと同じ構造）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    message_sequence INTEGER NOT NULL,
                    satisfaction TEXT NOT NULL,
                    user_message TEXT NOT NULL,
                    bot_response TEXT NOT NULL,
                    prompt_style TEXT NOT NULL,
                    feedback_reason TEXT DEFAULT ''
                )
            """)

            # ファイル管理テーブル
            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_management (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_name TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    file_type TEXT,
                    upload_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TEXT
                )
            """)

            # セッション管理テーブル
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    product_name TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    last_activity TEXT,
                    total_messages INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()

    def save_chat_message(self, session_id: str, product_name: str, user_message: str,
                         bot_response: str, sources_used: str = "", prompt_style: str = ""):
        """チャットメッセージを保存"""
        with sqlite3.connect(self.db_path) as conn:
            timestamp = datetime.now().isoformat()

            conn.execute("""
                INSERT INTO chat_history
                (timestamp, session_id, product_name, user_message,
                 bot_response, sources_used, prompt_style, message_length,
                 response_length, sources_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                session_id,
                product_name,
                user_message,
                bot_response,
                sources_used,
                prompt_style,
                len(user_message),
                len(bot_response),
                len(sources_used.split(";")) if sources_used else 0
            ))

            # セッション情報更新
            conn.execute("""
                INSERT OR REPLACE INTO sessions
                (session_id, product_name, start_time, last_activity, total_messages)
                VALUES (?, ?,
                    COALESCE((SELECT start_time FROM sessions WHERE session_id = ?), ?),
                    ?,
                    COALESCE((SELECT total_messages FROM sessions WHERE session_id = ?), 0) + 1)
            """, (session_id, product_name, session_id, timestamp, timestamp, session_id))

            conn.commit()

    def save_feedback(self, session_id: str, product_name: str, satisfaction: str,
                     total_messages: int, prompt_style: str, session_duration: str = "",
                     feedback_text: str = ""):
        """フィードバックを保存"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO user_feedback
                (timestamp, session_id, product_name, satisfaction, total_messages,
                 prompt_style, session_duration, feedback_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                session_id,
                product_name,
                satisfaction,
                total_messages,
                prompt_style,
                session_duration,
                feedback_text
            ))
            conn.commit()

    def save_file_info(self, product_name: str, file_name: str, file_path: str,
                       file_size: int, file_type: str):
        """ファイル情報を保存"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO file_management
                (product_name, file_name, file_path, file_size, file_type, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (product_name, file_name, file_path, file_size, file_type,
                  datetime.now().isoformat()))
            conn.commit()

    def get_chat_history(self, product_name: str, limit: int = 100) -> List[Tuple]:
        """チャット履歴を取得"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT timestamp, user_message, bot_response, sources_used
                FROM chat_history
                WHERE product_name = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (product_name, limit))
            return cursor.fetchall()

    def get_statistics(self, product_name: str = None) -> Dict:
        """利用統計を取得"""
        with sqlite3.connect(self.db_path) as conn:
            where_clause = "WHERE product_name = ?" if product_name else ""
            params = [product_name] if product_name else []

            # 総チャット数
            total_chats = conn.execute(
                f"SELECT COUNT(*) FROM chat_history {where_clause}", params
            ).fetchone()[0]

            # 満足度統計
            satisfaction_cursor = conn.execute(f"""
                SELECT satisfaction, COUNT(*)
                FROM user_feedback
                {where_clause}
                GROUP BY satisfaction
            """, params)
            satisfaction_stats = dict(satisfaction_cursor.fetchall())

            # セッション統計
            avg_messages = conn.execute(f"""
                SELECT AVG(total_messages)
                FROM sessions
                {where_clause}
            """, params).fetchone()[0] or 0

            return {
                "total_chats": total_chats,
                "satisfaction_stats": satisfaction_stats,
                "avg_messages_per_session": round(avg_messages, 2),
                "total_sessions": len(self.get_recent_sessions(product_name))
            }

    def get_recent_sessions(self, product_name: str = None, limit: int = 50) -> List[Dict]:
        """最近のセッション一覧を取得"""
        with sqlite3.connect(self.db_path) as conn:
            where_clause = "WHERE product_name = ?" if product_name else ""
            params = [product_name, limit] if product_name else [limit]

            cursor = conn.execute(f"""
                SELECT session_id, product_name, start_time, last_activity, total_messages
                FROM sessions
                {where_clause}
                ORDER BY last_activity DESC
                LIMIT ?
            """, params)

            sessions = []
            for row in cursor.fetchall():
                sessions.append({
                    "session_id": row[0],
                    "product_name": row[1],
                    "start_time": row[2],
                    "last_activity": row[3],
                    "total_messages": row[4]
                })

            return sessions

    def cleanup_old_data(self, days_old: int = 90):
        """古いデータを削除"""
        cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            # 古いチャット履歴を削除
            conn.execute("DELETE FROM chat_history WHERE timestamp < ?", (cutoff_date,))

            # 古いフィードバックを削除
            conn.execute("DELETE FROM user_feedback WHERE timestamp < ?", (cutoff_date,))

            # 古いセッションを削除
            conn.execute("DELETE FROM sessions WHERE last_activity < ?", (cutoff_date,))

            conn.commit()

    def get_database_size(self) -> float:
        """データベースサイズを取得（MB）"""
        if self.db_path.exists():
            return self.db_path.stat().st_size / (1024 * 1024)
        return 0

    def export_to_csv(self, table_name: str, output_path: str, product_name: str = None):
        """テーブルをCSVにエクスポート"""
        import csv

        with sqlite3.connect(self.db_path) as conn:
            if product_name and table_name in ["chat_history", "user_feedback", "sessions"]:
                cursor = conn.execute(f"SELECT * FROM {table_name} WHERE product_name = ?", (product_name,))
            else:
                cursor = conn.execute(f"SELECT * FROM {table_name}")

            # カラム名を取得
            column_names = [description[0] for description in cursor.description]

            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(column_names)
                writer.writerows(cursor.fetchall())

    def vacuum_database(self):
        """データベースを最適化"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("VACUUM")
            conn.commit()


# グローバルインスタンス
persistent_db = PersistentDatabase()