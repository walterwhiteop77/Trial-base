from database.users_db import db
from plugins.video_player import send_video_player  # ✅ Import player function

async def send_requested_file(client, message, user_id, search_id):
    """
    Send file from start link (e.g., https://t.me/bot?start=avx-file_id)
    NOW SENDS PLAYER INSTEAD OF SINGLE VIDEO
    """
    
    try:
        # ✅ PRESERVED: Find video in database
        file_data = await db.videos.find_one({"file_unique_id": search_id})
        
        if not file_data:
            return await message.reply("❌ File not found.")

        video_id = file_data['file_id']
        
        # 🆕 CHANGED: Send player instead of single video
        await send_video_player(
            client=client,
            message=message,
            video_id=video_id,
            auto_delete=True  # ✅ PRESERVED: 10 min auto-delete
        )

    except Exception as e:
        print(f"❌ Error sending file: {e}")
        await message.reply("❌ Error: File might be deleted or inaccessible.")
