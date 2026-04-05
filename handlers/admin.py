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

class PostState(StatesGroup):
    kanal_tanlash = State()
    post_kutish = State()
    vaqt_tanlash = State()
    sana_tanlash = State()

class ChannelState(StatesGroup):
    waiting_for_id = State()
    waiting_for_bot = State()

class TimeState(StatesGroup):
    waiting_for_time = State()

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📥 Post yuklash"), KeyboardButton(text="📅 Reja")],
        [KeyboardButton(text="⏰ Avtovaqt"), KeyboardButton(text="📢 Kanallar")],
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="⚙️ Sozlamalar")]
    ], resize_keyboard=True
)

@admin_router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    if not await db.is_admin(message.from_user.id):
        await message.answer(strings.START_REKLAMA)
        return
    await message.answer(strings.ADMIN_START, reply_markup=main_menu)

@admin_router.message(F.text == "📊 Statistika")
async def show_stats(message: Message):
    if not await db.is_admin(message.from_user.id): return
    stats_text = await db.get_bot_statistics()
    await message.answer(stats_text)

@admin_router.message(F.text == "📅 Reja")
async def show_schedule(message: Message):
    if not await db.is_admin(message.from_user.id): return
    posts = await db.get_all_pending_posts() 
    if not posts:
        await message.answer("Hozircha navbatda postlar yo'q.")
        return
    
    await message.answer("📅 Umumiy xabarlar rejasi:")
    for p in posts[:10]:
        qisqa_matn = p['text'][:40] + "..." if len(p['text']) > 40 else p['text']
        info_text = (
            f"⏰ Vaqt: {p['send_time']}\n"
            f"📝 Post: {qisqa_matn}\n"
            f"📢 Kanallar: {len(p['target_channels'])} ta"
        )
        btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"delpost_{p['_id']}")]])
        await message.answer(info_text, reply_markup=btn)

@admin_router.callback_query(F.data.startswith("delpost_"))
async def delete_post_call(call: CallbackQuery):
    pid = call.data.split("_")[1]
    post = await db.db.posts.find_one({"_id": ObjectId(pid)})
    if post and post.get("queue_msg_id"):
        try:
            await call.bot.delete_message(chat_id=config.QUEUE_CHANNEL_ID, message_id=post["queue_msg_id"])
        except: pass
    await db.db.posts.delete_one({"_id": ObjectId(pid)})
    await call.message.delete()
    await call.answer("✅ Post o'chirildi.")

@admin_router.message(F.text == "📢 Kanallar")
async def channels_list(message: Message):
    if not await db.is_admin(message.from_user.id): return
    kanallar = await db.get_channels()
    text = "📢 Umumiy kanallar ro'yxati:\n\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if kanallar:
        for k in kanallar:
            text += f"🔹 {k['channel_name']} | 🤖 {k['bot_username']}\n"
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"🗑 {k['channel_name'][:10]}", callback_data=f"delch_{k['channel_id']}")])
    else:
        text += "Hozircha kanallar yo'q.\n"
    kb.inline_keyboard.append([InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_new_ch")])
    await message.answer(text, reply_markup=kb)

@admin_router.callback_query(F.data == "add_new_ch")
async def add_ch_start(call: CallbackQuery, state: FSMContext):
    text = "📢 Kanal ID raqamini yuboring (-100 bilan boshlanishi shart):\n\n💡 Yordam: @userinfobot ga kanaldan xabar uzating va IDsini oling."
    await call.message.answer(text)
    await state.set_state(ChannelState.waiting_for_id)

@admin_router.message(ChannelState.waiting_for_id)
async def get_ch_id(message: Message, state: FSMContext):
    if not message.text.startswith("-100"):
        await message.answer("❌ Xato! Qaytadan yuboring:")
        return
    await state.update_data(ch_id=message.text.strip())
    await message.answer("Bot usernameni yuboring (@ bilan boshlanishi shart):")
    await state.set_state(ChannelState.waiting_for_bot)

@admin_router.message(ChannelState.waiting_for_bot)
async def get_ch_bot(message: Message, state: FSMContext):
    if not message.text.startswith("@"):
        await message.answer("❌ Xato! Qaytadan yuboring:")
        return
        
    data = await state.get_data()
    ch_id_str = data['ch_id']
    bot_uname = message.text.strip()
    
    # 🌟 KANAL NOMINI AVTOMATIK TOPISH 🌟
    kanal_nomi = ch_id_str 
    try:
        chat_info = await message.bot.get_chat(chat_id=ch_id_str)
        kanal_nomi = chat_info.title
    except:
        await message.answer("⚠️ Bot hali kanalga admin qilinmagan. Hozircha ID orqali saqlanadi.")

    await db.add_channel(ch_id_str, kanal_nomi, bot_uname)
    await message.answer(f"✅ Kanal saqlandi: {kanal_nomi}", reply_markup=main_menu)
    await state.clear()

@admin_router.callback_query(F.data.startswith("delch_"))
async def del_ch_call(call: CallbackQuery):
    ch_id = call.data.split("_")[1]
    await db.remove_channel(ch_id)
    await call.answer("❌ Kanal o'chirildi")
    await call.message.delete()

@admin_router.message(F.text == "⏰ Avtovaqt")
async def auto_times_menu(message: Message):
    if not await db.is_admin(message.from_user.id): return
    times = await db.get_auto_times()
    text = "⏰ Umumiy avto-vaqtlar:\n\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for t in times:
        text += f"🕒 {t}\n"
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"🗑 {t}", callback_data=f"deltime_{t}")])
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
        await db.add_auto_time(new_t)
        await message.answer("✅ Vaqt qo'shildi!", reply_markup=main_menu)
        await state.clear()
    except:
        await message.answer(strings.ERR_TIME_FORMAT)

@admin_router.callback_query(F.data.startswith("deltime_"))
async def del_time_call(call: CallbackQuery):
    t_val = call.data.split("_")[1]
    await db.delete_auto_time(t_val)
    await call.answer("✅ O'chirildi")
    await call.message.delete()

@admin_router.message(F.text == "📥 Post yuklash")
async def post_start(message: Message, state: FSMContext):
    if not await db.is_admin(message.from_user.id): return
    kanallar = await db.get_channels()
    if not kanallar:
        await message.answer("❌ Avval kanal qo'shing!")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=k['channel_name'], callback_data=f"ch_{k['channel_id']}")] for k in kanallar])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🌟 Barcha kanallar", callback_data="ch_all")])
    await message.answer("Boshladik! Avval qaysi kanalga post joylashni tanlang:", reply_markup=kb)
    await state.set_state(PostState.kanal_tanlash)

@admin_router.callback_query(StateFilter(PostState.kanal_tanlash))
async def post_select_ch(call: CallbackQuery, state: FSMContext):
    if call.data == "ch_all":
        ids = [k['channel_id'] for k in await db.get_channels()]
    else:
        ids = [call.data.split("_")[1]]
    await state.update_data(target_channels=ids)
    await call.message.delete()
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Bekor qilish")]], resize_keyboard=True)
    await call.message.answer("Yaxshi! Endi postni yuboring (Rasm yoki matn):", reply_markup=kb)
    await state.set_state(PostState.post_kutish)

@admin_router.message(StateFilter(PostState.post_kutish))
async def post_get_content(message: Message, state: FSMContext):
    if message.text == "Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu)
        return
    text = message.caption or message.text or ""
    if "[bot nomi]" not in text.lower() and "[bot_nomi]" not in text.lower():
        text += "\n\n🤖 Bot manzili: [bot nomi]"
    photo_id = message.photo[-1].file_id if message.photo else None
    await state.update_data(photo_id=photo_id, text=text)
    
    times = await db.get_auto_times()
    btns = [[KeyboardButton(text="Hozir (+1 min)"), KeyboardButton(text="Hozir (+5 min)")]]
    row = []
    for t in times:
        row.append(KeyboardButton(text=t))
        if len(row) == 3: btns.append(row); row = []
    if row: btns.append(row)
    btns.append([KeyboardButton(text="Bekor qilish")])
    await message.answer("⏰ Qachon yuboramiz? Vaqtni tanlang:", reply_markup=ReplyKeyboardMarkup(keyboard=btns, resize_keyboard=True))
    await state.set_state(PostState.vaqt_tanlash)

@admin_router.message(StateFilter(PostState.vaqt_tanlash))
async def post_select_time(message: Message, state: FSMContext):
    v = message.text.strip()
    if v == "Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu)
        return
    await state.update_data(tanlangan_vaqt=v)
    btns = [[KeyboardButton(text="Bugun"), KeyboardButton(text="Ertaga")], [KeyboardButton(text="Bekor qilish")]]
    await message.answer("📅 Sanani tanlang (yoki DD.MM qo'lda yozing):", reply_markup=ReplyKeyboardMarkup(keyboard=btns, resize_keyboard=True))
    await state.set_state(PostState.sana_tanlash)

@admin_router.message(StateFilter(PostState.sana_tanlash))
async def post_save_final(message: Message, state: FSMContext):
    d = message.text.strip()
    if d == "Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu)
        return
    data = await state.get_data()
    v = data['tanlangan_vaqt']
    hozir = datetime.now(config.TIMEZONE)
    
    if v.startswith("Hozir"):
        mins = 1 if "1" in v else 5
        yakuniy_v = (hozir + timedelta(minutes=mins)).strftime("%d.%m %H:%M")
    else:
        try: datetime.strptime(v, "%H:%M")
        except:
            await message.answer("❌ Xato vaqt!", reply_markup=main_menu)
            await state.clear(); return
            
        if d == "Bugun": sana_str = hozir.strftime("%d.%m")
        elif d == "Ertaga": sana_str = (hozir + timedelta(days=1)).strftime("%d.%m")
        else:
            try:
                datetime.strptime(d, "%d.%m")
                sana_str = d
            except:
                await message.answer("❌ Sana xato formatda!", reply_markup=main_menu)
                await state.clear(); return
        yakuniy_v = f"{sana_str} {v}"
    
    queue_msg_id = None
    try:
        q_text = f"⏳ KUTILYAPTI\n⏰ {yakuniy_v}\n\n{data['text']}"
        if data['photo_id']: q_msg = await message.bot.send_photo(chat_id=config.QUEUE_CHANNEL_ID, photo=data['photo_id'], caption=q_text)
        else: q_msg = await message.bot.send_message(chat_id=config.QUEUE_CHANNEL_ID, text=q_text)
        queue_msg_id = q_msg.message_id
    except: pass 
        
    await db.add_post(data['text'], data['photo_id'], yakuniy_v, data['target_channels'], queue_msg_id)
    await message.answer(f"{strings.POST_SAVED}\n📅 To'liq Vaqt: {yakuniy_v}", reply_markup=main_menu)
    await state.clear()
