#!/usr/bin/env python3
"""
检查数据库状态
"""

import asyncio
import aiomysql
from infrastructure.config import get_settings


async def check_database():
    """检查数据库状态"""
    print("检查数据库状态...")
    
    settings = get_settings()
    print(f"连接信息: {settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}")
    
    try:
        # 创建连接池
        pool = await aiomysql.create_pool(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_username,
            password=settings.mysql_password,
            db=settings.mysql_database,
            charset='utf8mb4'
        )
        
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # 检查数据库中的表
                await cur.execute('SHOW TABLES')
                tables = await cur.fetchall()
                print(f"数据库中的表: {tables}")
                
                # 检查table_columns表是否存在
                table_exists = any('table_columns' in str(table) for table in tables)
                if not table_exists:
                    print("❌ table_columns表不存在！")
                    return
                
                # 检查table_columns表的总行数
                await cur.execute('SELECT COUNT(*) FROM table_columns')
                count = await cur.fetchone()
                print(f"table_columns表总行数: {count[0]}")
                
                if count[0] == 0:
                    print("❌ table_columns表为空！")
                    return
                
                # 检查有注释的列数
                await cur.execute('''
                    SELECT COUNT(*) FROM table_columns 
                    WHERE column_comment IS NOT NULL 
                      AND column_comment != '' 
                      AND TRIM(column_comment) != ''
                ''')
                count2 = await cur.fetchone()
                print(f"有注释的列数: {count2[0]}")
                
                # 显示前5行数据
                await cur.execute('SELECT * FROM table_columns LIMIT 5')
                rows = await cur.fetchall()
                print("前5行数据:")
                for i, row in enumerate(rows, 1):
                    print(f"  {i}. {row}")
                
                # 显示表结构
                await cur.execute('DESCRIBE table_columns')
                columns = await cur.fetchall()
                print("表结构:")
                for col in columns:
                    print(f"  {col}")
        
        pool.close()
        await pool.wait_closed()
        
    except Exception as e:
        print(f"❌ 数据库检查失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_database())