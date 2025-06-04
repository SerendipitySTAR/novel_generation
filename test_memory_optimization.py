#!/usr/bin/env python3
"""
测试内存优化效果的脚本
验证 LoreKeeperAgent 实例缓存和资源清理是否有效
"""

import os
import sys
import time
import psutil
import threading
from typing import Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath('.'))

class MemoryTracker:
    def __init__(self):
        self.process = psutil.Process()
        self.peak_memory = 0
        self.memory_history = []
        
    def get_current_memory(self) -> float:
        """获取当前内存使用量（MB）"""
        memory_mb = self.process.memory_info().rss / 1024 / 1024
        if memory_mb > self.peak_memory:
            self.peak_memory = memory_mb
        self.memory_history.append(memory_mb)
        return memory_mb
    
    def print_memory_stats(self, label: str = ""):
        """打印内存统计信息"""
        current = self.get_current_memory()
        print(f"📊 {label} - 当前内存: {current:.2f} MB, 峰值: {self.peak_memory:.2f} MB")

def test_lore_keeper_caching():
    """测试 LoreKeeperAgent 实例缓存"""
    print("🧪 测试 LoreKeeperAgent 实例缓存")
    print("=" * 50)
    
    tracker = MemoryTracker()
    tracker.print_memory_stats("开始测试")
    
    # 设置虚拟API密钥
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = "sk-dummykeyfortesting"
    
    try:
        from src.agents.lore_keeper_agent import LoreKeeperAgent
        
        # 测试1：重复创建实例（模拟旧的行为）
        print("\n🔄 测试1：重复创建 LoreKeeperAgent 实例")
        instances = []
        for i in range(3):
            print(f"   创建实例 {i+1}...")
            instance = LoreKeeperAgent(db_name=f"test_memory_{i}.db")
            instances.append(instance)
            tracker.print_memory_stats(f"实例 {i+1}")
            time.sleep(1)  # 给系统时间处理
        
        # 清理实例
        print("\n🧹 清理实例...")
        for i, instance in enumerate(instances):
            if hasattr(instance, 'kb_manager') and hasattr(instance.kb_manager, 'cleanup_resources'):
                instance.kb_manager.cleanup_resources()
                print(f"   清理实例 {i+1}")
        instances.clear()
        tracker.print_memory_stats("清理后")
        
        # 测试2：重用实例（模拟新的行为）
        print("\n♻️  测试2：重用 LoreKeeperAgent 实例")
        shared_instance = LoreKeeperAgent(db_name="test_memory_shared.db")
        tracker.print_memory_stats("创建共享实例")
        
        for i in range(3):
            print(f"   重用实例进行操作 {i+1}...")
            # 模拟使用实例进行操作
            if hasattr(shared_instance, 'kb_manager'):
                stats = shared_instance.kb_manager.get_collection_stats(999)
                print(f"     操作结果: {stats.get('document_count', 0)} 文档")
            tracker.print_memory_stats(f"操作 {i+1}")
            time.sleep(1)
        
        # 最终清理
        if hasattr(shared_instance, 'kb_manager') and hasattr(shared_instance.kb_manager, 'cleanup_resources'):
            shared_instance.kb_manager.cleanup_resources()
        tracker.print_memory_stats("最终清理后")
        
        # 清理测试数据库
        for i in range(3):
            db_file = f"test_memory_{i}.db"
            if os.path.exists(db_file):
                os.remove(db_file)
        
        if os.path.exists("test_memory_shared.db"):
            os.remove("test_memory_shared.db")
        
        print(f"\n📈 内存使用总结:")
        print(f"   峰值内存: {tracker.peak_memory:.2f} MB")
        print(f"   内存历史: {len(tracker.memory_history)} 个记录")
        if len(tracker.memory_history) > 1:
            memory_growth = tracker.memory_history[-1] - tracker.memory_history[0]
            print(f"   内存增长: {memory_growth:.2f} MB")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

def test_workflow_memory_usage():
    """测试完整工作流程的内存使用"""
    print("\n🚀 测试完整工作流程内存使用")
    print("=" * 50)
    
    tracker = MemoryTracker()
    tracker.print_memory_stats("工作流程开始")
    
    # 设置虚拟API密钥
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = "sk-dummykeyfortesting"
    
    try:
        from src.orchestration.workflow_manager import WorkflowManager
        
        # 创建测试数据库
        test_db = "test_workflow_memory.db"
        if os.path.exists(test_db):
            os.remove(test_db)
        
        tracker.print_memory_stats("初始化前")
        
        # 初始化工作流程管理器
        manager = WorkflowManager(db_name=test_db)
        tracker.print_memory_stats("WorkflowManager 初始化后")
        
        # 测试输入：生成2章（较小的测试）
        test_input = {
            'theme': '测试主题：内存优化验证',
            'style_preferences': '测试风格',
            'chapters': 2,  # 只生成2章进行测试
            'words_per_chapter': 300,
            'skip_cost_estimate': True,
            'auto_mode': True
        }
        
        print(f"🚀 开始运行工作流程...")
        tracker.print_memory_stats("工作流程开始前")
        
        # 运行工作流程
        final_state = manager.run_workflow(test_input)
        tracker.print_memory_stats("工作流程完成后")
        
        # 检查结果
        generated_chapters = final_state.get('generated_chapters', [])
        error_message = final_state.get('error_message')
        lore_keeper_instance = final_state.get('lore_keeper_instance')
        
        print(f"\n📊 工作流程结果:")
        print(f"   生成章节数: {len(generated_chapters)}")
        print(f"   错误信息: {error_message}")
        print(f"   LoreKeeper实例缓存: {'是' if lore_keeper_instance else '否'}")
        
        # 手动清理资源（模拟cleanup_resources节点）
        if lore_keeper_instance and hasattr(lore_keeper_instance, 'kb_manager'):
            if hasattr(lore_keeper_instance.kb_manager, 'cleanup_resources'):
                lore_keeper_instance.kb_manager.cleanup_resources()
                print("   手动清理LoreKeeper资源")
        
        tracker.print_memory_stats("手动清理后")
        
        # 清理测试数据库
        if os.path.exists(test_db):
            os.remove(test_db)
        
        print(f"\n📈 工作流程内存总结:")
        print(f"   峰值内存: {tracker.peak_memory:.2f} MB")
        if len(tracker.memory_history) > 1:
            memory_growth = tracker.memory_history[-1] - tracker.memory_history[0]
            print(f"   内存增长: {memory_growth:.2f} MB")
            
            # 检查内存泄漏迹象
            if memory_growth > 100:  # 超过100MB增长
                print(f"⚠️  可能存在内存泄漏：内存增长 {memory_growth:.2f} MB")
            else:
                print(f"✅ 内存使用正常：增长 {memory_growth:.2f} MB")
        
    except Exception as e:
        print(f"❌ 工作流程测试失败: {e}")
        import traceback
        traceback.print_exc()

def test_chromadb_resource_management():
    """测试 ChromaDB 资源管理"""
    print("\n🗄️  测试 ChromaDB 资源管理")
    print("=" * 50)
    
    tracker = MemoryTracker()
    tracker.print_memory_stats("ChromaDB测试开始")
    
    # 设置虚拟API密钥
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = "sk-dummykeyfortesting"
    
    try:
        from src.knowledge_base.knowledge_base_manager import KnowledgeBaseManager
        
        # 测试创建多个KnowledgeBaseManager实例
        print("\n📚 创建多个 KnowledgeBaseManager 实例...")
        managers = []
        
        for i in range(3):
            print(f"   创建管理器 {i+1}...")
            manager = KnowledgeBaseManager(db_directory=f"./test_chroma_{i}")
            managers.append(manager)
            tracker.print_memory_stats(f"管理器 {i+1}")
            
            # 测试添加一些文本
            try:
                manager.add_texts(999, [f"测试文本 {i}"], [{"source": "test"}])
                print(f"     添加测试文本成功")
            except Exception as e:
                print(f"     添加测试文本失败: {e}")
        
        # 清理资源
        print("\n🧹 清理 KnowledgeBaseManager 资源...")
        for i, manager in enumerate(managers):
            if hasattr(manager, 'cleanup_resources'):
                manager.cleanup_resources()
                print(f"   清理管理器 {i+1}")
        
        tracker.print_memory_stats("清理后")
        
        # 清理测试目录
        import shutil
        for i in range(3):
            test_dir = f"./test_chroma_{i}"
            if os.path.exists(test_dir):
                shutil.rmtree(test_dir)
        
        print(f"\n📈 ChromaDB 内存总结:")
        print(f"   峰值内存: {tracker.peak_memory:.2f} MB")
        if len(tracker.memory_history) > 1:
            memory_growth = tracker.memory_history[-1] - tracker.memory_history[0]
            print(f"   内存增长: {memory_growth:.2f} MB")
        
    except Exception as e:
        print(f"❌ ChromaDB测试失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主函数"""
    print("🔧 内存优化测试")
    print("=" * 50)
    
    # 检查系统内存
    memory = psutil.virtual_memory()
    print(f"🖥️  系统内存: {memory.total / 1024 / 1024 / 1024:.2f} GB 总计, {memory.available / 1024 / 1024 / 1024:.2f} GB 可用")
    
    try:
        # 测试1：LoreKeeper实例缓存
        test_lore_keeper_caching()
        
        # 测试2：ChromaDB资源管理
        test_chromadb_resource_management()
        
        # 测试3：完整工作流程（可选）
        print("\n" + "=" * 50)
        response = input("是否运行完整工作流程内存测试？(可能较慢) [y/N]: ")
        if response.lower() in ['y', 'yes']:
            test_workflow_memory_usage()
        else:
            print("跳过完整工作流程测试")
        
        print("\n🎉 内存优化测试完成！")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
