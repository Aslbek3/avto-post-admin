import logging
from datetime import datetime
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
        [KeyboardButton(text="📅 Reja"), KeyboardButton(text="⚙️ Kanallar")]
    ],
    resize_keyboard=True
)

class PostState(StatesGroup):
    waiting_for_post = State()
    waiting_for_button = State()
    waiting_for_channel = State()
    waiting_for_time = State()

class ChannelState(StatesGroup):
    waiting_for_name = State()
    waiting_for_id = State()

# Menyudagi tugmalar ro'yxati (Bekor qilish tizimi uchun kerak)
MENU_BUTTONS = ["📥 Post yuklash", "📅 Reja", "⚙️ Kanallar", "/start"]

@router.message(F.text == "/start")
async def start_cmd(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS: return
    await state.clear()
    await message.answer("Assalomu alaykum, Admin! Tizim tayyor.", reply_markup=main_menu)

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
        
    # QAT'IY TEKSHIRUV: ID -100 yoki @ bilan boshlanishi shart
    if not (message.text.startswith("-100") or message.text.startswith("@")):
        await message.answer("❌ Xato! Kanal ID'si doim '-100' bilan yoki username '@' bilan boshlanishi kerak. Qaytadan yozing:")
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
    await callback.answer("Post rejadagi ro'yxatdan o'chirildi.")

# ==================== POST YUKLASH ====================
@router.message(F.text == "📥 Post yuklash")
async def post_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS: return
    await state.clear()
    await message.answer("Postni yuboring (rasm/video/matn):")
    await state.set_state(PostState.waiting_for_post)

@router.message(PostState.waiting_for_post)
async def post_get(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        await state.clear()
        return
        
    await state.update_data(msg_id=message.message_id, chat_id=message.chat.id)
    await message.answer("Tugma qo'shamizmi?\nFormat: `Batafsil - https://t.me/link`\nAgar yo'q bo'lsa, **Yo'q** deb yozing.")
    await state.set_state(PostState.waiting_for_button)

@router.message(PostState.waiting_for_button)
async def btn_get(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        await state.clear()
        return
        
    text = message.text or ""
    b_text, b_url = None, None
    if "http" in text:
        parts = text.split("http", 1)
        b_text = parts[0].replace("-", "").strip() or "O'tish"
        b_url = "http" + parts[1].strip()
    
    await state.update_data(b_text=b_text, b_url=b_url)
    channels = await db.channels.find().to_list(length=100)
    
    if not channels:
        await message.answer("❌ Bazada kanallar yo'q! Avval kanal qo'shing.")
        await state.clear()
        return
        
    builder = [[InlineKeyboardButton(text=c['channel_name'], callback_data=f"ch_{c['channel_id']}")] for c in channels]
    await message.answer("Qaysi kanalga joylaymiz?", reply_markup=InlineKeyboardMarkup(inline_keyboard=builder))
    await state.set_state(PostState.waiting_for_channel)

@router.callback_query(PostState.waiting_for_channel, F.data.startswith("ch_"))
async def ch_select(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(target=callback.data.split("ch_")[1])
    await callback.message.answer("Vaqtni kiriting (Masalan: `15:00` yoki `04-01 16:30`).\nVergul bilan bir nechta vaqt ham kiritish mumkin.")
    await state.set_state(PostState.waiting_for_time)

@router.message(PostState.waiting_for_time)
async def process_smart_time(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        await state.clear()
        return
        
    data = await state.get_data()
    times_input = message.text.replace(",", "\n").split("\n")
    
    success_count = 0
    errors = []
    
    for t_str in times_input:
        t_str = t_str.strip()
        if not t_str: continue
        
        try:
            if len(t_str) <= 5: 
                parsed_dt = datetime.strptime(f"{datetime.now().strftime('%m-%d')} {t_str}", "%m-%d %H:%M")
            else: 
                parsed_dt = datetime.strptime(t_str, "%m-%d %H:%M")
            
            final_dt = TIMEZONE.localize(parsed_dt.replace(year=2026))
            
            await db.posts.insert_one({
                "message_id": data['msg_id'], "from_chat_id": data['chat_id'],
                "target": data['target'], "time": final_dt.isoformat(),
                "status": "pending", "b_text": data.get('b_text'), "b_url": data.get('b_url')
            })
            success_count += 1
        except Exception as e:
            errors.append(f"`{t_str}` (Xato format. HH:MM ko'rinishida yozing)")

    res_text = f"✅ **{success_count}** ta post rejalashtirildi!"
    if errors:
        res_text += "\n\n❌ Xatolar:\n" + "\n".join(errors)
    
    await message.answer(res_text, reply_markup=main_menu)
    await state.clear()
