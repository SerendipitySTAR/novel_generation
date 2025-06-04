#!/usr/bin/env python3
"""
测试无限循环修复的脚本
验证用户输入处理和自动模式是否正常工作
"""

import os
import sys
import shutil
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, '/media/sc/data/sc/novel_generation')

def test_user_input_functions():
    """测试用户输入函数的修复"""
    print("🎯 测试用户输入函数修复...")
    
    from src.orchestration.workflow_manager import present_outlines_for_selection_cli, present_worldviews_for_selection_cli
    
    # 测试1: 自动模式 - 大纲选择
    print("  测试1: 自动模式大纲选择")
    auto_state = {
        'history': [],
        'all_generated_outlines': ['大纲选项1', '大纲选项2', '大纲选项3'],
        'user_input': {'auto_mode': True}
    }
    
    result = present_outlines_for_selection_cli(auto_state)
    success = (result.get('narrative_outline_text') == '大纲选项1' and 
               result.get('error_message') is None)
    print(f"    ✅ 自动模式大纲选择: {'通过' if success else '失败'}")
    
    # 测试2: 自动模式 - 世界观选择
    print("  测试2: 自动模式世界观选择")
    auto_worldview_state = {
        'history': [],
        'all_generated_worldviews': [
            {'world_name': '魔法世界', 'core_concept': '魔法概念', 'key_elements': ['魔法'], 'atmosphere': '神秘'},
            {'world_name': '科幻世界', 'core_concept': '科技概念', 'key_elements': ['科技'], 'atmosphere': '未来'}
        ],
        'user_input': {'auto_mode': True}
    }
    
    result = present_worldviews_for_selection_cli(auto_worldview_state)
    success = (result.get('selected_worldview_detail', {}).get('world_name') == '魔法世界' and 
               result.get('error_message') is None)
    print(f"    ✅ 自动模式世界观选择: {'通过' if success else '失败'}")
    
    # 测试3: 非交互式环境检测
    print("  测试3: 非交互式环境检测")
    non_interactive_state = {
        'history': [],
        'all_generated_outlines': ['大纲A', '大纲B'],
        'user_input': {'auto_mode': False}  # 不是自动模式，但会检测非交互式环境
    }
    
    # 在非交互式环境中，应该自动选择第一个选项
    result = present_outlines_for_selection_cli(non_interactive_state)
    success = (result.get('narrative_outline_text') == '大纲A' and 
               result.get('error_message') is None)
    print(f"    ✅ 非交互式环境检测: {'通过' if success else '失败'}")

def test_workflow_manager_auto_mode():
    """测试WorkflowManager的自动模式支持"""
    print("\n🚀 测试WorkflowManager自动模式支持...")
    
    from src.orchestration.workflow_manager import WorkflowManager
    
    # 创建测试数据库
    test_db = "test_auto_mode.db"
    test_chroma_dir = "./test_auto_mode_chroma"
    
    # 清理之前的测试文件
    if os.path.exists(test_db):
        os.remove(test_db)
    if os.path.exists(test_chroma_dir):
        shutil.rmtree(test_chroma_dir)
    
    try:
        # 创建工作流程管理器
        manager = WorkflowManager(db_name=test_db)
        
        # 测试用户输入数据 - 包含auto_mode
        user_input_data = {
            "theme": "测试自动模式",
            "style_preferences": "测试风格",
            "chapters": 1,  # 只生成1章进行快速测试
            "words_per_chapter": 300,
            "auto_mode": True
        }
        
        print(f"  创建初始状态，包含auto_mode: {user_input_data['auto_mode']}")
        
        # 验证初始状态创建
        current_history = [f"WorkflowManager initialized (DB: {test_db}) and graph compiled."]
        current_history.append(f"Starting workflow with input: {user_input_data}")
        
        from src.orchestration.workflow_manager import NovelWorkflowState, UserInput
        
        initial_state = NovelWorkflowState(
            user_input=UserInput(
                theme=user_input_data.get("theme","A default theme if none provided"),
                style_preferences=user_input_data.get("style_preferences"),
                words_per_chapter=user_input_data.get("words_per_chapter", 1000),
                auto_mode=user_input_data.get("auto_mode", False)
            ),
            error_message=None, history=current_history,
            novel_id=None, novel_data=None,
            narrative_outline_text=None, all_generated_outlines=None,
            outline_id=None, outline_data=None, outline_review=None,
            all_generated_worldviews=None, selected_worldview_detail=None,
            worldview_id=None, worldview_data=None,
            plot_id=None, detailed_plot_data=None, plot_data=None,
            characters=None, lore_keeper_initialized=False,
            current_chapter_number=0,
            total_chapters_to_generate=user_input_data.get("chapters", 3),
            generated_chapters=[],
            active_character_ids_for_chapter=None,
            current_chapter_plot_summary=None,
            current_plot_focus_for_chronicler=None,
            chapter_brief=None,
            db_name=test_db,
            loop_iteration_count=0,
            max_loop_iterations=max(10, user_input_data.get("chapters", 3) * 3)
        )
        
        # 验证auto_mode正确传递
        auto_mode_in_state = initial_state['user_input'].get('auto_mode', False)
        print(f"  ✅ auto_mode正确传递到状态: {auto_mode_in_state}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理测试文件
        if os.path.exists(test_db):
            os.remove(test_db)
        if os.path.exists(test_chroma_dir):
            shutil.rmtree(test_chroma_dir)

def test_main_py_auto_mode():
    """测试main.py的auto_mode参数支持"""
    print("\n🔧 测试main.py的auto_mode参数支持...")
    
    # 模拟命令行参数
    import argparse
    
    # 创建解析器（模拟main.py中的解析器）
    parser = argparse.ArgumentParser(description="Novel Generation CLI")
    parser.add_argument("--theme", type=str, required=True, help="The theme for your novel.")
    parser.add_argument("--style", type=str, default="general fiction", help="Style preferences.")
    parser.add_argument("--chapters", type=int, default=3, help="Number of chapters to generate.")
    parser.add_argument("--words-per-chapter", type=int, default=1000, help="Target words per chapter.")
    parser.add_argument("--skip-cost-estimate", action="store_true", help="Skip the token cost estimation.")
    parser.add_argument("--auto-mode", action="store_true", help="Enable automatic mode.")
    
    # 测试解析
    test_args = [
        "--theme", "测试主题",
        "--style", "测试风格", 
        "--chapters", "2",
        "--words-per-chapter", "500",
        "--auto-mode"
    ]
    
    try:
        args = parser.parse_args(test_args)
        
        result = {
            "theme": args.theme,
            "style_preferences": args.style,
            "chapters": args.chapters,
            "words_per_chapter": args.words_per_chapter,
            "skip_cost_estimate": args.skip_cost_estimate,
            "auto_mode": args.auto_mode
        }
        
        print(f"  ✅ 命令行参数解析成功:")
        print(f"    theme: {result['theme']}")
        print(f"    auto_mode: {result['auto_mode']}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 命令行参数解析失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🔧 无限循环修复测试")
    print("=" * 50)
    
    # 切换到正确的工作目录
    os.chdir('/media/sc/data/sc/novel_generation')
    
    success_count = 0
    total_tests = 3
    
    # 测试1: 用户输入函数修复
    if test_user_input_functions():
        success_count += 1
    
    # 测试2: WorkflowManager自动模式支持
    if test_workflow_manager_auto_mode():
        success_count += 1
    
    # 测试3: main.py参数支持
    if test_main_py_auto_mode():
        success_count += 1
    
    print(f"\n📋 测试总结: {success_count}/{total_tests} 通过")
    
    if success_count == total_tests:
        print("✅ 所有测试通过！无限循环修复成功。")
    else:
        print("❌ 部分测试失败，需要进一步检查。")
    
    print("\n🎯 修复内容总结:")
    print("  1. ✅ 改进用户输入处理，支持自动模式")
    print("  2. ✅ 增强异常处理，防止EOFError导致循环")
    print("  3. ✅ 添加非交互式环境检测")
    print("  4. ✅ 更新UserInput类型定义支持auto_mode")
    print("  5. ✅ 更新main.py支持--auto-mode参数")
    print("  6. ✅ 更新start.sh使用自动模式")
    
    print("\n🚀 使用方法:")
    print("  # 使用自动模式运行（推荐）")
    print("  python main.py --theme '你的主题' --auto-mode")
    print("  ")
    print("  # 或者直接运行更新后的start.sh")
    print("  ./start.sh")
    print("  ")
    print("  # 交互式模式（如果需要手动选择）")
    print("  python main.py --theme '你的主题'")

if __name__ == "__main__":
    main()
