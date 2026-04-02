from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from datetime import datetime, timedelta
from bson import ObjectId

import database as db
import config
import strings

admin_router = Router()

# ==================== HOLATLAR (FSM) ====================
class PostState(StatesGroup):
    post_kutish = State()
    kanal_tanlash = State()
    vaqt_tanlash = State()

class ChannelState(StatesGroup):
    waiting_for_id = State()
    waiting_for_bot = State()

class TimeState(StatesGroup):
    waiting_for_time = State()

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
    if not await db.is_admin(message.from_user.id):
        await message.answer(strings.START_REKLAMA)
        return
    await message.answer(strings.ADMIN_START, reply_markup=main_menu)

@admin_router.message(F.text == "🚀 PRO Versiya")
async def pro_ad(message: Message):
    if not await db.is_admin(message.from_user.id): return
    await message.answer(strings.PRO_INFO)

@admin_router.message(F.text == "📊 Statistika")
async def show_stats(message: Message):
    if not await db.is_admin(message.from_user.id): return
    stats_text = await db.get_general_statistics()
    await message.answer(stats_text)

# ==================== 2. REJA BO'LIMI ====================
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

# ==================== 3. KANALLARNI BOSHQARISH ====================
@admin_router.message(F.text == "📢 Kanallar")
async def channels_list(message: Message):
    if not await db.is_admin(message.from_user.id): return
    kanallar = await db.get_channels()
    text = "📢 **Ulangan kanallar:**\n\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if kanallar:
        for k in kanallar:
            text += f"🔹 ID: `{k['channel_id']}`\n🤖 Bot: {k['bot_username']}\n\n"
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"🗑 {k['channel_id']} ni o'chirish", callback_data=f"delch_{k['channel_id']}")])
    else:
        text += "Hozircha kanallar yo'q."
    kb.inline_keyboard.append([InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_new_ch")])
    await message.answer(text, reply_markup=kb)

@admin_router.callback_query(F.data == "add_new_ch")
async def add_ch_start(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Kanal ID raqamini yuboring (Masalan: -100123456789):")
    await state.set_state(ChannelState.waiting_for_id)

@admin_router.message(ChannelState.waiting_for_id)
async def get_ch_id(message: Message, state: FSMContext):
    if not message.text.startswith("-100"):
        await message.answer("❌ Xato! ID -100 bilan boshlanishi kerak.")
        return
    await state.update_data(ch_id=message.text.strip())
    await message.answer("Ushbu kanal uchun bot username yuboring (@...):")
    await state.set_state(ChannelState.waiting_for_bot)

@admin_router.message(ChannelState.waiting_for_bot)
async def get_ch_bot(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.add_channel(data['ch_id'], data['ch_id'], message.text.strip())
    await message.answer(strings.CH_SAVED, reply_markup=main_menu)
    await state.clear()

@admin_router.callback_query(F.data.startswith("delch_"))
async def del_ch_call(call: CallbackQuery):
    await db.remove_channel(call.data.split("_")[1])
    await call.answer("❌ Kanal o'chirildi")
    await call.message.delete()

# ==================== 4. AVTOVAQT BO'LIMI ====================
@admin_router.message(F.text == "⏰ Avtovaqt")
async def auto_times_menu(message: Message):
    if not await db.is_admin(message.from_user.id): return
    times = await db.get_auto_times()
    text = "⏰ **Sizning avto-vaqtlaringiz:**\n\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for t in times:
        text += f"🕒 {t}\n"
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"🗑 {t} o'chirish", callback_data=f"deltime_{t}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="➕ Vaqt qo'shish", callback_data="add_new_time")])
    await message.answer(text, reply_markup=kb)

@admin_router.callback_query(F.data == "add_new_time")
async def add_time_start(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Vaqtni kiriting (HH:MM):")
    await state.set_state(TimeState.waiting_for_time)

@admin_router.message(TimeState.waiting_for_time)
async def save_new_time(message: Message, state: FSMContext):
    try:
        new_t = message.text.strip()
        datetime.strptime(new_t, "%H:%M")
        await db.db.autotimes.insert_one({"time": new_t})
        await message.answer("✅ Vaqt qo'shildi!", reply_markup=main_menu)
        await state.clear()
    except:
        await message.answer(strings.ERR_TIME_FORMAT)

@admin_router.callback_query(F.data.startswith("deltime_"))
async def del_time_call(call: CallbackQuery):
    await db.db.autotimes.delete_one({"time": call.data.split("_")[1]})
    await call.answer("✅ O'chirildi")
    await call.message.delete()

# ==================== 5. POST YUKLASH TIZIMI ====================
@admin_router.message(F.text == "📥 Post yuklash")
async def post_start(message: Message, state: FSMContext):
    if not await db.is_admin(message.from_user.id): return
    await message.answer("Postni yuboring (Rasm va matn):")
    await state.set_state(PostState.post_kutish)

@admin_router.message(StateFilter(PostState.post_kutish))
async def post_get_content(message: Message, state: FSMContext):
    if message.text == "Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu)
        return
    photo_id = message.photo[-1].file_id if message.photo else None
    await state.update_data(photo_id=photo_id, text=message.caption or message.text or "")
    
    kanallar = await db.get_channels()
    if not kanallar:
        await message.answer("❌ Avval kanal qo'shing!")
        await state.clear()
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=k['channel_name'], callback_data=f"ch_{k['channel_id']}")] for k in kanallar])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🌈 Barcha kanallar", callback_data="ch_all")])
    await message.answer("Qaysi kanalga?", reply_markup=kb)
    await state.set_state(PostState.kanal_tanlash)

@admin_router.callback_query(StateFilter(PostState.kanal_tanlash))
async def post_select_ch(call: CallbackQuery, state: FSMContext):
    if call.data == "ch_all":
        ids = [k['channel_id'] for k in await db.get_channels()]
    else:
        ids = [call.data.split("_")[1]]
    await state.update_data(target_channels=ids)
    await call.message.delete()
    
    times = await db.get_auto_times()
    btns = [[KeyboardButton(text="Hozir (+1 min)"), KeyboardButton(text="Hozir (+5 min)")]]
    row = []
    for t in times:
        row.append(KeyboardButton(text=t))
        if len(row) == 3: btns.append(row); row = []
    if row: btns.append(row)
    btns.append([KeyboardButton(text="Bekor qilish")])
    await call.message.answer("Vaqtni tanlang:", reply_markup=ReplyKeyboardMarkup(keyboard=btns, resize_keyboard=True))
    await state.set_state(PostState.vaqt_tanlash)

@admin_router.message(StateFilter(PostState.vaqt_tanlash))
async def post_save_final(message: Message, state: FSMContext):
    v = message.text.strip()
    if v == "Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu)
        return
    hozir = datetime.now(config.TIMEZONE)
    yakuniy_v = ""
    if v == "Hozir (+1 min)": yakuniy_v = (hozir + timedelta(minutes=1)).strftime("%H:%M")
    elif v == "Hozir (+5 min)": yakuniy_v = (hozir + timedelta(minutes=5)).strftime("%H:%M")
    else:
        try:
            datetime.strptime(v, "%H:%M")
            yakuniy_v = v
        except:
            await message.answer(strings.ERR_TIME_FORMAT)
            return
    
    data = await state.get_data()
    await db.add_post(data['text'], data['photo_id'], yakuniy_v, data['target_channels'])
    await message.answer(f"{strings.POST_SAVED}\nVaqt: {yakuniy_v}", reply_markup=main_menu)
    await state.clear()
