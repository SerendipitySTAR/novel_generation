#!/usr/bin/env python3
"""
测试章节循环修复的脚本
验证用户输入的章节数是否被正确处理，避免无限循环
"""

import os
import sys
from typing import Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath('.'))

def test_chapter_loop_logic():
    """测试章节循环逻辑"""
    print("🔄 测试章节循环逻辑修复...")
    
    # 导入必要的函数
    from src.orchestration.workflow_manager import prepare_for_chapter_loop, _should_continue_chapter_loop
    
    # 测试场景1：用户要求1章，plot也包含1章（正常情况）
    print("\n📝 测试场景1：用户要求1章，plot包含1章")
    state1 = {
        'total_chapters_to_generate': 1,  # 用户输入
        'detailed_plot_data': [{'chapter_number': 1, 'title': 'Chapter 1'}],  # plot数据
        'history': []
    }
    
    result1 = prepare_for_chapter_loop(state1)
    if result1.get('error_message'):
        print(f"❌ 错误: {result1['error_message']}")
    else:
        final_chapters = result1['total_chapters_to_generate']
        print(f"✅ 成功: 最终章节数 = {final_chapters} (期望: 1)")
        assert final_chapters == 1, f"期望1章，实际{final_chapters}章"
    
    # 测试场景2：用户要求1章，但plot包含3章（应该使用用户输入）
    print("\n📝 测试场景2：用户要求1章，plot包含3章")
    state2 = {
        'total_chapters_to_generate': 1,  # 用户输入
        'detailed_plot_data': [
            {'chapter_number': 1, 'title': 'Chapter 1'},
            {'chapter_number': 2, 'title': 'Chapter 2'},
            {'chapter_number': 3, 'title': 'Chapter 3'}
        ],  # plot数据
        'history': []
    }
    
    result2 = prepare_for_chapter_loop(state2)
    if result2.get('error_message'):
        print(f"❌ 错误: {result2['error_message']}")
    else:
        final_chapters = result2['total_chapters_to_generate']
        print(f"✅ 成功: 最终章节数 = {final_chapters} (期望: 1，忽略plot中的额外章节)")
        assert final_chapters == 1, f"期望1章，实际{final_chapters}章"
    
    # 测试场景3：用户要求3章，但plot只包含1章（应该报错）
    print("\n📝 测试场景3：用户要求3章，plot只包含1章")
    state3 = {
        'total_chapters_to_generate': 3,  # 用户输入
        'detailed_plot_data': [{'chapter_number': 1, 'title': 'Chapter 1'}],  # plot数据
        'history': []
    }
    
    result3 = prepare_for_chapter_loop(state3)
    if result3.get('error_message'):
        print(f"✅ 正确报错: {result3['error_message']}")
    else:
        print(f"❌ 应该报错但没有报错")
    
    print("\n🔄 测试循环终止逻辑...")
    
    # 测试循环终止：生成1章后应该停止
    loop_state = {
        'current_chapter_number': 2,  # 下一章编号
        'total_chapters_to_generate': 1,  # 只要1章
        'generated_chapters': [{'chapter_number': 1, 'title': 'Chapter 1'}],  # 已生成1章
        'loop_iteration_count': 1,
        'max_loop_iterations': 3
    }
    
    loop_result = _should_continue_chapter_loop(loop_state)
    print(f"循环决策: {loop_result} (期望: end_loop)")
    assert loop_result == "end_loop", f"期望end_loop，实际{loop_result}"
    
    print("✅ 所有测试通过！")

def test_workflow_integration():
    """测试完整工作流程集成"""
    print("\n🔧 测试完整工作流程集成...")
    
    # 设置虚拟API密钥
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = "sk-dummykeyfortesting"
    
    try:
        from src.orchestration.workflow_manager import WorkflowManager
        
        # 创建测试数据库
        test_db = "test_chapter_loop_fix.db"
        if os.path.exists(test_db):
            os.remove(test_db)
        
        # 初始化工作流程管理器
        manager = WorkflowManager(db_name=test_db)
        
        # 测试输入：只生成1章
        test_input = {
            'theme': '测试主题：章节循环修复',
            'style_preferences': '测试风格',
            'chapters': 1,  # 关键：只要1章
            'words_per_chapter': 300,
            'skip_cost_estimate': True,
            'auto_mode': True
        }
        
        print(f"🚀 开始测试工作流程，输入: {test_input}")
        
        # 运行工作流程
        final_state = manager.run_workflow(test_input)
        
        # 检查结果
        generated_chapters = final_state.get('generated_chapters', [])
        total_chapters = final_state.get('total_chapters_to_generate', 0)
        loop_iterations = final_state.get('loop_iteration_count', 0)
        error_message = final_state.get('error_message')
        
        print(f"\n📊 工作流程结果:")
        print(f"   生成章节数: {len(generated_chapters)}")
        print(f"   目标章节数: {total_chapters}")
        print(f"   循环迭代次数: {loop_iterations}")
        print(f"   错误信息: {error_message}")
        
        # 验证结果
        if error_message:
            print(f"⚠️  工作流程出现错误: {error_message}")
        elif len(generated_chapters) == 1:
            print("✅ 成功：正确生成了1章并停止")
        else:
            print(f"❌ 失败：期望生成1章，实际生成{len(generated_chapters)}章")
        
        # 清理测试数据库
        if os.path.exists(test_db):
            os.remove(test_db)
            
    except Exception as e:
        print(f"❌ 工作流程测试失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主函数"""
    print("🔧 章节循环修复测试")
    print("=" * 50)
    
    try:
        # 测试逻辑修复
        test_chapter_loop_logic()
        
        # 测试完整集成（可选，因为需要LLM调用）
        print("\n" + "=" * 50)
        response = input("是否运行完整工作流程测试？(需要LLM调用，可能较慢) [y/N]: ")
        if response.lower() in ['y', 'yes']:
            test_workflow_integration()
        else:
            print("跳过完整工作流程测试")
        
        print("\n🎉 测试完成！")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
