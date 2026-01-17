"""
CSV数据转换器
将SQL查询结果转换为CSV格式，用于Agent服务
"""
import csv
import io
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class CSVConverter:
    """CSV数据转换器"""
    
    @staticmethod
    def convert_to_csv(data: List[Dict[str, Any]]) -> bytes:
        """
        将SQL查询结果转换为CSV字节流
        
        Args:
            data: SQL查询结果列表，格式: [{"col1": "val1", "col2": "val2"}, ...]
            
        Returns:
            bytes: CSV文件的字节内容
            
        Raises:
            ValueError: 数据格式错误
        """
        if not data:
            logger.warning("数据为空，返回空CSV")
            return b""
        
        if not isinstance(data, list):
            raise ValueError(f"数据必须是列表类型，实际类型: {type(data)}")
        
        if not isinstance(data[0], dict):
            raise ValueError(f"数据元素必须是字典类型，实际类型: {type(data[0])}")
        
        try:
            # 使用StringIO作为内存缓冲区
            output = io.StringIO()
            
            # 获取列名（从第一行数据）
            fieldnames = list(data[0].keys())
            
            if not fieldnames:
                raise ValueError("数据字典为空，无法提取列名")
            
            # 创建CSV writer
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            
            # 写入表头
            writer.writeheader()
            
            # 写入数据行
            for row in data:
                writer.writerow(row)
            
            # 获取CSV内容并转换为字节
            csv_content = output.getvalue()
            csv_bytes = csv_content.encode('utf-8')
            
            logger.info(f"CSV转换完成: {len(data)}行数据, {len(fieldnames)}列, {len(csv_bytes)}字节")
            
            return csv_bytes
            
        except Exception as e:
            logger.error(f"CSV转换失败: {str(e)}", exc_info=True)
            raise ValueError(f"CSV转换失败: {str(e)}") from e
    
    @staticmethod
    def validate_data(data: List[Dict[str, Any]]) -> bool:
        """
        验证数据格式是否适合转换为CSV
        
        Args:
            data: 待验证的数据
            
        Returns:
            bool: 是否有效
        """
        if not data:
            return False
        
        if not isinstance(data, list):
            return False
        
        if not all(isinstance(row, dict) for row in data):
            return False
        
        # 检查所有行是否有相同的键
        if len(data) > 1:
            first_keys = set(data[0].keys())
            if not all(set(row.keys()) == first_keys for row in data[1:]):
                logger.warning("数据行的列不一致")
                return False
        
        return True
