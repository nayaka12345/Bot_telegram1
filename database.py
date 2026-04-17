# ============================================================
# database.py - Manajemen Firebase Firestore
# Semua operasi baca/tulis ke Firebase ada di sini
# Prinsip: Minimasi read/write → gunakan cache RAM
# ============================================================

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, date
import asyncio
import logging
from config import FIREBASE_CRED_PATH, FIREBASE_COLLECTION
APPROVALS_COLLECTION = "approvals"

logger = logging.getLogger(__name__)

import os
import json

# ─── INISIALISASI FIREBASE ───────────────────────────────────
_db = None

def init_firebase():
    """Inisialisasi koneksi Firebase. Panggil sekali saat bot start."""
    global _db
    try:
        firebase_key_env = os.getenv("FIREBASE_KEY")
        if firebase_key_env:
            logger.info("Membaca Firebase Service Account dari Environment Variable (FIREBASE_KEY)...")
            firebase_key_dict = json.loads(firebase_key_env)
            cred = credentials.Certificate(firebase_key_dict)
        else:
            logger.info("Membaca Firebase Service Account dari file config (serviceAccountKey.json)...")
            cred = credentials.Certificate(FIREBASE_CRED_PATH)
            
        firebase_admin.initialize_app(cred)
        _db = firestore.client()
        logger.info("✅ Firebase berhasil diinisialisasi.")
    except Exception as e:
        logger.error(f"❌ Gagal inisialisasi Firebase: {e}")
        raise

def get_db():
    """Dapatkan instance Firestore client."""
    if _db is None:
        raise RuntimeError("Firebase belum diinisialisasi. Panggil init_firebase() lebih dulu.")
    return _db


# ─── STRUKTUR DATA USER DEFAULT ──────────────────────────────
def default_user_data(user_id: int, username: str = None) -> dict:
    """Buat struktur data user baru dengan nilai default."""
    return {
        "user_id": user_id,
        "username": username or "",
        "gender": None,           # "male" atau "female"
        "purpose": None,          # "curhat", "santai", "cari_teman"
        "province": None,
        "city": None,
        "chat_count": 0,          # Total chat sepanjang masa
        "daily_count": 0,         # Chat hari ini (untuk limit)
        "reset_count": 0,         # Sudah berapa kali limit di-reset
        "last_reset_date": datetime.now().isoformat(),  # Waktu terakhir reset
        "is_premium": False,
        "banned": False,
        "report_count": 0,        # Jumlah kali di-report
        "registered": False,      # Sudah pilih gender & purpose?
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


# ─── OPERASI USER ─────────────────────────────────────────────

async def get_user(user_id: int) -> dict | None:
    """
    Ambil data user dari Firebase.
    Return None jika user belum ada.
    """
    try:
        db = get_db()
        doc = db.collection(FIREBASE_COLLECTION).document(str(user_id)).get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        logger.error(f"❌ Gagal get_user({user_id}): {e}")
        return None


async def create_user(user_id: int, username: str = None) -> dict:
    """
    Buat dokumen user baru di Firebase.
    Return data user yang baru dibuat.
    """
    try:
        db = get_db()
        data = default_user_data(user_id, username)
        db.collection(FIREBASE_COLLECTION).document(str(user_id)).set(data)
        logger.info(f"✅ User baru dibuat: {user_id}")
        return data
    except Exception as e:
        logger.error(f"❌ Gagal create_user({user_id}): {e}")
        raise


async def update_user(user_id: int, data: dict) -> bool:
    """
    Update field tertentu dari data user di Firebase.
    Hanya field yang dikirim yang akan diupdate (merge).
    """
    try:
        db = get_db()
        data["updated_at"] = datetime.now().isoformat()
        db.collection(FIREBASE_COLLECTION).document(str(user_id)).update(data)
        return True
    except Exception as e:
        logger.error(f"❌ Gagal update_user({user_id}): {e}")
        return False


async def get_or_create_user(user_id: int, username: str = None) -> dict:
    """
    Dapatkan data user, jika belum ada maka buat baru.
    Fungsi utama yang dipanggil saat user berinteraksi.
    """
    user = await get_user(user_id)
    if user is None:
        user = await create_user(user_id, username)
    return user


# ─── SISTEM REPORT & BAN ──────────────────────────────────────

async def increment_report(user_id: int) -> int:
    """
    Tambah laporan untuk user. Return jumlah report saat ini.
    """
    try:
        db = get_db()
        ref = db.collection(FIREBASE_COLLECTION).document(str(user_id))
        
        # Gunakan transaction untuk konsistensi data
        @firestore.transactional
        def update_in_transaction(transaction, ref):
            snapshot = ref.get(transaction=transaction)
            if snapshot.exists:
                current = snapshot.get("report_count") or 0
                new_count = current + 1
                transaction.update(ref, {"report_count": new_count})
                return new_count
            return 0

        transaction = db.transaction()
        return update_in_transaction(transaction, ref)
    except Exception as e:
        logger.error(f"❌ Gagal increment_report({user_id}): {e}")
        return 0


async def ban_user(user_id: int) -> bool:
    """Ban user berdasarkan user_id."""
    return await update_user(user_id, {"banned": True})


async def unban_user(user_id: int) -> bool:
    """Unban user berdasarkan user_id."""
    return await update_user(user_id, {"banned": False, "report_count": 0})


# ─── SISTEM PREMIUM ───────────────────────────────────────────

async def set_premium(user_id: int, status: bool = True) -> bool:
    """Set status premium user. Dipanggil oleh admin."""
    return await update_user(user_id, {"is_premium": status})


# ─── BATCH SAVE (AUTO SAVE) ───────────────────────────────────

async def batch_save_users(users_data: dict) -> bool:
    """
    Simpan data banyak user sekaligus ke Firebase (batch write).
    Lebih efisien daripada update satu-satu.
    users_data = {user_id: {...data...}, ...}
    """
    try:
        db = get_db()
        batch = db.batch()
        
        for user_id, data in users_data.items():
            ref = db.collection(FIREBASE_COLLECTION).document(str(user_id))
            data["updated_at"] = datetime.now().isoformat()
            batch.update(ref, data)
        
        batch.commit()
        logger.info(f"✅ Batch save {len(users_data)} users berhasil.")
        return True
    except Exception as e:
        logger.error(f"❌ Gagal batch_save_users: {e}")
        return False


# ─── RESET DAILY COUNT ────────────────────────────────────────

def should_reset_daily(last_reset_date: str) -> bool:
    """Cek apakah daily count perlu direset (karena cooldown 36 jam)."""
    try:
        from config import RESET_COOLDOWN_HOURS
        last_date = datetime.fromisoformat(last_reset_date)
        time_diff = datetime.now() - last_date
        return time_diff.total_seconds() >= (RESET_COOLDOWN_HOURS * 3600)
    except Exception:
        # Fallback for old records that used date format 'YYYY-MM-DD'
        return True


async def reset_daily_count(user_id: int) -> bool:
    """Reset daily_count, tambah reset_count, dan update tanggal reset."""
    try:
        db = get_db()
        doc = db.collection(FIREBASE_COLLECTION).document(str(user_id)).get()
        current_reset = 0
        if doc.exists:
            data = doc.to_dict()
            current_reset = data.get("reset_count", 0)
        
        return await update_user(user_id, {
            "daily_count": 0,
            "reset_count": current_reset + 1,
            "last_reset_date": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"❌ Gagal reset_daily_count({user_id}): {e}")
        return False

# ─── SISTEM APPROVAL PEMBAYARAN ──────────────────────────────────

async def add_payment_proof(user_id: int, file_id: str) -> bool:
    """Simpan ID gambar bukti transfer ke dalam antrean approval."""
    try:
        db = get_db()
        data = {
            "user_id": user_id,
            "file_id": file_id,
            "timestamp": datetime.now().isoformat()
        }
        db.collection(APPROVALS_COLLECTION).document(str(user_id)).set(data)
        logger.info(f"✅ Bukti pembayaran diterima dari user {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Gagal simpan bukti pembayaran ({user_id}): {e}")
        return False

async def get_pending_approvals(limit: int = 1) -> list[dict]:
    """Ambil daftar user yang menunggu approval pembayaran."""
    try:
        db = get_db()
        docs = db.collection(APPROVALS_COLLECTION).order_by("timestamp").limit(limit).stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        logger.error(f"❌ Gagal get pending approvals: {e}")
        return []

async def delete_payment_proof(user_id: int) -> bool:
    """Hapus data persetujuan dari queue (misal karena di-approve/reject)"""
    try:
        db = get_db()
        db.collection(APPROVALS_COLLECTION).document(str(user_id)).delete()
        return True
    except Exception as e:
        logger.error(f"❌ Gagal menghapus payment proof user ({user_id}): {e}")
        return False

async def get_all_users() -> list[dict]:
    """Ambil semua data user dari Firebase. Berguna untuk broadcast."""
    try:
        db = get_db()
        docs = db.collection(FIREBASE_COLLECTION).stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        logger.error(f"❌ Gagal get_all_users: {e}")
        return []
