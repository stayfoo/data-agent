import asyncio

from langgraph.constants import START, END
from langgraph.graph import StateGraph

from app.agent.context import DataAgentContext
from app.agent.nodes.add_extra_context import add_extra_context
from app.agent.nodes.correct_sql import correct_sql
from app.agent.nodes.execute_sql import execute_sql
from app.agent.nodes.extract_keywords import extract_keywords
from app.agent.nodes.filter_metric import filter_metric
from app.agent.nodes.filter_table import filter_table
from app.agent.nodes.generate_sql import generate_sql
from app.agent.nodes.merge_retrieved_info import merge_retrieved_info
from app.agent.nodes.recall_column import recall_column
from app.agent.nodes.recall_metric import recall_metric
from app.agent.nodes.recall_value import recall_value
from app.agent.nodes.validata_sql import validata_sql
from app.agent.state import DataAgentState
from app.clients.embedding_client_manager import embedding_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.repositories.es.value_es_repository import ValueEsRepository
from app.repositories.mysql.dw_mysql_repository import DwMysqlRepository
from app.repositories.mysql.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository

# 构建工作流对象
# Graph 结构组装:
# 开始 → 提取关键字extract_keywords → 字段信息召回 recall_value、指标信息召回 recall_metric、字段值召回 recall_column
# → 合并召回信息 merge_retrieved_info → 过滤指标信息 filter_metric、过滤表信息 filter_table
# → 添加额外上下问信息 add_extra_context → 生成SQL generate_sql → 校验SQL validata_sql
#   → 如果 False → 矫正SQL → 执行SQL
#   → 如果 True → 执行SQL

# 构建图:
graph_builder = StateGraph(state_schema=DataAgentState,context_schema=DataAgentContext)
# 添加节点
graph_builder.add_node("extract_keywords",extract_keywords)
graph_builder.add_node("recall_column",recall_column)
graph_builder.add_node("recall_metric",recall_metric)
graph_builder.add_node("recall_value",recall_value)
graph_builder.add_node("merge_retrieved_info",merge_retrieved_info)
graph_builder.add_node("filter_metric",filter_metric)
graph_builder.add_node("filter_table",filter_table)
graph_builder.add_node("add_extra_context",add_extra_context)
graph_builder.add_node("generate_sql",generate_sql)
graph_builder.add_node("validata_sql",validata_sql)
graph_builder.add_node("correct_sql",correct_sql)
graph_builder.add_node("execute_sql",execute_sql)

# 添加边 - 关系
graph_builder.add_edge(START,"extract_keywords")
graph_builder.add_edge("extract_keywords","recall_column")
graph_builder.add_edge("extract_keywords","recall_metric")
graph_builder.add_edge("extract_keywords","recall_value")
graph_builder.add_edge("recall_column","merge_retrieved_info")
graph_builder.add_edge("recall_metric","merge_retrieved_info")
graph_builder.add_edge("recall_value","merge_retrieved_info")
graph_builder.add_edge("merge_retrieved_info","filter_metric")
graph_builder.add_edge("merge_retrieved_info","filter_table")
graph_builder.add_edge("filter_metric","add_extra_context")
graph_builder.add_edge("filter_table","add_extra_context")
graph_builder.add_edge("add_extra_context","generate_sql")
graph_builder.add_edge("generate_sql","validata_sql")


# 处理条件边 - 条件分支流转
graph_builder.add_conditional_edges(
    "validata_sql", #从哪个节点开始判断分支
    # 类型为 Callable[[State], str] 条件判断函数, 入参是图的 State，返回值是目标节点名称

    #根据 state 中的 error 状态决定下一个节点
    #    :param state: 状态字典，包含 "error" 键
    #    :return: 下一个节点名称（"execute_sql" 或 "correct_sql"）
    # 核心逻辑：无错误则执行SQL，有错误则修正SQL
    lambda state: "execute_sql" if state["error"] is None else "correct_sql" ,
    # 类型为dict[str, str]分支映射表：key = condition 函数的返回值，value = 目标节点名称
    {"correct_sql":"correct_sql","execute_sql":"execute_sql"}
)
graph_builder.add_edge("correct_sql","execute_sql")
graph_builder.add_edge("execute_sql",END)

# 编译图--获取全局graph对象
graph = graph_builder.compile()

# 查询图结构
# print(graph.get_graph().print_ascii())
# print(graph.get_graph().draw_mermaid())

if __name__ == '__main__':

    async def test():

        # 创建状态对象
        state = DataAgentState(query = "统计华北地区去年销售总额")

        # 初始化客户端
        embedding_manager.init()
        qdrant_client_manager.init()
        es_client_manager.init()
        meta_mysql_client_manager.init()
        dw_mysql_client_manager.init()

#
        async with meta_mysql_client_manager.session_factory() as meta_session,dw_mysql_client_manager.session_factory() as dw_session:
            # 创建repository
            column_qdrant_repository=ColumnQdrantRepository(qdrant_client_manager.client)
            metric_qdrant_repository= MetricQdrantRepository(qdrant_client_manager.client)
            value_es_repository=ValueEsRepository(es_client_manager.client)
            meta_mysql_repository=MetaMysqlRepository(meta_session)
            dw_mysql_repository=DwMysqlRepository(dw_session)
            # 创建上下文对象
            runtime = DataAgentContext(
                embedding_client=embedding_manager.client,
                column_qdrant_repository=column_qdrant_repository,
                metric_qdrant_repository=metric_qdrant_repository,
                value_es_repository=value_es_repository,
                meta_mysql_repository=meta_mysql_repository,
                dw_mysql_repository=dw_mysql_repository
            )

            # stream_mode:
            # values :在图的每一步之后流式传输状态的完整值。
            # updates: 在图的每一步之后流式传输状态更新
            # custom:  从您的图节点内部流式传输自定义数据
            # messages: 从任何调用语言模型（LLM）的图节点中流式传输模型数据

            # 调用图流式输出
            # 执行图
            async  for chunk in  graph.astream(input=state,context=runtime ,stream_mode="custom"):
                print(chunk)

        # 释放资源
        await qdrant_client_manager.close()
        await es_client_manager.close()
        await meta_mysql_client_manager.close()
        await dw_mysql_client_manager.close()

    asyncio.run(test())



"""
data-agent/
├─ app/
    ├─ agent/
         ├─ graph.py # 负责定义langgraph图
         ├─ state.py # 负责定义langgraph状态
         ├─ context.py # 负责定义langgraph运行上下文
         ├─ llm.py # 负责定义llm
         └─ nodes/
            ├─ extract_keywords.py # 负责定义关键词抽取的节点
            ├─ recall_column.py # 负责定义召回字段信息的节点
            ├─ recall_metric.py # 负责定义召回指标信息的节点
            ├─ recall_value.py  # 负责定义召回字段取值的节点
            ├─ merge_retrieved_info.py # 负责定义合并召回信息的节点
            ├─ filter_metric.py # 负责定义过滤指标信息的节点
            ├─ filter_table.py # 负责定义过滤表格信息的节点
            ├─ add_extra_context.py # 负责定义添加额外上下文信息的节点
            ├─ generate_sql.py # 负责定义生成SQL的节点
            ├─ validate_sql.py # 负责定义校验SQL的节点
            ├─ correct_sql.py # 负责定义校正SQL的节点
            └─ execute_sql.py # 负责定义执行SQL的节点
"""






