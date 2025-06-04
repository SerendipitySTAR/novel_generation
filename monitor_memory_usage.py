#!/usr/bin/env python3
"""
内存使用监控工具
用于监控小说生成过程中的内存使用情况，帮助诊断异常终止问题
"""

import os
import sys
import time
import psutil
import threading
from datetime import datetime
from typing import Dict, List, Any

class MemoryMonitor:
    def __init__(self, log_file: str = "memory_usage.log", interval: int = 5):
        self.log_file = log_file
        self.interval = interval
        self.monitoring = False
        self.monitor_thread = None
        self.process = psutil.Process()
        self.peak_memory = 0
        self.memory_history = []
        
    def start_monitoring(self):
        """开始监控"""
        if self.monitoring:
            print("⚠️  监控已在运行")
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print(f"🔍 开始监控内存使用，日志文件: {self.log_file}")
        
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        print("⏹️  停止监控")
        
    def _monitor_loop(self):
        """监控循环"""
        with open(self.log_file, 'w') as f:
            f.write("timestamp,pid,memory_mb,memory_percent,cpu_percent,threads,open_files\n")
            
            while self.monitoring:
                try:
                    # 获取内存信息
                    memory_info = self.process.memory_info()
                    memory_mb = memory_info.rss / 1024 / 1024
                    memory_percent = self.process.memory_percent()
                    cpu_percent = self.process.cpu_percent()
                    
                    # 获取线程和文件句柄数量
                    try:
                        num_threads = self.process.num_threads()
                        open_files = len(self.process.open_files())
                    except:
                        num_threads = 0
                        open_files = 0
                    
                    # 更新峰值内存
                    if memory_mb > self.peak_memory:
                        self.peak_memory = memory_mb
                    
                    # 记录历史
                    record = {
                        'timestamp': datetime.now().isoformat(),
                        'memory_mb': memory_mb,
                        'memory_percent': memory_percent,
                        'cpu_percent': cpu_percent,
                        'threads': num_threads,
                        'open_files': open_files
                    }
                    self.memory_history.append(record)
                    
                    # 保持历史记录在合理范围内
                    if len(self.memory_history) > 1000:
                        self.memory_history = self.memory_history[-500:]
                    
                    # 写入日志
                    f.write(f"{record['timestamp']},{self.process.pid},{memory_mb:.2f},{memory_percent:.2f},{cpu_percent:.2f},{num_threads},{open_files}\n")
                    f.flush()
                    
                    # 检查内存警告
                    if memory_mb > 1000:  # 超过1GB
                        print(f"⚠️  内存使用警告: {memory_mb:.2f} MB ({memory_percent:.1f}%)")
                    
                    if memory_mb > 2000:  # 超过2GB
                        print(f"🚨 内存使用严重警告: {memory_mb:.2f} MB ({memory_percent:.1f}%)")
                        print(f"   线程数: {num_threads}, 打开文件数: {open_files}")
                    
                except Exception as e:
                    print(f"❌ 监控错误: {e}")
                
                time.sleep(self.interval)
    
    def get_current_stats(self) -> Dict[str, Any]:
        """获取当前统计信息"""
        try:
            memory_info = self.process.memory_info()
            return {
                'current_memory_mb': memory_info.rss / 1024 / 1024,
                'peak_memory_mb': self.peak_memory,
                'memory_percent': self.process.memory_percent(),
                'cpu_percent': self.process.cpu_percent(),
                'threads': self.process.num_threads(),
                'open_files': len(self.process.open_files()) if hasattr(self.process, 'open_files') else 0
            }
        except Exception as e:
            return {'error': str(e)}
    
    def print_summary(self):
        """打印监控摘要"""
        stats = self.get_current_stats()
        print(f"\n📊 内存使用摘要:")
        print(f"   当前内存: {stats.get('current_memory_mb', 0):.2f} MB")
        print(f"   峰值内存: {stats.get('peak_memory_mb', 0):.2f} MB")
        print(f"   内存占用: {stats.get('memory_percent', 0):.1f}%")
        print(f"   CPU使用: {stats.get('cpu_percent', 0):.1f}%")
        print(f"   线程数: {stats.get('threads', 0)}")
        print(f"   打开文件: {stats.get('open_files', 0)}")

def check_system_resources():
    """检查系统资源"""
    print("🖥️  系统资源检查:")
    
    # 内存信息
    memory = psutil.virtual_memory()
    print(f"   总内存: {memory.total / 1024 / 1024 / 1024:.2f} GB")
    print(f"   可用内存: {memory.available / 1024 / 1024 / 1024:.2f} GB")
    print(f"   内存使用率: {memory.percent:.1f}%")
    
    # 磁盘信息
    disk = psutil.disk_usage('.')
    print(f"   磁盘总空间: {disk.total / 1024 / 1024 / 1024:.2f} GB")
    print(f"   磁盘可用空间: {disk.free / 1024 / 1024 / 1024:.2f} GB")
    print(f"   磁盘使用率: {(disk.used / disk.total) * 100:.1f}%")
    
    # CPU信息
    cpu_percent = psutil.cpu_percent(interval=1)
    print(f"   CPU使用率: {cpu_percent:.1f}%")
    print(f"   CPU核心数: {psutil.cpu_count()}")

def monitor_novel_generation():
    """监控小说生成过程"""
    print("🚀 小说生成内存监控")
    print("=" * 50)
    
    # 检查系统资源
    check_system_resources()
    
    # 创建监控器
    monitor = MemoryMonitor()
    
    try:
        # 开始监控
        monitor.start_monitoring()
        
        print(f"\n📝 监控已启动，按 Ctrl+C 停止监控")
        print(f"💡 建议在另一个终端运行小说生成程序")
        print(f"📊 实时监控数据将保存到: {monitor.log_file}")
        
        # 等待用户中断
        while True:
            time.sleep(10)
            stats = monitor.get_current_stats()
            if stats.get('current_memory_mb', 0) > 0:
                print(f"📊 当前内存: {stats['current_memory_mb']:.2f} MB, "
                      f"峰值: {stats['peak_memory_mb']:.2f} MB, "
                      f"线程: {stats.get('threads', 0)}")
    
    except KeyboardInterrupt:
        print(f"\n⏹️  用户中断监控")
    
    finally:
        monitor.stop_monitoring()
        monitor.print_summary()
        
        # 分析日志文件
        if os.path.exists(monitor.log_file):
            print(f"\n📈 分析监控日志...")
            analyze_memory_log(monitor.log_file)

def analyze_memory_log(log_file: str):
    """分析内存使用日志"""
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()[1:]  # 跳过标题行
        
        if not lines:
            print("📊 日志文件为空")
            return
        
        memory_values = []
        max_memory = 0
        max_threads = 0
        max_files = 0
        
        for line in lines:
            parts = line.strip().split(',')
            if len(parts) >= 6:
                memory_mb = float(parts[2])
                threads = int(parts[5])
                files = int(parts[6])
                
                memory_values.append(memory_mb)
                max_memory = max(max_memory, memory_mb)
                max_threads = max(max_threads, threads)
                max_files = max(max_files, files)
        
        if memory_values:
            avg_memory = sum(memory_values) / len(memory_values)
            print(f"📊 内存使用分析:")
            print(f"   平均内存: {avg_memory:.2f} MB")
            print(f"   峰值内存: {max_memory:.2f} MB")
            print(f"   最大线程数: {max_threads}")
            print(f"   最大打开文件数: {max_files}")
            
            # 检查是否有内存泄漏迹象
            if len(memory_values) > 10:
                first_half = memory_values[:len(memory_values)//2]
                second_half = memory_values[len(memory_values)//2:]
                first_avg = sum(first_half) / len(first_half)
                second_avg = sum(second_half) / len(second_half)
                
                if second_avg > first_avg * 1.5:
                    print(f"⚠️  可能存在内存泄漏：后半段平均内存({second_avg:.2f} MB)比前半段({first_avg:.2f} MB)高出50%以上")
    
    except Exception as e:
        print(f"❌ 分析日志失败: {e}")

def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] == "analyze":
        # 分析模式
        log_file = sys.argv[2] if len(sys.argv) > 2 else "memory_usage.log"
        if os.path.exists(log_file):
            analyze_memory_log(log_file)
        else:
            print(f"❌ 日志文件不存在: {log_file}")
    else:
        # 监控模式
        monitor_novel_generation()

if __name__ == "__main__":
    main()
