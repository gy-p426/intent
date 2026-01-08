"""
Association Analysis Algorithm Configuration

关联分析算法配置
"""

ASSOCIATION_CONFIG = {
    "name": "多元关联分析",
    "description": "分析变量之间的关联关系，支持二元、多变量两两、多变量综合三种分析模式",
    "algorithm_type": "associate",
    "data_format": "multi_columns",
    
    # 输入格式说明
    "input_format": {
        "data": {
            "type": "array",
            "description": "列数据数组，每个元素包含列名和数据值",
            "items": {
                "name": "string - 列名称",
                "values": "array - 列的值"
            },
            "example": [
                {"name": "age", "values": [25, 30, 35]},
                {"name": "salary", "values": [50000, 80000, 100000]},
                {"name": "education", "values": ["本科", "硕士", "博士"]}
            ]
        },
        "options": {
            "analysis_mode": "string - 分析模式: bivariate(二元) | pairwise(两两) | multivariate(综合)"
        }
    },
    
    # 必需参数(在data字段中)
    "required_parameters": [
        {
            "name": "data",
            "type": "array",
            "description": "列数据数组",
            "min_items": 2,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "列名称"},
                    "values": {"type": "array", "description": "列的值"}
                },
                "required": ["name", "values"]
            }
        }
    ],
    
    # 可选参数(在options字段中)
    "optional_parameters": [
        {
            "name": "analysis_mode",
            "type": "string",
            "description": "分析模式",
            "enum": ["bivariate", "pairwise", "multivariate"],
            "default": "auto",
            "notes": "如果不指定，系统会根据列数自动推断：2列→bivariate，≥3列→pairwise"
        }
    ],
    
    # 分析模式说明
    "analysis_modes": {
        "bivariate": {
            "name": "二元关联分析",
            "description": "分析两个变量之间的关联关系",
            "required_columns": 2,
            "methods": ["卡方检验", "相关性分析", "方差分析"],
            "use_cases": [
                "分析年龄和薪资的关系",
                "分析性别与产品偏好的关联"
            ]
        },
        "pairwise": {
            "name": "多变量两两关联分析",
            "description": "分析多个变量之间的两两关联关系，使用互信息方法",
            "min_columns": 3,
            "methods": ["互信息(MI)"],
            "use_cases": [
                "分析年龄、学历、工作年限之间的两两关联",
                "找出多个因素中哪些相互关联"
            ]
        },
        "multivariate": {
            "name": "多变量综合关联分析",
            "description": "分析多个自变量与一个因变量的综合关联关系，第一列为因变量",
            "min_columns": 3,
            "methods": ["条件互信息(CMI)", "回归分析"],
            "use_cases": [
                "分析哪些因素影响薪资（薪资为因变量）",
                "分析多个自变量对因变量的综合影响"
            ]
        }
    },
    
    # 数据要求
    "data_requirements": {
        "min_rows": 2,
        "min_columns": 2,
        "max_columns": None,
        "numeric_features_required": False,
        "same_length_required": True,
        "mode_specific": {
            "bivariate": {"exact_columns": 2},
            "pairwise": {"min_columns": 3},
            "multivariate": {"min_columns": 3}
        }
    },
    
    # 使用示例
    "examples": [
        # 二元分析示例
        "分析教育水平与薪资的关系",
        "分析性别与产品偏好的关联",
        "分析工作年限与收入的相关性",
        "分析年龄与工作满意度的关系",
        # 多元分析示例
        "分析年龄、学历、工作年限之间的关联关系",
        "分析哪些因素影响员工薪资",
        "找出影响销售额的关键因素",
        "分析多个变量对客户满意度的影响"
    ],
    
    # 预处理选项
    "preprocessing_options": {
        "handle_missing": True,
        "auto_detect_type": False,  # 数据类型检测由算法服务负责
        "remove_null_pairs": True
    },
    
    # 分析方法说明（二元分析）
    "methods": {
        "chi_square": {
            "name": "卡方检验",
            "condition": "两个都是分类变量",
            "statistic": "Chi-Square",
            "effect_size": "Cramér's V",
            "mode": "bivariate"
        },
        "correlation": {
            "name": "相关性分析",
            "condition": "两个都是数值变量",
            "statistic": "Pearson r",
            "effect_size": "Pearson r / R²",
            "mode": "bivariate"
        },
        "anova": {
            "name": "方差分析",
            "condition": "一个分类变量 + 一个数值变量",
            "statistic": "F-statistic",
            "effect_size": "Eta²",
            "mode": "bivariate"
        },
        "mutual_information": {
            "name": "互信息",
            "condition": "多个变量两两分析",
            "statistic": "MI值",
            "effect_size": "归一化MI",
            "mode": "pairwise"
        },
        "cmi_regression": {
            "name": "条件互信息+回归",
            "condition": "多个自变量与一个因变量",
            "statistic": "CMI值 + 回归系数",
            "effect_size": "R² / 调整R²",
            "mode": "multivariate"
        }
    },
    
    # 向后兼容性说明
    "backward_compatibility": {
        "old_format_supported": True,
        "old_format": {
            "data": {
                "column1": {"name": "string", "values": "array"},
                "column2": {"name": "string", "values": "array"}
            }
        },
        "conversion_note": "旧格式会自动转换为新格式的data数组"
    }
}

# 响应参数定义（算法服务返回的格式，中文字段，嵌套结构）
ASSOCIATION_RESULT = {
    "解释": {
        "type": "string",
        "description": "结果解释（通俗易懂的中文）",
        "examples": {
            # 二元分析示例
            "相关性分析（正相关）": "age 和 salary 之间呈正相关，即age越大，salary也越大",
            "相关性分析（负相关）": "age 和 job_satisfaction_score 之间呈负相关，即age越大，job_satisfaction_score越小",
            "相关性分析（不显著）": "age 和 salary 之间相关性不明显，可能没有线性关系",
            "卡方检验（显著）": "gender 和 product 之间有关系，关系很强",
            "卡方检验（不显著）": "gender 和 product 之间关系不明显，可能是独立的",
            "方差分析（显著）": "不同education的salary有差异，差异很大，其中MS的salary最高，HS的最低",
            "方差分析（不显著）": "不同education的salary差异不明显，可能差不多",
            # 多元分析示例
            "两两关联分析": "在age、education、experience三个变量中，education和experience关联最强，age和education关联较弱",
            "综合关联分析": "salary主要受education和experience影响，其中education的影响最大"
        }
    },
    "算法结果": {
        "type": "object",
        "description": "算法结果详情",
        "properties": {
            "方法": {
                "type": "string",
                "enum": ["卡方检验", "相关性分析", "方差分析", "互信息", "条件互信息+回归"],
                "description": "使用的分析方法",
                "example": "互信息"
            },
            "使用模式": {
                "type": "string",
                "enum": ["bivariate", "pairwise", "multivariate"],
                "description": "分析模式",
                "example": "pairwise"
            },
            "结论摘要": {
                "type": "object",
                "description": "分析结论摘要",
                "properties": {
                    "存在依赖的变量对": {
                        "type": "array",
                        "description": "存在显著依赖关系的变量对",
                        "items": {"type": "string"},
                        "example": ["education-salary", "experience-salary"]
                    },
                    "不存在显著依赖的变量对": {
                        "type": "array",
                        "description": "不存在显著依赖关系的变量对",
                        "items": {"type": "string"},
                        "example": ["age-gender"]
                    }
                }
            },
            "显著性": {
                "type": "object",
                "description": "显著性判定信息",
                "properties": {
                    "判定方式": {
                        "type": "string",
                        "description": "显著性判定方式",
                        "example": "基于P值阈值"
                    },
                    "阈值": {
                        "type": "float",
                        "description": "显著性阈值",
                        "example": 0.05
                    }
                }
            },
            "算法细节": {
                "type": "object",
                "description": "不同算法的特定输出详情",
                "oneOf": [
                    {
                        "description": "二元分析详情（保持向后兼容）",
                        "properties": {
                            "第一列": {"type": "string"},
                            "第二列": {"type": "string"},
                            "分析方法": {"type": "string"},
                            "统计量": {"type": "string"},
                            "P值": {"type": "float"},
                            "效应量": {"type": "string"},
                            "是否显著": {"type": "boolean"},
                            "显著性水平": {"type": "float"},
                            "详细信息": {"type": "object"}
                        }
                    },
                    {
                        "description": "两两关联分析详情",
                        "properties": {
                            "互信息矩阵": {"type": "object"},
                            "变量对列表": {"type": "array"},
                            "热力图数据": {"type": "object"}
                        }
                    },
                    {
                        "description": "综合关联分析详情",
                        "properties": {
                            "因变量": {"type": "string"},
                            "自变量": {"type": "array"},
                            "CMI值": {"type": "object"},
                            "回归结果": {"type": "object"}
                        }
                    }
                ]
            }
        }
    }
}
