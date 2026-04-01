from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import config

# Bazaga ulanish
cluster = AsyncIOMotorClient(config.MONGO_URL)
db = cluster.autopost_bot

async def check_db_connection():
    """Baza ishlayotganini tekshirish"""
    try:
        await cluster.admin.command('ping')
        print("✅ MongoDB bazasiga muvaffaqiyatli ulandi!")
    except Exception as e:
        print(f"❌ Bazaga ulanishda xatolik: {e}")

# ==========================================
# 👨‍💻 ADMINLAR BILAN ISHLASH
# ==========================================

async def is_admin(user_id: int) -> bool:
    """Foydalanuvchi admin ekanligini tekshirish"""
    # 1. Config faylidagi super adminlarni tekshiramiz
    if user_id in config.ADMINS:
        return True
    
    # 2. Bazadan adminlar ro'yxatini tekshiramiz
    admin = await db.admins.find_one({"user_id": user_id})
    return bool(admin)

# (Ixtiyoriy) Agar keyinchalik bazaga admin qo'shmoqchi bo'lsangiz:
async def add_admin(user_id: int):
    await db.admins.update_one({"user_id": user_id}, {"$set": {"user_id": user_id}}, upsert=True)

async def remove_admin(user_id: int):
    await db.admins.delete_one({"user_id": user_id})

# ==========================================
# 📢 KANALLAR BILAN ISHLASH
# ==========================================

async def add_channel(channel_id: str, channel_name: str, bot_username: str):
    """Kanalni va unga tegishli botni saqlash"""
    await db.channels.update_one(
        {"channel_id": channel_id},
        {"$set": {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "bot_username": bot_username
        }},
        upsert=True
    )

async def get_channels():
    """Barcha kanallarni ro'yxatini olish"""
    return await db.channels.find({}).to_list(length=100)

async def remove_channel(channel_id: str):
    """Kanalni o'chirish"""
    await db.channels.delete_one({"channel_id": channel_id})

# ==========================================
# ⏰ AVTO-VAQT SOZLAMALARI
# ==========================================

async def get_auto_times():
    """Tayyor vaqtlarni olish"""
    times = await db.autotimes.find().to_list(length=50)
    if not times:
        # Agar bazada vaqt bo'lmasa, standart shularni beradi
        return ["10:00", "12:00", "15:00", "18:00", "20:00", "22:00", "00:00"]
    return [t['time'] for t in times]

# ==========================================
# 📋 POSTLAR VA REJA BILAN ISHLASH
# ==========================================

async def add_post(text: str, photo_id: str, send_time: str, target_channels: list):
    """Yangi postni saqlash"""
    post_data = {
        "text": text,
        "photo_id": photo_id,
        "send_time": send_time,
        "target_channels": target_channels,
        "status": "pending"
    }
    await db.posts.insert_one(post_data)

async def get_pending_posts():
    """Chiqishini kutib turgan barcha postlarni olish"""
    return await db.posts.find({"status": "pending"}).sort("send_time", 1).to_list(length=1000)

async def mark_post_sent(post_id):
    """Post kanalga yuborilgach, bazadan o'chirish"""
    await db.posts.delete_one({"_id": post_id})
