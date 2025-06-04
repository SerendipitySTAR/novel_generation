#!/usr/bin/env python3
"""
分析无限循环问题的脚本
深入分析工作流程的状态和边配置
"""

import os
import sys
import json
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, '/media/sc/data/sc/novel_generation')

def analyze_workflow_graph():
    """分析工作流程图的配置"""
    print("🔍 分析工作流程图配置...")
    
    from src.orchestration.workflow_manager import WorkflowManager
    
    # 创建工作流程管理器
    manager = WorkflowManager(db_name="analysis_test.db")
    
    # 获取工作流程图信息
    workflow = manager.workflow
    
    print("📊 节点列表:")
    nodes = workflow.nodes
    for node_name in nodes:
        print(f"  - {node_name}")
    
    print("\n🔗 边配置:")
    # 检查边配置
    edges = workflow.edges
    for edge in edges:
        print(f"  {edge}")
    
    print("\n🎯 入口点:")
    print("  已设置入口点（无法直接访问）")
    
    # 清理测试文件
    if os.path.exists("analysis_test.db"):
        os.remove("analysis_test.db")

def analyze_node_functions():
    """分析节点函数的返回值"""
    print("\n🔬 分析节点函数返回值...")
    
    from src.orchestration.workflow_manager import (
        execute_narrative_pathfinder_agent,
        present_outlines_for_selection_cli,
        persist_novel_record_node,
        _check_node_output
    )
    
    # 模拟状态
    test_state = {
        'history': [],
        'all_generated_outlines': ['测试大纲1', '测试大纲2'],
        'user_input': {'auto_mode': True},
        'error_message': None
    }
    
    print("  测试 present_outlines_for_selection_cli:")
    result = present_outlines_for_selection_cli(test_state)
    print(f"    返回键: {list(result.keys())}")
    print(f"    error_message: {result.get('error_message')}")
    
    print("  测试 _check_node_output:")
    check_result = _check_node_output(result)
    print(f"    路由结果: {check_result}")

def analyze_state_updates():
    """分析状态更新逻辑"""
    print("\n📝 分析状态更新逻辑...")
    
    from src.orchestration.workflow_manager import NovelWorkflowState, UserInput
    
    # 创建测试状态
    test_state = NovelWorkflowState(
        user_input=UserInput(
            theme="测试主题",
            style_preferences="测试风格",
            words_per_chapter=800,
            auto_mode=True
        ),
        error_message=None,
        history=["初始历史"],
        novel_id=None,
        novel_data=None,
        narrative_outline_text=None,
        all_generated_outlines=None,
        outline_id=None,
        outline_data=None,
        outline_review=None,
        all_generated_worldviews=None,
        selected_worldview_detail=None,
        worldview_id=None,
        worldview_data=None,
        plot_id=None,
        detailed_plot_data=None,
        plot_data=None,
        characters=None,
        lore_keeper_initialized=False,
        current_chapter_number=0,
        total_chapters_to_generate=2,
        generated_chapters=[],
        active_character_ids_for_chapter=None,
        current_chapter_plot_summary=None,
        current_plot_focus_for_chronicler=None,
        chapter_brief=None,
        db_name="test.db",
        loop_iteration_count=0,
        max_loop_iterations=6
    )
    
    print(f"  初始状态键数量: {len(test_state)}")
    print(f"  auto_mode: {test_state['user_input'].get('auto_mode')}")
    print(f"  error_message: {test_state.get('error_message')}")

def check_langgraph_version():
    """检查LangGraph版本和配置"""
    print("\n📦 检查LangGraph版本...")
    
    try:
        import langgraph
        print(f"  LangGraph版本: {langgraph.__version__}")
    except Exception as e:
        print(f"  无法获取LangGraph版本: {e}")
    
    try:
        from langgraph.graph import StateGraph, END
        print("  StateGraph和END导入成功")
    except Exception as e:
        print(f"  StateGraph导入失败: {e}")

def identify_loop_cause():
    """识别循环的可能原因"""
    print("\n🎯 识别循环可能原因...")
    
    possible_causes = [
        "1. 节点函数返回的状态更新导致工作流重新启动",
        "2. _check_node_output 函数的路由逻辑有问题",
        "3. LangGraph 的状态管理机制异常",
        "4. 某个节点没有正确设置 error_message",
        "5. 工作流程图的边配置导致意外的循环",
        "6. 数据库操作导致状态不一致",
        "7. 异常处理机制触发了重启"
    ]
    
    for cause in possible_causes:
        print(f"  {cause}")

def suggest_solutions():
    """建议解决方案"""
    print("\n💡 建议解决方案...")
    
    solutions = [
        "1. 添加工作流程状态跟踪，记录每个节点的执行",
        "2. 在关键节点添加断点和日志输出",
        "3. 检查节点函数的返回值格式",
        "4. 验证 _check_node_output 的逻辑",
        "5. 添加工作流程执行计数器防止无限循环",
        "6. 使用更简单的工作流程进行测试",
        "7. 检查 LangGraph 的文档和最佳实践"
    ]
    
    for solution in solutions:
        print(f"  {solution}")

def create_minimal_test():
    """创建最小化测试"""
    print("\n🧪 创建最小化测试...")
    
    minimal_workflow_code = '''
from langgraph.graph import StateGraph, END
from typing import TypedDict, Dict, Any

class MinimalState(TypedDict):
    step: int
    message: str
    error_message: str

def step1(state: MinimalState) -> Dict[str, Any]:
    print(f"执行步骤1，当前步骤: {state.get('step', 0)}")
    return {"step": 1, "message": "步骤1完成", "error_message": None}

def step2(state: MinimalState) -> Dict[str, Any]:
    print(f"执行步骤2，当前步骤: {state.get('step', 0)}")
    return {"step": 2, "message": "步骤2完成", "error_message": None}

def check_continue(state: MinimalState) -> str:
    if state.get("error_message"):
        return "error"
    elif state.get("step", 0) >= 2:
        return "end"
    else:
        return "continue"

# 创建最小工作流
workflow = StateGraph(MinimalState)
workflow.add_node("step1", step1)
workflow.add_node("step2", step2)

workflow.set_entry_point("step1")
workflow.add_conditional_edges("step1", check_continue, {"continue": "step2", "error": END, "end": END})
workflow.add_conditional_edges("step2", check_continue, {"continue": "step1", "error": END, "end": END})

app = workflow.compile()

# 测试运行
initial_state = MinimalState(step=0, message="开始", error_message=None)
result = app.invoke(initial_state)
print(f"最终结果: {result}")
'''
    
    print("  最小化测试代码已准备，可以单独运行验证LangGraph行为")
    
    # 保存测试代码
    with open("minimal_workflow_test.py", "w", encoding="utf-8") as f:
        f.write(minimal_workflow_code)
    
    print("  测试代码已保存到 minimal_workflow_test.py")

def main():
    """主分析函数"""
    print("🔍 无限循环问题深度分析")
    print("=" * 50)
    
    # 切换到正确的工作目录
    os.chdir('/media/sc/data/sc/novel_generation')
    
    # 执行各项分析
    analyze_workflow_graph()
    analyze_node_functions()
    analyze_state_updates()
    check_langgraph_version()
    identify_loop_cause()
    suggest_solutions()
    create_minimal_test()
    
    print("\n📋 分析总结:")
    print("  从终端输出可以看出，工作流程在完成某些节点后重新启动")
    print("  这表明问题可能在于:")
    print("    1. 节点函数的返回值格式")
    print("    2. 状态更新逻辑")
    print("    3. LangGraph的内部机制")
    
    print("\n🎯 下一步行动:")
    print("  1. 运行 minimal_workflow_test.py 验证基础LangGraph行为")
    print("  2. 在关键节点添加详细日志")
    print("  3. 检查节点函数的返回值")
    print("  4. 考虑使用更简单的工作流程结构")

if __name__ == "__main__":
    main()
