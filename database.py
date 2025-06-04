import sqlite3

DB_FILE = "wordle.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_stats (
            guild_id INTEGER,
            user_id INTEGER,
            last_play_date TEXT,
            current_streak INTEGER,
            max_streak INTEGER,
            games_played INTEGER,
            wins INTEGER,
            attempts INTEGER,
            board TEXT,
            keyboard TEXT,
            done_today INTEGER,
            n1 INTEGER, n2 INTEGER, n3 INTEGER, n4 INTEGER, n5 INTEGER, n6 INTEGER,
            h1 INTEGER, h2 INTEGER, h3 INTEGER, h4 INTEGER, h5 INTEGER, h6 INTEGER,
            score REAL,
            hardmode_successes INTEGER,
            hardmode_streak INTEGER,
            hardmode_games INTEGER,
            hardmode_max_streak INTEGER,
            PRIMARY KEY (guild_id, user_id)
        )
    ''')
    conn.commit()
    conn.close()
