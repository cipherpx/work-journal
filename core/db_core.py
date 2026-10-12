import sqlite3
import os
import time
from contextlib import contextmanager
from core.cfg_manager import get_root_path, load_config_toml
from core.utils import make_dirs

ROOT = get_root_path()
DB_PATH = os.path.join(ROOT, str(load_config_toml()['path']['db_path']))
DB_LOCK = DB_PATH + ".lock"
make_dirs(os.path.dirname(DB_PATH))

@contextmanager
def db_conn():
    # 文件锁
    while os.path.exists(DB_LOCK):
        time.sleep(0.01)
    open(DB_LOCK, "w", encoding="utf-8").write("lock")

    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=FULL;")
    conn.execute("PRAGMA foreign_keys = ON;")

    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
        if os.path.exists(DB_LOCK):
            os.remove(DB_LOCK)

def db_integrity_check() -> bool:
    if not os.path.exists(DB_PATH):
        return False
    try:
        with db_conn() as c:
            res = c.execute("PRAGMA integrity_check;").fetchone()
            return res is not None and res[0] == "ok"
    except:
        return False

def init_db():
    try:
        # 先尝试检查
        if db_integrity_check():
            return
    except:
        # 检查失败 → 忽略，继续建表
        pass
    with db_conn() as c:
        c.execute('''
        CREATE TABLE IF NOT EXISTS log_main (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_type TEXT DEFAULT 'item',
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            day INTEGER NOT NULL,
            week_num INTEGER DEFAULT 0,
            title TEXT DEFAULT '',
            content TEXT DEFAULT '',
            priority TEXT DEFAULT '中',
            importance TEXT DEFAULT '一般',
            star INTEGER DEFAULT 3,
            auto_class TEXT DEFAULT '生活',
            tags TEXT DEFAULT '',
            create_time TEXT NOT NULL,
            update_time TEXT NOT NULL,
            batch_source TEXT DEFAULT ''
        )
        ''')