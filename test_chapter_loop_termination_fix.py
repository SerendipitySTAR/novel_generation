#!/usr/bin/env python3
"""
测试章节循环终止问题的修复
"""

import os
import sys
import shutil
import subprocess
import time
import signal
from pathlib import Path

def cleanup_test_files():
    """清理测试文件"""
    test_files = [
        "main_novel_generation.db",
        "novel_workflow_test.db",
        "./novel_workflow_chroma_db",
        "./chroma_db"
    ]
    
    for file_path in test_files:
        if os.path.exists(file_path):
            if os.path.isdir(file_path):
                shutil.rmtree(file_path)
                print(f"删除目录: {file_path}")
            else:
                os.remove(file_path)
                print(f"删除文件: {file_path}")

def test_workflow_termination():
    """测试工作流程是否正常终止"""
    print("🔧 测试章节循环终止问题修复...")
    
    # 清理之前的测试文件
    cleanup_test_files()
    
    # 构建测试命令
    python_path = "/media/sc/data/conda_envs/novels/bin/python3"
    main_script = "/media/sc/data/sc/novel_generation/main.py"
    
    cmd = [
        python_path, main_script,
        "--theme", "测试小说主题",
        "--style", "测试风格", 
        "--chapters", "2",  # 使用较少的章节数进行测试
        "--words-per-chapter", "500",  # 使用较少的字数
        "--auto-mode"
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    
    # 设置超时时间（5分钟）
    timeout_seconds = 300
    
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
        print("开始监控输出...")
        
        start_time = time.time()
        output_lines = []
        
        # 实时读取输出
        while True:
            # 检查进程是否结束
            if process.poll() is not None:
                # 进程已结束，读取剩余输出
                remaining_output = process.stdout.read()
                if remaining_output:
                    output_lines.extend(remaining_output.split('\n'))
                break
            
            # 检查超时
            if time.time() - start_time > timeout_seconds:
                print(f"⚠️ 进程运行超过 {timeout_seconds} 秒，强制终止")
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
                    if "DEBUG: cleanup_resources - Starting cleanup process" in line:
                        print("✅ 检测到清理资源开始")
                    elif "DEBUG: cleanup_resources - Cleanup completed successfully" in line:
                        print("✅ 检测到清理完成")
                    elif "DEBUG: _should_continue_chapter_loop" in line:
                        print("✅ 检测到章节循环条件检查")
                    elif "Chapter loop: Generated" in line and "All chapters complete" in line:
                        print("✅ 检测到章节生成完成")
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
        
        # 分析输出
        success_indicators = [
            "All chapters complete. Ending loop",
            "cleanup_resources - Cleanup completed successfully",
            "DEBUG: Workflow execution completed successfully"
        ]
        
        error_indicators = [
            "已杀死",
            "Killed",
            "CRITICAL ERROR",
            "Maximum loop iterations",
            "SAFETY:"
        ]
        
        found_success = any(indicator in line for line in output_lines for indicator in success_indicators)
        found_error = any(indicator in line for line in output_lines for indicator in error_indicators)
        
        if return_code == 0 and found_success and not found_error:
            print("✅ 测试通过：工作流程正常完成")
            return True, "成功"
        elif found_error:
            print("❌ 测试失败：检测到错误指示器")
            return False, "检测到错误"
        elif return_code != 0:
            print(f"❌ 测试失败：进程异常退出 (退出码: {return_code})")
            return False, f"异常退出码: {return_code}"
        else:
            print("⚠️ 测试结果不确定：未检测到明确的成功或失败指示器")
            return False, "结果不确定"
            
    except Exception as e:
        print(f"❌ 测试执行失败: {e}")
        return False, str(e)
    
    finally:
        # 清理测试文件
        cleanup_test_files()

def main():
    """主函数"""
    print("=" * 60)
    print("章节循环终止问题修复测试")
    print("=" * 60)
    
    success, message = test_workflow_termination()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 测试成功！章节循环终止问题已修复")
    else:
        print(f"💥 测试失败：{message}")
        print("请检查修复代码或进一步调试")
    print("=" * 60)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
