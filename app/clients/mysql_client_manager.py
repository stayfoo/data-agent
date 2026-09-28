import asyncio
from typing import Optional

from dns.entropy import pool
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker

from app.conf.app_config import app_config, DBConfig


class MysqlClientManager:
    def __init__(self, config: DBConfig):
        self.engine: Optional[AsyncEngine] = None
        self.config = config
        self.session_factory=None

    def _get_url(self):
        return f"mysql+asyncmy://{self.config.user}:{self.config.password}@{self.config.host}:{self.config.port}/{self.config.database}?charset=utf8mb4"

    def init(self):
        # 创建异步引擎
        self.engine = create_async_engine(
            url=self._get_url(), # 指定数据地址
            pool_size =5,  # 设置连接池最大空闲连接数
            pool_pre_ping= True  # 提前检测死连接，自动替换为新连接，避免业务报错。
        )
        """
        pool_size: 用于设置数据库连接池的固定大小，也就是连接池中始终保持的 “活跃” 数据库连接数量。
    核心作用：连接池会预先创建 10 个数据库连接并维护，当程序需要访问数据库时，直接从池中获取空闲连接，用完后归还，避免频繁创建 / 销毁连接（创建数据库连接是高开销操作）。
    10 表示连接池的最大 “常驻” 连接数，程序同时最多能从池中获取 10 个连接，超出的请求会等待（直到超时或有连接归还）。
    
        pool_pre_ping：是连接池的 “心跳检测” 开关，开启后会在从连接池获取连接时，先执行一个轻量的 ping 操作（比如 SELECT 1），验证连接是否有效。
    核心作用：解决 “失效连接” 问题：MySQL 默认 wait_timeout 8 小时，连接放着太久不用，服务端主动掐断连接，程序连接池还拿着旧失效连接，一执行 SQL 就报错。（如 MySQL server has gone away）。
    开启后，每次获取连接前会先检测连接可用性：如果连接失效，会自动丢弃该连接并重新创建一个新连接，保证程序拿到的是可用连接。	 
        """
        self.session_factory=async_sessionmaker(
            bind=self.engine, # 绑定异步引擎
            # autoflush=False, 只有你手动调用 session.flush() 或 session.commit() 时才会把内存中的对象变更同步到数据库；
            autoflush=True,
            autobegin=True,
            # 提交后，ORM 对象的属性仍保留内存中的值，访问时不触发任何数据库 IO
            expire_on_commit=False # 关闭自动过期
        )
        """
        # 创建异步数据库会话（自动管理会话的创建与关闭）
        async with AsyncSession(dw_mysql_client_manager.engine,autoflush=True,expire_on_commit=False) as session:
            pass
        
        1.：自动刷新
            autoflush（默认值为 True）控制当你执行查询操作时，是否自动将当前会话中未提交的修改（新增 / 修改 / 删除）先同步到数据库（但未真正提交事务）。
        可以用一个简单的比喻理解：
        你在会话里对数据做的修改，就像在草稿纸上写的内容；
            (1)flush 是把草稿纸内容 “誊抄” 到数据库的临时区域（未最终确认）；
            (2)commit 是最终 “盖章确认”，让修改永久生效；
            (3)autoflush=True 就是：你每次想 “查数据库”（执行查询）时，系统会先自动把草稿纸的内容誊抄好，再查，保证你查到的是最新的内容。
        
        
        2.autobegin:事务的自动开启
            autobegin（默认值为 True）控制 SQLAlchemy Session 是否自动为首次数据库操作开启事务，无需开发者手动调用 session.begin()。
        
        3.expire_on_commit:    
            expire_on_commit（默认值为 True）控制：当你调用 session.commit() 提交事务后，从数据库查询出来的 ORM 对象（实例）是否会被标记为 “过期（expired）”。
            (1)expire_on_commit=True:
                提交后状态：事务提交后，所有通过该会话查询到的 ORM 对象会被 “过期”—— 对象的属性仍可访问，但首次访问时会自动发起数据库查询，重新加载最新数据；
                核心目的：保证你访问的始终是数据库中的最新数据，避免使用内存中过时的缓存；
            (2)expire_on_commit=False:
                提交后状态：事务提交后，ORM 对象不会过期，访问属性时直接使用内存中已加载的数据，不会触发额外查询；
                核心优势：提升性能，减少数据库交互；
                
        注意：expire_on_commit在异步场景下需要设置为False   
            在异步环境下如果设置为true,表示通过该session获取的对象为过期，再次查询的时候会进行一次io请求，再次查询，但是在异步函数中执行io请求需要添加await关键字，而对查询结果处理操作并不是一个可等待的协程，又无法添加await关键字，所以无法使用True,需要设置为False
            
            理解案例：
                # 关闭自动过期
                session.expire_on_commit = False  
                # 先获取一个用户
                user = await session.get(User, 1)
                print(user.name)  # 输出：张三
                
                user.name = "李四"
                await session.commit()  
            
                # 提交后，对象不会刷新
                print(user.name)  
                # 👉 还是内存里的旧数据！可能不是最新的！
            
                
            
                 # 关闭自动过期
                session.expire_on_commit = True  
                # 先获取一个用户
                user = await session.get(User, 1)
                print(user.name)  # 输出：张三 
                # 1. 修改并提交
                user.name = "李四"
                await session.commit()  
            
                # 2. 提交后，旧对象已经“过期”
                print(user.name)  
                # 👉 自动重新去数据库查最新值！输出：李四
        """

    async def close(self):
        await self.engine.dispose()


dw_mysql_client_manager = MysqlClientManager(app_config.db_dw)
meta_mysql_client_manager = MysqlClientManager(app_config.db_meta)

if __name__ == '__main__':
    # 初始化客户端
    dw_mysql_client_manager.init()


    # 定义异步函数
    async def test():
        # 获取session
        # async with AsyncSession(bind=dw_mysql_client_manager.engine, autoflush=True, autobegin=True, expire_on_commit=True) as session:
        async with dw_mysql_client_manager.session_factory() as session:
            # 执行操作
            sql = "select *from fact_order limit 10"
            # 执行sql
            result = await session.execute(text(sql))

            # 获取结果
            # rows = result.mappings().fetchall()  # 提取查询结果rows对象结构如：[(),(),()]
            rows = result.scalars().fetchall() # 提取查询结果封装成字典结构如：[{},{},{}]
            # 输出返回结果类型
            # print(type(rows[0]))
            # rows = result.fetchall()
            print(type(rows))  # 输出首行数据
            print(rows)
            # print(rows[0])  # 输出首行数据
        await dw_mysql_client_manager.close()
    # 执行异步函数
    asyncio.run(test())
