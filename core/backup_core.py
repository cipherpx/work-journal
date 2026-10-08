import os
import shutil
from core.path_util import get_root_path, load_config, now_ts_file_str, make_dirs
from core.db_core import DB_PATH, db_integrity_check

cfg = load_config()
BAK_DIR = os.path.join(get_root_path(), cfg["path"]["backup_dir"])
MAX_SAVE = cfg["backup"]["max_backup_save"]
make_dirs(BAK_DIR)

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
    files = sorted([f for f in os.listdir(BAK_DIR) if f.endswith("_valid.db")])
    if len(files) > MAX_SAVE:
        for f in files[:len(files)-MAX_SAVE]:
            try:
                os.remove(os.path.join(BAK_DIR, f))
            except:
                pass
    return True

def restore_latest_backup():
    files = sorted([f for f in os.listdir(BAK_DIR) if f.endswith("_valid.db")])
    if not files:
        return False
    latest = os.path.join(BAK_DIR, files[-1])
    shutil.copy2(latest, DB_PATH)
    return True