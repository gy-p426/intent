"""
Algorithm Result Analyzer

使用大模型自动将算法原始结果转换为用户友好的自然语言分析。
这是新文档 `算法接入改.md` 中描述的核心功能。
"""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime

from infrastructure.config import get_settings

logger = logging.getLogger(__name__)


class AlgorithmResultAnalyzer:
    """
    算法结果分析器
    
    使用大模型自动分析算法执行结果，生成用户友好的自然语言描述。
    """
    
    def __init__(self):
        """初始化结果分析器"""
        self.settings = get_settings()
        self.enabled = self.settings.enable_llm_result_analysis
        self.model = self.settings.llm_analysis_model
        self.timeout = self.settings.llm_analysis_timeout
        self.max_retries = self.settings.llm_analysis_max_retries
        self.fallback_enabled = self.settings.llm_analysis_fallback_enabled
        
        # 延迟导入 LLM 客户端
        self._llm_client = None
        
        logger.info(f"算法结果分析器初始化完成，启用状态: {self.enabled}")
    
    @property
    def llm_client(self):
        """延迟加载 LLM 客户端"""
        if self._llm_client is None:
            try:
                from llm.llm_client import LLMClient
                self._llm_client = LLMClient(
                    api_key=self.settings.ark_api_key,
                    model=self.model,
                    timeout=self.timeout,
                    max_retries=self.max_retries,
                    retry_delay=2
                )
                logger.info("LLM 客户端加载成功")
            except Exception as e:
                logger.warning(f"LLM 客户端加载失败: {str(e)}")
                self._llm_client = None
        return self._llm_client
    
    async def analyze_result(
        self,
        user_question: str,
        algorithm_type: str,
        algorithm_result: Dict[str, Any],
        original_data_count: int = 0
    ) -> Dict[str, Any]:
        """
        分析算法结果，生成用户友好的自然语言描述
        
        Args:
            user_question: 用户原始问题
            algorithm_type: 算法类型
            algorithm_result: 算法原始返回结果
            original_data_count: 原始数据行数
            
        Returns:
            Dict[str, Any]: 包含 llm_analysis, technical_details, analysis_source 的结构化结果
        """
        if not self.enabled:
            logger.info("大模型分析功能已禁用，使用降级处理")
            return self._fallback_analysis(algorithm_type, algorithm_result, original_data_count)
        
        try:
            # 构建分析提示词
            prompt = self._build_analysis_prompt(
                user_question, algorithm_type, algorithm_result, original_data_count
            )
            
            # 调用大模型进行分析
            llm_analysis = await self._call_llm_analysis(prompt)
            
            if llm_analysis:
                return {
                    "llm_analysis": llm_analysis,
                    "technical_details": self._extract_technical_details(algorithm_type, algorithm_result),
                    "analysis_source": "llm_enhanced"
                }
            else:
                logger.warning("大模型分析返回空结果，使用降级处理")
                return self._fallback_analysis(algorithm_type, algorithm_result, original_data_count)
                
        except Exception as e:
            logger.error(f"大模型分析失败: {str(e)}")
            if self.fallback_enabled:
                logger.info("使用降级处理")
                return self._fallback_analysis(algorithm_type, algorithm_result, original_data_count)
            else:
                raise

    def _build_analysis_prompt(
        self,
        user_question: str,
        algorithm_type: str,
        algorithm_result: Dict[str, Any],
        original_data_count: int
    ) -> str:
        """构建大模型分析提示词"""
        
        # 算法类型中文映射
        algorithm_type_map = {
            "cluster": "聚类分析",
            "classify": "分类分析",
            "predict": "预测分析",
            "anomaly": "异常检测",
            "trend": "趋势分析",
            "associate": "关联分析",
            "compare": "对比分析",
            "similarity": "相似度分析",
            "profile": "画像分析",
            "causality": "因果分析",
            "alert": "预警分析",
            "recommend": "推荐分析"
        }
        
        algorithm_type_chinese = algorithm_type_map.get(algorithm_type, algorithm_type)
        
        # 简化结果数据（避免过长）
        result_summary = self._summarize_result(algorithm_result)
        
        prompt = f"""你是一个专业的数据分析师，请根据用户的问题和算法执行结果，生成一段用户友好的自然语言分析报告。

## 用户问题
{user_question}

## 算法类型
{algorithm_type_chinese}

## 算法执行结果
```json
{json.dumps(result_summary, indent=2, ensure_ascii=False)}
```

## 数据规模
分析了 {original_data_count} 条数据记录

## 要求
1. 用通俗易懂的语言解释算法结果
2. 突出关键发现和业务洞察
3. 提供实用的建议和下一步行动
4. 避免使用过于技术性的术语
5. 保持简洁，控制在300字以内

请直接输出分析报告，不要包含任何前缀或标题。"""
        
        return prompt
    
    def _summarize_result(self, algorithm_result: Dict[str, Any], max_items: int = 10) -> Dict[str, Any]:
        """简化算法结果，避免过长"""
        summary = {}
        
        for key, value in algorithm_result.items():
            if isinstance(value, list):
                if len(value) > max_items:
                    summary[key] = value[:max_items]
                    summary[f"{key}_total_count"] = len(value)
                    summary[f"{key}_note"] = f"仅显示前{max_items}条，共{len(value)}条"
                else:
                    summary[key] = value
            elif isinstance(value, dict):
                summary[key] = self._summarize_result(value, max_items)
            else:
                summary[key] = value
        
        return summary
    
    async def _call_llm_analysis(self, prompt: str) -> Optional[str]:
        """调用大模型进行分析"""
        if not self.llm_client:
            logger.warning("LLM 客户端不可用")
            return None
        
        try:
            # 调用 LLM - chat_completion 直接返回字符串
            # 注意：LLMClient 内部已有重试机制，这里不需要额外重试
            messages = [
                {"role": "system", "content": "你是一个专业的数据分析师，擅长将技术性的算法结果转换为用户友好的业务洞察。"},
                {"role": "user", "content": prompt}
            ]
            
            response = await self.llm_client.chat_completion(messages)
            
            # chat_completion 返回的是字符串，不是字典
            if response:
                return response
            else:
                logger.warning("LLM 分析返回空响应")
                return None
                
        except Exception as e:
            logger.error(f"LLM 分析调用失败: {str(e)}")
            return None
    
    def _extract_technical_details(self, algorithm_type: str, algorithm_result: Dict[str, Any]) -> Dict[str, Any]:
        """提取技术细节"""
        details = {
            "summary": f"算法执行完成",
            "status": algorithm_result.get("status", "unknown"),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # 根据算法类型提取特定指标
        if algorithm_type == "cluster":
            details["metrics"] = {
                "k_used": algorithm_result.get("k_used"),
                "cluster_count": len(set(
                    item.get("cluster_id") for item in algorithm_result.get("results", [])
                    if item.get("cluster_id") is not None
                ))
            }
        elif algorithm_type == "trend":
            results = algorithm_result.get("results", {})
            details["metrics"] = {
                "trend_direction": results.get("trend_direction"),
                "slope": results.get("slope"),
                "r_squared": results.get("r_squared")
            }
        elif algorithm_type == "predict":
            details["metrics"] = {
                "model_used": algorithm_result.get("metadata", {}).get("model_selected"),
                "forecast_periods": algorithm_result.get("metadata", {}).get("forecast_periods")
            }
        elif algorithm_type == "anomaly":
            results = algorithm_result.get("results", [])
            anomaly_count = sum(1 for item in results if item.get("cluster_id") == -1)
            details["metrics"] = {
                "total_points": len(results),
                "anomaly_count": anomaly_count,
                "anomaly_rate": round(anomaly_count / len(results) * 100, 2) if results else 0
            }
        
        # 保留原始数据的关键部分
        details["raw_data"] = {
            "status": algorithm_result.get("status"),
            "message": algorithm_result.get("message"),
            "result_keys": list(algorithm_result.keys())
        }
        
        return details

    def _fallback_analysis(
        self,
        algorithm_type: str,
        algorithm_result: Dict[str, Any],
        original_data_count: int
    ) -> Dict[str, Any]:
        """
        降级处理：当大模型分析失败时，生成基本的结果描述
        """
        # 算法类型中文映射
        algorithm_type_map = {
            "cluster": "聚类分析",
            "classify": "分类分析",
            "predict": "预测分析",
            "anomaly": "异常检测",
            "trend": "趋势分析",
            "associate": "关联分析",
            "compare": "对比分析",
            "similarity": "相似度分析",
            "profile": "画像分析",
            "causality": "因果分析",
            "alert": "预警分析",
            "recommend": "推荐分析"
        }
        
        algorithm_type_chinese = algorithm_type_map.get(algorithm_type, algorithm_type)
        status = algorithm_result.get("status", "unknown")
        
        # 根据算法类型生成基本描述
        if algorithm_type == "cluster":
            analysis = self._fallback_cluster_analysis(algorithm_result, original_data_count)
        elif algorithm_type == "trend":
            analysis = self._fallback_trend_analysis(algorithm_result, original_data_count)
        elif algorithm_type == "predict":
            analysis = self._fallback_predict_analysis(algorithm_result, original_data_count)
        elif algorithm_type == "anomaly":
            analysis = self._fallback_anomaly_analysis(algorithm_result, original_data_count)
        else:
            analysis = f"{algorithm_type_chinese}执行完成，共分析了{original_data_count}条数据。状态: {status}"
        
        return {
            "llm_analysis": analysis,
            "technical_details": self._extract_technical_details(algorithm_type, algorithm_result),
            "analysis_source": "fallback"
        }
    
    def _fallback_cluster_analysis(self, result: Dict[str, Any], data_count: int) -> str:
        """聚类分析降级描述"""
        k_used = result.get("k_used", "未知")
        results = result.get("results", [])
        
        if results:
            cluster_distribution = {}
            for item in results:
                cluster_id = item.get("cluster_id", "unknown")
                cluster_distribution[cluster_id] = cluster_distribution.get(cluster_id, 0) + 1
            
            cluster_desc = "、".join([f"第{k+1}组{v}个" for k, v in sorted(cluster_distribution.items()) if k != "unknown"])
            return f"聚类分析完成，将{data_count}条数据分成了{k_used}个组。分布情况：{cluster_desc}。"
        else:
            return f"聚类分析完成，共分析了{data_count}条数据，使用了{k_used}个聚类。"
    
    def _fallback_trend_analysis(self, result: Dict[str, Any], data_count: int) -> str:
        """趋势分析降级描述"""
        results = result.get("results", {})
        message = result.get("message", "")
        
        if isinstance(results, dict):
            trend_direction = results.get("trend_direction", "")
            slope = results.get("slope")
            
            direction_map = {"increasing": "上升", "decreasing": "下降", "stable": "稳定"}
            direction_chinese = direction_map.get(trend_direction, trend_direction)
            
            if direction_chinese:
                desc = f"趋势分析完成，在{data_count}个数据点中检测到{direction_chinese}趋势"
                if slope is not None:
                    desc += f"，斜率为{slope:.4f}"
                return desc + "。"
        
        return f"趋势分析完成。{message}" if message else f"趋势分析完成，共分析了{data_count}个数据点。"
    
    def _fallback_predict_analysis(self, result: Dict[str, Any], data_count: int) -> str:
        """预测分析降级描述"""
        success = result.get("success", False)
        metadata = result.get("metadata", {})
        model_used = metadata.get("model_selected", "自动选择")
        forecast_periods = metadata.get("forecast_periods", "未知")
        
        if success:
            return f"预测分析完成，基于{data_count}条历史数据，使用{model_used}模型预测了未来{forecast_periods}个周期的数据。"
        else:
            message = result.get("message", "未知错误")
            return f"预测分析执行失败：{message}"
    
    def _fallback_anomaly_analysis(self, result: Dict[str, Any], data_count: int) -> str:
        """异常检测降级描述"""
        results = result.get("results", [])
        
        if results:
            anomaly_count = sum(1 for item in results if item.get("cluster_id") == -1)
            normal_count = len(results) - anomaly_count
            anomaly_rate = round(anomaly_count / len(results) * 100, 1) if results else 0
            
            return f"异常检测完成，在{len(results)}个数据点中检测到{anomaly_count}个异常点（异常率{anomaly_rate}%），{normal_count}个正常点。"
        else:
            return f"异常检测完成，共分析了{data_count}条数据。"


# 全局结果分析器实例
_result_analyzer: Optional[AlgorithmResultAnalyzer] = None


def get_result_analyzer() -> AlgorithmResultAnalyzer:
    """获取结果分析器单例"""
    global _result_analyzer
    if _result_analyzer is None:
        _result_analyzer = AlgorithmResultAnalyzer()
    return _result_analyzer
