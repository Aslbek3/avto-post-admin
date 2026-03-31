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

# Asosiy menyu
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📥 Post yuklash")],
        [KeyboardButton(text="📅 Reja"), KeyboardButton(text="⚙️ Kanallar")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="🚀 PRO Versiya")]
    ],
    resize_keyboard=True
)

# Vaqt tanlash uchun maxsus tayyor tugmalar (Avto vaqt)
time_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Bugun 09:00"), KeyboardButton(text="Bugun 13:00")],
        [KeyboardButton(text="Bugun 18:00"), KeyboardButton(text="Bugun 21:00")],
        [KeyboardButton(text="Ertaga 09:00"), KeyboardButton(text="Ertaga 18:00")],
        [KeyboardButton(text="Bekor qilish")]
    ],
    resize_keyboard=True
)

# Holatlar
class PostState(StatesGroup):
    waiting_for_post = State()
    waiting_for_channel = State()
    waiting_for_time = State()
    waiting_for_auto_hour = State() 
    waiting_for_auto_date = State() 

class ChannelState(StatesGroup):
    waiting_for_name = State()
    waiting_for_id = State()

MENU_BUTTONS = ["📥 Post yuklash", "📅 Reja", "⚙️ Kanallar", "📊 Statistika", "🚀 PRO Versiya", "Bekor qilish", "/start"]

# ==================== START VA REKLAMA ====================
@router.message(F.text == "/start")
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    
    if message.from_user.id not in ADMINS:
        reklama_matni = (
            "👋 Assalomu alaykum!\n\n"
            "🤖 Bu bot Telegram kanallarga xabarlarni avtomatik joylash uchun mo'ljallangan.\n\n"
            "💎 **Shaxsiy Avto-Post botga ega bo'lishni xohlaysizmi?**\n"
            "Kanallaringizni avtomatlashtiring, vaqtni tejang va ishingizni osonlashtiring!\n\n"
            "Batafsil ma'lumot va bot xarid qilish uchun adminga yozing: @SizningUsername"
        )
        await message.answer(reklama_matni)
        return

    await message.answer("👋 Assalomu alaykum, Admin!\nSiz botning **Basic (Test)** versiyasidasiz.", reply_markup=main_menu)

# ==================== PRO REKLAMASI ====================
@router.message(F.text == "🚀 PRO Versiya")
async def pro_ad(message: types.Message):
    if message.from_user.id not in ADMINS: return
    text = (
        "🚀 **PRO Versiya Afzalliklari:**\n\n"
        "✅ Birdaniga yuzlab postlarni oson rejalashtirish;\n"
        "✅ Postlarga chiroyli ssilka tugmalari qo'shish;\n"
        "✅ Rasmlarga avtomatik Watermark (Suv belgisi) yozish;\n"
        "✅ Kanallar va postlar sonida umuman cheklov yo'q;\n"
        "✅ Interval taymer (har X minutda avtomatik post tashlash).\n\n"
        "Tarifni yangilash uchun adminga yozing: @SizningUsername"
    )
    await message.answer(text)

# ==================== STATISTIKA ====================
@router.message(F.text == "📊 Statistika")
async def show_stats(message: types.Message):
    if message.from_user.id not in ADMINS: return
    
    channels = await db.channels.find().to_list(length=100)
    pending_total = await db.posts.count_documents({"status": "pending"})
    sent_total = await db.posts.count_documents({"status": "sent"})
    
    text = (
        "📊 **Umumiy Statistika:**\n\n"
        f"📢 Jami kanallar: **{len(channels)} ta**\n"
        f"⏳ Jami kutayotgan postlar: **{pending_total} ta**\n"
        f"✅ Jami yuborilgan postlar: **{sent_total} ta**\n\n"
        "〰️〰️〰️〰️〰️〰️〰️〰️\n"
        "📈 **Kanallar bo'yicha holat:**\n\n"
    )
    
    if not channels:
        text += "Hozircha kanallar ulanmagan."
    else:
        for ch in channels:
            ch_pending = await db.posts.count_documents({"status": "pending", "target": ch['channel_id']})
            ch_sent = await db.posts.count_documents({"status": "sent", "target": ch['channel_id']})
            text += f"🔹 **{ch['channel_name']}**\n   ⏳ Kutmoqda: {ch_pending} ta | ✅ Yuborildi: {ch_sent} ta\n\n"
            
    await message.answer(text)

# ==================== KANALLAR ====================
@router.message(F.text == "⚙️ Kanallar")
async def channels_menu(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS: return
    await state.clear() 
    
    channels = await db.channels.find().to_list(length=100)
    text = "Sizning kanallaringiz:\n\n"
    if not channels: text += "Hozircha yo'q."
    for ch in channels: text += f"🔹 {ch['channel_name']} ({ch['channel_id']})\n"
    
    btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_channel")]])
    await message.answer(text, reply_markup=btn)

@router.callback_query(F.data == "add_channel")
async def add_ch(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Kanal nomini yozing (Masalan: Asosiy kanal):")
    await state.set_state(ChannelState.waiting_for_name)
    await callback.answer()

@router.message(ChannelState.waiting_for_name)
async def ch_name(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        await state.clear()
        return
        
    await state.update_data(name=message.text)
    await message.answer("Endi Kanal ID'sini (masalan: -100123456789) yoki Usernameni (@kanal_nomi) yozing:")
    await state.set_state(ChannelState.waiting_for_id)

@router.message(ChannelState.waiting_for_id)
async def ch_id(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        await state.clear()
        return
        
    if not (message.text.startswith("-100") or message.text.startswith("@")):
        await message.answer("❌ Xato! Kanal ID doim '-100' yoki username '@' bilan boshlanishi kerak. Qaytadan yozing:")
        return 
        
    data = await state.get_data()
    await db.channels.insert_one({"channel_name": data['name'], "channel_id": message.text})
    await message.answer(f"✅ Kanal '{data['name']}' muvaffaqiyatli saqlandi!")
    await state.clear()

# ==================== REJA (KUTISH ZALI) ====================
@router.message(F.text == "📅 Reja")
async def show_schedule(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS: return
    await state.clear()
    
    posts = await db.posts.find({"status": "pending"}).sort("time", 1).to_list(length=20)
    
    if not posts:
        await message.answer("Hozircha navbatda postlar yo'q.")
        return

    text = "📅 **Yaqin xabarlar rejasini:**\n\n"
    for i, p in enumerate(posts, 1):
        dt = datetime.fromisoformat(p['time'])
        time_str = dt.strftime("%m-%d %H:%M")
        text += f"{i}. ⏰ {time_str} | Kanal: `{p['target']}`\n"
        
        btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del_{p['_id']}")]
        ])
        await message.answer(text if i==1 else f"Post #{i} ({time_str})", reply_markup=btn)

@router.callback_query(F.data.startswith("del_"))
async def delete_post(callback: types.CallbackQuery):
    post_id = callback.data.split("_")[1]
    await db.posts.delete_one({"_id": ObjectId(post_id)})
    await callback.message.delete()
    await callback.answer("Post o'chirildi.")

# ==================== POST YUKLASH VA AVTO VAQT ====================
@router.message(F.text == "📥 Post yuklash")
async def post_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS: return
    await state.clear()
    await message.answer("Postni yuboring (rasm/video/matn):", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Bekor qilish")]], resize_keyboard=True))
    await state.set_state(PostState.waiting_for_post)

@router.message(PostState.waiting_for_post)
async def post_get(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        await message.answer("Bekor qilindi.", reply_markup=main_menu)
        await state.clear()
        return
        
    await state.update_data(msg_id=message.message_id, chat_id=message.chat.id)
    channels = await db.channels.find().to_list(length=100)
    
    if not channels:
        await message.answer("❌ Kanallar yo'q! Avval kanal qo'shing.", reply_markup=main_menu)
        await state.clear()
        return
        
    builder = [[InlineKeyboardButton(text=c['channel_name'], callback_data=f"ch_{c['channel_id']}")] for c in channels]
    await message.answer("Qaysi kanalga joylaymiz?", reply_markup=InlineKeyboardMarkup(inline_keyboard=builder))
    await state.set_state(PostState.waiting_for_channel)

@router.callback_query(PostState.waiting_for_channel, F.data.startswith("ch_"))
async def ch_select(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(target=callback.data.split("ch_")[1])
    await callback.message.delete()
    
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🤖 Avto vaqt")], [KeyboardButton(text="Bekor qilish")]],
        resize_keyboard=True
    )
    await callback.message.answer(
        "⏰ **Vaqtni kiriting:**\n(Masalan: `15:00` yoki `04-15 15:00`)\n\nYoki tayyor soatlarni tanlash uchun pastdagi **🤖 Avto vaqt** tugmasini bosing.",
        reply_markup=kb
    )
    await state.set_state(PostState.waiting_for_time)

@router.message(PostState.waiting_for_time)
async def process_manual_time(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        await message.answer("Bekor qilindi.", reply_markup=main_menu)
        await state.clear()
        return
        
    if message.text == "🤖 Avto vaqt":
        hours_kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="08:00"), KeyboardButton(text="10:00"), KeyboardButton(text="12:00")],
                [KeyboardButton(text="14:00"), KeyboardButton(text="16:00"), KeyboardButton(text="18:00")],
                [KeyboardButton(text="20:00"), KeyboardButton(text="22:00"), KeyboardButton(text="Bekor qilish")]
            ],
            resize_keyboard=True
        )
        await message.answer("⏰ Qaysi soatga rejalashtiramiz?", reply_markup=hours_kb)
        await state.set_state(PostState.waiting_for_auto_hour)
        return

    data = await state.get_data()
    t_str = message.text.strip()
    if "," in t_str or "\n" in t_str:
        await message.answer("❌ Basic versiyada faqat 1 ta vaqt kiritish mumkin!")
        return

    try:
        now = datetime.now(TIMEZONE)
        if len(t_str) <= 5: 
            parsed_dt = datetime.strptime(f"{now.strftime('%m-%d')} {t_str}", "%m-%d %H:%M")
            if parsed_dt.time() < now.time(): parsed_dt += timedelta(days=1)
        else: 
            parsed_dt = datetime.strptime(t_str, "%m-%d %H:%M")
        
        final_dt = TIMEZONE.localize(parsed_dt.replace(year=2026))
        
        await db.posts.insert_one({
            "message_id": data['msg_id'], "from_chat_id": data['chat_id'],
            "target": data['target'], "time": final_dt.isoformat(),
            "status": "pending", "is_pro": False
        })
        await message.answer(f"✅ Post saqlandi! Vaqti: {final_dt.strftime('%d-%m-%Y %H:%M')}", reply_markup=main_menu)
        await state.clear()
    except Exception:
        await message.answer("❌ Xato format. Soatni to'g'ri yozing.")

@router.message(PostState.waiting_for_auto_hour)
async def get_auto_hour(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        await message.answer("Bekor qilindi.", reply_markup=main_menu)
        await state.clear()
        return
        
    await state.update_data(auto_hour=message.text)
    
    dates_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Bugun"), KeyboardButton(text="Ertaga")],
            [KeyboardButton(text="Indinga"), KeyboardButton(text="Bekor qilish")]
        ],
        resize_keyboard=True
    )
    await message.answer(f"Tanlangan soat: **{message.text}**\nEndi sanani tanlang:", reply_markup=dates_kb)
    await state.set_state(PostState.waiting_for_auto_date)

@router.message(PostState.waiting_for_auto_date)
async def get_auto_date(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        await message.answer("Bekor qilindi.", reply_markup=main_menu)
        await state.clear()
        return
        
    data = await state.get_data()
    hour_str = data.get('auto_hour', '12:00')
    
    now = datetime.now(TIMEZONE)
    try:
        hour, minute = map(int, hour_str.split(':'))
        
        if message.text == "Bugun":
            target_date = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target_date < now:
                await message.answer("⚠️ Bu vaqt o'tib ketgan! Avtomatik tarzda ertangi kunga o'tkazildi.")
                target_date += timedelta(days=1)
        elif message.text == "Ertaga":
            target_date = (now + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        elif message.text == "Indinga":
            target_date = (now + timedelta(days=2)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            parsed_date = datetime.strptime(message.text.strip(), "%m-%d")
            target_date = TIMEZONE.localize(parsed_date.replace(year=2026, hour=hour, minute=minute))

        final_dt = TIMEZONE.localize(target_date.replace(tzinfo=None)) if target_date.tzinfo is None else target_date

        await db.posts.insert_one({
            "message_id": data['msg_id'], "from_chat_id": data['chat_id'],
            "target": data['target'], "time": final_dt.isoformat(),
            "status": "pending", "is_pro": False
        })
        
        await message.answer(f"✅ Avto-vaqt bilan rejalashtirildi!\nKuni va soati: **{final_dt.strftime('%d-%m-%Y %H:%M')}**", reply_markup=main_menu)
        await state.clear()
    except Exception as e:
        await message.answer("❌ Xatolik yuz berdi. Iltimos tugmalardan foydalaning.")
