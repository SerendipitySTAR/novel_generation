#!/usr/bin/env python3
"""
测试ChromaDB修复功能

验证修复后的系统是否正常工作
"""

import os
import sys
import traceback
from typing import Dict, Any


def test_knowledge_base_manager():
    """测试KnowledgeBaseManager"""
    print("🧪 测试KnowledgeBaseManager...")
    
    try:
        from src.knowledge_base.knowledge_base_manager import KnowledgeBaseManager
        
        # 创建测试实例
        kb_manager = KnowledgeBaseManager(
            collection_name_prefix="test_chromadb_fix",
            db_directory="./test_chroma_db"
        )
        
        test_novel_id = 888888
        
        # 测试添加文本
        print("  📝 测试添加文本...")
        test_texts = [
            "这是第一个测试文本，用于验证ChromaDB修复功能。",
            "这是第二个测试文本，包含不同的内容和关键词。",
            "第三个测试文本，用于测试检索功能的准确性。"
        ]
        
        kb_manager.add_texts(test_novel_id, test_texts)
        print("  ✅ 成功添加文本")
        
        # 测试检索
        print("  🔍 测试检索功能...")
        results = kb_manager.retrieve_relevant_chunks(test_novel_id, "测试文本", k=2)
        print(f"  ✅ 成功检索到 {len(results)} 个结果")
        
        if results:
            print("  📄 检索结果预览:")
            for i, result in enumerate(results[:2]):
                print(f"    {i+1}. {result[:50]}...")
        
        # 测试集合统计
        print("  📊 测试集合统计...")
        stats = kb_manager.get_collection_stats(test_novel_id)
        print(f"  ✅ 集合统计: {stats.get('document_count', 0)} 个文档")
        
        # 清理测试数据
        print("  🧹 清理测试数据...")
        kb_manager.delete_collection(test_novel_id)
        print("  ✅ 测试数据清理完成")
        
        # 清理测试目录
        import shutil
        if os.path.exists("./test_chroma_db"):
            shutil.rmtree("./test_chroma_db")
        
        return True
        
    except Exception as e:
        print(f"  ❌ KnowledgeBaseManager测试失败: {e}")
        print(f"  🔍 详细错误:")
        traceback.print_exc()
        return False


def test_lore_keeper_agent():
    """测试LoreKeeperAgent"""
    print("\n🧪 测试LoreKeeperAgent...")
    
    try:
        from src.agents.lore_keeper_agent import LoreKeeperAgent
        
        # 只测试导入和创建，不执行实际操作
        print("  📦 测试导入...")
        print("  ✅ 成功导入LoreKeeperAgent")
        
        # 测试创建实例
        print("  🏗️ 测试创建实例...")
        lore_keeper = LoreKeeperAgent(
            db_name="test_lore_keeper.db",
            chroma_db_directory="./test_lore_chroma"
        )
        print("  ✅ 成功创建LoreKeeperAgent实例")
        
        # 清理测试文件
        test_files = ["test_lore_keeper.db"]
        for file in test_files:
            if os.path.exists(file):
                os.remove(file)
        
        import shutil
        if os.path.exists("./test_lore_chroma"):
            shutil.rmtree("./test_lore_chroma")
        
        return True
        
    except Exception as e:
        print(f"  ❌ LoreKeeperAgent测试失败: {e}")
        print(f"  🔍 详细错误:")
        traceback.print_exc()
        return False


def test_context_synthesizer_agent():
    """测试ContextSynthesizerAgent"""
    print("\n🧪 测试ContextSynthesizerAgent...")
    
    try:
        from src.agents.context_synthesizer_agent import ContextSynthesizerAgent
        
        # 只测试导入和创建，不执行实际操作
        print("  📦 测试导入...")
        print("  ✅ 成功导入ContextSynthesizerAgent")
        
        # 测试创建实例
        print("  🏗️ 测试创建实例...")
        context_agent = ContextSynthesizerAgent(
            db_name="test_context.db",
            chroma_db_directory="./test_context_chroma"
        )
        print("  ✅ 成功创建ContextSynthesizerAgent实例")
        
        # 清理测试文件
        test_files = ["test_context.db"]
        for file in test_files:
            if os.path.exists(file):
                os.remove(file)
        
        import shutil
        if os.path.exists("./test_context_chroma"):
            shutil.rmtree("./test_context_chroma")
        
        return True
        
    except Exception as e:
        print(f"  ❌ ContextSynthesizerAgent测试失败: {e}")
        print(f"  🔍 详细错误:")
        traceback.print_exc()
        return False


def test_error_handling():
    """测试错误处理机制"""
    print("\n🧪 测试错误处理机制...")
    
    try:
        from src.knowledge_base.knowledge_base_manager import KnowledgeBaseManager
        
        # 创建一个可能触发错误的场景
        kb_manager = KnowledgeBaseManager(
            collection_name_prefix="test_error_handling",
            db_directory="./test_error_chroma"
        )
        
        test_novel_id = 777777
        
        print("  🔧 测试自动修复机制...")
        
        # 尝试检索不存在的集合
        results = kb_manager.retrieve_relevant_chunks(test_novel_id, "不存在的查询", k=1)
        print(f"  ✅ 空集合检索处理正常: {len(results)} 个结果")
        
        # 添加一些文本
        kb_manager.add_texts(test_novel_id, ["测试错误处理文本"])
        print("  ✅ 文本添加正常")
        
        # 再次检索
        results = kb_manager.retrieve_relevant_chunks(test_novel_id, "测试", k=1)
        print(f"  ✅ 正常检索: {len(results)} 个结果")
        
        # 清理
        kb_manager.delete_collection(test_novel_id)
        
        import shutil
        if os.path.exists("./test_error_chroma"):
            shutil.rmtree("./test_error_chroma")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 错误处理测试失败: {e}")
        print(f"  🔍 详细错误:")
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("🚀 ChromaDB修复功能测试")
    print("=" * 50)
    
    tests = [
        ("KnowledgeBaseManager", test_knowledge_base_manager),
        ("LoreKeeperAgent", test_lore_keeper_agent),
        ("ContextSynthesizerAgent", test_context_synthesizer_agent),
        ("错误处理机制", test_error_handling),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} 测试过程中发生异常: {e}")
            results[test_name] = False
    
    # 汇总结果
    print(f"\n{'='*50}")
    print("📊 测试结果汇总")
    print(f"{'='*50}")
    
    passed = 0
    total = len(tests)
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n总计: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！ChromaDB修复功能正常工作。")
        print("现在可以安全地运行小说生成系统了。")
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败。")
        print("建议检查错误信息并重新运行修复脚本。")
        print("\n🔧 修复建议:")
        print("1. 运行 python fix_chromadb_issues.py")
        print("2. 检查环境变量配置")
        print("3. 确保所有依赖包已正确安装")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
