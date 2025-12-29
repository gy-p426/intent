"""
Association Analysis Algorithm Configuration

关联分析算法配置
"""

ASSOCIATION_CONFIG = {
    "name": "关联分析",
    "description": "分析两个变量之间的关联关系,自动选择合适的统计方法(卡方检验/相关性分析/方差分析)",
    "algorithm_type": "associate",
    "data_format": "two_columns",
    
    # 输入格式说明
    "input_format": {
        "data": {
            "column1": {
                "name": "string - 第一列名称",
                "values": "array - 第一列的值"
            },
            "column2": {
                "name": "string - 第二列名称",
                "values": "array - 第二列的值"
            }
        },
        "options": {
            "significance_level": "float - 显著性水平(默认0.05,范围0.001-0.5)"
        }
    },
    
    # 必需参数(在data字段中)
    "required_parameters": [
        {
            "name": "column1",
            "type": "object",
            "description": "第一列数据",
            "properties": {
                "name": {"type": "string", "description": "列名称"},
                "values": {"type": "array", "description": "列的值"}
            }
        },
        {
            "name": "column2",
            "type": "object",
            "description": "第二列数据",
            "properties": {
                "name": {"type": "string", "description": "列名称"},
                "values": {"type": "array", "description": "列的值"}
            }
        }
    ],
    
    # 可选参数(在options字段中)
    "optional_parameters": [
        {
            "name": "significance_level",
            "type": "float",
            "description": "显著性水平(alpha值)",
            "default": 0.05,
            "min_value": 0.001,
            "max_value": 0.5
        }
    ],
    
    # 数据要求
    "data_requirements": {
        "min_rows": 2,
        "min_features": 2,
        "numeric_features_required": False,
        "same_length_required": True
    },
    
    # 使用示例
    "examples": [
        "分析教育水平与薪资的关系",
        "分析性别与产品偏好的关联",
        "分析工作年限与收入的相关性",
        "分析年龄与工作满意度的关系"
    ],
    
    # 预处理选项
    "preprocessing_options": {
        "handle_missing": True,
        "auto_detect_type": True,
        "remove_null_pairs": True
    },
    
    # 分析方法说明
    "methods": {
        "chi_square": {
            "name": "卡方检验",
            "condition": "两个都是分类变量",
            "statistic": "Chi-Square",
            "effect_size": "Cramér's V"
        },
        "correlation": {
            "name": "相关性分析",
            "condition": "两个都是数值变量",
            "statistic": "Pearson r",
            "effect_size": "Pearson r / R²"
        },
        "anova": {
            "name": "方差分析",
            "condition": "一个分类变量 + 一个数值变量",
            "statistic": "F-statistic",
            "effect_size": "Eta²"
        }
    }
}

# 🔥 修改：响应参数定义（analyzer.py返回的格式,不包含status）
ASSOCIATION_RESULT = {
    "column1_name": {
        "type": "string",
        "description": "第一列名称",
        "example": "education_level"
    },
    "column2_name": {
        "type": "string",
        "description": "第二列名称",
        "example": "annual_salary"
    },
    "column1_type": {
        "type": "string",
        "enum": ["numerical", "categorical"],
        "description": "第一列数据类型",
        "example": "categorical"
    },
    "column2_type": {
        "type": "string",
        "enum": ["numerical", "categorical"],
        "description": "第二列数据类型",
        "example": "numerical"
    },
    "method_used": {
        "type": "string",
        "enum": ["chi_square", "correlation", "anova"],
        "description": "使用的分析方法",
        "example": "anova"
    },
    "statistic_name": {
        "type": "string",
        "description": "统计量名称",
        "example": "F-statistic"
    },
    "statistic_value": {
        "type": "float",
        "description": "统计量的值",
        "example": 4271.02
    },
    "p_value": {
        "type": "float",
        "description": "P值（显著性概率）",
        "example": 2.75e-95
    },
    "effect_size": {
        "type": "float",
        "description": "效应量",
        "example": 0.989
    },
    "effect_size_name": {
        "type": "string",
        "description": "效应量名称",
        "example": "Eta²"
    },
    "significant": {
        "type": "boolean",
        "description": "是否显著",
        "example": True
    },
    "significance_level_used": {
        "type": "float",
        "description": "使用的显著性水平",
        "example": 0.05
    },
    "interpretation": {
        "type": "string",
        "description": "结果解释（中文）",
        "example": "education_level 的不同水平在 annual_salary 上存在显著差异（大效应,F=4271.0169,p<0.001,α=0.05）"
    },
    "details": {
        "type": "object",
        "description": "详细统计信息（根据方法不同而不同）",
        "properties": {
            # 卡方检验的details
            "chi_square": {"type": "float", "description": "卡方统计量"},
            "p_value": {"type": "float", "description": "P值"},
            "degrees_of_freedom": {"type": "integer", "description": "自由度"},
            "cramers_v": {"type": "float", "description": "Cramér's V效应量"},
            "contingency_table": {"type": "object", "description": "列联表"},
            "sample_size": {"type": "integer", "description": "样本数"},
            "strength": {"type": "string", "description": "效应强度"},
            
            # 相关性分析的details
            "pearson_r": {"type": "float", "description": "Pearson相关系数"},
            "pearson_p": {"type": "float", "description": "Pearson P值"},
            "spearman_r": {"type": "float", "description": "Spearman相关系数"},
            "spearman_p": {"type": "float", "description": "Spearman P值"},
            "r_squared": {"type": "float", "description": "决定系数R²"},
            "direction": {"type": "string", "description": "相关方向"},
            
            # ANOVA的details
            "f_statistic": {"type": "float", "description": "F统计量"},
            "eta_squared": {"type": "float", "description": "Eta²效应量"},
            "num_groups": {"type": "integer", "description": "组数"},
            "group_statistics": {
                "type": "array",
                "description": "各组统计信息",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "description": "类别名"},
                        "mean": {"type": "float", "description": "均值"},
                        "std": {"type": "float", "description": "标准差"},
                        "count": {"type": "integer", "description": "样本数"}
                    }
                }
            },
            "effect_strength": {"type": "string", "description": "效应强度"}
        }
    }
}
