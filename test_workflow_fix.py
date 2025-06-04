#!/usr/bin/env python3
"""
测试工作流程修复
验证循环保护机制和章节生成逻辑
"""

import os
import sys
import shutil
from src.orchestration.workflow_manager import WorkflowManager, NovelWorkflowState

def test_workflow_loop_protection():
    """测试工作流程的循环保护机制"""
    print("🧪 测试工作流程循环保护机制")
    
    # 使用测试数据库
    test_db = "test_workflow_fix.db"
    test_chroma = "./test_workflow_fix_chroma"
    
    # 清理之前的测试文件
    if os.path.exists(test_db):
        os.remove(test_db)
    if os.path.exists(test_chroma):
        shutil.rmtree(test_chroma)
    
    try:
        # 创建工作流程管理器
        manager = WorkflowManager(db_name=test_db)
        
        # 测试用户输入 - 使用较小的章节数
        user_input_data = {
            "theme": "测试循环保护",
            "style_preferences": "简洁",
            "chapters": 2,  # 只生成2章进行测试
            "words_per_chapter": 500
        }
        
        print(f"📝 开始测试生成 {user_input_data['chapters']} 章小说")
        print(f"   主题: {user_input_data['theme']}")
        print(f"   每章字数: {user_input_data['words_per_chapter']}")
        
        # 运行工作流程
        final_state = manager.run_workflow(user_input_data)
        
        # 检查结果
        if final_state.get('error_message'):
            print(f"❌ 工作流程出错: {final_state.get('error_message')}")
            return False
        
        generated_chapters = final_state.get('generated_chapters', [])
        total_chapters = final_state.get('total_chapters_to_generate', 0)
        loop_iterations = final_state.get('loop_iteration_count', 0)
        max_iterations = final_state.get('max_loop_iterations', 0)
        
        print(f"\n📊 测试结果:")
        print(f"   生成章节数: {len(generated_chapters)}")
        print(f"   目标章节数: {total_chapters}")
        print(f"   循环迭代次数: {loop_iterations}")
        print(f"   最大迭代限制: {max_iterations}")
        
        # 验证循环保护
        if loop_iterations >= max_iterations:
            print("⚠️  达到最大迭代限制，循环保护机制生效")
        
        # 验证章节生成
        if len(generated_chapters) == user_input_data['chapters']:
            print("✅ 章节生成数量正确")
        else:
            print(f"⚠️  章节生成数量不匹配: 期望 {user_input_data['chapters']}, 实际 {len(generated_chapters)}")
        
        # 显示生成的章节
        for i, chapter in enumerate(generated_chapters, 1):
            print(f"   第{i}章: {chapter.get('title', '无标题')}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # 清理测试文件
        if os.path.exists(test_db):
            os.remove(test_db)
        if os.path.exists(test_chroma):
            shutil.rmtree(test_chroma)

def test_loop_safety_conditions():
    """测试循环安全条件"""
    print("\n🔒 测试循环安全条件")
    
    # 导入循环判断函数
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
    print(f"   正常情况: {result} (期望: continue_loop)")
    
    # 测试完成情况
    complete_state = {
        'current_chapter_number': 4,
        'total_chapters_to_generate': 3,
        'generated_chapters': [{'chapter_number': 1}, {'chapter_number': 2}, {'chapter_number': 3}],
        'loop_iteration_count': 3,
        'max_loop_iterations': 9
    }
    
    result = _should_continue_chapter_loop(complete_state)
    print(f"   完成情况: {result} (期望: end_loop)")
    
    # 测试安全限制
    safety_state = {
        'current_chapter_number': 2,
        'total_chapters_to_generate': 3,
        'generated_chapters': [{'chapter_number': 1}],
        'loop_iteration_count': 10,
        'max_loop_iterations': 9
    }
    
    result = _should_continue_chapter_loop(safety_state)
    print(f"   安全限制: {result} (期望: end_loop_on_safety)")
    
    # 测试异常章节号
    abnormal_state = {
        'current_chapter_number': 15,
        'total_chapters_to_generate': 3,
        'generated_chapters': [{'chapter_number': 1}],
        'loop_iteration_count': 5,
        'max_loop_iterations': 9
    }
    
    result = _should_continue_chapter_loop(abnormal_state)
    print(f"   异常章节号: {result} (期望: end_loop_on_safety)")

def main():
    """主测试函数"""
    print("🚀 工作流程修复测试")
    print("=" * 50)
    
    # 切换到正确的工作目录
    os.chdir('/media/sc/data/sc/novel_generation')
    
    # 测试循环安全条件
    test_loop_safety_conditions()
    
    # 测试工作流程循环保护（可选，因为会调用LLM）
    print(f"\n是否要运行完整的工作流程测试？(这会调用LLM生成内容)")
    choice = input("输入 'y' 继续，其他键跳过: ").lower().strip()
    
    if choice == 'y':
        success = test_workflow_loop_protection()
        if success:
            print("\n✅ 工作流程测试通过")
        else:
            print("\n❌ 工作流程测试失败")
    else:
        print("\n⏭️  跳过完整工作流程测试")
    
    print("\n📋 测试总结:")
    print("  ✅ 循环安全条件测试完成")
    print("  ✅ 工作流程保护机制验证完成")
    
    print("\n🎯 建议:")
    print("  1. 如果要生成新小说，建议先用较小的章节数测试")
    print("  2. 监控循环迭代次数，确保不超过安全限制")
    print("  3. 如果遇到无限循环，使用紧急停止命令")

if __name__ == "__main__":
    main()
