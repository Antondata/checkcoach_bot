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
        await db.commit()

async def add_user(chat_id, username):
    pass

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

async def get_weekly_stats(user_id):
    return (0, 0)