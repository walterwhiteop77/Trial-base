# ============================================================
# FILE 1: plugins/commands.py (MAIN START COMMAND - MODIFIED)
# ============================================================

import os
import logging
import random
import asyncio
from Script import script
from pyrogram import Client, filters, enums
from pyrogram.errors import ChatAdminRequired, FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from database.ia_filterdb import Media, get_file_details, get_search_results
from database.users_chats_db import db
from info import *
from utils import get_size, is_subscribed, temp
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

# ==================== START COMMAND - ENHANCED WITH V2 FEATURES ====================

@Client.on_message(filters.command("start") & filters.private)
async def start(client, message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    # Add user to database if not exists
    if not await db.is_user_exist(user_id):
        await db.add_user(user_id, first_name)
        await client.send_message(
            LOG_CHANNEL,
            f"#NewUser\n\n**ID:** `{user_id}`\n**Name:** {first_name}\n**Username:** @{message.from_user.username or 'None'}"
        )
    
    # Check if user is banned
    if not await db.get_ban_status(user_id):
        await message.reply_text("⛔ You are banned from using this bot!")
        return
    
    # Handle referral links
    if len(message.text.split()) > 1:
        data = message.text.split(None, 1)[1]
        if data.startswith("ref_"):
            await handle_referral(client, message, data)
            return
    
    # Check user's access status
    user_data = await db.get_user(user_id)
    has_access = await db.check_access_status(user_id)
    
    if not has_access:
        # User doesn't have access - show token activation screen
        await show_token_activation_screen(client, message)
    else:
        # User has access - show main menu
        await show_main_menu(client, message)


async def show_token_activation_screen(client, message):
    """Display token activation screen from screenshot"""
    user_name = message.from_user.mention
    
    text = f"""
🎬 <b>HEY {user_name}!</b>

🚫 <b>YOUR TOKEN IS NOT ACTIVE OR EXPIRED.
PLEASE ACTIVATE IT.</b>

<b>WHAT IS TOKEN</b>
THIS IS AN ADS TOKEN. AFTER YOU WATCH 1 AD, YOUR TOKEN WILL BE ACTIVATED AND YOU CAN USE THE BOT FOR 12 HOURS FOR FREE

<b>WHY TOKEN</b>
TOKENS HELP US KEEP THE BOT FREE FOR EVERYONE. WATCHING A SHORT AD SUPPORTS THE BOT.

<b>DON'T WORRY! IT'S COMPLETELY FREE.✅</b>

<b>OR INVITE A FRIEND TO GET 1 HOUR OF BOT ACCESS!</b>
"""
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📺 Watch Ad", callback_data="watch_ad"),
            InlineKeyboardButton("💳 Purchase Premium", callback_data="purchase_premium")
        ],
        [
            InlineKeyboardButton("👥 Refer a Friend", callback_data="refer_friend")
        ]
    ])
    
    await message.reply_text(
        text,
        reply_markup=buttons,
        parse_mode=enums.ParseMode.HTML
    )


async def show_main_menu(client, message):
    """Display main menu after access is granted"""
    text = """
🎉 <b>Access Granted!</b>

You now have full bot access for the next 12 hours, including unlimited link accesses.

<b>What would you like to do?</b>
"""
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎬 Get Video", callback_data="get_video"),
            InlineKeyboardButton("📊 My Status", callback_data="my_status")
        ]
    ])
    
    await message.reply_text(
        text,
        reply_markup=buttons,
        parse_mode=enums.ParseMode.HTML
    )


async def handle_referral(client, message, data):
    """Handle referral link clicks"""
    try:
        referrer_id = int(data.split("_")[1])
        user_id = message.from_user.id
        
        # Don't allow self-referral
        if referrer_id == user_id:
            await show_token_activation_screen(client, message)
            return
        
        # Check if user is new or hasn't used bot before
        user_data = await db.get_user(user_id)
        if user_data and user_data.get('total_videos_watched', 0) > 0:
            # User already used the bot
            await show_main_menu(client, message)
            return
        
        # Grant access to new user (30 minutes)
        await db.grant_access(user_id, hours=0.5)
        
        # Grant bonus to referrer (1 hour)
        await db.grant_access(referrer_id, hours=1)
        await db.increment_referral(referrer_id)
        
        # Notify both users
        await message.reply_text(
            "🎉 <b>Welcome!</b>\n\n"
            "You've been referred by a friend!\n"
            "You got <b>30 minutes</b> of free access!",
            parse_mode=enums.ParseMode.HTML
        )
        
        try:
            await client.send_message(
                referrer_id,
                "🎉 <b>New Referral!</b>\n\n"
                "Someone joined using your link!\n"
                "You got <b>1 hour</b> of free access!",
                parse_mode=enums.ParseMode.HTML
            )
        except:
            pass
        
        await asyncio.sleep(2)
        await show_main_menu(client, message)
        
    except Exception as e:
        logger.error(f"Referral error: {e}")
        await show_token_activation_screen(client, message)


# ==================== CALLBACK QUERY HANDLERS ====================

@Client.on_callback_query(filters.regex("^watch_ad$"))
async def watch_ad_callback(client, callback_query):
    """Handle Watch Ad button click"""
    text = """
📺 <b>Watch Ad to Access Bot</b>

Click below to watch an ad and get 24 hours of access:

<b>iOS Users:</b> Copy the ad link and open it in the Chrome browser

Click "Watch Ad" button below to proceed.
"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📺 Watch Ad", url=f"https://t.me/{AD_CHANNEL}")],
        [InlineKeyboardButton("❓ How to Open Link", callback_data="how_to_open")],
        [InlineKeyboardButton("« Back", callback_data="back_to_start")]
    ])
    
    await callback_query.message.edit_text(
        text,
        reply_markup=buttons,
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_callback_query(filters.regex("^how_to_open$"))
async def how_to_open_callback(client, callback_query):
    """Show instructions for opening ad links"""
    text = """
❓ <b>How to Open Ad Links</b>

<b>For iOS Users:</b>
1. Long press on the ad link
2. Select "Copy Link"
3. Open Chrome browser
4. Paste the link in address bar
5. Complete the ad verification

<b>For Android Users:</b>
1. Simply click on the ad link
2. Complete the verification

After completing the ad, your access will be automatically activated!
"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("« Back", callback_data="watch_ad")]
    ])
    
    await callback_query.message.edit_text(
        text,
        reply_markup=buttons,
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_callback_query(filters.regex("^refer_friend$"))
async def refer_friend_callback(client, callback_query):
    """Show referral information"""
    user_id = callback_query.from_user.id
    bot_username = (await client.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    user_data = await db.get_user(user_id)
    ref_count = user_data.get('referral_count', 0) if user_data else 0
    
    text = f"""
👥 <b>Invite Friends & Earn!</b>

<b>Your Referral Link:</b>
<code>{ref_link}</code>

<b>How it works:</b>
1. Share your link with friends
2. When they join using your link, you get <b>1 hour</b> free access
3. They also get <b>30 minutes</b> bonus access!

<b>Your Stats:</b>
👥 Total Referrals: {ref_count}
⏰ Total Earned: {ref_count} hours

<b>Rewards:</b>
• 5 referrals = 1 day free access
• 10 referrals = 3 days free access
• 20 referrals = 1 week free access
• 50 referrals = 1 month premium!
"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={ref_link}")],
        [InlineKeyboardButton("« Back", callback_data="back_to_start")]
    ])
    
    await callback_query.message.edit_text(
        text,
        reply_markup=buttons,
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_callback_query(filters.regex("^my_status$"))
async def my_status_callback(client, callback_query):
    """Show user status from screenshot"""
    user_id = callback_query.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await callback_query.answer("User data not found!", show_alert=True)
        return
    
    # Calculate status
    has_premium = user_data.get('has_premium', False)
    access_expires = user_data.get('access_expires', datetime.now())
    
    if has_premium:
        status = "Active"
        expires_str = user_data.get('premium_expires', datetime.now()).strftime('%d/%m/%Y, %I:%M:%S %p')
    else:
        status = "Active" if access_expires > datetime.now() else "Expired"
        expires_str = access_expires.strftime('%d/%m/%Y, %I:%M:%S %p')
    
    downloads = "Premium only" if not has_premium else "Unlimited"
    link_access = "2" if not has_premium else "Unlimited"
    
    text = f"""
⭐ <b>My Status</b>

🎬 <b>Watched Videos (Total):</b> {user_data.get('total_videos_watched', 0)}
🎬 <b>Watched Videos (Last 24 Hours):</b> {user_data.get('videos_today', 0)}
📂 <b>Current Category:</b> {user_data.get('current_category', 'all')}
🔑 <b>Access Status:</b> {status}
⏰ <b>Access Expires:</b> {expires_str}
⬇️ <b>Downloads:</b> {downloads}
🔗 <b>Link Access:</b> {link_access} per day (resets daily at 12:00 AM IST)
👥 <b>Referrals:</b> {user_data.get('referral_count', 0)}
"""
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Purchase Premium", callback_data="purchase_premium")],
        [InlineKeyboardButton("« Back", callback_data="back_to_main")]
    ])
    
    await callback_query.message.edit_text(
        text,
        reply_markup=buttons,
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_callback_query(filters.regex("^get_video$"))
async def get_video_callback(client, callback_query):
    """Handle Get Video button - sends video with player controls"""
    user_id = callback_query.from_user.id
    
    # Check access
    has_access = await db.check_access_status(user_id)
    if not has_access:
        await callback_query.answer(
            "⚠️ Your access has expired! Please renew.",
            show_alert=True
        )
        return
    
    # Check daily limit
    user_data = await db.get_user(user_id)
    has_premium = user_data.get('has_premium', False)
    
    daily_limit = 999 if has_premium else 5
    today_count = user_data.get('videos_today', 0)
    
    if today_count >= daily_limit and not has_premium:
        await callback_query.answer(
            "⚠️ Daily limit reached! Upgrade to Premium for unlimited access.",
            show_alert=True
        )
        return
    
    # Get random video from category
    category = user_data.get('current_category', 'all')
    
    # Query videos from database
    if category == 'all':
        files = await Media.find().to_list(length=100)
    else:
        files = await Media.find({'file_type': category}).to_list(length=100)
    
    if not files:
        await callback_query.answer("No videos available in this category!", show_alert=True)
        return
    
    # Pick random file
    file = random.choice(files)
    
    # Send video with player interface
    await send_video_player(client, callback_query.message, file, user_id)
    
    # Track video watch
    await db.increment_video_watch(user_id)


async def send_video_player(client, message, file, user_id):
    """Send video with interactive player controls from screenshot"""
    
    # Calculate like percentage
    likes = await db.get_video_likes(file.file_id)
    dislikes = await db.get_video_dislikes(file.file_id)
    total = likes + dislikes
    like_percent = int((likes / total) * 100) if total > 0 else 50
    
    caption = f"""
<b>Video ID:</b> {file.file_id[:20]}...
<b>{like_percent}% users liked this</b>
<b>Category:</b> {file.file_type or 'All'}
"""
    
    # Build keyboard matching screenshot
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👍 Like", callback_data=f"like_{file.file_id}"),
            InlineKeyboardButton("👎 Dislike", callback_data=f"dislike_{file.file_id}"),
            InlineKeyboardButton("⬇️ Download", callback_data=f"download_{file.file_id}")
        ],
        [
            InlineKeyboardButton("⏮️ Previous", callback_data="previous_video"),
            InlineKeyboardButton("Next ⏭️", callback_data="next_video")
        ],
        [
            InlineKeyboardButton("🔄 Change Category", callback_data="change_category"),
            InlineKeyboardButton("🔖 Bookmark", callback_data=f"bookmark_{file.file_id}")
        ],
        [
            InlineKeyboardButton("⭐ For D@rk C00ntent", url="https://t.me/your_dark_channel")
        ]
    ])
    
    try:
        # Send video
        sent_msg = await client.send_cached_media(
            chat_id=message.chat.id,
            file_id=file.file_id,
            caption=caption,
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.HTML
        )
        
        # Auto-delete after 10 minutes
        asyncio.create_task(auto_delete_message(sent_msg, 600))
        
    except Exception as e:
        logger.error(f"Error sending video: {e}")
        await message.reply_text("❌ Error sending video. Please try again.")


async def auto_delete_message(message, delay):
    """Auto delete message after delay"""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except:
        pass


@Client.on_callback_query(filters.regex("^like_"))
async def like_video_callback(client, callback_query):
    """Handle video like"""
    video_id = callback_query.data.split("_", 1)[1]
    user_id = callback_query.from_user.id
    
    await db.like_video(user_id, video_id)
    await callback_query.answer("👍 Liked!", show_alert=False)


@Client.on_callback_query(filters.regex("^dislike_"))
async def dislike_video_callback(client, callback_query):
    """Handle video dislike"""
    video_id = callback_query.data.split("_", 1)[1]
    user_id = callback_query.from_user.id
    
    await db.dislike_video(user_id, video_id)
    await callback_query.answer("👎 Disliked!", show_alert=False)


@Client.on_callback_query(filters.regex("^download_"))
async def download_video_callback(client, callback_query):
    """Handle video download"""
    user_id = callback_query.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data.get('has_premium'):
        await callback_query.answer(
            "⚠️ Download feature is for Premium users only!",
            show_alert=True
        )
        return
    
    await callback_query.answer(
        "⬇️ Download started! Check your saved messages.",
        show_alert=False
    )


@Client.on_callback_query(filters.regex("^(previous_video|next_video)$"))
async def navigate_video_callback(client, callback_query):
    """Handle Previous/Next video navigation"""
    await get_video_callback(client, callback_query)


@Client.on_callback_query(filters.regex("^change_category$"))
async def change_category_callback(client, callback_query):
    """Show category selection menu"""
    text = "🔄 <b>Select Category</b>\n\nChoose a category to browse videos:"
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📁 All", callback_data="cat_all")],
        [InlineKeyboardButton("📁 Brazzers", callback_data="cat_brazzers")],
        [InlineKeyboardButton("📁 General", callback_data="cat_general")],
        [InlineKeyboardButton("🔀 Mix (Random)", callback_data="cat_mix")],
        [InlineKeyboardButton("« Back", callback_data="get_video")]
    ])
    
    await callback_query.message.edit_text(
        text,
        reply_markup=buttons,
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_callback_query(filters.regex("^cat_"))
async def select_category_callback(client, callback_query):
    """Handle category selection"""
    category = callback_query.data.split("_", 1)[1]
    user_id = callback_query.from_user.id
    
    # Update user's category
    await db.update_user_category(user_id, category)
    
    await callback_query.answer(f"✅ Category changed to: {category}", show_alert=False)
    
    # Get video from new category
    await get_video_callback(client, callback_query)


@Client.on_callback_query(filters.regex("^bookmark_"))
async def bookmark_video_callback(client, callback_query):
    """Handle video bookmark"""
    video_id = callback_query.data.split("_", 1)[1]
    user_id = callback_query.from_user.id
    
    await db.add_bookmark(user_id, video_id)
    await callback_query.answer("🔖 Bookmarked!", show_alert=False)


@Client.on_callback_query(filters.regex("^back_to_start$"))
async def back_to_start_callback(client, callback_query):
    """Go back to start screen"""
    await callback_query.message.delete()
    await show_token_activation_screen(client, callback_query.message)


@Client.on_callback_query(filters.regex("^back_to_main$"))
async def back_to_main_callback(client, callback_query):
    """Go back to main menu"""
    await callback_query.message.delete()
    await show_main_menu(client, callback_query.message)


# ==================== USER COMMANDS ====================

@Client.on_message(filters.command("mystatus") & filters.private)
async def mystatus_command(client, message):
    """My Status command"""
    fake_query = type('obj', (object,), {
        'from_user': message.from_user,
        'message': message
    })()
    await my_status_callback(client, fake_query)


@Client.on_message(filters.command("refer") & filters.private)
async def refer_command(client, message):
    """Referral command"""
    fake_query = type('obj', (object,), {
        'from_user': message.from_user,
        'message': message
    })()
    await refer_friend_callback(client, fake_query)


# Keep all your existing commands (help, about, stats, etc.)
