from dataclasses import dataclass
from typing import Optional


@dataclass
class ColumnConfig:
    name: str # 真实字段名
    role: str # 字段角色
    description: str # 字段的业务含义
    alias: list[str] # 字段同义词
    sync: bool # 该字段取值是否需要同步到ES建立全文索引


@dataclass
class TableConfig:
    name: str # 真实表名
    role: str # 表角色
    description: str # 表的业务含义说明
    columns: list[ColumnConfig]


@dataclass
class MetricConfig:
    name: str # 指标名称，如 GMV、AOV
    description: str  # 指标的业务含义与计算口径说明
    relevant_columns: list[str] # 指标相关字段
    alias: list[str] # 指标同义词


@dataclass
class MetaConfig:
    tables: Optional[list[TableConfig]] = None # 表格信息
    metrics: Optional[list[MetricConfig]] = None # 指标信息
