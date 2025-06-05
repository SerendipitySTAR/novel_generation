#!/usr/bin/env python3
"""
测试内存优化修复效果
"""

import os
import sys
import signal
import subprocess
import time
import threading
from pathlib import Path

def monitor_process_memory_detailed(pid, interval=3):
    """详细监控进程内存使用"""
    try:
        import psutil
        process = psutil.Process(pid)
        
        max_memory = 0
        memory_history = []
        
        while process.is_running():
            try:
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                memory_history.append(memory_mb)
                
                if memory_mb > max_memory:
                    max_memory = memory_mb
                
                print(f"MEMORY: {memory_mb:.1f}MB (Peak: {max_memory:.1f}MB)")
                
                # 如果内存使用超过阈值，发出警告
                if memory_mb > 8000:  # 8GB
                    print(f"CRITICAL: Memory usage extremely high: {memory_mb:.1f}MB")
                elif memory_mb > 4000:  # 4GB
                    print(f"WARNING: Memory usage very high: {memory_mb:.1f}MB")
                elif memory_mb > 2000:  # 2GB
                    print(f"CAUTION: Memory usage high: {memory_mb:.1f}MB")
                
                time.sleep(interval)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
        
        return max_memory, memory_history
    except ImportError:
        print("psutil not available, skipping detailed memory monitoring")
        return 0, []
    except Exception as e:
        print(f"Memory monitoring error: {e}")
        return 0, []

def test_memory_optimization():
    """测试内存优化效果"""
    print("🔧 测试内存优化修复效果...")
    
    # 清理之前的测试文件
    test_files = [
        "main_novel_generation.db",
        "novel_workflow_test.db",
        "./novel_workflow_chroma_db",
        "./chroma_db"
    ]
    
    for file_path in test_files:
        if os.path.exists(file_path):
            if os.path.isdir(file_path):
                import shutil
                shutil.rmtree(file_path)
                print(f"删除目录: {file_path}")
            else:
                os.remove(file_path)
                print(f"删除文件: {file_path}")
    
    # 构建测试命令 - 使用4章来测试内存使用
    python_path = "/media/sc/data/conda_envs/novels/bin/python3"
    main_script = "/media/sc/data/sc/novel_generation/main.py"
    
    cmd = [
        python_path, main_script,
        "--theme", "废柴少女修仙日记",
        "--style", "搞笑幽默",
        "--chapters", "4",
        "--words-per-chapter", "1200",
        "--auto-mode"
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        # 启动进程
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        print(f"进程启动，PID: {process.pid}")
        
        # 启动详细内存监控线程
        max_memory = 0
        memory_history = []
        
        def memory_monitor():
            nonlocal max_memory, memory_history
            max_memory, memory_history = monitor_process_memory_detailed(process.pid, 3)
        
        memory_thread = threading.Thread(target=memory_monitor, daemon=True)
        memory_thread.start()
        
        print("开始监控输出和内存使用...")
        
        start_time = time.time()
        output_lines = []
        chapters_completed = 0
        lore_keeper_updates = 0
        memory_cleanups = 0
        
        # 实时读取输出
        while True:
            # 检查进程是否结束
            if process.poll() is not None:
                # 进程已结束，读取剩余输出
                remaining_output = process.stdout.read()
                if remaining_output:
                    output_lines.extend(remaining_output.split('\n'))
                break
            
            # 检查超时（15分钟）
            if time.time() - start_time > 900:
                print(f"⚠️ 进程运行超过15分钟，强制终止")
                process.terminate()
                time.sleep(5)
                if process.poll() is None:
                    process.kill()
                return False, "进程超时"
            
            # 读取一行输出
            try:
                line = process.stdout.readline()
                if line:
                    line = line.strip()
                    output_lines.append(line)
                    print(f"OUTPUT: {line}")
                    
                    # 统计关键事件
                    if "Chapter" in line and "generated and saved" in line:
                        chapters_completed += 1
                        print(f"✅ 第{chapters_completed}章完成")
                    elif "Lore Keeper KB updated" in line:
                        lore_keeper_updates += 1
                        print(f"✅ LoreKeeper 更新 #{lore_keeper_updates}")
                    elif "Garbage collected" in line:
                        memory_cleanups += 1
                        print(f"🧹 内存清理 #{memory_cleanups}")
                    elif "已杀死" in line or "Killed" in line:
                        print("❌ 检测到进程被杀死")
                        break
                else:
                    time.sleep(0.1)
            except Exception as e:
                print(f"读取输出时出错: {e}")
                break
        
        # 获取进程退出码
        return_code = process.returncode
        elapsed_time = time.time() - start_time
        
        print(f"\n📊 测试结果:")
        print(f"   进程退出码: {return_code}")
        print(f"   运行时间: {elapsed_time:.1f} 秒")
        print(f"   输出行数: {len(output_lines)}")
        print(f"   完成章节数: {chapters_completed}")
        print(f"   LoreKeeper 更新次数: {lore_keeper_updates}")
        print(f"   内存清理次数: {memory_cleanups}")
        print(f"   峰值内存使用: {max_memory:.1f}MB")
        
        # 分析内存使用趋势
        if memory_history:
            avg_memory = sum(memory_history) / len(memory_history)
            print(f"   平均内存使用: {avg_memory:.1f}MB")
            
            # 检查内存增长趋势
            if len(memory_history) > 10:
                early_avg = sum(memory_history[:5]) / 5
                late_avg = sum(memory_history[-5:]) / 5
                growth_rate = (late_avg - early_avg) / early_avg * 100
                print(f"   内存增长率: {growth_rate:.1f}%")
                
                if growth_rate > 200:  # 增长超过200%
                    print("   ⚠️ 内存增长过快，可能存在内存泄漏")
                elif growth_rate > 100:  # 增长超过100%
                    print("   ⚠️ 内存增长较快，需要关注")
                else:
                    print("   ✅ 内存增长在可接受范围内")
        
        # 评估测试结果
        success = False
        message = ""
        
        if return_code == 0 and chapters_completed == 4:
            if max_memory < 8000:  # 峰值内存小于8GB
                success = True
                message = "成功：程序正常完成，内存使用在可接受范围内"
            else:
                message = f"部分成功：程序完成但内存使用过高 ({max_memory:.1f}MB)"
        elif chapters_completed > 0:
            message = f"部分成功：完成了{chapters_completed}章，但程序异常终止"
        else:
            message = "失败：程序未能完成任何章节"
        
        return success, message
            
    except Exception as e:
        print(f"❌ 测试执行失败: {e}")
        return False, str(e)

def main():
    """主函数"""
    print("=" * 60)
    print("内存优化修复效果测试")
    print("=" * 60)
    
    success, message = test_memory_optimization()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 测试成功！内存优化有效")
    else:
        print(f"💥 测试结果：{message}")
    print("=" * 60)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
