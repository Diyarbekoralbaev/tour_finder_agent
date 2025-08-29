import json
import uuid

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage

from virtual_sales_agent.graph import graph


def set_page_config():
    st.set_page_config(
        page_title="Tour Consultant - Aziza",
        page_icon="✈️",
        layout="wide",
        initial_sidebar_state="expanded",
    )


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

        .sidebar-footer {
            text-align: center;
            margin-top: 2rem;
            padding: 1rem;
            font-size: 0.8rem;
            color: #666;
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
                    <div class="avatar">👩‍💼</div>
                    <h1>Aziza - Tour Consultant</h1>
                    <p style="margin: 0.5rem 0; opacity: 0.9;">8+ Years Experience</p>
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

        # Popular Destinations
        st.markdown("### 🔥 Popular Destinations")
        destinations = ["Turkey", "UAE", "Thailand", "Maldives", "Egypt", "Georgia"]
        destination_html = "".join([f'<span class="destination-highlight">{dest}</span>' for dest in destinations])
        st.markdown(destination_html, unsafe_allow_html=True)

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

        st.markdown(
            """
            <div class="sidebar-footer">
                <div class="powered-by">
                    ✈️ Professional Tour Consulting<br>
                    🤖 AI-Enhanced Experience
                </div>
            </div>
        """,
            unsafe_allow_html=True,
        )


def display_chat_history():
    """Display the chat history."""
    if not st.session_state.messages:
        st.markdown(
            """
            <div class="welcome-section">
                <h1>👋 Salom! I'm Aziza, your personal tour consultant</h1>
                <p style="font-size: 1.1rem; color: #424242;">
                    With 8+ years of experience, I'll help you find the perfect international tour from Uzbekistan. 
                    Whether you're dreaming of Turkish beaches, Dubai luxury, or Maldivian paradise - let's make it happen!
                </p>
                <p style="color: #666; margin-top: 1rem;">
                    Tell me about your travel dreams, and I'll create the perfect recommendations for you.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Display chat messages
    for message in st.session_state.messages:
        role = "user" if isinstance(message, HumanMessage) else "assistant"

        with st.chat_message(role, avatar="🧳" if role == "user" else "👩‍💼"):
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
                with st.chat_message("assistant", avatar="👩‍💼"):
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


def main():
    set_page_config()
    set_page_style()
    initialize_session_state()
    setup_sidebar()

    # Main chat interface
    st.title("🌟 Professional Tour Consultation")

    display_chat_history()

    # Chat input
    if prompt := st.chat_input("Tell me about your dream vacation..."):
        # Add user message
        human_message = HumanMessage(content=prompt)
        st.session_state.messages.append(human_message)

        # Display user message
        with st.chat_message("user", avatar="🧳"):
            st.write(prompt)

        # Process through tour agent
        try:
            with st.spinner("Aziza is thinking about your perfect tour..."):
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

    # Quick action buttons
    if len(st.session_state.messages) == 0:
        st.markdown("### Quick Start Options")
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🏖️ Beach Vacation", use_container_width=True):
                prompt = "I want a relaxing beach vacation with beautiful resorts and crystal clear water"
                st.session_state.messages.append(HumanMessage(content=prompt))
                st.rerun()

        with col2:
            if st.button("🏛️ Cultural Tour", use_container_width=True):
                prompt = "I'm interested in a cultural tour with historical sites and local experiences"
                st.session_state.messages.append(HumanMessage(content=prompt))
                st.rerun()

        with col3:
            if st.button("💎 Luxury Experience", use_container_width=True):
                prompt = "I want a luxury vacation with premium accommodations and exclusive experiences"
                st.session_state.messages.append(HumanMessage(content=prompt))
                st.rerun()


if __name__ == "__main__":
    main()