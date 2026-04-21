# src/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 数据库连接 URL (请将密码替换为你在 Docker 中设置的密码)
# 格式: postgresql://用户名:密码@服务器IP:端口/数据库名
SQLALCHEMY_DATABASE_URL = "postgresql://hdu_admin:HDU%40gent@127.0.0.1:54321/hdu_agent_db"

# 创建数据库引擎
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ORM 模型基类
Base = declarative_base()

# 获取数据库会话的依赖函数（供 FastAPI 路由使用）
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
