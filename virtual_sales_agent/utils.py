import sys
from datetime import datetime
from typing import Any, Dict, List
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.prebuilt import ToolNode


def log_tool_call(tool_name: str, tool_args: Dict[str, Any]):
    """Log tool call to terminal with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("\n" + "=" * 60)
    print(f"🔧 TOOL CALLED: {tool_name}")
    print(f"⏰ Time: {timestamp}")
    print(f"📝 Arguments:")

    for key, value in tool_args.items():
        # Truncate long values for readability
        if isinstance(value, str) and len(value) > 100:
            display_value = value[:100] + "..."
        else:
            display_value = value
        print(f"   {key}: {display_value}")

    print("=" * 60)
    sys.stdout.flush()  # Ensure immediate output


class MonitoredToolNode(ToolNode):
    """Tool node that logs all tool calls"""

    def invoke(self, input: Dict[str, Any], config=None):
        # Get the last message which should contain tool calls
        messages = input.get("messages", [])
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                for tool_call in last_message.tool_calls:
                    tool_name = tool_call.get("name", "unknown")
                    tool_args = tool_call.get("args", {})
                    log_tool_call(tool_name, tool_args)

        # Execute the actual tool
        return super().invoke(input, config)


def handle_tool_error(state) -> dict:
    """Handle tool execution errors gracefully with logging."""
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls

    # Log the error
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n❌ TOOL ERROR at {timestamp}")
    print(f"Error: {repr(error)}")
    print("=" * 60)
    sys.stdout.flush()

    return {
        "messages": [
            ToolMessage(
                content=f"I encountered an issue: {repr(error)}\nLet me try to help you in a different way. Please provide more details about what you're looking for.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }


def create_monitored_tool_node_with_fallback(tools: list) -> MonitoredToolNode:
    """Create a monitored tool node with error handling fallback."""
    return MonitoredToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )


# Alternative: Simple function wrapper approach
def monitor_tool_calls(func):
    """Decorator to monitor individual tool calls"""

    def wrapper(*args, **kwargs):
        log_tool_call(func.__name__, kwargs)
        return func(*args, **kwargs)

    return wrapper

# Usage example for decorating individual tools:
# @monitor_tool_calls
# def search_tours(*args, **kwargs):
#     # your existing search_tours function
#     pass