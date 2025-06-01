from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Annotated
import operator

# 1. Define the state
class HelloWorldState(TypedDict):
    messages: Annotated[List[str], operator.add]
    counter: int

# 2. Define nodes
def node_a(state: HelloWorldState):
    print("Executing Node A")
    new_messages = state['messages'] + ["Message from Node A"]
    counter = state.get('counter', 0) + 1
    return {"messages": new_messages, "counter": counter}

def node_b(state: HelloWorldState):
    print("Executing Node B")
    new_messages = state['messages'] + ["Message from Node B"]
    counter = state.get('counter', 0) + 1
    return {"messages": new_messages, "counter": counter}

def node_c(state: HelloWorldState):
    print("Executing Node C")
    new_messages = state['messages'] + ["Message from Node C"]
    counter = state.get('counter', 0) + 1
    # Potentially decide to end or loop based on counter
    if counter > 3:
        print("Node C: Counter exceeded 3, preparing to end.")
    return {"messages": new_messages, "counter": counter}

# 3. Define conditional logic (optional for basic hello world, but good to show)
def should_continue(state: HelloWorldState):
    print("Executing Conditional Edge 'should_continue'")
    if state['counter'] > 3:
        print("Condition: Counter > 3. Routing to END.")
        return "end_workflow"
    else:
        print(f"Condition: Counter is {state['counter']}. Routing to Node C.")
        return "continue_to_c"

if __name__ == "__main__":
    print("--- LangGraph Hello World ---")

    # 4. Build the graph
    workflow = StateGraph(HelloWorldState)

    workflow.add_node("A", node_a)
    workflow.add_node("B", node_b)
    workflow.add_node("C", node_c)

    # Set up edges
    workflow.set_entry_point("A")
    workflow.add_edge("A", "B") # A -> B
    workflow.add_edge("B", "C") # B -> C

    # Example of a conditional edge
    # After C, check condition: if counter > 3, end. Otherwise, loop back to C (or another node).
    # For this example, we'll use a simple conditional branch.
    workflow.add_conditional_edges(
        "C", # Source node
        should_continue, # Condition function
        {
            "continue_to_c": "C", # If 'continue_to_c' is returned, go to Node C (loop)
            "end_workflow": END     # If 'end_workflow' is returned, go to END
        }
    )
    # If no conditional edge from C, you would do: workflow.add_edge("C", END) for a simple linear flow.


    # 5. Compile and run
    app = workflow.compile()

    initial_state = {"messages": ["Initial Message"], "counter": 0}
    print(f"Initial state: {initial_state}")

    # Stream events to see the execution path
    # for event in app.stream(initial_state):
    #     print(f"Event: {event}")
    # print("--- Streamed execution finished ---")

    # Or invoke to get the final state
    final_state = app.invoke(initial_state, {"recursion_limit": 10}) # Added recursion_limit for loops
    print(f"Final state: {final_state}")

    print("--- LangGraph Hello World Finished ---")
