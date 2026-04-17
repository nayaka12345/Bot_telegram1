# ============================================================
# utils.py - Fungsi helper & utilitas umum
# Berisi: keyboard builder, level system, format pesan, dll.
# ============================================================

import random
import logging
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import LEVEL_THRESHOLDS, STARTER_MESSAGES, CURHAT_EMPATHY_MESSAGES, FREE_CHAT_LIMIT_NEW, FREE_CHAT_LIMIT_NORMAL, PREMIUM_CHAT_LIMIT, ADMIN_IDS, PROVINCES, CITIES

logger = logging.getLogger(__name__)


# ─── LEVEL SYSTEM ─────────────────────────────────────────────

def get_level(chat_count: int) -> str:
    """
    Tentukan level user berdasarkan total chat_count.
    Level: Newbie → Active → Pro
    """
    level = "Newbie"
    for lvl, threshold in sorted(LEVEL_THRESHOLDS.items(), key=lambda x: x[1]):
        if chat_count >= threshold:
            level = lvl
    return level


def get_level_badge(level: str) -> str:
    """Dapatkan emoji badge untuk setiap level."""
    badges = {
        "Newbie": "🌱",
        "Active": "🔥",
        "Pro": "⚡",
    }
    return badges.get(level, "🌱")


def get_level_progress(chat_count: int) -> str:
    """Format progress menuju level berikutnya."""
    levels = sorted(LEVEL_THRESHOLDS.items(), key=lambda x: x[1])
    
    for i, (level, threshold) in enumerate(levels):
        # Cari level berikutnya
        if i + 1 < len(levels):
            next_level, next_threshold = levels[i + 1]
            if chat_count < next_threshold:
                remaining = next_threshold - chat_count
                return f"Butuh {remaining} chat lagi untuk naik ke {next_level}"
    
    return "Level maksimal tercapai! 🏆"


# ─── KEYBOARD BUILDER ─────────────────────────────────────────

def main_keyboard() -> InlineKeyboardMarkup:
    """
    Keyboard utama dengan tombol aksi cepat.
    Muncul saat user belum dalam sesi chat.
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔍 Find Partner", callback_data="action_find"),
            InlineKeyboardButton(text="👑 Upgrade", callback_data="action_upgrade"),
        ],
        [
            InlineKeyboardButton(text="📊 Status Saya", callback_data="action_status"),
            InlineKeyboardButton(text="ℹ️ Bantuan", callback_data="action_help"),
        ],
    ])
    return keyboard


def chat_keyboard() -> InlineKeyboardMarkup:
    """
    Keyboard saat sedang dalam sesi chat aktif.
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏭ Next", callback_data="action_next"),
            InlineKeyboardButton(text="🛑 Stop", callback_data="action_stop"),
        ],
        [
            InlineKeyboardButton(text="🚨 Report", callback_data="action_report"),
        ],
    ])
    return keyboard


def gender_keyboard() -> InlineKeyboardMarkup:
    """Keyboard pilihan gender saat registrasi."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👦 Laki-laki", callback_data="gender_male"),
            InlineKeyboardButton(text="👧 Perempuan", callback_data="gender_female"),
        ],
    ])
    return keyboard


def purpose_keyboard() -> InlineKeyboardMarkup:
    """Keyboard pilihan tujuan chat saat registrasi."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💙 Curhat", callback_data="purpose_curhat")],
        [InlineKeyboardButton(text="😄 Santai", callback_data="purpose_santai")],
        [InlineKeyboardButton(text="🤝 Cari Teman", callback_data="purpose_cari_teman")],
    ])
    return keyboard


def province_keyboard() -> InlineKeyboardMarkup:
    """Keyboard pilihan provinsi."""
    inline_kb = []
    # Susun 2 kolom per baris jika mau, atau 1 kolom. Di sini 1 kolom untuk presisi.
    for prov in PROVINCES:
        # callback data max 64 chars, ini cukup
        inline_kb.append([InlineKeyboardButton(text=prov, callback_data=f"prov_{prov}")])
    
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)


def city_keyboard(province: str) -> InlineKeyboardMarkup:
    """Keyboard pilihan kota berdasarkan provinsi."""
    inline_kb = []
    cities_list = CITIES.get(province, ["Lainnya"])
    
    for city in cities_list:
        inline_kb.append([InlineKeyboardButton(text=city, callback_data=f"city_{city}")])
        
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)

def waiting_keyboard() -> InlineKeyboardMarkup:
    """Keyboard saat sedang menunggu partner."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Batalkan", callback_data="action_stop")],
    ])
    return keyboard


def vip_find_keyboard() -> InlineKeyboardMarkup:
    """
    Keyboard khusus user VIP/Premium saat memilih mode Find.
    Memberikan pilihan filter: random, gender, kota, atau keduanya.
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎲 Random", callback_data="vip_find_random"),
        ],
        [
            InlineKeyboardButton(text="👦 Cari Cowok", callback_data="vip_find_gender_male"),
            InlineKeyboardButton(text="👧 Cari Cewek", callback_data="vip_find_gender_female"),
        ],
        [
            InlineKeyboardButton(text="🏙️ Satu Kota", callback_data="vip_find_kota"),
        ],
        [
            InlineKeyboardButton(text="👦🏙️ Cowok Satu Kota", callback_data="vip_find_male_kota"),
            InlineKeyboardButton(text="👧🏙️ Cewek Satu Kota", callback_data="vip_find_female_kota"),
        ],
        [
            InlineKeyboardButton(text="❌ Batal", callback_data="action_stop"),
        ],
    ])
    return keyboard


def confirm_keyboard() -> InlineKeyboardMarkup:
    """Keyboard konfirmasi aksi (ya/tidak)."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ya", callback_data="confirm_yes"),
            InlineKeyboardButton(text="❌ Tidak", callback_data="confirm_no"),
        ],
    ])
    return keyboard

def approval_keyboard(target_user_id: int) -> InlineKeyboardMarkup:
    """Keyboard konfirmasi approval transfer (Admin)."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Terima", callback_data=f"apprv_yes_{target_user_id}"),
            InlineKeyboardButton(text="❌ Tolak", callback_data=f"apprv_no_{target_user_id}"),
        ],
    ])
    return keyboard


def post_register_keyboard() -> InlineKeyboardMarkup:
    """Pilihan ringkas pasca registrasi."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Mulai Cari Partner (/start)", callback_data="action_find"),
            InlineKeyboardButton(text="Berhenti (/stop)", callback_data="action_stop"),
        ],
    ])
    return keyboard


def feedback_keyboard(partner_id: int) -> InlineKeyboardMarkup:
    """Feedback keyboard setelah partner pergi."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="😭 Dia nakal", callback_data=f"feedback_nakal_{partner_id}")],
        [InlineKeyboardButton(text="😕 Kurang nyaman", callback_data=f"feedback_nyaman_{partner_id}")],
        [InlineKeyboardButton(text="😊 Aman kok", callback_data=f"feedback_aman_{partner_id}")],
    ])
    return keyboard


# ─── RANDOM CONTENT ───────────────────────────────────────────

def get_random_starter() -> str:
    """Ambil starter message acak untuk memulai obrolan."""
    return random.choice(STARTER_MESSAGES)


def get_empathy_message() -> str:
    """Ambil pesan empati acak untuk mode curhat."""
    return random.choice(CURHAT_EMPATHY_MESSAGES)


# ─── FORMAT PESAN ─────────────────────────────────────────────

def get_user_limit(user_data: dict) -> int:
    """Tentukan limit chat harian berdasarkan status user."""
    if user_data.get("user_id") in ADMIN_IDS:
        return PREMIUM_CHAT_LIMIT
    if user_data.get("is_premium"):
        return PREMIUM_CHAT_LIMIT
    
    reset_count = user_data.get("reset_count", 0)
    if reset_count < 2:
        return FREE_CHAT_LIMIT_NEW
    return FREE_CHAT_LIMIT_NORMAL

def format_profile(user_data: dict) -> str:
    """Format tampilan profil user."""
    user_id = user_data.get("user_id", "?")
    gender = user_data.get("gender", "?")
    purpose = user_data.get("purpose", "?")
    province = user_data.get("province", "Belum diatur")
    city = user_data.get("city", "Belum diatur")
    chat_count = user_data.get("chat_count", 0)
    daily_count = user_data.get("daily_count", 0)
    is_premium = user_data.get("is_premium", False)
    banned = user_data.get("banned", False)
    
    level = get_level(chat_count)
    badge = get_level_badge(level)
    progress = get_level_progress(chat_count)
    
    gender_display = {
        "male": "👦 Laki-laki",
        "female": "👧 Perempuan",
    }.get(gender, "❓")
    
    purpose_display = {
        "curhat": "💙 Curhat",
        "santai": "😄 Santai",
        "cari_teman": "🤝 Cari Teman",
    }.get(purpose, "❓")
    
    user_limit = get_user_limit(user_data)
    if user_limit == PREMIUM_CHAT_LIMIT:
        status_line = "👑 *PREMIUM* (Bebas Limit)" if user_id not in ADMIN_IDS else "🛡️ *ADMIN* (Bebas Limit)"
    else:
        status_line = f"🆓 Free ({daily_count}/{user_limit} hari ini)"
    ban_line = "\n⛔ *AKUN KAMU DIBANNED*" if banned else ""
    
    return (
        f"👤 *PROFIL KAMU*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: `{user_id}`\n"
        f"⚧ Gender: {gender_display}\n"
        f"{badge} Level: *{level}*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💰 Status: {status_line}"
        f"{ban_line}"
    )


def format_match_notification(purpose: str) -> str:
    """Format notifikasi saat partner ditemukan."""
    purpose_display = {
        "curhat": "💙 Curhat",
        "santai": "😄 Santai",
        "cari_teman": "🤝 Cari Teman",
    }.get(purpose, "Chat")
    
    starter = get_random_starter()
    
    return (
        f"🎉 Kamu terhubung dengan seseorang!\n\n"
        f"💡 Tips:\n"
        f"- Sapa dulu biar ga awkward 😄\n"
        f"- Jaga sopan ya\n\n"
        f"Mulai ngobrol sekarang 👇"
    )

def format_searching_message(is_premium: bool, target_gender: str = None, target_location: bool = False) -> str:
    """Format pesan saat sedang mencari partner."""
    if not is_premium:
        return "🔍 Mencari teman ngobrol..."
    
    # Buat deskripsi filter yang aktif
    filters = []
    if target_gender == "male":
        filters.append("👦 Cowok")
    elif target_gender == "female":
        filters.append("👧 Cewek")
    if target_location:
        filters.append("🏙️ Satu Kota")
    
    if filters:
        filter_text = " + ".join(filters)
        return f"🔍 Mencari teman ngobrol...\n✨ Filter aktif: {filter_text} (Premium)"
    
    return "🔍 Mencari teman ngobrol... (Premium)"


def format_limit_warning(daily_count: int, limit: int) -> str:
    """Format peringatan saat mendekati/mencapai limit."""
    remaining = limit - daily_count
    if remaining <= 0:
        return (
            f"⚠️ *Limit harian tercapai!*\n"
            f"Kamu sudah menggunakan {limit} chat hari ini.\n\n"
            f"Upgrade ke *Premium* untuk chat unlimited!\n"
            f"Ketik /upgrade untuk info lebih lanjut."
        )
    elif remaining <= 2:
        return f"⚠️ Sisa {remaining} chat lagi hari ini. /upgrade untuk unlimited!"
    return ""


def format_stats(stats: dict) -> str:
    """Format statistik server untuk admin."""
    return (
        f"📊 *STATISTIK SERVER*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⏳ Menunggu partner: {stats.get('waiting', 0)}\n"
        f"💬 Chat aktif: {stats.get('active_chats', 0)}\n"
        f"👥 User di cache: {stats.get('cached_users', 0)}\n"
        f"💾 Antri di-save: {stats.get('dirty_users', 0)}"
    )


# ─── VALIDASI ─────────────────────────────────────────────────

def is_valid_gender(gender: str) -> bool:
    """Validasi nilai gender."""
    return gender in ("male", "female")


def is_valid_purpose(purpose: str) -> bool:
    """Validasi nilai tujuan chat."""
    return purpose in ("curhat", "santai", "cari_teman")


def sanitize_message(text: str) -> str:
    """
    Bersihkan pesan dari karakter berbahaya.
    Minimal implementation — bisa diperluas jika perlu.
    """
    if not text:
        return ""
    # Hapus karakter yang tidak diperlukan
    return text.strip()[:4096]  # Batas pesan Telegram


# ─── LOGGING HELPER ──────────────────────────────────────────

def setup_logging():
    """Setup konfigurasi logging untuk seluruh aplikasi."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("bot.log", encoding="utf-8"),
        ]
    )
    # Kurangi noise dari library
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("firebase_admin").setLevel(logging.WARNING)
