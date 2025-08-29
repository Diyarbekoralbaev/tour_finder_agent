from flask import Flask, request, jsonify
import requests
import json
import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Import LangGraph components
from langchain_core.messages import HumanMessage, AIMessage
from virtual_sales_agent.graph import graph

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
CHATWOOT_BASE_URL = os.environ.get('CHATWOOT_BASE_URL', 'https://app.chatwoot.com')
CHATWOOT_API_TOKEN = os.environ.get('CHATWOOT_API_TOKEN')
ACCOUNT_ID = int(os.environ.get('CHATWOOT_ACCOUNT_ID', '1'))

# Conversation state storage (in production, use Redis or database)
conversation_states = {}


class ChatwootAPI:
    def __init__(self, base_url: str, api_token: str, account_id: int):
        self.base_url = base_url
        self.api_token = api_token
        self.account_id = account_id
        self.headers = {
            'api_access_token': api_token,
            'Content-Type': 'application/json'
        }

    def send_message(self, conversation_id: str, content: str, message_type: str = 'outgoing') -> Optional[Dict]:
        """Send a message to a Chatwoot conversation"""
        url = f"{self.base_url}/api/v1/accounts/{self.account_id}/conversations/{conversation_id}/messages"

        payload = {
            'content': content,
            'message_type': message_type,
            'private': False
        }

        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error sending message to conversation {conversation_id}: {e}")
            return None


# Initialize Chatwoot API
chatwoot_api = ChatwootAPI(CHATWOOT_BASE_URL, CHATWOOT_API_TOKEN, ACCOUNT_ID)


class ConversationManager:
    """Manage conversation states and LangGraph integration"""

    @staticmethod
    def get_or_create_thread_id(conversation_id: str) -> str:
        """Get existing thread ID or create new one for conversation"""
        if conversation_id not in conversation_states:
            conversation_states[conversation_id] = {
                'thread_id': str(uuid.uuid4()),
                'messages': [],
                'customer_preferences': {},
                'created_at': datetime.now().isoformat()
            }
        return conversation_states[conversation_id]['thread_id']

    @staticmethod
    def get_config(conversation_id: str) -> Dict:
        """Get LangGraph config for conversation"""
        thread_id = ConversationManager.get_or_create_thread_id(conversation_id)
        return {
            "configurable": {
                "thread_id": thread_id,
            }
        }

    @staticmethod
    def add_message(conversation_id: str, message: Any):
        """Add message to conversation state"""
        if conversation_id not in conversation_states:
            ConversationManager.get_or_create_thread_id(conversation_id)
        conversation_states[conversation_id]['messages'].append({
            'content': message.content if hasattr(message, 'content') else str(message),
            'type': type(message).__name__,
            'timestamp': datetime.now().isoformat()
        })


class TourAgentProcessor:
    """Process messages through the LangGraph tour agent"""

    @staticmethod
    def process_message(conversation_id: str, user_message: str, sender_info: Dict = None, channel_info: Dict = None) -> \
    Optional[str]:
        """
        Process user message through LangGraph tour agent and return response
        """
        try:
            # Create contextual message with sender and channel info
            contextual_message = user_message
            context_parts = []

            # Add sender context
            if sender_info:
                sender_name = sender_info.get('name', '')
                if sender_name and sender_name != 'Unknown':
                    context_parts.append(f"Customer: {sender_name}")

                # Add location context if available
                location = sender_info.get('location', '')
                if location:
                    context_parts.append(f"Location: {location}")

            # Add channel context
            if channel_info:
                channel_type = channel_info.get('channel', '')
                if 'Instagram' in channel_type:
                    context_parts.append("Platform: Instagram")
                elif 'WhatsApp' in channel_type:
                    context_parts.append("Platform: WhatsApp")
                elif 'Telegram' in channel_type:
                    context_parts.append("Platform: Telegram")

            # Build contextual message
            if context_parts:
                context_str = " | ".join(context_parts)
                contextual_message = f"[{context_str}] {user_message}"

            # Create human message
            human_message = HumanMessage(content=contextual_message)

            # Get configuration for this conversation
            config = ConversationManager.get_config(conversation_id)

            # Store message in conversation state
            ConversationManager.add_message(conversation_id, human_message)

            # Process through LangGraph with automatic tool execution
            events = list(graph.stream(
                {"messages": [human_message]},
                config,
                stream_mode="values",
            ))

            # Extract the last AI response
            last_event = events[-1] if events else None
            if last_event and "messages" in last_event:
                messages = last_event["messages"]
                last_message = messages[-1] if messages else None

                if isinstance(last_message, AIMessage) and last_message.content:
                    # Store AI response in conversation state
                    ConversationManager.add_message(conversation_id, last_message)
                    return last_message.content

            return None

        except Exception as e:
            print(f"Error processing message through tour agent: {str(e)}")
            return None


def extract_message_info(webhook_data: Dict) -> Optional[Dict]:
    """Extract relevant information from Chatwoot webhook"""
    try:
        # Check if this is a message created event
        event_type = webhook_data.get('event', '')
        if event_type not in ['message_created', 'automation_event.message_created']:
            return None

        # Get conversation ID
        conversation_id = str(webhook_data.get('id'))
        if not conversation_id:
            return None

        # Extract message details
        messages = webhook_data.get('messages', [])
        if not messages:
            return None

        message = messages[0]

        # Check message type - Chatwoot uses numeric: 0=incoming, 1=outgoing, 2=activity
        message_type = message.get('message_type', 'unknown')
        if message_type != 0 and message_type != 'incoming':
            return None

        # Extract message content
        message_content = message.get('content', '').strip()
        if not message_content:
            return None

        # Extract sender information from message sender object
        sender_info = {}
        if 'sender' in message:
            sender = message['sender']
            additional_attrs = sender.get('additional_attributes', {})

            sender_info = {
                'name': sender.get('name', 'Unknown'),
                'email': sender.get('email', ''),
                'phone': sender.get('phone_number', ''),
                'id': sender.get('id'),
                'location': additional_attrs.get('location', ''),
                'company': additional_attrs.get('company_name', '')
            }

        # Extract channel information
        channel_info = {
            'channel': webhook_data.get('channel', ''),
            'inbox_id': webhook_data.get('inbox_id'),
            'can_reply': webhook_data.get('can_reply', True)
        }

        return {
            'conversation_id': conversation_id,
            'message_content': message_content,
            'sender_info': sender_info,
            'channel_info': channel_info,
            'timestamp': message.get('created_at')
        }

    except Exception as e:
        print(f"Error extracting message info: {str(e)}")
        return None


@app.route('/webhook/chatwoot', methods=['POST'])
def handle_chatwoot_webhook():
    """Handle incoming Chatwoot webhooks and process through tour agent"""

    try:
        # Get webhook data
        webhook_data = request.get_json()

        # Extract message information
        message_info = extract_message_info(webhook_data)
        if not message_info:
            return jsonify({'status': 'ignored', 'reason': 'not a valid incoming message'}), 200

        conversation_id = message_info['conversation_id']
        user_message = message_info['message_content']
        sender_info = message_info['sender_info']
        channel_info = message_info['channel_info']

        print(f"Processing tour inquiry from {sender_info['name']} in conversation {conversation_id}: '{user_message}'")

        # Process message through tour agent
        ai_response = TourAgentProcessor.process_message(
            conversation_id,
            user_message,
            sender_info,
            channel_info
        )

        if ai_response:
            # Send response back to Chatwoot
            result = chatwoot_api.send_message(conversation_id, ai_response)

            if result:
                return jsonify({
                    'status': 'success',
                    'message': 'Tour consultant response sent',
                    'conversation_id': conversation_id
                }), 200
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to send response to Chatwoot'
                }), 500
        else:
            # Fallback response if AI fails
            sender_name = sender_info.get('name', 'there')
            fallback_message = f"Hi {sender_name}! Thanks for your interest in our tours. Let me connect you with our travel expert right away to help you plan your perfect getaway!"
            chatwoot_api.send_message(conversation_id, fallback_message)

            return jsonify({
                'status': 'fallback',
                'message': 'Sent fallback response due to AI processing error'
            }), 200

    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error processing webhook: {str(e)}'
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'chatwoot_url': CHATWOOT_BASE_URL,
        'active_conversations': len(conversation_states),
        'graph_available': bool(graph),
        'service': 'Tour Consultant Agent'
    })


@app.route('/conversations', methods=['GET'])
def list_conversations():
    """List active conversations"""
    return jsonify({
        'active_conversations': len(conversation_states),
        'conversations': {
            conv_id: {
                'thread_id': state['thread_id'],
                'message_count': len(state['messages']),
                'created_at': state['created_at'],
                'customer_preferences': state.get('customer_preferences', {})
            }
            for conv_id, state in conversation_states.items()
        }
    })


@app.route('/conversation/<conversation_id>', methods=['GET'])
def get_conversation_details(conversation_id: str):
    """Get details for a specific conversation"""
    if conversation_id in conversation_states:
        return jsonify({
            'conversation_id': conversation_id,
            'state': conversation_states[conversation_id]
        })
    else:
        return jsonify({
            'error': 'Conversation not found'
        }), 404


@app.route('/api/search_tours', methods=['POST'])
def api_search_tours():
    """API endpoint for direct tour search"""
    try:
        data = request.get_json()

        # Import search function
        from virtual_sales_agent.tools import search_tours

        result = search_tours(
            origin_city=data.get('origin_city'),
            destination_place=data.get('destination'),
            departure_date=data.get('date'),
            budget_max=data.get('budget'),
            duration_days=data.get('duration'),
            sort_by=data.get('sort', 'price_asc')
        )

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/destinations', methods=['GET'])
def api_get_destinations():
    """API endpoint to get popular destinations"""
    try:
        from virtual_sales_agent.tools import get_popular_destinations

        result = get_popular_destinations()
        return jsonify(result)

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/', methods=['GET'])
def index():
    """Basic info endpoint"""
    return jsonify({
        'service': 'Professional Tour Consultant Agent',
        'status': 'running',
        'version': '2.0.0',
        'description': 'AI-powered travel consultant specializing in international tours from Uzbekistan',
        'endpoints': {
            'webhook': '/webhook/chatwoot',
            'health': '/health',
            'conversations': '/conversations',
            'search_tours': '/api/search_tours',
            'destinations': '/api/destinations'
        },
        'features': [
            'LangGraph-powered tour consultant',
            'Personalized tour recommendations',
            'Interest-based travel matching',
            'Multi-language support (EN/UZ/RU)',
            'Real-time tour search and booking',
            'Customer preference tracking',
            'Automated lead collection'
        ],
        'destinations': [
            'Turkey', 'UAE', 'Egypt', 'Thailand', 'Maldives',
            'Georgia', 'Vietnam', 'Malaysia', 'Indonesia', 'China'
        ]
    })


if __name__ == '__main__':
    # Validate required environment variables
    if not CHATWOOT_API_TOKEN:
        print("❌ ERROR: CHATWOOT_API_TOKEN environment variable is required!")
        print("Please set it with: export CHATWOOT_API_TOKEN='your_token_here'")
        exit(1)

    print("🌟 Starting Professional Tour Consultant Agent")
    print(f"🔗 Chatwoot URL: {CHATWOOT_BASE_URL}")
    print(f"🏢 Account ID: {ACCOUNT_ID}")
    print(f"🎯 Webhook endpoint: http://localhost:5000/webhook/chatwoot")
    print(f"❤️  Health check: http://localhost:5000/health")
    print("\n✈️ Tour consultant ready to help customers find their perfect vacation!")

    # Run the Flask app
    app.run(host='0.0.0.0', port=5005, debug=False)