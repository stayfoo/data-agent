from dataclasses import dataclass
from pathlib import Path

from omegaconf import OmegaConf


# 日志配置
@dataclass
class File:
    enable: bool
    level: str
    path: str
    rotation: str
    retention: str


@dataclass
class Console:
    enable: bool
    level: str


@dataclass
class LoggingConfig:
    file: File
    console: Console


# 数据库配置
@dataclass
class DBConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


@dataclass
class QdrantConfig:
    host: str
    port: int
    embedding_size: int


@dataclass
class EmbeddingConfig:
    host: str
    port: int
    model: str


@dataclass
class ESConfig:
    host: str
    port: int
    index_name: str


@dataclass
class LLMConfig:
    model_name: str
    api_key: str


# 定义封装实体
@dataclass
class AppConfig:
    logging: LoggingConfig
    db_meta: DBConfig
    db_dw: DBConfig
    qdrant: QdrantConfig
    embedding: EmbeddingConfig
    es: ESConfig
    llm: LLMConfig

# 定义配置路径
config_file = Path(__file__).parents[2] / 'conf' / 'app_config.yaml'
# 读取配置数据
context = OmegaConf.load(config_file)
# 获取配置内容
# print(context['name'])

# 创建封装结构
schema = OmegaConf.structured(AppConfig)
# 封装配置内容到配置对象中
app_config: AppConfig = OmegaConf.to_object(OmegaConf.merge(schema, context))

# 获取配置数据
# print(app_config.name)