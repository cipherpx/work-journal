from core.db_core import db_conn
from core.backup_core import backup_db_safe
from core.cfg_manager import load_config_toml, add_category_if_not_exists
import re
from datetime import datetime,date
from core.utils import now_datetime_str, get_week_num

cfg = load_config_toml()
AUTO_BACKUP_START = cfg['backup']['auto_backup_on_start']
AUTO_BACKUP_MODIFY = cfg['backup']['auto_backup_on_modify']

if AUTO_BACKUP_START:
    backup_db_safe()

research_keys = set(cfg['classify']['research_keys'].split(','))
experiment_keys = set(cfg['classify']['experiment_keys'].split(','))
course_keys = set(cfg['classify']['course_keys'].split(','))
project_keys = set(cfg['classify']['project_keys'].split(','))

def auto_classify(text):
    text = text.lower()
    if any(k in text for k in research_keys):
        return '科研'
    if any(k in text for k in experiment_keys):
        return '实验'
    if any(k in text for k in course_keys):
        return '课程'
    if any(k in text for k in project_keys):
        return '项目'
    return '生活'

# ==========================================
# 【自动日期】不传年月日时，自动使用今天
# ==========================================
def add_single_log(year=None, month=None, day=None, title='', content='', priority='低', importance='一般', star=1, category=None):
    # 自动补全当天日期
    today = date.today()
    if year is None or month is None or day is None:
        year, month, day = today.year, today.month, today.day

    if AUTO_BACKUP_MODIFY:
        backup_db_safe()

    wk = get_week_num(year, month, day)
    # 如果传入了分类，就用传入的，否则自动分类
    if category is None:
        cls = auto_classify(content)
    else:
        cls = category  # 用你输入的分类

    now = now_datetime_str()

    with db_conn() as c:
        c.execute('''
        INSERT INTO log_main
        (log_type,year,month,day,week_num,title,content,priority,importance,star,category,create_time,update_time)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', ('item',year,month,day,wk,title,content,priority,importance,star,cls,now,now))

# ==========================
# 终极多分隔符 + Python 引号解析
# 全单引号版本
# ==========================
def smart_split_line(line):
    sep_list = [s.strip() for s in cfg['batch']['split_sep'].split(',') if s.strip()]
    allow_multi = cfg['batch'].get('allow_multi_sep', False)

    if not allow_multi:
        sep = sep_list[0]
        parts = [p.strip() for p in line.split(sep)]
        return [p for p in parts if p]

    escaped = []
    for s in sep_list:
        if s == '\\t':
            escaped.append(r'\t')
        else:
            escaped.append(re.escape(s))
    any_sep = '|'.join(escaped)

    regex = re.compile(r'''
        "(?:\\.|[^"\\])"
        | '(?:\\.|[^'\\])'
        | [^%s]+
    ''' % any_sep, re.VERBOSE)

    parts = []
    for m in regex.findall(line):
        m = m.strip()
        if not m:
            continue
        if (m.startswith('"') and m.endswith('"')) or (m.startswith("'") and m.endswith("'")):
            m = m[1:-1]
        parts.append(m)
    return parts

def batch_parse_and_save(multi_text):
    if AUTO_BACKUP_MODIFY:
        backup_db_safe()

    lines = multi_text.strip().splitlines()
    count = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        parts = smart_split_line(line)
        if len(parts) < 5:
            continue

        try:
            ymd, content, prio, imp, star_str = parts[:5]
            y, m, d = map(int, ymd.split('-'))
            star = max(1, min(5, int(star_str)))
            title = content[:20]
            add_single_log(y, m, d, title, content, prio, imp, star)
            count += 1
        except:
            continue
    return count

def query_by_day(year, month, day, condition=None):  # 新增 condition，兼容旧代码
    sql = '''
    SELECT * FROM log_main 
    WHERE year=? AND month=? AND day=?
    '''
    params = [year, month, day]

    # 如果有额外条件，拼接（用于 当周/当月/全部）
    if condition is not None:
        sql += f' AND ({condition})'

    sql += ' ORDER BY star DESC, priority DESC'

    with db_conn() as c:
        return c.execute(sql, params).fetchall()

def query_by_week(year, week):
    with db_conn() as c:
        return c.execute('''
        SELECT * FROM log_main WHERE year=? AND week_num=?
        ORDER BY month,day
        ''', (year,week)).fetchall()

def query_logs(year=None, month=None, day=None, condition=None,order_by='star DESC, priority DESC', query_params=None):
    sql = "SELECT * FROM log_main WHERE 1=1"
    params = query_params.copy() if query_params else []

    if year:
        sql += " AND year=?"
        params.append(year)
    if month:
        sql += " AND month=?"
        params.append(month)
    if day:
        sql += " AND day=?"
        params.append(day)
    if condition:
        sql += f" AND ({condition})"

    sql += f' ORDER BY {order_by}'

    with db_conn() as c:
        return c.execute(sql, params).fetchall()

def advanced_log_query(cond):
    condition_parts = []
    params = []

    # ======================
    # 1. 日期条件
    # ======================
    if "date_eq" in cond:
        y, m, d = cond["date_eq"].split("-")
        condition_parts.append("year=? AND month=? AND day=?")
        params.extend([y, m, d])

    if "date_range" in cond:
        start, end = cond["date_range"]
        sy, sm, sd = start.split("-")
        ey, em, ed = end.split("-")
        # 日期区间拼接
        condition_parts.append("""
            (year > ?) 
            OR (year = ? AND month > ?) 
            OR (year = ? AND month = ? AND day >= ?)
        """)
        params.extend([sy, sy, sm, sy, sm, sd])

        condition_parts.append("""
            (year < ?) 
            OR (year = ? AND month < ?) 
            OR (year = ? AND month = ? AND day <= ?)
        """)
        params.extend([ey, ey, em, ey, em, ed])

    # ======================
    # 2. 标题/正文 搜索（模糊/精确/正则）
    # ======================
    if "text_cols" in cond:
        kw = cond["keyword"]
        mtype = cond["match_type"]
        text_parts = []

        for col in cond["text_cols"]:
            if mtype == "模糊匹配":
                text_parts.append(f"{col} LIKE ?")
                params.append(f"%{kw}%")
            elif mtype == "精确匹配":
                text_parts.append(f"{col} = ?")
                params.append(kw)
            elif mtype == "正则匹配":
                text_parts.append(f"{col} REGEXP ?")
                params.append(kw)

        condition_parts.append(" OR ".join(text_parts))

    # ======================
    # 3. 组合 condition 并调用你原来的函数
    # ======================
    final_condition = " AND ".join(f"({p})" for p in condition_parts) if condition_parts else None

    # 调用【原函数】完成查询！！！
    return query_logs(
        condition=final_condition,
        query_params=params
    )

def search_log(keyword):
    k = f'%{keyword}%'
    with db_conn() as c:
        return c.execute('''
        SELECT * FROM log_main
        WHERE title LIKE ? OR content LIKE ? OR category LIKE ?
        ''', (k,k,k)).fetchall()

def update_log_by_id(log_id, **kwargs):
    # 从配置读取允许更新的字段
    allowed_fields = load_config_toml()["update"]["allowed_fields"]

    # 收集要更新的字段
    update_fields = []
    values = []

    # 用户传入的合法字段
    for key, value in kwargs.items():
        if key in allowed_fields:
            update_fields.append(f"{key}=?")
            values.append(value)

    if not update_fields:
        return

    # ==========================================================
    # 核心逻辑：只要改了 年/月/日 任意一个，就重新计算周数
    # ==========================================================
    date_fields = {'year', 'month', 'day'}
    # 判断是否修改了任意日期字段
    if date_fields & kwargs.keys():
        # 先从数据库查出当前完整的 年、月、日
        with db_conn() as conn:
            cursor = conn.execute(
                "SELECT year, month, day FROM log_main WHERE id = ?",
                (log_id,)
            )
            current_year, current_month, current_day = cursor.fetchone()
        # 用最新的值（传入的覆盖数据库里的）
        final_year = kwargs.get('year', current_year)
        final_month = kwargs.get('month', current_month)
        final_day = kwargs.get('day', current_day)
        # 计算正确的周数
        week_num = get_week_num(final_year, final_month, final_day)

        # 加入更新
        update_fields.append("week_num = ?")
        values.append(week_num)

    # 强制自动更新时间（不受配置限制）
    update_fields.append("update_time=?")
    values.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


    # 执行 SQL
    sql = f"UPDATE log_main SET {', '.join(update_fields)} WHERE id=?"
    values.append(log_id)

    with db_conn() as conn:
        conn.execute(sql, values)

    if 'category' in kwargs.keys():
        add_category_if_not_exists(kwargs['category'])
