import asyncio
import logging
from datetime import datetime
import pytz

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from database import (
    check_db_connection, get_pending_posts, get_channels, mark_post_sent
)
from handlers.admin import admin_router

# Loglarni sozlash (xatolarni ko'rish uchun)
logging.basicConfig(level=logging.INFO)

# Vaqt mintaqasini sozlash (O'zbekiston)
TASHKENT_TZ = pytz.timezone('Asia/Tashkent')

async def send_scheduled_posts(bot: Bot):
    """Har daqiqa ishlaydigan funksiya: Vaqti kelgan postlarni yuboradi"""
    hozirgi_vaqt = datetime.now(TASHKENT_TZ).strftime("%H:%M")
    
    # Bazadan hali chiqmagan postlarni olish
    pending_posts = await get_pending_posts()
    all_channels = await get_channels()
    
    for post in pending_posts:
        # Agar post vaqti hozirgi vaqtga mos kelsa
        if post['send_time'] == hozirgi_vaqt:
            target_ids = post['target_channels']
            
            for ch_id in target_ids:
                # Kanal ma'lumotlarini qidirib topish
                kanal_info = next((c for c in all_channels if c['channel_id'] == ch_id), None)
                
                if kanal_info:
                    bot_username = kanal_info['bot_username']
                    # Matndagi [BOT_NOMI] ni o'zgartirish
                    final_text = post['text'].replace("[BOT_NOMI]", bot_username)
                    
                    try:
                        # Postni rasm yoki matn holida yuborish
                        if post.get('photo_id'):
                            await bot.send_photo(
                                chat_id=ch_id, 
                                photo=post['photo_id'], 
                                caption=final_text
                            )
                        else:
                            await bot.send_message(chat_id=ch_id, text=final_text)
                        
                        # Antispam: kanallar orasida qisqa tanaffus
                        await asyncio.sleep(0.1)
                        
                    except Exception as e:
                        logging.error(f"Xatolik {ch_id} kanalida: {e}")

            # Post hamma kanalga yuborilgach, uni bazada yakunlash
            await mark_post_sent(post['_id'])

async def main():
    # Bot va Dispatcher
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()

    # Routerlarni ulash
    dp.include_router(admin_router)

    # Bazani tekshirish
    await check_db_connection()

    # Taymerni (Scheduler) sozlash
    scheduler = AsyncIOScheduler(timezone=TASHKENT_TZ)
    # Har 1 daqiqada postlarni tekshirish funksiyasini chaqiradi
    scheduler.add_job(send_scheduled_posts, "interval", minutes=1, args=[bot])
    scheduler.start()

    print(f"🚀 Bot ishga tushdi... (Vaqt: {datetime.now(TASHKENT_TZ).strftime('%H:%M:%S')})")

    # Eskirgan xabarlarni tozalash va pollingni boshlash
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi.")
