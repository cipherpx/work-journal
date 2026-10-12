from core.log_service import query_by_day, query_by_week
from core.cfg_manager import get_root_path,load_config_toml
import os
from core.utils import replace_docx_content
from datetime import datetime, timedelta
from docx import Document

TPL_DIR = os.path.join(get_root_path(), str(load_config_toml()['path']['template_dir']))

def load_tpl(name):
    path = os.path.join(TPL_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
def load_tplx(tpl_path: str, save_path: str, replace_map: dict):
    """
        读取docx模板，替换占位文字，保留全部格式，另存文件
        :param tpl_path: 模板docx路径
        :param save_path: 输出新文件路径
        :param replace_map: 替换字典 {占位符: 替换内容}
    """
    # 加载模板文档
    docx = Document(os.path.join(TPL_DIR, tpl_path))

    replace_docx_content(docx, replace_map)
    # 另存为新文件，原模板不变
    docx.save(save_path)
    return save_path

def load_star_char():
    # 自动获取项目根路径，100%找到 config.toml
    #base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    #config_path = os.path.join(base_dir, "config.toml")
    # 加载配置
    #config = toml.load(config_path)
    return load_config_toml()['display']['star_symbol']

# 星星转换函数
def star_to_str(level):
    level = max(1, min(5, int(level)))
    return load_star_char() * level

def gen_daily_report(year, month, day):
    items = sort_items(query_by_day(year, month, day))

    group = {}
    num = {}
    for it in items:
        # 忽略星级为0的条目
        if it[10] == 0:
            continue

        cls = it[11]
        if cls not in group:
            group[cls] = []
            num[cls] = 1
        #group[cls].append(f"{star_to_str(it[10])}【{it[6]}】{it[7]}")
        group[cls].append(f'{num[cls]:02d}. {it[6]}：{it[7]}')
        num[cls] += 1

    tpl = load_tpl("daily.tpl")
    content = f"{year}年{month}月{day}日"

    # 按 config.toml 中的分类顺序排序
    category_order = load_config_toml()['category']['options']
    # 按配置文件顺序输出
    sorted_groups = [k for k in category_order if k in group]
    # 用排序后的分类输出
    for k in sorted_groups:
        content += f'\n■ {k}\n' + '\n'.join(group[k]) + '\n'
    return tpl.replace("{{content}}", content).replace("{{now}}", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


def gen_weekly_report_old(year, week):
    from datetime import datetime, timedelta

    first_day = datetime.fromisocalendar(year, week, 1)
    last_day = first_day + timedelta(days=6)

    week_line = f'{year}年第{week}周'
    range_line = f'{first_day.year}.{first_day.month}.{first_day.day}-{last_day.year}.{last_day.month}.{last_day.day}'

    items = query_by_week(year, week)
    group = {}
    for it in items:
        cls = it[11]

        if cls not in group:
            group[cls] = []
        real_month = it[3]
        real_day = it[4]
        group[cls].append(f'{real_month}月{real_day}日：{it[6]}')

    tpl = load_tpl('weekly.tpl')
    content = f'{week_line}\n{range_line}\n'

    for k, v in group.items():
        content += f'\n【{k}】\n' + '\n'.join(v)

    return tpl.replace("{{content}}", content).replace("{{now}}", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

def gen_weekly_report(year, week):

    # 1. 获取本周起止日期
    first_day = datetime.fromisocalendar(year, week, 1)
    last_day = first_day + timedelta(days=6)

    week_line = f'{year}年第{week}周'
    range_line = f'{first_day.year}.{first_day.month}.{first_day.day}-{last_day.year}.{last_day.month}.{last_day.day}'

    # 查询数据
    items = sort_items(query_by_week(year, week))
    if not items:
        return ''

    # 4. 读取配置分类顺序
    try:
        cate_order = load_config_toml()['category']['options']
    except:
        cate_order = ['实验', '工作', '生活', '学习', '自定义']

    # 分组合并
    group = {}
    for it in items:
        # 忽略星级为0的条目
        if it[10] == 0:
            continue

        cls = it[11]
        title = it[6].strip()

        if not title:
            continue

        if cls not in group:
            group[cls] = {}

        prefix = title[:2]
        if prefix not in group[cls]:
            group[cls][prefix] = []

        group[cls][prefix].append(title)

    # 按配置顺序拼接内容
    tpl = load_tpl('weekly.tpl')
    content = f'{week_line}\n{range_line}\n'

    for cate in cate_order:
        if cate not in group:
            continue

        content += f'\n【{cate}】\n'
        idx = 1

        for prefix, titles in group[cate].items():
            show=[]
            for t in titles:
                if len(t) > 2 and t[2:] not in show:
                    show.append(t[2:])
                elif len(t) <= 2 and t not in show:
                    show.append(t)
            show[0] = prefix + '：'+ show[0]
            content += f'{idx}. {'、'.join(show)}\n'
            idx += 1

    return tpl.replace("{{content}}", content).replace("{{now}}", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

def save_weekly_report_to_docx(year, week):
    cfg = load_config_toml()
    replace_dict = cfg['template_map']
    prefix_order = cfg['category']['prefix_order']

    first_day = datetime.fromisocalendar(year, week, 1)
    last_day = first_day + timedelta(days=6)

    replace_dict['{{YYYY}}'] = year
    replace_dict['{{WEEK}}'] = week
    replace_dict['{{START_DAY}}'] = first_day.strftime('%Y.%m.%d')
    replace_dict['{{END_DAY}}'] = last_day.strftime('%Y.%m.%d')

    # 查询数据
    items = sort_items(query_by_week(year, week))
    if not items:
        return ''

    # 4. 读取配置分类顺序
    try:
        cate_order = load_config_toml()['category']['options']
    except:
        cate_order = ['实验', '工作', '生活', '学习', '自定义']

    # 分组合并
    group = {}
    for it in items:
        # 忽略星级为0的条目
        if it[10] == 0:
            continue

        cls = it[11]
        title = it[6].strip()

        if not title:
            continue

        if cls not in group:
            group[cls] = {}

        prefix = title[:2]
        if prefix not in group[cls]:
            group[cls][prefix] = []

        group[cls][prefix].append(title)

    for cate in cate_order:
        if cate not in group:
            continue

        if f'{{{{{cate}}}}}' not in replace_dict.keys():
            continue
        idx = 1
        content = ''
        logs = []
        prefix_list = [k for k in prefix_order if k in group[cate].keys()]
        prefix_list += [k for k in group[cate].keys() if k not in prefix_order]
        # for prefix, titles in group[cate].items():
        for prefix in prefix_list:
            titles = group[cate][prefix]
            show=[]
            for t in titles:
                t = t[2:] if len(t) > 2 else t
                if t not in logs:
                    show.append(t)
                    logs.append(t)
            if show:
                show[0] = prefix + '：' + show[0]
                content += f'{idx}. {'、'.join(show)}\n'
                idx += 1
        replace_dict['{{'+ cate + '}}'] = content.rstrip('\n')

    for k,v in replace_dict.items():
        if not v:
            replace_dict[k] = '无'

    return load_tplx('weekly.tplx',os.path.join(cfg['path']['weekly_report_dir'],f'周汇报_{year}_{week}_{first_day.strftime('%m%d')}_{last_day.strftime('%m%d')}.docx'),replace_dict)



# ======================
# 独立排序函数
# ======================
def sort_items(items):
    config = load_config_toml()
    priority_order = config.get("sort", {}).get("priority", {"高": 3, "中": 2, "低": 1})
    importance_order = config.get("sort", {}).get("importance", {"重要": 3, "次要": 2, "一般": 1})

    #排序：星级 → 优先级 → 重要度 → 早晚
    items = sorted(
        items,
        key=lambda x: (
            -int(x[10]),
            -priority_order.get(x[8], 1),
            -importance_order.get(x[9], 1),
            x[0]
        )
    )
    return items