#!/usr/bin/env python3
"""
测试循环修复的验证脚本
验证章节循环是否能正确终止
"""

import os
import sys
import tempfile
import shutil
from typing import Dict, Any

def test_increment_chapter_logic():
    """测试increment_chapter_number函数的修复逻辑"""
    print("🔧 测试increment_chapter_number函数修复...")
    
    # 导入修复后的函数
    from src.orchestration.workflow_manager import increment_chapter_number
    
    # 测试场景1：已完成所有章节，不应该递增章节号
    print("\n📝 测试场景1：已完成所有章节")
    state_completed = {
        'current_chapter_number': 4,
        'total_chapters_to_generate': 4,
        'generated_chapters': [
            {'chapter_number': 1, 'title': 'Chapter 1'},
            {'chapter_number': 2, 'title': 'Chapter 2'},
            {'chapter_number': 3, 'title': 'Chapter 3'},
            {'chapter_number': 4, 'title': 'Chapter 4'}
        ],
        'loop_iteration_count': 3,
        'history': []
    }
    
    result = increment_chapter_number(state_completed)
    current_chapter = result.get('current_chapter_number')
    
    if current_chapter == 4:
        print(f"✅ 正确：章节号保持为{current_chapter}，没有递增")
    else:
        print(f"❌ 错误：章节号变为{current_chapter}，应该保持为4")
    
    # 测试场景2：还需要生成更多章节，应该递增章节号
    print("\n📝 测试场景2：还需要生成更多章节")
    state_incomplete = {
        'current_chapter_number': 2,
        'total_chapters_to_generate': 4,
        'generated_chapters': [
            {'chapter_number': 1, 'title': 'Chapter 1'},
            {'chapter_number': 2, 'title': 'Chapter 2'}
        ],
        'loop_iteration_count': 1,
        'history': []
    }
    
    result = increment_chapter_number(state_incomplete)
    current_chapter = result.get('current_chapter_number')
    
    if current_chapter == 3:
        print(f"✅ 正确：章节号递增为{current_chapter}")
    else:
        print(f"❌ 错误：章节号变为{current_chapter}，应该递增为3")

def test_should_continue_loop_logic():
    """测试_should_continue_chapter_loop函数的逻辑"""
    print("\n🔄 测试_should_continue_chapter_loop函数...")
    
    from src.orchestration.workflow_manager import _should_continue_chapter_loop
    
    # 测试场景1：已完成所有章节，应该结束循环
    print("\n📝 测试场景1：已完成所有章节")
    state_completed = {
        'current_chapter_number': 4,
        'total_chapters_to_generate': 4,
        'generated_chapters': [
            {'chapter_number': 1, 'title': 'Chapter 1'},
            {'chapter_number': 2, 'title': 'Chapter 2'},
            {'chapter_number': 3, 'title': 'Chapter 3'},
            {'chapter_number': 4, 'title': 'Chapter 4'}
        ],
        'loop_iteration_count': 4,
        'max_loop_iterations': 12
    }
    
    result = _should_continue_chapter_loop(state_completed)
    
    if result == "end_loop":
        print(f"✅ 正确：返回'{result}'，循环应该结束")
    else:
        print(f"❌ 错误：返回'{result}'，应该返回'end_loop'")
    
    # 测试场景2：还需要生成更多章节，应该继续循环
    print("\n📝 测试场景2：还需要生成更多章节")
    state_incomplete = {
        'current_chapter_number': 3,
        'total_chapters_to_generate': 4,
        'generated_chapters': [
            {'chapter_number': 1, 'title': 'Chapter 1'},
            {'chapter_number': 2, 'title': 'Chapter 2'}
        ],
        'loop_iteration_count': 2,
        'max_loop_iterations': 12
    }
    
    result = _should_continue_chapter_loop(state_incomplete)
    
    if result == "continue_loop":
        print(f"✅ 正确：返回'{result}'，循环应该继续")
    else:
        print(f"❌ 错误：返回'{result}'，应该返回'continue_loop'")

def test_mini_workflow():
    """测试一个简化的工作流程，验证循环是否正确终止"""
    print("\n🚀 测试简化工作流程...")
    
    try:
        from src.orchestration.workflow_manager import WorkflowManager
        from src.database.database_manager import DatabaseManager
        
        # 创建临时数据库
        test_db = "test_loop_fix.db"
        test_chroma_dir = "./test_loop_fix_chroma"
        
        # 清理之前的测试文件
        if os.path.exists(test_db):
            os.remove(test_db)
        if os.path.exists(test_chroma_dir):
            shutil.rmtree(test_chroma_dir)
        
        # 初始化数据库和工作流管理器
        _ = DatabaseManager(db_name=test_db)
        manager = WorkflowManager(db_name=test_db)
        
        # 测试输入：只生成1章
        test_input = {
            "theme": "测试主题",
            "style_preferences": "测试风格",
            "chapters": 1,  # 只生成1章
            "words_per_chapter": 500,
            "skip_cost_estimate": True,
            "auto_mode": True
        }
        
        print(f"🚀 开始测试工作流程，输入: {test_input}")
        
        # 运行工作流程
        final_state = manager.run_workflow(test_input)
        
        # 检查结果
        generated_chapters = final_state.get('generated_chapters', [])
        total_chapters = final_state.get('total_chapters_to_generate', 0)
        current_chapter = final_state.get('current_chapter_number', 0)
        loop_iterations = final_state.get('loop_iteration_count', 0)
        error_message = final_state.get('error_message')
        
        print(f"\n📊 工作流程结果:")
        print(f"   生成章节数: {len(generated_chapters)}")
        print(f"   目标章节数: {total_chapters}")
        print(f"   当前章节号: {current_chapter}")
        print(f"   循环迭代次数: {loop_iterations}")
        print(f"   错误信息: {error_message}")
        
        # 验证结果
        if error_message:
            print(f"⚠️  工作流程出现错误: {error_message}")
        elif len(generated_chapters) == 1 and current_chapter <= 2:  # 允许章节号为1或2
            print("✅ 成功：正确生成了1章并停止，没有陷入循环")
        else:
            print(f"❌ 失败：期望生成1章且章节号不超过2，实际生成{len(generated_chapters)}章，当前章节号{current_chapter}")
        
        # 清理测试数据库
        if os.path.exists(test_db):
            os.remove(test_db)
        if os.path.exists(test_chroma_dir):
            shutil.rmtree(test_chroma_dir)
            
    except Exception as e:
        print(f"❌ 测试工作流程时出错: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主测试函数"""
    print("🔍 开始验证循环修复...")
    
    # 测试单独的函数
    test_increment_chapter_logic()
    test_should_continue_loop_logic()
    
    # 测试完整工作流程
    test_mini_workflow()
    
    print("\n✅ 循环修复验证完成！")

if __name__ == "__main__":
    main()
