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

# 🔥 修改：响应参数定义（analyzer.py返回的格式，中文字段）
ASSOCIATION_RESULT = {
    "第一列": {
        "type": "string",
        "description": "第一列：列名(类型)",
        "example": "education_level(分类型)"
    },
    "第二列": {
        "type": "string",
        "description": "第二列：列名(类型)",
        "example": "annual_salary(数值型)"
    },
    "分析方法": {
        "type": "string",
        "enum": ["卡方检验", "相关性分析", "方差分析"],
        "description": "使用的分析方法",
        "example": "方差分析"
    },
    "统计量": {
        "type": "string",
        "description": "统计量：名称=值",
        "example": "F-statistic=4271.0169"
    },
    "P值": {
        "type": "float",
        "description": "P值（显著性概率）",
        "example": 2.75e-95
    },
    "效应量": {
        "type": "string",
        "description": "效应量：名称=值",
        "example": "Eta²=0.9890"
    },
    "是否显著": {
        "type": "boolean",
        "description": "是否显著",
        "example": True
    },
    "显著性水平": {
        "type": "float",
        "description": "使用的显著性水平",
        "example": 0.05
    },
    "结果解释": {
        "type": "string",
        "description": "结果解释（中文）",
        "example": "education_level 的不同水平在 annual_salary 上存在显著差异（大效应，F=4271.0169，p<0.001，α=0.05）"
    },
    "详细信息": {
        "type": "object",
        "description": "详细统计信息（所有字段均为中文，根据方法不同而不同）",
        "properties": {
            # 卡方检验的details
            "卡方统计量": {"type": "float", "description": "卡方统计量"},
            "P值": {"type": "float", "description": "P值"},
            "自由度": {"type": "integer", "description": "自由度"},
            "Cramér's V": {"type": "float", "description": "Cramér's V效应量"},
            "列联表": {"type": "object", "description": "列联表"},
            "样本数": {"type": "integer", "description": "样本数"},
            "效应强度": {"type": "string", "description": "效应强度"},
            
            # 相关性分析的details
            "Pearson相关系数": {"type": "float", "description": "Pearson相关系数"},
            "Pearson P值": {"type": "float", "description": "Pearson P值"},
            "Spearman相关系数": {"type": "float", "description": "Spearman相关系数"},
            "Spearman P值": {"type": "float", "description": "Spearman P值"},
            "决定系数R²": {"type": "float", "description": "决定系数R²"},
            "相关方向": {"type": "string", "description": "相关方向"},
            "相关强度": {"type": "string", "description": "相关强度"},
            
            # ANOVA的details
            "F统计量": {"type": "float", "description": "F统计量"},
            "Eta²效应量": {"type": "float", "description": "Eta²效应量"},
            "分组数": {"type": "integer", "description": "组数"},
            "各组统计": {
                "type": "array",
                "description": "各组统计信息",
                "items": {
                    "type": "object",
                    "properties": {
                        "类别": {"type": "string", "description": "类别名"},
                        "均值": {"type": "float", "description": "均值"},
                        "标准差": {"type": "float", "description": "标准差"},
                        "样本数": {"type": "integer", "description": "样本数"}
                    }
                }
            }
        }
    }
}
