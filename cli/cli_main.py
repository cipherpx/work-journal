import sys
from core.log_service import add_single_log, batch_parse_and_save, search_log
from core.gen_report import gen_daily_report, gen_weekly_report,star_to_str
from core.export_core import export_daily_all, export_weekly_all
from core.path_util import now_datetime_str
from core.db_core import db_conn



def print_help():
    print("""
日志管理系统 CLI
命令列表：
  add        单条录入
  batch      批量导入（粘贴多行文本）
  daily      生成日报（年 月 日）
  weekly     生成周报（年 周次）
  search     搜索日志（关键词）
  list       查看所有日志
  date       按日期查看日志
  edit       按ID编辑内容
  del        按ID删除日志
  clone      按ID拷贝克隆一条日志
  clear      清空所有日志并重置ID从1开始
  help       显示帮助
  exit       退出
    """)


def cli_add():
    try:
        from datetime import datetime
        today = datetime.today()

        def input_q(prompt):
            val = input(prompt).strip()
            if val.lower() == 'q':
                raise ValueError('cancel')
            return val

        # 日期
        y = input_q(f"年份（默认{today.year}）：") or today.year
        m = input_q(f"月份（默认{today.month}）：") or today.month
        d = input_q(f"日期（默认{today.day}）：") or today.day
        y = int(y)
        m = int(m)
        d = int(d)

        # 标题
        title = input_q("标题（默认未命名标题）：").strip() or "未命名标题"
        content = input_q("内容：").strip()

        # 优先级编码
        code = input_q("优先级编码(两位数字，高中低1-3，默认33)：").strip() or "33"
        code = code.ljust(2, '3')[:2]

        prio_map = {'1':'高', '2':'中', '3':'低'}
        imp_map  = {'1':'重要', '2':'次要', '3':'一般'}
        prio = prio_map.get(code[0], '低')
        imp  = imp_map.get(code[1], '一般')

        # 标注星级默认1
        star = int(input_q("星级(1-5，默认1)：") or 1)

        # 分类输入（默认实验）
        category = input_q("分类（默认实验）：").strip() or "实验"

        add_single_log(y, m, d, title, content, prio, imp, star,category)
        print("✅ 保存成功")

    except ValueError as e:
        if 'cancel' in str(e):
            print("\n❌ 已取消添加日志")
        else:
            print(f"❌ 输入格式错误")
    except Exception as e:
        print(f"❌ 失败：{e}")

def cli_batch():
    print("粘贴多行数据（格式：YYYY-MM-DD | 内容 | 紧急度 | 重要度 | 星级），输入空行结束：")
    lines = []
    while True:
        line = input()
        if not line:
            break
        lines.append(line)
    count = batch_parse_and_save("\n".join(lines))
    print(f"✅ 批量导入完成，共 {count} 条")


def cli_daily():
    try:
        from datetime import datetime
        today = datetime.today()

        y = int(input(f"年份（默认{today.year}）：") or today.year)
        m = int(input(f"月份（默认{today.month}）：") or today.month)
        d = int(input(f"日期（默认{today.day}）：") or today.day)

        content = gen_daily_report(y, m, d)
        print()
        print("===== 日报 =====")
        print(content)
        export_daily_all(y, m, d)
        print("✅ 已导出 TXT/Excel/Word/PDF 并复制到剪贴板")
    except Exception as e:
        print(f"❌ 失败：{e}")


def cli_weekly():
    try:
        from datetime import datetime
        now = datetime.now()
        y_default = now.year
        w_default = now.isocalendar()[1]

        y = int(input(f'年份（默认{y_default}）：') or y_default)
        w = int(input(f'周次（默认{w_default}）：') or w_default)

        content = gen_weekly_report(y, w)
        print()
        print("===== 周报 =====")
        print(content)
        export_weekly_all(y, w)
        print('✅ 已导出 TXT/Word/PDF 并复制到剪贴板')
    except Exception as e:
        print(f'❌ 失败：{e}')

def cli_search():
    kw = input("搜索关键词：")
    res = search_log(kw)
    print(f"共找到 {len(res)} 条：")
    for it in res:
        print(f"- {it[2]}-{it[3]:02d}-{it[4]:02d} {it[6]} [{it[11]}]")

# 查看所有日志
def cli_list_all():
    try:
        with db_conn() as c:
            cur = c.cursor()
            cur.execute("SELECT * FROM log_main ORDER BY id DESC")
            rows = cur.fetchall()

        print(f'共 {len(rows)} 条日志：')
        for r in rows:
            sid = r[0]
            y,m,d = r[2],r[3],r[4]
            title = r[6]
            star_lv = r[10]
            star_show = star_to_str(star_lv)
            print(f'ID:{sid} | {y}-{m:02d}-{d:02d} | {title} | {star_show}')
            print(f"  内容：{r[7]}\n")
    except Exception as e:
        print(f"❌ list 失败：{e}")

# 按日期查看
def cli_by_date():
    try:
        y = int(input("年份："))
        m = int(input("月份："))
        d = int(input("日期："))
        with db_conn() as c:
            cur = c.cursor()
            cur.execute("SELECT * FROM log_main WHERE year=? AND month=? AND day=?", (y, m, d))
            rows = cur.fetchall()

        print(f"\n当日共 {len(rows)} 条：")
        for r in rows:
            sid = r[0]
            title = r[6]
            star_show = star_to_str(r[10])
            print(f"ID:{sid} | {title} | {star_show}")
            print(f"  内容：{r[7]}\n")
    except Exception as e:
        print(f"❌ 失败：{e}")

# 编辑日志
def cli_edit():
    try:
        log_id = input("要编辑的日志ID：")
        content = input("新内容：")
        with db_conn() as c:
            cur = c.cursor()
            cur.execute("UPDATE log_main SET content=? WHERE id=?", (content, log_id))
        print("✅ 修改成功")
    except Exception as e:
        print(f"❌ 失败：{e}")

# 删除日志
def cli_delete():
    try:
        def parse_ids(s):
            ids = set()
            for part in s.split(','):
                part = part.strip()
                if '-' in part:
                    a, b = part.split('-', 1)
                    a = int(a.strip())
                    b = int(b.strip())
                    ids.update(range(a, b + 1))
                else:
                    if part.isdigit():
                        ids.add(int(part))
            return sorted(ids)

        id_str = input("输入要删除的ID(支持 1-2,3 格式)：").strip()
        del_ids = parse_ids(id_str)

        if not del_ids:
            print("❌ 未输入有效ID")
            return

        with db_conn() as c:
            cur = c.cursor()
            placeholders = ','.join(['?'] * len(del_ids))
            cur.execute(f"DELETE FROM log_main WHERE id IN ({placeholders})", del_ids)

        print(f"✅ 成功删除 {len(del_ids)} 条记录")
    except Exception as e:
        print(f"❌ 删除失败：{e}")


def cli_clone_log():
    try:
        src_id = input("输入要拷贝的日志ID：").strip()
        with db_conn() as c:
            cur = c.cursor()
            # 查询原日志所有字段
            cur.execute('''
                        SELECT year, month, day, title, content, priority, importance, star
                        FROM log_main
                        WHERE id = ?
                        ''', (src_id,))
            row = cur.fetchone()
        if not row:
            print("❌ 未找到该ID日志")
            return

        # 解包原有数据
        y, m, d, title, content, prio, imp, star = row
        # 调用你原有新增接口，复刻一条
        add_single_log(y, m, d, title, content, prio, imp, star)
        print("✅ 日志拷贝成功，已生成新记录")
    except Exception as e:
        print(f"❌ 拷贝失败：{e}")

def cli_clear_all():
    try:
        confirm = input("⚠️ 确定要删除所有日志吗？此操作不可恢复！输入 YES 确认：")
        if confirm != "YES":
            print("✅ 已取消清空")
            return

        with db_conn() as c:
            cur = c.cursor()
            # 1. 删除所有数据
            cur.execute("DELETE FROM log_main")
            # 2. 重置 ID 自增计数器，下次从 1 开始
            cur.execute("DELETE FROM sqlite_sequence WHERE name='log_main'")
        print("✅ 所有日志已清空，ID 已重置为从 1 开始")
    except Exception as e:
        print(f"❌ 清空失败：{e}")

def run_cli():
    print(f"日志管理系统 CLI —— {now_datetime_str()}")
    print_help()
    while True:
        cmd = input("\n请输入命令：").strip().lower()
        print()
        if cmd == "exit":
            print("👋 再见")
            sys.exit()
        elif cmd == "help":
            print_help()
        elif cmd == "add":
            cli_add()
        elif cmd == "batch":
            cli_batch()
        elif cmd == "daily":
            cli_daily()
        elif cmd == "weekly":
            cli_weekly()
        elif cmd == "search":
            cli_search()
        elif cmd == "list":
            cli_list_all()
        elif cmd == "date":
            cli_by_date()
        elif cmd == "edit":
            cli_edit()
        elif cmd == "del":
            cli_delete()
        elif cmd == "clone":
            cli_clone_log()
        elif cmd == "clear":
            cli_clear_all()
        else:
            print("❌ 未知命令，输入 help 查看帮助")



if __name__ == "__main__":
    run_cli()