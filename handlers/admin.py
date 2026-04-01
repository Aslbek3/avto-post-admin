from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import database as db
import config

admin_router = Router()

# ==========================================
# HOLATLAR (Bosqichma-bosqich ishlash uchun)
# ==========================================
class PostState(StatesGroup):
    post_kutish = State()
    kanal_tanlash = State()
    vaqt_tanlash = State()

# Asosiy menyu tugmalari
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Post yuklash"), KeyboardButton(text="📋 Reja")],
        [KeyboardButton(text="⏰ Avto-vaqt"), KeyboardButton(text="📢 Kanallar")]
    ],
    resize_keyboard=True
)

# ==========================================
# 1-SHAKL: ODDIY XABAR VA MENYU USHLAGICHLAR
# ==========================================

@admin_router.message(CommandStart())
async def start_cmd(message: Message):
    # Faqat adminlar ishlata oladi
    if message.from_user.id == config.MAIN_ADMIN or await db.is_admin(message.from_user.id):
        await message.answer("Bosh menyuga xush kelibsiz!", reply_markup=main_menu)

@admin_router.message(F.text == "📋 Reja")
async def show_plan(message: Message):
    stats = await db.get_plan_stats()
    if not stats:
        await message.answer("Hozircha navbatda turgan postlar yo'q.")
        return
    
    javob = "📋 **Navbatdagi postlar rejas:**\n\n"
    for s in stats:
        javob += f"Kanal ID ({s['_id'][0]}): {s['count']} ta post\n"
    await message.answer(javob)

# ==========================================
# 2-SHAKL: BOSQICHLI ISH JARAYONI (FSM)
# ==========================================

# 1-QADAM: Post yuklash tugmasi bosilganda
@admin_router.message(F.text == "➕ Post yuklash")
async def start_post(message: Message, state: FSMContext):
    await message.answer("Iltimos, tayyor postni yuboring (Rasm va tagida matn):")
    await state.set_state(PostState.post_kutish)

# 2-QADAM: Postni qabul qilish va Kanal tanlashga o'tish
@admin_router.message(StateFilter(PostState.post_kutish))
async def get_post_content(message: Message, state: FSMContext):
    # Rasm va matnni ajratib olish
    if message.photo:
        photo_id = message.photo[-1].file_id
        text = message.caption or ""
    else:
        photo_id = None
        text = message.text or ""
        
    # Xotiraga saqlab turamiz
    await state.update_data(photo_id=photo_id, text=text)
    
    # Kanallar ro'yxatini Inline tugma qilib chiqaramiz
    kanallar = await db.get_channels()
    tugmalar = []
    for k in kanallar:
        tugmalar.append([InlineKeyboardButton(text=k['channel_name'], callback_data=f"ch_{k['channel_id']}")])
    tugmalar.append([InlineKeyboardButton(text="Barcha kanallar", callback_data="ch_all")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=tugmalar)
    await message.answer("Qaysi kanalga yuboramiz?", reply_markup=kb)
    await state.set_state(PostState.kanal_tanlash)

# 3-QADAM: Kanal tanlangach, Vaqtni so'rash
@admin_router.callback_query(StateFilter(PostState.kanal_tanlash))
async def select_channel(call: CallbackQuery, state: FSMContext):
    tanlov = call.data
    
    if tanlov == "ch_all":
        kanallar = await db.get_channels()
        target_ids = [k['channel_id'] for k in kanallar]
    else:
        # Faqat bitta kanal ID sini olamiz
        kanal_id = int(tanlov.split("_")[1])
        target_ids = [kanal_id]
        
    await state.update_data(target_channels=target_ids)
    
    # Vaqtlarni bazadan olib tugma qilib chiqaramiz
    vaqtlar = await db.get_auto_times()
    vaqt_tugmalari = [[InlineKeyboardButton(text=v, callback_data=f"time_{v}")] for v in vaqtlar]
    kb = InlineKeyboardMarkup(inline_keyboard=vaqt_tugmalari)
    
    await call.message.edit_text("Post chiqish vaqtini belgilang:", reply_markup=kb)
    await state.set_state(PostState.vaqt_tanlash)

# 4-QADAM: Vaqt tanlangach, Bazaga saqlash va jarayonni tugatish
@admin_router.callback_query(StateFilter(PostState.vaqt_tanlash))
async def select_time(call: CallbackQuery, state: FSMContext):
    vaqt = call.data.split("_")[1] # Masalan "15:00" ni ajratib oladi
    
    # Xotirada yig'ilgan barcha ma'lumotlarni olamiz
    data = await state.get_data()
    
    # Bazaga yozamiz
    await db.add_post(
        text=data['text'],
        photo_id=data['photo_id'],
        send_time=vaqt,
        target_channels=data['target_channels']
    )
    
    await call.message.edit_text(f"✅ Post muvaffaqiyatli saqlandi!\n⏰ Chiqish vaqti: {vaqt}")
    
    # Holatni tozalash (jarayon tugadi)
    await state.clear()
