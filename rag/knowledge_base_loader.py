"""
知识库加载器
负责加载和解析intent.txt文件
"""
import logging
from typing import List
from pathlib import Path
from pydantic import BaseModel


logger = logging.getLogger(__name__)


class IntentEntry(BaseModel):
    """知识库条目"""
    text: str  # 用户问题示例
    intent: str  # 对应的微服务名称


class KnowledgeBaseLoader:
    """
    知识库加载器
    解析CSV格式的intent.txt文件（格式：text,intent）
    """
    
    def __init__(self, file_path: str):
        """
        初始化知识库加载器
        
        Args:
            file_path: 知识库文件路径
        """
        self.file_path = file_path
        self._entries: List[IntentEntry] = []
    
    def load(self) -> List[IntentEntry]:
        """
        加载知识库文件
        
        Returns:
            List[IntentEntry]: 知识库条目列表
        """
        try:
            file = Path(self.file_path)
            
            if not file.exists():
                logger.error(f"知识库文件不存在: {self.file_path}")
                return []
            
            entries = []
            with open(file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
                # 跳过标题行
                if len(lines) > 0 and lines[0].strip().lower() == 'text,intent':
                    lines = lines[1:]
                
                for line_num, line in enumerate(lines, start=2):
                    line = line.strip()
                    if not line:  # 跳过空行
                        continue
                    
                    parts = line.split(',', 1)  # 只分割第一个逗号
                    if len(parts) != 2:
                        logger.warning(
                            f"知识库文件格式错误 (行 {line_num}): {line}. "
                            f"期望格式: text,intent"
                        )
                        continue
                    
                    text, intent = parts[0].strip(), parts[1].strip()
                    if not text or not intent:
                        logger.warning(
                            f"知识库文件包含空字段 (行 {line_num}): {line}"
                        )
                        continue
                    
                    entries.append(IntentEntry(text=text, intent=intent))
            
            self._entries = entries
            logger.info(f"成功加载知识库: {len(entries)} 条记录")
            return entries
            
        except Exception as e:
            logger.error(f"加载知识库文件失败: {str(e)}", exc_info=True)
            return []
    
    def reload(self) -> List[IntentEntry]:
        """
        重新加载知识库
        
        Returns:
            List[IntentEntry]: 知识库条目列表
        """
        logger.info(f"重新加载知识库: {self.file_path}")
        return self.load()
    
    @property
    def entries(self) -> List[IntentEntry]:
        """获取已加载的知识库条目"""
        return self._entries
