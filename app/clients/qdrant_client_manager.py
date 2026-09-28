import asyncio
import random
from typing import Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import Distance, models

from app.conf.app_config import app_config, QdrantConfig

"""
Qdrant 是一款开源、高性能、云原生的向量数据库，专门用于高维向量存储 + 相似度检索，是现在 AI 应用（RAG、推荐、搜索）的标配存储组件。

Qdrant 的作用（核心用途）:
1、存储向量。保存大模型 /embedding 模型生成的高维向量。
2、快速相似度检索。 给定一个向量，快速找出最相似的 Top-K 向量。
3、支持过滤检索。向量检索 + 元数据（Payload）条件过滤同时使用。
4、支撑 AI 应用。
    RAG 知识库检索；
    语义搜索、智能问答；
    图片 / 音视频多模态检索；
    推荐系统、用户匹配、去重；
"""

class QdrantClientManager():
    """Qdrant向量数据库异步客户端管理器：封装客户端的初始化、关闭逻辑"""
    def __init__(self, config: QdrantConfig):
        """
        初始化Qdrant客户端管理器
        :param config: Qdrant 配置对象，包含host/port等连接信息
        """
        self.client: Optional[AsyncQdrantClient] = None # 定义异步Qdrant客户端对象，初始为None（init方法中初始化）
        self.config = config # 保存Qdrant连接配置

    def _get_url(self):
        """
        拼接Qdrant服务的连接URL
        :return: 符合Qdrant客户端要求的http连接地址
        """
        return f"http://{self.config.host}:{self.config.port}"

    def init(self):
        """初始化异步Qdrant客户端（创建客户端实例）"""
        self.client = AsyncQdrantClient(url=self._get_url())

    async def close(self):
        """异步关闭 Qdrant 客户端，释放连接资源"""
        await self.client.close()


# 实例化Qdrant客户端管理器（传入全局配置中的Qdrant配置）
qdrant_client_manager = QdrantClientManager(app_config.qdrant)

if __name__ == '__main__':

    # 初始化客户端对象
    qdrant_client_manager.init()
    # 获取客户端
    client =qdrant_client_manager.client
    async def test():
        """测试Qdrant异步客户端核心功能：创建集合、插入向量、相似度检索"""
        # 1.判断指定集合是否存在
        if not await client.collection_exists(collection_name="my_collection"):
            # 2.不存在集合，创建
            await client.create_collection(
                collection_name="my_collection", # 集合名称（类似数据库表名）
                # 向量字段配置：10维向量，使用余弦相似度计算
                vectors_config=models.VectorParams(size=app_config.qdrant.embedding_size, distance=Distance.COSINE),
            )

            """
            # 设置向量数据库向量存储规则
            vectors_config=models.VectorParams(size=10, distance=models.Distance.COSINE),
            参数一：size=10 表示存储10个维度向量
                简单理解就是：你要存的每个向量是 10 个数字组成的数组
                一般跟着模型设置值，BGE-large → 1024 维，属于高精度模型
             
            参数二：distance=models.Distance.COSINE 用余弦相似度做距离计算方式
                特点“它不看向量长度，只看方向，方向越接近，两个向量就越相似
                最适合文本、图像、语义、特征、推荐、RAG。
            """

        # 3.新增向量数据
        # await client.upsert(
        #     collection_name="my_collection",
              # 列表推导式生成 10 个PointStruct对象（包含ID和随机向量）
        #     points=[
        #         models.PointStruct(
        #             id=i, # 向量唯一标识ID
        #             payload={
        #                 "color": f"red{i}",
        #             },
        #             vector=[ random.random() for _ in range(1024)], # 生成10维随机向量
        #         )
        #         for i in range(10)
        #
        #     ],
        # )


        # 4.查询向量数据.  向量相似度检索：查找最相似的10个向量
        points = await client.query_points(
            collection_name="my_collection", # 检索的集合名称
            query=[ random.random() for _ in range(1024)], # 10维随机查询向量（type: ignore忽略类型提示）
            limit=2,  # 返回最相似的前10个向量
            score_threshold=0.4  # 相似度得分阈值：只返回得分≥0.5的结果
        )

        # 注意：查询向量对应的条件不是query_vector，修改为query

        # 打印检索结果中的向量点信息（包含ID、向量、得分等）
        print(points)
        print("-----------------")
        print(points.points)
        print("-----------------")
        print(points.points[0].payload)
        list=[point.payload for point in points.points]
        print(list)
        # for point in points.points:
        #     print(point)




        await qdrant_client_manager.close()

    # 运行异步测试函数（asyncio.run 是执行异步函数的标准方式）
    asyncio.run(test())
