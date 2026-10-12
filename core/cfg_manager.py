import os
import shutil
import tempfile
import webbrowser

import toml
from pathlib import Path
from core.constants import CURRENT_CONFIG_VERSION, REPO_URL

BASE_DIR = Path(__file__).resolve().parents[1]
TOML_PATH = BASE_DIR /'config' / 'config.toml'
CFG_EXAMPLE = BASE_DIR / 'config' / 'config.example.toml'
LICENSE_PATH = BASE_DIR / "LICENSE"
GITHUB_LICENSE_URL = f'https://github.com/{REPO_URL}/blob/main/LICENSE'


def get_root_path():
    return os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

def load_config_toml(cfg_path:Path=TOML_PATH, cfg_example:Path=CFG_EXAMPLE):
    if not cfg_path.exists():
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        if cfg_example.exists():
            shutil.copyfile(cfg_example, cfg_path)
        else:
            raise FileNotFoundError(
                f'配置文件 {cfg_path} 不存在，且示例文件 {cfg_example} 也不存在，无法生成默认配置。')
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = toml.load(f)
    # 版本检查 + 迁移
    cfg_version = cfg.get("config_version", "0")
    if cfg_version != CURRENT_CONFIG_VERSION:
        cfg = migrate_config(cfg, cfg_version)
        # 迁移后写回
        update_config_toml(cfg, cfg_path)
    return cfg

def _v(s: str) -> tuple:
    """版本号字符串转元组，用于比较
    '1.10' → (1, 10)
    """
    return tuple(int(x) for x in s.split("."))

def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并字典，override 优先

    - 两边都是 dict → 递归合并
    - override 里没有的 key → 用 base 的
    - override 里有的 key → 用 override 的
    """
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result

def migrate_config(cfg, from_version):
    """按版本号逐级迁移配置
    每个版本用独立的 if 块（不用 elif），保证跨版本升级能逐级执行
    旧配置没有 config_version 字段，视为版本 0。
    迁移策略：以示例配置为模板，现有配置的值优先。
    """
    v = _v(from_version)

    # 0 → 1.0：升级配置
    if v < (1, 0):
        cfg_example = Path(CFG_EXAMPLE)
        if cfg_example.exists():
            with cfg_example.open("r", encoding="utf-8") as f:
                example_cfg = toml.load(f)
            # 避免示例里的 config_version 参与合并
            example_cfg.pop("config_version", None)
            cfg = _deep_merge(example_cfg, cfg)

    # 1.0 → 1.1：（占位，未来加）
    # if v < (1, 1):
    #     ...

    # 1.1 → 1.2：（占位，未来加）
    # if v < (1, 2):
    #     ...

    cfg["config_version"] = CURRENT_CONFIG_VERSION
    return cfg


def update_config_toml(cfg,config_path:Path=TOML_PATH):
    """原子写入配置，写前备份"""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        shutil.copyfile(config_path, config_path.with_name(config_path.name + ".bak"))

    fd, tmp_path = tempfile.mkstemp(
        dir=config_path.parent, suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            toml.dump(cfg, f)
        # 原子替换
        os.replace(tmp_path, config_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

def update_config_category(new_options):
    # 加载原有配置
    cfg = load_config_toml()
    # 去重、保留顺序，强制保留末尾 '自定义'
    unique_list = []
    for item in new_options:
        item = item.strip()
        if item and item not in unique_list and item != '自定义':
            unique_list.append(item)
    # 末尾固定加自定义
    unique_list.append('自定义')
    # 写回配置
    cfg['category']['options'] = unique_list
    update_config_toml(cfg)
    return unique_list

def add_category_if_not_exists(new_category):
    # 🔥 先判断 None，绝对安全
    if new_category is None:
        return
    # 去除空格
    new_category = new_category.strip()
    # 空字符串也不处理
    if not new_category:
        return

    # 加载你的配置
    config = load_config_toml()

    if new_category not in config['category']['options']:
        config['category']['options'].insert(-1, new_category)
        # 保存
    update_config_toml(config)


def open_license():
    """打开 LICENSE：优先本地文件，没有则跳 GitHub"""
    if LICENSE_PATH.exists():
        webbrowser.open(LICENSE_PATH.as_uri())
    else:
        webbrowser.open(GITHUB_LICENSE_URL)