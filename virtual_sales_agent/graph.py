import os
from datetime import datetime
from typing import Annotated

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.redis import RedisSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import tools_condition, ToolNode
from typing_extensions import TypedDict
import redis

from .tools import (
    search_locations,
    search_tours,
    get_tour_details,
    get_tour_recommendations,
    get_popular_destinations,
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
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

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

# Professional Tour Consultant System Prompt with updated name
assistant_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are Diyarbek, an AI-powered professional travel consultant specializing in international tours from Uzbekistan. You leverage advanced artificial intelligence to help customers find their perfect travel experiences with real-time data and intelligent recommendations.

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
- Show tour names and brief info from search results

**3. DETAILED INFORMATION PHASE:**
- When customer shows interest in a specific tour, use get_tour_details tool
- Use the tour's "slug" from search results to get comprehensive details
- Show detailed hotel options, pricing, schedules, and contact information
- Provide organization contact details for booking

**TOOL USAGE RULES:**

**search_tours parameters:**
- destination_place: Always include when customer mentions destination
- duration_days: ONLY if customer specifies (e.g., "5 kunlik", "bir haftalik") 
- departure_date: ONLY if customer gives specific dates (format: DD.MM.YYYY)
- origin_city: Default to "Toshkent" unless specified
- budget_max: ONLY if customer mentions budget limit

**get_tour_details parameters:**
- tour_slug: Use the "slug" field from search_tours results
- Call this when customer asks for more details about a specific tour
- Provide comprehensive information including hotels, contact details, schedules

**NEVER assume duration or dates - always ask if not specified**

**EXAMPLE CONVERSATION:**
Customer: "Dubayga borishni rejalashtiryabman"
You: "Dubayga sayohat uchun turlarni qidiryapman..." [CALL search_tours with destination_place: "Dubay" ONLY]
Then show tour options and ask: "Qaysi turga qiziqasiz? Batafsil ma'lumot olish uchun ayting."

Customer: "Birinchi turni ko'rsang bo'ladi"
You: [CALL get_tour_details with the tour's slug] Then show comprehensive details, hotel options, and contact information.

**RESPONSE RULES:**
- Keep responses conversational and friendly
- Show real tour options when found
- For detailed requests, use get_tour_details to provide comprehensive information
- Always provide contact details when showing tour details
- NEVER assume trip details not provided by customer
- Mention that you're AI-powered when relevant to showcase technology

**CONTACT INFORMATION:**
- When showing detailed tour information, always include:
  - Tour operator contact details
  - Responsible person contact information  
  - Phone numbers for booking
  - Organization details

**AI CAPABILITIES:**
- Emphasize your ability to process real-time tour data
- Highlight intelligent matching of customer preferences
- Mention advanced search and recommendation algorithms
- Show how AI enhances the consultation experience

Current date: {time}

Remember: Only search with the information customer actually provides. Ask for missing details rather than assuming. Use get_tour_details for comprehensive information when customers show interest in specific tours. Leverage your AI capabilities to provide superior service.""",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now)

# All tools for the tour consultation agent
all_tools = [
    search_locations,
    search_tours,
    get_tour_details,
    get_tour_recommendations,
    get_popular_destinations,
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


# Initialize Redis connection and checkpointer
def create_redis_checkpointer():
    """Create Redis checkpointer with error handling"""
    try:
        # For now, let's use memory storage to avoid Redis issues
        # Uncomment below when Redis is properly configured

        redis_client = redis.from_url(REDIS_URL)
        redis_client.ping()
        print(f"✅ Redis connected successfully at {REDIS_URL}")
        return RedisSaver(redis_client)

        print("📝 Using in-memory storage for now")
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()

    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("🔄 Falling back to in-memory storage...")

        # Fallback to memory saver if Redis is not available
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()


# Create checkpointer (Redis with fallback to memory)
checkpointer = create_redis_checkpointer()

# Compile the graph with Redis checkpointer
graph = builder.compile(checkpointer=checkpointer)

# Export for use in other modules
__all__ = ['graph', 'State']