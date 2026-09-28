from sentry_sdk.utils import ContextVar

# 负责定义异步任务上下文变量

request_id_ctx_var=ContextVar("request_id")

# ContextVar = 协程上下文变量
# ContextVar 是 Python 3.7+ 引入的上下文变量，来自 contextvars 标准库，核心作用是：在异步编程、多任务协程、函数嵌套调用中，安全地存储和传递「上下文数据」，且不会互相干扰。
# 简单理解：专门适配现代 Python 的异步协程（asyncio） 和多任务并发场景，多个协程同时运行时，各自的 ContextVar 值完全隔离，不会互相覆盖




# 定义上下文变量request_id_ctx_var，用于在异步/多请求场景下存储和获取当前请求的唯一标识request_id
# 参数1："request_id" - 上下文变量的名称，用于标识该变量的用途
# 参数2：default=1 - 默认值，当未显式设置 request_id 时，获取到的值为 1
# request_id_ctx_var = ContextVar("request_id",default=1)

