import time
from datetime import datetime
import motor.motor_asyncio
from bson import ObjectId
import config

BOT_START_TIME = time.time()

client = motor.motor_asyncio.AsyncIOMotorClient(config.MONGO_URL)
db = client[config.DB_NAME]

async def check_db_connection():
    try:
        await client.admin.command('ping')
        print("✅ Baza ulangan!")
    except Exception as e:
        print(f"❌ Baza xatosi: {e}")

# ================= ADMINLAR =================
async def is_admin(user_id: int) -> bool:
    if user_id in config.ADMINS: return True
    admin = await db.admins.find_one({"user_id": user_id})
    return bool(admin)

# ================= UMUMIY KANALLAR =================
async def get_channels():
    settings = await db.global_settings.find_one({"_id": "bot_settings"})
    if settings and "channels" in settings: return settings["channels"]
    return []

async def add_channel(channel_id: str, channel_name: str, bot_username: str):
    new_ch = {"channel_id": channel_id, "channel_name": channel_name, "bot_username": bot_username}
    await db.global_settings.update_one(
        {"_id": "bot_settings"},
        {"$push": {"channels": new_ch}},
        upsert=True
    )

async def remove_channel(channel_id: str):
    await db.global_settings.update_one(
        {"_id": "bot_settings"},
        {"$pull": {"channels": {"channel_id": channel_id}}}
    )

# ================= UMUMIY AVTO-VAQT =================
async def get_auto_times():
    settings = await db.global_settings.find_one({"_id": "bot_settings"})
    if settings and "auto_times" in settings: return settings["auto_times"]
    return []

async def add_auto_time(new_time: str):
    await db.global_settings.update_one(
        {"_id": "bot_settings"},
        {"$addToSet": {"auto_times": new_time}},
        upsert=True
    )

async def delete_auto_time(time_val: str):
    await db.global_settings.update_one(
        {"_id": "bot_settings"},
        {"$pull": {"auto_times": time_val}}
    )

# ================= UMUMIY POSTLAR =================
async def add_post(text: str, photo_id: str, send_time: str, target_channels: list, queue_msg_id: int):
    post = {
        "text": text,
        "photo_id": photo_id,
        "send_time": send_time,
        "target_channels": target_channels,
        "queue_msg_id": queue_msg_id,
        "status": "pending"
    }
    await db.posts.insert_one(post)

async def get_all_pending_posts():
    return await db.posts.find({"status": "pending"}).to_list(length=None)

async def mark_post_sent(post_id: ObjectId):
    await db.posts.update_one({"_id": post_id}, {"$set": {"status": "sent"}})

# ================= STATISTIKA =================
async def get_bot_statistics() -> str:
    total_admins = await db.admins.count_documents({}) + len(config.ADMINS)
    total_pending = await db.posts.count_documents({"status": "pending"})
    total_failed = await db.posts.count_documents({"status": "failed"})
    
    uptime_seconds = int(time.time() - BOT_START_TIME)
    uptime_str = f"{uptime_seconds // 3600}s {(uptime_seconds % 3600) // 60}d"
    
    start_db_ping = time.time()
    await client.admin.command("ping")
    end_db_ping = time.time()
    db_ping_ms = round((end_db_ping - start_db_ping) * 1000)
    
    text = (
        "📈 **Bot Holati:**\n"
        f"├ 👮‍♂️ Adminlar: {total_admins}\n"
        f"├ ⏳ Navbatda: {total_pending} | ⚠️ Xatolar: {total_failed}\n"
        f"└ 🖥 Uptime: {uptime_str} | ⚡️ Ping: {db_ping_ms}ms"
    )
    return text
