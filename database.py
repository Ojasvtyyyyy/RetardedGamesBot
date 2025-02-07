from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.client = None
        self.db = None
        self.connect()

    def connect(self):
        try:
            mongodb_uri = os.environ.get('MONGODB_URI')
            if not mongodb_uri:
                raise ValueError("MONGODB_URI environment variable not set")
            
            self.client = MongoClient(mongodb_uri)
            self.db = self.client.telegram_bot
            logger.info("Successfully connected to MongoDB")
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {str(e)}")
            raise

    # FMK Players Management
    def add_fmk_player(self, chat_id: int, user_id: int, user_name: str):
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
            cursor = collection.find().sort("timestamp", -1).limit(limit)
            return list(cursor)
        except Exception as e:
            logger.error(f"Error getting chat history: {str(e)}")
            return []

    # Terms and Conditions Management
    def save_user_agreement(self, user_id: int, username: str, first_name: str, 
                           last_name: str, chat_id: int, chat_type: str):
        """Save user's agreement to terms and conditions"""
        try:
            collection = self.db.user_agreements
            agreement = {
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
                {"$set": agreement},
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            logger.error(f"Error saving user agreement: {str(e)}")
            return False

    def has_user_agreed(self, user_id: int):
        """Check if user has agreed to terms and conditions"""
        try:
            collection = self.db.user_agreements
            result = collection.find_one({"user_id": user_id})
            return bool(result)
        except Exception as e:
            logger.error(f"Error checking user agreement: {str(e)}")
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
        """Check if user is blocked"""
        try:
            collection = self.db.blocked_users
            result = collection.find_one({"user_id": user_id})
            return bool(result)
        except Exception as e:
            logger.error(f"Error checking blocked status: {str(e)}")
            return False

# Create a singleton instance
db = Database()
