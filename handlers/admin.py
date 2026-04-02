from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from datetime import datetime, timedelta
from bson import ObjectId

import database as db
import config
import strings  # Barcha matnlar shu fayldan olinadi

admin_router = Router()

# ==================== HOLATLAR (FSM) ====================
class PostState(StatesGroup):
    post_kutish = State()
    kanal_tanlash = State()
    vaqt_tanlash = State()

# ==================== ASOSIY MENYU ====================
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📥 Post yuklash"), KeyboardButton(text="📅 Reja")],
        [KeyboardButton(text="⏰ Avtovaqt"), KeyboardButton(text="📢 Kanallar")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="🚀 PRO Versiya")]
    ],
    resize_keyboard=True
)

# ==================== 1. START VA REKLAMA ====================
@admin_router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    # Adminlikni tekshirish (Config + Baza)
    if not await db.is_admin(message.from_user.id):
        await message.answer(strings.START_REKLAMA)
        return
    await message.answer(strings.ADMIN_START, reply_markup=main_menu)

@admin_router.message(F.text == "🚀 PRO Versiya")
async def pro_ad(message: Message):
    if not await db.is_admin(message.from_user.id): return
    await message.answer(strings.PRO_INFO)

# ==================== 2. STATISTIKA ====================
@admin_router.message(F.text == "📊 Statistika")
async def show_stats(message: Message):
    if not await db.is_admin(message.from_user.id): return
    # Umumiy statistikani bazadan olish
    stats_text = await db.get_general_statistics()
    await message.answer(stats_text)

# ==================== 3. REJA (O'CHIRISH BILAN) ====================
@admin_router.message(F.text == "📅 Reja")
async def show_schedule(message: Message):
    if not await db.is_admin(message.from_user.id): return
    posts = await db.get_pending_posts() 
    if not posts:
        await message.answer("Hozircha navbatda postlar yo'q.")
        return
    
    await message.answer("📅 **Yaqin xabarlar rejasi (Top 10):**")
    for p in posts[:10]:
        btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"delpost_{p['_id']}")]
        ])
        info = f"⏰ Vaqt: {p['send_time']}\n📢 Kanallar: {len(p['target_channels'])} ta"
        await message.answer(info, reply_markup=btn)

@admin_router.callback_query(F.data.startswith("delpost_"))
async def delete_post(call: CallbackQuery):
    pid = call.data.split("_")[1]
    await db.db.posts.delete_one({"_id": ObjectId(pid)})
    await call.message.delete()
    await call.answer("✅ Post o'chirildi.")

# ==================== 4. POST YUKLASH TIZIMI (FSM) ====================
@admin_router.message(F.text == "📥 Post yuklash")
async def start_post(message: Message, state: FSMContext):
    if not await db.is_admin(message.from_user.id): return
    await message.answer("Iltimos, postni yuboring (Rasm va matn):")
    await state.set_state(PostState.post_kutish)

@admin_router.message(StateFilter(PostState.post_kutish))
async def get_post(message: Message, state: FSMContext):
    # Bekor qilish tekshiruvi
    if message.text == "Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu)
        return

    # Kontentni ajratish
    photo_id = message.photo[-1].file_id if message.photo else None
    text = message.caption or message.text or ""
    
    await state.update_data(photo_id=photo_id, text=text)
    
    kanallar = await db.get_channels()
    if not kanallar:
        await message.answer("❌ Kanallar mavjud emas! Avval kanal qo'shing.")
        await state.clear()
        return
        
    tugmalar = [[InlineKeyboardButton(text=k['channel_name'], callback_data=f"ch_{k['channel_id']}")] for k in kanallar]
    tugmalar.append([InlineKeyboardButton(text="🌈 Barcha kanallar", callback_data="ch_all")])
    
    await message.answer("Qaysi kanalga yuboramiz?", reply_markup=InlineKeyboardMarkup(inline_keyboard=tugmalar))
    await state.set_state(PostState.kanal_tanlash)

@admin_router.callback_query(StateFilter(PostState.kanal_tanlash))
async def select_channel(call: CallbackQuery, state: FSMContext):
    if call.data == "ch_all":
        kanallar = await db.get_channels()
        target_ids = [k['channel_id'] for k in kanallar]
    else:
        target_ids = [call.data.split("_")[1]]
        
    await state.update_data(target_channels=target_ids)
    await call.message.delete()
    
    # Avtovaqtlarni tugma qilib chiqarish
    vaqtlar = await db.get_auto_times()
    btns = [[KeyboardButton(text="Hozir (+1 min)"), KeyboardButton(text="Hozir (+5 min)")]]
    
    row = []
    for v in vaqtlar:
        row.append(KeyboardButton(text=v))
        if len(row) == 3:
            btns.append(row)
            row = []
    if row: btns.append(row)
    btns.append([KeyboardButton(text="Bekor qilish")])
    
    await call.message.answer("⏰ Vaqtni tanlang yoki yozing (HH:MM):", 
                             reply_markup=ReplyKeyboardMarkup(keyboard=btns, resize_keyboard=True))
    await state.set_state(PostState.vaqt_tanlash)

@admin_router.message(StateFilter(PostState.vaqt_tanlash))
async def save_final_post(message: Message, state: FSMContext):
    v = message.text.strip()
    if v == "Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu)
        return

    hozir = datetime.now(config.TIMEZONE)
    yakuniy_v = ""
    
    if v == "Hozir (+1 min)":
        yakuniy_v = (hozir + timedelta(minutes=1)).strftime("%H:%M")
    elif v == "Hozir (+5 min)":
        yakuniy_v = (hozir + timedelta(minutes=5)).strftime("%H:%M")
    else:
        try:
            datetime.strptime(v, "%H:%M")
            yakuniy_v = v
        except:
            await message.answer(strings.ERR_TIME_FORMAT)
            return
            
    data = await state.get_data()
    # Bazaga saqlash
    await db.add_post(data['text'], data['photo_id'], yakuniy_v, data['target_channels'])
    
    await message.answer(f"{strings.POST_SAVED}\n⏰ Vaqt: {yakuniy_v}", reply_markup=main_menu)
    await state.clear()
