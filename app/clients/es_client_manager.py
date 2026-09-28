import asyncio
from typing import Optional

from elasticsearch import AsyncElasticsearch

from app.conf.app_config import app_config, ESConfig

# Elasticsearch（简称 ES）是一个开源、分布式、RESTful 风格的搜索引擎，基于 Lucene 构建，主打全文检索、结构化检索、日志分析、数据统计。


class EsClientManager:
    """Elasticsearch异步客户端管理器：封装ES客户端的初始化、连接、关闭逻辑"""
    def __init__(self, config: ESConfig):
        """
        初始化ES客户端管理器
        :param es_config: ES配置对象，包含host（主机地址）、port（端口号）等核心连接参数
        """
        # 保存ES服务的连接配置信息
        self.client: Optional[AsyncElasticsearch] = None
        # 定义异步ES客户端对象，初始值为None（通过init方法初始化）
        self.config = config

    def _get_url(self):
        """
        拼接ES服务的连接URL
        :return: 符合ES客户端要求的http格式连接地址（如：http://127.0.0.1:9200）
        """
        return f"http://{self.config.host}:{self.config.port}"

    def init(self):
        """初始化异步Elasticsearch客户端实例（创建连接）"""
        # 创建异步ES客户端，hosts参数接收列表形式的连接地址
        self.client = AsyncElasticsearch(
            hosts=[self._get_url()]
        )

    async def close(self):
        """异步关闭ES客户端连接，释放资源（需在程序退出前调用）"""
        await self.client.close()

# 实例化ES客户端管理器，传入全局配置中的ES连接配置
es_client_manager = EsClientManager(app_config.es)

if __name__ == '__main__':
    # 初始化客户端对象
    es_client_manager.init()
    # 获取客户端
    client = es_client_manager.client

    # 定义异步函数
    async def test():

        # 查询并判断指定的索引是否存在
        if not await client.indices.exists(index="my_book"):

            # 不存在，创建索引，指定映射
            # 创建索引
            # 参考：https://www.elastic.co/guide/en/elasticsearch/reference/8.19/getting-started.html#getting-started-explicit-mapping
            await client.indices.create(
                index="my_book",
                mappings={
                    "dynamic": False,
                    "properties": {
                        "name": {
                            "type": "text",
                            "analyzer": "ik_max_word",
                            "search_analyzer": "ik_smart"
                        },
                        "author": {
                            "type": "text"
                        },
                        "release_date": {
                            "type": "date",
                            "format": "yyyy-MM-dd"
                        },
                        "page_count": {
                            "type": "integer"
                        }
                    }
                },
            )

        # 插入数据
        # 参考：https://www.elastic.co/guide/en/elasticsearch/reference/8.19/getting-started.html#getting-started-add-multiple-documents

        # 批量添加数据
        # await client.bulk(
        #     operations=[
        #         {
        #             "index": {
        #                 "_index": "my_book"
        #             }
        #         },
        #         {
        #             "name": "Revelation Space",
        #             "author": "Alastair Reynolds",
        #             "release_date": "2000-03-15",
        #             "page_count": 585
        #         },
        #         {
        #             "index": {
        #                 "_index": "my_book"
        #             }
        #         },
        #         {
        #             "name": "1984",
        #             "author": "George Orwell",
        #             "release_date": "1985-06-01",
        #             "page_count": 328
        #         },
        #         {
        #             "index": {
        #                 "_index": "my_book"
        #             }
        #         },
        #         {
        #             "name": "Fahrenheit 451",
        #             "author": "Ray Bradbury",
        #             "release_date": "1953-10-15",
        #             "page_count": 227
        #         },
        #         {
        #             "index": {
        #                 "_index": "my_book"
        #             }
        #         },
        #         {
        #             "name": "Brave New World",
        #             "author": "Aldous Huxley",
        #             "release_date": "1932-06-01",
        #             "page_count": 268
        #         },
        #         {
        #             "index": {
        #                 "_index": "my_book"
        #             }
        #         },
        #         {
        #             "name": "The Handmaids Tale",
        #             "author": "Margaret Atwood",
        #             "release_date": "1985-06-01",
        #             "page_count": 311
        #         }
        #     ],
        # )

        # 搜索
        # 参考：https://www.elastic.co/guide/en/elasticsearch/reference/8.19/getting-started.html#getting-started-match-query

        # 检索数据
        resp = await client.search(
            index="my_book",
            query={
                "match": {
                    "name": "Space"
                }
            },
        )
        print(type(resp))
        print(resp['hits']['hits'][0]["_source"]['name'])





        await es_client_manager.close()



    asyncio.run(test())



