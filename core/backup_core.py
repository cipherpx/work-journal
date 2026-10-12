import os
import shutil
from core.cfg_manager import get_root_path, load_config_toml
from core.db_core import DB_PATH, db_integrity_check,db_conn
from core.utils import now_ts_file_str, make_dirs
import sqlite3
from pathlib import Path


cfg = load_config_toml()
BAK_DIR = get_root_path() / Path(cfg["path"]["backup_dir"])
MAX_SAVE = cfg["backup"]["max_backup_save"]
make_dirs(BAK_DIR)

def _hot_sqlite_backup(dst_db: Path) -> bool:
    """内部：执行sqlite热备份，不抛异常，成功返回True"""
    dst_conn = sqlite3.connect(dst_db)
    try:
        with db_conn() as src_conn, dst_conn as conn:
            src_conn.backup(conn, pages=-1)
        return True
    except Exception:
        return False
    finally:
        dst_conn.close()

def _prune_old_backups(backup_dir: Path, max_keep: int, suffix: str = "_valid.db") -> None:
    """内部：清理过期备份，静默失败"""
    if not os.path.isdir(backup_dir):
        return
    bak_files = [
        backup_dir / f
        for f in os.listdir(backup_dir)
        if f.endswith(suffix)
    ]
    bak_files.sort()
    if len(bak_files) <= max_keep:
        return
    # 删除最旧一批
    for fp in bak_files[: len(bak_files) - max_keep]:
        try:
            os.remove(fp)
        except Exception:
            pass

def backup_db_safe_hot(bak_dir: Path = BAK_DIR, is_prune_old:bool = True) -> tuple[bool,str]:
    """
    热备份，复用原有业务规则：时间戳命名、备份目录、最大保留份数、自动清理旧备份
    返回: True备份完整成功；任意环节失败返回False，不向外抛出异常
    """
    if not os.path.exists(DB_PATH):
        return False,''

    # 源库完整性校验
    if not db_integrity_check():
        return False,''

    ts = now_ts_file_str()
    bak_name = f"log_{ts}_valid.db"
    bak_full = bak_dir / bak_name

    # 确保备份目录存在
    try:
        os.makedirs(bak_dir, exist_ok=True)
    except Exception:
        return False,''

    # 执行热备份
    ok = _hot_sqlite_backup(bak_full)
    if not ok:
        return False,''

    # 校验备份产出物；损坏则删除脏文件
    conn = sqlite3.connect(bak_full)
    try:
        with conn as c:
            res = c.execute("PRAGMA integrity_check;").fetchone()
            if res is None or res[0] != "ok":
                try:
                    os.remove(bak_full)
                except Exception:
                    pass
                return False,''
            else:
                pass
    except:
        return False,''
    finally:
        conn.close()

    # 回收旧备份
    if is_prune_old:
        _prune_old_backups(bak_dir, MAX_SAVE, suffix="_valid.db")
    return True,str(bak_full)

def backup_db_safe():
    if not os.path.exists(DB_PATH):
        return False
    if not db_integrity_check():
        return False

    ts = now_ts_file_str()
    bak_name = f"log_{ts}_valid.db"
    bak_full = os.path.join(BAK_DIR, bak_name)
    shutil.copy2(DB_PATH, bak_full)

    # 清理过期备份
    _prune_old_backups(BAK_DIR, MAX_SAVE, suffix="_valid.db")
    return True

def restore_latest_backup():
    files = sorted([f for f in os.listdir(BAK_DIR) if f.endswith("_valid.db")])
    if not files:
        return False
    latest = os.path.join(BAK_DIR, files[-1])
    shutil.copy2(latest, DB_PATH)
    return True
