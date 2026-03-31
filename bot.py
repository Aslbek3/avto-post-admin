import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher
from motor.motor_asyncio import AsyncIOMotorClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, MONGO_URL, TIMEZONE, ADMINS
from handlers import router

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

cluster = AsyncIOMotorClient(MONGO_URL)
db = cluster["avto_post_db"]

scheduler = AsyncIOScheduler(timezone=TIMEZONE)

# Bazadagi barcha adminlarni olish funksiyasi
async def get_all_admins():
    admins_db = await db.admins.find().to_list(length=100)
    return ADMINS + [a['user_id'] for a in admins_db]

async def check_and_post():
    try:
        now = datetime.now(TIMEZONE).isoformat()
        cursor = db.posts.find({"status": "pending", "time": {"$lte": now}})
        posts = await cursor.to_list(length=100) 

        active_admins = await get_all_admins()

        for p in posts:
            try:
                # 1. Postni haqiqiy kanalga yuborish
                await bot.copy_message(
                    chat_id=p['target'],
                    from_chat_id=p['from_chat_id'],
                    message_id=p['message_id']
                )
                
                # 2. Statusni 'sent' qilish
                await db.posts.update_one(
                    {"_id": p["_id"]}, 
                    {"$set": {"status": "sent", "sent_at": datetime.now(TIMEZONE).isoformat()}}
                )
                
                # ================= 3. ADMINGA HISOBOT =================
                report_text = f"✅ **Post yuborildi!**\n📢 Kanal: `{p['target']}`\n⏰ Vaqt: `{p['time'][:16]}`"
                for admin in active_admins:
                    try:
                        await bot.send_message(chat_id=admin, text=report_text)
                        # Post nusxasini adminga ham tashlab qo'yamiz
                        await bot.copy_message(chat_id=admin, from_chat_id=p['from_chat_id'], message_id=p['message_id'])
                    except: pass
                # =====================================================

                # 4. Antispam
                await asyncio.sleep(0.05) 
                
            except Exception as e:
                await db.posts.update_one({"_id": p["_id"]}, {"$set": {"status": "failed", "error": str(e)}})
                err_text = f"⚠️ **XATOLIK!**\nKanal: `{p['target']}`\nSabab: `{str(e)}`"
                for admin in active_admins:
                    try: await bot.send_message(chat_id=admin, text=err_text)
                    except: pass 
                
    except Exception as main_e:
        logging.error(f"Taymer xatosi: {main_e}")

async def main():
    dp.include_router(router)
    scheduler.add_job(check_and_post, "interval", minutes=1)
    scheduler.start()
    logging.info("🟢 Bot (To'liq versiya) ishga tushdi...")
    await bot.delete_webhook(drop_pending_updates=True) 
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try: asyncio.run(main())
    except KeyboardInterrupt: pass
