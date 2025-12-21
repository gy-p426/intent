#!/usr/bin/env python3
"""
显示table_columns表结构
"""

import asyncio
import aiomysql
from infrastructure.config import get_settings


async def show_table_structure():
    """显示table_columns表结构"""
    print("显示table_columns表结构...")
    
    settings = get_settings()
    
    try:
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
                # 显示表结构
                await cur.execute('DESCRIBE table_columns')
                columns = await cur.fetchall()
                print("table_columns表结构:")
                print("字段名\t\t类型\t\t\t空值\t键\t默认值\t额外")
                print("-" * 80)
                for col in columns:
                    print(f"{col[0]:<15}\t{col[1]:<15}\t{col[2]:<5}\t{col[3] or '':<5}\t{col[4] or '':<10}\t{col[5] or ''}")
        
        pool.close()
        await pool.wait_closed()
        
    except Exception as e:
        print(f"❌ 查询失败: {str(e)}")


if __name__ == "__main__":
    asyncio.run(show_table_structure())