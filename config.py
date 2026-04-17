# ============================================================
# config.py - Konfigurasi utama bot
# Ganti nilai di bawah dengan data kamu sendiri
# ============================================================

import os

# Memuat file .env jika ada (gunakan python-dotenv jika di-install)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─── TOKEN BOT ──────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "ISI_TOKEN_KAMU_DISINI_JIKA_TANPA_ENV")

# ─── ADMIN ──────────────────────────────────────────────────
# Daftar user_id admin (bisa lebih dari satu)
ADMIN_IDS = [5929852318]  # Ganti dengan Telegram user_id kamu

# ─── LIMIT CHAT ─────────────────────────────────────────────
FREE_CHAT_LIMIT_NEW = 10    # Limit untuk pendaftar baru
FREE_CHAT_LIMIT_NORMAL = 7  # Limit jika sudah 2x reset
PREMIUM_CHAT_LIMIT = 9999   # Unlimited untuk premium
RESET_COOLDOWN_HOURS = 36   # Cooldown sebelum limit reset (1.5 hari)

# ─── LEVEL SYSTEM ───────────────────────────────────────────
LEVEL_THRESHOLDS = {
    "Newbie": 0,
    "Active": 20,
    "Pro": 50,
}

# ─── LOKASI ─────────────────────────────────────────────────
PROVINCES = ["DKI Jakarta", "Jawa Barat", "Jawa Tengah", "Jawa Timur", "Lainnya"]
CITIES = {
    "DKI Jakarta": ["Jakarta Pusat", "Jakarta Selatan", "Jakarta Barat", "Jakarta Timur", "Jakarta Utara"],
    "Jawa Barat": ["Bekasi", "Bandung", "Depok", "Bogor", "Lainnya"],
    "Jawa Tengah": ["Semarang", "Solo (Surakarta)", "Yogyakarta", "Magelang", "Lainnya"],
    "Jawa Timur": ["Surabaya", "Malang", "Sidoarjo", "Kediri", "Lainnya"],
}

# ─── AUTO SAVE INTERVAL ─────────────────────────────────────
AUTO_SAVE_INTERVAL = 300    # Simpan ke Firebase setiap 5 menit (detik)

# ─── REPORT SYSTEM ──────────────────────────────────────────
MAX_REPORTS_BEFORE_BAN = 5  # Jumlah report sebelum user di-ban

# ─── FIREBASE ───────────────────────────────────────────────
FIREBASE_CRED_PATH = "serviceAccountKey.json"
FIREBASE_COLLECTION = "users"

# ─── STARTER MESSAGES ───────────────────────────────────────
STARTER_MESSAGES = [
    "💬 Lagi sibuk apa akhir-akhir ini?",
    "🌙 Lebih suka malam atau pagi?",
    "🎵 Lagi dengerin lagu apa?",
    "☕ Kamu tim kopi atau teh?",
    "🎯 Ada target yang lagi kamu kejar sekarang?",
    "📚 Terakhir baca buku apa?",
    "🌍 Kalau bisa pergi ke mana aja, kamu mau ke mana?",
    "🍕 Makanan favorit kamu apa?",
    "😴 Tidur siang atau tidak sama sekali?",
    "🎮 Hobi kamu apa selain main HP?",
    "🌅 Hal yang paling kamu syukuri hari ini?",
    "💡 Mimpi terbesar kamu apa?",
]

# ─── PESAN EMPATI CURHAT MODE ───────────────────────────────
CURHAT_EMPATHY_MESSAGES = [
    "💙 Kamu tidak sendiri. Ada seseorang yang siap mendengarkan kamu...",
    "🤗 Terkadang berbagi cerita bisa meringankan beban. Yuk, cerita...",
    "💪 Setiap orang butuh tempat untuk curhat. Kamu sudah di tempat yang tepat!",
    "🌸 Apapun yang sedang kamu rasakan, itu valid. Ceritakan saja...",
]

# ─── INSTRUKSI UPGRADE PREMIUM ───────────────────────────────
UPGRADE_INSTRUCTIONS = """
👑 *UPGRADE KE PREMIUM*
🔥 _{fake_count} orang sudah upgrade ke VIP hari ini!_

Nikmati fitur eksklusif:
✅ Chat unlimited (tanpa batas harian)
✅ Pilih partner berdasarkan gender
✅ No ads
✅ Badge Premium ⭐

💰 *Harga:* Rp 60.000 / bulan

📱 *Cara Pembayaran:*
Menerima berbagai metode pembayaran via QRIS dan Transfer:

1️⃣ *E-Wallet (Dana/OVO/GoPay/LinkAja/ShopeePay):*
Scan/transfer ke nomor: 0895385776293 (a/n Admin)

2️⃣ *Transfer Bank:*
BCA: Lagi tidak tersedia (a/n Admin Bot)

3️⃣ *QRIS:*
(Minta barcode QRIS dari admin)

✨ *Cara konfirmasi:*
Setelah pencet tombol Upgrade ini, kamu **tinggal kirim/upload foto screenshot bukti pembayaran aja langsung ke obrolan bot ini.**

Admin akan memproses aktivasi secepatnya.
ℹ️ Setelah dikonfirmasi admin, bot akan otomatis mengirimkan notifikasi dan akunmu langsung berstatus Premium.
"""
