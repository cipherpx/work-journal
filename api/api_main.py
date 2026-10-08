from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from core.log_service import add_single_log, batch_parse_and_save, search_log
from core.gen_report import gen_daily_report, gen_weekly_report

app = FastAPI(title="日志管理系统API", version="1.0")

class LogItem(BaseModel):
    year: int
    month: int
    day: int
    title: str
    content: str
    priority: str = "中"
    importance: str = "一般"
    star: int = 3

@app.post("/log/add", summary="单条添加日志")
def api_add_log(item: LogItem):
    try:
        add_single_log(item.year, item.month, item.day, item.title, item.content, item.priority, item.importance, item.star)
        return {"code": 0, "msg": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/log/batch", summary="批量导入日志")
def api_batch_log(text: str):
    try:
        count = batch_parse_and_save(text)
        return {"code": 0, "msg": "success", "count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/log/daily", summary="获取日报")
def api_daily(year: int, month: int, day: int):
    try:
        content = gen_daily_report(year, month, day)
        return {"code": 0, "msg": "success", "data": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/log/weekly", summary="获取周报")
def api_weekly(year: int, week: int):
    try:
        content = gen_weekly_report(year, week)
        return {"code": 0, "msg": "success", "data": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/log/search", summary="搜索日志")
def api_search(keyword: str):
    try:
        res = search_log(keyword)
        return {"code": 0, "msg": "success", "data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.api_main:app", host="0.0.0.0", port=8000, reload=True)