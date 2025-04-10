import aiosqlite

DB_PATH = 'tasks.db'

# Инициализация базы данных
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER UNIQUE,
                username TEXT,
                phone_number TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER,
                receiver_id INTEGER,
                task_text TEXT,
                status TEXT DEFAULT 'pending'
            )
        ''')
        await db.commit()

# Добавление нового пользователя
async def add_user(chat_id, username, phone_number=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT OR IGNORE INTO users (chat_id, username, phone_number)
            VALUES (?, ?, ?)
        ''', (chat_id, username, phone_number))
        await db.commit()

# Получение всех пользователей
async def get_all_contacts():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT chat_id, username, phone_number FROM users')
        rows = await cursor.fetchall()
        return [{'chat_id': row[0], 'username': row[1], 'phone_number': row[2]} for row in rows]

# Добавление новой задачи
async def add_task(sender_id, receiver_id, task_text, status="pending"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO tasks (sender_id, receiver_id, task_text, status)
            VALUES (?, ?, ?, ?)
        ''', (sender_id, receiver_id, task_text, status))
        await db.commit()

# Обновление статуса всех задач для пользователя
async def update_task_status(receiver_id, new_status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            UPDATE tasks
            SET status = ?
            WHERE receiver_id = ? AND status = 'pending'
        ''', (new_status, receiver_id))
        await db.commit()

# Обновление статуса конкретной задачи по тексту
async def update_task_status_by_text(user_id, task_text, new_status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            UPDATE tasks
            SET status = ?
            WHERE receiver_id = ? AND task_text = ?
        ''', (new_status, user_id, task_text))
        await db.commit()

# Удаление задачи по тексту
async def delete_task_by_text(user_id, task_text):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            DELETE FROM tasks
            WHERE receiver_id = ? AND task_text = ?
        ''', (user_id, task_text))
        await db.commit()

# Получение всех задач пользователя
async def get_tasks_for_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            SELECT task_text, status
            FROM tasks
            WHERE receiver_id = ?
        ''', (user_id,))
        rows = await cursor.fetchall()
        return [{'task_text': row[0], 'status': row[1]} for row in rows]

# Получение задач, которые пользователь поставил другим
async def get_assigned_tasks(sender_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            SELECT task_text, status, receiver_id
            FROM tasks
            WHERE sender_id = ?
        ''', (sender_id,))
        rows = await cursor.fetchall()

        assigned_tasks = []
        for task in rows:
            receiver_username = await get_username_by_id(task[2])
            assigned_tasks.append({
                'task_text': task[0],
                'status': task[1],
                'receiver_username': receiver_username,
                'receiver_id': task[2]
            })
        return assigned_tasks

# Получение имени пользователя по chat_id
async def get_username_by_id(chat_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT username FROM users WHERE chat_id = ?', (chat_id,))
        row = await cursor.fetchone()
        return row[0] if row else "Неизвестный"

# Получение количества задач, поставленных пользователем
async def get_task_count(sender_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT COUNT(*) FROM tasks WHERE sender_id = ?', (sender_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0
