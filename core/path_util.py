import os
import datetime
import toml

def get_root_path():
    return os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

def load_config():
    cfg_path = os.path.join(get_root_path(), "config.toml")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return toml.load(f)

def now_datetime_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def now_ts_file_str():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def make_dirs(*paths):
    for p in paths:
        os.makedirs(p, exist_ok=True)

def get_year_month_path(base_dir, year, month):
    p = os.path.join(base_dir, str(year), f"{month:02d}")
    make_dirs(p)
    return p

def get_week_num(year, month, day):
    return datetime.date(year, month, day).isocalendar()[1]