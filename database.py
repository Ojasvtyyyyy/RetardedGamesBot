from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv
import logging
import time

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        # Initialize reconnection timer first
        self.last_reconnect_attempt = 0
        self.reconnect_cooldown = 60  # seconds
        
        # Then initialize database connections
        self.client = None
        self.db = None
        self.connect()

    def connect(self):
        """Connect to MongoDB with improved retry logic"""
        try:
            # Check cooldown period
            current_time = time.time()
            if current_time - self.last_reconnect_attempt < self.reconnect_cooldown:
                logger.debug("Skipping reconnect attempt due to cooldown")
                return False
                
            self.last_reconnect_attempt = current_time
            mongodb_uri = os.environ.get('MONGODB_URI')
            if not mongodb_uri:
                raise ValueError("MONGODB_URI environment variable not set")
            
            # Increased timeouts and better retry settings
            max_retries = 5
            retry_count = 0
            while retry_count < max_retries:
                try:
                    self.client = MongoClient(mongodb_uri,
                                           serverSelectionTimeoutMS=20000,  # Increased timeout
                                           connectTimeoutMS=20000,         # Increased timeout
                                           socketTimeoutMS=20000,          # Increased timeout
                                           maxPoolSize=10,                 # Reduced pool size
                                           minPoolSize=1,                  # Keep minimum connection
                                           maxIdleTimeMS=45000,           # Close idle connections after 45s
                                           retryWrites=True,
                                           retryReads=True,               # Added retry reads
                                           w='majority',                  # Write concern
                                           waitQueueTimeoutMS=10000)      # Queue timeout
                    
                    # Test the connection
                    self.client.admin.command('ping')
                    self.db = self.client.telegram_bot
                    logger.info("Successfully connected to MongoDB")
                    return True
                    
                except Exception as e:
                    retry_count += 1
                    if retry_count == max_retries:
                        raise
                    wait_time = min(2 ** retry_count, 30)  # Cap max wait at 30 seconds
                    logger.warning(f"MongoDB connection attempt {retry_count} failed: {str(e)}")
                    logger.warning(f"Waiting {wait_time} seconds before retry")
                    time.sleep(wait_time)
                    
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {str(e)}")
            self.client = None
            self.db = None
            return False

    def ensure_connection(self):
        """Ensure database connection is active"""
        try:
            if self.db is None:
                return self.connect()
            
            # Test existing connection
            self.client.admin.command('ping')
            return True
            
        except Exception as e:
            logger.warning(f"Database connection lost: {str(e)}")
            return self.connect()

    # FMK Players Management
    def add_fmk_player(self, chat_id: int, user_id: int, user_name: str):
        if not self.ensure_connection():
            logger.error("Database connection failed")
            return False
            
        try:
            collection = self.db.fmk_players
            result = collection.update_one(
                {"chat_id": chat_id},
                {
                    "$addToSet": {
                        "players": {
                            "user_id": user_id,
                            "user_name": user_name
                        }
                    }
                },
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            logger.error(f"Error adding FMK player: {str(e)}")
            return False

    def remove_fmk_player(self, chat_id: int, user_id: int):
        try:
            collection = self.db.fmk_players
            result = collection.update_one(
                {"chat_id": chat_id},
                {
                    "$pull": {
                        "players": {
                            "user_id": user_id
                        }
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error removing FMK player: {str(e)}")
            return False

    def get_fmk_players(self, chat_id: int):
        try:
            collection = self.db.fmk_players
            result = collection.find_one({"chat_id": chat_id})
            return result.get('players', []) if result else []
        except Exception as e:
            logger.error(f"Error getting FMK players: {str(e)}")
            return []

    # Chat History Management
    def log_interaction(self, user_id: int, username: str, first_name: str, 
                       last_name: str, chat_id: int, chat_type: str, 
                       message: str, response: str):
        try:
            collection = self.db.chat_history
            interaction = {
                "timestamp": datetime.now(),
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "chat_id": chat_id,
                "chat_type": chat_type,
                "message": message,
                "response": response
            }
            result = collection.insert_one(interaction)
            return result.inserted_id is not None
        except Exception as e:
            logger.error(f"Error logging interaction: {str(e)}")
            return False

    def get_chat_history(self, limit: int = 100):
        try:
            collection = self.db.chat_history
            # If limit is 0, don't apply any limit
            cursor = collection.find().sort("timestamp", -1)
            if limit > 0:
                cursor = cursor.limit(limit)
            return list(cursor)
        except Exception as e:
            logger.error(f"Error getting chat history: {str(e)}")
            return []

    # Terms and Conditions Management
    def save_user_agreement(self, user_id: int, username: str, first_name: str, 
                           last_name: str, chat_id: int, chat_type: str):
        """Save user agreement with retry logic"""
        try:
            if self.db is None:
                logger.error("Database not available")
                return False

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    collection = self.db.user_agreements
                    agreement_data = {
                        "user_id": user_id,
                        "username": username,
                        "first_name": first_name,
                        "last_name": last_name,
                        "chat_id": chat_id,
                        "chat_type": chat_type,
                        "agreed_at": datetime.now()
                    }
                    result = collection.update_one(
                        {"user_id": user_id},
                        {"$set": agreement_data},
                        upsert=True
                    )
                    return result.modified_count > 0 or result.upserted_id is not None
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"Retry {attempt + 1} failed: {str(e)}")
                    time.sleep(1)
            return False
        except Exception as e:
            logger.error(f"Error saving user agreement: {str(e)}")
            return False

    def has_user_agreed(self, user_id: int):
        """Check if user has agreed to terms and conditions"""
        try:
            if self.db is None:
                logger.warning("Database not available, defaulting to requiring agreement")
                return False
                
            collection = self.db.user_agreements
            result = collection.find_one({"user_id": user_id})
            return bool(result)
        except Exception as e:
            logger.error(f"Error checking user agreement: {str(e)}")
            # Default to requiring agreement if we can't check
            return False

    # Blocking functionality
    def block_user(self, user_id: int, blocked_by: int, reason: str = "Manual block"):
        """Block a user from using /gf"""
        try:
            collection = self.db.blocked_users
            block_data = {
                "user_id": user_id,
                "blocked_by": blocked_by,
                "blocked_at": datetime.now(),
                "reason": reason
            }
            result = collection.update_one(
                {"user_id": user_id},
                {"$set": block_data},
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            logger.error(f"Error blocking user: {str(e)}")
            return False

    def unblock_user(self, user_id: int):
        """Unblock a user"""
        try:
            collection = self.db.blocked_users
            result = collection.delete_one({"user_id": user_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error unblocking user: {str(e)}")
            return False

    def is_user_blocked(self, user_id: int):
        """Check if user is blocked with fallback"""
        try:
            if self.db is None:
                logger.warning("Database not available, defaulting to not blocked")
                return False
                
            collection = self.db.blocked_users
            result = collection.find_one({"user_id": user_id})
            return bool(result)
        except Exception as e:
            logger.error(f"Error checking blocked status: {str(e)}")
            # Default to not blocked if we can't check
            return False

    def is_user_registered(self, chat_id: int, user_id: int):
        """Check if user is registered for FMK in this chat"""
        try:
            if self.db is None:
                return False
            
            collection = self.db.fmk_players
            result = collection.find_one({
                "chat_id": chat_id,
                "players": {
                    "$elemMatch": {
                        "user_id": user_id
                    }
                }
            })
            return bool(result)
        except Exception as e:
            logger.error(f"Error checking FMK registration: {str(e)}")
            return False

    # Chat Participant Management
    def add_chat_participant(self, chat_id: int, user_id: int, user_name: str):
        """Add participant to active chat (up to 3 users)"""
        try:
            if self.db is None:
                return False
            
            collection = self.db.active_chats
            
            # Check current participants count
            chat = collection.find_one({"chat_id": chat_id})
            if chat and len(chat.get('participants', [])) >= 3:
                return False, "Chat is full (max 3 users)"
            
            # Add new participant
            result = collection.update_one(
                {"chat_id": chat_id},
                {
                    "$addToSet": {
                        "participants": {
                            "user_id": user_id,
                            "user_name": user_name,
                            "joined_at": datetime.now()
                        }
                    }
                },
                upsert=True
            )
            return True, None
        except Exception as e:
            logger.error(f"Error adding chat participant: {str(e)}")
            return False, str(e)

    def remove_chat_participant(self, chat_id: int, user_id: int):
        """Remove participant from active chat"""
        try:
            if self.db is None:
                return False
            
            collection = self.db.active_chats
            result = collection.update_one(
                {"chat_id": chat_id},
                {
                    "$pull": {
                        "participants": {
                            "user_id": user_id
                        }
                    }
                }
            )
            
            # If no participants left, remove chat
            chat = collection.find_one({"chat_id": chat_id})
            if chat and len(chat.get('participants', [])) == 0:
                collection.delete_one({"chat_id": chat_id})
            
            return True
        except Exception as e:
            logger.error(f"Error removing chat participant: {str(e)}")
            return False

    def get_chat_participants(self, chat_id: int):
        """Get list of participants in a chat"""
        try:
            if self.db is None:
                return []
            
            collection = self.db.active_chats
            chat = collection.find_one({"chat_id": chat_id})
            return chat.get('participants', []) if chat else []
        except Exception as e:
            logger.error(f"Error getting chat participants: {str(e)}")
            return []

    def store_user_context(self, chat_id: int, user_id: int, context: str):
        """Store user's last message context"""
        try:
            if self.db is None:
                return False
            
            collection = self.db.user_contexts
            result = collection.update_one(
                {"chat_id": chat_id, "user_id": user_id},
                {
                    "$set": {
                        "context": context,
                        "updated_at": datetime.now()
                    }
                },
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error storing user context: {str(e)}")
            return False

    def get_user_context(self, chat_id: int, user_id: int):
        """Get user's last message context"""
        try:
            if self.db is None:
                return None
            
            collection = self.db.user_contexts
            result = collection.find_one({"chat_id": chat_id, "user_id": user_id})
            return result.get('context') if result else None
        except Exception as e:
            logger.error(f"Error getting user context: {str(e)}")
            return None

    def get_chat_history_for_prompt(self, chat_id: int, limit: int = 10):
        """Get formatted chat history for AI prompt"""
        try:
            if self.db is None:
                return ""
            
            collection = self.db.chat_history
            history = collection.find(
                {"chat_id": chat_id}
            ).sort("timestamp", -1).limit(limit)
            
            formatted_history = []
            history_list = list(history)
            for msg in reversed(history_list):  # Process in chronological order
                user_name = msg.get('first_name') or msg.get('username') or f"User{msg['user_id']}"
                if msg.get('message'):
                    formatted_history.append(f"{user_name}: {msg['message']}")
                if msg.get('response'):
                    formatted_history.append(f"Girlfriend: {msg['response']}")
                
            return "\n".join(formatted_history)
        except Exception as e:
            logger.error(f"Error getting chat history for prompt: {str(e)}")
            return ""

    def get_user_original_chat_type(self, user_id: int):
        """Get the original chat type where user started terms agreement"""
        try:
            if self.db is None:
                logger.warning("Database not available")
                return {}
            
            collection = self.db.user_chat_types
            result = collection.find_one({"user_id": user_id})
            if result:
                return {
                    'chat_id': result.get('chat_id'),
                    'chat_type': result.get('chat_type')
                }
            return {}
        except Exception as e:
            logger.error(f"Error getting user chat type: {str(e)}")
            return {}

    def save_user_chat_type(self, user_id: int, chat_id: int, chat_type: str):
        """Save the original chat type where user started terms agreement"""
        try:
            if self.db is None:
                logger.error("Database not available")
                return False
            
            collection = self.db.user_chat_types
            result = collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "chat_id": chat_id,
                        "chat_type": chat_type,
                        "updated_at": datetime.now()
                    }
                },
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            logger.error(f"Error saving user chat type: {str(e)}")
            return False

# Create a singleton instance
db = Database()
