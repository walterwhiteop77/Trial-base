import pytz
import random
import logging
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from info import DB_URL, DB_NAME, TIMEZONE, VERIFY_EXPIRE
import motor.motor_asyncio
from info import DATABASE_URI, DATABASE_NAME
from datetime import datetime, timedelta


# Logger Setup
logger = logging.getLogger(__name__)

# Database Connection
client = AsyncIOMotorClient(DB_URL)
mydb = client[DB_NAME]

# ⏰ IST Timezone Helper (Using pytz for accuracy)
def get_ist_now():
    return datetime.now(pytz.timezone(TIMEZONE))

def get_ist_today():
    return get_ist_now().date()

# -------------------- DATABASE CLASS --------------------
class Database:
    def __init__(self):
        self.users = mydb.users
        self.codes = mydb.codes
        self.misc = mydb.misc
        self.videos = mydb.videoz
        self.historys = mydb.historyz
        self.brazzers = mydb.brazzers
        self.verify_id = mydb.verify_id
        self.refer_collection = mydb.referrals
        self.braz_history = mydb.braz_history        
        self.blocked_users = mydb.blocked_users

    # ---------- USERS ----------
    async def add_user(self, id, name):
        if not await self.users.find_one({"id": id}):
            await self.users.insert_one({
                "id": id,
                "name": name,
                "video_count": 0,
                "last_date": None,
                "expiry_time": None
            })

    async def is_user_exist(self, id):
        return bool(await self.users.find_one({'id': int(id)}))

    async def total_users_count(self):
        return await self.users.count_documents({})

    async def delete_user(self, user_id):
        await self.users.delete_many({'id': int(user_id)})

    async def get_user(self, user_id):
        return await self.users.find_one({"id": user_id})

    async def update_user(self, user_data):
        await self.users.update_one({"id": user_data["id"]}, {"$set": user_data}, upsert=True)

    async def get_all_users(self):
        return self.users.find({})
        
    # ---------- COUNTS ----------
    async def total_files_count(self):
        return await self.videos.count_documents({})

    async def total_brazzers_videos(self):
        return await self.brazzers.count_documents({})

    async def total_blocked_count(self):
        return await self.blocked_users.count_documents({})

    async def total_redeem_count(self):
        return await self.codes.count_documents({})
        
    # ---------- REFERRAL SYSTEM ----------
    
    async def is_user_in_list(self, user_id):
        user = await self.refer_collection.find_one({"user_id": int(user_id)})
        return True if user else False

    async def get_refer_points(self, user_id: int):
        user = await self.refer_collection.find_one({"user_id": int(user_id)})
        return user.get("points", 0) if user else 0

    async def add_refer_points(self, user_id: int, points: int):
        # Yeh points ko seedha SET kar dega (replace)
        await self.refer_collection.update_one(
            {"user_id": int(user_id)}, 
            {"$set": {"points": points}}, 
            upsert=True
        )

    async def change_points(self, user_id: int, amount: int):
        # Yeh points ko ADD ya SUBTRACT karega
        current_points = await self.get_refer_points(user_id)
        new_points = current_points + amount
        if new_points < 0:
            new_points = 0
            
        await self.refer_collection.update_one(
            {"user_id": int(user_id)}, 
            {"$set": {"points": new_points}}, 
            upsert=True
        )
        return new_points

    # ---------- MANUAL PAYMENT (ADD PREMIUM) ----------
    async def add_premium_access(self, user_id, days):
        # Current expiry check karo
        user = await self.get_user(user_id)
        now = datetime.now(timezone.utc)
        
        current_expiry = user.get("expiry_time")
        
        if current_expiry and isinstance(current_expiry, datetime):
            # Ensure timezone awareness
            if current_expiry.tzinfo is None:
                current_expiry = current_expiry.replace(tzinfo=timezone.utc)
            
            # Agar pehle se premium hai, to usme days add karo
            if current_expiry > now:
                new_expiry = current_expiry + timedelta(days=days)
            else:
                new_expiry = now + timedelta(days=days)
        else:
            # Agar premium nahi hai, to abhi se start karo
            new_expiry = now + timedelta(days=days)

        await self.users.update_one(
            {"id": user_id},
            {"$set": {"expiry_time": new_expiry}}
        )
        return new_expiry
        
    # ---------- BLOCK SYSTEM ----------

    async def unblock_user(self, user_id: int):
        """Unblock a user."""
        await self.blocked_users.delete_one({"user_id": user_id})

    async def get_all_blocked_users(self):
        """Fetch all blocked users."""
        return self.blocked_users.find({})

    # ---------- ADVANCED BAN SYSTEM DB ----------
    async def is_user_blocked(self, user_id):
        user = await self.blocked_users.find_one({"user_id": user_id})
        return bool(user)

    async def block_user(self, user_id, reason="Spam"):
        await self.blocked_users.update_one(
            {"user_id": user_id},
            {"$set": {"blocked_at": datetime.now(timezone.utc), "reason": reason}},
            upsert=True
        )

    async def add_temp_ban(self, user_id, duration_seconds):
        expiry = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
        await self.users.update_one(
            {"id": user_id},
            {"$set": {"temp_ban_expiry": expiry}}
        )

    async def is_temp_banned(self, user_id):
        user = await self.users.find_one({"id": user_id})
        if not user or "temp_ban_expiry" not in user:
            return False, 0
            
        expiry = user["temp_ban_expiry"]
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
            
        now = datetime.now(timezone.utc)
        if now < expiry:
            remaining = int((expiry - now).total_seconds())
            return True, remaining
        else:
            # Ban expire ho gaya, remove field
            await self.users.update_one({"id": user_id}, {"$unset": {"temp_ban_expiry": ""}})
            return False, 0
            
    # ---------- PREMIUM / EXPIRY ----------
    async def has_premium_access(self, user_id):
        user_data = await self.get_user(user_id)
        if not user_data:
            return False

        expiry_time = user_data.get("expiry_time")
        if not expiry_time:
            return False

        # Use UTC for comparison
        now = datetime.now(timezone.utc)
        
        if isinstance(expiry_time, datetime):
            # If stored time is naive (no timezone), treat it as UTC
            if expiry_time.tzinfo is None:
                expiry_time = expiry_time.replace(tzinfo=timezone.utc)
            return now <= expiry_time
        else:
            await self.users.update_one({"id": user_id}, {"$set": {"expiry_time": None}})
            return False

    async def update_one(self, filter_query, update_data):
        try:
            result = await self.users.update_one(filter_query, update_data)
            return result.matched_count == 1
        except Exception as e:
            print(f"Error updating document: {e}")
            return False

    async def get_expired(self, current_time):
        expired_users = []
        # Ensure current_time is consistent with DB storage (UTC usually)
        cursor = self.users.find({"expiry_time": {"$lt": current_time}})
        async for user in cursor:
            expired_users.append(user)
        return expired_users

    async def get_expiring_soon(self, label, delta):
        reminder_key = f"reminder_{label}_sent"
        now = datetime.now(timezone.utc)
        target_time = now + delta
        window = timedelta(seconds=30)
        start_range = target_time - window
        end_range = target_time + window
        reminder_users = []
        cursor = self.users.find({
            "expiry_time": {"$gte": start_range, "$lte": end_range},
            reminder_key: {"$ne": True}
        })
        async for user in cursor:
            reminder_users.append(user)
            await self.users.update_one(
                {"id": user["id"]}, {"$set": {reminder_key: True}}
            )
        return reminder_users

    async def remove_premium_access(self, user_id):
        return await self.update_one(
            {"id": user_id}, {"$set": {"expiry_time": None}}
        )

    async def premium_users_count(self):
        return await self.users.count_documents({
            "expiry_time": {"$gt": datetime.now(timezone.utc)}
        })

    async def get_db_size(self):
        stats = await mydb.command("dbstats")
        return stats.get("dataSize", 0)

    # ---------- VIDEOS SYSTEM ----------
    async def add_video(self, file_unique_id, file_id):
        exists = await self.videos.find_one({"file_unique_id": file_unique_id})
        if not exists:
            await self.videos.insert_one({
                "file_unique_id": file_unique_id,
                "file_id": file_id,
                "added_at": datetime.now(timezone.utc)
            })
            return True
        return False

    async def total_videos(self):
        return await self.videos.count_documents({})

    # 1. Main Videos aur History delete karne ke liye
    async def delete_main_data(self):
        await self.videos.delete_many({})
        await self.historys.delete_many({})
        return True

    # 2. Brazzers aur Braz History delete karne ke liye
    async def delete_brazzers_data(self):
        await self.brazzers.delete_many({})
        await self.braz_history.delete_many({})
        return True
        
    async def increase_video_count(self, user_id, username):
        today = get_ist_today()
        # Convert today date to datetime object for storage (Midnight)
        today_dt = datetime.combine(today, datetime.min.time())

        user = await self.users.find_one({"id": user_id})

        if user:
            last_date = user.get("last_date")
            
            # Safe conversion of stored date
            if isinstance(last_date, datetime):
                if last_date.tzinfo is not None:
                    # Convert to IST if aware
                    check_date = last_date.astimezone(pytz.timezone(TIMEZONE)).date()
                else:
                    # Treat naive as is
                    check_date = last_date.date()
            else:
                check_date = None

            if check_date != today:
                await self.users.update_one(
                    {"id": user_id},
                    {"$set": {
                        "video_count": 1,
                        "last_date": today_dt,
                        "username": username
                    }}
                )
            else:
                await self.users.update_one(
                    {"id": user_id},
                    {"$inc": {"video_count": 1},
                     "$set": {"username": username}}
                )
        else:
            await self.users.insert_one({
                "id": user_id,
                "name": username,
                "video_count": 1,
                "last_date": today_dt,
                "expiry_time": None
            })
            
    async def get_video_count(self, user_id: int):
        today = get_ist_today()
        user = await self.users.find_one({"id": user_id})
        if user:
            last_date = user.get("last_date")
            if isinstance(last_date, datetime):
                if last_date.tzinfo is not None:
                    check_date = last_date.astimezone(pytz.timezone(TIMEZONE)).date()
                else:
                    check_date = last_date.date()
                    
                if check_date == today:
                    return user.get("video_count", 0)
        return 0
        
    async def get_unseen_video(self, user_id):
        seen = await self.historys.find_one({"user_id": user_id})
        seen_ids = seen.get("seen", []) if seen else []

        # Optimization: Only fetch file_id field, limit 500
        cursor = self.videos.find({"file_id": {"$nin": seen_ids}}, {"file_id": 1}).limit(500)
        unseen_videos = await cursor.to_list(length=500)

        if not unseen_videos:
            return None

        video = random.choice(unseen_videos)
        await self.mark_seen(user_id, video["file_id"])
        return video["file_id"]

    async def get_random_video(self):
        """
        Gets a random video when user has seen everything.
        Uses MongoDB $sample for efficiency.
        """
        try:
            pipeline = [{"$sample": {"size": 1}}]
            cursor = self.videos.aggregate(pipeline)
            result = await cursor.to_list(length=1)
            
            if result:
                return result[0]["file_id"]
        except Exception as e:
            print(f"Random video error: {e}")
        return None

    async def mark_seen(self, user_id, file_id):
        await self.historys.update_one(
            {"user_id": user_id},
            {"$addToSet": {"seen": file_id}},
            upsert=True
        )

    async def reset_seen_videos(self, user_id: int):
        await self.historys.update_one(
            {"user_id": user_id},
            {"$set": {"seen": []}},
            upsert=True
        )
        
    async def add_brazzers_video(self, file_unique_id, file_id):
        exists = await self.brazzers.find_one({"file_unique_id": file_unique_id})
        if not exists:
            await self.brazzers.insert_one({
                "file_unique_id": file_unique_id,
                "file_id": file_id
            })
            return True
        return False

    # ✅ See Unseen Brazzers
    async def get_unseen_brazzers(self, user_id):
        seen = await self.braz_history.find_one({"user_id": user_id})
        seen_ids = seen.get("seen", []) if seen else []
        cursor = self.brazzers.find({"file_id": {"$nin": seen_ids}})
        unseen_videos = await cursor.to_list(length=1000)

        if not unseen_videos:
            return None

        video = random.choice(unseen_videos)
        await self.mark_brazzers_seen(user_id, video["file_id"])
        return video["file_id"]

    # ✅ Mark Brazzers Seen
    async def mark_brazzers_seen(self, user_id, file_id):
        await self.braz_history.update_one(
            {"user_id": user_id},
            {"$addToSet": {"seen": file_id}},
            upsert=True
        )
        
    async def reset_seen_brazzers(self, user_id: int):
        await self.braz_history.update_one(
            {"user_id": user_id},
            {"$set": {"seen": []}},
            upsert=True
        )
            
    # ---------- VERIFICATION SYSTEM ----------
    async def get_notcopy_user(self, user_id):
        user_id = int(user_id)
        user = await self.misc.find_one({"user_id": user_id})
        
        # Use UTC for default date
        default_date = datetime(2020, 5, 17, 0, 0, 0, tzinfo=timezone.utc)

        if not user:
            res = {
                "user_id": user_id,
                "last_verified": default_date,
            }
            # Insert and then return (safest method)
            await self.misc.insert_one(res)
            return res
        return user

    async def update_notcopy_user(self, user_id, value: dict):
        user_id = int(user_id)
        myquery = {"user_id": user_id}
        newvalues = {"$set": value}
        return await self.misc.update_one(myquery, newvalues)

    async def is_user_verified(self, user_id):
        user = await self.get_notcopy_user(user_id)
        
        # Fetch date safely
        pastDate = user.get("last_verified")
        
        # If date is missing for some reason, default to old date
        if not pastDate:
             pastDate = datetime(2020, 5, 17, 0, 0, 0, tzinfo=timezone.utc)

        # Standardize pastDate to UTC
        if pastDate.tzinfo is None:
             pastDate = pastDate.replace(tzinfo=timezone.utc)
        
        # Get current time in UTC
        current_time = datetime.now(timezone.utc)
        
        # 🟢 FAST EXPIRE LOGIC
        time_diff = current_time - pastDate
        
        if time_diff < timedelta(seconds=VERIFY_EXPIRE):
            return True
            
        return False

    async def create_verify_id(self, user_id: int, hash, file_id=None):
        res = {"user_id": user_id, "hash": hash, "verified": False, "file_id": file_id}
        return await self.verify_id.insert_one(res)

    async def get_verify_id_info(self, user_id: int, hash):
        return await self.verify_id.find_one({"user_id": user_id, "hash": hash})

    async def update_verify_id_info(self, user_id, hash, value: dict):
        myquery = {"user_id": user_id, "hash": hash}
        newvalues = {"$set": value}
        return await self.verify_id.update_one(myquery, newvalues)

    async def get_verification_stats(self):
        # Count verified users since midnight UTC
        midnight_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        level1_count = await self.misc.count_documents({
            "last_verified": {"$gte": midnight_utc}
        })
        return level1_count

# Initialize
db = Database()


# database/users_chats_db.py
# Enhanced with V2 features while preserving all existing functionality

import motor.motor_asyncio
from info import DATABASE_URI, DATABASE_NAME
from datetime import datetime, timedelta

class Database:
    
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users
        self.grp = self.db.groups
        
        # New collections for V2 features
        self.video_stats = self.db.video_stats  # Video likes/dislikes
        self.bookmarks = self.db.bookmarks  # User bookmarks

    def new_user(self, id, name):
        """Enhanced user document with V2 fields"""
        return dict(
            id=id,
            name=name,
            ban_status=True,  # True = Not banned (keeping existing logic)
            
            # EXISTING PREMIUM FIELDS (preserved)
            has_premium=False,
            premium_expires=None,
            premium_type=None,
            
            # NEW V2 FIELDS - Token/Access System
            access_expires=datetime.now(),  # Token expiration
            total_videos_watched=0,  # Lifetime count
            videos_today=0,  # Daily count
            last_video_date=datetime.now().date().isoformat(),  # For daily reset
            current_category='all',  # User's browsing category
            referral_count=0,  # Number of successful referrals
            liked_videos=[],  # List of video IDs user liked
            disliked_videos=[],  # List of video IDs user disliked
        )

    def new_group(self, id, title):
        """Existing group document - unchanged"""
        return dict(
            id=id,
            title=title,
            chat_status=True,
        )

    # ==================== EXISTING FUNCTIONS (PRESERVED) ====================

    async def add_user(self, id, name):
        """Existing function - unchanged"""
        user = self.new_user(id, name)
        await self.col.insert_one(user)

    async def is_user_exist(self, id):
        """Existing function - unchanged"""
        user = await self.col.find_one({'id': int(id)})
        return bool(user)

    async def total_users_count(self):
        """Existing function - unchanged"""
        count = await self.col.count_documents({})
        return count

    async def remove_ban(self, id):
        """Existing function - unchanged"""
        await self.col.update_one({'id': id}, {'$set': {'ban_status': True}})

    async def ban_user(self, user_id):
        """Existing function - unchanged"""
        await self.col.update_one({'id': user_id}, {'$set': {'ban_status': False}})

    async def get_ban_status(self, id):
        """Existing function - unchanged"""
        user = await self.col.find_one({'id': int(id)})
        if not user:
            return True
        return user.get('ban_status', True)

    async def get_all_users(self):
        """Existing function - unchanged"""
        return self.col.find({})

    async def delete_user(self, user_id):
        """Existing function - unchanged"""
        await self.col.delete_many({'id': int(user_id)})

    async def get_user(self, user_id):
        """Existing function - unchanged"""
        user = await self.col.find_one({'id': int(user_id)})
        return user

    # ==================== EXISTING PREMIUM FUNCTIONS (ENHANCED) ====================

    async def add_premium(self, user_id, time_str):
        """Enhanced to also grant access - existing functionality preserved"""
        # Parse time string (e.g., "1 month", "7 days")
        parts = time_str.split()
        amount = int(parts[0])
        unit = parts[1].lower()
        
        if 'month' in unit:
            days = amount * 30
        elif 'week' in unit:
            days = amount * 7
        elif 'day' in unit:
            days = amount
        elif 'year' in unit:
            days = amount * 365
        else:
            days = amount * 30  # Default to months
        
        expiry_time = datetime.now() + timedelta(days=days)
        
        await self.col.update_one(
            {'id': user_id},
            {'$set': {
                'has_premium': True,
                'premium_expires': expiry_time,
                'premium_type': time_str,
                'access_expires': expiry_time  # Also extend access token
            }}
        )

    async def remove_premium(self, user_id):
        """Existing function - unchanged"""
        await self.col.update_one(
            {'id': user_id},
            {'$set': {
                'has_premium': False,
                'premium_expires': None,
                'premium_type': None
            }}
        )

    async def has_premium_access(self, user_id):
        """Check if user has active premium - existing logic"""
        user = await self.col.find_one({'id': int(user_id)})
        if user and user.get('has_premium'):
            if user.get('premium_expires'):
                if user['premium_expires'] > datetime.now():
                    return True
                else:
                    # Auto-remove expired premium
                    await self.remove_premium(user_id)
        return False

    async def get_premium_users(self):
        """Existing function - unchanged"""
        users = self.col.find({'has_premium': True})
        return await users.to_list(length=None)

    # ==================== NEW V2 FUNCTIONS ====================

    async def check_access_status(self, user_id):
        """Check if user has active access (premium OR token)"""
        user = await self.get_user(user_id)
        if not user:
            return False
        
        # Premium users always have access
        if await self.has_premium_access(user_id):
            return True
        
        # Check token access
        access_expires = user.get('access_expires', datetime.now())
        return access_expires > datetime.now()

    async def grant_access(self, user_id, hours=12):
        """Grant temporary token access"""
        user = await self.get_user(user_id)
        if not user:
            return
        
        # Extend current access or create new
        current_expiry = user.get('access_expires', datetime.now())
        if current_expiry > datetime.now():
            # Extend from current expiry
            new_expiry = current_expiry + timedelta(hours=hours)
        else:
            # Create new expiry from now
            new_expiry = datetime.now() + timedelta(hours=hours)
        
        await self.col.update_one(
            {'id': user_id},
            {'$set': {'access_expires': new_expiry}}
        )

    async def increment_video_watch(self, user_id):
        """Track video watches with daily reset"""
        user = await self.get_user(user_id)
        if not user:
            return
        
        today = datetime.now().date().isoformat()
        
        # Reset daily count if new day
        if user.get('last_video_date') != today:
            await self.col.update_one(
                {'id': user_id},
                {'$set': {
                    'videos_today': 1,
                    'last_video_date': today
                },
                '$inc': {'total_videos_watched': 1}}
            )
        else:
            await self.col.update_one(
                {'id': user_id},
                {'$inc': {
                    'videos_today': 1,
                    'total_videos_watched': 1
                }}
            )

    async def update_user_category(self, user_id, category):
        """Update user's current browsing category"""
        await self.col.update_one(
            {'id': user_id},
            {'$set': {'current_category': category}}
        )

    async def increment_referral(self, user_id):
        """Increment referral count"""
        await self.col.update_one(
            {'id': user_id},
            {'$inc': {'referral_count': 1}}
        )

    async def like_video(self, user_id, video_id):
        """Add video to user's liked list"""
        # Remove from disliked if exists
        await self.col.update_one(
            {'id': user_id},
            {'$pull': {'disliked_videos': video_id}}
        )
        # Add to liked
        await self.col.update_one(
            {'id': user_id},
            {'$addToSet': {'liked_videos': video_id}}
        )
        
        # Update video stats
        await self.video_stats.update_one(
            {'video_id': video_id},
            {'$inc': {'likes': 1}, '$pull': {'disliked_by': user_id}, '$addToSet': {'liked_by': user_id}},
            upsert=True
        )

    async def dislike_video(self, user_id, video_id):
        """Add video to user's disliked list"""
        # Remove from liked if exists
        await self.col.update_one(
            {'id': user_id},
            {'$pull': {'liked_videos': video_id}}
        )
        # Add to disliked
        await self.col.update_one(
            {'id': user_id},
            {'$addToSet': {'disliked_videos': video_id}}
        )
        
        # Update video stats
        await self.video_stats.update_one(
            {'video_id': video_id},
            {'$inc': {'dislikes': 1}, '$pull': {'liked_by': user_id}, '$addToSet': {'disliked_by': user_id}},
            upsert=True
        )

    async def get_video_likes(self, video_id):
        """Get like count for a video"""
        stats = await self.video_stats.find_one({'video_id': video_id})
        return stats.get('likes', 0) if stats else 0

    async def get_video_dislikes(self, video_id):
        """Get dislike count for a video"""
        stats = await self.video_stats.find_one({'video_id': video_id})
        return stats.get('dislikes', 0) if stats else 0

    async def add_bookmark(self, user_id, video_id):
        """Bookmark a video"""
        await self.bookmarks.update_one(
            {'user_id': user_id},
            {'$addToSet': {'videos': video_id}},
            upsert=True
        )

    async def get_bookmarks(self, user_id):
        """Get user's bookmarks"""
        doc = await self.bookmarks.find_one({'user_id': user_id})
        return doc.get('videos', []) if doc else []

    async def remove_bookmark(self, user_id, video_id):
        """Remove a bookmark"""
        await self.bookmarks.update_one(
            {'user_id': user_id},
            {'$pull': {'videos': video_id}}
        )

    # ==================== EXISTING GROUP FUNCTIONS (UNCHANGED) ====================

    async def add_chat(self, chat, title):
        """Existing function - unchanged"""
        chat_doc = self.new_group(chat, title)
        await self.grp.insert_one(chat_doc)

    async def get_chat(self, chat):
        """Existing function - unchanged"""
        chat_doc = await self.grp.find_one({'id': int(chat)})
        return chat_doc.get('chat_status', True) if chat_doc else True

    async def re_enable_chat(self, id):
        """Existing function - unchanged"""
        await self.grp.update_one({'id': int(id)}, {'$set': {'chat_status': True}})

    async def update_settings(self, id, settings):
        """Existing function - unchanged"""
        await self.grp.update_one({'id': int(id)}, {'$set': {'settings': settings}})

    async def get_settings(self, id):
        """Existing function - unchanged"""
        chat = await self.grp.find_one({'id': int(id)})
        if chat:
            return chat.get('settings')
        return False

    async def disable_chat(self, chat):
        """Existing function - unchanged"""
        await self.grp.update_one({'id': int(chat)}, {'$set': {'chat_status': False}})

    async def total_chat_count(self):
        """Existing function - unchanged"""
        count = await self.grp.count_documents({})
        return count

    async def get_all_chats(self):
        """Existing function - unchanged"""
        return self.grp.find({})

    async def get_db_size(self):
        """Existing function - unchanged"""
        return (await self.db.command("dbstats"))['dataSize']

# Initialize database instance
db = Database(DATABASE_URI, DATABASE_NAME)
