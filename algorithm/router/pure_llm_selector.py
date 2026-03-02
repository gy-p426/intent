"""
纯LLM算法类型选择器
不使用RAG，直接通过提示词让大模型判断算法类型
"""

import logging
from typing import Optional, List, Dict
from llm.llm_client import LLMClient
from algorithm.models import AlgorithmType
from infrastructure.config import get_settings

logger = logging.getLogger(__name__)


class PureLLMAlgorithmSelector:
    """纯LLM算法类型选择器"""
    
    def __init__(self):
        """初始化选择器"""
        self.settings = get_settings()
        
        try:
            # 使用专门的算法识别配置
            self.llm_client = LLMClient(
                model=self.settings.algorithm_detection_model,
                timeout=self.settings.algorithm_detection_timeout,
                max_retries=self.settings.algorithm_detection_max_retries
            )
            logger.info(f"纯LLM算法选择器初始化成功，模型: {self.settings.algorithm_detection_model}")
        except Exception as e:
            logger.error(f"纯LLM算法选择器初始化失败: {str(e)}")
            raise
    
    async def select_algorithm(self, question: str) -> Optional[AlgorithmType]:
        """
        选择算法类型
        
        Args:
            question: 用户问题
            
        Returns:
            Optional[AlgorithmType]: 算法类型
        """
        try:
            logger.debug(f"使用纯LLM识别算法类型: {question}")
            
            # 构建提示词
            messages = self._build_prompt(question)
            
            # 调用LLM
            response = await self.llm_client.chat_completion(messages)
            
            # 解析响应
            algorithm_type = self._parse_response(response)
            
            if algorithm_type:
                logger.info(f"纯LLM识别算法类型成功: {question} -> {algorithm_type.value}")
            else:
                logger.warning(f"纯LLM无法识别算法类型: {question}")
            
            return algorithm_type
            
        except Exception as e:
            logger.error(f"纯LLM算法选择失败: {str(e)}")
            return None
    
    def _build_prompt(self, question: str) -> List[Dict[str, str]]:
        """
        构建LLM提示词
        
        Args:
            question: 用户问题
            
        Returns:
            List[Dict[str, str]]: 消息列表
        """
        system_prompt = """你是一个专业的算法类型识别专家。根据用户的问题，从以下算法类型中选择最合适的一个：

算法类型详细说明：

1. cluster (聚类分析)
   - 用途：将数据按相似性分组，发现数据中的自然群体
   - 关键词：分群、聚类、分组、归类、K-means、按...分类
   - 示例：将客户按购买偏好分群、根据用户特征自动分群


2. predict (预测分析) ⭐ forecast_service
   - 用途：预测未来的数值，基于历史数据预测未来走向
   - 关键词：预测、预估、预报、预见、未来、下个月、明年、接下来
   - 示例：预测下个月销售额、预测未来7天的出车次数、预估明年的收入
   - 注意：强调"未来"时间点的数值预测，不是分析历史数据

3. anomaly (异常检测)
   - 用途：发现数据中的异常点、离群点或异常模式
   - 关键词：异常点、异常值、异常波动、离群点、outlier、检测异常、发现异常
   - 示例：检测交易数据中的异常点、发现销售数据中的异常波动

4. associate (关联分析)
   - 用途：发现数据项之间的关联规则和关系
   - 关键词：关联、关系、规则、购物篮、一起购买
   - 示例：分析购买商品的关联关系、找出经常一起购买的产品

5. similarity (相似度分析)
   - 用途：计算实体间的相似程度
   - 关键词：相似、相似度、匹配、相近
   - 示例：计算两条曲线的相似度、判断两篇文章的相似程度

6. trend (趋势分析) ⭐ forecast_service
   - 用途：分解时间序列的趋势成分、季节性成分，分析整体走势方向
   - 关键词：趋势分解、趋势成分、季节性分解、STL分解、整体走势、长期趋势、上升趋势、下降趋势
   - 示例：分解销售数据的趋势和季节性成分、分析整体趋势是上升还是下降、使用STL分解时间序列
   - 注意：侧重于分解和识别趋势方向，不涉及周期对比（环比/同比）

7. causality (因果分析)
    - 用途：分析变量间的因果关系，找出根本原因
    - 关键词：原因、因果、根因、影响因素、为什么
    - 示例：分析销量下降的原因、找出客户流失的根本原因

8. nl2sql(数据查询)
    - 用途：通过用户自然语言生成sql在数据库中查询数据，仅对数据做查询、同比分析、环比分析、分类、占比分析处理
    - 关键词：查询、同步、环比、分类、占比
    - 示例1：查询一总站的所有人员的电话信息
    - 示例2：对2025年8月每天的出车次数做同比分析/环比分析
    - 示例3：将员工的绩效按优秀、合格、不合格分类
    - 示例4：分析员工绩效总分在80分以上的占比

识别原则：
1. 仔细分析用户问题的核心目标和意图
2. 重点关注问题中的关键动词和目标名词
3. 当问题包含多个可能的算法特征时，选择与主要目标最匹配的算法

⭐ 特别注意区分 forecast_service 的两个算法：

【predict vs trend 区分规则】

A. predict（预测）：
   - 核心特征：预测"未来"的数值
   - 触发词：预测、预估、预报、未来、下个月、明年、接下来N天
   - 示例："预测下个月销售额" → predict
   - 示例："预测未来7天的出车次数" → predict

B. trend（趋势分析）：
   - 核心特征：分解趋势成分、分析整体走势方向
   - 触发词：趋势分解、季节性分解、STL、整体趋势、长期走势、趋势方向
   - 示例："分解销售数据的趋势和季节性" → trend
   - 示例："分析整体趋势是上升还是下降" → trend
   - 示例："使用STL分解时间序列" → trend

【易混淆场景判断】
- "分析销售的整体趋势" → trend（"整体趋势"表示趋势分解）
- "预测下月销售趋势" → predict（"预测下月"表示未来预测）

【其他区分规则】
- "分析异常点" = anomaly（目标是找异常点）
- "分析异常数据的趋势" = trend（目标是分析趋势，异常数据只是数据来源）
- "对比A和B部门" = compare（非时间维度对比）

请直接输出算法类型名称，不需要解释。"""

        user_prompt = f"用户问题: {question}"
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    def _parse_response(self, response: str) -> Optional[AlgorithmType]:
        """
        解析LLM响应
        
        Args:
            response: LLM响应文本
            
        Returns:
            Optional[AlgorithmType]: 算法类型
        """
        try:
            response = response.strip().lower()
            
            # 定义有效的算法类型
            valid_algorithms = {
                'cluster', 'classify', 'predict', 'anomaly', 'associate', 
                'compare', 'similarity', 'trend', 'profile', 'causality', 
                'nl2sql',
            }
            
            # 直接匹配
            if response in valid_algorithms:
                return AlgorithmType(response)
            
            # 从响应中查找有效的算法类型
            for algorithm in valid_algorithms:
                if algorithm in response:
                    return AlgorithmType(algorithm)
            
            logger.warning(f"无法解析LLM响应为有效算法类型: {response}")
            return None
            
        except Exception as e:
            logger.error(f"解析LLM响应失败: {str(e)}, 响应: {response}")
            return None