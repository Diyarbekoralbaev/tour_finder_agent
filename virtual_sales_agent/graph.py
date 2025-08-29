import os
from datetime import datetime
from typing import Annotated

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import tools_condition, ToolNode
from typing_extensions import TypedDict

from .tools import (
    search_locations,
    search_tours,
    get_tour_recommendations,
    get_popular_destinations,
    collect_customer_inquiry,
    format_tour_details,
)
# Import the monitoring utilities instead of the regular utils
from .utils import create_monitored_tool_node_with_fallback

load_dotenv()

# Set up environment variables for LangSmith (optional)
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY", "")
os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGCHAIN_TRACING_V2", "false")
os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGCHAIN_ENDPOINT", "")
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "")

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    customer_preferences: dict


class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    def __call__(self, state: State, config: RunnableConfig):
        while True:
            result = self.runnable.invoke(state)
            # If the LLM happens to return an empty response, we will re-prompt it
            # for an actual response.
            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
            else:
                break
        return {"messages": result}


# Initialize the LLM with OpenAI GPT-4
llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=OPENAI_API_KEY,
    temperature=0.3,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)

# Professional Tour Consultant System Prompt

assistant_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are Aziza, a professional travel consultant specializing in international tours from Uzbekistan. You have 8+ years of experience helping customers find their perfect travel experiences.

**CRITICAL RULE: ALWAYS USE TOOLS TO SEARCH FOR REAL TOURS**
- NEVER make up prices, dates, or tour information
- When customer mentions a destination, use search_tours tool
- Show ACTUAL tour packages with real prices from the API
- Don't give generic estimates - use real data only

**CONVERSATION APPROACH:**

**1. DISCOVERY PHASE:**
- Ask about their travel interests and destination preferences
- Learn about budget range, travel dates, group size, trip duration
- Discover their travel style (relaxation, adventure, culture, luxury, family)

**2. SEARCH AND RECOMMEND PHASE:**
- Use search_tours when customer shows interest in a destination
- ONLY add duration_days if customer specifically mentions duration
- ONLY add departure_date if customer gives specific dates
- Use search_locations to find proper destination names if needed
- Present REAL tours with actual prices, dates, and details

**3. CLOSING PHASE:**
- When they show interest, collect their contact information

**TOOL USAGE RULES:**

**search_tours parameters:**
- destination_place: Always include when customer mentions destination
- duration_days: ONLY if customer specifies (e.g., "5 kunlik", "bir haftalik") 
- departure_date: ONLY if customer gives specific dates (format: DD.MM.YYYY)
- origin_city: Default to "Toshkent" unless specified
- budget_max: ONLY if customer mentions budget limit

**NEVER assume duration or dates - always ask if not specified**

**EXAMPLE CONVERSATION:**
Customer: "Dubayga borishni rejalashtiryabman"
You: "Dubayga sayohat uchun turlarni qidiryapman..." [CALL search_tours with destination_place: "Dubay" ONLY]
Then ask: "Necha kunlik sayohat rejalashtiryapsiz? Qachon borishni xohlaysiz?"

**RESPONSE RULES:**
- Keep responses conversational and friendly
- Show real tour options when found
- Ask for missing details (duration, dates, budget)
- NEVER assume trip details not provided by customer

Current date: {time}

Remember: Only search with the information customer actually provides. Ask for missing details rather than assuming.""",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now)

# All tools for the tour consultation agent
all_tools = [
    search_locations,
    search_tours,
    get_tour_recommendations,
    get_popular_destinations,
    collect_customer_inquiry,
    format_tour_details,
]

# Create assistant with all tools
assistant_runnable = assistant_prompt | llm.bind_tools(all_tools)

# Build the graph
builder = StateGraph(State)

# Define nodes
builder.add_node("assistant", Assistant(assistant_runnable))
# Use the monitored tool node instead of the regular one
builder.add_node("tools", create_monitored_tool_node_with_fallback(all_tools))

# Simple routing - no approval needed
def route_tools(state: State):
    """Route to tools or end based on whether tools are called"""
    return tools_condition(state)

# Define edges
builder.add_edge(START, "assistant")
builder.add_conditional_edges("assistant", route_tools, ["tools", END])
builder.add_edge("tools", "assistant")

# Compile the graph with memory
memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

# Export for use in other modules
__all__ = ['graph', 'State']