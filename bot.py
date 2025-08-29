import asyncio
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import re

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

# Import LangGraph components
from langchain_core.messages import HumanMessage, AIMessage
from virtual_sales_agent.graph import graph

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")


# Conversation states for FSM
class TourConsultationStates(StatesGroup):
    waiting_for_interests = State()
    waiting_for_destination = State()
    waiting_for_budget = State()
    waiting_for_dates = State()
    waiting_for_contact = State()
    showing_recommendations = State()


# Global storage for conversation contexts
conversation_contexts = {}


class ConversationManager:
    """Manage Telegram conversation states and LangGraph integration"""

    @staticmethod
    def get_or_create_thread_id(user_id: int) -> str:
        """Get existing thread ID or create new one for user"""
        if user_id not in conversation_contexts:
            conversation_contexts[user_id] = {
                'thread_id': str(uuid.uuid4()),
                'messages': [],
                'preferences': {},
                'created_at': datetime.now().isoformat()
            }
        return conversation_contexts[user_id]['thread_id']

    @staticmethod
    def get_config(user_id: int) -> Dict:
        """Get LangGraph config for user conversation"""
        thread_id = ConversationManager.get_or_create_thread_id(user_id)
        return {
            "configurable": {
                "thread_id": thread_id,
            }
        }

    @staticmethod
    def add_message(user_id: int, message: Any):
        """Add message to conversation context"""
        if user_id not in conversation_contexts:
            ConversationManager.get_or_create_thread_id(user_id)
        conversation_contexts[user_id]['messages'].append({
            'content': message.content if hasattr(message, 'content') else str(message),
            'type': type(message).__name__,
            'timestamp': datetime.now().isoformat()
        })


class TourAgentProcessor:
    """Process messages through the LangGraph tour agent"""

    @staticmethod
    async def process_message(user_id: int, user_message: str, user_info: Dict = None) -> Optional[str]:
        """Process user message through LangGraph tour agent"""
        try:
            # Create contextual message with user info
            contextual_message = user_message
            context_parts = []

            if user_info:
                if user_info.get('first_name'):
                    context_parts.append(f"Customer: {user_info['first_name']}")
                if user_info.get('username'):
                    context_parts.append(f"@{user_info['username']}")
                context_parts.append("Platform: Telegram")

            # Build contextual message
            if context_parts:
                context_str = " | ".join(context_parts)
                contextual_message = f"[{context_str}] {user_message}"

            # Create human message
            human_message = HumanMessage(content=contextual_message)

            # Get configuration for this conversation
            config = ConversationManager.get_config(user_id)

            # Store message in conversation context
            ConversationManager.add_message(user_id, human_message)

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
                    # Store AI response in conversation context
                    ConversationManager.add_message(user_id, last_message)
                    return last_message.content

            return None

        except Exception as e:
            logger.error(f"Error processing message through tour agent: {str(e)}")
            return None


# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher(storage=MemoryStorage())
router = Router()


def create_interest_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for travel interests selection"""
    builder = InlineKeyboardBuilder()

    interests = [
        ("🏖️ Beach & Resort", "interest_beach"),
        ("🏛️ Culture & History", "interest_culture"),
        ("🏔️ Adventure & Nature", "interest_adventure"),
        ("💎 Luxury & Shopping", "interest_luxury"),
        ("👨‍👩‍👧‍👦 Family Friendly", "interest_family"),
        ("🍜 Food & Cuisine", "interest_food"),
        ("💒 Romantic Getaway", "interest_romance"),
        ("🧘 Wellness & Spa", "interest_wellness"),
    ]

    for text, callback_data in interests:
        builder.button(text=text, callback_data=callback_data)

    builder.button(text="✨ Surprise Me!", callback_data="interest_surprise")
    builder.adjust(2, 2, 2, 2, 1)

    return builder.as_markup()


def create_budget_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for budget selection"""
    builder = InlineKeyboardBuilder()

    budgets = [
        ("💰 Budget (Under $500)", "budget_low"),
        ("💳 Mid-Range ($500-$1000)", "budget_mid"),
        ("💎 Luxury ($1000+)", "budget_high"),
        ("🤷‍♀️ I'm Flexible", "budget_flexible"),
    ]

    for text, callback_data in budgets:
        builder.button(text=text, callback_data=callback_data)

    builder.adjust(1)
    return builder.as_markup()


def create_quick_destinations_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for popular destinations"""
    builder = InlineKeyboardBuilder()

    destinations = [
        ("🇹🇷 Turkey", "dest_turkey"),
        ("🇦🇪 UAE (Dubai)", "dest_uae"),
        ("🇹🇭 Thailand", "dest_thailand"),
        ("🇲🇻 Maldives", "dest_maldives"),
        ("🇬🇪 Georgia", "dest_georgia"),
        ("🇪🇬 Egypt", "dest_egypt"),
        ("🤔 Not Sure Yet", "dest_recommendations"),
    ]

    for text, callback_data in destinations:
        builder.button(text=text, callback_data=callback_data)

    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def format_tour_message(tour: Dict[str, Any]) -> str:
    """Format tour information for Telegram message"""

    name = tour.get('name', 'Tour Package')
    location = tour.get('locations', 'Multiple Destinations')
    operator = tour.get('organization_name', 'Tour Company')
    price = tour.get('price', 0)
    days = tour.get('days', 0)
    nights = tour.get('nights', 0)
    dates = f"{tour.get('from_date', '')} - {tour.get('to_date', '')}"

    # Clean and shorten description
    description = tour.get('description', 'Complete tour package with accommodation and transfers.')
    if len(description) > 200:
        description = description[:200] + "..."

    message = f"""🌟 *{name}*

📍 *Destination:* {location}
🏢 *Operator:* {operator}

💰 *Price:* ${price} USD
⏱️ *Duration:* {days} days / {nights} nights  
📅 *Dates:* {dates}

📝 *About:*
{description}
"""

    # Add features if available
    features = tour.get('features', [])
    if features and len(features) > 0:
        message += "\n✨ *Included:*\n"
        for feature in features[:3]:  # Show max 3 features
            message += f"• {feature.get('name', 'Service')}\n"

        if len(features) > 3:
            message += f"• ...and {len(features) - 3} more services\n"

    return message


@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """Handle /start command"""
    user_name = message.from_user.first_name or "traveler"

    welcome_text = f"""👋 Salom {user_name}! 

Men Aziza, sizning shaxsiy sayohat maslahatchi-ingizman! 8 yildan ortiq tajriba bilan O'zbekistondan jahon bo'ylab sayohatlar uyushtirib kelaman.

Men sizga eng mos kelgan turni topishda yordam beraman va orzuingizdagi sayohatni amalga oshirish uchun har qanday savollaringizga javob beraman.

Qaysi mamlakatga sayohat qilishni xohlaysiz? Yoki qiziqishlaringiz haqida gapirib bering - men sizga mukammal tavsiyalar beraman!

Boshlash uchun pastdagi tugmalardan birini tanlang:"""

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🎯 Qiziqishlarim asosida tavsiya", callback_data="start_interests")
    keyboard.button(text="🗺️ Mashhur yo'nalishlar", callback_data="start_destinations")
    keyboard.button(text="💬 Maslahatchi bilan gaplashish", callback_data="start_chat")
    keyboard.adjust(1)

    await message.answer(
        welcome_text,
        reply_markup=keyboard.as_markup()
    )


@router.callback_query(F.data == "start_interests")
async def start_interests_handler(callback: CallbackQuery, state: FSMContext):
    """Handle interests-based recommendation start"""

    await callback.message.edit_text(
        "Ajoyib! Sizning qiziqishlaringizni bilish uchun, quyidagi variantlardan sizga yoqqanlarini tanlang:\n\n"
        "Sizning sayohatda nimadan zavqlanishni xohlaysiz?",
        reply_markup=create_interest_keyboard()
    )

    await state.set_state(TourConsultationStates.waiting_for_interests)
    await callback.answer()


@router.callback_query(F.data == "start_destinations")
async def start_destinations_handler(callback: CallbackQuery):
    """Handle popular destinations selection"""

    await callback.message.edit_text(
        "Bu yerda bizning eng mashhur yo'nalishlarimiz! Qaysi biri sizni qiziqtiradi?",
        reply_markup=create_quick_destinations_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "start_chat")
async def start_chat_handler(callback: CallbackQuery):
    """Handle direct chat with consultant"""

    await callback.message.edit_text(
        "Zo'r! Men sizning shaxsiy maslahatchi-ingiz sifatida bu yerda bo'laman.\n\n"
        "Menga sayohatga oid istalgan savol bering:\n"
        "• Qaysi mamlakatga bormoqchisiz?\n"
        "• Qancha muddat sayohat qilasiz?\n"
        "• Byudjetingiz qancha?\n"
        "• Nima uchun sayohat qilasiz?\n\n"
        "Yoki shunchaki 'Dubayga bormoqchiman' deb yozing - men barchasini tushunaman! 😊"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("interest_"))
async def handle_interest_selection(callback: CallbackQuery, state: FSMContext):
    """Handle travel interest selection"""

    interest_map = {
        "interest_beach": "beach",
        "interest_culture": "culture",
        "interest_adventure": "adventure",
        "interest_luxury": "luxury",
        "interest_family": "family",
        "interest_food": "food",
        "interest_romance": "romance",
        "interest_wellness": "wellness",
        "interest_surprise": "surprise"
    }

    selected_interest = interest_map.get(callback.data, "general")

    # Store user preference
    user_data = await state.get_data()
    user_data['interests'] = [selected_interest]
    await state.set_data(user_data)

    # Process through AI agent
    user_info = {
        'first_name': callback.from_user.first_name,
        'username': callback.from_user.username
    }

    ai_message = f"I'm interested in {selected_interest} travel. Can you recommend some destinations and tours for me?"

    ai_response = await TourAgentProcessor.process_message(
        callback.from_user.id,
        ai_message,
        user_info
    )

    if ai_response:
        await callback.message.edit_text(ai_response)

        # Add budget selection keyboard
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="💰 Byudjet haqida gaplashish", callback_data="ask_budget")
        keyboard.button(text="📞 Aloqa ma'lumotlarini berish", callback_data="provide_contact")
        keyboard.adjust(1)

        await callback.message.reply("Qo'shimcha ma'lumot:", reply_markup=keyboard.as_markup())
    else:
        await callback.message.edit_text(
            "Kechirasiz, hozirda texnik muammo bor. Iltimos, keyinroq qayta urinib ko'ring yoki to'g'ridan-to'g'ri menga yozing!"
        )

    await callback.answer()


@router.callback_query(F.data.startswith("dest_"))
async def handle_destination_selection(callback: CallbackQuery):
    """Handle destination selection"""

    dest_map = {
        "dest_turkey": "Turkey",
        "dest_uae": "Dubai UAE",
        "dest_thailand": "Thailand",
        "dest_maldives": "Maldives",
        "dest_georgia": "Georgia",
        "dest_egypt": "Egypt",
        "dest_recommendations": "I need recommendations"
    }

    selected_dest = dest_map.get(callback.data, "general")

    # Process through AI agent
    user_info = {
        'first_name': callback.from_user.first_name,
        'username': callback.from_user.username
    }

    if selected_dest == "I need recommendations":
        ai_message = "I'm not sure where to travel. Can you help me choose a destination based on popular options?"
    else:
        ai_message = f"I want to travel to {selected_dest}. Can you show me available tours and tell me about this destination?"

    ai_response = await TourAgentProcessor.process_message(
        callback.from_user.id,
        ai_message,
        user_info
    )

    if ai_response:
        await callback.message.edit_text(ai_response)

        # Add action buttons
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="💰 Narxlar haqida", callback_data="ask_budget")
        keyboard.button(text="📅 Sanalar haqida", callback_data="ask_dates")
        keyboard.button(text="📞 Bog'lanish", callback_data="provide_contact")
        keyboard.adjust(2, 1)

        await callback.message.reply("Qo'shimcha yordam:", reply_markup=keyboard.as_markup())
    else:
        await callback.message.edit_text(
            "Kechirasiz, hozirda ma'lumot yuklanmayapti. Iltimos, keyinroq urinib ko'ring!"
        )

    await callback.answer()


@router.callback_query(F.data == "ask_budget")
async def ask_budget_handler(callback: CallbackQuery):
    """Handle budget inquiry"""

    await callback.message.reply(
        "Keling, byudjetingiz haqida gaplashamiz. Taxminan qancha pul sarf qilishni rejalashtiryapsiz?",
        reply_markup=create_budget_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("budget_"))
async def handle_budget_selection(callback: CallbackQuery):
    """Handle budget selection"""

    budget_map = {
        "budget_low": "under $500 - budget friendly options",
        "budget_mid": "$500-$1000 - mid-range comfort",
        "budget_high": "over $1000 - luxury travel",
        "budget_flexible": "flexible budget - show me best options"
    }

    selected_budget = budget_map.get(callback.data, "flexible")

    # Process through AI agent
    user_info = {
        'first_name': callback.from_user.first_name,
        'username': callback.from_user.username
    }

    ai_message = f"My budget is {selected_budget}. Please show me suitable tour options."

    ai_response = await TourAgentProcessor.process_message(
        callback.from_user.id,
        ai_message,
        user_info
    )

    if ai_response:
        await callback.message.edit_text(ai_response)

        # Add contact button
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="📞 Bron qilish uchun bog'lanish", callback_data="provide_contact")
        keyboard.button(text="🔄 Boshqa variantlar", callback_data="start_destinations")
        keyboard.adjust(1)

        await callback.message.reply("Keyingi qadam:", reply_markup=keyboard.as_markup())
    else:
        await callback.message.edit_text("Byudjet ma'lumotini qayta ishlashda xatolik yuz berdi.")

    await callback.answer()


@router.callback_query(F.data == "ask_dates")
async def ask_dates_handler(callback: CallbackQuery, state: FSMContext):
    """Handle date inquiry"""

    await callback.message.reply(
        "Qachon sayohat qilmoqchisiz? \n\n"
        "Masalan: 'Sentyabr oyida' yoki '15-25 oktyabr' yoki 'Qish fasli' deb yozing."
    )

    await state.set_state(TourConsultationStates.waiting_for_dates)
    await callback.answer()


@router.callback_query(F.data == "provide_contact")
async def provide_contact_handler(callback: CallbackQuery, state: FSMContext):
    """Handle contact information request"""

    await callback.message.reply(
        "Ajoyib! Sizga mos turlarni topish va batafsil ma'lumot berish uchun bog'lanish ma'lumotlaringizni qoldiring.\n\n"
        "Iltimos, quyidagicha yuboring:\n\n"
        "*Ism:* Sizning to'liq ismingiz\n"
        "*Telefon:* +998901234567\n"
        "*Izoh:* Qo'shimcha xohlagan narsalar\n\n"
        "Yoki shunchaki telefon raqamingizni yuboring - qolganini keyinroq aniqlaymiz!"
    )

    await state.set_state(TourConsultationStates.waiting_for_contact)
    await callback.answer()


@router.message(TourConsultationStates.waiting_for_dates)
async def handle_date_input(message: Message, state: FSMContext):
    """Handle date input from user"""

    user_info = {
        'first_name': message.from_user.first_name,
        'username': message.from_user.username
    }

    ai_message = f"I want to travel in {message.text}. Please show me available tours for these dates."

    ai_response = await TourAgentProcessor.process_message(
        message.from_user.id,
        ai_message,
        user_info
    )

    if ai_response:
        await message.answer(ai_response)

        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="📞 Bron qilish", callback_data="provide_contact")
        keyboard.button(text="💰 Narxlar haqida", callback_data="ask_budget")
        await message.answer("Keyingi qadam:", reply_markup=keyboard.as_markup())
    else:
        await message.answer("Sanalarni qayta ishlashda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")

    await state.clear()


@router.message(TourConsultationStates.waiting_for_contact)
async def handle_contact_input(message: Message, state: FSMContext):
    """Handle contact information input"""

    contact_text = message.text
    user_name = message.from_user.first_name or "Mijoz"

    # Try to extract phone number
    phone_pattern = r'\+?[\d\s\-\(\)]{10,20}'
    phone_match = re.search(phone_pattern, contact_text)
    phone = phone_match.group(0) if phone_match else None

    # Use telegram username as fallback
    telegram_username = f"@{message.from_user.username}" if message.from_user.username else None

    if not phone and not telegram_username:
        await message.answer(
            "Iltimos, telefon raqamingizni yoki Telegram username-ingizni qoldiring. "
            "Masalan: +998901234567"
        )
        return

    # Process through AI agent with contact collection
    user_info = {
        'first_name': message.from_user.first_name,
        'username': message.from_user.username
    }

    ai_message = f"""Please collect my contact information:
Name: {user_name}
Phone: {phone if phone else 'Not provided'}
Telegram: {telegram_username if telegram_username else 'Not provided'}
Additional notes: {contact_text}
I want to proceed with booking a tour."""

    ai_response = await TourAgentProcessor.process_message(
        message.from_user.id,
        ai_message,
        user_info
    )

    if ai_response:
        await message.answer(ai_response)

        # Success message
        await message.answer(
            "✅ *Ma'lumotlaringiz qabul qilindi!*\n\n"
            "Bizning mutaxassis maslahatchi 24 soat ichida siz bilan bog'lanadi va:\n"
            "• Sizga mos turlarni taklif qiladi\n"
            "• Batafsil dastur va narxlarni beradi\n"
            "• Barcha savollaringizga javob beradi\n\n"
            "Yangi sayohat uchun /start ni bosing!",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await message.answer(
            "Ma'lumotlaringiz qabul qilindi! Tez orada mutaxassis siz bilan bog'lanadi."
        )

    await state.clear()


@router.message()
async def handle_general_message(message: Message):
    """Handle all other messages through AI agent"""

    user_info = {
        'first_name': message.from_user.first_name,
        'username': message.from_user.username
    }

    ai_response = await TourAgentProcessor.process_message(
        message.from_user.id,
        message.text,
        user_info
    )

    if ai_response:
        await message.answer(ai_response)

        # Add helpful action buttons after AI response
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🎯 Tavsiyalar", callback_data="start_interests")
        keyboard.button(text="📞 Bog'lanish", callback_data="provide_contact")
        keyboard.adjust(2)

        await message.answer("Yordam kerakmi?", reply_markup=keyboard.as_markup())
    else:
        # Fallback response
        await message.answer(
            "Kechirasiz, sizning so'rovingizni tushunmadim. Iltimos, boshqacha so'zlab ko'ring yoki "
            "/start buyrug'ini bosing 😊"
        )


# Error handler
@router.message.exception()
async def handle_errors(update, exception):
    """Handle bot errors"""
    logger.error(f"Bot error: {exception}")
    return True


async def on_startup():
    """Bot startup actions"""
    logger.info("🤖 Tour Consultant Telegram Bot starting...")
    logger.info("✅ Bot is ready to help customers find perfect tours!")


async def on_shutdown():
    """Bot shutdown actions"""
    logger.info("🔄 Tour Consultant Bot shutting down...")


async def main():
    """Main function to run the bot"""

    # Add router to dispatcher
    dp.include_router(router)

    # Set startup and shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Start bot
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")