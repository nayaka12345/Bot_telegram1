# ============================================================
# handlers.py - Route & logika untuk setiap command/pesan
# Menangani interaksi dengan user Telegram
# ============================================================

import logging
import os
import random
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import CommandStart, Command

import config
import database as db
import matching as match
import utils

logger = logging.getLogger(__name__)
router = Router()

# ─── MIDDLEWARE-LIKE HELPER ───────────────────────────────────

async def check_user_status(message: Message, send_warning: bool = True, user_id: int = None) -> dict | None:
    """
    Cek status user (banned, perlu reset harian, dll).
    Return data user dari cache, atau None jika banned/error.
    """
    uid = user_id or message.from_user.id
    user = match.get_cached_user(uid)
    
    # Jika tidak ada di cache RAM, ambil dari Firebase
    if not user:
        # Gunakan username dari message, tapi fallback kosong jika bukan dari message langsung
        username = message.from_user.username if not user_id else ""
        user = await db.get_or_create_user(uid, username)
        match.cache_user(uid, user)
    
    if user.get("banned"):
        if send_warning:
            await message.answer("⛔ Akun Anda telah di-banned karena banyak laporan pelanggaran.")
        return None
        
    # Reset daily limit jika beda hari
    if db.should_reset_daily(user.get("last_reset_date", "")):
        await db.reset_daily_count(uid)
        user["daily_count"] = 0
        user["last_reset_date"] = db.datetime.now().isoformat()
        match.update_cached_user(uid, {"daily_count": 0, "last_reset_date": user["last_reset_date"], "reset_count": user.get("reset_count", 0) + 1})
        
    return user


async def check_limit(user: dict, message: Message) -> bool:
    """Cek apakah user mencapai limit harian. Return True jika bisa lanjut."""
    if user.get("is_premium"):
        return True
        
    limit = utils.get_user_limit(user)
    if user.get("daily_count", 0) >= limit:
        await message.answer(
            "⚠️ Mof, limit chat harian kamu sudah habis.\n"
            "Ketik /upgrade untuk lanjut chat tanpa batas!",
            reply_markup=utils.main_keyboard()
        )
        return False
    return True


# ─── COMMAND HANDLERS ─────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handler untuk /start"""
    user = await check_user_status(message)
    if not user: return
    
    # Hentikan sesi jika sedang aktif atau dalam antrean
    match.end_session(message.from_user.id)
    match.remove_from_queue(message.from_user.id)
    
    if not user.get("registered") or not user.get("gender") or not user.get("province"):
        # Baru pertama kali masuk, perlu registrasi
        await message.answer(
            "👋 Selamat datang di Bot Anonymous Chat!\n\n"
            "Sebelum mulai, pilih gender kamu dulu:",
            reply_markup=utils.gender_keyboard()
        )
    else:
        # Sudah terdaftar, tampilkan menu utama
        await message.answer(
            "Halo kembali! Siap mencari teman ngobrol?",
            reply_markup=utils.main_keyboard()
        )


@router.message(Command("find"))
async def cmd_find(message: Message):
    """Mulai mencari partner via command"""
    args = message.text.split()
    target_gender = None
    target_location = False
    
    if len(args) > 1:
        param = args[1].lower()
        if param in ["cowok", "cewek"]:
            target_gender = "male" if param == "cowok" else "female"
        elif param == "kota":
            target_location = True
            
    await handle_find_action(message, message.from_user.id, target_gender, target_location)


@router.message(Command("stop"))
async def cmd_stop(message: Message):
    """Berhenti chatting atau keluar antrean via command"""
    await handle_stop_action(message, message.from_user.id)


@router.message(Command("next"))
async def cmd_next(message: Message):
    """Ganti partner via command"""
    await handle_next_action(message, message.from_user.id)


@router.message(Command("upgrade"))
async def cmd_upgrade(message: Message):
    """Instruksi upgrade premium"""
    user_id = message.from_user.id
    match.update_cached_user(user_id, {"registration_step": "awaiting_payment_proof"})
    
    fake_count = random.randint(30, 85)
    instructions = config.UPGRADE_INSTRUCTIONS.format(fake_count=fake_count)
    
    if os.path.exists("qris.jpg"):
        photo = FSInputFile("qris.jpg")
        await message.answer_photo(photo, caption=instructions, parse_mode="Markdown")
    else:
        await message.answer(instructions, parse_mode="Markdown")


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Lihat status profil sendiri"""
    user = await check_user_status(message)
    if not user: return
    
    profile_text = utils.format_profile(user)
    await message.answer(profile_text, parse_mode="Markdown", reply_markup=utils.main_keyboard())


@router.message(Command("report"))
async def cmd_report(message: Message, bot: Bot):
    """Melaporkan partner chat yang toxic"""
    user_id = message.from_user.id
    partner_id = match.get_partner(user_id)
    
    if not partner_id:
        await message.answer("Kamu tidak sedang dalam obrolan.")
        return
        
    await message.answer(
        "🚨 Apakah kamu yakin ingin melaporkan partner ini?\n"
        "Ini akan mengakhiri sesi chat kalian.",
        reply_markup=utils.confirm_keyboard()
    )


@router.message(Command("approv"))
async def cmd_approv(message: Message):
    """[Admin] Proses persetujuan langganan"""
    if message.from_user.id not in config.ADMIN_IDS:
        return
        
    approvals = await db.get_pending_approvals(limit=1)
    if not approvals:
        await message.answer("🎉 Tidak ada antrean persetujuan pembayaran saat ini!")
        return
        
    data = approvals[0]
    target_id = data["user_id"]
    file_id = data["file_id"]
    
    txt = f"💳 **Review Pembayaran Baru**\nID User: `{target_id}`\nTanggal: {data['timestamp']}"
    await message.answer_photo(file_id, caption=txt, parse_mode="Markdown", reply_markup=utils.approval_keyboard(target_id))


# ─── ADMIN COMMANDS ───────────────────────────────────────────

import asyncio

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, bot: Bot):
    """[Admin] Kirim broadcast ke semua user teregistrasi."""
    if message.from_user.id not in config.ADMIN_IDS:
        return
        
    text = message.text.replace("/broadcast ", "", 1).strip()
    if not text or text == "/broadcast":
        await message.answer("Format: /broadcast <pesan text/caption>")
        return
        
    users = await db.get_all_users()
    await message.answer(f"⏳ Sedang mengirim pesan broadcast ke {len(users)} pengguna...")
    
    success = 0
    fail = 0
    for u in users:
        try:
            # Gunakan copy_to agar semua format (gambar/video dll) bisa di broadcast
            await message.copy_to(chat_id=u["user_id"])
            success += 1
            await asyncio.sleep(0.05) # Cegah rate-limit
        except Exception:
            fail += 1
            
    await message.answer(f"✅ Broadcast Selesai!\nBerhasil terkirim: {success}\nGagal (diblokir): {fail}")

@router.message(Command("setpremium"))
async def cmd_setpremium(message: Message):
    """[Admin] Set user jadi premium. Format: /setpremium <user_id> [1|0]"""
    if message.from_user.id not in config.ADMIN_IDS:
        return
        
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Format: /setpremium <user_id> [1|0]")
        return
        
    try:
        target_id = int(parts[1])
        status = True if len(parts) < 3 or parts[2] == "1" else False
        
        # Update Firebase
        await db.set_premium(target_id, status)
        
        # Update RAM cache kalau ada
        target_user = match.get_cached_user(target_id)
        if target_user:
            match.update_cached_user(target_id, {"is_premium": status})
            
        await message.answer(f"✅ Premium status untuk {target_id} diubah jadi {status}.")
    except Exception as e:
        await message.answer(f"❌ Error: {e}")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """[Admin] Lihat statistik server"""
    if message.from_user.id not in config.ADMIN_IDS:
        return
    
    stats = match.get_stats()
    text = utils.format_stats(stats)
    await message.answer(text, parse_mode="Markdown")


# ─── CALLBACK HANDLERS ────────────────────────────────────────

@router.callback_query(F.data.startswith("gender_"))
async def callback_gender(call: CallbackQuery):
    """Pilih gender saat registrasi"""
    gender = call.data.split("_")[1]
    user_id = call.from_user.id
    
    if not utils.is_valid_gender(gender): return
    
    match.update_cached_user(user_id, {"gender": gender})
    await call.message.edit_text(
        "Oke! Sekarang, apa tujuan kamu mencari teman chat?",
        reply_markup=utils.purpose_keyboard()
    )


@router.callback_query(F.data.startswith("purpose_"))
async def callback_purpose(call: CallbackQuery):
    """Pilih tujuan chat saat registrasi"""
    purpose = call.data.replace("purpose_", "")
    user_id = call.from_user.id
    
    if not utils.is_valid_purpose(purpose): return
    
    match.update_cached_user(user_id, {"purpose": purpose})
    await call.message.edit_text(
        "Di provinsi mana kamu tinggal sekarang?",
        reply_markup=utils.province_keyboard()
    )


@router.callback_query(F.data.startswith("prov_"))
async def callback_province(call: CallbackQuery):
    """Pilih provinsi saat registrasi"""
    province = call.data.replace("prov_", "")
    user_id = call.from_user.id
    
    if province == "Lainnya":
        match.update_cached_user(user_id, {"registration_step": "awaiting_province"})
        await call.message.edit_text("Silakan ketikkan nama provinsi kamu:")
        return
        
    match.update_cached_user(user_id, {"province": province})
    await call.message.edit_text(
        "Pilih kota tempat tinggalmu:",
        reply_markup=utils.city_keyboard(province)
    )

@router.callback_query(F.data.startswith("city_"))
async def callback_city(call: CallbackQuery):
    """Pilih kota saat registrasi"""
    city = call.data.replace("city_", "")
    user_id = call.from_user.id
    
    if city == "Lainnya":
        match.update_cached_user(user_id, {"registration_step": "awaiting_city"})
        await call.message.edit_text("Silakan ketikkan nama kota kamu:")
        return
        
    match.update_cached_user(user_id, {"city": city, "registered": True, "registration_step": None})
    await call.message.edit_text(
        "Yeayy... kamu sudah selesai daftar!\nCari teman ngobrol sekarang yuk 👇",
        reply_markup=utils.post_register_keyboard()
    )


@router.callback_query(F.data == "action_find")
async def callback_find(call: CallbackQuery):
    await call.answer()
    await handle_find_action(call.message, call.from_user.id)


@router.callback_query(F.data == "action_stop")
async def callback_stop(call: CallbackQuery):
    await call.answer()
    await handle_stop_action(call.message, call.from_user.id)


@router.callback_query(F.data == "action_next")
async def callback_next(call: CallbackQuery):
    await call.answer()
    await handle_next_action(call.message, call.from_user.id)


@router.callback_query(F.data == "action_upgrade")
async def callback_upgrade(call: CallbackQuery):
    await call.answer()
    match.update_cached_user(call.from_user.id, {"registration_step": "awaiting_payment_proof"})
    fake_count = random.randint(30, 85)
    instructions = config.UPGRADE_INSTRUCTIONS.format(fake_count=fake_count)
    
    if os.path.exists("qris.jpg"):
        photo = FSInputFile("qris.jpg")
        await call.message.answer_photo(photo, caption=instructions, parse_mode="Markdown")
    else:
        await call.message.answer(instructions, parse_mode="Markdown")


@router.callback_query(F.data == "action_status")
async def callback_status(call: CallbackQuery):
    await call.answer()
    user = await check_user_status(call.message, send_warning=False, user_id=call.from_user.id)
    if user:
        profile_text = utils.format_profile(user)
        # Edit text tidak selalu jalan jika pesannya sudah beda format, pakai answer baru
        await call.message.answer(profile_text, parse_mode="Markdown", reply_markup=utils.main_keyboard())


@router.callback_query(F.data.startswith("apprv_"))
async def callback_approval(call: CallbackQuery, bot: Bot):
    if call.from_user.id not in config.ADMIN_IDS:
        return
        
    parts = call.data.split("_")
    action = parts[1] # "yes" or "no"
    target_id = int(parts[2])
    
    await call.message.delete()
    await db.delete_payment_proof(target_id)
    
    if action == "yes":
        await db.set_premium(target_id, True)
        
        target_user = match.get_cached_user(target_id)
        if target_user:
            match.update_cached_user(target_id, {"is_premium": True})
            
        await call.message.answer(f"✅ Premium status untuk ID `{target_id}` berhasil diaktifkan.", parse_mode="Markdown")
        try:
            await bot.send_message(target_id, "🎉 Bukti pembayaranmu diterima! Akun kamu sekarang sudah PREMIUM!", reply_markup=utils.main_keyboard())
        except Exception:
            pass
    elif action == "no":
        await call.message.answer(f"❌ Status approve pembayaran ID `{target_id}` ditolak.", parse_mode="Markdown")
        try:
            await bot.send_message(target_id, "❌ Bukti pembayaran kamu ditolak. Silakan lengkapi pembayaran atau hubungi admin.")
        except Exception:
            pass


@router.callback_query(F.data.startswith("confirm_"))
async def callback_confirm_report(call: CallbackQuery, bot: Bot):
    """Menangani jawaban laporan (Ya/Tidak)"""
    action = call.data.split("_")[1]
    user_id = call.from_user.id
    
    await call.message.delete()
    
    if action == "no":
        await call.message.answer("Laporan dibatalkan.")
        return
        
    # Jika YA: Repot user
    partner_id = match.get_partner(user_id)
    if partner_id:
        # Tambah report ke Firebase
        reports = await db.increment_report(partner_id)
        if reports >= config.MAX_REPORTS_BEFORE_BAN:
            await db.ban_user(partner_id)
            # Opsional: update cache if needed
            match.update_cached_user(partner_id, {"banned": True})
            
        # Putus koneksi
        match.end_session(user_id)
        await bot.send_message(
            partner_id, 
            "Sesi telah dihentikan, dan pengguna melaporkan obrolan kalian.",
            reply_markup=utils.main_keyboard()
        )
        
    await call.message.answer(
        "✅ Partner telah dilaporkan. Sesi chat telah dihentikan.",
        reply_markup=utils.main_keyboard()
    )


@router.callback_query(F.data.startswith("feedback_"))
async def callback_feedback(call: CallbackQuery, bot: Bot):
    """Menangani review chat saat partner left"""
    parts = call.data.split("_")
    action = parts[1] # nakal / nyaman / aman
    partner_id = int(parts[2])
    
    if action == "aman":
        await call.message.edit_text("Syukurlah! Semoga obrolan selanjutnya lebih seru ya 😊")
        return
        
    # Jika review negatif
    await call.message.edit_text("😭 Jahat banget\n🥺 Nailong sedih dengernya...\nKami akan coba jaga kamu lebih baik ya 💛")
    
    # Daftarkan report
    reports = await db.increment_report(partner_id)
    if reports >= config.MAX_REPORTS_BEFORE_BAN:
        await db.ban_user(partner_id)
        match.update_cached_user(partner_id, {"banned": True})

# ─── MESSAGE RELAY (CHAT ENGINE) ───────────────────────────────

@router.message(F.photo)
async def handle_photo_upload(message: Message, bot: Bot):
    """Menangani upload foto (bukti pembayaran atau relay)"""
    user_id = message.from_user.id
    user = match.get_cached_user(user_id)
    
    if user and user.get("registration_step") == "awaiting_payment_proof":
        file_id = message.photo[-1].file_id # Ambil foto resolusi terbesar
        success = await db.add_payment_proof(user_id, file_id)
        if success:
            match.update_cached_user(user_id, {"registration_step": None})
            await message.answer("✅ Bukti pembayaran berhasil diunggah! Memasukkan Anda ke antrean untuk diverifikasi admin.")
        else:
            await message.answer("❌ Gagal menyimpan bukti. Silakan coba kirim ulang foto.")
        return

    # Jika bukan lagi antre bayar, relay gambarnya
    await relay_message(message, bot)

@router.message(~F.text.startswith('/'))  # Tangkap semua pesan teks selain command
async def relay_message(message: Message, bot: Bot):
    """Relay pesan dari user A ke user B"""
    user_id = message.from_user.id
    partner_id = match.get_partner(user_id)
    
    # Cek apakah user sedang dalam step registrasi manual (provinsi/kota)
    user = match.get_cached_user(user_id)
    if user and user.get("registration_step"):
        step = user["registration_step"]
        if message.text:
            text = message.text.strip()[:50]  # Batasi 50 karakter
            if step == "awaiting_province":
                match.update_cached_user(user_id, {"province": text, "registration_step": None})
                await message.answer("Pilih kota tempat tinggalmu:", reply_markup=utils.city_keyboard(text))
            elif step == "awaiting_city":
                match.update_cached_user(user_id, {"city": text, "registered": True, "registration_step": None})
                await message.answer(
                    "Yeayy... kamu sudah selesai daftar!\nCari teman ngobrol sekarang yuk 👇",
                    reply_markup=utils.post_register_keyboard()
                )
        return

    if not partner_id:
        if not match.is_in_queue(user_id):
            await message.answer(
                "Kamu belum terhubung dengan siapa pun.\n"
                "Ketik /find untuk mulai mencari.",
                reply_markup=utils.main_keyboard()
            )
        return
        
    # Ada partner, kirim pesan ke sana
    try:
        await message.copy_to(partner_id)
    except Exception as e:
        logger.error(f"Gagal relay pesan/media dari {user_id} ke {partner_id}: {e}")
        # Bila gagal, asumsikan partner blocked bot, putus sesi
        await handle_stop_action(message, user_id)
        await message.answer("Partner sepertinya terputus. Sesi dihentikan.")
            

# ─── LOGIC HANDLERS (ACTION HELPERS) ──────────────────────────

async def try_matchmaking(seeker_user_id: int, bot: Bot, target_gender: str = None, target_location: bool = False):
    """Proses utama matching algorithm."""
    seeker = match.get_cached_user(seeker_user_id)
    if not seeker: return
    
    # Masukkan filter VIP ke seeker sebelum mencari
    seeker["target_gender"] = target_gender
    seeker["target_location"] = target_location
    
    # 1. Cari kandidat
    partner = match.find_match(seeker)
    
    if not partner:
        # Masukkan ke queue
        match.add_to_queue(
            seeker_user_id, 
            seeker.get("purpose", ""), 
            seeker.get("gender", ""), 
            seeker.get("province", ""),
            seeker.get("city", ""),
            seeker.get("is_premium", False),
            target_gender,
            target_location
        )
        return
        
    # 2. Match ditemukan!
    partner_id = partner["user_id"]
    match.create_partnership(seeker_user_id, partner_id)
    
    # Increment limits
    match.increment_daily_count(seeker_user_id)
    match.increment_daily_count(partner_id)
    
    # Notifikasi
    p_purpose = partner["purpose"]
    s_purpose = seeker["purpose"]
    
    msg1 = utils.format_match_notification(p_purpose)
    msg2 = utils.format_match_notification(s_purpose)
    
    # Tambahan: Curhat Mode
    if s_purpose == "curhat":
        msg1 += f"\n\n{utils.get_empathy_message()}"
    if p_purpose == "curhat":
        msg2 += f"\n\n{utils.get_empathy_message()}"
    
    await bot.send_message(seeker_user_id, msg1, parse_mode="Markdown", reply_markup=utils.chat_keyboard())
    await bot.send_message(partner_id, msg2, parse_mode="Markdown", reply_markup=utils.chat_keyboard())
    
    # Warning limit jika free user
    seeker_user = match.get_cached_user(seeker_user_id)
    seeker_limit = utils.get_user_limit(seeker_user)
    if seeker_limit != config.PREMIUM_CHAT_LIMIT:
        w = utils.format_limit_warning(seeker_user.get("daily_count", 0), seeker_limit)
        if w: await bot.send_message(seeker_user_id, w, parse_mode="Markdown")
        
    partner_user = match.get_cached_user(partner_id)
    partner_limit = utils.get_user_limit(partner_user)
    if partner_limit != config.PREMIUM_CHAT_LIMIT:
        w = utils.format_limit_warning(partner_user.get("daily_count", 0), partner_limit)
        if w: await bot.send_message(partner_id, w, parse_mode="Markdown")


async def handle_find_action(message, user_id: int, target_gender: str = None, target_location: bool = False):
    """Logika saat user klik/ketik Find"""
    user = await check_user_status(message, user_id=user_id)
    if not user: return
    
    if not await check_limit(user, message):
        return
        
    if not user.get("registered") or not user.get("province"):
        await message.answer("Daftar dulu ya. Ketik /start")
        return
        
    if match.has_partner(user_id):
        await message.answer("Kamu masih dalam sesi chat. Ketik /stop dulu.")
        return
        
    if match.is_in_queue(user_id):
        await message.answer("Tunggu sebentar, masih mencari... ⏳")
        return
        
    is_premium = user.get("is_premium") or utils.get_user_limit(user) == config.PREMIUM_CHAT_LIMIT
    
    if (target_gender or target_location) and not is_premium:
        await message.answer("Ups! Sayangnya filter kriteria spesifik (gender/kota) hanyalah fitur *VIP/Premium*.\nKetik /upgrade untuk berlangganan.", parse_mode="Markdown")
        return
        
    msg_text = utils.format_searching_message(is_premium)
    await message.answer(msg_text, reply_markup=utils.waiting_keyboard())
    
    # Tarik instance bot jika dibutuhkan dari message dict
    bot = message.bot or message.message.bot if hasattr(message, "message") else message._bot
    if bot:
        await try_matchmaking(user_id, bot, target_gender, target_location)


async def handle_stop_action(message, user_id: int):
    """Logika saat user klik/ketik Stop"""
    # Cancel dari antrean
    if match.is_in_queue(user_id):
        match.remove_from_queue(user_id)
        await message.answer("Pencarian dibatalkan.", reply_markup=utils.main_keyboard())
        return
        
    # Akhiri sesi chat jika ada
    partner_id = match.end_session(user_id)
    if partner_id:
        fb_msg = "😢 Teman ngobrolmu sudah pergi...\nApakah semuanya baik-baik saja?"
        
        await message.answer(
            fb_msg, 
            reply_markup=utils.feedback_keyboard(partner_id)
        )
        
        bot = message.bot or message.message.bot if hasattr(message, "message") else getattr(message, "bot", None)
        if bot:
            try:
                await bot.send_message(
                    partner_id, 
                    fb_msg, 
                    reply_markup=utils.feedback_keyboard(user_id)
                )
            except Exception:
                pass
    else:
        await message.answer("Kamu tidak sedang ngobrol dengan siapa pun.", reply_markup=utils.main_keyboard())


async def handle_next_action(message, user_id: int):
    """Logika saat user klik/ketik Next"""
    await handle_stop_action(message, user_id)
    await handle_find_action(message, user_id)

