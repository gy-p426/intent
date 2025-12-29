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

2. classify (分类预测)
   - 用途：预测数据的类别标签，判断数据属于哪个类别
   - 关键词：分类、预测类别、判断、识别类型、分级
   - 示例：判断邮件是否为垃圾邮件、预测客户是否会流失

3. predict (预测分析)
   - 用途：预测未来的数值或趋势
   - 关键词：预测、预估、预报、预见、未来
   - 示例：预测下个月销售额、预测明天天气

4. anomaly (异常检测)
   - 用途：发现数据中的异常点、离群点或异常模式
   - 关键词：异常点、异常值、异常波动、离群点、outlier、检测异常、发现异常
   - 示例：检测交易数据中的异常点、发现销售数据中的异常波动

5. associate (关联分析)
   - 用途：发现数据项之间的关联规则和关系
   - 关键词：关联、关系、规则、购物篮、一起购买
   - 示例：分析购买商品的关联关系、找出经常一起购买的产品

6. compare (对比分析)
   - 用途：比较不同组别或时期的差异
   - 关键词：对比、比较、差异、A/B测试、vs
   - 示例：对比两个季度的销售业绩、比较不同地区用户行为

7. similarity (相似度分析)
   - 用途：计算实体间的相似程度
   - 关键词：相似、相似度、匹配、相近
   - 示例：计算两条曲线的相似度、判断两篇文章的相似程度

8. trend (趋势分析)
   - 用途：分析时间序列数据的趋势变化、季节性模式
   - 关键词：趋势、变化趋势、走势、季节性、趋势分析、变化方向
   - 示例：分析销售数据的趋势变化、检测销售额的上升趋势

9. profile (用户画像)
   - 用途：构建实体的特征画像和档案
   - 关键词：画像、档案、特征、360度视图
   - 示例：基于交易数据生成用户画像、构建客户360度视图

10. causality (因果分析)
    - 用途：分析变量间的因果关系，找出根本原因
    - 关键词：原因、因果、根因、影响因素、为什么
    - 示例：分析销量下降的原因、找出客户流失的根本原因

11. alert (预警系统)
    - 用途：基于阈值的监控预警
    - 关键词：预警、报警、监控、阈值、警报
    - 示例：当库存低于阈值时发出预警、监控系统异常并实时报警

12. recommend (推荐系统)
    - 用途：提供个性化推荐和建议
    - 关键词：推荐、建议、优化、个性化
    - 示例：根据用户行为推荐产品、提供业务优化建议

识别原则：
1. 仔细分析用户问题的核心目标和意图
2. 重点关注问题中的关键动词和目标名词
3. 当问题包含多个可能的算法特征时，选择与主要目标最匹配的算法
4. 特别注意区分相似的场景：
   - "分析异常点" = anomaly (目标是找异常点)
   - "分析异常数据的趋势" = trend (目标是分析趋势，异常数据只是数据来源)
   - "检测异常" = anomaly (动作是检测异常)
   - "检测趋势" = trend (动作是检测趋势)

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
                'alert', 'recommend'
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