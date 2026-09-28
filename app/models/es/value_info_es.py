from typing import TypedDict


# 业务实体类: 用于统一封装不同存储系统中的数据结构, 如 Meta 数据库、Elasticsearch、Qdrant,
# 作为应用上层组件进行读写操作时的标准参数类型和返回值类型。
# 本项目定义的业务实体有：ValueInfoEs、ColumnInfoQdrant、MetricInfoQdrant
class ValueInfoEs(TypedDict):
    id:str
    value:str
    type:str
    column_id:str
    column_name:str
    table_id:str
    table_name:str