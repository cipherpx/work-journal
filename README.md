# work-journal  
仓库地址：https://github.com/cipherpx/work-journal  
本地轻量日志管理工具，基于 Python + Tkinter + SQLite，支持命令行、图形界面。  
> 本项目为本地优先（Local-First）应用，所有日志数据保存在本地SQLite数据库，不会上传网络。    
⚠️ **提示**  
> 本项目处于测试阶段，建议做好数据备份，谨慎用于正式业务场景。  
```
```text
 _______________________________________
/                                       \
|   W O R K   -   J O U R N A L         |
|                                       |
|   daily logs · reports · exports      |
|                                       |
\_______________________________________/
        ,,__         ^~~~^
      c''   )?     (vv)____
        '''' \___(___) \\  )\/\
                   ||---- |
                   ||    ||
```
## ✨ 核心功能   
- 日志录入：标题、内容、日期、优先级、重要性、星级、分类标签  
- 日志克隆：快速复制已有日志生成新记录，默认日期为今日，标题不自动追加后缀  
- 日志搜索：  
  - 字段区分处理日期 / 文本 / 数字类型  
  - 日期快捷条件：近一周、近一月、近三月、半年、近一年（按月推移，处理月末边界）  
- 数据导出、日报/周报生成  
- 数据库备份：自动备份和手动热备份  
## 🛠️ 技术栈  
- Python：**3.8+**，理论可用但未做全覆盖测试   
- GUI：tkinter + ttk  
- 数据库：SQLite3  
## 📋 使用说明  
1. 克隆仓库，安装依赖  
2. 运行图形化主程序 `run_gui.py`  
3. 所有数据存储在本地 sqlite 数据库，无需额外服务  
## ⚠️ 注意事项  
- 本工具完全本地运行，**不会联网上传你的日志内容**  
- 建议定期使用手动备份功能保存日志   
- 项目仅供个人学习交流使用，请遵照法律法规合理使用，使用者自行承担使用产生的相关责任。 
## 项目目录  
work-journal/  
|-- api/  
|   |-- api_main.py  
|-- cli/  
|   |-- cli_main.py  
|-- config/  
|   |-- config.example.toml  
|-- core/  
|   |-- backup_core.py  
|   |-- cfg_manager.py  
|   |-- constants.py  
|   |-- db_core.py  
|   |-- export_core.py  
|   |-- gen_report.py  
|   |-- log_service.py  
|   |-- utils.py  
|-- gui/  
|   |-- gui_main.py  
|-- template/  
|   |-- daily.tpl  
|   |-- weekly.tpl  
|-- CHANGELOG.md  
|-- LICENSE  
|-- README.md  
|-- requirements.txt  
|-- run_cli.py  
|-- run_gui.py  
## License Notice  
This software is available **for non-commercial research use only**, and use is restricted to individuals and non-profit academic institutions.  
- Any use by commercial entities or legal persons is prohibited, even for internal research purposes.  
- Integration or embedding of this tool into any commercial product or commercial workflow is prohibited.  
- Distributed derivative works must adopt this identical license (share-alike).  
- Commercial use requires prior written permission from cipherpx.  

