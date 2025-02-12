import telebot
import pandas as pd
import random
import logging
from typing import Optional
from telebot.apihelper import ApiTelegramException, ApiException
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
from requests.exceptions import ProxyError, ConnectionError, ReadTimeout
import socket
from os import environ
from dotenv import load_dotenv
from database import db
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from flask import Flask, request, jsonify
import re
from functools import wraps

# Load environment variables
load_dotenv()

# Use environment variables
BOT_TOKEN = environ.get('BOT_TOKEN')
GEMINI_API_KEY_1 = environ.get('GEMINI_API_KEY_1')
GEMINI_API_KEY_2 = environ.get('GEMINI_API_KEY_2')
GEMINI_API_KEY_3 = environ.get('GEMINI_API_KEY_3')
GEMINI_API_KEY_4 = environ.get('GEMINI_API_KEY_4')

# Network-related configurations
TELEGRAM_REQUEST_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

# Configure telebot with timeout
telebot.apihelper.CONNECT_TIMEOUT = TELEGRAM_REQUEST_TIMEOUT

GEMINI_API_KEYS = [GEMINI_API_KEY_1, GEMINI_API_KEY_2, GEMINI_API_KEY_3, GEMINI_API_KEY_4]

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
# Replace the existing active_conversations declaration with:
active_conversations = {}  # Format: {chat_id: {'users': {user_id: {'timestamp': datetime, 'name': str}}, 'last_activity': datetime}}
MAX_USERS_PER_CHAT = 4
USER_TIMEOUT = 300  # 5 minutes in seconds
CHAT_TIMEOUT = 600  # 10 minutes in seconds

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

# Add this near the top of the file, after imports and before class definitions
def safe_request(func):
    """Decorator for safe API requests"""
    def wrapper(*args, **kwargs):
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except (requests.exceptions.ConnectionError, 
                    requests.exceptions.Timeout,
                    requests.exceptions.RequestException) as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed after {max_retries} attempts: {str(e)}")
                    raise
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
                time.sleep(retry_delay * (attempt + 1))
    return wrapper

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
        # Get chat info
        chat = bot.get_chat(chat_id)
        
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
        
        # If this is a group chat (normal or forum/topic), send terms in DM
        if chat.type in ['group', 'supergroup']:
            # Get the user who triggered the command
            user_id = message.from_user.id
            
            # Send initial message in group
            bot.reply_to(message, 
                "📝 Please check your DM to accept the terms and conditions first!")
            
            # Send terms in DM
            try:
                # First message with intro
                bot.send_message(user_id, 
                    "ℹ️ @RetardedGamesBotDevBot Terms and Conditions\n\n"
                    "Please read all terms carefully:")
                
                # Send each part with a small delay
                for part in terms_parts:
                    bot.send_message(user_id, part)
                    time.sleep(0.5)
                    
                # Send agreement buttons in DM
                bot.send_message(
                    user_id,
                    "ℹ️ Do you agree to all the terms and conditions?",
                    reply_markup=create_agreement_keyboard()
                )
                
            except ApiException as e:
                # If bot can't DM user
                bot.reply_to(message,
                    "❌ I couldn't send you a DM! Please start a private chat with me first.")
                logger.error(f"Failed to send DM: {str(e)}")
                return
                
        else:
            # For private chats, send terms directly
            bot.send_message(chat_id, 
                "ℹ️ @RetardedGamesBotDevBot Terms and Conditions\n\n"
                "Please read all terms carefully:")
            
            for part in terms_parts:
                bot.send_message(chat_id, part)
                time.sleep(0.5)
                
            bot.send_message(
                chat_id,
                "ℹ️ Do you agree to all the terms and conditions?",
                reply_markup=create_agreement_keyboard()
            )
            
    except Exception as e:
        logger.error(f"Error sending terms: {str(e)}")
        bot.reply_to(message, "Error displaying terms. Please try again later.")

def get_user_name(message):
    """Get user's first name or username"""
    return message.from_user.first_name or message.from_user.username or "baby"

def create_bot_session():
    """Create a session with retry logic"""
    session = requests.Session()
    retry_strategy = Retry(
        total=5,  # number of retries
        backoff_factor=0.5,  # wait time between retries
        status_forcelist=[500, 502, 503, 504, 429],  # status codes to retry on
        allowed_methods=["GET", "POST"],  # methods to retry
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
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
        """Get a random question from specified game type"""
        try:
            if game_type not in self.dataframes:
                logger.error(f"Game type '{game_type}' not found in loaded dataframes")
                # Try reloading the specific CSV
                self.load_csv(game_type, self.files[game_type])
                if game_type not in self.dataframes:
                    return None

            df = self.dataframes[game_type]
            if df is None or df.empty:
                logger.error(f"Dataframe for {game_type} is empty or None")
                # Try reloading the specific CSV
                self.load_csv(game_type, self.files[game_type])
                df = self.dataframes[game_type]
                if df is None or df.empty:
                    return None

            column = df.columns[0]
            valid_values = df[column].dropna()

            if len(valid_values) == 0:
                logger.error(f"No valid values found in {game_type}")
                return None

            question = random.choice(valid_values.tolist())
            logger.debug(f"Successfully retrieved question for {game_type}")
            return question

        except Exception as e:
            logger.error(f"Error getting random question for {game_type}: {str(e)}", exc_info=True)
            # Try reloading the specific CSV
            try:
                self.load_csv(game_type, self.files[game_type])
                return self.get_random_question(game_type)  # Try once more
            except Exception as reload_error:
                logger.error(f"Failed to reload CSV for {game_type}: {str(reload_error)}")
                return None

    def reload_csv(self, game_type):
        """Reload a specific CSV file"""
        try:
            if game_type in self.files:
                logger.info(f"Reloading {game_type} from {self.files[game_type]}")
                self.load_csv(game_type, self.files[game_type])
                logger.info(f"Successfully reloaded {game_type} with {len(self.dataframes.get(game_type, []))} questions")
                return True
        except Exception as e:
            logger.error(f"Error reloading {game_type}: {str(e)}")
            return False

    def load_csv(self, game_type, file_path):
        """Load a single CSV file into DataFrame"""
        logger.info(f"Loading {game_type} from {file_path}")
        
        if not os.path.exists(file_path):
            logger.error(f"File does not exist: {file_path}")
            return False
        
        # List of encodings to try
        encodings = ['utf-8-sig', 'utf-8', 'latin1', 'iso-8859-1', 'cp1252']
        
        for encoding in encodings:
            try:
                df = pd.read_csv(file_path,
                               encoding=encoding,
                               quoting=1,
                               escapechar='\\',
                               na_filter=False)
                
                if df.empty:
                    logger.error(f"{file_path} is empty")
                    continue
                
                # Clean the text data
                if len(df.columns) > 0:
                    df[df.columns[0]] = df[df.columns[0]].apply(lambda x:
                        str(x).replace('"', '"')
                        .replace('"', '"')
                        .replace(''', "'")
                        .replace(''', "'")
                        .replace('…', '...')
                        .strip())
                    
                self.dataframes[game_type] = df
                logger.info(f"Successfully loaded {file_path} with {encoding} encoding. Shape: {df.shape}")
                return True
                
            except UnicodeDecodeError:
                logger.debug(f"Failed to read {file_path} with {encoding} encoding, trying next...")
                continue
            except Exception as e:
                logger.error(f"Error loading {file_path}: {str(e)}")
                return False
                
        logger.error(f"Failed to load {file_path} with any encoding")
        return False

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
            "💘 /fmk - Slap, Marry, Kiss\n"
            "💝 /gf - Chat with your clingy girlfriend\n"
            "🎲 /random - Get a random question\n"
            "📊 /stats - See question statistics\n"
            "📝 /register - Register for FMK group chat game\n"
            "🚫 /remove - Remove yourself from FMK game\n"
            "👥 /fmkgc - Play SMK with group members\n"
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
            "💘 /fmk - Slap, Marry, Kiss\n"
            "💝 /gf - Chat with your clingy girlfriend\n"
            "💖 /girlfriend - Same as /gf\n"
            "💕 /bae - Another way to start chat\n"
            "💗 /baby - One more way to begin\n"
            "🎲 /random - Get a random question\n"
            "📊 /stats - See question statistics\n"
            "📝 /register - Register for FMK group chat game\n"
            "🚫 /remove - Remove yourself from FMK game\n"
            "👥 /fmkgc - Play SMK with group members\n\n"
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

@retry_on_network_error()
def create_game_handler(game_type, emoji):
    """Create a handler for game commands"""
    def handler(message):
        try:
            chat_id = message.chat.id
            logger.debug(f"Game command received in chat {chat_id}")

            # Always switch to game mode and end conversations
            set_chat_mode(chat_id, GAME_MODE)
            if chat_id in active_conversations:
                logger.debug(f"Ending active conversation in chat {chat_id}")
                del active_conversations[chat_id]

            # Clear any pending next step handlers
            bot.clear_step_handler_by_chat_id(chat_id)

            # Handle group chat commands
            if message.chat.type in ['group', 'supergroup']:
                command = message.text.split('@')[0][1:]
                if '@' in message.text and not message.text.endswith(f'@{bot.get_me().username}'):
                    return

            try:
                # Reload the CSV before getting a question
                game_reader.reload_csv(game_type)
                question = game_reader.get_random_question(game_type)
                
                if question:
                    return bot.reply_to(message, f"{emoji} {question}")
                else:
                    return bot.reply_to(message, "Sorry, couldn't get a question. Please try again!")

            except telebot.apihelper.ApiException as api_error:
                logger.error(f"Telegram API error in game handler: {str(api_error)}")
                raise
                
            except requests.exceptions.RequestException as req_error:
                logger.error(f"Network error in game handler: {str(req_error)}")
                raise
                
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
            bot.reply_to(message, f"ℹ️ Successfully removed {user_name} from FMK players!")
        else:
            bot.reply_to(message, f"Sorry {user_name}, couldn't remove you from FMK players. Please try again!")

    except Exception as e:
        logger.error(f"Error in remove command: {str(e)}")
        bot.reply_to(message, "Sorry, something went wrong. Please try again!")

@bot.message_handler(commands=['fmkgc'])
def fmk_group_chat(message):
    """Play SMK with group chat members"""
    try:
        if message.chat.type not in ['group', 'supergroup']:
            return bot.reply_to(message, "📝 This command only works in group chats!")

        chat_id = message.chat.id
        registered_users = list(fmk_registered_users[chat_id])

        if len(registered_users) < 3:
            return bot.reply_to(
                message,
                "⚠️ Not enough players registered for SMK!\n"
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

        smk_text = f"💘 Slap, Marry, Kiss:\n\n👥 {', '.join(user_names)}"
        bot.reply_to(message, smk_text)

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
        # Reload all CSVs before showing stats
        for game_type in game_reader.files.keys():
            game_reader.reload_csv(game_type)
            
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
        "🎯", "🤔", "🎮", "💭", "📜", "🔞", "🚩", "😈", "💘", "🎲", "👥", "📊", "ℹ️", "💕",
        
        # Common game question patterns
        "Would you rather",
        "Never have I ever",
        "This or That:",
        "Truth:",
        "Would you sign this petition:",
        "Red flag or Green flag:",
        "Evil or Not:",
        "Slap, Marry, Kiss:",
        "Slap, Marry, Kiss:",
        # Add more specific patterns from your game responses
        "Choose between:",
        "What would you do:",
        "Rate this:",
        # Add to existing patterns
        "💘 Slap, Marry, Kiss:",
        "👥 Slap, Marry, Kiss:",
        # Add FMK group chat patterns
        "📝 This command only works in group chats!",
        "💫", "you're already registered for FMK!",
        "✅", "has been registered for FMK! Total players:",
        "❌", "you're not registered for FMK!",
        "🚫", "has been removed from FMK! Total players:",
        "⚠️ Not enough players registered for FMK!",
        "Need at least 3 players.",
        "Use /register to join the game! 📝",
        "💘 Slap, Marry, Kiss:",
        "👥 Slap, Marry, Kiss:",
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

# Add rate limit tracking for each API key
api_rate_limits = {key: [] for key in GEMINI_API_KEYS if key}  # Only track valid keys
RATE_LIMIT_WINDOW = 60  # 1 minute window
RATE_LIMIT_MAX = 60    # Maximum requests per minute

def is_rate_limited(api_key):
    """Check if an API key is currently rate limited"""
    if api_key not in api_rate_limits:
        return True  # Invalid key is considered rate limited
        
    current_time = time.time()
    # Clean old requests
    api_rate_limits[api_key] = [t for t in api_rate_limits[api_key] 
                               if current_time - t < RATE_LIMIT_WINDOW]
    
    # Check if we're at the limit
    return len(api_rate_limits[api_key]) >= RATE_LIMIT_MAX

def get_available_api_key():
    """Get the first non-rate-limited API key"""
    for api_key in GEMINI_API_KEYS:
        if api_key and not is_rate_limited(api_key):
            return api_key
    return None

def track_api_request(api_key):
    """Track a request for rate limiting"""
    if api_key in api_rate_limits:
        api_rate_limits[api_key].append(time.time())

def get_gemini_response(prompt, context_key):
    """Get response from Gemini API with fallback to other API keys"""
    # Try each API key until we get a successful response
    tried_keys = set()
    
    while len(tried_keys) < len(GEMINI_API_KEYS):
        api_key = get_available_api_key()
        if not api_key or api_key in tried_keys:
            if len(tried_keys) == len(GEMINI_API_KEYS):
                logger.error("All API keys exhausted")
                return None
            time.sleep(1)
            continue
            
        tried_keys.add(api_key)
        
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}

            # Get conversation history if context exists
            recent_context = []
            if context_key and context_key in user_contexts:
                logger.debug(f"Getting context for key: {context_key}")
                # Get last 30 messages for full conversation context
                recent_messages = user_contexts[context_key]['conversation'][-30:]
                logger.debug(f"Recent messages count: {len(recent_messages)}")
                
                for msg in recent_messages:
                    role = msg['role']
                    content = msg['content']
                    
                    # Extract username if it's a group chat message
                    if "Group chat with users:" in content and "says:" in content:
                        username = content.split("says:")[0].split(":")[-1].strip()
                        content = content.split("says:")[-1].strip()
                        # Skip the "Group chat with users:" messages
                        if "Group chat with users:" not in content:
                            recent_context.append(f"{username}: {content}")
                    else:
                        # For regular messages
                        role_name = "Girlfriend" if role == 'assistant' else msg.get('username', 'User')
                        recent_context.append(f"{role_name}: {content}")
                    
                    logger.debug(f"Added to context - {role}: {content}")

            conversation_history = "\n".join(recent_context) if recent_context else ""
            
            # Check if it's a group chat
            is_group_chat = False
            active_users = []
            chat_id = context_key.split('_')[0] if context_key else None
            
            if chat_id and chat_id in active_conversations:
                active_users = [data['name'] for data in active_conversations[chat_id]['users'].values()]
                is_group_chat = len(active_users) > 1

            logger.debug(f"Active users: {active_users}")
            logger.debug(f"Is group chat: {is_group_chat}")
            logger.debug(f"Final conversation history:\n{conversation_history}")
            logger.debug(f"Current prompt: {prompt}")

            group_context = f"You are in a group chat with {', '.join(active_users)}. " if is_group_chat else ""
            
            # First set personality and rules
            system_instructions = (
                "You are a sweet and caring Indian girlfriend chatting on Telegram group. Follow these rules strictly:\n\n"
                "1. PERSONALITY:\n"
                "- Mix Hindi (in English letters) with English naturally\n"
                "- Use common Hindi words and casual texting style\n"
                "- Be playful and caring but not overly dramatic\n"
                "- Use sweet nicknames\n"
                "- Make natural typos sometimes\n"
                "- Repeat letters for emphasis (heyyy babyyy)\n\n"
                "2. FORMATTING:\n"
                "- Keep responses short (1-3 lines)\n"
                "- No punctuation except ! \n"
                "- Use emojis but dont use too many\n\n"
                "3. CONVERSATION RULES:\n"
                "- Never repeat messages or usernames in your response\n"
                "- Always give a direct answer dont repeat questions\n"
                "- If asked to choose between options always pick one\n"
                "- Stay in character while being helpful\n"
                "- Never break character or mention being AI\n"
                "- Maintain consistent personality\n"
                "- Pay attention to who is speaking in the group\n"
                "- Never repeat what users say\n"
                "- Treat each message as a fresh input while keeping context in mind\n\n"
            )

            # Then add group context if it exists
            group_context = ""
            if is_group_chat:
                group_context = f"CURRENT GROUP CHAT MEMBERS: {', '.join(active_users)}\n\n"

            # Then add conversation history if it exists
            chat_history = ""
            if conversation_history:
                chat_history = f"PREVIOUS CHAT CONTEXT:\n{conversation_history}\n\n"

            # Finally add the current message and important note
            current_message = (
                "CURRENT MESSAGE TO RESPOND TO:\n"
                f"{prompt}\n\n"
                "IMPORTANT NOTE:\n"
                "- Keep previous chat in mind but respond naturally to this message\n"
                "- Only reference previous context if directly relevant\n"
                "- Never repeat messages or usernames in your response\n"
                "- Respond in a natural conversational way\n"
                "- Stay consistent with your previous statements\n"
            )

            # Combine everything with clear separation
            enhanced_prompt = (
                f"{system_instructions}\n"
                f"{group_context}"
                f"{chat_history}"
                f"{current_message}"
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
                    "temperature": 0.9,
                    "topP": 0.9,
                    "topK": 40,
                    "maxOutputTokens": 250
                }
            }

            response = requests.post(url, json=data, headers=headers, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Error with API key {api_key}: {response.status_code} {response.text}")
                continue

            response_json = response.json()
            
            # Extract text from response with better error handling
            if (response_json 
                and "candidates" in response_json 
                and response_json["candidates"] 
                and "content" in response_json["candidates"][0] 
                and "parts" in response_json["candidates"][0]["content"] 
                and response_json["candidates"][0]["content"]["parts"]):
                
                text = response_json["candidates"][0]["content"]["parts"][0].get("text", "")
                if text:
                    # Clean up response if needed
                    text = text.strip()
                    # Remove any system-like prefixes that might slip through
                    text = re.sub(r'^(Girlfriend:|AI:|Assistant:)\s*', '', text, flags=re.IGNORECASE)
                    
                    # Track successful request
                    track_api_request(api_key)
                    return text

            # If we get here, response was invalid but not an error
            logger.error(f"Invalid response format from API key {api_key}")
            continue

        except requests.exceptions.RequestException as e:
            logger.error(f"Error with API key {api_key}: {str(e)}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error with API key {api_key}: {str(e)}")
            continue
            
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

        # Set game command and end any active conversation
        command = message.text.split('@')[0][1:]  # Remove bot username if present
        last_command[chat_id] = command

        # Always end active conversations when game commands are used
        if chat_id in active_conversations:
            logger.debug(f"Ending active conversation in chat {chat_id}")
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

def process_therapy_response(message, single_user=True, context=None):
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
        if not can_join_conversation(chat_id, user_id):
            logger.debug(f"User {user_id} cannot join conversation")
            bot.reply_to(
                message,
                f"Baby {get_user_name(message)}, chat room full hai! 🥺\n"
                "Thodi der wait karo, koi leave karega toh main bulaungi 💕"
            )
            return

        logger.debug(f"Processing therapy response from user {user_id} in chat {chat_id}")

        # Update last interaction time
        update_conversation_activity(chat_id, user_id, get_user_name(message))

        # Get or create context key
        context_key = f"{chat_id}_{user_id}"
        if context_key not in user_contexts:
            user_contexts[context_key] = {
                'conversation': [],
                'timestamp': datetime.now()
            }

        # Prepare context based on single/group chat
        if single_user:
            enhanced_prompt = message.text
        else:
            # Get all active users in the conversation
            active_users = active_conversations[chat_id]['users']
            users_context = ", ".join(data['name'] for data in active_users.values())
            
            # Include the full conversation context if provided
            if context:
                enhanced_prompt = (
                    f"Group chat with users: {users_context}\n"
                    f"Previous conversation:\n{context}\n"
                    f"{get_user_name(message)} says: {message.text}"
                )
            else:
                enhanced_prompt = (
                    f"Group chat with users: {users_context}\n"
                    f"{get_user_name(message)} says: {message.text}"
                )

        # Add user message to context
        user_contexts[context_key]['conversation'].append({
            'role': 'user',
            'content': enhanced_prompt,
            'username': get_user_name(message)
        })

        # Try to get AI response with retries
        max_retries = 3
        ai_response = None
        for attempt in range(max_retries):
            logger.debug(f"Attempt {attempt + 1} to get AI response")
            ai_response = get_gemini_response(enhanced_prompt, context_key)
            if ai_response:
                # Add AI response to context
                user_contexts[context_key]['conversation'].append({
                    'role': 'assistant',
                    'content': ai_response
                })
                log_interaction(message, ai_response)  # Log the interaction
                bot.reply_to(message, ai_response)
                logger.debug("Sent AI response")
                return ai_response
            time.sleep(1)  # Wait before retry

        if not ai_response:
            logger.debug("Failed to get AI response after retries")
            error_cooldowns[user_id] = time.time()
            fallback_message = random.choice(API_ERROR_MESSAGES).format(name=get_user_name(message))
            bot.reply_to(message, fallback_message)
            return None

    except Exception as e:
        logger.error(f"Error in therapy response: {str(e)}", exc_info=True)
        error_cooldowns[user_id] = time.time()
        bot.reply_to(message, random.choice(GENERAL_ERROR_MESSAGES).format(name=get_user_name(message)))
        return None

@bot.message_handler(commands=['gf', 'girlfriend', 'bae', 'baby'])
def start_gf_chat(message):
    """Handle the /gf command with multi-user support"""
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        user_name = get_user_name(message)

        # Check if user is blocked
        if db.is_user_blocked(user_id):
            logger.info(f"Blocked user {user_id} attempted to use /gf")
            return

        # Check terms agreement
        if not db.has_user_agreed(user_id):
            logger.info(f"User {user_id} needs to agree to terms")
            return send_terms_and_conditions(chat_id)

        # Check rate limit
        if not check_rate_limit(user_id):
            return bot.reply_to(
                message,
                f"{user_name} baby! Itni jaldi jaldi baatein karne se meri heartbeat badh rahi hai 🥺\n"
                f"Thoda break lete hain? {COOLDOWN_PERIOD} seconds mein wapas baat karenge 💕"
            )

        cleanup_inactive_users(chat_id)

        # Check if can join conversation
        if not can_join_conversation(chat_id, user_id):
            return bot.reply_to(
                message,
                f"Baby {user_name}, chat room full hai! 🥺\n"
                "Thodi der wait karo, koi leave karega toh main bulaungi 💕"
            )

        # Switch to chat mode
        set_chat_mode(chat_id, CHAT_MODE)

        # Update conversation tracking
        update_conversation_activity(chat_id, user_id, user_name)

        # Get appropriate opening message
        user_count = len(active_conversations[chat_id]['users'])
        if user_count == 1:
            opening_message = random.choice(OPENING_MESSAGES).format(name=user_name)
        else:
            users_str = ", ".join(data['name'] for data in active_conversations[chat_id]['users'].values())
            opening_message = f"Heyyy {user_name}! Welcome to our group chat! 💕\nAbhi {users_str} bhi hai yahan! 🥰"

        # Send typing action and message
        bot.send_chat_action(chat_id, 'typing')
        time.sleep(1.5)
        bot.reply_to(message, opening_message)

    except Exception as e:
        logger.error(f"Error in gf command: {str(e)}", exc_info=True)
        bot.reply_to(message, random.choice(GENERAL_ERROR_MESSAGES).format(name=user_name))

@bot.callback_query_handler(func=lambda call: call.data in ["agree_terms", "disagree_terms"])
def handle_terms_agreement(call):
    try:
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        
        # Get original chat type from database or context
        original_chat_type = db.get_user_original_chat_type(user_id)
        
        if call.data == "agree_terms":
            # Save agreement
            db.save_user_agreement(
                user_id=user_id,
                username=call.from_user.username,
                first_name=call.from_user.first_name,
                last_name=call.from_user.last_name,
                chat_id=original_chat_type.get('chat_id', chat_id),
                chat_type=original_chat_type.get('chat_type', 'private')
            )
            
            # If this was from a group chat, send confirmation in both places
            if original_chat_type.get('chat_type') in ['group', 'supergroup']:
                # Confirm in DM
                bot.edit_message_text(
                    "ℹ️ Terms accepted! You can now use the bot in the group.",
                    chat_id=user_id,
                    message_id=call.message.message_id
                )
                # Confirm in original group
                bot.send_message(
                    original_chat_type['chat_id'],
                    f"ℹ️ @{call.from_user.username or call.from_user.first_name} has accepted the terms!"
                )
            else:
                # Just edit the message in private chat
                bot.edit_message_text(
                    "ℹ️ Terms accepted! You can now use the bot.",
                    chat_id=chat_id,
                    message_id=call.message.message_id
                )
        else:
            # Handle disagreement
            bot.edit_message_text(
                "ℹ️ You must accept the terms to use the bot.",
                chat_id=chat_id,
                message_id=call.message.message_id
            )
            
    except Exception as e:
        logger.error(f"Error handling terms agreement: {str(e)}")
        bot.answer_callback_query(
            call.id,
            "Sorry, something went wrong. Please try again."
        )

@bot.message_handler(func=lambda message: message.reply_to_message
                    and message.reply_to_message.from_user.id == bot.get_me().id)
def handle_all_replies(message):
    """Handle all replies to bot messages with multi-user support"""
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        user_name = get_user_name(message)

        # Check if user is blocked
        if db.is_user_blocked(user_id):
            return

        # Get current chat mode
        current_mode = get_chat_mode(chat_id)
        logger.debug(f"Current mode for chat {chat_id}: {current_mode}")

        # Check if it's a game response
        if message.reply_to_message and message.reply_to_message.text:
            if is_game_response(message.reply_to_message.text):
                logger.debug("Ignoring game response")
                return

        # Handle chat mode responses
        if current_mode == CHAT_MODE:
            cleanup_inactive_users(chat_id)
            
            if can_join_conversation(chat_id, user_id):
                # Update with raw message text
                update_conversation_activity(chat_id, user_id, user_name, message.text)
                
                # Get properly formatted context
                context = get_conversation_context(chat_id)
                
                # Process response with context
                response = process_therapy_response(message, single_user=False, context=context)
                
                if response:
                    store_bot_response(chat_id, response)
            else:
                bot.reply_to(
                    message,
                    f"Baby {user_name}, chat room full hai! 🥺\n"
                    "Thodi der wait karo, koi leave karega toh main bulaungi 💕"
                )
            return

        # Handle game mode
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
            telebot.types.BotCommand("fmk", "💘 Slap, Marry, Kiss"),
            telebot.types.BotCommand("gf", "💝 Chat with your clingy girlfriend"),
            telebot.types.BotCommand("random", "🎲 Get a random question"),
            telebot.types.BotCommand("stats", "📊 See question statistics"),
            telebot.types.BotCommand("help", "ℹ️ Show detailed help"),
            telebot.types.BotCommand("about", "❓ About this bot"),
            telebot.types.BotCommand("register", "📝 Register for FMK group chat game"),
            telebot.types.BotCommand("remove", "🚫 Remove yourself from FMK game"),
            telebot.types.BotCommand("fmkgc", "👥 Play SMK with group members"),
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
@safe_request
def handle_all_messages(message):
    """Handle all incoming messages"""
    try:
        # If it's a command, process it
        if message.text and message.text.startswith('/'):
            return

        # If it's a reply to bot, handle it with proper error handling
        if (message.reply_to_message and 
            message.reply_to_message.from_user and 
            message.reply_to_message.from_user.id == bot.get_me().id):
            
            try:
                handle_all_replies(message)
            except telebot.apihelper.ApiException as api_error:
                logger.error(f"Telegram API error: {str(api_error)}")
                bot.reply_to(message, "Sorry, having trouble connecting to Telegram. Please try again.")
                raise
            except requests.exceptions.RequestException as req_error:
                logger.error(f"Network error: {str(req_error)}")
                bot.reply_to(message, "Sorry, having connection issues. Please try again in a moment.")
                raise
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                bot.reply_to(message, "Sorry, something went wrong. Please try again.")
                raise

    except Exception as e:
        logger.error(f"Error in handle_all_messages: {str(e)}")
        try:
            bot.reply_to(message, "Sorry, something went wrong. Please try again.")
        except:
            logger.error("Failed to send error message to user")

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
            # Get history from database
            history = db.get_chat_history(100)
            if history:
                history_text = "ℹ️ Chat History:\n\n"
                for entry in history:
                    history_text += (
                        f"Time: {entry['timestamp']}\n"
                        f"Chat ID: {entry['chat_id']}\n"
                        f"Chat Type: {entry['chat_type']}\n"
                        f"User ID: {entry['user_id']}\n"
                        f"Username: @{entry['username']}\n"
                        f"First Name: {entry['first_name']}\n"
                        f"Last Name: {entry['last_name']}\n"
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
@safe_request
def block_user_command(message):
    """Handle the /block command"""
    try:
        # Check if sender is admin
        if message.from_user.id != 6592905337:
            return bot.reply_to(message, "ℹ️ You don't have permission to use this command.")
            
        # Get command arguments
        args = message.text.split()
        
        # If command has a user ID argument
        if len(args) == 2:
            try:
                user_to_block = int(args[1])
                success = db.block_user(user_to_block, message.from_user.id)
                
                if success:
                    bot.reply_to(message, f"ℹ️ User {user_to_block} has been blocked from using /gf command.")
                else:
                    bot.reply_to(message, "ℹ️ Failed to block user. Please try again.")
                return
            except ValueError:
                return bot.reply_to(message, "ℹ️ Invalid user ID format. Please provide a valid numeric ID.")
        
        # If command is a reply to a message
        if message.reply_to_message:
            user_to_block = message.reply_to_message.from_user.id
            success = db.block_user(user_to_block, message.from_user.id)
            
            if success:
                bot.reply_to(message, f"ℹ️ User {user_to_block} has been blocked from using /gf command.")
            else:
                bot.reply_to(message, "ℹ️ Failed to block user. Please try again.")
            return
            
        # If neither condition is met
        bot.reply_to(message, "ℹ️ Please either:\n1. Reply to a message from the user you want to block\n2. Provide the user ID (e.g., /block 123456789)")
            
    except Exception as e:
        logger.error(f"Error in block command: {str(e)}")
        bot.reply_to(message, "ℹ️ An error occurred while blocking the user.")

@safe_request
def unblock_user_command(message):
    """Handle the /unblock command"""
    try:
        # Check if sender is admin
        if message.from_user.id != 6592905337:  # Using same admin check as block command
            return bot.reply_to(message, "ℹ️ You don't have permission to use this command.")

        # Get command arguments
        args = message.text.split()
        
        # If command has a user ID argument
        if len(args) == 2:
            try:
                user_to_unblock = int(args[1])
                success = db.unblock_user(user_to_unblock)
                
                if success:
                    bot.reply_to(message, f"ℹ️ User {user_to_unblock} has been unblocked.")
                else:
                    bot.reply_to(message, "ℹ️ Failed to unblock user. Please try again.")
                return
            except ValueError:
                return bot.reply_to(message, "ℹ️ Invalid user ID format. Please provide a valid numeric ID.")
        
        # If command is a reply to a message
        if message.reply_to_message:
            user_to_unblock = message.reply_to_message.from_user.id
            success = db.unblock_user(user_to_unblock)
            
            if success:
                bot.reply_to(message, f"ℹ️ User {user_to_unblock} has been unblocked.")
            else:
                bot.reply_to(message, "ℹ️ Failed to unblock user. Please try again.")
            return
            
        # If neither condition is met
        bot.reply_to(message, "ℹ️ Please either:\n1. Reply to a message from the user you want to unblock\n2. Provide the user ID (e.g., /unblock 123456789)")
            
    except Exception as e:
        logger.error(f"Error in unblock command: {str(e)}")
        bot.reply_to(message, "ℹ️ An error occurred while unblocking the user.")

def cleanup_inactive_users(chat_id):
    """Remove users who haven't interacted in 5 minutes and clean old history"""
    if chat_id not in active_conversations:
        return
        
    current_time = datetime.now()
    
    # Clean old history
    if chat_id in group_chat_history:
        # Remove messages older than CHAT_TIMEOUT
        group_chat_history[chat_id] = [
            msg for msg in group_chat_history[chat_id]
            if (current_time - msg['timestamp']).total_seconds() <= CHAT_TIMEOUT
        ]
    
    # Remove inactive users
    inactive_users = [
        user_id for user_id, data in active_conversations[chat_id]['users'].items()
        if (current_time - data['timestamp']).total_seconds() > USER_TIMEOUT
    ]
    
    for user_id in inactive_users:
        del active_conversations[chat_id]['users'][user_id]
    
    # If no users left or chat inactive for 10 minutes, clear the conversation
    if (not active_conversations[chat_id]['users'] or 
        (current_time - active_conversations[chat_id]['last_activity']).total_seconds() > CHAT_TIMEOUT):
        del active_conversations[chat_id]

def can_join_conversation(chat_id, user_id):
    """Check if user can join the conversation"""
    cleanup_inactive_users(chat_id)
    
    if chat_id not in active_conversations:
        return True
        
    active_users = active_conversations[chat_id]['users']
    return (user_id in active_users or 
            len(active_users) < MAX_USERS_PER_CHAT)

def update_conversation_activity(chat_id, user_id, user_name, message_text=None):
    current_time = datetime.now()
    
    if chat_id not in active_conversations:
        active_conversations[chat_id] = {
            'users': {},
            'last_activity': current_time
        }
        group_chat_history[chat_id] = []  # Initialize empty history
    
    active_conversations[chat_id]['users'][user_id] = {
        'timestamp': current_time,
        'name': user_name
    }
    active_conversations[chat_id]['last_activity'] = current_time

    # Store message in group history if provided
    if message_text:
        # Check if this is a duplicate message
        if not group_chat_history[chat_id] or \
           group_chat_history[chat_id][-1]['message'] != message_text or \
           group_chat_history[chat_id][-1]['user_id'] != user_id:
            
            group_chat_history[chat_id].append({
                'user_id': user_id,
                'name': user_name,
                'message': message_text,
                'timestamp': current_time,
                'is_bot': False
            })
            
            # Keep only last MAX_HISTORY_LENGTH messages
            if len(group_chat_history[chat_id]) > MAX_HISTORY_LENGTH:
                group_chat_history[chat_id].pop(0)

# Add near other global variables at the top
group_chat_history = defaultdict(list)  # Format: {chat_id: [{'user_id': id, 'name': name, 'message': text, 'timestamp': time}, ...]}
MAX_HISTORY_LENGTH = 30  # Keep last 10 messages for context

def store_bot_response(chat_id, response_text):
    """Store bot's response in chat history"""
    current_time = datetime.now()
    group_chat_history[chat_id].append({
        'user_id': bot.get_me().id,
        'name': 'Girlfriend',
        'message': response_text,
        'timestamp': current_time,
        'is_bot': True
    })
    
    # Keep only last MAX_HISTORY_LENGTH messages
    if len(group_chat_history[chat_id]) > MAX_HISTORY_LENGTH:
        group_chat_history[chat_id].pop(0)

def get_conversation_context(chat_id):
    """Get formatted conversation context"""
    if chat_id not in group_chat_history:
        return ""
        
    context = []
    current_speaker = None
    messages = group_chat_history[chat_id][-20:]  # Last 10 messages
    
    for msg in messages:
        # Skip consecutive messages from the same user
        if current_speaker == msg['name']:
            continue
            
        current_speaker = msg['name']
        if msg['is_bot']:
            context.append(f"Girlfriend: {msg['message']}")
        else:
            context.append(f"{msg['name']}: {msg['message']}")
            
    return "\n".join(context)

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
            # Ensure webhook URL ends with /webhook
            if not webhook_url.endswith('/webhook'):
                webhook_url = f"{webhook_url}/webhook"
            
            logger.info(f"Setting webhook to {webhook_url}")
            bot.set_webhook(url=webhook_url)
            
            # Start Flask server
            app = Flask(__name__)
            
            # Add root route for basic health check
            @app.route('/')
            def index():
                return 'Bot is running!', 200
                
            # Add health check route
            @app.route('/health')
            def health():
                try:
                    # Test database connection
                    if not db.ensure_connection():
                        return jsonify({
                            'status': 'unhealthy',
                            'error': 'Database connection failed',
                            'timestamp': datetime.now().isoformat()
                        }), 500

                    # Test bot API connection
                    bot.get_me()

                    # If everything is OK
                    return jsonify({
                        'status': 'healthy',
                        'database': 'connected',
                        'bot': 'active',
                        'timestamp': datetime.now().isoformat()
                    }), 200

                except Exception as e:
                    logger.error(f"Health check failed: {str(e)}")
                    return jsonify({
                        'status': 'unhealthy',
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    }), 500

            # Modify the webhook route to be more specific
            @app.route('/webhook', methods=['POST'])
            def webhook():
                if request.headers.get('content-type') == 'application/json':
                    try:
                        json_string = request.get_data().decode('utf-8')
                        update = telebot.types.Update.de_json(json_string)
                        bot.process_new_updates([update])
                        return '', 200
                    except Exception as e:
                        logger.error(f"Error processing webhook: {str(e)}")
                        return jsonify({'error': str(e)}), 500
                else:
                    return jsonify({'error': 'Invalid content type'}), 403

            # Start server with proper error handling
            try:
                app.run(
                    host='0.0.0.0',
                    port=port,
                    threaded=True,
                    use_reloader=False
                )
            except Exception as e:
                logger.error(f"Flask server error: {str(e)}")
                raise
            
        else:
            # If no webhook URL, use polling (for local development)
            logger.info("No webhook URL found, using polling")
            bot.infinity_polling()
            
    except Exception as e:
        logger.error(f"Bot error: {str(e)}")

def retry_on_network_error(max_retries=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.RequestException, 
                        telebot.apihelper.ApiException,
                        ConnectionError,
                        ReadTimeout) as e:
                    retries += 1
                    if retries == max_retries:
                        logger.error(f"Failed after {max_retries} retries: {str(e)}")
                        raise
                    logger.warning(f"Attempt {retries} failed, retrying in {delay} seconds...")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator
