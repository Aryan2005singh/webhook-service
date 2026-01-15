"""
Database layer for SQLite interactions.
"""
import sqlite3
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from contextlib import contextmanager


class Database:
    """SQLite database manager."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    from_msisdn TEXT NOT NULL,
                    to_msisdn TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    text TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            # Indexes for efficient queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_from_msisdn 
                ON messages(from_msisdn)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ts 
                ON messages(ts, message_id)
            """)
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get database connection context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def is_healthy(self) -> bool:
        """Check if database is accessible."""
        try:
            with self._get_connection() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception:
            return False
    
    def insert_message(
        self,
        message_id: str,
        from_msisdn: str,
        to_msisdn: str,
        ts: str,
        text: Optional[str]
    ) -> Tuple[bool, bool]:
        """
        Insert message with idempotency.
        
        Returns:
            (success, is_duplicate) tuple
        """
        created_at = datetime.now(timezone.utc).isoformat()
        
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO messages 
                    (message_id, from_msisdn, to_msisdn, ts, text, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (message_id, from_msisdn, to_msisdn, ts, text, created_at)
                )
                conn.commit()
                
                # If rowcount is 0, it was a duplicate
                is_duplicate = cursor.rowcount == 0
                return True, is_duplicate
        except Exception:
            return False, False
    
    def get_messages(
        self,
        limit: int,
        offset: int,
        from_filter: Optional[str] = None,
        since_filter: Optional[str] = None,
        q_filter: Optional[str] = None
    ) -> Tuple[List[dict], int]:
        """
        Retrieve messages with pagination and filters.
        
        Returns:
            (messages_list, total_count) tuple
        """
        # Build WHERE clause
        where_clauses = []
        params = []
        
        if from_filter:
            where_clauses.append("from_msisdn = ?")
            params.append(from_filter)
        
        if since_filter:
            where_clauses.append("ts >= ?")
            params.append(since_filter)
        
        if q_filter:
            where_clauses.append("text LIKE ?")
            params.append(f"%{q_filter}%")
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        with self._get_connection() as conn:
            # Get total count
            count_query = f"SELECT COUNT(*) as total FROM messages WHERE {where_sql}"
            total = conn.execute(count_query, params).fetchone()["total"]
            
            # Get paginated data
            data_query = f"""
                SELECT message_id, from_msisdn as 'from', to_msisdn as 'to', 
                       ts, text, created_at
                FROM messages 
                WHERE {where_sql}
                ORDER BY ts ASC, message_id ASC
                LIMIT ? OFFSET ?
            """
            rows = conn.execute(data_query, params + [limit, offset]).fetchall()
            
            messages = [dict(row) for row in rows]
            return messages, total
    
    def get_stats(self) -> dict:
        """Get system statistics."""
        with self._get_connection() as conn:
            # Total messages
            total = conn.execute(
                "SELECT COUNT(*) as count FROM messages"
            ).fetchone()["count"]
            
            # Unique senders count
            senders = conn.execute(
                "SELECT COUNT(DISTINCT from_msisdn) as count FROM messages"
            ).fetchone()["count"]
            
            # Top 10 senders
            top_senders = conn.execute("""
                SELECT from_msisdn as 'from', COUNT(*) as count
                FROM messages
                GROUP BY from_msisdn
                ORDER BY count DESC
                LIMIT 10
            """).fetchall()
            
            # First and last message timestamps
            timestamps = conn.execute("""
                SELECT 
                    MIN(ts) as first_ts,
                    MAX(ts) as last_ts
                FROM messages
            """).fetchone()
            
            return {
                "total_messages": total,
                "senders_count": senders,
                "messages_per_sender": [dict(row) for row in top_senders],
                "first_message_ts": timestamps["first_ts"],
                "last_message_ts": timestamps["last_ts"]
            }
