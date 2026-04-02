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

# Loglarni sozlash
logging.basicConfig(level=logging.INFO)

async def send_scheduled_posts(bot: Bot):
    """Vaqti kelgan postlarni har bir kanal uchun maxsus bot nomi bilan yuborish"""
    hozirgi_vaqt = datetime.now(config.TIMEZONE).strftime("%H:%M")
    
    # Barcha kutilayotgan postlarni olish
    all_pending = await db.get_all_pending_posts()
    
    for post in all_pending:
        if post['send_time'] == hozirgi_vaqt:
            uid = post['owner_id']
            # Faqat shu post egasining kanallarini olamiz
            user_channels = await db.get_channels(uid)
            target_ids = post['target_channels']
            
            for ch_id in target_ids:
                # Kanal ma'lumotini qidirish
                kanal_info = next((c for c in user_channels if c['channel_id'] == ch_id), None)
                
                if kanal_info:
                    bot_link = kanal_info['bot_username']
                    # Katta va kichik harflardagi [bot nomi] ni dinamik almashtirish
                    msg_text = post['text'].replace("[bot nomi]", bot_link).replace("[BOT_NOMI]", bot_link)
                    
                    try:
                        if post.get('photo_id'):
                            await bot.send_photo(chat_id=ch_id, photo=post['photo_id'], caption=msg_text)
                        else:
                            await bot.send_message(chat_id=ch_id, text=msg_text)
                        
                        await asyncio.sleep(0.1) # Spamdan himoya
                    except Exception as e:
                        logging.error(f"Yuborishda xato ({ch_id}): {e}")

            # Yuborib bo'lingach, bazadan o'chiramiz
            await db.mark_post_sent(post['_id'])

async def setup_error_handler(dp: Dispatcher, bot: Bot):
    """Xatolarni ushlab, foydalanuvchiga yuborish"""
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
    
    # Routerni ulash
    dp.include_router(admin_router)
    
    await db.check_db_connection()
    await setup_error_handler(dp, bot)

    # Har 1 daqiqada ishlaydigan taymer
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
