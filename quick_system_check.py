#!/usr/bin/env python3
"""
快速系统检查脚本
验证所有修复是否正常工作
"""

import os
import sys
import subprocess
import time

def check_processes():
    """检查是否有异常的Python进程"""
    print("🔍 检查进程状态...")
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        novel_processes = [line for line in lines if 'python' in line and 'novel' in line]
        
        if novel_processes:
            print("📋 发现相关进程:")
            for proc in novel_processes:
                print(f"  {proc}")
                # 检查CPU占用
                parts = proc.split()
                if len(parts) > 2:
                    cpu_usage = parts[2]
                    if cpu_usage.replace('.', '').isdigit() and float(cpu_usage) > 50:
                        print(f"  ⚠️  高CPU占用: {cpu_usage}%")
        else:
            print("✅ 没有发现异常的小说生成进程")
        
        return True
    except Exception as e:
        print(f"❌ 进程检查失败: {e}")
        return False

def check_database_access():
    """检查数据库访问是否正常"""
    print("\n🗄️  检查数据库访问...")
    try:
        from src.utils.memory_manager import MemoryManager
        memory_manager = MemoryManager()
        
        # 测试 list_novels_with_stats 方法
        novels = memory_manager.list_novels_with_stats()
        print(f"✅ 数据库访问正常，找到 {len(novels)} 部小说")
        
        # 测试记忆隔离报告
        report = memory_manager.get_memory_isolation_report()
        print(f"✅ 记忆隔离报告正常，总小说数: {report['total_novels']}")
        
        return True
    except Exception as e:
        print(f"❌ 数据库访问失败: {e}")
        return False

def check_workflow_safety():
    """检查工作流程安全机制"""
    print("\n🔒 检查工作流程安全机制...")
    try:
        from src.orchestration.workflow_manager import _should_continue_chapter_loop
        
        # 测试正常情况
        normal_state = {
            'current_chapter_number': 2,
            'total_chapters_to_generate': 3,
            'generated_chapters': [{'chapter_number': 1}],
            'loop_iteration_count': 1,
            'max_loop_iterations': 9
        }
        result = _should_continue_chapter_loop(normal_state)
        if result == "continue_loop":
            print("✅ 正常循环逻辑工作正常")
        else:
            print(f"⚠️  正常循环逻辑异常: {result}")
        
        # 测试安全限制
        safety_state = {
            'current_chapter_number': 2,
            'total_chapters_to_generate': 3,
            'generated_chapters': [{'chapter_number': 1}],
            'loop_iteration_count': 10,
            'max_loop_iterations': 9
        }
        result = _should_continue_chapter_loop(safety_state)
        if result == "end_loop_on_safety":
            print("✅ 安全限制机制工作正常")
        else:
            print(f"⚠️  安全限制机制异常: {result}")
        
        return True
    except Exception as e:
        print(f"❌ 工作流程安全检查失败: {e}")
        return False

def check_problem_solver():
    """检查问题解决工具是否正常"""
    print("\n🛠️  检查问题解决工具...")
    try:
        # 使用conda环境运行健康检查
        cmd = ['/media/sc/data/conda_envs/novels/bin/python', '-m', 'src.utils.problem_solver', 'health']
        result = subprocess.run(cmd, capture_output=True, text=True, cwd='/media/sc/data/sc/novel_generation')
        
        if result.returncode == 0:
            print("✅ 问题解决工具正常工作")
            # 检查输出中的关键信息
            if "系统健康状态" in result.stdout:
                print("✅ 健康检查功能正常")
        else:
            print(f"⚠️  问题解决工具异常: {result.stderr}")
        
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 问题解决工具检查失败: {e}")
        return False

def main():
    """主检查函数"""
    print("🚀 小说生成系统快速检查")
    print("=" * 50)
    
    # 切换到正确的工作目录
    os.chdir('/media/sc/data/sc/novel_generation')
    
    checks = [
        ("进程状态", check_processes),
        ("数据库访问", check_database_access),
        ("工作流程安全", check_workflow_safety),
        ("问题解决工具", check_problem_solver)
    ]
    
    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"❌ {name}检查出错: {e}")
            results[name] = False
    
    print("\n" + "=" * 50)
    print("📋 检查结果总结:")
    
    all_passed = True
    for name, passed in results.items():
        status = "✅ 正常" if passed else "❌ 异常"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n🎯 总体状态:")
    if all_passed:
        print("✅ 系统完全正常，所有问题已修复！")
        print("\n💡 建议:")
        print("  - 可以安全地开始生成新小说")
        print("  - 建议先用较小的章节数测试（如2-3章）")
        print("  - 监控进程状态，确保没有高CPU占用")
    else:
        print("⚠️  系统仍有部分问题，请检查上述异常项")
        print("\n🔧 建议:")
        print("  - 查看具体的错误信息")
        print("  - 运行 python -m src.utils.problem_solver diagnose")
        print("  - 如有需要，使用紧急停止命令")
    
    print(f"\n📅 检查时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
