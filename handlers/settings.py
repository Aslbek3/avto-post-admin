from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import database as db

settings_router = Router()

# Kanallar qo'shish uchun bosqichlar (2-shakl: FSM)
class ChannelState(StatesGroup):
    kanal_id_kutish = State()
    bot_nomi_kutish = State()

# ==========================================
# 📢 KANALLAR BO'LIMI
# ==========================================

@settings_router.message(F.text == "📢 Kanallar")
async def channels_menu(message: Message, state: FSMContext):
    # Bazadagi bor kanallarni ko'rsatish
    kanallar = await db.get_channels()
    matn = "📢 **Ulangan kanallar ro'yxati:**\n\n"
    
    if kanallar:
        for k in kanallar:
            matn += f"▪️ Kanal: {k['channel_id']} | Boti: {k['bot_username']}\n"
    else:
        matn += "Hozircha hech qanday kanal ulanmagan.\n"
        
    matn += "\nYangi kanal qo'shish uchun kanalning ID raqamini yoki username'ni yuboring (masalan: @Kino_Olami yoki -100123456):"
    
    await message.answer(matn)
    await state.set_state(ChannelState.kanal_id_kutish)

@settings_router.message(ChannelState.kanal_id_kutish)
async def get_channel_id(message: Message, state: FSMContext):
    # Kanal manzilini xotiraga olish
    await state.update_data(channel_id=message.text)
    
    await message.answer("Endi ushbu kanalga yuboriladigan postlar tagiga qaysi bot manzili chiqishini xohlaysiz?\nShuni yuboring (masalan: @Opalar_robot):")
    await state.set_state(ChannelState.bot_nomi_kutish)

@settings_router.message(ChannelState.bot_nomi_kutish)
async def get_bot_username(message: Message, state: FSMContext):
    # Xotiradan oldingi ma'lumotni olish
    data = await state.get_data()
    kanal_id = data['channel_id']
    bot_username = message.text
    
    # Bazaga yozish (database.py dagi funksiyani chaqiramiz)
    # Eslatma: ID string bo'lgani uchun ishlayveradi, qulaylik uchun ismini ham ID qilib saqlaymiz
    await db.add_channel(
        channel_id=kanal_id, 
        channel_name=kanal_id, 
        bot_username=bot_username
    )
    
    await message.answer(f"✅ Kanal muvaffaqiyatli qo'shildi!\n\nKanal: {kanal_id}\nBot ssilkasi: {bot_username}")
    await state.clear()

# ==========================================
# ⏰ AVTO-VAQT BO'LIMI
# ==========================================

@settings_router.message(F.text == "⏰ Avto-vaqt")
async def auto_time_menu(message: Message):
    # Bazadan tayyor vaqtlarni olish
    vaqtlar = await db.get_auto_times()
    
    matn = "⏰ **Joriy avto-vaqtlar ro'yxati:**\n\n"
    for v in vaqtlar:
        matn += f"🕒 {v}\n"
        
    matn += "\n(Bu vaqtlar post yuklash menyusida sizga tayyor tugma bo'lib ko'rinadi. O'zgartirish funksiyasini ham shu yerga qo'shish mumkin)."
    
    await message.answer(matn)
