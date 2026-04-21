# src/core/init_db.py
from src.core.database import engine, Base
from src.core.models import User, ChatMessage

def init_db():
    print("正在连接数据库并创建表结构...")
    # 自动检查并创建定义好的所有表（如果表已存在则会忽略）
    Base.metadata.create_all(bind=engine)
    print("数据库初始化完成！")

if __name__ == "__main__":
    init_db()
