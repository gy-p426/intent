"""
@Author      : Surface
@Date        : 2025/12/24 20:40 
@Description : DTW(动态时间规整)算法配置
"""

"""
DTW Algorithm Configuration

DTW相似度分析算法配置
"""

DTW_CONFIG = {
    "name": "DTW相似度分析",
    "description": "动态时间规整(DTW)算法，用于计算两个数值序列（数组）之间的相似度",
    "algorithm_type": "similarity",
    "data_format": "tabular",
    
    # 必需参数
    "required_parameters": [
        {
            "name": "time_column",  
            "type": "string",
            "description": "时间列名，用于数据排序",
        },
        {
            "name": "time_series1",  
            "type": "string",
            "description": "第一个数值序列的列名",
        },
        {
            "name": "time_series2",
            "type": "string",
            "description": "第二个数值序列的列名",
        }
    ],

    
    # 可选参数
    "optional_parameters": [
        {
            "name": "window_size",
            "type": "integer",
            "description": "Sakoe-Chiba带约束窗口大小,限制路径搜索范围",
            "default": None,
            "min_value": 1
        },
        {
            "name": "distance_metric",
            "type": "string",
            "description": "距离度量方法:euclidean(欧氏), manhattan(曼哈顿), cosine(余弦)",
            "default": "euclidean",
            "options": ["euclidean", "manhattan", "cosine"]
        },
        {
            "name": "normalize",
            "type": "boolean",
            "description": "是否对序列进行归一化处理",
            "default": True
        },
        {
            "name": "step_pattern",
            "type": "string",
            "description": "步进模式:symmetric1, symmetric2, asymmetric",
            "default": "symmetric2",
            "options": ["symmetric1", "symmetric2", "asymmetric"]
        }
    ],
    
    # 数据要求
    "data_requirements": {
        "min_sequence_length": 2,
        "numeric_values_required": True,
        "equal_length_required": False  # DTW支持不等长序列
    },
    
    # 使用示例
    "examples": [
        "比较两个温度传感器的读数序列相似度",
        "分析实际销量序列和预测销量序列的匹配程度",
        "对比两台设备的功率消耗曲线",
        "识别两个股票价格走势的相似性"
    ],
    
    # 预处理选项
    "preprocessing_options": {
        "handle_missing": True,
        "normalize_features": True,
        "remove_outliers": False,
        "interpolation": True
    }
}

# DTW算法响应参数
DTW_RESULT = {
    "dtw_distance": {
        "type": "float",
        "description": "DTW距离值(距离越小表示两个序列越相似)"
    },
    "normalized_distance": {
        "type": "float",
        "description": "归一化的DTW距离(0-1之间)"
    },
    "similarity_score": {
        "type": "float",
        "description": "相似度分数(0-1之间,1表示完全相似)"
    },
    "warping_path": {
        "type": "array",
        "description": "最优对齐路径，[[i1, j1], [i2, j2], ...]显示两个序列如何匹配",
        "example": "[[0, 0], [1, 1], [1, 2], [2, 3], ...]"
    },
    "cost_matrix": {
        "type": "array",
        "description": "累积代价矩阵,shape为(len(sequence_a), len(sequence_b))"
    },
    "aligned_sequences": {
        "type": "object",
        "description": "对齐后的序列数据",
        "properties": {
            "time_series1_aligned": {
                "type": "array",
                "description": "按对齐路径重排的序列1"
            },
            "time_series2_aligned": {
                "type": "array",
                "description": "按对齐路径重排的序列2"
            }
        }
    },
    "visualization_data": {
        "type": "object",
        "description": "用于可视化的数据",
        "properties": {
            "time_series1": {"type": "array", "description": "原始序列1"},
            "time_series2": {"type": "array", "description": "原始序列2"},
            "warping_path": {"type": "array", "description": "对齐路径"},
            "cost_matrix": {"type": "array", "description": "代价矩阵"}
        }
    },
    "statistics": {
        "type": "object",
        "description": "统计信息",
        "properties": {
            "time_series1_length": {"type": "integer", "description": "序列1长度"},
            "time_series2_length": {"type": "integer", "description": "序列2长度"},
            "path_length": {"type": "integer", "description": "对齐路径长度"},
            "average_distance": {"type": "float", "description": "平均逐点距离"},
            "min_distance": {"type": "float", "description": "最小逐点距离"},
            "max_distance": {"type": "float", "description": "最大逐点距离"}
        }
    }
}

