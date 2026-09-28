import anyio
from fastapi import APIRouter
from fastapi.params import Depends
from starlette.responses import StreamingResponse

from app.api.dependencies import get_query_service
from app.api.schemas.query_schema import QuerySchema
from app.services.query_service import QueryService

# 负责定义查询接口

# 声明查询的路由
query_router = APIRouter()


# # 视频流模拟函数--生成器函数
# async def fake_video_streamer():
#     for i in range(10):
#         yield f"data: stage:{i} \n\n"
#         await anyio.sleep(1)
#
#
# @query_router.get("/")
# async def main():
#     return StreamingResponse(fake_video_streamer(),media_type="text/event-stream")
#

@query_router.post("/api/query")
async def query(query: QuerySchema, service: QueryService=Depends(get_query_service)):
    # query: QuerySchema：请求体模型。FastAPI 会自动把客户端发来的 JSON 解析成 QuerySchema 实例。
    # service: QueryService = Depends(get_query_service)：依赖注入。
    # FastAPI 会调用 get_query_service()，拿到一个 QueryService 实例并传入。
    # 这样业务逻辑（查询、检索、调用模型等）都封装在 QueryService 里，路由函数只负责接收请求和返回响应。
    return StreamingResponse(service.query(query.query), media_type="text/event-stream")