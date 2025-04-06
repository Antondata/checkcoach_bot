import aiosqlite

DB_NAME = "bot_database.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS Users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER UNIQUE NOT NULL,
                username TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS Tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_text TEXT NOT NULL,
                is_done BOOLEAN DEFAULT 0,
                date TEXT DEFAULT (date('now')),
                FOREIGN KEY(user_id) REFERENCES Users(id)
            )
        """)
        await db.commit()

async def add_user(chat_id: int, username: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR IGNORE INTO Users (chat_id, username)
            VALUES (?, ?)
        """, (chat_id, username))
        await db.commit()

async def get_user_id(chat_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id FROM Users WHERE chat_id = ?", (chat_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def add_task(user_id: int, task_text: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO Tasks (user_id, task_text)
            VALUES (?, ?)
        """, (user_id, task_text))
        await db.commit()

async def get_tasks(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT task_text FROM Tasks
            WHERE user_id = ? AND is_done = 0
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def mark_task_done(user_id: int, task_text: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE Tasks
            SET is_done = 1
            WHERE user_id = ? AND task_text = ?
        """, (user_id, task_text))
        await db.commit()

async def remove_task(user_id: int, task_text: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            DELETE FROM Tasks
            WHERE user_id = ? AND task_text = ?
        """, (user_id, task_text))
        await db.commit()

async def clear_old_tasks():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            DELETE FROM Tasks
            WHERE is_done = 1 AND date < date('now', '-7 day')
        """)
        await db.commit()

async def get_weekly_stats(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT COUNT(*), SUM(is_done)
            FROM Tasks
            WHERE user_id = ? AND date >= date('now', '-7 days')
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            total = row[0] or 0
            completed = row[1] or 0
            return total, completed

async def get_all_users():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT chat_id, username FROM Users") as cursor:
            rows = await cursor.fetchall()
            return [{'chat_id': row[0], 'username': row[1]} for row in rows]
