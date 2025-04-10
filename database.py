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
        cursor = await db.execute('''
            DELETE FROM tasks
            WHERE receiver_id = ? AND task_text = ?
        ''', (user_id, task_text))
        await db.commit()
        if cursor.rowcount == 0:
            # Задача не найдена, можно логировать
            pass

# Получение всех задач пользователя (опционально по статусу)
async def get_tasks_for_user(user_id, status=None):
    async with aiosqlite.connect(DB_PATH) as db:
        if status:
            cursor = await db.execute('''
                SELECT task_text, status
                FROM tasks
                WHERE receiver_id = ? AND status = ?
            ''', (user_id, status))
        else:
            cursor = await db.execute('''
                SELECT task_text, status
                FROM tasks
                WHERE receiver_id = ?
            ''', (user_id,))
        rows = await cursor.fetchall()
        return [{'task_text': row[0], 'status': row[1]} for row in rows]

# Получение задач, которые пользователь поставил другим (оптимизировано)
async def get_assigned_tasks(sender_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            SELECT t.task_text, t.status, u.username
            FROM tasks t
            JOIN users u ON t.receiver_id = u.chat_id
            WHERE t.sender_id = ?
        ''', (sender_id,))
        rows = await cursor.fetchall()

        return [
            {'task_text': task_text, 'status': status, 'receiver_username': username}
            for task_text, status, username in rows
        ]

# Получение количества задач, поставленных пользователем
async def get_task_count(sender_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT COUNT(*) FROM tasks WHERE sender_id = ?', (sender_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

# Получение имени пользователя по chat_id
async def get_username_by_id(chat_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT username FROM users WHERE chat_id = ?', (chat_id,))
        row = await cursor.fetchone()
        return row[0] if row else "Неизвестный"
