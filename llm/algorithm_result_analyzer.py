"""
算法结果分析专用LLM模块
用于将算法的原始返回数据转换为用户友好的自然语言分析结果
"""
import json
import logging
from typing import Dict, Any, Optional
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


class AlgorithmResultAnalyzer:
    """
    算法结果分析器
    使用大模型将算法原始输出转换为用户友好的自然语言分析
    """
    
    def __init__(self, llm_client: LLMClient):
        """
        初始化算法结果分析器
        
        Args:
            llm_client: LLM API客户端
        """
        self.client = llm_client
        logger.info("AlgorithmResultAnalyzer initialized")
    
    async def analyze_algorithm_result(
        self, 
        user_question: str,
        algorithm_type: str,
        algorithm_result: Dict[str, Any],
        original_data_summary: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        使用大模型分析算法结果
        
        Args:
            user_question: 用户原始问题
            algorithm_type: 算法类型
            algorithm_result: 算法原始返回数据
            original_data_summary: 原始数据摘要信息
            
        Returns:
            str: 用户友好的自然语言分析结果
            
        Raises:
            Exception: LLM调用或响应解析失败
        """
        try:
            logger.debug(f"开始分析算法结果，算法类型: {algorithm_type}")
            
            # 构建分析提示词
            messages = self._build_analysis_prompt(
                user_question, algorithm_type, algorithm_result, original_data_summary
            )
            
            # 调用LLM API
            response = await self.client.chat_completion(messages)
            
            # 清理和验证响应
            analysis_result = self._clean_analysis_response(response)
            
            logger.info(f"算法结果分析完成，生成了 {len(analysis_result)} 字符的分析")
            return analysis_result
            
        except Exception as e:
            logger.error(f"算法结果分析失败: {str(e)}", exc_info=True)
            # 返回降级结果而不是抛出异常
            return self._generate_fallback_analysis(algorithm_type, algorithm_result)
    
    def _build_analysis_prompt(
        self, 
        user_question: str,
        algorithm_type: str,
        algorithm_result: Dict[str, Any],
        original_data_summary: Optional[Dict[str, Any]] = None
    ) -> list:
        """
        构建算法结果分析提示词
        
        Args:
            user_question: 用户原始问题
            algorithm_type: 算法类型
            algorithm_result: 算法结果
            original_data_summary: 数据摘要
            
        Returns:
            list: 消息列表
        """
        # 系统提示词
        system_prompt = """你是一个专业的数据分析师，擅长将复杂的算法分析结果转换为用户容易理解的自然语言描述。

你的任务是：
1. 分析用户的原始问题和算法执行结果
2. 用通俗易懂的语言解释分析结果
3. 突出关键发现和洞察
4. 提供实用的业务建议

输出要求：
- 使用自然、流畅的中文
- 避免过多技术术语
- 重点突出对用户有价值的信息
- 结构清晰，逻辑连贯
- 长度控制在200-500字之间

请直接输出分析结果，不需要额外的格式标记。"""
        
        # 格式化算法结果为JSON字符串
        try:
            algorithm_result_json = json.dumps(algorithm_result, indent=2, ensure_ascii=False)
        except Exception:
            algorithm_result_json = str(algorithm_result)
        
        # 构建数据摘要信息
        data_summary_text = ""
        if original_data_summary:
            data_summary_text = f"\n\n数据摘要信息：\n{json.dumps(original_data_summary, indent=2, ensure_ascii=False)}"
        
        # 用户提示词
        user_prompt = f"""请分析以下算法执行结果：

用户原始问题：{user_question}

算法类型：{algorithm_type}

算法执行结果：
{algorithm_result_json}{data_summary_text}

请用自然语言分析这个结果，重点解释：
1. 根据用户问题，这个分析结果说明了什么？
2. 有哪些关键发现和洞察？
3. 对用户有什么实际价值和建议？

请直接给出分析结果："""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        logger.debug(f"构建分析提示词: system={len(system_prompt)} chars, user={len(user_prompt)} chars")
        
        return messages
    
    def _clean_analysis_response(self, response: str) -> str:
        """
        清理和验证分析响应
        
        Args:
            response: 大模型返回的响应
            
        Returns:
            str: 清理后的分析结果
        """
        try:
            # 基本清理
            cleaned_response = response.strip()
            
            # 移除可能的格式标记
            if cleaned_response.startswith('```'):
                lines = cleaned_response.split('\n')
                # 移除第一行和最后一行的```标记
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                cleaned_response = '\n'.join(lines).strip()
            
            # 确保有内容
            if not cleaned_response:
                raise ValueError("分析结果为空")
            
            # 长度检查
            if len(cleaned_response) < 50:
                logger.warning(f"分析结果过短: {len(cleaned_response)} 字符")
            elif len(cleaned_response) > 1000:
                logger.warning(f"分析结果过长: {len(cleaned_response)} 字符，将截取前1000字符")
                cleaned_response = cleaned_response[:1000] + "..."
            
            return cleaned_response
            
        except Exception as e:
            logger.error(f"清理分析响应失败: {str(e)}")
            return response.strip() if response else "分析结果处理失败"
    
    def _generate_fallback_analysis(
        self, 
        algorithm_type: str, 
        algorithm_result: Dict[str, Any]
    ) -> str:
        """
        生成降级分析结果（当LLM调用失败时使用）
        
        Args:
            algorithm_type: 算法类型
            algorithm_result: 算法结果
            
        Returns:
            str: 降级分析结果
        """
        try:
            status = algorithm_result.get('status', 'unknown')
            
            if status == 'success':
                # 根据算法类型生成基本分析
                if algorithm_type == 'cluster':
                    k_used = algorithm_result.get('k_used', 0)
                    results = algorithm_result.get('results', [])
                    return f"聚类分析已完成，成功将 {len(results)} 个数据点分为 {k_used} 个聚类。每个聚类代表具有相似特征的数据组，可以帮助您理解数据的内在结构和模式。"
                
                elif algorithm_type == 'classify':
                    results = algorithm_result.get('results', [])
                    return f"分类分析已完成，对 {len(results)} 个数据点进行了分类预测。分类结果可以帮助您了解数据的类别分布，为决策提供参考。"
                
                elif algorithm_type == 'anomaly':
                    results = algorithm_result.get('results', [])
                    anomalies = [r for r in results if r.get('cluster_id') == -1]
                    return f"异常检测已完成，在 {len(results)} 个数据点中发现了 {len(anomalies)} 个异常点。这些异常点可能代表特殊情况或需要关注的数据，建议进一步分析。"
                
                elif algorithm_type == 'trend':
                    trend_direction = algorithm_result.get('results', {}).get('trend_direction', 'unknown')
                    direction_map = {'increasing': '上升', 'decreasing': '下降', 'stable': '稳定'}
                    direction_chinese = direction_map.get(trend_direction, '未知')
                    return f"趋势分析已完成，数据呈现 {direction_chinese} 趋势。这个趋势信息可以帮助您了解数据的变化规律，为未来规划提供参考。"
                
                elif algorithm_type == 'predict':
                    predictions = algorithm_result.get('predictions', [])
                    forecast_values = algorithm_result.get('results', {}).get('forecast', [])
                    count = len(predictions) or len(forecast_values)
                    return f"预测分析已完成，生成了 {count} 个预测值。预测结果基于历史数据模式，可以帮助您了解未来可能的发展趋势。"
                
                else:
                    return f"{algorithm_type} 算法分析已完成。分析结果包含了基于您数据的深度洞察，可以为您的业务决策提供数据支持。"
            
            else:
                error_msg = algorithm_result.get('error', algorithm_result.get('message', '未知错误'))
                return f"算法分析过程中遇到了问题：{error_msg}。建议检查数据质量或调整分析参数后重试。"
                
        except Exception as e:
            logger.error(f"生成降级分析失败: {str(e)}")
            return f"{algorithm_type} 算法已执行完成，但分析结果处理遇到问题。请查看技术细节了解具体结果。"
    
    async def analyze_multiple_results(
        self,
        user_question: str,
        results: list[Dict[str, Any]]
    ) -> str:
        """
        分析多个算法结果（用于对比分析等场景）
        
        Args:
            user_question: 用户原始问题
            results: 多个算法结果列表
            
        Returns:
            str: 综合分析结果
        """
        try:
            # 构建多结果分析提示词
            system_prompt = """你是一个专业的数据分析师，擅长综合分析多个算法结果并提供洞察。

请分析多个算法的执行结果，找出它们之间的关联性、一致性或差异性，并提供综合性的业务建议。

输出要求：
- 突出不同算法结果之间的关系
- 提供综合性的洞察和建议
- 用自然流畅的中文表达
- 长度控制在300-600字之间"""
            
            results_json = json.dumps(results, indent=2, ensure_ascii=False)
            
            user_prompt = f"""用户问题：{user_question}

多个算法执行结果：
{results_json}

请综合分析这些结果，提供整体性的洞察和建议："""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = await self.client.chat_completion(messages)
            return self._clean_analysis_response(response)
            
        except Exception as e:
            logger.error(f"多结果分析失败: {str(e)}")
            return f"已完成多个算法的分析，共 {len(results)} 个结果。建议查看各个算法的详细结果进行对比分析。"
    
    def get_analysis_summary_stats(self) -> Dict[str, Any]:
        """
        获取分析统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        # 这里可以添加统计信息收集逻辑
        return {
            "analyzer_status": "active",
            "supported_algorithms": [
                "cluster", "classify", "anomaly", "trend", "predict"
            ],
            "fallback_enabled": True
        }