"""
性能测试脚本
用于测试系统的性能表现和响应时间
"""

import asyncio
import time
import random
import string
from typing import List, Dict, Any
import statistics
import json
from datetime import datetime

import httpx
from unittest.mock import Mock, patch


class PerformanceTester:
    """性能测试器"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.coc_endpoint = f"{base_url}/pillow/coc/chat"
        self.iw_endpoint = f"{base_url}/pillow/instance_world/chat"
        self.results = []
        
    def generate_test_data(self, num_sessions: int = 10) -> List[Dict]:
        """生成测试数据"""
        sessions = []
        for i in range(num_sessions):
            sessions.append({
                "user_id": f"perf_test_{i:06d}",
                "session_id": f"perf_session_{i:03d}_{int(time.time())}",
                "world_id": random.choice(["trpg_01", "world_01"]),
                "gm_id": random.choice(["gm_01", "gm_02"]),
                "message": self._generate_random_message()
            })
        return sessions
    
    def _generate_random_message(self) -> str:
        """生成随机消息"""
        messages = [
            "你好，我想了解一下这个世界",
            "我向前走一步",
            "我需要查看我的角色属性",
            "我选择攻击怪物",
            "我想要使用魔法",
            "我检查一下背包",
            "我要存档",
            "我想和NPC对话"
        ]
        return random.choice(messages)
    
    async def test_concurrent_requests(self, 
                                    num_requests: int = 50, 
                                    concurrency: int = 10) -> Dict[str, Any]:
        """测试并发请求性能"""
        print(f"🧪 开始并发性能测试: {num_requests} 个请求, {concurrency} 并发")
        
        sessions = self.generate_test_data(concurrency)
        start_time = time.time()
        
        semaphore = asyncio.Semaphore(concurrency)
        
        async def make_request(session_data: Dict, request_id: int):
            async with semaphore:
                # 随机延迟以避免突发
                await asyncio.sleep(random.uniform(0, 0.1))
                
                request_start = time.time()
                
                try:
                    # 随机选择COC或副本世界端点
                    endpoint = random.choice([self.coc_endpoint, self.iw_endpoint])
                    
                    async with httpx.AsyncClient(timeout=30) as client:
                        response = await client.post(endpoint, json={
                            **session_data,
                            "step": 6,
                            "ext_param": {"action": "playing"}
                        })
                        
                        request_duration = time.time() - request_start
                        
                        return {
                            "request_id": request_id,
                            "status_code": response.status_code,
                            "duration": request_duration,
                            "success": response.status_code == 200,
                            "endpoint": endpoint
                        }
                        
                except Exception as e:
                    request_duration = time.time() - request_start
                    return {
                        "request_id": request_id,
                        "status_code": 0,
                        "duration": request_duration,
                        "success": False,
                        "error": str(e),
                        "endpoint": endpoint
                    }
        
        # 创建并发任务
        tasks = []
        for i in range(num_requests):
            session_data = random.choice(sessions)
            task = make_request(session_data, i)
            tasks.append(task)
        
        # 执行并发请求
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_duration = time.time() - start_time
        
        # 分析结果
        successful_requests = [r for r in results if isinstance(r, dict) and r.get("success", False)]
        failed_requests = [r for r in results if isinstance(r, dict) and not r.get("success", True)]
        
        if successful_requests:
            durations = [r["duration"] for r in successful_requests]
            
            analysis = {
                "test_type": "concurrent_requests",
                "timestamp": datetime.now().isoformat(),
                "total_requests": num_requests,
                "concurrency": concurrency,
                "successful_requests": len(successful_requests),
                "failed_requests": len(failed_requests),
                "success_rate": len(successful_requests) / num_requests * 100,
                "total_duration": total_duration,
                "requests_per_second": len(successful_requests) / total_duration,
                "avg_duration": statistics.mean(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
                "median_duration": statistics.median(durations),
                "p95_duration": self._calculate_percentile(durations, 95),
                "p99_duration": self._calculate_percentile(durations, 99)
            }
        else:
            analysis = {
                "test_type": "concurrent_requests",
                "timestamp": datetime.now().isoformat(),
                "total_requests": num_requests,
                "concurrency": concurrency,
                "successful_requests": 0,
                "failed_requests": len(failed_requests),
                "success_rate": 0,
                "total_duration": total_duration,
                "requests_per_second": 0,
                "avg_duration": 0,
                "min_duration": 0,
                "max_duration": 0,
                "median_duration": 0,
                "p95_duration": 0,
                "p99_duration": 0
            }
        
        # 详细结果
        analysis["detailed_results"] = results
        
        print(f"✅ 并发测试完成")
        print(f"   成功率: {analysis['success_rate']:.1f}%")
        print(f"   平均响应时间: {analysis.get('avg_duration', 0):.3f}s")
        print(f"   P95响应时间: {analysis.get('p95_duration', 0):.3f}s")
        print(f"   每秒请求数: {analysis.get('requests_per_second', 0):.2f}")
        
        return analysis
    
    async def test_response_time_under_load(self, 
                                          duration: int = 60,
                                          initial_concurrency: int = 5) -> Dict[str, Any]:
        """测试在负载下的响应时间"""
        print(f"🧪 开始负载测试: {duration}秒, {initial_concurrency}并发")
        
        sessions = self.generate_test_data(initial_concurrency)
        results = []
        start_time = time.time()
        
        async def continuous_requests():
            request_id = 0
            while time.time() - start_time < duration:
                session_data = random.choice(sessions)
                
                request_start = time.time()
                
                try:
                    endpoint = random.choice([self.coc_endpoint, self.iw_endpoint])
                    
                    async with httpx.AsyncClient(timeout=30) as client:
                        response = await client.post(endpoint, json={
                            **session_data,
                            "step": 6,
                            "ext_param": {"action": "playing"}
                        })
                        
                        request_duration = time.time() - request_start
                        
                        results.append({
                            "request_id": request_id,
                            "timestamp": time.time(),
                            "duration": request_duration,
                            "status_code": response.status_code,
                            "success": response.status_code == 200
                        })
                        
                except Exception as e:
                    request_duration = time.time() - request_start
                    
                    results.append({
                        "request_id": request_id,
                        "timestamp": time.time(),
                        "duration": request_duration,
                        "status_code": 0,
                        "success": False,
                        "error": str(e)
                    })
                
                request_id += 1
                
                # 小延迟
                await asyncio.sleep(0.1)
        
        # 启动多个并发任务
        tasks = [continuous_requests() for _ in range(initial_concurrency)]
        await asyncio.gather(*tasks)
        
        # 分析结果
        total_duration = time.time() - start_time
        successful_results = [r for r in results if r["success"]]
        failed_results = [r for r in results if not r["success"]]
        
        if successful_results:
            durations = [r["duration"] for r in successful_results]
            
            analysis = {
                "test_type": "response_time_under_load",
                "timestamp": datetime.now().isoformat(),
                "test_duration": duration,
                "concurrency": initial_concurrency,
                "total_requests": len(results),
                "successful_requests": len(successful_results),
                "failed_requests": len(failed_results),
                "success_rate": len(successful_results) / len(results) * 100,
                "requests_per_second": len(successful_results) / total_duration,
                "avg_response_time": statistics.mean(durations),
                "min_response_time": min(durations),
                "max_response_time": max(durations),
                "median_response_time": statistics.median(durations),
                "p95_response_time": self._calculate_percentile(durations, 95)
            }
        else:
            analysis = {
                "test_type": "response_time_under_load",
                "timestamp": datetime.now().isoformat(),
                "test_duration": duration,
                "concurrency": initial_concurrency,
                "total_requests": len(results),
                "successful_requests": 0,
                "failed_requests": len(results),
                "success_rate": 0,
                "requests_per_second": 0
            }
        
        print(f"✅ 负载测试完成")
        print(f"   总请求数: {len(results)}")
        print(f"   成功率: {analysis['success_rate']:.1f}%")
        print(f"   平均响应时间: {analysis.get('avg_response_time', 0):.3f}s")
        
        return analysis
    
    def _calculate_percentile(self, data: List[float], percentile: int) -> float:
        """计算百分位数"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)
        
        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))
    
    def save_results(self, results: Dict, filename: str = None):
        """保存测试结果"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_test_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"📊 测试结果已保存到: {filename}")


def mock_performance_test():
    """模拟性能测试（不依赖真实服务）"""
    print("🧪 开始模拟性能测试")
    
    # 模拟COC服务
    from src.services.coc_service import COCService
    from src.models.coc_game_state import COCGameState
    
    mock_llm = Mock()
    mock_llm.chat_completion.return_value = {
        "content": "这是一个模拟的AI回复",
        "tokens": 50
    }
    
    mock_db = Mock()
    service = COCService(mock_llm, mock_db, {})
    
    # 模拟session
    session = Mock(spec=COCGameState)
    session.session_id = "perf_test_session"
    session.game_status = "playing"
    session.investigator_card = {
        "name": "测试调查员",
        "currentHP": 10,
        "currentMP": 8,
        "currentSAN": 70
    }
    session.turn_number = 5
    session.round_number = 1
    session.dialogue_summary = None
    
    # 模拟请求
    request = Mock()
    request.message = "性能测试消息"
    
    # 测量响应构建性能
    start_time = time.time()
    
    # 模拟构建响应
    response = service._build_response("测试内容")
    
    duration = time.time() - start_time
    
    print(f"✅ 构建响应耗时: {duration:.6f}秒")
    
    return {
        "test_type": "mock_performance",
        "response_build_time": duration,
        "timestamp": datetime.now().isoformat()
    }


async def main():
    """主测试函数"""
    print("🚀 开始Flai Agent性能测试\n")
    
    # 首先运行模拟测试
    mock_result = mock_performance_test()
    print(f"模拟测试结果: {mock_result}\n")
    
    try:
        # 创建性能测试器
        tester = PerformanceTester()
        
        print("=" * 60)
        
        # 运行并发测试（小型）
        concurrent_result = await tester.test_concurrent_requests(
            num_requests=20,
            concurrency=5
        )
        
        print("\n" + "=" * 60)
        
        # 运行响应时间测试
        response_time_result = await tester.test_response_time_under_load(
            duration=30,
            initial_concurrency=3
        )
        
        # 保存结果
        all_results = {
            "mock_test": mock_result,
            "concurrent_test": concurrent_result,
            "response_time_test": response_time_result
        }
        
        tester.save_results(all_results)
        
        print("\n🎉 性能测试完成!")
        
        return True
        
    except Exception as e:
        print(f"❌ 性能测试失败: {e}")
        return False


if __name__ == "__main__":
    # 如果服务不运行，只运行模拟测试
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "mock":
        mock_performance_test()
    else:
        asyncio.run(main())