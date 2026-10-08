from gui.gui_main import run_gui
from core.db_core import init_db

if __name__ == "__main__":
    init_db()

    run_gui()