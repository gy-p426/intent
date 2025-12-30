"""
字段名映射工具模块

将 API 返回数据的英文字段名转换为中文字段名，提高非技术用户的可读性。
"""

from typing import Any, Dict, List, Optional, Union
import logging

logger = logging.getLogger(__name__)


class FieldMapper:
    """字段名映射工具类"""
    
    # 通用字段映射
    COMMON_MAPPING: Dict[str, str] = {
        "success": "是否成功",
        "message": "消息",
        "timestamp": "时间戳",
        "value": "数值",
        "data_points": "数据点数",
        "mean": "均值",
        "std": "标准差",
        "min": "最小值",
        "max": "最大值",
        "start": "开始时间",
        "end": "结束时间",
        "error": "错误信息",
        "error_details": "错误详情",
    }
    
    # 趋势分析专用映射
    TREND_MAPPING: Dict[str, str] = {
        "data_characteristics": "数据特征",
        "outlier_count": "异常值数量",
        "outlier_ratio": "异常值比例",
        "is_normal": "是否正态分布",
        "has_seasonality": "是否有季节性",
        "decomposition": "分解结果",
        "trend": "趋势分量",
        "seasonal": "季节性分量",
        "residual": "残差分量",
        "analysis_metrics": "分析指标",
        "trend_strength": "趋势强度",
        "seasonal_strength": "季节性强度",
        "residual_variance": "残差方差",
        "algorithm": "算法",
        "period_used": "使用周期",
        "analysis_type": "分析类型",
        "algorithm_used": "使用算法",
        "detection": "检测结果",
        "trend_direction": "趋势方向",
        "sen_slope": "Sen斜率",
        "slope": "斜率",
        "intercept": "截距",
        "p_value": "p值",
        "z_statistic": "Z统计量",
        "s_statistic": "S统计量",
        "r_squared": "R平方值",
        "std_error": "标准误差",
        "confidence_interval": "置信区间",
        "statistical_significance": "统计显著性",
        "confidence_level": "置信水平",
        "method": "检测方法",
        "sample_size": "样本量",
        "interpretation": "结果解释",
        "method_used": "使用方法",
    }

    # 预测专用映射
    FORECAST_MAPPING: Dict[str, str] = {
        "results": "预测结果",
        "forecast": "预测值",
        "timestamps": "时间点",
        "confidence_lower": "置信下限",
        "confidence_upper": "置信上限",
        "training_data_points": "训练数据点数",
        "forecast_horizon": "预测步数",
        "training_date_range": "训练数据范围",
        "model_used": "使用模型",
        "data_analysis": "数据分析",
        "missing_ratio": "缺失比例",
        "horizon": "预测期数",
        "model_id": "模型ID",
        "model_name": "模型名称",
        "model_version": "模型版本",
        "target_stats": "目标变量统计",
        "feature_count": "特征数量",
        "missing_values": "缺失值数量",
        "metrics": "评估指标",
        "rmse": "均方根误差",
        "mae": "平均绝对误差",
        "r2": "决定系数",
        "reused_model": "是否复用模型",
    }
    
    # readable_summary 摘要字段映射
    READABLE_SUMMARY_MAPPING: Dict[str, str] = {
        "title": "标题",
        "key_findings": "关键发现",
        "explanation": "详细解释",
        "recommendations": "建议",
        "readable_summary": "通俗摘要",
    }
    
    @classmethod
    def get_combined_mapping(cls, mapping_type: Optional[str] = None) -> Dict[str, str]:
        """
        获取合并后的字段映射字典
        
        Args:
            mapping_type: 映射类型，可选值：
                - "trend": 趋势分析（通用 + 趋势 + 摘要）
                - "forecast": 预测（通用 + 预测 + 摘要）
                - "all": 所有映射
                - None: 所有映射（默认）
        
        Returns:
            合并后的映射字典
        """
        combined = {}
        combined.update(cls.COMMON_MAPPING)
        combined.update(cls.READABLE_SUMMARY_MAPPING)
        
        if mapping_type == "trend":
            combined.update(cls.TREND_MAPPING)
        elif mapping_type == "forecast":
            combined.update(cls.FORECAST_MAPPING)
        else:  # "all" or None
            combined.update(cls.TREND_MAPPING)
            combined.update(cls.FORECAST_MAPPING)
        
        return combined

    @classmethod
    def convert_keys_recursive(cls, data: Any, mapping: Dict[str, str]) -> Any:
        """
        递归转换所有键名
        
        Args:
            data: 要转换的数据，可以是字典、列表或其他类型
            mapping: 字段映射字典
        
        Returns:
            转换后的数据
        """
        if data is None:
            return None
        
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                # 转换键名
                new_key = mapping.get(key, key)
                if new_key == key and key not in mapping:
                    # 未找到映射，记录警告日志
                    logger.debug(f"未找到字段映射: {key}")
                # 递归转换值
                result[new_key] = cls.convert_keys_recursive(value, mapping)
            return result
        
        elif isinstance(data, list):
            return [cls.convert_keys_recursive(item, mapping) for item in data]
        
        else:
            # 其他类型（字符串、数字、布尔值等）直接返回
            return data
    
    @classmethod
    def convert_to_chinese(
        cls, 
        data: Dict[str, Any], 
        mapping_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        将字典的英文键名转换为中文
        
        Args:
            data: 要转换的字典数据
            mapping_type: 映射类型，可选值：
                - "trend": 趋势分析
                - "forecast": 预测
                - "all": 所有映射（默认）
        
        Returns:
            转换后的字典
        """
        if not data:
            return data
        
        mapping = cls.get_combined_mapping(mapping_type)
        return cls.convert_keys_recursive(data, mapping)
    
    @classmethod
    def get_english_to_chinese_table(cls) -> Dict[str, str]:
        """
        获取完整的英文到中文映射表（用于文档参考）
        
        Returns:
            完整的映射字典
        """
        return cls.get_combined_mapping("all")
