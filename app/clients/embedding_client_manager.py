from typing import Optional

import httpx
from langchain_core.embeddings import Embeddings

from app.conf.app_config import app_config, EmbeddingConfig


class TEIEmbeddings(Embeddings):
    """通过 Text Embeddings Inference (TEI) 的 HTTP API 获取文本向量。"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        # TEI 的 /embed 接口支持 inputs 为字符串列表，适合批量构建向量索引。
        self._client = httpx.Client(timeout=60, trust_env=False)
        self._async_client = httpx.AsyncClient(timeout=60, trust_env=False)

    def _embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.post(f"{self.base_url}/embed", json={"inputs": texts})
        response.raise_for_status()
        return response.json()

    async def _aembed(self, texts: list[str]) -> list[list[float]]:
        response = await self._async_client.post(
            f"{self.base_url}/embed", json={"inputs": texts}
        )
        response.raise_for_status()
        return response.json()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed([text.replace("\n", " ") for text in texts])

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._aembed([text.replace("\n", " ") for text in texts])

    async def aembed_query(self, text: str) -> list[float]:
        return (await self.aembed_documents([text]))[0]

    async def aclose(self) -> None:
        await self._async_client.aclose()
        self._client.close()


class EmbeddingClientManager:
    """管理本地 TEI embedding 客户端的创建和关闭。"""

    def __init__(self, config: EmbeddingConfig):
        self.client: Optional[TEIEmbeddings] = None
        self.config = config

    def _get_url(self) -> str:
        return f"http://{self.config.host}:{self.config.port}"

    def init(self) -> None:
        self.client = TEIEmbeddings(base_url=self._get_url())

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None


embedding_manager = EmbeddingClientManager(app_config.embedding)



# import asyncio
# from typing import Optional
#
# from langchain_huggingface import HuggingFaceEndpointEmbeddings
#
# from app.conf.app_config import app_config, EmbeddingConfig
#
#
# """
# Hugging Face 文本嵌入推理（Text Embeddings Inference，简称 TEI）是一套用于部署和提供开源文本嵌入与序列分类模型服务的工具包。
# TEI 可为当下最主流的各类模型实现高性能的特征提取。
# bedding Inference客户端使用HuggingFaceEndpointEmbeddings，具体用法参考官方文档。
# 向量模型服务创建时使用的是bge-large-zh-v1.5模型
#
#
# bge-large-zh-v1.5 是底层 AI 向量模型
# TEI 是专门用来把这个模型包装成「在线向量接口服务」的部署工具
# HuggingFaceEndpointEmbeddings 是 LangChain 里的客户端，用来远程调用 TEI 跑起来的向量服务
#
# TEI和bge的关系： BGE 是嵌入向量模型，TEI 是跑模型的服务化引擎；你通过 TEI 调用 BGE 做向量化
#
#
# """
#
# class EmbeddingClientManager:
#     """
#     嵌入式向量嵌入客户端管理器类
#     用于管理 HuggingFaceEndpointEmbeddings 客户端的初始化和配置
#     """
#     def __init__(self,config:EmbeddingConfig):
#         """
#         初始化嵌入式客户端管理器
#         Args:
#             config (EmbeddingConfig): 嵌入服务的配置对象，包含 host、port 等关键配置
#         """
#         # 保存嵌入服务配置
#         # 初始化嵌入客户端对象，初始值为 None，后续通过 init 方法初始化
#         self.client:Optional[HuggingFaceEndpointEmbeddings] =None
#         self.config =config
#
#     def _get_url(self):
#         """
#         私有方法：根据配置拼接嵌入服务的完整 URL
#
#         Returns:
#             str: 拼接后的嵌入式服务地址（http://host:port 格式）
#         """
#         return f"http://{self.config.host}:{self.config.port}"
#     def init(self):
#         """
#         初始化 HuggingFaceEndpointEmbeddings 客户端
#         将拼接好的服务 URL 作为模型地址传入客户端
#         """
#         self.client = HuggingFaceEndpointEmbeddings(model=self._get_url())
#
# # 创建 EmbeddedClientManager 实例（全局变量），传入应用配置中的嵌入服务配置
# embedding_manager = EmbeddingClientManager(app_config.embedding)
#
# # 主程序入口：测试嵌入式客户端功能
# if __name__ == '__main__':
#     # 初始化向量对象      # 初始化嵌入客户端
#     embedding_manager.init()
#     # 获取向量对象
#     embeddings=embedding_manager.client
#     # 定义异步函数
#     async def test():
#         # 定义文本
#         text="我是中国人"
#         text_list=["我是中国人","我爱中国"]
#         # 转换 list[float]
#         # query_result =await embeddings.aembed_query(text)      # .embed_query(text) 对文本 text 进行向量嵌入
#         # list[list[float],list[float]]
#         result_list=await embeddings.aembed_documents(text_list)
#
#         print(result_list)
#         # print(len(query_result)) # 打印嵌入向量的长度
#         # print(type(query_result))
#         # print(query_result)     # 打印嵌入向量的具体值
#
#     asyncio.run(test())
