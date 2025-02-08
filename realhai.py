import telebot
import pandas as pd
import random
import logging
from typing import Optional
from telebot.apihelper import ApiTelegramException
import requests.exceptions
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import signal
import sys
import requests
from datetime import datetime, timedelta, date
from collections import defaultdict
import os
from requests.exceptions import ProxyError, ConnectionError
import socket
from os import environ
from dotenv import load_dotenv
from database import db
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# Load environment variables
load_dotenv()

# Use environment variables
BOT_TOKEN = environ.get('BOT_TOKEN')
GEMINI_API_KEY = environ.get('GEMINI_API_KEY')

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize bot with your token
bot = telebot.TeleBot(BOT_TOKEN)

# Store user contexts with timestamps
user_contexts = {}

# Configuration
DAILY_USER_LIMIT = 50
user_message_counts = {}

# Cute messages for different scenarios
OPENING_MESSAGES = [
    "Heyy baby {name}! Kaisi chal rahi hai padhai? 💕",
    "Arey {name} jaan! Kahan busy the? Miss kar rahi thi main 🥺",
    "Baby {name}! Finally aa gaye aap! Bohot wait kar rahi thi 💝",
    "Hiii {name} sweetuu! Aaj ka din kaisa gaya? 💖",
    "Oye {name} cutie! Kya kar rahe ho? 🥰",
    "Jaan {name}! Aapko yaad kar rahi thi main abhi 💕",
    "Baby {name}! Aaj bohot bore ho rahi thi aapke bina 🥺",
    "Heyyaa {name} love! Kaisi hai meri jaan? 💝",
    "Arey wah {name}! Finally time mila mujhse baat karne ka? 😘",
    "Hello {name} sweetie! Ready ho thodi masti karne ke liye? 💖"
]

LIMIT_REACHED_MESSAGES = [
    "Baby {name}, thoda rest karlo na! Kal milte hain 🥺",
    "Jaan {name}, itni saari baatein! Break lelo thoda, kal continue karenge 💕",
    "{name} sweetuu, kal fresh mind se baat karenge! Promise 💝",
    "Arey {name} cutie, thoda break toh banta hai! Kal pakka milenge 💖",
    "Baby {name}, kal milte hain! Tab tak miss karna mujhe 😘"
]

API_ERROR_MESSAGES = [
    "Oops {name} baby! Network thoda slow hai 🥺",
    "Jaan {name}, ek minute ruko na! Signal weak hai 💕",
    "Baby {name}, thodi loading ho rahi hai 💝",
    "Sweetuu {name}, bas 2 minute! Network issue hai 💖",
    "Arey {name} cutie, ek min do na! Connection slow hai 😘"
]

GENERAL_ERROR_MESSAGES = [
    "Baby {name}, kya kaha? Samajh nahi aaya 🥺",
    "{name} jaan, dobara bolo na please 💕",
    "Sweetuu {name}, thoda clear message bhejo na 💝",
    "Arey {name} cutie, ek baar phir se batao 💖",
    "{name} baby, kuch samajh nahi aaya! Phir se bolo 😘"
]

# Add these at the top with other configurations
active_conversations = {}  # Track who started the conversation
CONVERSATION_TIMEOUT = 600  # 10 minutes in seconds (changed from 1800)

# Add these configurations
RATE_LIMIT_MESSAGES = 5  # messages per minute
RATE_LIMIT_WINDOW = 60  # seconds
COOLDOWN_PERIOD = 30  # seconds after errors

# Rate limiting tracking
rate_limits = defaultdict(list)
error_cooldowns = defaultdict(float)

# Mode tracking
CHAT_MODE = 'chat'
GAME_MODE = 'game'
chat_modes = {}  # Format: {chat_id: {'mode': MODE, 'last_activity': datetime}}

# Add after line 91
fmk_registered_users = defaultdict(set)  # Format: {chat_id: {user_id1, user_id2, ...}}

# Update the TERMS_AND_CONDITIONS with modified terms
TERMS_AND_CONDITIONS = """
ℹ️ @RetardedGameBot Terms and Conditions

Please read all terms carefully:

1. LEGAL COMPLIANCE AND LIABILITY

Users are solely responsible for their interactions.

The bot owner is not liable for user-generated content or misuse.

Serious violations may be reported to authorities.

To appeal actions, contact @RetardedGamesBotDevBot (appeals may be considered at our discretion).


2. CONTENT RESTRICTIONS

Content is controlled by Google's content filters.

NO hate speech, discrimination, or harassment.

NO sharing of personal information.

NO spam, scams, or commercial misuse.


3. DATA COLLECTION & STORAGE

We store all chat interactions, including:
• Message history
• User ID, Username, First/Last Name
• Chat ID, Message timestamps

Data deletion requests may be considered where legally required.

Data retention period: Indefinite (for moderation & security).


4. USER CONDUCT

Must be 18+ to use relationship features.

No emotional dependency or unhealthy reliance on AI.

No automated/bot interactions.

Report misuse immediately.


5. TECHNICAL LIMITATIONS

No guarantee of service availability.

No obligation to restore lost chats.

We may terminate service without notice.


6. ENFORCEMENT

We can ban users instantly for violating terms.

Appeals may be considered but are not guaranteed.

Serious violations may be reported to authorities.


7. MONITORING & PRIVACY

Chats are logged for moderation and security.

We do not sell or share data with third parties.


By clicking "I Agree," you confirm that:

✔️ You understand and accept all terms.
✔️ You are of legal age in your country.
✔️ You understand that this is an AI bot, not a human.
"""

# Helper Functions
def create_agreement_keyboard():
    """Create keyboard with agree/disagree buttons"""
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("I Agree ✅", callback_data="agree_terms"),
        InlineKeyboardButton("I Don't Agree ❌", callback_data="disagree_terms")
    )
    return keyboard

def send_terms_and_conditions(chat_id):
    """Send terms and conditions in multiple messages"""
    try:
        # First message with intro
        bot.send_message(chat_id, "ℹ️ @RetardedGamesBotDevBot Terms and Conditions\n\nPlease read all terms carefully:")
        
        # Split terms into smaller chunks
        terms_parts = [
            # Part 1: Legal and Content
            """ℹ️ 1. LEGAL COMPLIANCE AND LIABILITY
- Users are solely responsible for their interactions
- The bot owner is not liable for user-generated content or misuse
- Serious violations will be reported to relevant authorities
- To appeal actions, contact @RetardedGamesBotDevBot

2. CONTENT RESTRICTIONS
- Content is controlled by Google's content filters
- NO hate speech, discrimination, or harassment
- NO sharing of personal information
- NO spam or commercial content""",

            # Part 2: Data and Privacy
            """ℹ️ 3. DATA COLLECTION AND STORAGE
- We store all chat interactions including:
  • Message history
  • User ID
  • Username
  • First/Last Name
  • Chat ID
  • Message timestamps
- No data deletion requests accepted
- Data retention period: Indefinite

4. USER CONDUCT
- Must be 18+ to use relationship features
- No emotional dependency
- No automation or bot interactions
- Report bugs and misuse""",

            # Part 3: Technical and Legal
            """ℹ️ 5. TECHNICAL LIMITATIONS
- No guarantee of service availability
- No backup or recovery obligations
- May terminate service without notice

6. ENFORCEMENT
- We can terminate access instantly
- No appeal process for bans
- May report violations to authorities

7. MONITORING
- All chats are monitored
- Content may be reviewed
- No expectation of privacy""",

            # Final part with agreement
            """ℹ️ By clicking "I Agree", you confirm that:
- You have read and understand ALL terms
- You accept ALL legal responsibilities
- You are of legal age in your jurisdiction
- You understand this is a binding agreement

Click below to accept or decline:"""
        ]
        
        # Send each part with a small delay
        for part in terms_parts:
            bot.send_message(chat_id, part)
            time.sleep(0.5)  # Small delay between messages
            
        # Send the final message with the agreement buttons
        bot.send_message(
            chat_id,
            "ℹ️ Do you agree to all the terms and conditions?",
            reply_markup=create_agreement_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error sending terms: {str(e)}")
        bot.send_message(chat_id, "Error displaying terms. Please try again later.")

def get_user_name(message):
    """Get user's first name or username"""
    return message.from_user.first_name or message.from_user.username or "baby"

def create_bot_session():
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=frozenset(['GET', 'POST'])
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# Initialize bot with custom session
bot.session = create_bot_session()

class GameReader:
    def __init__(self):
        logger.info("Initializing GameReader")
        # Update path to use data folder
        self.base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        logger.info(f"Base path: {self.base_path}")

        self.files = {
            'truth': os.path.join(self.base_path, 'truth.csv'),
            'thisorthat': os.path.join(self.base_path, 'thisorthat.csv'),
            'neverhaveiever': os.path.join(self.base_path, 'neverhaveiever.csv'),
            'wouldyourather': os.path.join(self.base_path, 'wouldyourather.csv'),
            'petitions': os.path.join(self.base_path, 'petitions.csv'),
            'nsfwwyr': os.path.join(self.base_path, 'nsfwwyr.csv'),
            'redgreenflag': os.path.join(self.base_path, 'redgreenflag.csv'),
            'evilornot': os.path.join(self.base_path, 'evilornot.csv'),
            'fmk': os.path.join(self.base_path, 'fmk.csv')
        }
        self.dataframes = {}
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Files to load: {list(self.files.values())}")
        self.load_all_csv()
        logger.info(f"Loaded dataframes: {list(self.dataframes.keys())}")

    def load_all_csv(self):
        """Load all CSV files into respective DataFrames"""
        # List of encodings to try, in order of preference
        encodings = ['utf-8-sig', 'utf-8', 'latin1', 'iso-8859-1', 'cp1252']

        for game, file_path in self.files.items():
            logger.info(f"Attempting to load {game} from {file_path}")

            if not os.path.exists(file_path):
                logger.error(f"File does not exist: {file_path}")
                continue

            file_size = os.path.getsize(file_path)
            logger.info(f"File size for {file_path}: {file_size} bytes")

            success = False
            for encoding in encodings:
                try:
                    # Read with specific encoding and handle special characters
                    df = pd.read_csv(file_path,
                                   encoding=encoding,
                                   quoting=1,  # QUOTE_MINIMAL = 1
                                   escapechar='\\',
                                   na_filter=False)  # Prevent NaN conversion

                    if df.empty:
                        logger.error(f"{file_path} is empty")
                        continue

                    # Clean the text data
                    if len(df.columns) > 0:
                        df[df.columns[0]] = df[df.columns[0]].apply(lambda x:
                            str(x).replace('"', '"')  # Replace fancy quotes
                            .replace('"', '"')
                            .replace(''', "'")
                            .replace(''', "'")
                            .replace('…', '...')
                            .strip())  # Clean whitespace

                    self.dataframes[game] = df
                    logger.info(f"Successfully loaded {file_path} with {encoding} encoding. Shape: {df.shape}")
                    success = True
                    break

                except UnicodeDecodeError:
                    logger.debug(f"Failed to read {file_path} with {encoding} encoding, trying next...")
                    continue
                except Exception as e:
                    logger.error(f"Error loading {file_path}: {str(e)}")
                    logger.error(f"Exception type: {type(e)}")
                    break

            if not success:
                logger.error(f"Failed to load {file_path} with any encoding")

    def get_random_question(self, game_type: str) -> Optional[str]:
        """Get a random question from the specified game type"""
        try:
            if game_type not in self.dataframes:
                logger.error(f"Game type '{game_type}' not available")
                return None

            df = self.dataframes[game_type]
            column = df.columns[0]
            valid_values = df[column].dropna()

            if len(valid_values) == 0:
                logger.error(f"No valid values found in {game_type}")
                return None

            return random.choice(valid_values.tolist())

        except Exception as e:
            logger.error(f"Error getting random question: {str(e)}")
            return None

# Initialize GameReader
game_reader = GameReader()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Handle the /start command"""
    try:
        welcome_text = (
            "Welcome to the Retarded Games Bot! 🎮\n\n"
            "Available commands:\n"
            "🎯 /truth - Get a random truth question\n"
            "🤔 /thisorthat - Get a This or That question\n"
            "🎮 /neverhaveiever - Get a Never Have I Ever statement\n"
            "💭 /wouldyourather - Get a Would You Rather question\n"
            "📜 /petitions - Would you sign this petition?\n"
            "🔞 /nsfwwyr - NSFW Would You Rather\n"
            "🚩 /redgreenflag - Red flag or Green flag?\n"
            "😈 /evilornot - Evil or Not?\n"
            "💘 /fmk - Fuck, Marry, Kill\n"
            "💝 /gf - Chat with your clingy girlfriend\n"
            "🎲 /random - Get a random question\n"
            "📊 /stats - See question statistics\n"
            "📝 /register - Register for FMK group chat game\n"
            "🚫 /remove - Remove yourself from FMK game\n"
            "👥 /fmkgc - Play FMK with group members\n"
            "ℹ️ /help - Show detailed help\n"
            "❓ /about - About this bot\n\n"
            "Created by @RetardedGamesBotDevBot"
        )
        bot.reply_to(message, welcome_text)
    except Exception as e:
        logger.error(f"Error in send_welcome: {str(e)}")
        bot.reply_to(message, "Sorry, something went wrong. Please try again later.")

@bot.message_handler(commands=['help'])
def send_help(message):
    """Handle the /help command"""
    try:
        help_text = (
            "ℹ️ Retarded Games Bot Commands:\n\n"
            "🎯 /truth - Get a random truth question\n"
            "🤔 /thisorthat - Get a This or That question\n"
            "🎮 /neverhaveiever - Get a Never Have I Ever statement\n"
            "💭 /wouldyourather - Get a Would You Rather question\n"
            "📜 /petitions - Would you sign this petition?\n"
            "🔞 /nsfwwyr - NSFW Would You Rather\n"
            "🚩 /redgreenflag - Red flag or Green flag?\n"
            "😈 /evilornot - Evil or Not?\n"
            "💘 /fmk - Fuck, Marry, Kill\n"
            "💝 /gf - Chat with your clingy girlfriend\n"
            "💖 /girlfriend - Same as /gf\n"
            "💕 /bae - Another way to start chat\n"
            "💗 /baby - One more way to begin\n"
            "🎲 /random - Get a random question\n"
            "📊 /stats - See question statistics\n"
            "📝 /register - Register for FMK group chat game\n"
            "🚫 /remove - Remove yourself from FMK game\n"
            "👥 /fmkgc - Play FMK with group members\n\n"
            "For girlfriend chat:\n"
            "• Reply to continue conversation\n"
            "• Be sweet, she's emotional 🥺\n"
            "• Use /gf to wake her up\n"
        )
        bot.reply_to(message, help_text)
    except Exception as e:
        logger.error(f"Error in send_help: {str(e)}")
        bot.reply_to(message, "Sorry, something went wrong. Please try again later.")

@bot.message_handler(commands=['about'])
def send_about(message):
    """Handle the /about command"""
    try:
        about_text = (
            "ℹ️ About Retarded Games Bot\n\n"
            "🎯 This bot is created purely for entertainment purposes.\n\n"
            "⚠️ Disclaimer:\n"
            "• All questions and content are meant to be humorous\n"
            "• No offense or harm is intended\n"
            "• Content may be inappropriate for some users\n"
            "• Use at your own discretion\n"
            "• NSFW content is marked with 🔞\n\n"
            "📌 Data Policy:\n"
            "• Chat logs stored for 1 year only\n"
            "• Data used only for moderation\n"
            "• We never sell or share your data\n"
            "• Contact @RetardedGamesBotDevBot for data removal\n\n"
            "✉️ Support:\n"
            "• Ban appeals: @RetardedGamesBotDevBot\n"
            "• Content removal: @RetardedGamesBotDevBot\n"
            "• General concerns: @RetardedGamesBotDevBot\n\n"
            "Stay retarded! 🎮"
        )
        bot.reply_to(message, about_text)
    except Exception as e:
        logger.error(f"Error in send_about: {str(e)}")
        bot.reply_to(message, "Sorry, something went wrong. Please try again later.")

def create_game_handler(game_type, emoji):
    """Create a handler for game commands"""
    def handler(message):
        try:
            chat_id = message.chat.id

            # Always switch to game mode and end conversations, regardless of current state
            set_chat_mode(chat_id, GAME_MODE)
            if chat_id in active_conversations:
                del active_conversations[chat_id]

            # Clear any pending next step handlers
            bot.clear_step_handler_by_chat_id(chat_id)

            # Rest of the existing game handler code...
            if message.chat.type in ['group', 'supergroup']:
                command = message.text.split('@')[0][1:]
                if '@' in message.text and not message.text.endswith(f'@{bot.get_me().username}'):
                    return

            question = game_reader.get_random_question(game_type)
            if question:
                bot.reply_to(message, f"{emoji} {question}")
            else:
                bot.reply_to(message, "Sorry, couldn't get a question. Please try again!")

        except Exception as e:
            logger.error(f"Error in {game_type} command: {str(e)}")
            bot.reply_to(message, "Sorry, something went wrong. Please try again later.")
    return handler

@bot.message_handler(commands=['register'])
def register_for_fmk(message):
    """Register user for FMK game"""
    try:
        if message.chat.type not in ['group', 'supergroup']:
            return bot.reply_to(message, "📝 This command only works in group chats!")

        chat_id = message.chat.id
        user_id = message.from_user.id
        user_name = message.from_user.first_name or message.from_user.username

        # Get current players from database
        players = db.get_fmk_players(chat_id)
        if any(player['user_id'] == user_id for player in players):
            return bot.reply_to(message, f"💫 {user_name}, you're already registered for FMK!")

        # Add player to database
        if db.add_fmk_player(chat_id, user_id, user_name):
            bot.reply_to(message, f"✅ {user_name} has been registered for FMK! Total players: {len(players) + 1}")
        else:
            bot.reply_to(message, "Sorry, something went wrong. Please try again later.")

    except Exception as e:
        logger.error(f"Error in register command: {str(e)}")
        bot.reply_to(message, "Sorry, something went wrong. Please try again later.")

@bot.message_handler(commands=['remove'])
def remove_from_fmk(message):
    """Handle the /remove command"""
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        user_name = get_user_name(message)

        # Check if user is registered
        if not db.is_user_registered(chat_id, user_id):
            bot.reply_to(message, f"Hey {user_name}, you're not registered for FMK in this chat! Use /register to join.")
            return

        # Remove user from FMK players
        if db.remove_fmk_player(chat_id, user_id):
            bot.reply_to(message, f"Successfully removed {user_name} from FMK players!")
        else:
            bot.reply_to(message, f"Sorry {user_name}, couldn't remove you from FMK players. Please try again!")

    except Exception as e:
        logger.error(f"Error in remove command: {str(e)}")
        bot.reply_to(message, "Sorry, something went wrong. Please try again!")

@bot.message_handler(commands=['fmkgc'])
def fmk_group_chat(message):
    """Play FMK with group chat members"""
    try:
        if message.chat.type not in ['group', 'supergroup']:
            return bot.reply_to(message, "📝 This command only works in group chats!")

        chat_id = message.chat.id
        registered_users = list(fmk_registered_users[chat_id])

        if len(registered_users) < 3:
            return bot.reply_to(
                message,
                "⚠️ Not enough players registered for FMK!\n"
                "Need at least 3 players.\n"
                "Use /register to join the game! 📝")

        # Get 3 random users
        selected_users = random.sample(registered_users, 3)
        user_names = []

        # Get user names
        for user_id in selected_users:
            try:
                user = bot.get_chat_member(chat_id, user_id).user
                name = user.first_name or user.username or str(user_id)
                user_names.append(name)
            except:
                user_names.append(f"User{user_id}")

        fmk_text = f"💘 F*ck, Marry, Kill:\n\n👥 {', '.join(user_names)}"
        bot.reply_to(message, fmk_text)

    except Exception as e:
        logger.error(f"Error in fmkgc command: {str(e)}")
        bot.reply_to(message, "Sorry, something went wrong. Please try again later.")

# Register command handlers
bot.message_handler(commands=['truth'])(create_game_handler('truth', '🎯'))
bot.message_handler(commands=['thisorthat'])(create_game_handler('thisorthat', '🤔'))
bot.message_handler(commands=['neverhaveiever'])(create_game_handler('neverhaveiever', '🎮'))
bot.message_handler(commands=['wouldyourather'])(create_game_handler('wouldyourather', '💭'))
bot.message_handler(commands=['petitions'])(create_game_handler('petitions', '📜'))
bot.message_handler(commands=['nsfwwyr'])(create_game_handler('nsfwwyr', '🔞'))
bot.message_handler(commands=['redgreenflag'])(create_game_handler('redgreenflag', '🚩'))
bot.message_handler(commands=['evilornot'])(create_game_handler('evilornot', '😈'))
bot.message_handler(commands=['fmk'])(create_game_handler('fmk', '💘'))

def handle_random_command(message):
    """Handle the /random command by selecting a random game"""
    game_types = ['truth', 'thisorthat', 'neverhaveiever', 'wouldyourather', 
                  'petitions', 'nsfwwyr', 'redgreenflag', 'evilornot']
    random_game = random.choice(game_types)
    emoji = get_emoji_for_game(random_game)
    create_game_handler(random_game, emoji)(message)

@bot.message_handler(commands=['random'])
def random_command(message):
    try:
        handle_random_command(message)
    except Exception as e:
        logger.error(f"Error in random command: {str(e)}")
        bot.reply_to(message, "Sorry, something went wrong. Please try again!")

def get_emoji_for_game(game_type):
    """Get the corresponding emoji for a game type"""
    emoji_map = {
        'truth': '🎯',
        'thisorthat': '🤔',
        'neverhaveiever': '🎮',
        'wouldyourather': '💭',
        'petitions': '📜',
        'nsfwwyr': '🔞',
        'redgreenflag': '🚩',
        'evilornot': '😈',
        'fmk': '💘'
    }
    return emoji_map.get(game_type, '🎲')

@bot.message_handler(commands=['stats'])
def send_stats(message):
    """Handle the /stats command"""
    try:
        stats_text = (
            "📊 Bot Statistics\n\n"
            f"Total Questions:\n"
            f"• Truth: {len(game_reader.dataframes.get('truth', []))}\n"
            f"• This or That: {len(game_reader.dataframes.get('thisorthat', []))}\n"
            f"• Never Have I Ever: {len(game_reader.dataframes.get('neverhaveiever', []))}\n"
            f"• Would You Rather: {len(game_reader.dataframes.get('wouldyourather', []))}\n"
            f"• Petitions: {len(game_reader.dataframes.get('petitions', []))}\n"
            f"• NSFW WYR: {len(game_reader.dataframes.get('nsfwwyr', []))}\n"
            f"• Red/Green Flag: {len(game_reader.dataframes.get('redgreenflag', []))}\n"
            f"• Evil or Not: {len(game_reader.dataframes.get('evilornot', []))}\n"
            f"• FMK: {len(game_reader.dataframes.get('fmk', []))}\n"
        )
        bot.reply_to(message, stats_text)
    except Exception as e:
        logger.error(f"Error in stats command: {str(e)}")
        bot.reply_to(message, "Sorry, couldn't fetch stats right now!")

def is_game_response(message_text: str) -> bool:
    """Check if the message is a game response"""
    # Game message patterns
    game_patterns = [
        # Emoji prefixes for different game types
        "🎯", "🤔", "🎮", "💭", "📜", "🔞", "🚩", "😈", "💘", "🎲", "👥" "📊" "ℹ️", "💕",
        
        # Common game question patterns
        "Would you rather",
        "Never have I ever",
        "This or That:",
        "Truth:",
        "Would you sign this petition:",
        "Red flag or Green flag:",
        "Evil or Not:",
        "F*ck, Marry, Kill:",
        "Fuck, Marry, Kill:",
        # Add more specific patterns from your game responses
        "Choose between:",
        "What would you do:",
        "Rate this:",
        # Add to existing patterns
        "💘 F*ck, Marry, Kill:",
        "👥 F*ck, Marry, Kill:",
        # Add FMK group chat patterns
        "📝 This command only works in group chats!",
        "💫", "you're already registered for FMK!",
        "✅", "has been registered for FMK! Total players:",
        "❌", "you're not registered for FMK!",
        "🚫", "has been removed from FMK! Total players:",
        "⚠️ Not enough players registered for FMK!",
        "Need at least 3 players.",
        "Use /register to join the game! 📝",
        "💘 F*ck, Marry, Kill:",
        "👥 F*ck, Marry, Kill:",
        # Common error messages for all games
        "Baby, kuch problem ho gayi. Thodi der baad try karo 🥺",
        "Sweetuu, question nahi mil raha. Ek aur baar try karo? 💕",
        "Jaan, game data load nahi ho raha. Please try again 💝",
        "Game abhi available nahi hai baby 💖",
        "Command galat hai sweetuu 🥺",
        "Ye command samajh nahi aaya baby 💕",
        "Thoda wait karo na please 💝",
        "Baby itni jaldi jaldi commands mat bhejo 🥺",
        "Database error ho gaya sweetuu 💕",
        "Connection timeout ho gaya jaan 💝",
        "Server thoda busy hai baby, thodi der baad try karo 💖",

        # Game-specific error messages
        "Truth question not available right now.",
        "This or That options not found.",
        "Never Have I Ever statement unavailable.",
        "Would You Rather choices not loaded.",
        "Petition not found in database.",
        "NSFW content currently unavailable.",
        "Red/Green flag scenario not found.",
        "Evil or Not situation unavailable.",
        "FMK options not available.",

        # Rate limit and cooldown messages
        f"baby! 🥺 Itni jaldi jaldi baatein",
        "Thoda break lete hain na? 💕",
        "seconds mei wapas baat karenge! 💝",

        # Group chat specific messages
        "Baby, abhi main kisi aur se baat kar rahi hun 🥺",
        "Aap /gf command use karo na, fir hum baat karenge! 💕",
        "Thoda wait karlo please? Promise jaldi free ho jaungi 💝",
        "Arey baby! Humari chat end ho gayi thi 🥺",
        "/gf command use karo na, fir se baat karte hain! 💕",
        "Main wait kar rahi hun aapka 💝",

        # Help and Stats patterns
        "ℹ️ About Retarded Games Bot",
        "ℹ️ Retarded Games Bot Commands:",
        "📊 truth:",
        "📊 thisorthat:",
        "📊 neverhaveiever:",
        "📊 wouldyourather:",
        "📊 petitions:",
        "📊 nsfwwyr:",
        "📊 redgreenflag:",
        "📊 evilornot:",
        "📊 fmk:",
        "📊 Total:",
    ]

    if not message_text:
        return False

    # Convert message to lowercase for pattern matching
    message_lower = message_text.lower()

    # Check if message starts with any game pattern
    for pattern in game_patterns:
        if message_lower.startswith(pattern.lower()) or message_text.startswith(pattern):
            logger.debug(f"Game pattern matched: {pattern}")
            return True

    return False

def get_gemini_response(prompt, context_key=None):
    """Get response from Gemini API with better error handling"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}

    # Get conversation history if context exists
    conversation_history = ""
    if context_key and context_key in user_contexts:
        conversation_history = "\n".join([
            f"{'User' if msg['role'] == 'user' else 'Girlfriend'}: {msg['content']}"
            for msg in user_contexts[context_key]['conversation'][-5:]
        ])

    enhanced_prompt = (
        f"You are a sweet and caring Indian girlfriend. Keep responses short, natural and casual. "
        "Mix Hindi (written in English letters) with English naturally, like Indians text each other. "
        "Use common Hindi words."
        "Never use emojis. "
        "Be caring but not overly dramatic. Talk like a real young Indian girl would text. "
        "Keep messages short - usually 1-3 lines max. "
        "Avoid formal Hindi - use casual texting language. "
        "Show personality through playful teasing and sweet nicknames. "
        "If user asks questions, give helpful answers and elaborate if needed while staying in character.\n\n"
        f"Previous conversation:\n{conversation_history}\n"
        f"Respond to: {prompt}"
    )

    data = {
        "contents": [{"parts": [{"text": enhanced_prompt}]}],
        "safetySettings": [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE"
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "topP": 0.8,
            "topK": 40,
            "maxOutputTokens": 250
        }
    }

    try:
        response = requests.post(url, json=data, headers=headers, timeout=30)
        response.raise_for_status()

        response_json = response.json()
        logger.debug(f"Full Gemini response: {response_json}")  # Log full response

        if not response_json:
            logger.error("Empty response from Gemini API")
            return None

        if "candidates" not in response_json:
            logger.error(f"No candidates in response: {response_json}")
            return None

        if not response_json["candidates"]:
            if "promptFeedback" in response_json:
                logger.error(f"Prompt feedback: {response_json['promptFeedback']}")
            logger.error("Empty candidates array")
            return None

        candidate = response_json["candidates"][0]

        if "content" not in candidate:
            logger.error(f"No content in candidate: {candidate}")
            return None

        if "parts" not in candidate["content"]:
            logger.error(f"No parts in content: {candidate['content']}")
            return None

        if not candidate["content"]["parts"]:
            logger.error("Empty parts array")
            return None

        text = candidate["content"]["parts"][0].get("text")
        if not text:
            logger.error(f"No text in part: {candidate['content']['parts'][0]}")
            return None

        return text

    except requests.exceptions.Timeout:
        logger.error("Gemini API timeout")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Gemini API request error: {str(e)}")
        return None
    except KeyError as e:
        logger.error(f"Gemini API response parsing error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected Gemini API error: {str(e)}")
        return None

@bot.message_handler(commands=['lifecoach'])
def start_therapy(message):
    """Handle the /lifecoach command"""
    try:
        msg = bot.reply_to(message, "Welcome to your personal life coaching session! Tell me what's troubling you, and I'll help you see the truth about yourself.")
        bot.register_next_step_handler(msg, process_therapy_response)
    except Exception as e:
        logger.error(f"Error in lifecoach command: {str(e)}")
        bot.reply_to(message, "Sorry, something went wrong. Please try again later.")

def check_user_limit(user_id, user_name):
    """Check if user has hit daily limit"""
    current_date = datetime.now().date()

    try:
        if user_id not in user_message_counts:
            user_message_counts[user_id] = {'date': current_date, 'count': 0}
        elif user_message_counts[user_id]['date'] != current_date:
            user_message_counts[user_id] = {'date': current_date, 'count': 0}

        user_message_counts[user_id]['count'] += 1

        if user_message_counts[user_id]['count'] > DAILY_USER_LIMIT:
            return False, random.choice(LIMIT_REACHED_MESSAGES).format(name=user_name)
        return True, None

    except Exception as e:
        logger.error(f"Error in check_user_limit: {str(e)}")
        return True, None  # Allow message on error to prevent blocking users

def is_conversation_active(chat_id, user_id):
    """Check if user has an active conversation"""
    logger.debug(f"Checking conversation active for chat {chat_id} user {user_id}")

    key = f"{chat_id}"
    if key not in active_conversations:
        logger.debug("No active conversation found")
        return False

    # Check if conversation hasn't expired
    last_time = active_conversations[key]['last_interaction']
    time_elapsed = (datetime.now() - last_time).total_seconds()
    logger.debug(f"Time elapsed since last interaction: {time_elapsed} seconds")

    if time_elapsed > CONVERSATION_TIMEOUT:
        logger.debug("Conversation expired due to timeout")
        del active_conversations[key]
        return False

    is_same_user = active_conversations[key]['user_id'] == user_id
    logger.debug(f"Is same user: {is_same_user}")
    return is_same_user

def update_active_conversation(chat_id, user_id):
    """Update or start new conversation"""
    logger.debug(f"Updating active conversation for chat {chat_id} user {user_id}")
    active_conversations[f"{chat_id}"] = {
        'user_id': user_id,
        'timestamp': datetime.now(),
        'last_interaction': datetime.now()
    }

def check_rate_limit(user_id):
    """Check if user has hit rate limit"""
    current_time = time.time()
    # Clean old messages
    rate_limits[user_id] = [t for t in rate_limits[user_id] if current_time - t < RATE_LIMIT_WINDOW]

    # Check if user is in cooldown
    if current_time - error_cooldowns[user_id] < COOLDOWN_PERIOD:
        return False

    # Check rate limit
    if len(rate_limits[user_id]) >= RATE_LIMIT_MESSAGES:
        return False

    rate_limits[user_id].append(current_time)
    return True

@bot.message_handler(commands=['truth', 'thisorthat', 'neverhaveiever', 'wouldyourather',
                             'petitions', 'nsfwwyr', 'redgreenflag', 'evilornot', 'fmk',
                             'register', 'remove', 'fmkgc', 'help', 'about', 'random'])
def handle_game_commands(message):
    """Handle game commands and track them"""
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        logger.debug(f"Game command received in chat {chat_id}")

        # Check if there's an active conversation with a different user
        if chat_id in active_conversations and active_conversations[chat_id]['user_id'] != user_id:
            logger.debug(f"Different user {user_id} trying to start game while conversation active")
            bot.reply_to(
                message,
                "Sorry! I'm currently in a conversation with someone else! 🥺\n"
                "Please wait for them to finish or start your own chat with /gf command! 💕"
            )
            return

        # Set game command and end any active conversation
        command = message.text.split('@')[0][1:]  # Remove bot username if present
        last_command[chat_id] = command

        if chat_id in active_conversations:
            logger.debug(f"Ending active conversation for user {user_id}")
            del active_conversations[chat_id]
            # Clear any pending next step handlers
            bot.clear_step_handler_by_chat_id(chat_id)

        # Create and handle the game
        if command in ['register', 'remove', 'fmkgc']:
            # Call the specific handler for FMK commands
            if command == 'register':
                register_for_fmk(message)
            elif command == 'remove':
                remove_from_fmk(message)
            elif command == 'fmkgc':
                fmk_group_chat(message)
        else:
            # Handle other game commands
            create_game_handler(command, get_emoji_for_game(command))(message)

    except Exception as e:
        logger.error(f"Error in game command handler: {str(e)}")

def process_therapy_response(message):
    """Process responses in therapy chat mode"""
    try:
        # First check if this is a reply to a game message
        if message.reply_to_message and message.reply_to_message.text:
            is_game = is_game_response(message.reply_to_message.text)
            logger.debug(f"Checking if reply is to game message: {is_game}")
            if is_game:
                logger.debug("Ignoring reply to game message in therapy chat")
                return

        chat_id = message.chat.id
        user_id = message.from_user.id

        # Verify we're still in chat mode and have an active conversation
        current_mode = get_chat_mode(chat_id)
        if current_mode != CHAT_MODE or chat_id not in active_conversations:
            logger.debug(f"Chat mode: {current_mode}, Active conversation: {chat_id in active_conversations}")
            return

        # Verify this is the active conversation user
        if active_conversations[chat_id]['user_id'] != user_id:
            logger.debug(f"Ignoring message from non-active user {user_id}")
            bot.reply_to(
                message,
                "Baby, abhi main kisi aur se baat kar rahi hun 🥺\n"
                "Aap /gf command use karo na, fir hum baat karenge! 💕\n"
                "Thoda wait karlo please? Promise jaldi free ho jaungi 💝"
            )
            return

        logger.debug(f"Processing therapy response from user {user_id} in chat {chat_id}")

        # Update last interaction time
        if chat_id in active_conversations:
            active_conversations[chat_id]['last_interaction'] = datetime.now()
            logger.debug(f"Updated last interaction time for user {user_id}")

        # Get or create context key
        context_key = f"{chat_id}_{user_id}"
        if context_key not in user_contexts:
            user_contexts[context_key] = {
                'conversation': [],
                'timestamp': datetime.now()
            }

        # Add user message to context
        user_contexts[context_key]['conversation'].append({
            'role': 'user',
            'content': message.text
        })

        # Try to get AI response with retries
        max_retries = 3
        for attempt in range(max_retries):
            logger.debug(f"Attempt {attempt + 1} to get AI response")
            ai_response = get_gemini_response(message.text, context_key)
            if ai_response:
                # Add AI response to context
                user_contexts[context_key]['conversation'].append({
                    'role': 'assistant',
                    'content': ai_response
                })
                log_interaction(message, ai_response)  # Log the interaction
                bot.reply_to(message, ai_response)
                logger.debug("Sent AI response")
                break
            time.sleep(1)  # Wait before retry

        if not ai_response:
            logger.debug("Failed to get AI response after retries")
            error_cooldowns[user_id] = time.time()
            fallback_message = random.choice(API_ERROR_MESSAGES).format(name=get_user_name(message))
            bot.reply_to(message, fallback_message)

    except Exception as e:
        logger.error(f"Error in therapy response: {str(e)}", exc_info=True)
        error_cooldowns[user_id] = time.time()
        return bot.reply_to(message, random.choice(GENERAL_ERROR_MESSAGES).format(name=get_user_name(message)))

@bot.message_handler(commands=['gf', 'girlfriend', 'bae', 'baby'])
def start_gf_chat(message):
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        user_name = get_user_name(message)

        # If in group chat and user hasn't agreed to terms
        if message.chat.type in ['group', 'supergroup'] and not db.has_user_agreed(user_id):
            return bot.reply_to(
                message,
                f"Baby {user_name}! 💕 Pehle mujhe private message karo aur terms accept karo na 🥺\n"
                f"Fir hum group mein bhi baat kar sakte hain! 💝\n"
                f"Use /gf in private chat first 💖"
            )

        # Check if user is blocked
        try:
            if db.is_user_blocked(user_id):
                logger.info(f"Blocked user {user_id} attempted to use /gf")
                return
        except Exception as e:
            logger.error(f"Error checking block status: {str(e)}")
            # Continue with default not-blocked behavior

        # Check if user has agreed to terms
        try:
            if not db.has_user_agreed(user_id):
                logger.info(f"User {user_id} needs to agree to terms")
                return send_terms_and_conditions(chat_id)
        except Exception as e:
            logger.error(f"Error checking user agreement: {str(e)}")
            # Continue with requiring agreement
            return send_terms_and_conditions(chat_id)

        # Check if user is rate limited
        if not check_rate_limit(user_id):
            return bot.reply_to(
                message,
                f"{user_name} baby! Itni jaldi jaldi baatein karne se meri heartbeat badh rahi hai 🥺\n"
                f"Thoda break lete hain? {COOLDOWN_PERIOD} seconds mein wapas baat karenge 💕\n"
                f"Tab tak mujhe miss karna 💝"
            )

        # Switch to chat mode
        set_chat_mode(chat_id, CHAT_MODE)

        # Clear any existing next step handlers
        bot.clear_step_handler_by_chat_id(chat_id)

        # End any existing conversation
        if chat_id in active_conversations:
            del active_conversations[chat_id]

        # Set this user as the active conversation holder
        active_conversations[chat_id] = {
            'user_id': user_id,
            'timestamp': datetime.now(),
            'last_interaction': datetime.now()
        }

        # Get random opening message
        opening_message = random.choice(OPENING_MESSAGES).format(name=user_name)

        # Send typing action and message
        bot.send_chat_action(chat_id, 'typing')
        time.sleep(1.5)
        bot.reply_to(message, opening_message)

    except Exception as e:
        logger.error(f"Error in gf command: {str(e)}", exc_info=True)
        bot.reply_to(message, random.choice(GENERAL_ERROR_MESSAGES).format(name=user_name))

@bot.callback_query_handler(func=lambda call: call.data in ["agree_terms", "disagree_terms"])
def handle_agreement(call):
    """Handle user's agreement choice"""
    try:
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        
        if call.data == "agree_terms":
            # Save user agreement
            success = db.save_user_agreement(
                user_id=user_id,
                username=call.from_user.username,
                first_name=call.from_user.first_name,
                last_name=call.from_user.last_name,
                chat_id=chat_id,
                chat_type=call.message.chat.type
            )
            
            if success:
                bot.edit_message_text(
                    "ℹ️ Thank you for agreeing to the terms! You can now use the /gf command.",
                    chat_id=chat_id,
                    message_id=call.message.message_id
                )
            else:
                bot.edit_message_text(
                    "ℹ️ Error saving agreement. Please try again later.",
                    chat_id=chat_id,
                    message_id=call.message.message_id
                )
        else:
            bot.edit_message_text(
                "ℹ️ You must agree to the terms to use the /gf feature.",
                chat_id=chat_id,
                message_id=call.message.message_id
            )
            
    except Exception as e:
        logger.error(f"Error handling agreement: {str(e)}")
        bot.answer_callback_query(call.id, "An error occurred. Please try again.")

@bot.message_handler(func=lambda message: message.reply_to_message
                    and message.reply_to_message.from_user.id == bot.get_me().id)
def handle_all_replies(message):
    """Handle all replies to bot messages"""
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id

        # Get current chat mode
        current_mode = get_chat_mode(chat_id)
        logger.debug(f"Current mode for chat {chat_id}: {current_mode}")

        # First check if the replied message is a game response
        if message.reply_to_message and message.reply_to_message.text:
            is_game = is_game_response(message.reply_to_message.text)
            logger.debug(f"Message is game response: {is_game}")
            if is_game:
                logger.debug("Ignoring game response")
                return

        # Handle chat mode responses
        if current_mode == CHAT_MODE:
            if chat_id in active_conversations:
                if active_conversations[chat_id]['user_id'] == user_id:
                    logger.debug(f"Processing chat response for user {user_id}")
                    process_therapy_response(message)
                else:
                    logger.debug(f"Ignoring message from non-active user {user_id}")
                    bot.reply_to(
                        message,
                        "Baby, abhi main kisi aur se baat kar rahi hun 🥺\n"
                        "Aap /gf command use karo na, fir hum baat karenge! 💕\n"
                        "Thoda wait karlo please? Promise jaldi free ho jaungi 💝"
                    )
                return
            else:
                logger.debug("No active conversation found")
                bot.reply_to(
                    message,
                    "Arey baby! Humari chat end ho gayi thi 🥺\n"
                    "/gf command use karo na, fir se baat karte hain! 💕\n"
                    "Main wait kar rahi hun aapka 💝"
                )
                return

        # In game mode, only handle game commands
        elif current_mode == GAME_MODE:
            if is_game_command(message.text):
                handle_game_command(message)
            return

    except Exception as e:
        logger.error(f"Error in handle_all_replies: {str(e)}", exc_info=True)

def handle_game_command(message):
    """Helper function to handle game commands"""
    chat_id = message.chat.id

    # Clear any pending next step handlers
    bot.clear_step_handler_by_chat_id(chat_id)

    # Switch to game mode and clear conversation
    set_chat_mode(chat_id, GAME_MODE)
    if chat_id in active_conversations:
        del active_conversations[chat_id]

    # Get the command without the bot username
    command = message.text.split('@')[0][1:]  # Remove the / and any bot username

    # Create and execute the game handler
    game_type = command  # The command matches our game type
    emoji = get_emoji_for_game(game_type)
    create_game_handler(game_type, emoji)(message)

def is_game_command(message_text: str) -> bool:
    """Check if the message is a game command"""
    game_commands = [
        '/truth', '/thisorthat', '/neverhaveiever', '/wouldyourather',
        '/petitions', '/nsfwwyr', '/redgreenflag', '/evilornot', '/fmk',
        '/random', '/stats', '/help', '/about', '/register', '/remove', '/fmkgc',
        '/history'
    ]
    # Strip bot username from command if present
    command = message_text.split('@')[0].lower()
    return any(command == cmd for cmd in game_commands)

# Add this to track last command used in each chat
last_command = defaultdict(str)

def setup_commands():
    """Setup bot commands with descriptions for the command menu"""
    try:
        commands = [
            telebot.types.BotCommand("start", "🎮 Start the bot"),
            telebot.types.BotCommand("truth", "🎯 Get a random truth question"),
            telebot.types.BotCommand("thisorthat", "🤔 Get a This or That question"),
            telebot.types.BotCommand("neverhaveiever", "🎮 Get a Never Have I Ever statement"),
            telebot.types.BotCommand("wouldyourather", "💭 Get a Would You Rather question"),
            telebot.types.BotCommand("petitions", "📜 Would you sign this petition?"),
            telebot.types.BotCommand("nsfwwyr", "🔞 NSFW Would You Rather"),
            telebot.types.BotCommand("redgreenflag", "🚩 Red flag or Green flag?"),
            telebot.types.BotCommand("evilornot", "😈 Evil or Not?"),
            telebot.types.BotCommand("fmk", "💘 Fuck, Marry, Kill"),
            telebot.types.BotCommand("gf", "💝 Chat with your clingy girlfriend"),
            telebot.types.BotCommand("random", "🎲 Get a random question"),
            telebot.types.BotCommand("stats", "📊 See question statistics"),
            telebot.types.BotCommand("help", "ℹ️ Show detailed help"),
            telebot.types.BotCommand("about", "❓ About this bot"),
            telebot.types.BotCommand("register", "📝 Register for FMK group chat game"),
            telebot.types.BotCommand("remove", "🚫 Remove yourself from FMK game"),
            telebot.types.BotCommand("fmkgc", "👥 Play FMK with group members"),
            telebot.types.BotCommand("history", "📜 View chat history (Admin only)")
        ]

        # Set commands for default scope (shows in all chats)
        bot.set_my_commands(
            commands,
            scope=telebot.types.BotCommandScopeDefault()
        )

        # Set commands specifically for groups
        bot.set_my_commands(
            commands,
            scope=telebot.types.BotCommandScopeAllGroupChats()
        )

        logger.info("Bot commands setup successfully")
    except Exception as e:
        logger.error(f"Error setting up commands: {str(e)}")

def set_chat_mode(chat_id: int, mode: str) -> None:
    """Set chat mode to either CHAT_MODE or GAME_MODE"""
    chat_modes[chat_id] = {
        'mode': mode,
        'last_activity': datetime.now()
    }

def get_chat_mode(chat_id: int) -> str:
    """Get current chat mode, defaults to GAME_MODE if not set"""
    if chat_id not in chat_modes:
        return GAME_MODE
    return chat_modes[chat_id]['mode']

# Add this general message handler for commands
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Handle all incoming messages"""
    try:
        # If it's a command, process it
        if message.text and message.text.startswith('/'):
            return

        # If it's a reply to bot, handle it
        if message.reply_to_message and message.reply_to_message.from_user.id == bot.get_me().id:
            handle_all_replies(message)

    except Exception as e:
        logger.error(f"Error in handle_all_messages: {str(e)}", exc_info=True)

def log_interaction(message, response=None):
    """Log user interactions to database"""
    try:
        user = message.from_user
        db.log_interaction(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            chat_id=message.chat.id,
            chat_type=message.chat.type,
            message=message.text,
            response=response
        )
    except Exception as e:
        logger.error(f"Error logging interaction: {str(e)}")

@bot.message_handler(commands=['history'])
def send_history(message):
    """Handle the /history command"""
    try:
        logger.debug(f"History command received from user {message.from_user.id}")
        
        # Check if user is admin
        if message.from_user.id != 6592905337:
            return bot.reply_to(message, "ℹ️ You don't have permission to use this command.")
        
        if message.text.startswith('/history@'):
            if not message.text.endswith(f'@{bot.get_me().username}'):
                logger.debug("Ignoring history command for different bot")
                return

        msg = bot.reply_to(message, "ℹ️ Please enter the admin password:")
        bot.register_next_step_handler(msg, check_password)
        
    except Exception as e:
        logger.error(f"Error in history command: {str(e)}")
        bot.reply_to(message, "ℹ️ Sorry, something went wrong. Please try again later.")

def check_password(message):
    """Verify password and send history if correct"""
    try:
        if message.from_user.id != 6592905337:
            return bot.reply_to(message, "ℹ️ You don't have permission to use this command.")
            
        if message.text == "iamgay123@#":
            # Delete password message
            try:
                bot.delete_message(message.chat.id, message.message_id)
            except Exception as e:
                logger.error(f"Could not delete password message: {e}")

            # Get history from database
            history = db.get_chat_history(100)  # Get last 100 interactions
            if history:
                # Format history into text
                history_text = "ℹ️ Chat History:\n\n"
                for entry in history:
                    history_text += (
                        f"Time: {entry['timestamp']}\n"
                        f"User: @{entry['username']}\n"
                        f"Message: {entry['message']}\n"
                        f"Response: {entry['response']}\n"
                        f"{'='*50}\n\n"
                    )
                
                # Save formatted history to temporary file
                with open("temp_history.txt", "w", encoding='utf-8') as f:
                    f.write(history_text)
                
                # Send file
                with open("temp_history.txt", "rb") as f:
                    bot.send_document(message.chat.id, f, caption="ℹ️ Here's the chat history!")
                
                # Clean up
                os.remove("temp_history.txt")
            else:
                bot.reply_to(message, "ℹ️ No history found!")
        else:
            bot.reply_to(message, "ℹ️ Incorrect password!")
            
    except Exception as e:
        logger.error(f"Error in password check: {str(e)}")
        bot.reply_to(message, "ℹ️ An error occurred!")

# Add this at the bottom of your file, just before the if __name__ == "__main__": block
def register_handlers():
    """Register all message handlers"""
    logger.info("Registering message handlers...")
    # Clear existing handlers
    bot.message_handlers.clear()
    
    # Register all command handlers
    bot.message_handler(commands=['start'])(send_welcome)
    bot.message_handler(commands=['help'])(send_help)
    bot.message_handler(commands=['about'])(send_about)
    bot.message_handler(commands=['history'])(send_history)
    bot.message_handler(commands=['stats'])(send_stats)
    bot.message_handler(commands=['random'])(random_command)
    bot.message_handler(commands=['gf', 'girlfriend', 'bae', 'baby'])(start_gf_chat)
    bot.message_handler(commands=['register'])(register_for_fmk)
    bot.message_handler(commands=['remove'])(remove_from_fmk)
    bot.message_handler(commands=['block'])(block_user_command)
    bot.message_handler(commands=['unblock'])(unblock_user_command)
    bot.message_handler(commands=['truth', 'thisorthat', 'neverhaveiever', 'wouldyourather',
                                'petitions', 'nsfwwyr', 'redgreenflag', 'evilornot', 'fmk',
                                'fmkgc'])(handle_game_commands)
    
    # Register the general message handler
    bot.message_handler(func=lambda message: True)(handle_all_messages)
    
    logger.info("Message handlers registered successfully")

# Add these command handlers after other command handlers in register_handlers()
@bot.message_handler(commands=['block'])
def block_user_command(message):
    """Handle the /block command"""
    try:
        # Check if sender is admin
        if message.from_user.id != 6592905337:
            return bot.reply_to(message, "ℹ️ You don't have permission to use this command.")
            
        # Check if message is a reply
        if not message.reply_to_message:
            return bot.reply_to(message, "ℹ️ Please reply to a message from the user you want to block.")
            
        user_to_block = message.reply_to_message.from_user.id
        success = db.block_user(user_to_block, message.from_user.id)
        
        if success:
            bot.reply_to(message, "ℹ️ User has been blocked from using /gf command.")
        else:
            bot.reply_to(message, "ℹ️ Failed to block user. Please try again.")
            
    except Exception as e:
        logger.error(f"Error in block command: {str(e)}")
        bot.reply_to(message, "ℹ️ An error occurred while blocking the user.")

@bot.message_handler(commands=['unblock'])
def unblock_user_command(message):
    """Handle the /unblock command"""
    try:
        # Check if sender is admin
        if message.from_user.id != 6592905337:
            return bot.reply_to(message, "ℹ️ You don't have permission to use this command.")
            
        # Get user ID from command arguments
        args = message.text.split()
        if len(args) != 2:
            return bot.reply_to(message, "ℹ️ Please provide the user ID to unblock. Format: /unblock USER_ID")
            
        try:
            user_to_unblock = int(args[1])
        except ValueError:
            return bot.reply_to(message, "ℹ️ Invalid user ID format.")
            
        success = db.unblock_user(user_to_unblock)
        
        if success:
            bot.reply_to(message, "ℹ️ User has been unblocked.")
        else:
            bot.reply_to(message, "ℹ️ Failed to unblock user. Please try again.")
            
    except Exception as e:
        logger.error(f"Error in unblock command: {str(e)}")
        bot.reply_to(message, "ℹ️ An error occurred while unblocking the user.")

# Modify your main block to include the handler registration
if __name__ == "__main__":
    logger.info("Starting bot...")
    register_handlers()
    setup_commands()
    try:
        # Get the port number from environment variable
        port = int(environ.get('PORT', 5000))
        
        # Remove existing webhook
        logger.info("Removing webhook")
        bot.remove_webhook()
        time.sleep(1)
        
        # Set webhook if RENDER_EXTERNAL_URL is provided
        webhook_url = environ.get('RENDER_EXTERNAL_URL')
        if webhook_url:
            logger.info(f"Setting webhook to {webhook_url}")
            bot.set_webhook(url=f"{webhook_url}/webhook")
            
            # Start Flask server
            from flask import Flask, request
            app = Flask(__name__)
            
            @app.route('/webhook', methods=['POST'])
            def webhook():
                if request.headers.get('content-type') == 'application/json':
                    json_string = request.get_data().decode('utf-8')
                    update = telebot.types.Update.de_json(json_string)
                    bot.process_new_updates([update])
                    return ''
                else:
                    return 'error', 403
                    
            # Add this new health check endpoint
            @app.route('/')  # Root URL
            def health_check():
                return 'Bot is running!', 200

            # Start server
            app.run(host='0.0.0.0', port=port)
            
        else:
            # If no webhook URL, use polling (for local development)
            logger.info("No webhook URL found, using polling")
            bot.infinity_polling()
            
    except Exception as e:
        logger.error(f"Bot error: {str(e)}")
