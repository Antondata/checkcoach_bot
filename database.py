import aiosqlite

async def init_db():
    async with aiosqlite.connect('tasks.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                task_text TEXT,
                status TEXT DEFAULT 'active'
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER UNIQUE,
                username TEXT
            )
        ''')
        await db.commit()

async def add_user(chat_id, username):
    async with aiosqlite.connect('tasks.db') as db:
        await db.execute("INSERT OR IGNORE INTO users (chat_id, username) VALUES (?, ?)", (chat_id, username))
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect('tasks.db') as db:
        cursor = await db.execute("SELECT chat_id, username FROM users")
        rows = await cursor.fetchall()
        return [{'chat_id': row[0], 'username': row[1]} for row in rows]

async def get_user_id(chat_id):
    return chat_id

async def add_task(user_id, task_text):
    async with aiosqlite.connect('tasks.db') as db:
        await db.execute("INSERT INTO tasks (user_id, task_text, status) VALUES (?, ?, 'active')", (user_id, task_text))
        await db.commit()

async def remove_task(user_id, task_text):
    async with aiosqlite.connect('tasks.db') as db:
        await db.execute("DELETE FROM tasks WHERE user_id=? AND task_text=?", (user_id, task_text))
        await db.commit()

async def complete_task(user_id, task_text):
    async with aiosqlite.connect('tasks.db') as db:
        await db.execute("UPDATE tasks SET status='completed' WHERE user_id=? AND task_text=?", (user_id, task_text))
        await db.commit()

async def get_active_tasks(user_id):
    async with aiosqlite.connect('tasks.db') as db:
        cursor = await db.execute("SELECT task_text FROM tasks WHERE user_id=? AND status='active'", (user_id,))
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def get_completed_tasks(user_id):
    async with aiosqlite.connect('tasks.db') as db:
        cursor = await db.execute("SELECT task_text FROM tasks WHERE user_id=? AND status='completed'", (user_id,))
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def get_weekly_stats(user_id):
    # Заглушка, если нужно можно сделать реальную статистику по датам
    return (0, 0)
