import aiosqlite

async def init_db():
    async with aiosqlite.connect('tasks.db') as db:
        # Таблица пользователей
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER UNIQUE,
                username TEXT,
                is_favorite BOOLEAN DEFAULT 0
            )
        ''')
        
        # Таблица задач
        await db.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                task_text TEXT,
                category TEXT,
                due_date TEXT,
                priority TEXT,
                status TEXT DEFAULT 'active',
                file_id TEXT
            )
        ''')
        await db.commit()

# Работа с пользователями
async def add_user(chat_id, username):
    async with aiosqlite.connect('tasks.db') as db:
        await db.execute('''
            INSERT OR IGNORE INTO users (chat_id, username) VALUES (?, ?)
        ''', (chat_id, username))
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect('tasks.db') as db:
        cursor = await db.execute('SELECT chat_id, username, is_favorite FROM users')
        rows = await cursor.fetchall()
        return [{'chat_id': row[0], 'username': row[1], 'is_favorite': bool(row[2])} for row in rows]

async def set_favorite(chat_id, is_favorite):
    async with aiosqlite.connect('tasks.db') as db:
        await db.execute('UPDATE users SET is_favorite=? WHERE chat_id=?', (is_favorite, chat_id))
        await db.commit()

async def get_user_id(chat_id):
    return chat_id

async def get_favorite_users():
    async with aiosqlite.connect('tasks.db') as db:
        cursor = await db.execute('SELECT chat_id FROM users WHERE is_favorite=1')
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

# Работа с задачами
async def add_task(user_id, task_text, category=None, due_date=None, priority=None, file_id=None):
    async with aiosqlite.connect('tasks.db') as db:
        await db.execute('''
            INSERT INTO tasks (user_id, task_text, category, due_date, priority, status, file_id)
            VALUES (?, ?, ?, ?, ?, 'active', ?)
        ''', (user_id, task_text, category, due_date, priority, file_id))
        await db.commit()

async def complete_task(user_id, task_text):
    async with aiosqlite.connect('tasks.db') as db:
        await db.execute('''
            UPDATE tasks SET status='completed' WHERE user_id=? AND task_text=?
        ''', (user_id, task_text))
        await db.commit()

async def remove_task(user_id, task_text):
    async with aiosqlite.connect('tasks.db') as db:
        await db.execute('''
            DELETE FROM tasks WHERE user_id=? AND task_text=?
        ''', (user_id, task_text))
        await db.commit()

async def update_due_date(user_id, task_text, new_due_date):
    async with aiosqlite.connect('tasks.db') as db:
        await db.execute('''
            UPDATE tasks SET due_date=? WHERE user_id=? AND task_text=?
        ''', (new_due_date, user_id, task_text))
        await db.commit()

async def get_active_tasks(user_id):
    async with aiosqlite.connect('tasks.db') as db:
        cursor = await db.execute('''
            SELECT task_text, category, due_date, priority FROM tasks
            WHERE user_id=? AND status='active'
        ''', (user_id,))
        rows = await cursor.fetchall()
        return rows

async def get_completed_tasks(user_id):
    async with aiosqlite.connect('tasks.db') as db:
        cursor = await db.execute('''
            SELECT task_text, category, due_date FROM tasks
            WHERE user_id=? AND status='completed'
        ''', (user_id,))
        rows = await cursor.fetchall()
        return rows

async def get_tasks_due_today(user_id):
    async with aiosqlite.connect('tasks.db') as db:
        cursor = await db.execute('''
            SELECT task_text FROM tasks
            WHERE user_id=? AND due_date=date('now') AND status='active'
        ''', (user_id,))
        rows = await cursor.fetchall()
        return [row[0] for row in rows]
