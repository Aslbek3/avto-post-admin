import asyncio
import logging
import traceback
from datetime import datetime
from aiogram import Bot, Dispatcher
from aiogram.types import ErrorEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
import database as db
import strings
from handlers.admin import admin_router

# Loglarni sozlash (Xatolarni ko'rish uchun)
logging.basicConfig(level=logging.INFO)

async def send_scheduled_posts(bot: Bot):
    """Vaqti kelgan postlarni yuborish mantiqi"""
    hozirgi_vaqt = datetime.now(config.TIMEZONE).strftime("%H:%M")
    pending_posts = await db.get_pending_posts()
    all_channels = await db.get_channels()
    
    for post in pending_posts:
        # Faqat vaqti kelgan postni tekshiramiz
        if post['send_time'] == hozirgi_vaqt:
            target_ids = post['target_channels']
            
            for ch_id in target_ids:
                kanal_info = next((c for c in all_channels if c['channel_id'] == ch_id), None)
                if kanal_info:
                    bot_username = kanal_info['bot_username']
                    # [BOT_NOMI] belgisini kanal boti bilan almashtirish
                    final_text = post['text'].replace("[BOT_NOMI]", bot_username)
                    
                    try:
                        if post.get('photo_id'):
                            await bot.send_photo(chat_id=ch_id, photo=post['photo_id'], caption=final_text)
                        else:
                            await bot.send_message(chat_id=ch_id, text=final_text)
                        
                        # SPAMDAN HIMOYA: Har bir kanal orasida 0.1 soniya kutish
                        await asyncio.sleep(0.1)
                    except Exception as e:
                        logging.error(f"Kanalga yuborishda xato ({ch_id}): {e}")

            # MUHIM: Post yuborilgandan keyingina bazadan o'chiriladi
            await db.mark_post_sent(post['_id'])

async def setup_error_handler(dp: Dispatcher, bot: Bot):
    """Xatolik yuz berganda foydalanuvchiga xabar berish"""
    @dp.error()
    async def error_handler(event: ErrorEvent):
        logging.error(f"XATOLIK: {traceback.format_exc()}")
        chat_id = None
        if event.update.message:
            chat_id = event.update.message.chat.id
        elif event.update.callback_query:
            chat_id = event.update.callback_query.message.chat.id
            
        if chat_id:
            try:
                err_msg = f"{strings.USER_ERROR_MSG}\n\n⚠️ *Texnik xato:* `{str(event.exception)[:100]}`"
                await bot.send_message(chat_id, err_msg, parse_mode="Markdown")
            except: 
                pass

async def main():
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    
    # Routerni ulash (admin.py dagi kodlar ishlashi uchun)
    dp.include_router(admin_router)
    
    # Baza bilan aloqani tekshirish
    await db.check_db_connection()
    
    # Xato ushlagichni sozlash
    await setup_error_handler(dp, bot)

    # Har daqiqada bazani tekshiradigan taymer
    scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)
    scheduler.add_job(send_scheduled_posts, "interval", minutes=1, args=[bot])
    scheduler.start()

    print("🚀 Bot ishga tushdi...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi.")
