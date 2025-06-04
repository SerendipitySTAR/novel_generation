#!/usr/bin/env python3
"""
测试动态token计算功能的独立脚本
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.utils.token_calculator import NovelGenerationCostEstimator
from src.utils.dynamic_token_config import DynamicTokenConfig

def test_cost_estimation():
    """测试成本估算功能"""
    print("=== 测试Token成本估算功能 ===\n")
    
    estimator = NovelGenerationCostEstimator()
    
    # 测试不同配置
    test_configs = [
        {
            'name': '小型小说 (3章, 800字/章)',
            'config': {
                'theme': '一个侦探调查时间异常的城市',
                'style_preferences': '科幻悬疑',
                'chapters': 3,
                'words_per_chapter': 800
            }
        },
        {
            'name': '中型小说 (5章, 1200字/章)',
            'config': {
                'theme': 'A detective investigating anomalies in a city where time flows differently',
                'style_preferences': 'noir mystery with sci-fi elements',
                'chapters': 5,
                'words_per_chapter': 1200
            }
        },
        {
            'name': '大型小说 (10章, 1500字/章)',
            'config': {
                'theme': 'An epic fantasy adventure in a world where magic and technology coexist',
                'style_preferences': 'epic fantasy with steampunk elements, detailed world-building',
                'chapters': 10,
                'words_per_chapter': 1500
            }
        }
    ]
    
    for test_case in test_configs:
        print(f"--- {test_case['name']} ---")
        config = test_case['config']
        
        try:
            result = estimator.estimate_full_workflow_cost(config)
            
            print(f"主题: {config['theme'][:50]}...")
            print(f"风格: {config['style_preferences']}")
            print(f"章节数: {config['chapters']}")
            print(f"每章字数: {config['words_per_chapter']}")
            print(f"总预估tokens: {result['total_tokens']:,}")
            print(f"  - 输入tokens: {result['total_input_tokens']:,}")
            print(f"  - 输出tokens: {result['total_output_tokens']:,}")
            print(f"预估成本: ${result['estimated_cost_usd']:.2f} USD")
            
            print("\n详细分解:")
            for est in result['estimates']:
                print(f"  {est.operation_name}: {est.total_tokens:,} tokens (${est.estimated_cost_usd:.2f})")
            
        except Exception as e:
            print(f"错误: {e}")
        
        print("\n" + "="*60 + "\n")

def test_dynamic_token_config():
    """测试动态token配置功能"""
    print("=== 测试动态Token配置功能 ===\n")
    
    config = DynamicTokenConfig()
    
    # 测试不同Agent的token计算
    test_cases = [
        {
            'agent': 'narrative_pathfinder',
            'context': {
                'theme': '一个侦探调查时间异常的城市',
                'style': '科幻悬疑'
            }
        },
        {
            'agent': 'plot_architect',
            'context': {
                'outline': '这是一个关于时间异常的故事大纲，包含了复杂的情节设置和人物关系。',
                'worldview': '未来世界中时间流动异常，不同区域有不同的时间流速。',
                'num_chapters': 5
            }
        },
        {
            'agent': 'chapter_chronicler',
            'context': {
                'brief': '这是第一章的简介，包含了人物介绍和场景设置。',
                'words_per_chapter': 1200
            }
        }
    ]
    
    for test_case in test_cases:
        agent_name = test_case['agent']
        context = test_case['context']
        
        try:
            tokens = config.get_tokens_for_agent(agent_name, context)
            print(f"Agent: {agent_name}")
            print(f"计算的max_tokens: {tokens:,}")
            print(f"上下文: {context}")
            print()
        except Exception as e:
            print(f"Agent {agent_name} 错误: {e}")
            print()

def compare_old_vs_new():
    """比较旧的硬编码方式与新的动态计算方式"""
    print("=== 硬编码 vs 动态计算对比 ===\n")
    
    config = DynamicTokenConfig()
    
    # 旧的硬编码值
    old_values = {
        'narrative_pathfinder': 32768,
        'plot_architect': 32768,
        'chapter_chronicler': 32768,
        'character_sculptor': 32768
    }
    
    # 测试上下文
    test_context = {
        'narrative_pathfinder': {
            'theme': '一个侦探调查时间异常的城市',
            'style': '科幻悬疑'
        },
        'plot_architect': {
            'outline': '详细的故事大纲，包含主要情节线和人物发展',
            'worldview': '科幻世界设定，时间异常现象',
            'num_chapters': 5
        },
        'chapter_chronicler': {
            'brief': '章节简介和背景信息',
            'words_per_chapter': 1000
        },
        'character_sculptor': {
            'outline': '故事大纲',
            'worldview': '世界观设定',
            'plot': '情节摘要',
            'num_characters': 3
        }
    }
    
    print(f"{'Agent':<20} {'旧值(硬编码)':<15} {'新值(动态)':<15} {'节省率':<10}")
    print("-" * 65)
    
    total_old = 0
    total_new = 0
    
    for agent_name in old_values:
        old_tokens = old_values[agent_name]
        context = test_context.get(agent_name, {})
        
        try:
            new_tokens = config.get_tokens_for_agent(agent_name, context)
            savings = ((old_tokens - new_tokens) / old_tokens) * 100
            
            print(f"{agent_name:<20} {old_tokens:<15,} {new_tokens:<15,} {savings:>6.1f}%")
            
            total_old += old_tokens
            total_new += new_tokens
            
        except Exception as e:
            print(f"{agent_name:<20} {old_tokens:<15,} {'错误':<15} {'N/A':<10}")
    
    print("-" * 65)
    total_savings = ((total_old - total_new) / total_old) * 100
    print(f"{'总计':<20} {total_old:<15,} {total_new:<15,} {total_savings:>6.1f}%")
    print(f"\n总token节省: {total_old - total_new:,} tokens")
    print(f"成本节省估算: ${((total_old - total_new) / 1000) * 0.03:.2f} USD (仅输入tokens)")

if __name__ == "__main__":
    print("动态Token计算系统测试\n")
    print("=" * 80)
    
    try:
        test_cost_estimation()
        test_dynamic_token_config()
        compare_old_vs_new()
        
        print("所有测试完成！")
        
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
