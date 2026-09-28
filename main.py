# 导入FastAPI核心类
import uuid

from fastapi import FastAPI,Request

from app.api.routers.query_router import query_router
from app.core.context import request_id_ctx_var
from app.core.lifespan import lifespan

# 在终端的 main.py 所在的目录直接执行命令: fastapi dev , 启动测试服务器。


# 创建FastAPI应用实例
app = FastAPI(lifespan=lifespan)

# 注册路由 - 绑定查询 router
app.include_router(query_router)

# 整合中间件->设置异步协程上下文变量.  装饰器下面的函数会被调用。
@app.middleware("http")
async def add_request_cxt_var(request: Request, call_next):
    # 设置异步协程上下文变量
    request_id_ctx_var.set(uuid.uuid4())
    # FastAPI 返回值 会自动转换为 JSON
    return await call_next(request)
