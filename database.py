import sqlite3
import asyncio
from typing import Optional

class Database:
    def __init__(self, db_path: str = "wojak_bot.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                free_generations_used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Migrate old free_used column to free_generations_used
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'free_used' in columns and 'free_generations_used' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN free_generations_used INTEGER DEFAULT 0')
            cursor.execute('UPDATE users SET free_generations_used = CASE WHEN free_used = 1 THEN 3 ELSE 0 END')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                telegram_charge_id TEXT,
                amount INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_user(self, user_id: int) -> Optional[dict]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, username, first_name, last_name, free_generations_used
            FROM users WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'user_id': result[0],
                'username': result[1],
                'first_name': result[2],
                'last_name': result[3],
                'free_generations_used': result[4]
            }
        return None
    
    def create_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name))
        
        conn.commit()
        conn.close()
    
    def use_free_generation(self, user_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users SET free_generations_used = free_generations_used + 1 WHERE user_id = ?
        ''', (user_id,))
        
        conn.commit()
        conn.close()
    
    def has_free_generations_left(self, user_id: int) -> bool:
        user_data = self.get_user(user_id)
        if not user_data:
            return True  # New users get free generations
        return user_data['free_generations_used'] < 3
    
    def add_payment(self, user_id: int, telegram_charge_id: str, amount: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO payments (user_id, telegram_charge_id, amount)
            VALUES (?, ?, ?)
        ''', (user_id, telegram_charge_id, amount))
        
        conn.commit()
        conn.close()
    
    def get_bot_stats(self) -> dict:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total users
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        # Users with free generations left
        cursor.execute('SELECT COUNT(*) FROM users WHERE free_generations_used < 3')
        users_with_free_left = cursor.fetchone()[0]
        
        # Total payments and stars
        cursor.execute('SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM payments')
        payments_result = cursor.fetchone()
        total_payments = payments_result[0]
        total_stars = payments_result[1]
        
        # Total generations (free + paid)
        cursor.execute('SELECT SUM(free_generations_used) FROM users')
        free_generations = cursor.fetchone()[0] or 0
        total_generations = free_generations + total_payments
        
        conn.close()
        
        return {
            'total_users': total_users,
            'users_with_free_left': users_with_free_left,
            'total_payments': total_payments,
            'total_stars': total_stars,
            'total_generations': total_generations
        }
    
    def reset_free_generations(self, user_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users SET free_generations_used = 0 WHERE user_id = ?
        ''', (user_id,))
        
        # Create user if doesn't exist
        if cursor.rowcount == 0:
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, free_generations_used)
                VALUES (?, 0)
            ''', (user_id,))
        
        conn.commit()
        conn.close()