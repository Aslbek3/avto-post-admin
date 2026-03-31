import logging
from datetime import datetime, timedelta
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

from config import MONGO_URL, ADMINS, TIMEZONE

router = Router()
cluster = AsyncIOMotorClient(MONGO_URL)
db = cluster["avto_post_db"]

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📥 Post yuklash")],
        [KeyboardButton(text="📅 Reja"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="⚙️ Sozlamalar")]
    ],
    resize_keyboard=True
)

class PostState(StatesGroup):
    waiting_for_post = State()
    waiting_for_channel = State()
    waiting_for_auto_hour = State() 
    waiting_for_auto_date = State() 

class SettingsState(StatesGroup):
    waiting_for_ch_name = State()
    waiting_for_ch_id = State()
    waiting_for_admin_id = State()
    waiting_for_time_add = State()

MENU_BUTTONS = ["📥 Post yuklash", "📅 Reja", "⚙️ Sozlamalar", "📊 Statistika", "Bekor qilish", "/start"]

# Admin tekshirish funksiyasi (Baza va Config orqali)
async def is_admin(user_id):
    if user_id in ADMINS: return True
    doc = await db.admins.find_one({"user_id": user_id})
    return bool(doc)

@router.message(F.text == "/start")
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    if not await is_admin(message.from_user.id):
        await message.answer("👋 Assalomu alaykum!\nSizda bu botdan foydalanish huquqi yo'q.")
        return
    await message.answer("👋 Assalomu alaykum, Admin!\nBarcha funksiyalar ochiq. Nima qilamiz?", reply_markup=main_menu)

# ==================== STATISTIKA ====================
@router.message(F.text == "📊 Statistika")
async def show_stats(message: types.Message):
    if not await is_admin(message.from_user.id): return
    channels = await db.channels.find().to_list(length=100)
    pending_total = await db.posts.count_documents({"status": "pending"})
    sent_total = await db.posts.count_documents({"status": "sent"})
    
    text = f"📊 **Umumiy Statistika:**\n\n📢 Kanallar: **{len(channels)}**\n⏳ Kutmoqda: **{pending_total}**\n✅ Yuborildi: **{sent_total}**\n\n📈 **Kanallar kesimida:**\n\n"
    for ch in channels:
        p = await db.posts.count_documents({"status": "pending", "target": ch['channel_id']})
        s = await db.posts.count_documents({"status": "sent", "target": ch['channel_id']})
        text += f"🔹 {ch['channel_name']}\n   ⏳ Kutmoqda: {p} | ✅ Yuborildi: {s}\n\n"
    await message.answer(text)

# ==================== SOZLAMALAR (Admin, Kanal, Vaqt) ====================
@router.message(F.text == "⚙️ Sozlamalar")
async def settings_menu(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanallar", callback_data="set_channels"), InlineKeyboardButton(text="👥 Adminlar", callback_data="set_admins")],
        [InlineKeyboardButton(text="⏰ Avto-vaqtlar", callback_data="set_times")]
    ])
    await message.answer("⚙️ **Sozlamalar bo'limi:**", reply_markup=kb)

# --- Adminlar ---
@router.callback_query(F.data == "set_admins")
async def set_admins(call: types.CallbackQuery):
    admins_db = await db.admins.find().to_list(length=100)
    text = "👥 **Qo'shimcha Adminlar:**\n"
    for a in admins_db: text += f"🔸 ID: `{a['user_id']}`\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="add_admin"), InlineKeyboardButton(text="➖ O'chirish", callback_data="del_admin_list")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data == "add_admin")
async def add_admin(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Yangi adminning Telegram ID raqamini yuboring:")
    await state.set_state(SettingsState.waiting_for_admin_id)

@router.message(SettingsState.waiting_for_admin_id)
async def save_admin(msg: types.Message, state: FSMContext):
    if msg.text in MENU_BUTTONS: await state.clear(); return
    try:
        await db.admins.insert_one({"user_id": int(msg.text.strip())})
        await msg.answer("✅ Admin qo'shildi!")
        await state.clear()
    except:
        await msg.answer("❌ Xato ID!")

@router.callback_query(F.data == "del_admin_list")
async def del_admin_list(call: types.CallbackQuery):
    admins_db = await db.admins.find().to_list(length=100)
    kb = [[InlineKeyboardButton(text=f"❌ {a['user_id']}", callback_data=f"deladm_{a['user_id']}")] for a in admins_db]
    await call.message.edit_text("O'chirmoqchi bo'lgan adminni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("deladm_"))
async def del_adm(call: types.CallbackQuery):
    aid = int(call.data.split("_")[1])
    await db.admins.delete_one({"user_id": aid})
    await call.answer("O'chirildi!", show_alert=True)
    await set_admins(call)

# --- Kanallar ---
@router.callback_query(F.data == "set_channels")
async def set_channels(call: types.CallbackQuery):
    channels = await db.channels.find().to_list(length=100)
    text = "📢 **Kanallar:**\n"
    for c in channels: text += f"🔹 {c['channel_name']} ({c['channel_id']})\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_ch"), InlineKeyboardButton(text="➖ O'chirish", callback_data="del_ch_list")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data == "add_ch")
async def add_ch_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Kanal nomini yozing:")
    await state.set_state(SettingsState.waiting_for_ch_name)

@router.message(SettingsState.waiting_for_ch_name)
async def add_ch_name(msg: types.Message, state: FSMContext):
    if msg.text in MENU_BUTTONS: await state.clear(); return
    await state.update_data(name=msg.text)
    await msg.answer("Kanal ID (-100...) yoki Username (@kanal) yuboring:")
    await state.set_state(SettingsState.waiting_for_ch_id)

@router.message(SettingsState.waiting_for_ch_id)
async def add_ch_id(msg: types.Message, state: FSMContext):
    if msg.text in MENU_BUTTONS: await state.clear(); return
    data = await state.get_data()
    await db.channels.insert_one({"channel_name": data['name'], "channel_id": msg.text.strip()})
    await msg.answer(f"✅ Kanal '{data['name']}' qo'shildi!")
    await state.clear()

@router.callback_query(F.data == "del_ch_list")
async def del_ch_list(call: types.CallbackQuery):
    channels = await db.channels.find().to_list(length=100)
    kb = [[InlineKeyboardButton(text=f"❌ {c['channel_name']}", callback_data=f"delch_{c['_id']}")] for c in channels]
    await call.message.edit_text("O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("delch_"))
async def del_ch(call: types.CallbackQuery):
    cid = call.data.split("_")[1]
    await db.channels.delete_one({"_id": ObjectId(cid)})
    await call.answer("O'chirildi!", show_alert=True)
    await set_channels(call)

# --- Avto Vaqtlar ---
@router.callback_query(F.data == "set_times")
async def set_times(call: types.CallbackQuery):
    times = await db.autotimes.find().to_list(length=50)
    text = "⏰ **Avto-vaqtlar:**\n"
    for t in times: text += f"🔹 {t['time']}\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Vaqt qo'shish", callback_data="add_time"), InlineKeyboardButton(text="➖ O'chirish", callback_data="del_time_list")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data == "add_time")
async def add_time_st(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Yangi soatni kiriting (`15:00`):")
    await state.set_state(SettingsState.waiting_for_time_add)

@router.message(SettingsState.waiting_for_time_add)
async def save_time(msg: types.Message, state: FSMContext):
    if msg.text in MENU_BUTTONS: await state.clear(); return
    await db.autotimes.insert_one({"time": msg.text.strip()})
    await msg.answer("✅ Vaqt qo'shildi!")
    await state.clear()

@router.callback_query(F.data == "del_time_list")
async def del_time_list(call: types.CallbackQuery):
    times = await db.autotimes.find().to_list(length=50)
    kb = [[InlineKeyboardButton(text=f"❌ {t['time']}", callback_data=f"deltm_{t['_id']}")] for t in times]
    await call.message.edit_text("O'chirmoqchi bo'lgan vaqtni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("deltm_"))
async def del_tm(call: types.CallbackQuery):
    tid = call.data.split("_")[1]
    await db.autotimes.delete_one({"_id": ObjectId(tid)})
    await call.answer("O'chirildi!", show_alert=True)
    await set_times(call)

# ==================== REJA KUTISH ZALI ====================
@router.message(F.text == "📅 Reja")
async def show_schedule(message: types.Message):
    if not await is_admin(message.from_user.id): return
    posts = await db.posts.find({"status": "pending"}).sort("time", 1).to_list(length=20)
    if not posts:
        await message.answer("Hozircha navbatda postlar yo'q.")
        return
    text = "📅 **Yaqin xabarlar rejasini:**\n\n"
    for i, p in enumerate(posts, 1):
        dt = datetime.fromisoformat(p['time'])
        text += f"{i}. ⏰ {dt.strftime('%m-%d %H:%M')} | Kanal: `{p['target']}`\n"
        btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"delpost_{p['_id']}")]])
        await message.answer(text if i==1 else f"Post #{i} ({dt.strftime('%H:%M')})", reply_markup=btn)

@router.callback_query(F.data.startswith("delpost_"))
async def delete_post(call: types.CallbackQuery):
    pid = call.data.split("_")[1]
    await db.posts.delete_one({"_id": ObjectId(pid)})
    await call.message.delete()
    await call.answer("Post o'chirildi.")

# ==================== POST YUKLASH TIZIMI ====================
@router.message(F.text == "📥 Post yuklash")
async def post_start(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    await state.clear()
    await message.answer("Postni yuboring (rasm/video/matn):", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Bekor qilish")]], resize_keyboard=True))
    await state.set_state(PostState.waiting_for_post)

@router.message(PostState.waiting_for_post)
async def post_get(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        await message.answer("Bekor qilindi.", reply_markup=main_menu); await state.clear(); return
        
    await state.update_data(msg_id=message.message_id, chat_id=message.chat.id)
    channels = await db.channels.find().to_list(length=100)
    
    if not channels:
        await message.answer("❌ Kanallar yo'q! Sozlamalardan kanal qo'shing.", reply_markup=main_menu)
        await state.clear()
        return
        
    builder = [[InlineKeyboardButton(text=c['channel_name'], callback_data=f"ch_{c['channel_id']}")] for c in channels]
    await message.answer("Qaysi kanalga joylaymiz?", reply_markup=InlineKeyboardMarkup(inline_keyboard=builder))
    await state.set_state(PostState.waiting_for_channel)

@router.callback_query(PostState.waiting_for_channel, F.data.startswith("ch_"))
async def ch_select(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(target=callback.data.split("ch_")[1])
    await callback.message.delete()
    
    # Bazadan vaqtlarni olib tugma yasaymiz
    times = await db.autotimes.find().to_list(length=50)
    buttons = []
    row = []
    for t in times:
        row.append(KeyboardButton(text=t['time']))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    buttons.append([KeyboardButton(text="Bekor qilish")])
    
    await callback.message.answer("⏰ **Qaysi soatga rejalashtiramiz?**", reply_markup=ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True))
    await state.set_state(PostState.waiting_for_auto_hour)

@router.message(PostState.waiting_for_auto_hour)
async def get_auto_hour(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        await message.answer("Bekor qilindi.", reply_markup=main_menu); await state.clear(); return
        
    await state.update_data(auto_hour=message.text.strip())
    
    dates_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Bugun"), KeyboardButton(text="Ertaga")],
            [KeyboardButton(text="Indinga"), KeyboardButton(text="Bekor qilish")]
        ], resize_keyboard=True
    )
    await message.answer(
        f"Soat: **{message.text}**\n\n"
        "📅 **Sanani tanlang** yoki qo'lda yozing (Masalan: `04-15` yoki `05-01`):", 
        reply_markup=dates_kb
    )
    await state.set_state(PostState.waiting_for_auto_date)

@router.message(PostState.waiting_for_auto_date)
async def get_auto_date(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        await message.answer("Bekor qilindi.", reply_markup=main_menu); await state.clear(); return
        
    data = await state.get_data()
    hour_str = data.get('auto_hour', '12:00')
    now = datetime.now(TIMEZONE)
    
    try:
        hour, minute = map(int, hour_str.split(':'))
        t_str = message.text.strip()
        
        if t_str == "Bugun":
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target < now: target += timedelta(days=1)
        elif t_str == "Ertaga":
            target = (now + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        elif t_str == "Indinga":
            target = (now + timedelta(days=2)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            # Qo'lda yozilgan sana: 04-15 kabi
            parsed_date = datetime.strptime(t_str.replace(".", "-"), "%m-%d")
            target = now.replace(month=parsed_date.month, day=parsed_date.day, hour=hour, minute=minute, second=0, microsecond=0)
            if target < now - timedelta(days=1): # O'tib ketgan oy bo'lsa kelasi yilga
                target = target.replace(year=now.year + 1)

        final_dt = TIMEZONE.localize(target.replace(tzinfo=None)) if target.tzinfo is None else target
        await db.posts.insert_one({
            "message_id": data['msg_id'], "from_chat_id": data['chat_id'],
            "target": data['target'], "time": final_dt.isoformat(), "status": "pending"
        })
        await message.answer(f"✅ **Post saqlandi!**\nKanal: {data['target']}\nVaqti: {final_dt.strftime('%d-%m-%Y %H:%M')}", reply_markup=main_menu)
        await state.clear()
    except Exception as e:
        await message.answer("❌ Sana xato! Tayyor tugmalarni bosing yoki `04-15` ko'rinishida yozing.")
