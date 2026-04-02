# settings.py
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import database as db
import strings # Matnlarni ulaymiz

settings_router = Router()

class ChannelState(StatesGroup):
    kanal_id_kutish = State()
    bot_nomi_kutish = State()

class TimeState(StatesGroup):
    vaqt_kutish = State()

# ==================== KANALLAR ====================
@settings_router.message(F.text == "📢 Kanallar")
async def channels_menu(message: Message, state: FSMContext):
    kanallar = await db.get_channels()
    matn = strings.CHANNELS_LIST
    kb = InlineKeyboardMarkup(inline_keyboard=[])

    if kanallar:
        for k in kanallar:
            matn += f"▪️ {k['channel_id']} | 🤖 {k['bot_username']}\n"
            # Har bir kanal yoniga o'chirish tugmasi
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"🗑 {k['channel_id']} ni o'chirish", callback_data=f"del_ch_{k['channel_id']}")])
    
    kb.inline_keyboard.append([InlineKeyboardButton(text="➕ Yangi kanal qo'shish", callback_data="add_channel")])
    await message.answer(matn, reply_markup=kb)

# Kanal o'chirish callback
@settings_router.callback_query(F.data.startswith("del_ch_"))
async def delete_channel(call: CallbackQuery):
    ch_id = call.data.replace("del_ch_", "")
    await db.remove_channel(ch_id)
    await call.answer("❌ Kanal o'chirildi")
    await call.message.delete()

# ==================== AVTO-VAQT ====================
@settings_router.message(F.text == "⏰ Avtovaqt")
async def auto_time_menu(message: Message):
    vaqtlar = await db.get_auto_times()
    matn = strings.TIMES_LIST
    kb = InlineKeyboardMarkup(inline_keyboard=[])

    for v in vaqtlar:
        matn += f"🕒 {v}\n"
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"🗑 {v} ni o'chirish", callback_data=f"del_tm_{v}")])

    kb.inline_keyboard.append([InlineKeyboardButton(text="➕ Yangi vaqt qo'shish", callback_data="add_time")])
    await message.answer(matn, reply_markup=kb)

# Vaqt o'chirish callback
@settings_router.callback_query(F.data.startswith("del_tm_"))
async def delete_time(call: CallbackQuery):
    v_val = call.data.replace("del_tm_", "")
    # Bazadan o'chirish kodi (database.py da bo'lishi kerak)
    await db.db.autotimes.delete_one({"time": v_val}) 
    await call.answer(f"✅ {v_val} o'chirildi")
    await call.message.delete()
