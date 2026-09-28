from pydantic import BaseModel

# 请求参数和返回值结果

# 负责定义查询接口请求体结构
class QuerySchema(BaseModel):
    # 接收用户输入的查询字符串，会自动校验字段类型和非空
    query: str
