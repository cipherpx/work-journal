# work-journal  
一个轻量工作日志管理工具，支持命令行、图形界面。
支持日志录入、按日/周查询、自动生成日报周报，可导出Word/Excel/PDF报告。  
> ⚠️ **Beta 测试版提示**
> 本项目目前处于测试阶段，部分功能尚未完善，可能存在Bug。
> 建议做好数据备份，谨慎用于正式业务场景。  
## 项目目录  
work-journal/  
├── api/  
│   └── api_main.py  
├── cli/  
│   └── cli_main.py  
├── core/  
│   ├── backup_core.py  
│   ├── db_core.py  
│   ├── export_core.py  
│   ├── gen_report.py  
│   ├── log_service.py  
│   ├── path_util.py  
│   └── utils.py    
├── gui/  
│   └── gui_main.py  
├── template/  
│   ├── daily.tpl  
│   ├── weekly.tpl  
├── CHANGELOG.md  
├── LICENSE  
├── README.md  
├── config.toml.example  
├── diy_func.py  
├── requirements.txt  
├── run_cli.py  
└── run_gui.py  
## License Notice
This software is available **for non-commercial research use only**, and use is restricted to individuals and non-profit academic institutions.
- Any use by commercial entities or legal persons is prohibited, even for internal research purposes.
- Integration or embedding of this tool into any commercial product or commercial workflow is prohibited.
- Distributed derivative works must adopt this identical license (share-alike).
- Commercial use requires prior written permission from cipherpx.

