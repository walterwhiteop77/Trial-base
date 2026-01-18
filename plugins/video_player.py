import asyncio
import random
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.users_db import db
from info import PROTECT_CONTENT, PREMIUM_DAILY_LIMIT, DAILY_LIMIT, VERIFICATION_DAILY_LIMIT
from utils import temp

# Store active players {user_id: {"message_id": int, "current_video": str, "category": str, "expire_task": Task}}
ACTIVE_PLAYERS = {}

# ================================================
# 🎬 VIDEO PLAYER HANDLER
# ================================================
@Client.on_message(filters.command("player") | filters.regex(r"(?i)^get video$"))
async def video_player_handler(client, message: Message):
    user_id = message.from_user.id
    
    # Check if user already has active player
    if user_id in ACTIVE_PLAYERS:
        try:
            old_msg_id = ACTIVE_PLAYERS[user_id]["message_id"]
            await client.delete_messages(message.chat.id, old_msg_id)
        except:
            pass
        
        # Cancel old expiry task
        if "expire_task" in ACTIVE_PLAYERS[user_id]:
            ACTIVE_PLAYERS[user_id]["expire_task"].cancel()
    
    # Get first video
    video_id = await db.get_unseen_video(user_id)
    
    if not video_id:
        video_id = await db.get_random_video()
    
    if not video_id:
        return await message.reply("❌ No videos available.")
    
    # Get video metadata
    video_data = await db.get_video_metadata(video_id)
    
    # Build player interface
    player_msg = await send_player(client, message, video_id, video_data, category="All")
    
    # Store player info
    ACTIVE_PLAYERS[user_id] = {
        "message_id": player_msg.id,
        "current_video": video_id,
        "category": "All",
        "expire_task": None
    }
    
    # Start expiry timer (10 minutes)
    expire_task = asyncio.create_task(expire_player(client, message.chat.id, player_msg.id, user_id))
    ACTIVE_PLAYERS[user_id]["expire_task"] = expire_task
    
    # Increase video count
    username = message.from_user.username or message.from_user.first_name
    await db.increase_video_count(user_id, username)

# ================================================
# 🎨 BUILD PLAYER MESSAGE
# ================================================
async def send_player(client, message, video_id, video_data, category="All"):
    """Send/Update video player with buttons"""
    
    # Video metadata
    video_unique_id = video_data.get("file_unique_id", "Unknown")
    likes = video_data.get("likes", 0)
    dislikes = video_data.get("dislikes", 0)
    total_votes = likes + dislikes
    like_percentage = int((likes / total_votes * 100)) if total_votes > 0 else 0
    
    # Caption
    caption = (
        f"<b>Video ID:</b> <code>{video_unique_id}</code>\n"
        f"<b>{like_percentage}% users liked this</b>\n"
        f"<b>Category:</b> {category}\n\n"
        f"<blockquote>ᴛʜɪꜱ ᴘʟᴀʏᴇʀ ᴡɪʟʟ ᴇxᴘɪʀᴇ ɪɴ 10 ᴍɪɴᴜᴛᴇꜱ.\n"
        f"ᴜꜱᴇ ɴᴇxᴛ/ᴘʀᴇᴠɪᴏᴜꜱ ᴛᴏ ꜱᴡɪᴛᴄʜ ᴠɪᴅᴇᴏꜱ.</blockquote>"
    )
    
    # Buttons
    buttons = [
        [
            InlineKeyboardButton("👍 Like", callback_data=f"player_like_{video_unique_id}"),
            InlineKeyboardButton("👎 Dislike", callback_data=f"player_dislike_{video_unique_id}"),
            InlineKeyboardButton("⬇️ Download", callback_data=f"player_download_{video_unique_id}")
        ],
        [
            InlineKeyboardButton("⏮️ Previous", callback_data="player_prev"),
            InlineKeyboardButton("Next ⏭️", callback_data="player_next")
        ],
        [
            InlineKeyboardButton("🔄 Change Category", callback_data="player_category"),
            InlineKeyboardButton("🔖 Bookmark", callback_data=f"player_bookmark_{video_unique_id}")
        ],
        [
            InlineKeyboardButton("⭐ For D@rk C00ntent", url="https://t.me/your_channel")
        ]
    ]
    
    # Send video
    player_msg = await client.send_video(
        chat_id=message.chat.id,
        video=video_id,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(buttons),
        protect_content=PROTECT_CONTENT
    )
    
    return player_msg

# ================================================
# 🔘 CALLBACK HANDLERS
# ================================================
@Client.on_callback_query(filters.regex(r"^player_"))
async def player_callback_handler(client, callback: CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data
    
    # Check if player exists
    if user_id not in ACTIVE_PLAYERS:
        return await callback.answer("⚠️ Player expired. Use /player to start again.", show_alert=True)
    
    player_info = ACTIVE_PLAYERS[user_id]
    
    # ---- NEXT BUTTON ----
    if data == "player_next":
        await handle_next_video(client, callback, player_info)
    
    # ---- PREVIOUS BUTTON ----
    elif data == "player_prev":
        await handle_prev_video(client, callback, player_info)
    
    # ---- LIKE BUTTON ----
    elif data.startswith("player_like_"):
        video_id = data.replace("player_like_", "")
        await db.add_video_reaction(video_id, "like", user_id)
        await callback.answer("👍 Liked!", show_alert=False)
        await refresh_player(client, callback, player_info)
    
    # ---- DISLIKE BUTTON ----
    elif data.startswith("player_dislike_"):
        video_id = data.replace("player_dislike_", "")
        await db.add_video_reaction(video_id, "dislike", user_id)
        await callback.answer("👎 Disliked!", show_alert=False)
        await refresh_player(client, callback, player_info)
    
    # ---- DOWNLOAD BUTTON ----
    elif data.startswith("player_download_"):
        await callback.answer("⬇️ Downloading... (Feature coming soon)", show_alert=True)
    
    # ---- BOOKMARK BUTTON ----
    elif data.startswith("player_bookmark_"):
        video_id = data.replace("player_bookmark_", "")
        await db.add_bookmark(user_id, video_id)
        await callback.answer("🔖 Bookmarked!", show_alert=True)
    
    # ---- CATEGORY BUTTON ----
    elif data == "player_category":
        await callback.answer("🔄 Category feature coming soon!", show_alert=True)

# ================================================
# ⏭️ NEXT VIDEO HANDLER
# ================================================
async def handle_next_video(client, callback, player_info):
    user_id = callback.from_user.id
    
    # Get new video
    video_id = await db.get_unseen_video(user_id)
    
    if not video_id:
        video_id = await db.get_random_video()
    
    if not video_id:
        return await callback.answer("❌ No more videos!", show_alert=True)
    
    # Update player
    video_data = await db.get_video_metadata(video_id)
    
    # Edit message with new video
    await edit_player(client, callback, video_id, video_data, player_info)
    
    # Update stored info
    ACTIVE_PLAYERS[user_id]["current_video"] = video_id
    
    await callback.answer("⏭️ Next video loaded!")

# ================================================
# ⏮️ PREVIOUS VIDEO HANDLER
# ================================================
async def handle_prev_video(client, callback, player_info):
    user_id = callback.from_user.id
    
    # Get previous video from history
    prev_video = await db.get_previous_video(user_id)
    
    if not prev_video:
        return await callback.answer("⚠️ No previous video!", show_alert=True)
    
    video_data = await db.get_video_metadata(prev_video)
    
    # Edit message with previous video
    await edit_player(client, callback, prev_video, video_data, player_info)
    
    # Update stored info
    ACTIVE_PLAYERS[user_id]["current_video"] = prev_video
    
    await callback.answer("⏮️ Previous video loaded!")

# ================================================
# 🔄 EDIT PLAYER (Change Video without Deleting)
# ================================================
async def edit_player(client, callback, video_id, video_data, player_info):
    """Edit existing player message with new video"""
    
    video_unique_id = video_data.get("file_unique_id", "Unknown")
    likes = video_data.get("likes", 0)
    dislikes = video_data.get("dislikes", 0)
    total_votes = likes + dislikes
    like_percentage = int((likes / total_votes * 100)) if total_votes > 0 else 0
    category = player_info.get("category", "All")
    
    caption = (
        f"<b>Video ID:</b> <code>{video_unique_id}</code>\n"
        f"<b>{like_percentage}% users liked this</b>\n"
        f"<b>Category:</b> {category}\n\n"
        f"<blockquote>ᴛʜɪꜱ ᴘʟᴀʏᴇʀ ᴡɪʟʟ ᴇxᴘɪʀᴇ ɪɴ 10 ᴍɪɴᴜᴛᴇꜱ.\n"
        f"ᴜꜱᴇ ɴᴇxᴛ/ᴘʀᴇᴠɪᴏᴜꜱ ᴛᴏ ꜱᴡɪᴛᴄʜ ᴠɪᴅᴇᴏꜱ.</blockquote>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("👍 Like", callback_data=f"player_like_{video_unique_id}"),
            InlineKeyboardButton("👎 Dislike", callback_data=f"player_dislike_{video_unique_id}"),
            InlineKeyboardButton("⬇️ Download", callback_data=f"player_download_{video_unique_id}")
        ],
        [
            InlineKeyboardButton("⏮️ Previous", callback_data="player_prev"),
            InlineKeyboardButton("Next ⏭️", callback_data="player_next")
        ],
        [
            InlineKeyboardButton("🔄 Change Category", callback_data="player_category"),
            InlineKeyboardButton("🔖 Bookmark", callback_data=f"player_bookmark_{video_unique_id}")
        ],
        [
            InlineKeyboardButton("⭐ For D@rk C00ntent", url="https://t.me/your_channel")
        ]
    ]
    
    # Edit media (change video)
    try:
        await callback.message.edit_media(
            media=video_id,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await callback.message.edit_caption(caption)
    except Exception as e:
        print(f"Edit player error: {e}")

# ================================================
# 🔄 REFRESH PLAYER (Update likes without changing video)
# ================================================
async def refresh_player(client, callback, player_info):
    """Refresh player to show updated likes/dislikes"""
    video_id = player_info["current_video"]
    video_data = await db.get_video_metadata(video_id)
    
    video_unique_id = video_data.get("file_unique_id", "Unknown")
    likes = video_data.get("likes", 0)
    dislikes = video_data.get("dislikes", 0)
    total_votes = likes + dislikes
    like_percentage = int((likes / total_votes * 100)) if total_votes > 0 else 0
    category = player_info.get("category", "All")
    
    caption = (
        f"<b>Video ID:</b> <code>{video_unique_id}</code>\n"
        f"<b>{like_percentage}% users liked this</b>\n"
        f"<b>Category:</b> {category}\n\n"
        f"<blockquote>ᴛʜɪꜱ ᴘʟᴀʏᴇʀ ᴡɪʟʟ ᴇxᴘɪʀᴇ ɪɴ 10 ᴍɪɴᴜᴛᴇꜱ.\n"
        f"ᴜꜱᴇ ɴᴇxᴛ/ᴘʀᴇᴠɪᴏᴜꜱ ᴛᴏ ꜱᴡɪᴛᴄʜ ᴠɪᴅᴇᴏꜱ.</blockquote>"
    )
    
    try:
        await callback.message.edit_caption(caption)
    except:
        pass

# ================================================
# ⏰ PLAYER EXPIRY TASK
# ================================================
async def expire_player(client, chat_id, message_id, user_id):
    """Delete player after 10 minutes"""
    await asyncio.sleep(600)  # 10 minutes
    
    try:
        await client.delete_messages(chat_id, message_id)
        if user_id in ACTIVE_PLAYERS:
            del ACTIVE_PLAYERS[user_id]
    except Exception as e:
        print(f"Expire player error: {e}")
