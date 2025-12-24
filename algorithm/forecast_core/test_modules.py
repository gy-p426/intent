# forecast_modules/test_modules.py
"""
迁移包功能测试脚本
验证所有模块是否可以正常导入和使用
"""
import sys
import os
from datetime import datetime, timedelta

# 添加父目录到路径，以便导入 forecast_modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


def test_imports():
    """测试模块导入"""
    print("=" * 60)
    print("测试模块导入")
    print("=" * 60)
    
    errors = []
    
    # 测试主包导入
    try:
        import forecast_modules
        print(f"✓ forecast_modules 版本: {forecast_modules.__version__}")
    except Exception as e:
        errors.append(f"forecast_modules: {e}")
        print(f"✗ forecast_modules 导入失败: {e}")
    
    # 测试趋势分析模块
    try:
        from forecast_modules.trend_analysis import router as trend_router
        from forecast_modules.trend_analysis import TrendService
        print("✓ trend_analysis 模块导入成功")
    except Exception as e:
        errors.append(f"trend_analysis: {e}")
        print(f"✗ trend_analysis 导入失败: {e}")
    
    # 测试单变量预测模块
    try:
        from forecast_modules.auto_univariate_forecast import router as forecast_router
        from forecast_modules.auto_univariate_forecast import AutoUnivariatePredictor
        print("✓ auto_univariate_forecast 模块导入成功")
    except Exception as e:
        errors.append(f"auto_univariate_forecast: {e}")
        print(f"✗ auto_univariate_forecast 导入失败: {e}")
    
    # 测试多变量预测模块
    try:
        from forecast_modules.multivariate_forecast import router as multivariate_router
        from forecast_modules.multivariate_forecast import MultivariatePredictor
        print("✓ multivariate_forecast 模块导入成功")
    except Exception as e:
        errors.append(f"multivariate_forecast: {e}")
        print(f"✗ multivariate_forecast 导入失败: {e}")
    
    return len(errors) == 0, errors


def test_trend_analysis():
    """测试趋势分析功能"""
    print("\n" + "=" * 60)
    print("测试趋势分析功能")
    print("=" * 60)
    
    try:
        from forecast_modules.trend_analysis import TrendService
        import numpy as np
        
        # 生成测试数据
        np.random.seed(42)
        n = 100
        trend = np.linspace(0, 10, n)
        seasonal = 5 * np.sin(2 * np.pi * np.arange(n) / 24)
        noise = np.random.normal(0, 1, n)
        values = trend + seasonal + noise + 50
        
        timestamps = [
            (datetime.now() - timedelta(hours=n-i)).strftime("%Y-%m-%d %H:%M")
            for i in range(n)
        ]
        
        data = [{"timestamp": t, "value": v} for t, v in zip(timestamps, values)]
        
        # 测试趋势分解（使用正确的方法名）
        service = TrendService()
        series = service.prepare_data(data)
        result = service.decompose_trend_stl(series, period=24)
        
        if result and "trend" in result:
            print(f"✓ 趋势分解成功，趋势点数: {len(result['trend'])}")
        else:
            print("✗ 趋势分解失败")
            return False
        
        # 测试趋势检测（使用正确的方法名）
        detection = service.detect_trend_mann_kendall(series)
        
        if detection and "trend_direction" in detection:
            print(f"✓ 趋势检测成功，趋势方向: {detection['trend_direction']}")
        else:
            print("✗ 趋势检测失败")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ 趋势分析测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_univariate_forecast():
    """测试单变量预测功能"""
    print("\n" + "=" * 60)
    print("测试单变量预测功能")
    print("=" * 60)
    
    try:
        from forecast_modules.auto_univariate_forecast import AutoUnivariatePredictor
        import numpy as np
        
        # 生成测试数据
        np.random.seed(42)
        n = 100
        trend = np.linspace(100, 150, n)
        seasonal = 10 * np.sin(2 * np.pi * np.arange(n) / 24)
        noise = np.random.normal(0, 2, n)
        values = (trend + seasonal + noise).tolist()
        
        timestamps = [
            (datetime.now() - timedelta(hours=n-i)).strftime("%Y-%m-%d %H:%M")
            for i in range(n)
        ]
        
        # 测试预测（使用正确的方法名和参数格式）
        predictor = AutoUnivariatePredictor()
        request_data = {
            'data': {
                'timestamp': timestamps,
                'value': values
            },
            'config': {
                'forecast_horizon': 12
            }
        }
        result = predictor.forecast(request_data)
        
        if result and result.get('success') and 'results' in result:
            forecast_data = result['results']
            print(f"✓ 单变量预测成功，预测点数: {len(forecast_data.get('forecast', []))}")
            print(f"  使用模型: {result.get('model_used', 'unknown')}")
        else:
            print(f"✗ 单变量预测失败: {result.get('message', 'unknown error')}")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ 单变量预测测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multivariate_forecast():
    """测试多变量预测功能"""
    print("\n" + "=" * 60)
    print("测试多变量预测功能")
    print("=" * 60)
    
    try:
        from forecast_modules.multivariate_forecast import MultivariatePredictor
        import numpy as np
        
        # 生成测试数据
        np.random.seed(42)
        n = 100
        
        timestamps = [
            (datetime.now() - timedelta(hours=n-i)).strftime("%Y-%m-%d %H:%M")
            for i in range(n)
        ]
        
        feature1 = np.random.uniform(10, 100, n).tolist()
        feature2 = np.random.uniform(0, 1, n).tolist()
        target = [50 + 0.5 * f1 + 20 * f2 + np.random.normal(0, 5) 
                  for f1, f2 in zip(feature1, feature2)]
        
        # 构造请求数据（使用正确的格式）
        data = [
            {"timestamp": t, "target": tgt, "feature1": f1, "feature2": f2}
            for t, tgt, f1, f2 in zip(timestamps, target, feature1, feature2)
        ]
        
        request = {
            'data': data,
            'config': {
                'target_column': 'target',
                'feature_columns': ['feature1', 'feature2'],
                'algorithm': 'random_forest',
                'forecast_horizon': 7
            }
        }
        
        # 测试预测（使用正确的方法名）
        predictor = MultivariatePredictor()
        result = predictor.forecast(request)
        
        if result and result.get('success') and 'results' in result:
            forecast_data = result['results']
            print(f"✓ 多变量预测成功，预测点数: {len(forecast_data.get('forecast', []))}")
            print(f"  使用算法: {result.get('model_used', 'unknown')}")
            if 'metrics' in result:
                print(f"  R² 分数: {result['metrics'].get('r2', 'N/A'):.4f}")
        else:
            print(f"✗ 多变量预测失败: {result.get('message', 'unknown error')}")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ 多变量预测测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fastapi_integration():
    """测试 FastAPI 集成"""
    print("\n" + "=" * 60)
    print("测试 FastAPI 集成")
    print("=" * 60)
    
    try:
        from fastapi import FastAPI
        from forecast_modules.trend_analysis import router as trend_router
        from forecast_modules.auto_univariate_forecast import router as forecast_router
        from forecast_modules.multivariate_forecast import router as multivariate_router
        
        app = FastAPI(title="测试应用")
        
        app.include_router(trend_router, prefix="/api/v1")
        app.include_router(forecast_router, prefix="/api/v2")
        app.include_router(multivariate_router, prefix="/api/v3")
        
        # 检查路由是否注册成功
        routes = [r.path for r in app.routes]
        
        expected_routes = [
            "/api/v1/trend/decomposition",
            "/api/v2/forecast/auto",
            "/api/v3/forecast/multivariate"
        ]
        
        missing = [r for r in expected_routes if r not in routes]
        
        if not missing:
            print(f"✓ FastAPI 集成成功，已注册 {len(routes)} 个路由")
        else:
            print(f"✗ 缺少路由: {missing}")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ FastAPI 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("forecast_modules 迁移包测试")
    print("=" * 60)
    
    results = {}
    
    # 测试导入
    success, errors = test_imports()
    results["模块导入"] = success
    
    if not success:
        print("\n模块导入失败，跳过功能测试")
        print("错误列表:")
        for err in errors:
            print(f"  - {err}")
    else:
        # 测试各模块功能
        results["趋势分析"] = test_trend_analysis()
        results["单变量预测"] = test_univariate_forecast()
        results["多变量预测"] = test_multivariate_forecast()
        results["FastAPI集成"] = test_fastapi_integration()
    
    # 输出总结
    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results.items():
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("所有测试通过！迁移包可以正常使用。")
    else:
        print("部分测试失败，请检查错误信息。")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
