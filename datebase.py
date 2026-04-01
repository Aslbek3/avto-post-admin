from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import config

# MongoDB'ga ulanish
cluster = AsyncIOMotorClient(config.MONGO_URL)
db = cluster.autopost_bot

# Baza ichidagi papkalar (kolleksiyalar)
admins_col = db.admins
channels_col = db.channels
posts_col = db.posts
settings_col = db.settings

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

async def add_admin(user_id: int):
    """Yangi admin qo'shish"""
    await admins_col.update_one(
        {"user_id": user_id}, 
        {"$set": {"user_id": user_id}}, 
        upsert=True
    )

async def remove_admin(user_id: int):
    """Adminni o'chirish"""
    await admins_col.delete_one({"user_id": user_id})

async def is_admin(user_id: int) -> bool:
    """Foydalanuvchi admin ekanligini tekshirish"""
    if user_id == config.MAIN_ADMIN:
        return True
    admin = await admins_col.find_one({"user_id": user_id})
    return bool(admin)

# ==========================================
# 📢 KANALLAR BILAN ISHLASH
# ==========================================

async def add_channel(channel_id: int, channel_name: str, bot_username: str):
    """Kanalni va unga tegishli botni bazaga saqlash"""
    await channels_col.update_one(
        {"channel_id": channel_id},
        {"$set": {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "bot_username": bot_username # Aynan shu [BOT_NOMI] ga aylanadi
        }},
        upsert=True
    )

async def get_channels():
    """Barcha kanallarni ro'yxatini olish"""
    return await channels_col.find({}).to_list(length=100)

async def remove_channel(channel_id: int):
    """Kanalni bazadan o'chirish"""
    await channels_col.delete_one({"channel_id": channel_id})

# ==========================================
# ⏰ AVTO-VAQT SOZLAMALARI
# ==========================================

async def get_auto_times():
    """Tayyor vaqtlarni olish. Agar yo'q bo'lsa, standart vaqtlarni beradi"""
    setting = await settings_col.find_one({"type": "auto_times"})
    if setting and "times" in setting:
        return setting["times"]
    # Standart 7 ta vaqt
    return ["10:00", "12:00", "15:00", "18:00", "20:00", "22:00", "00:00"]

async def save_auto_times(times_list: list):
    """Yangi vaqtlarni bazaga saqlash"""
    await settings_col.update_one(
        {"type": "auto_times"},
        {"$set": {"times": times_list}},
        upsert=True
    )

# ==========================================
# 📋 POSTLAR VA REJA BILAN ISHLASH
# ==========================================

async def add_post(text: str, photo_id: str, send_time: str, target_channels: list):
    """Yangi postni bazaga 'pending' (kutilmoqda) holatida saqlash"""
    post_data = {
        "text": text,
        "photo_id": photo_id,
        "send_time": send_time, # Masalan: "15:00"
        "target_channels": target_channels, # Qaysi kanallarga ketishi (ID lar ro'yxati)
        "status": "pending",
        "created_at": datetime.now()
    }
    await posts_col.insert_one(post_data)

async def get_pending_posts():
    """Chiqishini kutib turgan barcha postlarni olish"""
    return await posts_col.find({"status": "pending"}).to_list(length=1000)

async def mark_post_sent(post_id):
    """Post kanalga yuborilgach, bazadan o'chirish yoki 'sent' qilib belgilash"""
    # Xotira to'lmasligi uchun post chiqqach uni o'chirib yuboramiz
    await posts_col.delete_one({"_id": post_id})

async def get_plan_stats():
    """Reja menyusi uchun qaysi kanalda nechta post kutib turganini sanash"""
    pipeline = [
        {"$match": {"status": "pending"}},
        {"$unwind": "$target_channels"},
        {"$group": {"_id": "$target_channels", "count": {"$sum": 1}}}
    ]
    stats = await posts_col.aggregate(pipeline).to_list(length=100)
    return stats

# ==========================================
# 📊 UMUMIY STATISTIKA
# ==========================================

async def get_general_statistics():
    """Adminlar menyusidagi statistika tugmasi uchun"""
    admin_count = await admins_col.count_documents({})
    channel_count = await channels_col.count_documents({})
    pending_posts = await posts_col.count_documents({"status": "pending"})
    
    return (f"📊 Tizim statistikasi:\n\n"
            f"👨‍💻 Adminlar: {admin_count + 1} ta\n"
            f"📢 Kanallar: {channel_count} ta\n"
            f"⏳ Navbatdagi postlar: {pending_posts} ta")
