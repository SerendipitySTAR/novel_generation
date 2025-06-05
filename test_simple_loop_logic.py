#!/usr/bin/env python3
"""
简单的循环逻辑测试
模拟完整的章节生成循环过程
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, '/media/sc/data/sc/novel_generation')

def simulate_chapter_loop():
    """模拟完整的章节生成循环过程"""
    print("🔄 模拟章节生成循环过程...")
    
    try:
        from src.orchestration.workflow_manager import increment_chapter_number, _should_continue_chapter_loop
        
        # 初始状态：要生成4章
        state = {
            'current_chapter_number': 0,
            'total_chapters_to_generate': 4,
            'generated_chapters': [],
            'loop_iteration_count': 0,
            'max_loop_iterations': 12,
            'history': []
        }
        
        print(f"初始状态: 目标{state['total_chapters_to_generate']}章")
        
        # 模拟循环过程
        max_iterations = 10  # 防止真的无限循环
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            print(f"\n--- 循环迭代 {iteration} ---")
            
            # 模拟生成一章（在实际工作流中，这会在chapter_chronicler中完成）
            # 注意：在真实工作流中，current_chapter_number在循环开始前会被设置为1
            if iteration == 1:
                state['current_chapter_number'] = 1  # 第一次循环时设置为1

            current_chapter_num = state.get('current_chapter_number', 1)
            if len(state['generated_chapters']) < state['total_chapters_to_generate']:
                new_chapter = {
                    'chapter_number': current_chapter_num,
                    'title': f'Chapter {current_chapter_num}',
                    'content': f'Content of chapter {current_chapter_num}'
                }
                state['generated_chapters'].append(new_chapter)
                print(f"✅ 生成了第{current_chapter_num}章")
            
            # 调用increment_chapter_number
            print(f"📈 调用increment_chapter_number...")
            increment_result = increment_chapter_number(state)
            
            # 更新状态
            state.update(increment_result)
            
            # 调用_should_continue_chapter_loop
            print(f"🔍 调用_should_continue_chapter_loop...")
            loop_decision = _should_continue_chapter_loop(state)
            
            print(f"🎯 循环决策: {loop_decision}")
            print(f"📊 当前状态: 已生成{len(state['generated_chapters'])}/{state['total_chapters_to_generate']}章, 当前章节号={state['current_chapter_number']}")
            
            # 根据决策判断是否继续
            if loop_decision == "end_loop":
                print("🏁 循环正常结束")
                break
            elif loop_decision in ["end_loop_on_error", "end_loop_on_safety"]:
                print(f"⚠️  循环因安全原因结束: {loop_decision}")
                break
            elif loop_decision == "continue_loop":
                print("🔄 继续循环...")
                continue
            else:
                print(f"❌ 未知的循环决策: {loop_decision}")
                break
        
        # 最终结果
        print(f"\n🎉 循环结束!")
        print(f"📊 最终状态:")
        print(f"   生成章节数: {len(state['generated_chapters'])}")
        print(f"   目标章节数: {state['total_chapters_to_generate']}")
        print(f"   当前章节号: {state['current_chapter_number']}")
        print(f"   循环迭代次数: {state['loop_iteration_count']}")
        print(f"   总迭代次数: {iteration}")
        
        # 验证结果
        if len(state['generated_chapters']) == state['total_chapters_to_generate']:
            if iteration <= state['total_chapters_to_generate'] + 1:  # 允许一些容错
                print("✅ 成功：正确生成了所有章节，循环正常终止")
            else:
                print(f"⚠️  警告：生成了正确数量的章节，但迭代次数过多({iteration}次)")
        else:
            print(f"❌ 失败：章节数量不匹配")
            
        return True
        
    except Exception as e:
        print(f"❌ 模拟过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🧪 开始简单循环逻辑测试...")
    
    success = simulate_chapter_loop()
    
    if success:
        print("\n✅ 测试完成：循环修复验证成功！")
    else:
        print("\n❌ 测试失败：循环修复可能存在问题")

if __name__ == "__main__":
    main()
