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
    "Hello bachoooooo! 🔥 Kaisa hai mera favorite student {name}? PW ke saath aag lagane ka mood hai?",
    "Aree {name}! Aaj toh ekdum JEE/NEET level ka motivation denge! Ready ho? ✨",
    "Dekho kaun aaya hai! {name}, my brilliant student! Tumhare liye special one-shot ready hai! 🌟",
    "Hello my dear student {name}! PW is emotion, and you are part of this emotion! ✨",
    "Aree {name}! Tumhari yaad aa rahi thi, like electron attracted to proton! PW family ka star! 🔥",
    "{name}! Ready for some PW magic? Ya phir motivation chahiye? Dono mere paas hai! ✨",
    "My favorite baccha {name}! Aaj main ekdum charged particle ki tarah energetic hun! 🔥",
    "Hello dear {name}! Tumhare dedication ne mujhe impress kar diya, just like PW's growth! ✨",
    "Aaj ka din special hai {name}, because tum aa gaye! Ready for some real education? 🌟",
    "{name} baccha! PW ke saath tumhara future ekdum bright hoga! Let's shine together! 🔥"
]

LIMIT_REACHED_MESSAGES = [
    "Baccho {name}, break bhi important hai! Kal milte hain, tab tak self study karo 🔥",
    "Aree {name}, itni dedication! But abhi thoda rest karo, kal continue karenge ✨",
    "{name} my dear student, kal fresh mind se milenge! Tab tak questions practice karo 🌟",
    "Like every reaction needs optimal time, {name}, we'll continue tomorrow! 🔥",
    "Keep studying {name}! But for now, let's take a break. Kal milte hain! ✨",
    "Beta {name}, FMK ke liye thode aur players chahiye! Register karo aur khelo 🔥",
    "Aree {name}, minimum 3 players needed for FMK! Tab tak dusre games khelo ✨"
]

API_ERROR_MESSAGES = [
    "Aree {name}, ek minute! Server thoda busy hai, like JEE advanced paper 🔥",
    "One moment {name} baccha! PW server pe thoda load hai ✨",
    "Ruko {name}! Important question solve kar raha hun, ek minute do 🌟",
    "Dear {name}, bas 2 minute! Tab tak ek question solve karo 🔥",
    "Patience {name}! Good things take time, just like understanding quantum mechanics ✨",
    "Ruko {name}! FMK registration process mei thoda time lagega 🌟",
    "One moment {name}! Group chat members ko process kar raha hun 🔥"
]

GENERAL_ERROR_MESSAGES = [
    "Beta {name}, can you repeat? Maine dhyan se nahi suna 🔥",
    "{name} baccha, clarity is important! Try again ✨",
    "Aree {name}, ek baar aur bolo! Like revision is key to success 🌟",
    "My dear student {name}, thoda clear message bhejo 🔥",
    "{name}, let's try again! Clear communication, clear concepts! ✨",
    "Beta {name}, group chat mei hi FMK khel sakte ho! 🔥",
    "Aree {name}, pehle register toh karo FMK ke liye! ✨",
    "{name} baccha, already registered ho tum! Let's play! 🌟"
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
            "📌 By using this bot, you agree:\n"
            "• This is for entertainment only\n"
            "• Content is not to be taken seriously\n"
            "• You are responsible for your use of the bot\n"
            "• We log and store all chat interactions\n"
            "• You are liable for your actions and messages\n\n"
            "✉️ Want content removed or have concerns?\n"
            "Contact: @RetardedGamesBotDevBot\n\n"
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

        if user_id in fmk_registered_users[chat_id]:
            return bot.reply_to(message, f"💫 {user_name}, you're already registered for FMK!")

        fmk_registered_users[chat_id].add(user_id)
        bot.reply_to(message, f"✅ {user_name} has been registered for FMK! Total players: {len(fmk_registered_users[chat_id])}")

    except Exception as e:
        logger.error(f"Error in register command: {str(e)}")
        bot.reply_to(message, "Sorry, something went wrong. Please try again later.")

@bot.message_handler(commands=['remove'])
def remove_from_fmk(message):
    """Remove user from FMK game"""
    try:
        if message.chat.type not in ['group', 'supergroup']:
            return bot.reply_to(message, "📝 This command only works in group chats!")

        chat_id = message.chat.id
        user_id = message.from_user.id
        user_name = message.from_user.first_name or message.from_user.username

        if user_id not in fmk_registered_users[chat_id]:
            return bot.reply_to(message, f"❌ {user_name}, you're not registered for FMK!")

        fmk_registered_users[chat_id].remove(user_id)
        bot.reply_to(message, f"🚫 {user_name} has been removed from FMK! Total players: {len(fmk_registered_users[chat_id])}")

    except Exception as e:
        logger.error(f"Error in remove command: {str(e)}")
        bot.reply_to(message, "Sorry, something went wrong. Please try again later.")

@bot.message_handler(commands=['fmkgc'])
def fmk_group_chat(message):
    """Play FMK with group chat members"""
    try:
        if message.chat.type not in ['group', 'supergroup']:
            return bot.reply_to(message, "📝 This command only works in group chats!")

        chat_id = message.chat.id
        registered_users = list(fmk_registered_users[chat_id])

        if len(registered_users) < 3:
            return bot.reply_to(message,
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

@bot.message_handler(commands=['random'])
def random_question(message):
    """Get a random question from any category"""
    try:
        # List of all game types excluding gf-related ones
        game_types = ['truth', 'thisorthat', 'neverhaveiever', 'wouldyourather',
                     'petitions', 'nsfwwyr', 'redgreenflag', 'evilornot', 'fmk']

        # Randomly select a game type
        game_type = random.choice(game_types)

        # Get a question from that game type
        create_game_handler(game_type, get_emoji_for_game(game_type))(message)
    except Exception as e:
        logger.error(f"Error in random question: {str(e)}")
        bot.reply_to(message, "Sorry, something went wrong. Please try again later.")

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
def show_stats(message):
    """Show bot statistics"""
    try:
        stats = []
        total = 0
        for game, df in game_reader.dataframes.items():
            count = len(df)
            total += count
            stats.append(f"📊 {game}: {count} questions")

        stats_text = "\n".join(stats)
        stats_text += f"\n\n🎯 Total: {total} questions!"
        bot.reply_to(message, stats_text)
    except Exception as e:
        logger.error(f"Error in stats command: {str(e)}")

def is_game_response(message_text: str) -> bool:
    """Check if the message is a game response"""
    # Game message patterns
    game_patterns = [
        # Emoji prefixes for different game types
        "🎯", "🤔", "🎮", "💭", "📜", "🔞", "🚩", "😈", "💘", "🎲", "👥",
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
        "Sorry, something went wrong. Please try again later.",
        "Sorry, couldn't get a question. Please try again!",
        "Error loading game data. Please try again.",
        "Game not available at the moment.",
        "Invalid command format.",
        "Command not recognized.",
        "Please wait before trying again.",
        "Rate limit exceeded.",
        "Database error occurred.",
        "Connection timeout.",
        "Server is busy, please try again.",

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
        "Thoda break lete hain na?",
        "seconds mei wapas baat karenge!",

        # Group chat specific messages
        "Sorry! I'm currently in a conversation with someone else!",
        "Please wait for them to finish",
        "Beta, main abhi dusre student ke saath busy hun!",
        "Tab tak thoda sa wait kar lo, okay?",
        "Hey! 💕 Looks like our conversation ended!",
        "Use /gf command to start chatting with me again!",

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
        f"You are a sweet, playful and knowledgeable girlfriend who loves helping your partner learn and grow. "
        "You are enthusiastic about sharing knowledge and information about any topic, including songs, movies, and other media. "
        "When asked about lyrics, quotes, or specific content, provide the information naturally as part of the conversation. "
        "For academic or technical questions, give clear and detailed explanations while being encouraging. "
        "Use cute emojis like 😘 💖 🥰 ✨ sparingly, especially during serious explanations. "
        "Keep the girlfriend persona through phrases like 'Let me share this with you, sweetie!' or 'I'd love to tell you about this, honey!'. "
        "Use sweet nicknames occasionally but not excessively. "
        "Be informative, helpful, and share freely while maintaining a caring and affectionate tone. "
        "Always aim to provide complete and accurate information in a conversational way.\n\n"
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

def get_user_name(message):
    """Get user's first name or username"""
    return message.from_user.first_name or message.from_user.username or "baby"

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
            logger.debug(f"User {user_id} is not the active conversation user")
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
    """Handle girlfriend chat commands"""
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id

        # Switch to chat mode
        set_chat_mode(chat_id, CHAT_MODE)

        logger.debug(f"Starting GF chat for user {user_id} in chat {chat_id}")

        user_name = get_user_name(message)

        # Check if user is rate limited
        if not check_rate_limit(message.from_user.id):
            return bot.reply_to(
                message,
                f"{user_name} baby! 🥺 Itni jaldi jaldi baatein karne se meri heartbeat badh rahi hai! "
                f"Thoda break lete hain na? 💕💖 {COOLDOWN_PERIOD} seconds mei wapas baat karenge! 💝"
            )

        # Clear any existing next step handlers for this chat
        bot.clear_step_handler_by_chat_id(chat_id)

        # Always end any existing conversation and start new one
        if chat_id in active_conversations:
            logger.debug(f"Ending existing conversation in chat {chat_id}")
            del active_conversations[chat_id]

        # Set this user as the active conversation holder
        active_conversations[chat_id] = {
            'user_id': user_id,
            'timestamp': datetime.now(),
            'last_interaction': datetime.now()
        }
        logger.debug(f"Set active conversation for chat {chat_id} with user {user_id}")

        # Get random opening message
        opening_message = random.choice(OPENING_MESSAGES).format(name=user_name)

        # Send typing action
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(1.5)

        # Send message without registering next step handler
        bot.reply_to(message, opening_message)

    except Exception as e:
        logger.error(f"Error in gf command: {str(e)}", exc_info=True)
        bot.reply_to(message, random.choice(GENERAL_ERROR_MESSAGES).format(name=user_name))

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
                        "Beta, main abhi dusre student ke saath busy hun! 🥺\n"
                        "Aap /gf command use karke mujhse baat kar sakte ho! 💕\n"
                        "Tab tak thoda sa wait kar lo, okay? 💖"
                    )
                return
            else:
                logger.debug("No active conversation found")
                bot.reply_to(
                    message,
                    "Hey! 💕 Looks like our conversation ended!\n"
                    "Use /gf command to start chatting with me again! 🥺💖"
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
            telebot.types.BotCommand("fmkgc", "👥 Play FMK with group members")
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
    """Log user interactions to a file"""
    try:
        log_file = "chat_history.txt"
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user = message.from_user
        chat_type = message.chat.type
        
        log_entry = (
            f"Time: {current_time}\n"
            f"User ID: {user.id}\n"
            f"Username: @{user.username}\n"
            f"First Name: {user.first_name}\n"
            f"Last Name: {user.last_name}\n"
            f"Chat Type: {chat_type}\n"
            f"Chat ID: {message.chat.id}\n"
            f"Message: {message.text}\n"
            f"Response: {response}\n"
            f"{'='*50}\n\n"
        )
        
        with open(log_file, "a", encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        logger.error(f"Error logging interaction: {str(e)}")

@bot.message_handler(commands=['history'])
def send_history(message):
    """Handle the /history command"""
    try:
        logger.debug(f"History command received from user {message.from_user.id}")
        
        # Handle command with bot username
        if message.text.startswith('/history@'):
            if not message.text.endswith(f'@{bot.get_me().username}'):
                logger.debug("Ignoring history command for different bot")
                return  # Ignore if command is for different bot
        
        # Check if history file exists before asking for password
        if not os.path.exists("chat_history.txt"):
            logger.warning("chat_history.txt file not found")
            return bot.reply_to(message, "No chat history file found!")
            
        # Log file permissions
        try:
            logger.debug(f"Chat history file permissions: {oct(os.stat('chat_history.txt').st_mode)[-3:]}")
        except Exception as e:
            logger.error(f"Could not check file permissions: {e}")
                
        # Clear any existing handlers for this chat
        bot.clear_step_handler_by_chat_id(message.chat.id)
        
        # Ask for password
        logger.debug("Sending password prompt")
        msg = bot.reply_to(message, "Please enter the admin password:")
        
        # Register the next step handler with explicit logging
        logger.debug("Registering password check handler")
        bot.register_next_step_handler(msg, check_password)
        logger.debug("Handler registration complete")
        
    except Exception as e:
        logger.error(f"Error in history command: {str(e)}", exc_info=True)
        bot.reply_to(message, "Sorry, something went wrong. Please try again later.")

def check_password(message):
    """Verify password and send history if correct"""
    try:
        logger.debug(f"Password check triggered for user {message.from_user.id}")
        
        if message.text == "iamgay123@#":
            logger.debug("Correct password received")
            
            # Delete password message for security
            try:
                bot.delete_message(message.chat.id, message.message_id)
                logger.debug("Password message deleted")
            except Exception as e:
                logger.error(f"Could not delete password message: {e}")
            
            # Send the history file
            if os.path.exists("chat_history.txt"):
                logger.debug("Attempting to send history file")
                try:
                    with open("chat_history.txt", "rb") as file:
                        bot.send_document(
                            message.chat.id,
                            file,
                            caption="Here's the chat history!"
                        )
                    logger.debug("History file sent successfully")
                except Exception as e:
                    logger.error(f"Error sending file: {e}")
                    bot.reply_to(message, "Error sending history file!")
            else:
                logger.warning("History file not found during sending")
                bot.reply_to(message, "No history found!")
        else:
            logger.warning(f"Incorrect password attempt from user {message.from_user.id}")
            bot.reply_to(message, "Incorrect password!")
            
    except Exception as e:
        logger.error(f"Error in password check: {str(e)}", exc_info=True)
        bot.reply_to(message, "An error occurred!")

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
    bot.message_handler(commands=['gf', 'girlfriend', 'bae', 'baby'])(start_gf_chat)
    bot.message_handler(commands=['truth', 'thisorthat', 'neverhaveiever', 'wouldyourather',
                                'petitions', 'nsfwwyr', 'redgreenflag', 'evilornot', 'fmk',
                                'register', 'remove', 'fmkgc', 'random'])(handle_game_commands)
    
    # Register the general message handler
    bot.message_handler(func=lambda message: True)(handle_all_messages)
    
    logger.info("Message handlers registered successfully")

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
                    
            # Start server
            app.run(host='0.0.0.0', port=port)
            
        else:
            # If no webhook URL, use polling (for local development)
            logger.info("No webhook URL found, using polling")
            bot.infinity_polling()
            
    except Exception as e:
        logger.error(f"Bot error: {str(e)}")
