#!/usr/bin/env python3
"""
测试ChapterChroniclerAgent解析功能的独立脚本
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agents.chapter_chronicler_agent import ChapterChroniclerAgent

def test_parsing_with_mock_responses():
    """测试不同格式的LLM响应解析"""
    print("=== 测试ChapterChroniclerAgent解析功能 ===\n")
    
    # 创建一个临时的ChapterChroniclerAgent实例用于测试解析
    class MockChapterAgent:
        def __init__(self):
            pass
        
        def _parse_llm_response(self, llm_response: str, novel_id: int, chapter_number: int):
            # 复制ChapterChroniclerAgent的解析逻辑
            from src.agents.chapter_chronicler_agent import ChapterChroniclerAgent
            agent = ChapterChroniclerAgent.__new__(ChapterChroniclerAgent)
            return agent._parse_llm_response(llm_response, novel_id, chapter_number)
    
    mock_agent = MockChapterAgent()
    
    # 测试用例：不同格式的LLM响应
    test_cases = [
        {
            'name': '标准格式',
            'response': """Title:
时间的裂痕

Content:
白秋离站在银都的中央广场，手中的时间探测器发出微弱的嗡鸣声。这是她第一次真正感受到时间异常的存在。

"时间在这里流动得不对劲，"她对着通讯器说道，"每一秒都像是被拉长了。"

她的助手时影从阴影中走出，脸上带着担忧的表情。"我们必须小心，白秋离。这种异常可能是人为制造的。"

Summary:
白秋离在银都中央广场首次探测到时间异常，与助手时影讨论了异常的可能原因，为后续调查奠定了基础。"""
        },
        {
            'name': '格式稍有变化',
            'response': """Title: 午夜的秘密

Content: 
深夜十二点，银都的街道变得异常安静。白秋离穿过空旷的街道，她知道时间回潮即将开始。

她的脚步声在空旷的街道上回响，每一步都带着紧张和期待。

Summary: 白秋离在午夜时分穿过银都街道，准备迎接时间回潮现象。"""
        },
        {
            'name': '缺少Summary',
            'response': """Title:
沙漏的秘密

Content:
在地下神庙的深处，白秋离发现了古老的沙漏装置。这个装置比她想象的要复杂得多，上面刻满了她从未见过的符文。

"这些符文...它们在发光，"她轻声说道。

装置的中心有一个巨大的沙漏，里面的沙子不是普通的沙子，而是闪闪发光的时间碎片。"""
        },
        {
            'name': '混乱格式',
            'response': """这是一个关于时间异常的章节。

标题：时间猎手

白秋离是一名时间考古学家，她专门研究时间异常现象。今天，她接到了一个紧急任务。

"我们在东区发现了严重的时间扭曲，"她的上司通过通讯器说道。

白秋离立即收拾装备，准备前往现场。她知道这可能是她职业生涯中最重要的一次调查。

总结：白秋离接到紧急任务，准备调查东区的时间扭曲现象。"""
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"--- 测试用例 {i}: {test_case['name']} ---")
        print(f"输入响应长度: {len(test_case['response'])} 字符")
        print(f"输入响应预览: {test_case['response'][:100]}...")
        print()
        
        try:
            result = mock_agent._parse_llm_response(test_case['response'], 1, i)
            
            if result:
                print("✅ 解析成功!")
                print(f"标题: {result['title']}")
                print(f"内容长度: {len(result['content'])} 字符")
                print(f"内容预览: {result['content'][:100]}...")
                print(f"摘要: {result['summary']}")
            else:
                print("❌ 解析失败!")
                
        except Exception as e:
            print(f"❌ 解析出错: {e}")
        
        print("\n" + "="*60 + "\n")

def test_prompt_generation():
    """测试prompt生成功能"""
    print("=== 测试Prompt生成功能 ===\n")
    
    try:
        # 创建一个临时的ChapterChroniclerAgent实例
        class MockPromptAgent:
            def _construct_prompt(self, chapter_brief: str, current_chapter_plot_summary: str, 
                                style_preferences: str, words_per_chapter: int = 1000) -> str:
                from src.agents.chapter_chronicler_agent import ChapterChroniclerAgent
                agent = ChapterChroniclerAgent.__new__(ChapterChroniclerAgent)
                return agent._construct_prompt(chapter_brief, current_chapter_plot_summary, 
                                             style_preferences, words_per_chapter)
        
        mock_agent = MockPromptAgent()
        
        # 测试数据
        chapter_brief = """
        小说主题: 时间异常调查
        风格: 科幻悬疑
        主要人物: 白秋离 - 时间考古学家
        背景: 银都，一个存在时间回潮现象的城市
        """
        
        plot_summary = "白秋离接到调查任务，前往东区调查时间异常现象"
        style = "科幻悬疑，节奏紧凑"
        words_per_chapter = 1200
        
        prompt = mock_agent._construct_prompt(chapter_brief, plot_summary, style, words_per_chapter)
        
        print(f"生成的Prompt长度: {len(prompt)} 字符")
        print(f"包含字数要求: {'1200' in prompt}")
        print(f"包含格式要求: {'Title:' in prompt and 'Content:' in prompt and 'Summary:' in prompt}")
        print("\nPrompt预览:")
        print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
        
    except Exception as e:
        print(f"Prompt生成测试失败: {e}")

if __name__ == "__main__":
    print("ChapterChroniclerAgent解析功能测试\n")
    print("=" * 80)
    
    try:
        test_parsing_with_mock_responses()
        test_prompt_generation()
        
        print("所有测试完成！")
        
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
