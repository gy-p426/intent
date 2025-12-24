"""
Template Algorithm Configuration

新算法配置模板 - 请根据你的算法需求修改
"""

TEMPLATE_CONFIG = {
    # TODO: 修改为你的算法信息
    "name": "模板算法",
    "description": "这是一个算法开发模板，请修改为你的算法描述",
    "algorithm_type": "cluster",  # 修改为你的算法类型
    "data_format": "tabular",     # 修改为你的数据格式要求
    
    # TODO: 定义你的算法必需参数
    "required_parameters": [
        {
            "name": "param1",
            "type": "string",
            "description": "参数1的描述"
        },
        {
            "name": "param2",
            "type": "array",
            "description": "参数2的描述"
        }
    ],
    
    # TODO: 定义你的算法可选参数
    "optional_parameters": [
        {
            "name": "param3",
            "type": "integer",
            "description": "参数3的描述",
            "default": None,
            "min_value": 1
        }
    ],
    
    # TODO: 定义你的算法数据要求
    "data_requirements": {
        "min_rows": 2,
        "min_features": 1,
        "numeric_features_required": True  # 根据需要修改
    },
    
    # TODO: 添加你的算法使用示例
    "examples": [
        "算法使用示例1",
        "算法使用示例2",
        "算法使用示例3"
    ],
    
    # TODO: 定义你的算法预处理选项
    "preprocessing_options": {
        "handle_missing": True,
        "normalize_features": False,
        "remove_outliers": False
    }
}

# TODO:自己写一下响应参数，方便我后续针对每个算法开发接收的参数
TEMPLATE_RESULT = {

}