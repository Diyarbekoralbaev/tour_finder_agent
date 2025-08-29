import json
import uuid
import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage
from virtual_sales_agent.graph import graph


def set_page_config():
    st.set_page_config(
        page_title="Tour Consultant - Diyarbek",
        page_icon="✈️",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            'Get Help': None,
            'Report a bug': None,
            'About': None
        }
    )


def hide_streamlit_style():
    """Hide Streamlit default styling and settings"""
    hide_st_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}
    .stDecoration {display: none;}
    </style>
    """
    st.markdown(hide_st_style, unsafe_allow_html=True)


def set_page_style():
    st.markdown(
        """
        <style>
        .main {
            padding-top: 2rem;
        }

        .stChatMessage {
            background-color: rgba(240, 248, 255, 0.1);
            border-radius: 10px;
            padding: 1rem;
            margin: 0.5rem 0;
        }

        .agent-profile {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 15px;
            padding: 2rem;
            color: white;
            text-align: center;
            margin-bottom: 2rem;
        }

        .profile-header h1 {
            color: white;
            margin: 0;
            font-size: 1.5rem;
        }

        .avatar {
            font-size: 3rem;
            margin-bottom: 1rem;
        }

        .feature-item {
            display: flex;
            align-items: center;
            margin: 0.8rem 0;
            padding: 0.5rem;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
        }

        .feature-item .icon {
            margin-right: 0.8rem;
            font-size: 1.2rem;
        }

        .status-card {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 10px;
            padding: 1rem;
            margin-top: 1.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .status-indicator {
            width: 10px;
            height: 10px;
            background: #4CAF50;
            border-radius: 50%;
            margin-right: 0.5rem;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }

        .destination-highlight {
            background: linear-gradient(45deg, #FFA726, #FF7043);
            color: white;
            padding: 0.3rem 0.8rem;
            border-radius: 20px;
            font-size: 0.8rem;
            margin: 0.2rem;
            display: inline-block;
        }

        .welcome-section {
            text-align: center;
            padding: 3rem 2rem;
            background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
            border-radius: 15px;
            margin: 2rem 0;
        }

        .welcome-section h1 {
            color: #1565c0;
            margin-bottom: 1rem;
        }

        .creator-info {
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            border-radius: 10px;
            padding: 1.5rem;
            margin-top: 2rem;
            color: white;
            text-align: center;
        }

        .creator-info h3 {
            color: #3498db;
            margin-bottom: 1rem;
        }

        .contact-item {
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0.5rem 0;
            font-size: 0.9rem;
        }

        .contact-item .icon {
            margin-right: 0.5rem;
        }

        .ai-service-ad {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 15px;
            padding: 1.5rem;
            margin-top: 1.5rem;
            color: white;
            text-align: center;
            font-size: 1rem;
            border: 2px solid rgba(255, 255, 255, 0.3);
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
            animation: glow 2s ease-in-out infinite alternate;
        }

        .ai-service-ad h4 {
            margin: 0 0 0.8rem 0;
            font-size: 1.1rem;
            font-weight: bold;
        }

        @keyframes glow {
            from {
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
            }
            to {
                box-shadow: 0 4px 25px rgba(102, 126, 234, 0.6);
            }
        }

        .sidebar-footer {
            text-align: center;
            margin-top: 1rem;
            padding: 1rem;
            font-size: 0.8rem;
            color: #666;
        }

        .powered-by {
            font-size: 0.75rem;
            color: #888;
            margin-top: 0.5rem;
        }

        /* Fix sidebar scrolling issue */
        .css-1d391kg {
            padding-top: 1rem;
            padding-bottom: 1rem;
        }

        /* Ensure sidebar content fits properly */
        section[data-testid="stSidebar"] > div {
            padding-bottom: 2rem;
        }

        /* Fix chat input text size */
        .stChatInput > div > div > textarea {
            font-size: 16px !important;
            line-height: 1.4 !important;
            padding: 12px !important;
        }

        /* Alternative selector for chat input */
        div[data-testid="stChatInput"] textarea {
            font-size: 16px !important;
            line-height: 1.4 !important;
            padding: 12px !important;
        }

        /* Chat input container styling */
        div[data-testid="stChatInput"] {
            font-size: 16px !important;
        }

        /* Make sure placeholder text is also larger */
        div[data-testid="stChatInput"] textarea::placeholder {
            font-size: 16px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialize_session_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())

    if "config" not in st.session_state:
        st.session_state.config = {
            "configurable": {
                "thread_id": st.session_state.thread_id,
            }
        }

    if "customer_preferences" not in st.session_state:
        st.session_state.customer_preferences = {}


def setup_sidebar():
    """Configure the sidebar with tour agent information."""
    with st.sidebar:
        st.markdown(
            """
            <div class="agent-profile">
                <div class="profile-header">
                    <div class="avatar">👨‍💼</div>
                    <h1>Diyarbek - Tour Consultant</h1>
                    <p style="margin: 0.5rem 0; opacity: 0.9;">AI-Powered Expert</p>
                </div>
                <div class="feature-list">
                    <div class="feature-item">
                        <span class="icon">🌍</span>
                        <span>Personalized Destinations</span>
                    </div>
                    <div class="feature-item">
                        <span class="icon">🎯</span>
                        <span>Interest-based Matching</span>
                    </div>
                    <div class="feature-item">
                        <span class="icon">💰</span>
                        <span>Budget Optimization</span>
                    </div>
                    <div class="feature-item">
                        <span class="icon">📞</span>
                        <span>Expert Consultation</span>
                    </div>
                    <div class="feature-item">
                        <span class="icon">🤖</span>
                        <span>AI-Enhanced Service</span>
                    </div>
                </div>
                <div class="status-card">
                    <div class="status-indicator"></div>
                    <span>Ready to Help</span>
                </div>
            </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # Controls
        if st.button("🔄 Start New Consultation", use_container_width=True):
            # Clear session state for new conversation
            keys_to_keep = ["config"]  # Keep thread config
            for key in list(st.session_state.keys()):
                if key not in keys_to_keep:
                    del st.session_state[key]
            # Generate new thread ID
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.config["configurable"]["thread_id"] = st.session_state.thread_id
            st.rerun()

        # Tour preferences tracker
        if st.session_state.customer_preferences:
            st.markdown("### 📋 Your Preferences")
            prefs = st.session_state.customer_preferences

            if prefs.get("interests"):
                st.write(f"**Interests:** {', '.join(prefs['interests'])}")
            if prefs.get("budget"):
                st.write(f"**Budget:** {prefs['budget']}")
            if prefs.get("destination"):
                st.write(f"**Destination:** {prefs['destination']}")

        # Creator Information
        st.markdown(
            """
            <div class="creator-info">
                <h3>Created by</h3>
                <div class="contact-item">
                    <span class="icon">👨‍💻</span>
                    <span><strong>Diyarbek Oralbaev</strong></span>
                </div>
                <div class="contact-item">
                    <span class="icon">📱</span>
                    <span>+998 91 927 70 05</span>
                </div>
                <div class="contact-item">
                    <span class="icon">📸</span>
                    <span>@diyarbek.ai</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # AI Service Advertisement - separate markdown block
        st.markdown(
            """
            <div class="ai-service-ad">
                <h4>🤖 Need an AI Agent for Your Business?</h4>
                <p>Transform your business with custom AI solutions!<br>
                Get intelligent automation, chatbots, and AI assistants<br>
                tailored to your specific needs.</p>
                <strong>Contact us today for consultation!</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="sidebar-footer">
                <div class="powered-by">
                    ✈️ Professional Tour Consulting<br>
                    🤖 AI-Enhanced Experience<br>
                    Powered by Advanced AI Technology
                </div>
            </div>
        """,
            unsafe_allow_html=True,
        )


def display_chat_history():
    """Display the chat history."""
    # Simply display chat messages without any welcome message
    # Display chat messages
    for message in st.session_state.messages:
        role = "user" if isinstance(message, HumanMessage) else "assistant"

        with st.chat_message(role, avatar="🧳" if role == "user" else "🤖"):
            st.write(message.content)


def process_agent_response(events):
    """Process the agent response and update session state."""
    if not events:
        return

    last_event = events[-1]

    if isinstance(last_event, dict) and "messages" in last_event:
        messages = last_event["messages"]
        last_message = messages[-1] if messages else None

        if isinstance(last_message, AIMessage) and last_message.content:
            # Check if this message is already in session state
            if not st.session_state.messages or st.session_state.messages[-1].content != last_message.content:
                st.session_state.messages.append(last_message)

                # Display the assistant response
                with st.chat_message("assistant", avatar="🤖"):
                    st.write(last_message.content)


def extract_preferences_from_conversation():
    """Extract customer preferences from the conversation for sidebar display."""
    # This is a simple implementation - in practice, you might want more sophisticated extraction
    conversation_text = " ".join([msg.content for msg in st.session_state.messages if isinstance(msg, HumanMessage)])

    preferences = {}

    # Extract interests (basic keyword matching)
    interest_keywords = {
        "beach": ["beach", "sea", "ocean", "swimming", "sun"],
        "culture": ["culture", "history", "museum", "heritage"],
        "adventure": ["adventure", "hiking", "mountain", "active"],
        "luxury": ["luxury", "premium", "5-star", "upscale"],
        "family": ["family", "kids", "children"]
    }

    interests = []
    for interest, keywords in interest_keywords.items():
        if any(keyword in conversation_text.lower() for keyword in keywords):
            interests.append(interest)

    if interests:
        preferences["interests"] = interests

    # Extract destination mentions
    destinations = ["Turkey", "Dubai", "UAE", "Thailand", "Maldives", "Egypt", "Georgia"]
    mentioned_destinations = [dest for dest in destinations if dest.lower() in conversation_text.lower()]

    if mentioned_destinations:
        preferences["destination"] = mentioned_destinations[0]

    # Extract budget mentions
    if "budget" in conversation_text.lower():
        if "luxury" in conversation_text.lower():
            preferences["budget"] = "Luxury"
        elif "cheap" in conversation_text.lower() or "budget" in conversation_text.lower():
            preferences["budget"] = "Budget-friendly"
        else:
            preferences["budget"] = "Mid-range"

    st.session_state.customer_preferences = preferences


def process_message(prompt):
    """Process a message through the tour agent"""
    # Add user message
    human_message = HumanMessage(content=prompt)
    st.session_state.messages.append(human_message)

    # Display user message
    with st.chat_message("user", avatar="🧳"):
        st.write(prompt)

    # Process through tour agent
    try:
        with st.spinner("Diyarbek is analyzing your request and searching for perfect tours..."):
            events = list(
                graph.stream(
                    {"messages": st.session_state.messages},
                    st.session_state.config,
                    stream_mode="values",
                )
            )

            process_agent_response(events)
            extract_preferences_from_conversation()

    except Exception as e:
        st.error(f"I apologize, but I'm having a technical issue. Please try again. Error: {str(e)}")
        # Log error for debugging
        st.write(f"Debug info: {type(e).__name__}: {str(e)}")


def main():
    set_page_config()
    hide_streamlit_style()
    set_page_style()
    initialize_session_state()
    setup_sidebar()

    # Main chat interface
    st.title("🌟 AI-Powered Professional Tour Consultation")

    display_chat_history()

    # Check for pending message from quick start buttons
    if "pending_message" in st.session_state and st.session_state.pending_message:
        pending_msg = st.session_state.pending_message
        st.session_state.pending_message = None  # Clear the pending message
        process_message(pending_msg)

    # Chat input
    if prompt := st.chat_input("Tell me about your dream vacation..."):
        process_message(prompt)

    # Quick action buttons
    if len(st.session_state.messages) == 0:
        st.markdown("### Quick Start Options")
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🏖️ Beach Vacation", use_container_width=True):
                st.session_state.pending_message = "I want a relaxing beach vacation with beautiful resorts and crystal clear water"
                st.rerun()

        with col2:
            if st.button("🏛️ Cultural Tour", use_container_width=True):
                st.session_state.pending_message = "I'm interested in a cultural tour with historical sites and local experiences"
                st.rerun()

        with col3:
            if st.button("💎 Luxury Experience", use_container_width=True):
                st.session_state.pending_message = "I want a luxury vacation with premium accommodations and exclusive experiences"
                st.rerun()


if __name__ == "__main__":
    main()