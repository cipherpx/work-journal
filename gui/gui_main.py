import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from core.log_service import add_single_log, batch_parse_and_save, query_logs, advanced_log_query
from core.gen_report import gen_daily_report, gen_weekly_report, save_weekly_report_to_docx
from core.export_core import export_daily_all, export_weekly_all
from core.path_util import get_week_num
from tkcalendar import DateEntry
from datetime import date,datetime
from diy_func import update_config_category, load_config_toml, parse_and_fix_date, show_save_success
from core.log_service import update_log_by_id


class LogGUI:
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

        # 增加右键快捷菜单
        self.right_menu = tk.Menu(self.root, tearoff=0)
        self.right_menu.add_command(label='另存周报', command=self.save_weekly_report)

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
        self.notebook.add(self.tab1, text="逐条登记")
        self.notebook.add(self.tab2, text="批量导入")
        self.notebook.add(self.tab3, text="日报/周报")
        self.notebook.add(self.tab4, text="日志查询")
        self.notebook.add(self.tab5, text="高级日志搜索")
        self.notebook.pack(expand=True, fill='both')
        self.notebook.bind("<<NotebookTabChanged>>", self.tab_switch_focus)

        # -------- 逐条登记 --------
        # 日历选择框 + 分类 同行
        # 日期 日历选择框（稳定不消失）
        ttk.Label(self.tab1, text='日期：').grid(row=0, column=0, padx=5, pady=5, sticky='w')

        self.date_entry = DateEntry(
            self.tab1,
            width=12,
            date_pattern='yyyy-mm-dd',
            locale='zh_CN'
        )
        self.date_entry.grid(row=0, column=1, padx=3, pady=5, sticky='w')

        # 分类
        ttk.Label(self.tab1, text='分类：').grid(row=0, column=2, padx=(15, 5), pady=5, sticky='w')
        self.cate_var = tk.StringVar(value=self.cate_default)
        self.cate_cb = ttk.Combobox(
            self.tab1,
            textvariable=self.cate_var,
            values=self.cate_options,
            state='readonly'
        )
        self.cate_cb.grid(row=0, column=3, padx=5, pady=5, sticky='ew')
        self.cate_cb.bind('<<ComboboxSelected>>', self.on_cate_selected)

        # 紧急度
        ttk.Label(self.tab1, text="紧急度：").grid(row=1, column=0, padx=5, pady=5, sticky="w")
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
        lab_star.grid(row=1, column=4, padx=5, pady=5, sticky="ew")

        # 星星放进Frame，不溢出
        star_frame = ttk.Frame(self.tab1)
        star_frame.grid(row=1, column=5, padx=2, pady=5)

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
        ttk.Label(self.tab2, text="粘贴多行数据（每行一条，格式：YYYY-MM-DD | 内容 | 紧急度 | 重要度 | 星级）：").pack(pady=5)
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
        # ====================== 高级日志搜索 ======================
        self.create_advanced_search_tab()

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

    def create_query_tab_old(self):

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

        # ========== 结果列表 ==========
        # 替换成表格（Treeview）
        self.query_tree = ttk.Treeview(self.tab4, columns=("id", "date", "category", "title", "content"),show="headings")
        style = ttk.Style()
        style.configure("Treeview.Heading", anchor="center")  # 表头居中
        style.configure("Treeview", rowheight=25, anchor="center")  # 内容居中

        self.query_tree.heading("id", text="ID")
        self.query_tree.heading("date", text="日期")
        self.query_tree.heading("category", text="分类")
        self.query_tree.heading("title", text="标题")
        self.query_tree.heading("content", text="内容")

        self.query_tree.column("id", width=50, anchor="center")
        self.query_tree.column("date", width=100, anchor="center")
        self.query_tree.column("category", width=80, anchor="center")
        self.query_tree.column("title", width=150, anchor="center")
        self.query_tree.column("content", width=400, anchor="center")

        self.query_tree.bind('<Double-1>', self.tree_cell_edit)

        self.query_tree.pack(fill="both", expand=True, padx=10, pady=10)

        # 状态栏
        self.status_bar = ttk.Label(self.tab4, text="● 就绪", anchor="w")
        self.status_bar.pack(side='bottom', fill='x', padx=5, pady=2)
        # 存储查询结果
        self.query_logs = []

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

        # ========== 结果列表 ==========
        # 【升级：新增序号列 + 星级/紧急度/重要性/更新时间 + 日志ID】
        self.query_tree = ttk.Treeview(None, columns=(
            "seq",  # 序号（新）
            "id",  # 日志ID
            "date",  # 日期
            "category",  # 分类
            "title",  # 标题
            "content",  # 内容
            "star",  # 星级（新）
            "urgency",  # 紧急度（新）
            "importance",  # 重要性（新）
            "update_time"  # 更新时间（新）
        ), show="headings")

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
        self.query_tree.heading("urgency", text="紧急度")
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
        self.query_tree.column("urgency", width=70, anchor="center", stretch=False)
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
        self.status_bar = ttk.Label(self.tab4, text="就绪", anchor="w")
        self.status_bar.pack(side='bottom', fill='x', padx=5, pady=2)

        # 存储查询结果
        self.query_logs = []


    def create_advanced_search_tab(self):
        # 顶部搜索条件区域
        search_top = ttk.Frame(self.tab5)
        search_top.pack(fill='x', padx=10, pady=5)

        # 1. 字段多选区
        field_frame = ttk.LabelFrame(search_top, text="选择查询字段")
        field_frame.grid(row=0, column=0, sticky="nw", padx=5)
        self.search_field_vars = {}
        for idx, field in enumerate(self.config["search"]["enable_fields"]):
            cn_name = self.col_cn_map.get(field, field)
            var = tk.BooleanVar()
            cb = ttk.Checkbutton(field_frame, text=cn_name, variable=var)
            cb.grid(row=idx // 4, column=idx % 4, sticky="w", padx=3)
            self.search_field_vars[field] = var

        # 2. 日期筛选区
        date_frame = ttk.LabelFrame(search_top, text="日期筛选")
        date_frame.grid(row=0, column=1, sticky="nw", padx=5)
        self.date_mode_var = tk.StringVar(value="single")
        ttk.Radiobutton(date_frame, text="单日", variable=self.date_mode_var, value="single",
                        command=self.switch_search_date_mode).grid(row=0, column=0)
        ttk.Radiobutton(date_frame, text="时间段", variable=self.date_mode_var, value="range",
                        command=self.switch_search_date_mode).grid(row=0, column=1)

        self.search_start_date = ttk.Entry(date_frame, width=12)
        self.search_start_date.grid(row=1, column=0, padx=2, pady=3)
        self.search_end_date = ttk.Entry(date_frame, width=12, state=tk.DISABLED)
        self.search_end_date.grid(row=1, column=1, padx=2, pady=3)

        # 3. 关键词+匹配模式
        kw_frame = ttk.LabelFrame(search_top, text="文本检索")
        kw_frame.grid(row=0, column=2, sticky="nw", padx=5)
        self.search_keyword = ttk.Entry(kw_frame, width=20)
        self.search_keyword.grid(row=0, column=0, pady=3)
        self.match_type_var = tk.StringVar(value="模糊匹配")
        match_cbx = ttk.Combobox(kw_frame, textvariable=self.match_type_var,
                                 values=self.config["search"]["match_type_list"], state="readonly", width=12)
        match_cbx.grid(row=0, column=1, padx=3)

        # 功能按钮区
        btn_frame = ttk.Frame(self.tab5)
        btn_frame.pack(fill='x', padx=10, pady=3)
        ttk.Button(btn_frame, text="开始搜索", command=self.do_advanced_search).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="清空条件", command=self.clear_search_cond).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="克隆选中日志", command=self.clone_search_log).pack(side='left', padx=5)

        # 搜索结果表格（只读）
        self.search_tree = ttk.Treeview(self.tab5, columns=self.all_cols, show="headings")
        for col in self.all_cols:
            self.search_tree.heading(col, text=self.col_cn_map[col])
            self.search_tree.column(col, width=100)

        # 禁用编辑
        self.search_tree.unbind("<Double-1>")
        self.search_tree.bind("<Double-1>", lambda e: None)

        # 滚动条
        search_scroll = ttk.Scrollbar(self.tab5, orient='vertical', command=self.search_tree.yview)
        self.search_tree.configure(yscrollcommand=search_scroll.set)
        self.search_tree.pack(fill='both', expand=True, padx=10, pady=5)
        search_scroll.pack(side='right', fill='y')

        # 状态栏
        self.search_status = ttk.Label(self.tab5, text="就绪")
        self.search_status.pack(side='bottom', fill='x', padx=10)

    def switch_search_date_mode(self):
        if self.date_mode_var.get() == "single":
            self.search_end_date.config(state=tk.DISABLED)
        else:
            self.search_end_date.config(state=tk.NORMAL)

    def clear_search_cond(self):
        for var in self.search_field_vars.values():
            var.set(False)
        self.search_keyword.delete(0, tk.END)
        self.search_start_date.delete(0, tk.END)
        self.search_end_date.delete(0, tk.END)
        self.match_type_var.set("模糊匹配")
        self.search_tree.delete(*self.search_tree.get_children())
        self.search_status.config(text="条件已清空")

    def get_search_condition(self):
        cond = {}
        select_fields = [k for k, v in self.search_field_vars.items() if v.get()]
        if not select_fields:
            self.search_status.config(text="请至少勾选一个查询字段")
            return None
        cond["query_fields"] = select_fields

        if "date" in select_fields:
            s_date = self.search_start_date.get().strip()
            if not s_date:
                self.search_status.config(text="请填写日期")
                return None
            fix_s = parse_and_fix_date(s_date)
            if not fix_s:
                self.search_status.config(text="起始日期格式错误")
                return None
            if self.date_mode_var.get() == "single":
                cond["date_eq"] = fix_s
            else:
                e_date = self.search_end_date.get().strip()
                fix_e = parse_and_fix_date(e_date)
                if not fix_e:
                    self.search_status.config(text="结束日期格式错误")
                    return None
                cond["date_range"] = (fix_s, fix_e)

        keyword = self.search_keyword.get().strip()
        text_cols = ["title", "content"]
        use_text_cols = [f for f in select_fields if f in text_cols]
        if keyword and use_text_cols:
            cond["text_cols"] = use_text_cols
            cond["keyword"] = keyword
            cond["match_type"] = self.match_type_var.get()
        return cond

    def do_advanced_search(self):
        cond = self.get_search_condition()
        if not cond:
            return
        res_data = advanced_log_query(cond)
        self.search_tree.delete(*self.search_tree.get_children())
        for row in res_data:
            self.search_tree.insert("", 'end', values=row)
        self.search_status.config(text=f"查询完成，共 {len(res_data)} 条结果")

    def clone_search_log(self):
        """克隆选中日志到逐条录入页，不复制ID"""
        select_item = self.search_tree.focus()
        if not select_item:
            self.search_status.config(text="请先选中一条日志")
            return
        row_vals = self.search_tree.item(select_item, "values")
        data_dict = dict(zip(self.all_cols, row_vals))

        self.notebook.select(self.tab1)

        # 回填表单
        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, data_dict["date"])
        self.cate_cb.set(data_dict["category"])
        self.title_entry.delete(0, tk.END)
        self.title_entry.insert(0, data_dict["title"])

        # 还原换行符
        content = data_dict["content"].replace(r"\n", "\n")
        self.content_text.delete("1.0", tk.END)
        self.content_text.insert("1.0", content)

        self.set_star(data_dict["star"])
        self.prio_var.set(data_dict["urgency"])
        self.imp_var.set(data_dict["importance"])

        self.search_status.config(text="✅ 克隆成功，修改后可保存为新日志")

    def bind_tree_full_tip(self, tree):
        tip_win = None
        tip_label = None

        def show_tip(event):
            nonlocal tip_win, tip_label
            row = tree.identify_row(event.y)
            col = tree.identify_column(event.x)
            if not row or not col:
                if tip_win:
                    tip_win.destroy()
                    tip_win = None
                return
            idx = int(col.strip('#')) - 1
            all_val = tree.item(row, "values")
            if idx >= len(all_val):
                return
            full_txt = str(all_val[idx])
            if not full_txt.strip():
                if tip_win:
                    tip_win.destroy()
                    tip_win = None
                return
            if not tip_win:
                tip_win = tk.Toplevel(tree)
                tip_win.wm_overrideredirect(True)
                tip_label = tk.Label(tip_win, bg="white", relief="solid", wraplength=700, justify="left",
                                     font=("微软雅黑", 9))
                tip_label.pack(padx=6, pady=4)
            tip_label.config(text=full_txt)
            tip_win.geometry(f"+{event.x_root + 15}+{event.y_root + 15}")
            tip_win.deiconify()

        def hide_tip(event):
            nonlocal tip_win
            if tip_win:
                tip_win.destroy()
                tip_win = None

        tree.bind("<Motion>", show_tip)
        tree.bind("<Leave>", hide_tip)

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
        if self.notebook.index(self.notebook.select()) == 3:
            self.query_btn.focus()
            self.status_bar.config(text="● 就绪")


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

    # ------------------------------
    # 查询日志：所有/当日/当周/当月/当年
    # ------------------------------
    def do_query_log_old(self):
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
                day=today.day,order_by='id ASC'
            )

        elif period == "week":
            week_num = today.isocalendar()[1]
            items = query_logs(condition=f"week_num={week_num}",order_by='id ASC')

        elif period == "month":
            items = query_logs(
                year=today.year,
                month=today.month,order_by='id ASC'
            )

        elif period == "year":
            items = query_logs(year=today.year,order_by='id ASC')

        else:
            items = []

        self.query_logs = items

        # 清空表格
        for item in self.query_tree.get_children():
            self.query_tree.delete(item)

        # 插入表格
        for log in items:
            log_id = log[0]
            date_str = f"{log[2]}-{log[3]:02d}-{log[4]:02d}"
            cate = log[11]
            title = log[6]
            content = log[7][:50] + "..." if len(log[7]) > 50 else log[7]
            show_content = content.replace("\n", " ").replace("\r", "")
            self.query_tree.insert("", "end", values=(log_id, date_str, cate, title, show_content))

        # 状态栏提示
        if items:
            self.status_bar.config(text=f"✅ 查询成功：共 {len(items)} 条日志")
        else:
            self.status_bar.config(text="ℹ 查询结果：0 条日志")

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
        # 【升级】插入新表格（10列：序号、日志ID、日期、分类、标题、内容、星级、紧急度、重要性、更新时间）
        # ======================
        for seq, log in enumerate(items, start=1):
            log_id = log[0]
            date_str = f"{log[2]}-{log[3]:02d}-{log[4]:02d}"
            cate = log[11]
            title = log[6]
            content = log[7]
            star = log[10]  # 星级
            urgency = log[8]  # 紧急度
            importance = log[9]  # 重要性
            update_time = log[14] if len(log) > 12 else ""  # 更新时间

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
                urgency,  # 紧急度
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
            # 下标对应：0序号 1日志ID 2日期 3分类 4标题 5内容 6星级 7紧急度 8重要性 9更新时间
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