"""
@Author      : Surface
@Date        : 2025/12/24
@Description : FP-Growth关联分析算法配置
"""

"""
FP-Growth Algorithm Configuration

FP-Growth频繁模式增长关联分析算法配置
"""

FPGROWTH_CONFIG = {
    "name": "FP-Growth关联分析",
    "description": "FP-Growth(频繁模式增长)算法,用于发现数据中的频繁模式和关联规则",
    "algorithm_type": "association",
    "data_format": "tabular",
    
    # 必需参数
    "required_parameters": [
        {
            "name": "group_id_column",
            "type": "string",
            "description": "分组ID列名,用于标识每个分组"
        },
        {
            "name": "element_column",
            "type": "string",
            "description": "元素列名,表示分组中包含的元素"
        }
    ],
    
    # 可选参数
    "optional_parameters": [
        {
            "name": "min_support",
            "type": "float",
            "description": "最小支持度阈值(0-1之间),元素集至少需要在这个比例的分组中出现",
            "default": 0.01,
            "min_value": 0.0,
            "max_value": 1.0
        },
        {
            "name": "min_confidence",
            "type": "float",
            "description": "最小置信度阈值(0-1之间),用于生成关联规则",
            "default": 0.5,
            "min_value": 0.0,
            "max_value": 1.0
        },
        {
            "name": "max_length",
            "type": "integer",
            "description": "频繁元素集的最大长度限制",
            "default": None,
            "min_value": 1
        },
        {
            "name": "metric",
            "type": "string",
            "description": "规则评估指标：confidence(置信度), lift(提升度), leverage(杠杆率), conviction(确信度)",
            "default": "confidence",
            "options": ["confidence", "lift", "leverage", "conviction"]
        },
        {
            "name": "min_lift",
            "type": "float",
            "description": "最小提升度阈值(仅当metric为lift时使用)",
            "default": 1.0,
            "min_value": 0.0
        }
    ],
    
    # 数据要求
    "data_requirements": {
        "min_groups": 10,
        "min_unique_elements": 2,
        "data_format": "每行一个分组-元素对,或每行一个分组包含多个元素"
    },
    
    # 使用示例
    "examples": [
        "发现超市购物篮中的商品关联规则(分组=订单,元素=商品)",
        "分析网站用户浏览行为模式(分组=会话,元素=页面)",
        "挖掘电商平台的商品推荐规则(分组=用户,元素=商品)",
        "识别医疗诊断中的症状关联模式(分组=患者,元素=症状)",
        "发现学生选课中的课程组合模式(分组=学生,元素=课程)",
        "分析基因组数据中的基因共现模式(分组=样本,元素=基因)",
        "挖掘社交网络中的标签关联(分组=用户,元素=标签)"
    ],
    
    # 预处理选项
    "preprocessing_options": {
        "handle_missing": True,
        "remove_duplicates": True,
        "case_sensitive": False,  # 元素名称是否区分大小写
        "min_group_length": 1  # 最小分组长度(包含的元素数)
    }
}

# FP-Growth算法响应参数
FPGROWTH_RESULT = {
    "frequent_itemsets": {
        "type": "array",
        "description": "频繁元素集列表",
        "items": {
            "type": "object",
            "properties": {
                "itemset": {
                    "type": "array",
                    "description": "元素集中的元素列表",
                    "example": ["元素A", "元素B"]
                },
                "support": {
                    "type": "float",
                    "description": "支持度(0-1之间),表示该元素集在所有分组中出现的比例"
                },
                "count": {
                    "type": "integer",
                    "description": "该元素集出现的分组次数"
                },
                "length": {
                    "type": "integer",
                    "description": "元素集包含的元素数量"
                }
            }
        }
    },
    "association_rules": {
        "type": "array",
        "description": "关联规则列表",
        "items": {
            "type": "object",
            "properties": {
                "antecedent": {
                    "type": "array",
                    "description": "规则前件(条件部分)"
                },
                "consequent": {
                    "type": "array",
                    "description": "规则后件(结果部分)"
                },
                "support": {
                    "type": "float",
                    "description": "规则的支持度"
                },
                "confidence": {
                    "type": "float",
                    "description": "规则的置信度,P(后件|前件)"
                },
                "lift": {
                    "type": "float",
                    "description": "规则的提升度,confidence/P(后件)"
                },
                "leverage": {
                    "type": "float",
                    "description": "规则的杠杆率,support(规则) - support(前件)*support(后件)"
                },
                "conviction": {
                    "type": "float",
                    "description": "规则的确信度,[1-support(后件)]/[1-confidence]"
                }
            }
        }
    },
    "statistics": {
        "type": "object",
        "description": "统计信息",
        "properties": {
            "total_groups": {
                "type": "integer",
                "description": "总分组数"
            },
            "total_unique_elements": {
                "type": "integer",
                "description": "唯一元素总数"
            },
            "frequent_itemsets_count": {
                "type": "integer",
                "description": "频繁元素集数量"
            },
            "association_rules_count": {
                "type": "integer",
                "description": "关联规则数量"
            },
            "avg_group_length": {
                "type": "float",
                "description": "平均分组长度"
            },
            "max_itemset_length": {
                "type": "integer",
                "description": "最大元素集长度"
            }
        }
    },
    "top_itemsets": {
        "type": "array",
        "description": "支持度最高的前N个元素集",
        "items": {
            "type": "object",
            "properties": {
                "itemset": {"type": "array"},
                "support": {"type": "float"},
                "count": {"type": "integer"}
            }
        }
    },
    "top_rules": {
        "type": "array",
        "description": "按指定指标排序的前N条规则",
        "items": {
            "type": "object",
            "properties": {
                "rule": {"type": "string", "description": "规则描述"},
                "antecedent": {"type": "array"},
                "consequent": {"type": "array"},
                "confidence": {"type": "float"},
                "lift": {"type": "float"}
            }
        }
    },
    "visualization_data": {
        "type": "object",
        "description": "用于可视化的数据",
        "properties": {
            "itemsets_by_length": {
                "type": "object",
                "description": "按长度分组的频繁元素集统计"
            },
            "support_distribution": {
                "type": "array",
                "description": "支持度分布数据"
            },
            "confidence_distribution": {
                "type": "array",
                "description": "置信度分布数据"
            },
            "lift_distribution": {
                "type": "array",
                "description": "提升度分布数据"
            }
        }
    }
}
