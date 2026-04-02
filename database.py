from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import config

# Bazaga ulanish
cluster = AsyncIOMotorClient(config.MONGO_URL)
db = cluster.autopost_bot

async def check_db_connection():
    try:
        await cluster.admin.command('ping')
        print("✅ MongoDB ulandi!")
    except Exception as e:
        print(f"❌ Baza xatosi: {e}")

# ==================== ADMINLAR ====================
async def is_admin(user_id: int) -> bool:
    if user_id in config.ADMINS:
        return True
    admin = await db.admins.find_one({"user_id": user_id})
    return bool(admin)

# ==================== KANALLAR ====================
async def get_channels():
    return await db.channels.find({}).to_list(length=100)

async def add_channel(channel_id: str, channel_name: str, bot_username: str):
    await db.channels.update_one(
        {"channel_id": channel_id},
        {"$set": {"channel_name": channel_name, "channel_id": channel_id, "bot_username": bot_username}},
        upsert=True
    )

async def remove_channel(channel_id: str):
    await db.channels.delete_one({"channel_id": channel_id})

# ==================== POSTLAR ====================
async def add_post(text: str, photo_id: str, send_time: str, target_channels: list):
    await db.posts.insert_one({
        "text": text,
        "photo_id": photo_id,
        "send_time": send_time,
        "target_channels": target_channels,
        "status": "pending"
    })

async def get_pending_posts():
    return await db.posts.find({"status": "pending"}).sort("send_time", 1).to_list(length=1000)

async def mark_post_sent(post_id):
    await db.posts.delete_one({"_id": post_id})

# ==================== AVTO-VAQT ====================
async def get_auto_times():
    times = await db.autotimes.find().to_list(length=50)
    if not times:
        return ["10:00", "15:00", "20:00"] # Bo'sh bo'lsa standart vaqtlar
    return [t['time'] for t in times]

# ==================== STATISTIKA ====================
async def get_general_statistics():
    channels_count = await db.channels.count_documents({})
    pending_posts = await db.posts.count_documents({"status": "pending"})
    
    text = (
        "📊 **Bot Statistikasi:**\n\n"
        f"📢 Ulangan kanallar: {channels_count} ta\n"
        f"⏳ Navbatdagi postlar: {pending_posts} ta\n"
    )
    return text
