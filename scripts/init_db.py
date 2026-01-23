"""
数据库初始化脚本
创建表结构并设置 TimescaleDB hypertable
"""
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.models import Base

# 加载环境变量
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/polymarket')


def init_database():
    """初始化数据库"""
    print("=" * 60)
    print("初始化 Polymarket 数据库")
    print("=" * 60)

    # 创建引擎
    engine = create_engine(DATABASE_URL, echo=True)

    # 创建所有表
    print("\n创建表结构...")
    Base.metadata.create_all(engine)
    print("✓ 表结构创建完成")

    # 设置 TimescaleDB hypertable（时序表）
    print("\n设置 TimescaleDB hypertable...")
    with engine.connect() as conn:
        try:
            # 将 trades 表转换为 hypertable
            conn.execute(text(
                "SELECT create_hypertable('trades', 'timestamp', if_not_exists => TRUE);"
            ))
            conn.commit()
            print("✓ trades 表已设置为 hypertable")
        except Exception as e:
            print(f"⚠ hypertable 设置失败（可能已存在）: {e}")

    print("\n" + "=" * 60)
    print("✓ 数据库初始化完成！")
    print("=" * 60)


if __name__ == "__main__":
    init_database()
