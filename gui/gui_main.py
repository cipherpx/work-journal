import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk, scrolledtext, messagebox, filedialog
from core.backup_core import backup_db_safe_hot
from core.log_service import add_single_log, batch_parse_and_save, query_logs
from core.gen_report import gen_daily_report, gen_weekly_report, save_weekly_report_to_docx
from core.export_core import export_daily_all, export_weekly_all
from core.cfg_manager import load_config_toml, update_config_category, open_license
from core.constants import APP_VERSION, ABOUT_ART, REPO_URL
from tkcalendar import DateEntry
from datetime import date, datetime, timedelta
from core.utils import parse_and_fix_date, show_save_success, get_week_num
from core.log_service import update_log_by_id


class LogGUI:

    OP_NUMBER = ["=", "!=", ">", "<", ">=", "<="]
    OP_TEXT_FUZZY = ["包含", "不包含", "=", "!="]
    OP_DATETIME_SHORTCUT = ["近一周", "近一月", "近三个月", "近半年", "近一年"]
    DEFAULT_DATETIME_SHORTCUT = OP_DATETIME_SHORTCUT[0]
    OP_DATETIME = OP_DATETIME_SHORTCUT + OP_NUMBER + ["自定义区间"]

    OP_SQL_MAP = {
        "=": "=",
        "!=": "!=",
        ">": ">",
        "<": "<",
        ">=": ">=",
        "<=": "<=",
        "包含": "LIKE",
        "不包含": "NOT LIKE",
    }

    def __init__(self, root):
        self.root = root
        self.root.title('日志管理系统')

        try:
            self.config = load_config_toml()

            self.cate_options = self.config['category']['options']
            self.cate_default = self.config['category']['default']
        except:
            self.config = None
            self.cate_options = ['实验', '工作', '生活', '学习', '自定义']
            self.cate_default = '实验'

        self.star_val = 1
        self.star_labels = []

        # 日志查询与编辑所需变量
        self.query_logs = []  # 保存查询到的日志列表
        self.current_query_period = "all"  # 当前查询时间段
        self.edit_log_id = None  # 正在编辑的日志ID（None=新增模式）

        self.edit_btn_frame = None
        self.edit_origin_data = {}

        self.allow_edit_period = self.config.get("edit", {}).get("allow_edit_period", ["day", "week"])
        self.allow_edit_cols = self.config.get("edit", {}).get("allow_edit_cols", [])
        self.all_cols = self.config["edit"]["all_cols"]
        self.col_cn_map = self.config["edit"].get("col_cn", {})
        self.db_col_to_idx = self.config["tuple_index"]["log_main"]

        # 增加右键快捷菜单
        self.right_menu = tk.Menu(self.root, tearoff=0)
        self.right_menu.add_command(label='另存周报', command=self.save_weekly_report)

        # 日志搜索动态筛选面板配置
        self.condition_rows = []
        self.exclude_search_cols = self.config["edit"].get("exclude_search_cols", [])
        self.col_type_map = self.config["edit"].get("col_type", {})
        self.cn_to_col_map = {cn: col for col, cn in self.col_cn_map.items()}
        self.star_options = self.config["ui_filter_options"]["star"]
        self.sort_priority_map = self.config["sort"]["priority"]
        self.sort_importance_map = self.config["sort"]["importance"]
        self.rank_field_map = {
            "priority": self.sort_priority_map,
            "importance": self.sort_importance_map
        }
        self.extra_rows_hidden = False

        #self.root.geometry("1200x800")
        w = 1200
        h = 800
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.create_widgets()


    def create_widgets(self):
        # 标签页
        self.notebook = ttk.Notebook(self.root)
        self.tab1 = ttk.Frame(self.notebook)
        # 让 tab1 整体可以拉伸
        self.tab1.grid_rowconfigure(3, weight=1)
        # 让第1、2、3、4、5列均分宽度
        for col in range(1, 6):
            self.tab1.grid_columnconfigure(col, weight=1)
        self.tab2 = ttk.Frame(self.notebook)
        self.tab3 = ttk.Frame(self.notebook)
        self.tab4 = ttk.Frame(self.notebook)
        self.tab5 = ttk.Frame(self.notebook)
        self.tab6 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab1, text="逐条登记")
        self.notebook.add(self.tab2, text="批量导入")
        self.notebook.add(self.tab3, text="日报/周报")
        self.notebook.add(self.tab4, text="日志查询")
        self.notebook.add(self.tab5, text="日志搜索")
        self.notebook.add(self.tab6, text="关于")
        self.notebook.pack(expand=True, fill='both')
        self.notebook.bind("<<NotebookTabChanged>>", self.tab_switch_focus)

        # -------- 逐条登记 --------
        # 日历选择框 + 分类 同行
        # 日期 日历选择框（稳定不消失）
        ttk.Label(self.tab1, text='日期：').grid(row=0, column=0, padx=5, pady=5, sticky='w')

        self.date_entry = DateEntry(
            self.tab1,
            # width=12,
            date_pattern='yyyy-mm-dd',
            locale='zh_CN',
        )
        self.date_entry.grid(row=0, column=1, padx=3, pady=5, sticky='ew')

        # 分类
        ttk.Label(self.tab1, text='分类：', anchor="center").grid(row=0, column=2, padx=(0, 5), pady=5, sticky='ew')
        self.cate_var = tk.StringVar(value=self.cate_default)
        self.cate_cb = ttk.Combobox(
            self.tab1,
            textvariable=self.cate_var,
            values=self.cate_options,
            state='readonly'
        )
        self.cate_cb.grid(row=0, column=3, padx=5, pady=5, sticky='ew')
        self.cate_cb.bind('<<ComboboxSelected>>', self.on_cate_selected)

        # 优先级
        ttk.Label(self.tab1, text="优先级：").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.prio_var = tk.StringVar(value="低")
        ttk.Combobox(self.tab1, textvariable=self.prio_var, values=["高", "中", "低"]) \
            .grid(row=1, column=1, padx=3, pady=5, sticky="ew")

        # 重要度 标签居中
        lab_imp = ttk.Label(self.tab1, text="重要度：", anchor="center")
        lab_imp.grid(row=1, column=2, padx=5, pady=5, sticky="ew")
        self.imp_var = tk.StringVar(value="一般")
        ttk.Combobox(self.tab1, textvariable=self.imp_var, values=["重要", "次要", "一般"]) \
            .grid(row=1, column=3, padx=3, pady=5, sticky="ew")

        # 星级标签 + 星星放在同一个单元格内横向排列，不溢出
        # 星级标签居中
        lab_star = ttk.Label(self.tab1, text="星级：", anchor="center")
        lab_star.grid(row=1, column=4, padx=5, pady=5, sticky="e")

        # 星星放进Frame，不溢出
        star_frame = ttk.Frame(self.tab1)
        star_frame.grid(row=1, column=5, padx=0, pady=5, sticky="w")

        self.star_val = 1  # 默认1星
        self.star_labels = []

        # 生成5个可点击星星
        for i in range(5):
            lbl = ttk.Label(star_frame, text="★", font=("微软雅黑", 12))
            lbl.pack(side="left", padx=2)
            # 绑定点击事件
            lbl.bind("<Button-1>", lambda e, idx=i: self.set_star(idx))
            self.star_labels.append(lbl)

        # 初始化星星显示
        self.refresh_star()

        ttk.Label(self.tab1, text="标题：").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.title_var = tk.StringVar()
        # ttk.Entry(self.tab1, textvariable=self.title_var, width=50).grid(row=1, column=1, columnspan=3)
        self.title_entry = ttk.Entry(self.tab1, textvariable=self.title_var)
        self.title_entry.grid(row=2, column=1, columnspan=5, padx=5, pady=5,sticky='ew')
        self.bind_double_clear(self.title_entry)

        ttk.Label(self.tab1, text="内容：").grid(row=3, column=0, padx=5, pady=5, sticky="nw")
        self.content_text = scrolledtext.ScrolledText(self.tab1, width=80, height=20,undo=True)
        self.content_text.config(maxundo=2)
        self.content_text.grid(row=3, column=1, columnspan=5, padx=5, pady=5, sticky='nsew')
        self.bind_double_clear(self.content_text)

        ttk.Button(self.tab1, text="保存", command=self.save_single).grid(row=4, column=1, pady=10)
        ttk.Button(self.tab1, text="清空", command=lambda: self.clear_single('Manual')).grid(row=4, column=2, pady=10)

        # -------- 批量导入 --------
        ttk.Label(self.tab2, text="粘贴多行数据（每行一条，格式：YYYY-MM-DD | 内容 | 优先级 | 重要度 | 星级）：").pack(pady=5)
        self.batch_text = scrolledtext.ScrolledText(self.tab2, width=100, height=30)
        self.batch_text.pack(padx=5, pady=5, fill="both", expand=1)
        ttk.Button(self.tab2, text="批量导入", command=self.do_batch).pack(pady=5)

        # -------- 日报/周报 --------
        ttk.Label(self.tab3, text="日期（日报）：").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.daily_y = tk.IntVar(value=date.today().year)
        self.daily_m = tk.IntVar(value=date.today().month)
        self.daily_d = tk.IntVar(value=date.today().day)
        ttk.Entry(self.tab3, textvariable=self.daily_y, width=6).grid(row=0, column=1)
        ttk.Entry(self.tab3, textvariable=self.daily_m, width=4).grid(row=0, column=2)
        ttk.Entry(self.tab3, textvariable=self.daily_d, width=4).grid(row=0, column=3)
        ttk.Button(self.tab3, text="生成日报", command=self.make_daily).grid(row=0, column=4, padx=5)

        ttk.Label(self.tab3, text="周次（周报）：").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.week_y = tk.IntVar(value=date.today().year)
        self.week_w = tk.IntVar(value=get_week_num(date.today().year, date.today().month, date.today().day))
        ttk.Entry(self.tab3, textvariable=self.week_y, width=6).grid(row=1, column=1)
        ttk.Entry(self.tab3, textvariable=self.week_w, width=4).grid(row=1, column=2)
        ttk.Button(self.tab3, text="生成周报", command=self.make_weekly).grid(row=1, column=4, padx=5)

        self.report_text = scrolledtext.ScrolledText(self.tab3, width=100, height=25,undo=True)
        self.report_text.config(maxundo=2)
        self.report_text.grid(row=2, column=0, columnspan=5, padx=5, pady=5, sticky="nsew")
        self.tab3.grid_rowconfigure(2, weight=1)
        self.tab3.grid_columnconfigure(0, weight=1)
        # 增加双击清空文本、右键菜单功能
        self.bind_double_clear(self.report_text)
        self.report_text.bind('<Button-3>', self.pop_right_menu)

        # ====================== 查询面板 ======================
        self.create_query_tab()
        # ====================== 日志搜索 ======================
        self.create_search_tab()
        # ======================  About ======================
        self.create_about_tab()

    def pop_right_menu(self, event):
        # 记录当前触发右键的控件
        self.current_widget = event.widget
        if isinstance(self.current_widget, scrolledtext.ScrolledText) and len(self.current_widget.get('1.0', tk.END).strip()) == 0:
            return
        # 在鼠标坐标弹出菜单
        self.right_menu.tk_popup(event.x_root, event.y_root)
    def save_weekly_report(self):
        #widget = self.current_widget
        try:
            output_file = save_weekly_report_to_docx(self.week_y.get(),self.week_w.get())
            #messagebox.showinfo('成功', f'周报已生成并导出: {output_file}')
            show_save_success(self.root,output_file,f'周报已生成并导出: {output_file}','成功')
        except Exception as e:
            messagebox.showerror('错误', f'生成失败：{e}')

    # 通用清空逻辑
    def clear_widget(self, event, widget):
        # 判断是单行输入框Entry
        if isinstance(widget, ttk.Entry):
            widget.delete(0, tk.END)
        # 滚动文本框
        else:
            widget.delete('1.0', tk.END)
            # 清除选中高亮
            widget.tag_remove(tk.SEL, '1.0', tk.END)
            # 光标放到起始位置
            widget.mark_set(tk.INSERT, '1.0')
        # return "break" 阻断tkinter自带双击选中整行逻辑
        return 'break'

    # 绑定工具方法
    def bind_double_clear(self, widget):
        widget.bind("<Double-Button-1>", lambda e: self.clear_widget(e, widget))


    def create_query_tab(self):
        # ========== 顶部查询区域 ==========
        self.top_frame = ttk.Frame(self.tab4)
        self.top_frame.pack(fill="x", padx=10, pady=8)

        ttk.Label(self.top_frame, text="查询范围：").pack(side="left", padx=5)

        self.query_period = tk.StringVar(value="day")
        options = [
            ("所有日志", "all"),
            ("当日", "day"),
            ("当周", "week"),
            ("当月", "month"),
            ("当年", "year")
        ]
        for txt, val in options:
            ttk.Radiobutton(
                self.top_frame, text=txt, variable=self.query_period, value=val
            ).pack(side="left", padx=3)

        # ========== 按钮 ==========
        self.query_btn = ttk.Button(self.top_frame, text="查询", command=self.do_query_log)
        self.query_btn.pack(side="left", padx=5)
        ttk.Button(self.top_frame, text="编辑", command=self.open_inline_edit).pack(side="left", padx=5)
        self.bakdb_btn = ttk.Button(self.top_frame, text="手动备份数据库", command=self.on_backup_db)
        self.bakdb_btn.pack(side="right", padx=15)


        # ========== 结果列表 ==========
        # 【升级：新增序号列 + 星级/优先级/重要性/更新时间 + 日志ID】
        """过时
        self.query_tree = ttk.Treeview(None, columns=(
            "seq",  # 序号（新）
            "id",  # 日志ID
            "date",  # 日期
            "category",  # 分类
            "title",  # 标题
            "content",  # 内容
            "star",  # 星级（新）
            "priority",  # 优先级（新）
            "importance",  # 重要性（新）
            "update_time"  # 更新时间（新）
        ), show="headings")
        """
        self.query_tree = ttk.Treeview(None,columns=self.all_cols, show="headings")

        style = ttk.Style()
        style.configure("Treeview.Heading", anchor="center")
        style.configure("Treeview", rowheight=25)

        # ---------------- 列定义 ----------------
        """
        self.query_tree.heading("seq", text="序号")
        self.query_tree.heading("id", text="日志ID")
        self.query_tree.heading("date", text="日期")
        self.query_tree.heading("category", text="分类")
        self.query_tree.heading("title", text="标题")
        self.query_tree.heading("content", text="内容")
        self.query_tree.heading("star", text="星级")
        self.query_tree.heading("priority", text="优先级")
        self.query_tree.heading("importance", text="重要性")
        self.query_tree.heading("update_time", text="更新时间")"""

        for col_name in self.all_cols:
            self.query_tree.heading(col_name, text=self.col_cn_map[col_name])

        # ---------------- 列宽 ----------------
        # 短列固定宽度，禁止挤压 stretch=False
        self.query_tree.column("seq", width=50, anchor="center", stretch=False)
        self.query_tree.column("id", width=50, anchor="center", stretch=False)
        self.query_tree.column("date", width=100, anchor="center", stretch=False)
        self.query_tree.column("category", width=80, anchor="center", stretch=False)
        self.query_tree.column("title", width=150, anchor="center", stretch=False)
        self.query_tree.column("star", width=40, anchor="center", stretch=False)
        self.query_tree.column("priority", width=70, anchor="center", stretch=False)
        self.query_tree.column("importance", width=70, anchor="center", stretch=False)
        self.query_tree.column("update_time", width=150, anchor="center", stretch=False)
        self.query_tree.column("content", width=400,minwidth=250, anchor="w", stretch=False)

        # 双击编辑
        self.query_tree.bind('<Double-1>', self.tree_cell_edit)

        # 表格+横竖滚动条容器（全部pack，无grid冲突）
        tree_box = ttk.Frame(self.tab4)
        tree_box.pack(fill="both", expand=True, padx=10, pady=10)

        # 表格+垂直滚动条一行
        row_frame = ttk.Frame(tree_box)
        row_frame.pack(fill="both", expand=True)

        v_scroll = ttk.Scrollbar(row_frame, orient="vertical", command=self.query_tree.yview)
        self.query_tree.configure(yscrollcommand=v_scroll.set)
        self.query_tree.pack(side="left", fill="both", expand=True, in_=row_frame)
        v_scroll.pack(side="right", fill="y")

        # 底部水平滚动条
        h_scroll = ttk.Scrollbar(tree_box, orient="horizontal", command=self.query_tree.xview)
        self.query_tree.configure(xscrollcommand=h_scroll.set)
        h_scroll.pack(fill="x")

        # 状态栏
        self.status_bar = ttk.Label(self.tab4, text="● 就绪", anchor="w")
        self.status_bar.pack(side='bottom', fill='x', padx=5, pady=2)

        # 存储查询结果
        self.query_logs = []

    def create_search_tab(self):
        """日志搜索页面，支持多字段组合筛选，只读表格展示查询结果。
        布局范式与tab4保持统一，保证跨页面渲染行为一致。
        """
        # 网格权重配置，与tab4完全相同，保障纵向拉伸
        self.tab5.columnconfigure(0, weight=1)
        self.tab5.rowconfigure(1, weight=1)

        # 顶部筛选面板 row=0
        frm_filter = ttk.LabelFrame(self.tab5, text="筛选条件")
        frm_filter.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        frm_filter.columnconfigure(0, weight=1)

        # 第0行：添加筛选条件按钮
        frm_btn_add = ttk.Frame(frm_filter)
        frm_btn_add.grid(row=0, column=0, sticky="w", padx=6, pady=3)

        btn_add_row = ttk.Button(frm_btn_add, text="添加筛选条件", command=self.add_condition_row)
        btn_add_row.pack(side="left")

        btn_clear_input = ttk.Button(frm_btn_add, text="清空输入条件", command=self.clear_condition_inputs)
        btn_clear_input.pack(side="left", padx=4)

        self.btn_remove_extra = ttk.Button(frm_btn_add, text="移除新增条件", command=self.remove_added_rows)
        self.btn_remove_extra.pack(side="left", padx=4)

        self.btn_remove_blank = ttk.Button(frm_btn_add, text="移除空白条件", command=self.remove_blank_condition_rows)
        self.btn_remove_blank.pack(side="left", padx=4)


        # 第1行：动态条件行容器
        self.frame_condition_container = ttk.Frame(frm_filter)
        self.frame_condition_container.grid(row=1, column=0, sticky="ew", padx=6, pady=3)
        self.frame_condition_container.columnconfigure(0, weight=1)

        # 第2行：功能按钮行，沿用原有回调函数名称
        frm_btn = ttk.Frame(frm_filter)
        frm_btn.grid(row=2, column=0, pady=8, sticky="w")

        self.btn_search: ttk.Button = ttk.Button(frm_btn, text="搜索", command=self.on_log_search)
        self.btn_search.grid(row=0, column=0, padx=3)

        self.btn_toggle_extra = ttk.Button(frm_btn, text="折叠附加条件",command=self.toggle_extra_condition_rows,state="disabled")
        self.btn_toggle_extra.grid(row=0, column=1, padx=3)

        ttk.Button(frm_btn, text="克隆选中日志", command=self.on_clone_selected_log).grid(row=0, column=2, padx=3)

        # 页面加载自动生成默认1条条件行
        self.add_condition_row()

        # ------------------------------
        # 结果表格容器 row=1，与tab4容器结构完全一致
        # ------------------------------
        tree_container = ttk.Frame(self.tab5)
        tree_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)

        # 表格样式
        style = ttk.Style()
        style.configure("Treeview.Heading", anchor="center")
        style.configure("Treeview", rowheight=25)

        self.search_tree = ttk.Treeview(tree_container, columns=self.all_cols, show="headings")
        # 表头映射
        for col_name in self.all_cols:
            self.search_tree.heading(col_name, text=self.col_cn_map[col_name])
        # 列属性配置
        self.search_tree.column("seq", width=50, anchor="center", stretch=False)
        self.search_tree.column("id", width=50, anchor="center", stretch=False)
        self.search_tree.column("date", width=100, anchor="center", stretch=False)
        self.search_tree.column("category", width=80, anchor="center", stretch=False)
        self.search_tree.column("title", width=150, anchor="center", stretch=False)
        self.search_tree.column("star", width=40, anchor="center", stretch=False)
        self.search_tree.column("priority", width=68, anchor="center", stretch=False)
        self.search_tree.column("importance", width=68, anchor="center", stretch=False)
        self.search_tree.column("update_time", width=150, anchor="center", stretch=False)
        self.search_tree.column("content", width=400, minwidth=250, anchor="w", stretch=False)

        # 只读限制，屏蔽双击编辑行为
        # self.search_tree.unbind("<Double-1>")
        # self.search_tree.bind("<Double-1>", lambda e: None)
        # 允许复制，不允许编辑
        self.search_tree.bind('<Double-1>', self.search_tree_cell_edit)

        # 垂直滚动条
        v_scroll = ttk.Scrollbar(tree_container, orient="vertical", command=self.search_tree.yview)
        self.search_tree.configure(yscrollcommand=v_scroll.set)
        self.search_tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")

        # 水平滚动条
        h_scroll = ttk.Scrollbar(tree_container, orient="horizontal", command=self.search_tree.xview)
        self.search_tree.configure(xscrollcommand=h_scroll.set)
        h_scroll.grid(row=1, column=0, sticky="ew")

        # ------------------------------
        # 底部状态栏 row=2
        # ------------------------------
        self.search_status = ttk.Label(self.tab5, text="● 就绪", anchor="w")
        self.search_status.grid(row=2, column=0, sticky="ew", padx=10, pady=3)

        # 查询结果缓存
        self.search_logs_raw = []

    def create_about_tab(self):
        art_label = ttk.Label(
            self.tab6,
            text=ABOUT_ART,
            font=("Consolas", 11),
            justify="left",
        )
        art_label.pack(pady=(30, 10))

        # 分隔线
        ttk.Separator(self.tab6, orient="horizontal").pack(fill="x", padx=60, pady=10)

        # 版本信息
        info_frame = ttk.Frame(self.tab6)
        info_frame.pack(pady=5)
        ttk.Label(
            info_frame,
            text="日志管理系统",
            font=("微软雅黑", 13, "bold"),
        ).pack(pady=(0, 5))

        ttk.Label(
            info_frame,
            text=f'Version {APP_VERSION}',
            font=("Consolas", 10),
            foreground="#666",
        ).pack()

        ttk.Label(
            info_frame,
            text="by cipherpx",
            font=("微软雅黑", 9),
            foreground="#888",
        ).pack(pady=(2, 0))

        ttk.Label(
            info_frame,
            text="基于 Python + Tkinter + SQLite",
            font=("微软雅黑", 9),
            foreground="#666",
        ).pack(pady=(5, 0))

        # 分隔线
        ttk.Separator(self.tab6, orient="horizontal").pack(fill="x", padx=60, pady=15)

        # 功能说明
        desc_text = (
            "功能：逐条登记 · 批量导入 · 日报周报\n"
            "          日志查询 · 日志搜索 · 数据备份"
        )
        ttk.Label(
            self.tab6,
            text=desc_text,
            font=("微软雅黑", 10),
            justify="center",
            foreground="#444",
        ).pack(pady=5)

        # 底部版权
        # 协议行：可点击 LICENSE
        bottom_row = ttk.Frame(self.tab6)
        bottom_row.pack(side="bottom", pady=(0, 15))

        ttk.Label(
            bottom_row,
            text="Licensed under a custom non-commercial license. See ",
            font=("Consolas", 9),
            foreground="#999",
        ).pack(side="left")

        license_link = ttk.Label(
            bottom_row,
            text="LICENSE",
            font=("Consolas", 9),
            foreground="#4a90d9",
            cursor="hand2",
        )
        license_link.pack(side="left")
        license_link.bind("<Button-1>", lambda e: open_license())

        ttk.Label(
            bottom_row,
            text=" for details.  ·  ",
            font=("Consolas", 9),
            foreground="#999",
        ).pack(side="left")

        github_url = f'https://github.com/{REPO_URL}'
        # GitHub（版权下方）
        link_label = ttk.Label(
            bottom_row,
            text=f"GitHub",
            font=("Consolas", 9),
            foreground="#4a90d9",
            cursor="hand2",
        )
        link_label.pack(side="left")
        link_label.bind("<Button-1>", lambda e: webbrowser.open(github_url))

        ttk.Label(
            self.tab6,
            text="© 2026 cipherpx",
            font=("Consolas", 9),
            foreground="#999",
        ).pack(side="bottom", pady=(0, 15))

    # 日志搜索筛选条件框
    def add_condition_row(self):
        row_frame = ttk.Frame(self.frame_condition_container)
        row_frame.pack(fill="x", pady=2)

        # 1. 最左侧 AND/OR 下拉
        logic_var = tk.StringVar(value="AND")
        cb_logic = ttk.Combobox(row_frame, textvariable=logic_var, values=["AND", "OR"], width=6, state="readonly")
        cb_logic.pack(side="left", padx=2)

        # 字段下拉
        field_var = tk.StringVar()
        field_options = [
            (self.col_cn_map[cid], cid)
            for cid in self.all_cols
            if cid not in self.exclude_search_cols
        ]
        disp_text_list = [item[0] for item in field_options]

        cb_field = ttk.Combobox(row_frame, textvariable=field_var, values=disp_text_list, width=10, state="readonly")
        cb_field.pack(side="left", padx=2)
        cb_field.current(0)

        # 运算符下拉
        op_var = tk.StringVar()
        cb_op = ttk.Combobox(row_frame, textvariable=op_var, width=14, state="readonly")
        cb_op.pack(side="left", padx=2)

        # 值输入框容器
        val_container = ttk.Frame(row_frame)
        val_container.pack(side="left", padx=2, fill="x", expand=True)

        # 删除按钮
        btn_del = ttk.Button(row_frame, text="×", width=2)
        btn_del.pack(side="left", padx=2)
        # 保存输入框变量，给collect_conditions读取
        entry_var = tk.StringVar()
        dt_start_var = tk.StringVar()
        dt_end_var = tk.StringVar()
        #刷新按钮状态
        entry_var.trace_add("write", lambda name, index, mode: self.update_toggle_btn_state())
        dt_start_var.trace_add("write", lambda name, index, mode: self.update_toggle_btn_state())
        dt_end_var.trace_add("write", lambda name, index, mode: self.update_toggle_btn_state())

        # 删除回调
        def del_this():
            row_frame.destroy()
            for idx, item in enumerate(self.condition_rows):
                if item["frame"] == row_frame:
                    self.condition_rows.pop(idx)
                    break
            self.sync_row_ui_state()
            self.update_toggle_btn_state()

        btn_del.config(command=del_this)

        def on_op_change(event):
            disp_text = field_var.get()
            real_col = self.cn_to_col_map.get(disp_text)
            if real_col is None:
                return
            col_t = self.col_type_map.get(real_col, "text")
            if col_t != "datetime":
                return

            op = op_var.get()
            shortcut_set = set(self.OP_DATETIME_SHORTCUT)
            # 判断新操作符所属大类
            if op in shortcut_set:
                new_kind = "shortcut"
            elif op in self.OP_NUMBER:
                new_kind = "single_dt"
            elif op == "自定义区间":
                new_kind = "range_dt"
            else:
                new_kind = None

            children = val_container.winfo_children()
            need_rebuild = True
            if children:
                if new_kind == "single_dt" and len(children) == 1:
                    need_rebuild = False
                elif new_kind == "range_dt" and len(children) > 1:
                    need_rebuild = False
                elif new_kind == "shortcut" and len(children) == 0:
                    need_rebuild = False

            if need_rebuild:
                for w in val_container.winfo_children():
                    w.destroy()
                dt_start_var.set("")
                dt_end_var.set("")

            if op in shortcut_set:
                dt_start_var.set("")
                dt_end_var.set("")
            elif op in self.OP_NUMBER:
                if need_rebuild:
                    de = DateEntry(val_container, textvariable=dt_start_var, date_pattern='yyyy-mm-dd', width=12)
                    de.pack(side="left")
                else:
                    cb_op.focus()
                dt_end_var.set("")
            elif op == "自定义区间":
                if need_rebuild:
                    ttk.Label(val_container, text="开始日期:").pack(side="left")
                    de1 = DateEntry(val_container, textvariable=dt_start_var, date_pattern='yyyy-mm-dd')
                    de1.pack(side="left", padx=2)

                    ttk.Label(val_container, text=" - ").pack(side="left")

                    ttk.Label(val_container, text="结束日期:").pack(side="left")
                    de2 = DateEntry(val_container, textvariable=dt_end_var, date_pattern='yyyy-mm-dd')
                    de2.pack(side="left", padx=2)
                else:
                    cb_op.focus()
            self.update_toggle_btn_state()

        # 切换字段时，更新运算符、生成输入控件
        def on_field_change(event):
            def _clear():
                for w in val_container.winfo_children():
                    w.destroy()
                entry_var.set("")

            def _set_op(op_values,default:int | None =None):
                """
                统一设置操作符下拉框
                :param op_values: 选项列表
                :param default: None=选第0项；int=指定索引下标
                """
                cb_op["values"] = op_values
                if not op_values:
                    return
                if default is not None and default < len(op_values):
                    pick_val = op_values[default]
                else:
                    pick_val = op_values[0]

                op_var.set(pick_val)
                cb_op.current(op_values.index(pick_val))

            def _make_combo(options, default=None):
                """在 val_container 里生成一个只读下拉框并选中默认项"""
                cb = ttk.Combobox(
                    val_container,
                    textvariable=entry_var,
                    values=options,
                    state="readonly",
                )
                cb.pack(fill="x", expand=True)
                if default is not None:
                    entry_var.set(default)
                elif options:
                    entry_var.set(options[0])

            def _make_entry():
                ttk.Entry(val_container, textvariable=entry_var).pack(fill="x", expand=True)

            # ---------- 主逻辑 ----------
            disp_text = field_var.get()
            real_col = self.cn_to_col_map.get(disp_text)

            _clear()
            if real_col is None:
                return

            col_t = self.col_type_map.get(real_col, "text")

            # 1. priority / importance
            if real_col in self.rank_field_map:
                _set_op(self.OP_NUMBER)
                tmp = list(self.rank_field_map[real_col].keys())
                _make_combo(tmp, default=tmp[-1])

            # 2. star
            elif real_col == "star":
                _set_op(self.OP_NUMBER)
                _make_combo(self.star_options, default=self.star_options[2])

            # 3. category
            elif real_col == "category":
                _set_op(self.OP_TEXT_FUZZY,2)
                _make_combo(self.cate_options[:-1], default=self.cate_default)

            # 4. datetime：不生成输入控件
            elif col_t == "datetime":
                _set_op(self.OP_DATETIME,self.OP_DATETIME.index(self.DEFAULT_DATETIME_SHORTCUT))
                dt_start_var.set("")
                dt_end_var.set("")
                cb_op.winfo_toplevel().after(0, lambda: cb_op.event_generate("<<ComboboxSelected>>"))

            # 5. 普通 number
            elif col_t == "number":
                _set_op(self.OP_NUMBER)
                _make_entry()

            # 6. 普通 text
            else:
                _set_op(self.OP_TEXT_FUZZY)
                _make_entry()

            self.update_toggle_btn_state()


        cb_field.bind("<<ComboboxSelected>>", on_field_change)
        cb_op.bind("<<ComboboxSelected>>", on_op_change)

        pack_kw = dict(fill="x", padx=4, pady=2)  # 把你真实的pack参数写进来
        row_frame.pack(**pack_kw)

        # 存入行信息
        item = {
            "logic_var": logic_var,
            "logic_cb": cb_logic,
            "frame": row_frame,
            "pack_kw": pack_kw,
            "field_var": field_var,
            "op_var": op_var,
            "op_cb": cb_op,
            "entry_var": entry_var,
            "val_container": val_container,
            "btn_del": btn_del,
            "dt_start_var": dt_start_var,
            "dt_end_var": dt_end_var,
        }
        self.condition_rows.append(item)
        self.update_toggle_btn_state()

        cb_field.event_generate("<<ComboboxSelected>>")
        # 刷新每行UI状态
        self.sync_row_ui_state()

    def sync_row_ui_state(self):
        for idx, row in enumerate(self.condition_rows):
            if idx == 0:
                # 第一行：禁用AND/OR下拉，隐藏删除按钮
                row["logic_cb"].config(state="disabled")
                row["btn_del"].pack_forget()
            else:
                # 后续行：启用AND/OR下拉，显示删除按钮
                row["logic_cb"].config(state="readonly")
                row["btn_del"].pack(side="left", padx=2)
        if len(self.condition_rows) <= 1:
            self.btn_remove_extra.config(state="disabled")
        else:
            self.btn_remove_extra.config(state="normal")

    def remove_added_rows(self):
        """移除除受保护首行以外所有新增条件行，首行保留"""
        for idx in reversed(range(1, len(self.condition_rows))):
            row = self.condition_rows[idx]
            row["frame"].destroy()
            self.condition_rows.pop(idx)
        self.sync_row_ui_state()
        self.update_toggle_btn_state()
        self.extra_rows_hidden = False

    def _row_has_value(self, row_dict):
        """判断一行条件是否填了值（兼容 text/number/datetime）"""
        disp_text = row_dict["field_var"].get()
        real_col = self.cn_to_col_map.get(disp_text)
        col_t = self.col_type_map.get(real_col, "text")
        if col_t == "datetime":
            op = row_dict["op_var"].get()
            # 默认快捷时间 → 空白（不看日期）
            if op == self.DEFAULT_DATETIME_SHORTCUT:
                return False
            # 其他快捷时间 → 有值（不看日期）
            if op in self.OP_DATETIME_SHORTCUT:
                return True
            # 普通运算符 / 自定义区间 → 起止都是今天才算空白
            today_str = date.today().strftime("%Y-%m-%d")
            start = row_dict["dt_start_var"].get().strip()
            if op in self.OP_NUMBER:
                return start != today_str
            if op == self.OP_DATETIME[-1]:
                end = row_dict["dt_end_var"].get().strip()
                return not (start == today_str and end == today_str)
            return True
        return bool(row_dict["entry_var"].get().strip())

    def _clear_row_value(self, row_dict):
        """清空一行条件的值，datetime 行重置为默认快捷时间"""
        # 普通输入/下拉
        row_dict["entry_var"].set("")
        for w in row_dict["val_container"].winfo_children():
            if isinstance(w, ttk.Entry) and not isinstance(w, DateEntry):
                w.delete(0, tk.END)

        # datetime：切回默认快捷时间
        disp_text = row_dict["field_var"].get()
        real_col = self.cn_to_col_map.get(disp_text)
        col_t = self.col_type_map.get(real_col, "text")

        if col_t != "datetime":
            return

        op = row_dict["op_var"].get()
        today_str = date.today().strftime("%Y-%m-%d")
        if op in self.OP_DATETIME_SHORTCUT:
            cb_op = row_dict.get("op_cb")
            if cb_op is not None:
                values = list(cb_op["values"])
                if self.DEFAULT_DATETIME_SHORTCUT in values:
                    cb_op.current(values.index(self.DEFAULT_DATETIME_SHORTCUT))
            return
        # 普通运算符 / 自定义区间 → 日期重置为今天
        row_dict["dt_start_var"].set(today_str)
        row_dict["dt_end_var"].set(today_str)
    def clear_condition_inputs(self):
        """条件框全部保留，只清空所有输入框里填写的文字，下拉选项不变"""
        for row in self.condition_rows:
            self._clear_row_value(row)
        self.update_toggle_btn_state()

    def remove_blank_condition_rows(self):
        """
        手动按钮触发：移除输入为空的附加条件行；首行强制保留，不做改动
        只判断输入框内容，行是否折叠隐藏不影响判断
        """
        keep_list = []
        for idx, row_dict in enumerate(self.condition_rows):
            # 首行强制保留
            if idx == 0:
                keep_list.append(row_dict)
                continue
            # 非首行：有内容则保留；空白则销毁控件
            if self._row_has_value(row_dict):
                keep_list.append(row_dict)
            else:
                row_dict["frame"].destroy()

        self.condition_rows = keep_list
        self.update_toggle_btn_state()

    def _build_rank_condition(self, col: str, op: str, user_val: str):
        """
        【内部私有】处理带业务权重的等级字段 priority / importance
        支持运算符：= != > < >= <=
        user_val：只能是标签文本(低/中/高)，不再支持直接输入数字
        return: (sql_snippet , params_list)
        """
        if col not in self.rank_field_map:
            return None, []

        label_2_weight = self.rank_field_map[col]
        val_strip = user_val.strip()

        # 只接受标签，移除数字解析逻辑
        if val_strip not in label_2_weight:
            # 非法标签，永假条件
            return "1 = 0", []
        base_weight = label_2_weight[val_strip]

        # 筛选满足运算符条件的全部标签
        satisfied_labels = []
        for label, weight in label_2_weight.items():
            if op == "=":
                ok = weight == base_weight
            elif op == "!=":
                ok = weight != base_weight
            elif op == ">":
                ok = weight > base_weight
            elif op == "<":
                ok = weight < base_weight
            elif op == ">=":
                ok = weight >= base_weight
            elif op == "<=":
                ok = weight <= base_weight
            else:
                # 不支持的运算符，永假
                return "1 = 0", []
            if ok:
                satisfied_labels.append(label)

        if not satisfied_labels:
            return "1 = 0", []

        total_cnt = len(label_2_weight)
        satisfy_cnt = len(satisfied_labels)

        # SQL片段化简
        if satisfy_cnt == 1:
            sql_snippet = f"{col} = ?"
            params = satisfied_labels
        elif (total_cnt - satisfy_cnt) == 1:
            exclude_item = (set(label_2_weight.keys()) - set(satisfied_labels)).pop()
            sql_snippet = f"{col} != ?"
            params = [exclude_item]
        else:
            placeholders = ", ".join(["?"] * satisfy_cnt)
            sql_snippet = f"{col} IN ({placeholders})"
            params = satisfied_labels

        return sql_snippet, params

    def _sub_months(self, dt: datetime, months: int):
        target_month = dt.month - months
        target_year = dt.year
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        try:
            return datetime(target_year, target_month, dt.day)
        except ValueError:
            # 取目标月份最后一天
            if target_month == 12:
                next_m = 1
                next_y = target_year + 1
            else:
                next_m = target_month + 1
                next_y = target_year
            last_day = (datetime(next_y, next_m, 1) - timedelta(days=1)).day
            return datetime(target_year, target_month, last_day)

    def _build_datetime_shortcut(self, op: str) -> str | None:
        """
        快捷时间筛选，计算“近X”的起始日期
        :param op: "近一周"/"近一月"/"近三个月"/"近半年"/"近一年"
        :return: YYYY‑MM‑dd 日期字符串，不合法返回 None
        """
        now = datetime.now()
        start_dt: datetime
        if op == "近一周":
            start_dt = now - timedelta(days=7)
        elif op == "近一月":
            start_dt = self._sub_months(now, 1)
        elif op == "近三个月":
            start_dt = self._sub_months(now, 3)
        elif op == "近半年":
            start_dt = self._sub_months(now, 6)
        elif op == "近一年":
            start_dt = self._sub_months(now, 12)
        else:
            return None

        return start_dt.strftime("%Y-%m-%d")

    def _validate_condition_rows(self, conds):
        """
        校验collect_conditions输出的conds列表
        返回 (is_valid:bool, valid_conds:list, error_msg:str)
        """
        valid_conds = []
        for idx, c in enumerate(conds):
            col = c.get("col", "")
            op = c.get("op", "")
            val = c.get("value", "").strip()
            raw_val_end = c.get("value_end") or ""
            val_end = raw_val_end.strip()

            # 下拉项为空防御
            if not col or not op:
                return False, [], f"第{idx + 1}行：字段或者运算符未选择"

            # 快捷时间运算符，无需输入值，直接放行
            if op in self.OP_DATETIME_SHORTCUT:
                valid_conds.append(c)
                continue

            # DB查询条件：value不能为空
            if op == self.OP_DATETIME[-1]:
                if not val or not val_end:
                    return False, [], f"第{idx + 1}行：自定义区间需要填写开始、结束两个日期"
                valid_conds.append(c)
                continue
            if not val:
                continue

            valid_conds.append(c)

        # 全部过滤完，一条有效条件都没有
        if len(valid_conds) == 0:
            if len(conds) == 1:
                # 仅首行、且无有效DB条件，返回ok，上层condition_sql=None查询全部
                return True, [], ""
            else:
                # 有多条条件行，但全部DB条件为空 → 弹窗提示
                return False, [], "至少填写一条筛选条件输入内容"

        return True, valid_conds, ""

    def _build_pubmed_where(self, parts: list[str], logics: list[str]) -> str | None:
        """
        PubMed风格行前置逻辑拼接
        parts: 有效子条件片段列表
        logics: 逻辑运算符列表，长度 = len(parts)-1
        返回带嵌套括号完整where表达式
        """
        if not parts:
            return None
        if len(logics) > len(parts) - 1:
            logics = logics[:len(parts) - 1]
        expr = parts[0]
        for logic, part in zip(logics, parts[1:]):
            expr = f"({expr}) {logic} ({part})"
        return expr

    def collect_conditions(self):
        """
        收集全部筛选条件行的数据
        返回值：list[dict]，每一行条件对应一条字典

        返回字典字段说明：
            logic: str
                当前行与上一行的逻辑关系，"AND" / "OR"
                ⚠️第一行的logic无实际业务意义，拼接查询时需要忽略

            col: str
                数据库真实列名，由界面中文表头通过 cn_to_col_map 转换得到

            op: str
                运算符，来源各字段对应的运算符下拉框
                数字类：=, !=, >, <, >=, <=
                文本类：=, !=, 包含, 不包含
                时间类：近一周,近一月,近三个月,近半年,近一年,自定义区间（暂未实现）

            value: str
                筛选输入值，来自值组件(entry_var)
                    - combobox下拉选项：选中的文本
                    - category选【自定义】：用户手动输入的字符串

            value_end: str | None
            仅【自定义区间】有效，结束日期；其余条件为None

        特殊处理：
            1. 字段解析失败(找不到真实列名)，直接丢弃该行条件
            2. datetime字段：强制清空value，暂不实现时间取值
            3. 前后空格自动strip()
        """
        cond_list = []
        for row_item in self.condition_rows:
            logic = row_item["logic_var"].get()
            disp_cn = row_item["field_var"].get()
            op = row_item["op_var"].get()

            real_col = self.cn_to_col_map.get(disp_cn)
            if not real_col:
                continue

            col_t = self.col_type_map.get(real_col, "text")

            val_end = None
            if col_t == "datetime":
                val = row_item["dt_start_var"].get().strip()
                if op == "自定义区间":
                    val_end = row_item["dt_end_var"].get().strip()
            else:
                val = row_item["entry_var"].get().strip()

            cond_list.append({
                "logic": logic,
                "col": real_col,
                "op": op,
                "value": val,
                "value_end": val_end,
            })
        return cond_list

    def on_log_search(self):
        """日志搜索触发入口"""
        try:
            self.update_toggle_btn_state()
            conds = self.collect_conditions()
            ok, valid_conds, err_msg = self._validate_condition_rows(conds)
            if not ok:
                tk.messagebox.showwarning("条件校验失败", err_msg)
                return

            sub_parts = []
            sub_logics = []
            params = []

            for idx, c in enumerate(valid_conds):
                col = c["col"]
                op = c["op"]
                val = c["value"].strip()

                # rank_field_map内的字段，OP_NUMBER全部交给函数处理
                if col in self.rank_field_map:
                    frag, pms = self._build_rank_condition(col, op, val)
                    if frag is None:
                        continue
                else:
                    col_t = self.col_type_map.get(col, "text")
                    val_end = c.get("value_end")

                    if col_t == "datetime":
                        op_dt = op
                        # 虚拟date列：拼装sqlite表达式；真实字段直接用列名
                        if col == "date":
                            expr = r"date(year || '-' || printf('%02d', month) || '-' || printf('%02d', day))"
                        else:
                            expr = col

                        # 快捷日期：近一周 /近一月等
                        if op_dt in self.OP_DATETIME_SHORTCUT:
                            start_date = self._build_datetime_shortcut(op_dt)
                            if start_date is None:
                                continue
                            if col == "date":
                                frag = f"{expr} >= ?"
                            else:
                                frag = f"date({expr}) >= ?"
                            pms = [start_date]
                        elif op_dt == "自定义区间":
                            # 校验起止都不为空
                            if not val or not val_end:
                                continue
                            if col == "date":
                                frag = f"{expr} BETWEEN ? AND ?"
                                pms = [val, val_end]
                            else:
                                frag = f"date({expr}) BETWEEN ? AND ?"
                                pms = [val, val_end]
                        else:
                            # 普通 > >= < <= = !=
                            if not val:
                                continue
                            sql_op = self.OP_SQL_MAP.get(op_dt)
                            if sql_op is None:
                                continue
                            if col == "date":
                                frag = f"{expr} {sql_op} ?"
                            else:
                                frag = f"date({expr}) {sql_op} ?"
                            pms = [val]
                        # 收集条件片段，跳过后面普通文本逻辑
                        if frag is not None:
                            if len(sub_parts) == 0:
                                sub_parts.append(frag)
                                params.extend(pms)
                            else:
                                sub_logics.append(c["logic"])
                                sub_parts.append(frag)
                                params.extend(pms)
                        continue

                    if not val:
                        continue

                    sql_op = self.OP_SQL_MAP.get(op)
                    if sql_op is None:
                        continue

                    if sql_op in ("LIKE", "NOT LIKE"):
                        ph_val = f"%{val}%"
                    else:
                        ph_val = val

                    frag = f"{col} {sql_op} ?"
                    pms = [ph_val]
                # 收集有效条件
                if len(sub_parts) == 0:
                    sub_parts.append(frag)
                    params.extend(pms)
                else:
                    sub_logics.append(c["logic"])
                    sub_parts.append(frag)
                    params.extend(pms)

            condition_sql = self._build_pubmed_where(sub_parts, sub_logics)
            # 调试，出问题打开看
            # print("sub_parts:", sub_parts)
            # print("sub_logics:", sub_logics)
            # print("condition_sql:", condition_sql)
            raw_rows = query_logs(condition=condition_sql, query_params=params,order_by="id ASC")
            self.search_logs_raw = raw_rows

            # 渲染：直接转list，不要 row["colname"]
            for item in self.search_tree.get_children():
                self.search_tree.delete(item)

            # 从toml映射取下标，不再写死数字
            m = self.db_col_to_idx
            for seq, row_tuple in enumerate(list(self.search_logs_raw), start=1):
                log_id = row_tuple[m["id"]]
                year = row_tuple[m["year"]]
                month = row_tuple[m["month"]]
                day = row_tuple[m["day"]]
                date_str = f"{year}-{month:02d}-{day:02d}"
                category = row_tuple[m["category"]]
                title = row_tuple[m["title"]]
                content = row_tuple[m["content"]]
                star = row_tuple[m["star"]]
                priority = row_tuple[m["priority"]]
                importance = row_tuple[m["importance"]]
                update_time = row_tuple[m["update_time"]] if len(row_tuple) > m["update_time"] else ""
                show_content = content.replace("\n", '\\n').replace("\r", "\\r")
                row_vals = [
                    seq,
                    log_id,
                    date_str,
                    category,
                    title,
                    show_content,
                    star,
                    priority,
                    importance,
                    update_time
                ]
                self.search_tree.insert("", "end", values=row_vals)

            self.search_status.config(text=f"共匹配 {len(self.search_logs_raw)} 条记录")

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.search_status.config(text=f"查询异常：{str(e)}")

    def update_toggle_btn_state(self):
        extra_count = len(self.condition_rows) - 1
        if extra_count >= 1:
            self.btn_toggle_extra.config(state="normal")
        else:
            self.btn_toggle_extra.config(state="disabled", text="折叠附加条件")
            self.extra_rows_hidden = False

        has_removable = False
        # 跳过idx=0首行，只看附加行
        for idx, row_dict in enumerate(self.condition_rows):
            if idx == 0:
                continue
            if not self._row_has_value(row_dict):
                has_removable = True
                break

        if has_removable:
            self.btn_remove_blank["state"] = "normal"
        else:
            self.btn_remove_blank["state"] = "disabled"

    def toggle_extra_condition_rows(self):
        extra_count = len(self.condition_rows) - 1
        if extra_count < 1:
            return

        rows_to_toggle = self.condition_rows[1:]

        if self.extra_rows_hidden:
            # 展开附加条件
            for row_dict in rows_to_toggle:
                frm = row_dict["frame"]
                frm.pack(**row_dict["pack_kw"])
            self.btn_toggle_extra.config(text="折叠附加条件")
            self.extra_rows_hidden = False
        else:
            # 折叠附加条件，仅隐藏，不销毁
            for row_dict in rows_to_toggle:
                frm = row_dict["frame"]
                frm.pack_forget()
            self.btn_toggle_extra.config(text="展开附加条件")
            self.extra_rows_hidden = True

    def on_clone_selected_log(self):
        """克隆选中日志条目"""
        selection = self.search_tree.selection()
        if not selection:
            tk.messagebox.showwarning("提示", "请先选中一条日志记录")
            return
        item_id = selection[0]
        row_data = self.search_tree.item(item_id, "values")
        raw_dict = dict(zip(self.all_cols, row_data))

        # date 使用今天，其他复制选中行
        today = datetime.now().date()

        # 先清空tab1原有表单（复用你已有的clear_single）
        self.clear_single()

        # 回填到tab1控件
        self.date_entry.set_date(today)
        self.title_var.set(raw_dict["title"])
        self.cate_var.set(raw_dict["category"])

        # treeview取出是字符串，转int
        self.prio_var.set(raw_dict["priority"])
        self.imp_var.set(raw_dict["importance"])
        self.star_val = int(raw_dict["star"])
        self.refresh_star()

        self.content_text.delete("1.0", tk.END)
        real_content = raw_dict["content"].replace("\\n", "\n")
        self.content_text.insert("1.0", real_content)

        # 切到tab1，让用户直接编辑保存
        self.notebook.select(0)

    def save_single(self):
        try:
            # 获取选中/输入的合法日期
            t_d = self.date_entry.get_date()
            y = t_d.year
            m = t_d.month
            d = t_d.day
            title = self.title_var.get().strip()
            content = self.content_text.get("1.0", tk.END).strip()
            prio = self.prio_var.get()
            imp = self.imp_var.get()
            star = self.star_val
            category = self.cate_var.get().strip()

            if not title or not content:
                messagebox.showwarning("警告", "标题和内容不能为空")
                return
            add_single_log(y, m, d, title, content, prio, imp, star, category)
            self.on_cate_input_done()
            messagebox.showinfo("成功", "保存成功")
            self.clear_single()
        except Exception as e:
            messagebox.showerror("错误", f"保存失败：{e}")

    def tab_switch_focus(self, event):
        # 切换到【逐条登记】tab 时 → 刷新分类下拉框
        if self.notebook.index(self.notebook.select()) == 0:
            self.refresh_category_combobox()
            self.title_entry.focus()
        # 切换到查询页时，自动把焦点给查询按钮
        elif self.notebook.index(self.notebook.select()) == 3:
            self.query_btn.focus()
            self.status_bar.config(text="● 就绪")
        elif self.notebook.index(self.notebook.select()) == 4:
            self.btn_search.focus()


    def refresh_category_combobox(self):
        """ 刷新分类下拉选项 """
        updated_list = self.config["category"]['options']
        self.cate_options = updated_list
        self.cate_cb.config(values=self.cate_options)

    def set_star(self, idx):
        # 点击第idx个，设为对应星级 1~5
        if self.star_val == idx + 1:
            self.star_val = 0
        else:
            self.star_val = idx + 1
        self.refresh_star()

    def refresh_star(self):
        # LightRoom 同款：前面实心，后面空心
        for i in range(5):
            if i < self.star_val:
                self.star_labels[i].config(text="★")
            else:
                self.star_labels[i].config(text="☆")

    def on_cate_selected(self, event=None):
        current = self.cate_var.get()
        if current == '自定义':
            self.cate_cb.config(state='normal')
            # 关键修复：不加 focus，日历就不会消失
        else:
            self.cate_cb.config(state='readonly')

    def on_cate_input_done(self, event=None):
        text = self.cate_var.get().strip()
        if not text:
            return

        # 只处理：不是自定义 + 不在列表里
        if text != '自定义' and text not in self.cate_options:
            # 直接调用你现有的工具方法 → 自动去重、自动写 TOML、自动返回正确列表
            updated_list = update_config_category(self.cate_options + [text])

            # 同步更新内存和界面
            self.cate_options = updated_list
            self.cate_cb.config(values=self.cate_options)

        # 只有界面失焦时才改状态，代码调用不动它
        if event is not None:
            self.cate_cb.config(state='readonly')

    def clear_single(self,flag = 'Auto'):
        self.title_var.set('')
        self.content_text.delete('1.0', tk.END)
        self.cate_var.set(self.cate_default)
        self.cate_cb.config(state='readonly')
        self.date_entry.set_date(date.today())
        if flag == 'Manual':
            self.prio_var.set('低')
            self.imp_var.set('一般')
            self.star_val = 1
            self.refresh_star()

    def do_batch(self):
        txt = self.batch_text.get("1.0", tk.END).strip()
        if not txt:
            messagebox.showwarning("警告", "内容不能为空")
            return
        count = batch_parse_and_save(txt)
        messagebox.showinfo("成功", f"批量导入完成，共 {count} 条")
        self.batch_text.delete("1.0", tk.END)

    def on_backup_db(self):
        """按钮回调：自选目录热备份数据库"""
        # 弹出选择文件夹窗口
        target_dir = filedialog.askdirectory(
            title="选择数据库备份保存目录",
            mustexist=True
        )
        # 用户点取消，返回空字符串，直接退出
        if not target_dir:
            return

        ok,bakfile_name = backup_db_safe_hot(Path(target_dir),is_prune_old=False)
        if not ok:
            messagebox.showerror("备份失败", "数据库备份执行出错")
            return
        messagebox.showinfo("备份完成", f"备份文件已保存至：\n{bakfile_name}")




    def make_daily(self):
        try:
            y = self.daily_y.get()
            m = self.daily_m.get()
            d = self.daily_d.get()
            content = gen_daily_report(y, m, d)
            export_daily_all(y, m, d)
            self.report_text.delete('1.0', tk.END)
            self.report_text.insert(tk.END, content)
            messagebox.showinfo('成功', '日报已生成并导出')
        except Exception as e:
            messagebox.showerror('错误', f'日报生成失败：{e}')

    def make_weekly(self):
        try:
            y = self.week_y.get()
            w = self.week_w.get()
            content = gen_weekly_report(y, w)
            export_weekly_all(y, w)
            self.report_text.delete('1.0', tk.END)
            self.report_text.insert(tk.END, content)
            messagebox.showinfo('成功', '周报已生成并导出')
        except Exception as e:
            messagebox.showerror('错误', f'周报生成失败：{e}')


    def do_query_log(self):
        self.edit_origin_data.clear()
        self.clear_edit_buttons()
        today = date.today()
        period = self.query_period.get()
        self.current_query_period = period

        # 全部用你现有的 query_logs
        if period == "all":
            items = query_logs(order_by='id ASC')

        elif period == "day":
            items = query_logs(
                year=today.year,
                month=today.month,
                day=today.day,
                order_by='id ASC'
            )

        elif period == "week":
            week_num = today.isocalendar()[1]
            items = query_logs(condition=f"week_num={week_num}", order_by='id ASC')

        elif period == "month":
            items = query_logs(
                year=today.year,
                month=today.month,
                order_by='id ASC'
            )

        elif period == "year":
            items = query_logs(year=today.year, order_by='id ASC')

        else:
            items = []

        self.query_logs = items

        # 清空表格
        for item in self.query_tree.get_children():
            self.query_tree.delete(item)

        # ======================
        # 【升级】插入新表格（10列：序号、日志ID、日期、分类、标题、内容、星级、优先级、重要性、更新时间）
        # ======================
        for seq, log in enumerate(items, start=1):
            log_id = log[0]
            date_str = f"{log[2]}-{log[3]:02d}-{log[4]:02d}"
            cate = log[11]
            title = log[6]
            content = log[7]
            star = log[10]  # 星级
            priority = log[8]  # 优先级
            importance = log[9]  # 重要性
            update_time = log[14] if len(log) > 14 else ""  # 更新时间

            # 内容显示优化
            show_content = content.replace("\n", '\\n').replace("\r", "\\r")
            '''if len(show_content) > 50:
                show_content = show_content[:50] + "..."
            '''

            # 插入新表格（10列）
            self.query_tree.insert("", "end", values=(
                seq,  # 序号
                log_id,  # 日志ID
                date_str,  # 日期
                cate,  # 分类
                title,  # 标题
                show_content,  # 内容
                star,  # 星级
                priority,  # 优先级
                importance,  # 重要性
                update_time  # 更新时间
            ))

        # 状态栏提示
        if items:
            self.status_bar.config(text=f"✅ 查询成功：共 {len(items)} 条日志")
        else:
            self.status_bar.config(text="ℹ 查询结果：0 条日志")


    # 打开行内编辑
    def open_inline_edit(self):
        if self.current_query_period not in self.allow_edit_period:
            self.status_bar.config(text="❌ 该查询范围不允许编辑")
            return

        selected = self.query_tree.selection()
        if not selected:
            from tkinter import messagebox
            messagebox.showwarning("提示", "请选择一行")
            return
        # 强制存入选中行原始完整数据
        for row_id in selected:
            if row_id not in self.edit_origin_data:
                self.edit_origin_data[row_id] = self.query_tree.item(row_id, 'values')
        self.show_edit_buttons()

    def show_edit_buttons(self):
        if self.edit_btn_frame:
            return
        # 变量名全程不变
        self.edit_btn_frame = ttk.Frame(self.top_frame)
        self.edit_btn_frame.pack(side="left", padx=5)

        self.update_btn = ttk.Button(self.edit_btn_frame, text="更新", command=self.do_update_all)
        self.cancel_btn = ttk.Button(self.edit_btn_frame, text="取消", command=self.do_cancel_edit)
        self.update_btn.pack(side="left", padx=3)
        self.cancel_btn.pack(side="left", padx=3)

    def clear_edit_buttons(self):
        if self.edit_btn_frame:
            self.edit_btn_frame.destroy()
            self.edit_btn_frame = None

    def tree_cell_edit(self, event):

        # 这段代码换个位置，方便克隆日志 2026年7月18日
        #if self.current_query_period not in self.allow_edit_period:
        #    self.status_bar.config(text="❌ 该查询范围不允许编辑")
        #    return

        row_id = self.query_tree.focus()
        col_id = self.query_tree.identify_column(event.x)
        if not row_id or not col_id:
            return

        # 校验是否为可编辑列
        col_idx = int(col_id.strip("#")) - 1
        col_name = self.all_cols[col_idx] if col_idx < len(self.all_cols) else ""
        if col_name not in self.allow_edit_cols:
            self.status_bar.config(text="❌ 此列禁止修改")
            return
        elif self.current_query_period not in self.allow_edit_period:
            self.status_bar.config(text='〇 数据可复制，但不可编辑')
        else:
            self.status_bar.config(text="✅ 可编辑")

        # 保存原始数据（变量名不变）
        if row_id not in self.edit_origin_data:
            self.edit_origin_data[row_id] = self.query_tree.item(row_id, 'values')

        # 创建编辑框
        x, y, w, h = self.query_tree.bbox(row_id, col_id)
        edit_entry = ttk.Entry(self.query_tree)
        edit_entry.place(x=x, y=y, width=w, height=h)
        old_val = self.query_tree.set(row_id, col_id)
        edit_entry.insert(0, old_val)
        edit_entry.focus()

        # 确认编辑
        def save_edit(e=None):
            new_val = edit_entry.get().strip()
            edit_entry.destroy()
            if row_id not in self.query_tree.get_children():
                return

            if self.current_query_period not in self.allow_edit_period:
                self.status_bar.config(text="❌ 该查询范围不允许编辑")
                return

            # 列 & 行
            col_idx = int(col_id.replace("#", "")) - 1
            col_name = self.all_cols[col_idx]

            if col_name == 'date':
                res = parse_and_fix_date(new_val)
                if not res:
                    self.status_bar.config(text="❌ 日期格式非法，仅支持 YYYY-MM-DD")
                    return
                new_val = res

            if new_val == old_val.strip():
                self.status_bar.config(text="◆ 数据未修改.")
                return

            col_cn = self.col_cn_map.get(col_name, col_name)  # 自动取中文
            row_idx = self.query_tree.index(row_id) + 1
            # 当前时间戳
            now = datetime.now().strftime("%H:%M:%S")
            # 状态栏最终显示
            self.status_bar.config(
                text=f"[{now}] 第{row_idx}行 {col_cn}：{old_val} → {new_val}"
            )

            self.query_tree.set(row_id, col_id, new_val)
            # 标记该行已修改，纳入取消还原范围
            self.show_edit_buttons()

        edit_entry.bind('<Return>', save_edit)
        edit_entry.bind('<FocusOut>', save_edit)

    def search_tree_cell_edit(self, event):
        row_id = self.search_tree.focus()
        col_id = self.search_tree.identify_column(event.x)
        if not row_id or not col_id:
            return

        col_idx = int(col_id.strip("#")) - 1
        col_name = self.all_cols[col_idx] if col_idx < len(self.all_cols) else ""
        if col_name not in self.allow_edit_cols:
            return
        self.search_status.config(text='〇 数据可复制，但不可编辑')
        x, y, w, h = self.search_tree.bbox(row_id, col_id)
        edit_entry = ttk.Entry(self.search_tree)
        edit_entry.place(x=x, y=y, width=w, height=h)

        old_val = self.search_tree.set(row_id, col_id)
        edit_entry.insert(0, old_val)
        edit_entry.focus()

        def on_finish(_=None):
            edit_entry.destroy()
            self.search_status.config(text='● 就绪')

        edit_entry.bind("<Return>", on_finish)
        #edit_entry.bind("<FocusOut>", lambda e: edit_entry.destroy())
        edit_entry.bind("<FocusOut>",on_finish)

    # 执行更新
    def do_update_all(self):
        if self.current_query_period not in self.allow_edit_period:
            self.status_bar.config(text="❌ 该查询范围不允许编辑")
            return
        if not self.edit_origin_data:
            return

        for row_id, old_vals in self.edit_origin_data.items():
            vals = list(self.query_tree.item(row_id, 'values'))
            # ============================
            # 自动锁定：不可编辑列 = 原值
            # 列名全部来自 TOML 的 all_cols
            # ============================
            for idx, col_name in enumerate(self.all_cols):
                if col_name not in self.allow_edit_cols:
                    vals[idx] = old_vals[idx]
            # 下标对应：0序号 1日志ID 2日期 3分类 4标题 5内容 6星级 7优先级 8重要性 9更新时间
            log_id = vals[1]
            date_str = vals[2]
            category = vals[3]
            title = vals[4]
            content = vals[5].replace(r'\n', '\n').replace(r'\t', '\t').replace(r'\r', '\r')
            star = vals[6]
            priority = vals[7]
            importance = vals[8]

            y, m, d = map(int, date_str.split('-'))

            update_log_by_id(
                log_id=log_id,
                year=y, month=m, day=d,
                title=title,
                content=content,
                category=category,
                star=star,
                priority=priority,
                importance=importance
            )

        self.clear_edit_buttons()
        self.edit_origin_data.clear()
        self.do_query_log()
        self.status_bar.config(text="✅ 更新成功")

    # 取消编辑
    def do_cancel_edit(self):
        # 逐行强制还原初始完整数据
        for row_id, origin_vals in self.edit_origin_data.items():
            try:
                self.query_tree.item(row_id, values=origin_vals)
            except:
                pass
        # 清理
        self.clear_edit_buttons()
        self.edit_origin_data.clear()
        self.status_bar.config(text="❌ 已取消修改，数据复原")

def run_gui():
    root = tk.Tk()
    app = LogGUI(root)
    root.mainloop()

if __name__ == "__main__":
    run_gui()