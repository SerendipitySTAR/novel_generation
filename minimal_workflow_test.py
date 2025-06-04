
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
