#!/usr/bin/env python3
"""
专门测试 LoreKeeper 更新后的程序终止问题
"""

import os
import sys
import signal
import subprocess
import time
import threading
from pathlib import Path

def monitor_process_memory(pid, interval=2):
    """监控进程内存使用"""
    try:
        import psutil
        process = psutil.Process(pid)
        
        while process.is_running():
            try:
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                print(f"MEMORY_MONITOR: PID {pid} using {memory_mb:.1f}MB")
                
                # 如果内存使用超过阈值，发出警告
                if memory_mb > 2000:  # 2GB
                    print(f"WARNING: High memory usage detected: {memory_mb:.1f}MB")
                
                time.sleep(interval)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
    except ImportError:
        print("psutil not available, skipping memory monitoring")
    except Exception as e:
        print(f"Memory monitoring error: {e}")

def test_lore_keeper_termination():
    """测试 LoreKeeper 更新后的终止问题"""
    print("🔧 测试 LoreKeeper 更新后的程序终止问题...")
    
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
    
    # 构建测试命令 - 使用4章来重现问题
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
        
        # 启动内存监控线程
        memory_thread = threading.Thread(
            target=monitor_process_memory, 
            args=(process.pid, 3),
            daemon=True
        )
        memory_thread.start()
        
        print("开始监控输出...")
        
        start_time = time.time()
        output_lines = []
        lore_keeper_update_completed = False
        increment_chapter_started = False
        
        # 实时读取输出
        while True:
            # 检查进程是否结束
            if process.poll() is not None:
                # 进程已结束，读取剩余输出
                remaining_output = process.stdout.read()
                if remaining_output:
                    output_lines.extend(remaining_output.split('\n'))
                break
            
            # 检查超时（10分钟）
            if time.time() - start_time > 600:
                print(f"⚠️ 进程运行超过10分钟，强制终止")
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
                    
                    # 检查关键输出
                    if "DEBUG: execute_lore_keeper_update_kb - Successfully completed" in line:
                        lore_keeper_update_completed = True
                        print("✅ 检测到 LoreKeeper 更新完成")
                    elif "KnowledgeBaseManager: Cleaned up vector store cache" in line:
                        print("✅ 检测到向量存储缓存清理")
                    elif "DEBUG: increment_chapter_number" in line:
                        increment_chapter_started = True
                        print("✅ 检测到章节递增开始")
                    elif "DEBUG: _should_continue_chapter_loop" in line:
                        print("✅ 检测到章节循环条件检查")
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
        print(f"   LoreKeeper 更新完成: {lore_keeper_update_completed}")
        print(f"   章节递增开始: {increment_chapter_started}")
        
        # 分析问题
        if lore_keeper_update_completed and not increment_chapter_started:
            print("❌ 问题确认：LoreKeeper 更新完成后，章节递增未开始")
            print("   这表明问题出现在 LangGraph 的条件边缘路由中")
            return False, "LoreKeeper 更新后状态传递失败"
        elif return_code != 0:
            print(f"❌ 进程异常退出 (退出码: {return_code})")
            return False, f"异常退出码: {return_code}"
        else:
            print("✅ 测试通过：程序正常完成")
            return True, "成功"
            
    except Exception as e:
        print(f"❌ 测试执行失败: {e}")
        return False, str(e)

def main():
    """主函数"""
    print("=" * 60)
    print("LoreKeeper 更新后程序终止问题测试")
    print("=" * 60)
    
    success, message = test_lore_keeper_termination()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 测试成功！问题已修复")
    else:
        print(f"💥 测试失败：{message}")
        print("需要进一步调试 LangGraph 状态传递问题")
    print("=" * 60)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
