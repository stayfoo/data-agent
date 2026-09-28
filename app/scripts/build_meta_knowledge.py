import asyncio
from pathlib import Path

import sys
# sys.path 是 Python 内置模块 sys 中的一个列表（list），
# 里面存储的是 Python 解释器在导入模块时，会依次搜索的目录路径。
# 简单来说：当你执行 import app 时，Python 会遍历 sys.path 里的每一个路径，检查该路径下是否有 app 模块（文件夹 /.py 文件），找到则导入，找不到就报 ModuleNotFoundError。
print(sys.path)


import argparse

from app.clients.embedding_client_manager import embedding_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.repositories.es.value_es_repository import ValueEsRepository
from app.repositories.mysql.dw_mysql_repository import DwMysqlRepository
from app.repositories.mysql.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.services.meta_knowledge_service import MetaKnowledgeService


# 知识库构建脚本入口
# 主要负责解析调用者传入的配置文件路径。具体内容如下：
# 脚本文件执行，配置文件的加载方式：动态传递配置文件位置，解析获取文件路径
# python -m app.scripts.build_meta_knowledge -c .\conf\meta_config.yaml

"""
主要实现思路:
    # 1.加载配置文件

    # 2.处理表信息
    # 2.1 保存表信息到meta数据库
    # 2.2 为字段信息建立向量索引
    # 2.3 为字段取值建立全文索引

    # 3.处理指标信息
    # 3.1 保存指标信息到meta数据库
    # 3.2 为指标信息建立向量索引
"""

async def build(config:Path):
    """
        构建元知识库函数
        用于执行构建元知识相关的业务逻辑，例如加载配置、初始化数据等
        """
    # 打印INFO级别的日志，记录当前正在执行的操作

    # 初始化meta客户端
    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()
    qdrant_client_manager.init()
    embedding_manager.init()
    es_client_manager.init()


    # 获取session
    async with meta_mysql_client_manager.session_factory() as meta_session,dw_mysql_client_manager.session_factory() as dw_session:
        # 创建repository对象
        meta_mysql_repository = MetaMysqlRepository(meta_session)
        dw_mysql_repository = DwMysqlRepository(dw_session)
        column_qdrant_repository=ColumnQdrantRepository(qdrant_client_manager.client)
        value_es_repository=ValueEsRepository(es_client_manager.client)
        metric_qdrant_repository=MetricQdrantRepository(qdrant_client_manager.client)
        # 创建service对象
        meta_knowledge_service = MetaKnowledgeService(
            meta_mysql_repository=meta_mysql_repository,
            dw_mysql_repository=dw_mysql_repository,
            column_qdrant_repository=column_qdrant_repository,
            embedding_client=embedding_manager.client,
            value_es_repository=value_es_repository,
            metric_qdrant_repository=metric_qdrant_repository
        )
        # 调用build函数
        await meta_knowledge_service.build(config)

    # 释放资源
    await meta_mysql_client_manager.close()
    await dw_mysql_client_manager.close()
    await qdrant_client_manager.close()
    await es_client_manager.close()
    await embedding_manager.close()


# 判断当前脚本是否作为主程序运行

if __name__ == '__main__':
    # 1.构建命令行解析对象
    parser = argparse.ArgumentParser()

    # 2.配置参数
    parser.add_argument('-c', '--conf')

    # 3.获取参数
    args = parser.parse_args()
    # 4.转换为Path
    config_path:Path= Path(args.conf)

    # 调用build函数，执行元知识构建逻辑
    asyncio.run(build(config_path))


"""
命令终端：python ./app/scripts/build_meta_knowledge.py


用于构建元数据知识库的脚本。
输入: YAML 配置文件, 配置文件中定义了需要同步至元数据知识库的表格信息与指标信息。

脚本功能包括：
根据配置内容，将指定的表及指标信息同步至 Meta 数据库；
为字段信息和指标信息构建向量索引；
为字段取值建立全文索引。

知识库构建：
问题：脚本构建与web服务构建的优势有哪些？

Python 脚本构建知识库的核心优势
1. 速度极快，适合大批量文档导入
    脚本可以多线程、多进程、异步并发处理
    直接读写向量库（ES/Chroma/PGVector/Milvus）
    不需要走 HTTP 网络请求
    百万级文档导入，脚本比 Web 快 5～50 倍
    Web 方式：
    必须走接口请求
    有网络开销、限流、超时问题
    不适合大批量
2. 稳定性高，不会因为服务崩溃中断
    脚本是一次性任务，跑失败了可以断点续跑
    不依赖服务启动、不依赖端口、不依赖网络
    可以随时重试、跳过错误文件
    Web 方式：
    服务挂了 → 全部中断
    并发高 → 服务 OOM → 全量失败
    无法轻松断点续传
3. 资源占用可控，不影响线上服务
    构建知识库非常耗 CPU/GPU/ 内存（分词、向量化）
    脚本可以在离线机器跑
    完全不影响线上智能体服务的稳定性
    Web 方式：
    构建压力 = 线上服务压力
    容易把服务拖垮
    生产环境严禁这么干

"""

"""
构建元数据知识库模块的核心代码采用分层设计，具体组织结构如下：

data-agent/
├── conf/
│   └── meta_config.yaml # 配置文件，用于指定待同步的表格和指标
└── app/
    ├── conf/
    │   └── meta_config.py # 用于定义meta_config.yaml的参数结构
    ├── scripts/
    │   └── build_meta_knowledge.py # 构建元数据知识库的入口脚本，负责解析命令行参数
    ├── services/
    │   └── meta_knowledge_service.py # 负责实现构建元数据知识库的核心逻辑
    ├── models/
    │   ├── table_info.py # 用于定义表格信息的业务实体类
    │   ├── column_info.py # 用于定义字段信息的业务实体类
    │   ├── metric_info.py # 用于定义指标信息的业务实体类
    │   ├── column_metric.py # 用于定义字段指标关系的业务实体类
    │   └── value_info.py # 用于定义字段取值的业务实体类
    └── repositories/
        ├── mysql/
        │   ├── meta/
        │   │   ├── meta_mysql_repository.py # 负责实现meta数据库的读写操作
        │   │   └── mappers/
        │   │       ├── table_info_mapper.py # table_info orm实体和业务实体的类型转换
        │   │       ├── column_info_mapper.py # column_info orm实体和业务实体的类型转换
        │   │       ├── metric_info_mapper.py # metric_info orm实体和业务实体的类型转换
        │   │       └── column_metric_mapper.py # column_metric orm实体和业务实体的类型转换
        │   ├── dw/
        │   │   └── dw_mysql_repository.py # 负责实现dw数据库的读写操作
        ├── qdrant/
        │   ├── column_qdrant_repository.py # 负责实现qdrant中column相关集合的读写操作
        │   └── metric_qdrant_repository.py # 负责实现qdrant中metric相关集合的读写操作
        └── es/
            └── value_qdrant_repository.py # 用于定义es中value索引的实体类

"""
