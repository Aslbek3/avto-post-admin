from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from datetime import datetime, timedelta

import database as db
import config

admin_router = Router()

# Holatlar
class PostState(StatesGroup):
    post_kutish = State()
    kanal_tanlash = State()
    vaqt_tanlash = State()

class ChannelState(StatesGroup):
    info_kutish = State()

# Asosiy menyu
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📥 Post yuklash"), KeyboardButton(text="📅 Reja")],
        [KeyboardButton(text="📢 Kanallar"), KeyboardButton(text="🚀 PRO Versiya")]
    ],
    resize_keyboard=True
)

# ==========================================
# 1. START VA REKLAMA
# ==========================================
@admin_router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    
    if not await db.is_admin(message.from_user.id):
        reklama_matni = (
            "👋 Assalomu alaykum!\n\n"
            "🤖 Bu bot Telegram kanallarga xabarlarni avtomatik joylash uchun mo'ljallangan.\n\n"
            "💎 **Shaxsiy Avto-Post botga ega bo'lishni xohlaysizmi?**\n"
            "Kanallaringizni avtomatlashtiring, vaqtni tejang va ishingizni osonlashtiring!\n\n"
            "Batafsil ma'lumot va bot xarid qilish uchun adminga yozing."
        )
        await message.answer(reklama_matni)
        return
        
    await message.answer("👋 Assalomu alaykum, Admin!\nNima qilamiz?", reply_markup=main_menu)

@admin_router.message(F.text == "🚀 PRO Versiya")
async def pro_ad(message: Message):
    if not await db.is_admin(message.from_user.id): return
    text = (
        "🚀 **PRO Versiya Afzalliklari:**\n\n"
        "✅ Birdaniga yuzlab postlarni oson rejalashtirish;\n"
        "✅ Postlarga chiroyli ssilka tugmalari qo'shish;\n"
        "✅ Rasmlarga avtomatik Watermark (Suv belgisi) yozish;\n"
        "✅ Kanallar va postlar sonida umuman cheklov yo'q;\n"
        "✅ Interval taymer (har X minutda avtomatik post tashlash).\n\n"
        "Tarifni yangilash uchun adminga yozing: @aslbek_1203"
    )
    await message.answer(text)

# ==========================================
# 2. REJA (KUTISH ZALI)
# ==========================================
@admin_router.message(F.text == "📅 Reja")
async def show_schedule(message: Message):
    if not await db.is_admin(message.from_user.id): return
    
    posts = await db.get_pending_posts() 
    
    if not posts:
        await message.answer("Hozircha navbatda postlar yo'q.")
        return
        
    await message.answer("📅 **Yaqin xabarlar rejasi:**")
    
    for i, p in enumerate(posts[:20], 1):
        btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"delpost_{p['_id']}")]
        ])
        await message.answer(f"Post #{i} | ⏰ {p['send_time']} | 📢 {len(p['target_channels'])} ta kanal", reply_markup=btn)

@admin_router.callback_query(F.data.startswith("delpost_"))
async def delete_post(call: CallbackQuery):
    pid = call.data.split("_")[1]
    from bson import ObjectId
    # Eski xato: db.db.posts emas, faqat db.posts bo'lishi kerak
    await db.db.posts.delete_one({"_id": ObjectId(pid)})
    await call.message.delete()
    await call.answer("✅ Post o'chirildi.")

# ==========================================
# 3. KANALLAR SOZLAMASI
# ==========================================
@admin_router.message(F.text == "📢 Kanallar")
async def channels_menu(message: Message, state: FSMContext):
    if not await db.is_admin(message.from_user.id): return
    
    kanallar = await db.get_channels()
    matn = "📢 **Kanallar ro'yxati:**\n\n"
    for k in kanallar: 
        matn += f"▪️ {k['channel_id']} | Boti: {k['bot_username']}\n"
        
    matn += "\nYangi kanal qo'shish uchun Kanal manzili va Bot manzilini bitta xabarda probel bilan yozing.\n(Masalan: @KinoOlami @Kino_boti)"
    
    await message.answer(matn)
    await state.set_state(ChannelState.info_kutish)

@admin_router.message(ChannelState.info_kutish)
async def add_channel_fast(message: Message, state: FSMContext):
    # Menyuga qaytish tugmasi bosilsa to'xtatish
    if message.text in ["📥 Post yuklash", "📅 Reja", "📢 Kanallar", "🚀 PRO Versiya"]:
        await state.clear()
        return
        
    qism = message.text.split()
    if len(qism) == 2:
        await db.add_channel(
            channel_id=qism[0], 
            channel_name=qism[0], 
            bot_username=qism[1]
        )
        await message.answer("✅ Kanal muvaffaqiyatli saqlandi!")
    else:
        await message.answer("❌ Xato kiritildi. Iltimos, ikkita manzilni probel tashlab yozing.")
    
    await state.clear()

# ==========================================
# 4. POST YUKLASH TIZIMI
# ==========================================
@admin_router.message(F.text == "📥 Post yuklash")
async def start_post(message: Message, state: FSMContext):
    if not await db.is_admin(message.from_user.id): return
    await message.answer("Iltimos, postni yuboring (Rasm va matn):")
    await state.set_state(PostState.post_kutish)

@admin_router.message(StateFilter(PostState.post_kutish))
async def get_post(message: Message, state: FSMContext):
    # Rasm va matnni olish
    if message.photo:
        photo_id = message.photo[-1].file_id
        text = message.caption or ""
    else:
        photo_id = None
        text = message.text or ""
        
    await state.update_data(photo_id=photo_id, text=text)
    
    kanallar = await db.get_channels()
    if not kanallar:
        await message.answer("❌ Kanallar mavjud emas! Avval kanal qo'shing.")
        await state.clear()
        return
        
    # Inline tugmalar yasash
    tugmalar = []
    for k in kanallar:
        tugmalar.append([InlineKeyboardButton(text=k['channel_name'], callback_data=f"ch_{k['channel_id']}")])
    tugmalar.append([InlineKeyboardButton(text="Barcha kanallar", callback_data="ch_all")])
    
    await message.answer("Qaysi kanalga yuboramiz?", reply_markup=InlineKeyboardMarkup(inline_keyboard=tugmalar))
    await state.set_state(PostState.kanal_tanlash)

@admin_router.callback_query(StateFilter(PostState.kanal_tanlash))
async def select_channel(call: CallbackQuery, state: FSMContext):
    tanlov = call.data
    
    if tanlov == "ch_all":
        kanallar = await db.get_channels()
        target_ids = [k['channel_id'] for k in kanallar]
    else:
        target_ids = [tanlov.split("_")[1]]
        
    await state.update_data(target_channels=target_ids)
    await call.message.delete()
    
    # Vaqtlarni tugma qilib chiqarish
    vaqtlar = await db.get_auto_times()
    tugmalar = [
        [KeyboardButton(text="Hozir (+1 min)"), KeyboardButton(text="Hozir (+5 min)")]
    ]
    
    qator = []
    for v in vaqtlar:
        qator.append(KeyboardButton(text=v))
        if len(qator) == 3:
            tugmalar.append(qator)
            qator = []
    if qator:
        tugmalar.append(qator)
        
    tugmalar.append([KeyboardButton(text="Bekor qilish")])
    
    kb = ReplyKeyboardMarkup(keyboard=tugmalar, resize_keyboard=True)
    await call.message.answer("⏰ Vaqtni tanlang yoki qo'lda yozing (Masalan: 15:00):", reply_markup=kb)
    await state.set_state(PostState.vaqt_tanlash)

@admin_router.message(StateFilter(PostState.vaqt_tanlash))
async def save_time(message: Message, state: FSMContext):
    vaqt = message.text.strip()
    
    if vaqt == "Bekor qilish":
        await message.answer("Jarayon bekor qilindi.", reply_markup=main_menu)
        await state.clear()
        return

    hozir = datetime.now(config.TIMEZONE)
    yakuniy_vaqt_str = ""
    
    if vaqt == "Hozir (+1 min)":
        yakuniy_vaqt_str = (hozir + timedelta(minutes=1)).strftime("%H:%M")
    elif vaqt == "Hozir (+5 min)":
        yakuniy_vaqt_str = (hozir + timedelta(minutes=5)).strftime("%H:%M")
    else:
        try:
            # Vaqt formati to'g'riligini tekshirish
            datetime.strptime(vaqt, "%H:%M")
            yakuniy_vaqt_str = vaqt
        except ValueError:
            await message.answer("❌ Noto'g'ri format. Vaqtni faqat HH:MM ko'rinishida yozing.")
            return
            
    data = await state.get_data()
    
    # Bazaga saqlash
    await db.add_post(
        text=data['text'], 
        photo_id=data['photo_id'], 
        send_time=yakuniy_vaqt_str, 
        target_channels=data['target_channels']
    )
    
    await message.answer(f"✅ Post muvaffaqiyatli saqlandi!\n⏰ Chiqish vaqti: {yakuniy_vaqt_str}", reply_markup=main_menu)
    await state.clear()
