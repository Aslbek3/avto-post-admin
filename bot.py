import asyncio
import logging
import traceback
from datetime import datetime
from aiogram import Bot, Dispatcher
from aiogram.types import ErrorEvent
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError # Yangi qatorlar
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
import database as db
import strings
from handlers.admin import admin_router
from handlers.settings import settings_router

logging.basicConfig(level=logging.INFO)

async def send_scheduled_posts(bot: Bot):
    hozirgi_vaqt = datetime.now(config.TIMEZONE).strftime("%d.%m %H:%M")
    all_pending = await db.get_all_pending_posts()
    umumiy_kanallar = await db.get_channels()
    
    for post in all_pending:
        if post['send_time'] == hozirgi_vaqt:
            target_ids = post['target_channels']
            muvaffaqiyatli = False 
            
            for ch_id in target_ids:
                kanal_info = next((c for c in umumiy_kanallar if c['channel_id'] == ch_id), None)
                
                if kanal_info:
                    bot_link = kanal_info['bot_username']
                    msg_text = post['text'].replace("[bot nomi]", bot_link).replace("[BOT_NOMI]", bot_link)
                    
                    # Spamga tushmaslik uchun urinish
                    try:
                        if post.get('photo_id'):
                            await bot.send_photo(chat_id=ch_id, photo=post['photo_id'], caption=msg_text)
                        else:
                            await bot.send_message(chat_id=ch_id, text=msg_text)
                        
                        muvaffaqiyatli = True 
                        await asyncio.sleep(1) # Yuborish tezligini 1 soniyaga uzaytirdik (XAVFSIZ TEZLIK)
                        
                    except TelegramRetryAfter as e:
                        # Telegram botni vaqtinchalik cheklasa, aytilgan vaqtcha kutadi
                        logging.warning(f"⚠️ SPAM LIMITI! {e.retry_after} soniya kutamiz...")
                        await asyncio.sleep(e.retry_after)
                        
                        # Kutib bo'lgach, yana bir bor yuborib ko'radi
                        try:
                            if post.get('photo_id'):
                                await bot.send_photo(chat_id=ch_id, photo=post['photo_id'], caption=msg_text)
                            else:
                                await bot.send_message(chat_id=ch_id, text=msg_text)
                            muvaffaqiyatli = True
                        except Exception:
                            pass
                            
                    except TelegramForbiddenError:
                        logging.error(f"❌ Bot kanaldan chiqarib yuborilgan: {ch_id}")
                    except Exception as e:
                        logging.error(f"Yuborishda xato ({ch_id}): {e}")

            if post.get('queue_msg_id'):
                try:
                    await bot.delete_message(chat_id=config.QUEUE_CHANNEL_ID, message_id=post['queue_msg_id'])
                except Exception as e:
                    pass

            if muvaffaqiyatli:
                await db.mark_post_sent(post['_id'])
            else:
                await db.db.posts.update_one({"_id": post['_id']}, {"$set": {"status": "failed"}})

async def setup_error_handler(dp: Dispatcher, bot: Bot):
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
    
    dp.include_router(admin_router)
    dp.include_router(settings_router) 
    
    await db.check_db_connection()
    await setup_error_handler(dp, bot)

    scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)
    scheduler.add_job(send_scheduled_posts, "interval", minutes=1, args=[bot])
    scheduler.start()

    print("🚀 Bot ishga tushdi (Anti-Spam o'rnatilgan)...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi.")
