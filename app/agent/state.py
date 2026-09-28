from typing import TypedDict

from app.models.es.value_info_es import ValueInfoEs
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant

# state 用于定义智能体状态

# 列信息封装实体
class ColumnInfoState(TypedDict):
    name: str
    type: str
    role: str
    examples: list
    description: str
    alias: list[str]

# 表信息封装实体
class TableInfoState(TypedDict):
    name: str
    role: str
    description: str
    columns: list[ColumnInfoState]


# 指标信息封装实体
class MetricInfoState(TypedDict):
    name: str
    description: str
    relevant_columns: list[str]
    alias: list[str]


class DateInfoState(TypedDict):
    date: str
    weekday: str
    quarter: str


class DBInfoState(TypedDict):
    version: str
    dialect: str

class DataAgentState(TypedDict):
    error: str # 错误信息，根据 state 中是否存在错误信息，可以进行流程执行
    query: str # 用户的查询
    keywords:list[str] # 提取关键字列表
    recall_columns:list[ColumnInfoQdrant]  # 召回列信息列表
    recall_metric:list[MetricInfoQdrant]  # 召回指标信息列表
    recall_values:list[ValueInfoEs]   # 召回值信息列表
    table_infos:list[TableInfoState]  # 封装表信息列表
    metric_infos:list[MetricInfoState]  # 封装指标信息列表
    date_info: DateInfoState  # 时间信息
    db_info: DBInfoState     # 数据库环境信息
    sql:str



