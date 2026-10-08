#! python3
# run_cli.py
# 实现功能：打开命令行界面
# Author：cipher
# Date: 2026/5/14 17:27

from cli.cli_main import run_cli
from core.db_core import init_db

init_db()

if __name__ == "__main__":
    init_db()
    run_cli()