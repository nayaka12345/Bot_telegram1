# ============================================================
# matching.py - Sistem matching & manajemen chat di RAM
# PRINSIP: Semua operasi pairing & relay dilakukan di RAM
# Firebase hanya untuk penyimpanan permanen
# ============================================================

import random
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ─── STRUKTUR DATA UTAMA (IN-MEMORY) ─────────────────────────
# waiting_queue: list user yang sedang menunggu partner
# Setiap entry adalah dict: {user_id, purpose, gender, is_premium}
waiting_queue: list[dict] = []

# partner_map: mapping user_id → partner_id (dua arah)
# contoh: {111: 222, 222: 111}
partner_map: dict[int, int] = {}

# active_users: cache data user di RAM untuk performa
# Disimpan ke Firebase secara berkala (auto save)
# Format: {user_id: {gender, purpose, is_premium, daily_count, ...}}
active_users: dict[int, dict] = {}

# pending_dirty: user yang datanya berubah di RAM tapi belum di-save ke Firebase
# Digunakan oleh auto-save system
pending_dirty: set[int] = set()


# ─── MANAJEMEN ANTRIAN ────────────────────────────────────────

def add_to_queue(user_id: int, purpose: str, gender: str, province: str, city: str, is_premium: bool = False):
    """
    Tambahkan user ke antrian waiting.
    Pastikan tidak ada duplikat.
    """
    # Hapus dulu jika sudah ada
    remove_from_queue(user_id)
    
    waiting_queue.append({
        "user_id": user_id,
        "purpose": purpose,
        "gender": gender,
        "province": province,
        "city": city,
        "is_premium": is_premium,
    })
    logger.debug(f"🔍 User {user_id} masuk antrian. Total: {len(waiting_queue)}")


def remove_from_queue(user_id: int) -> bool:
    """Hapus user dari antrian. Return True jika berhasil dihapus."""
    global waiting_queue
    before = len(waiting_queue)
    waiting_queue = [u for u in waiting_queue if u["user_id"] != user_id]
    removed = len(waiting_queue) < before
    if removed:
        logger.debug(f"🗑️ User {user_id} dihapus dari antrian.")
    return removed


def is_in_queue(user_id: int) -> bool:
    """Cek apakah user sedang dalam antrian."""
    return any(u["user_id"] == user_id for u in waiting_queue)


def get_queue_position(user_id: int) -> int:
    """Dapatkan posisi user dalam antrian (1-indexed). Return -1 jika tidak ada."""
    for i, u in enumerate(waiting_queue):
        if u["user_id"] == user_id:
            return i + 1
    return -1


# ─── MATCHING ENGINE ──────────────────────────────────────────

def find_match(seeker: dict) -> Optional[dict]:
    """
    Cari partner terbaik untuk user tertentu.
    
    Prioritas matching:
    1. Same purpose + gender preference (premium)
    2. Same purpose
    3. Fallback random (siapapun yang menunggu)
    
    Return dict user partner, atau None jika tidak ada.
    """
    candidates = [u for u in waiting_queue if u["user_id"] != seeker["user_id"]]
    
    if not candidates:
        return None
    
    # ── Prioritas 1: Same purpose, filter lokasi jika premium ──
    same_purpose = [u for u in candidates if u["purpose"] == seeker["purpose"]]
    
    if same_purpose:
        # Premium user diprioritaskan mendapat lokasi yang sama
        if seeker.get("is_premium"):
            # 1. Cari yang kotanya sama persis
            same_city = [u for u in same_purpose if u.get("city") == seeker.get("city")]
            if same_city:
                return random.choice(same_city)
                
            # 2. Cari yang provinsinya sama
            same_prov = [u for u in same_purpose if u.get("province") == seeker.get("province")]
            if same_prov:
                return random.choice(same_prov)
                
            # 3. Fallback ke same_purpose biasa jika tidak ada yang se-lokasi
            pass
        return random.choice(same_purpose)
    
    # ── Prioritas 2: Fallback random ──────────────────────────
    logger.debug(f"⚡ Fallback random match untuk user {seeker['user_id']}")
    return random.choice(candidates)


def create_partnership(user_a: int, user_b: int):
    """
    Buat pasangan chat antara dua user.
    Hapus keduanya dari antrian.
    """
    partner_map[user_a] = user_b
    partner_map[user_b] = user_a
    remove_from_queue(user_a)
    remove_from_queue(user_b)
    logger.info(f"💬 Match berhasil: {user_a} ↔ {user_b}")


def get_partner(user_id: int) -> Optional[int]:
    """Dapatkan partner_id dari user_id. Return None jika tidak punya partner."""
    return partner_map.get(user_id)


def has_partner(user_id: int) -> bool:
    """Cek apakah user sedang dalam sesi chat aktif."""
    return user_id in partner_map


def end_session(user_id: int) -> Optional[int]:
    """
    Akhiri sesi chat. Hapus kedua user dari partner_map.
    Return partner_id yang tadi dipasangkan, atau None.
    """
    partner_id = partner_map.pop(user_id, None)
    if partner_id:
        partner_map.pop(partner_id, None)
        logger.info(f"🔚 Sesi diakhiri: {user_id} & {partner_id}")
    return partner_id


# ─── CACHE USER DI RAM ────────────────────────────────────────

def cache_user(user_id: int, user_data: dict):
    """Simpan/update data user di cache RAM."""
    active_users[user_id] = user_data.copy()


def get_cached_user(user_id: int) -> Optional[dict]:
    """Ambil data user dari cache RAM."""
    return active_users.get(user_id)


def update_cached_user(user_id: int, updates: dict):
    """
    Update field tertentu di cache RAM.
    Tandai sebagai 'dirty' untuk auto-save.
    """
    if user_id not in active_users:
        active_users[user_id] = {}
    active_users[user_id].update(updates)
    pending_dirty.add(user_id)  # Tandai perlu di-save ke Firebase


def get_dirty_users() -> dict:
    """
    Ambil semua user yang perlu di-save ke Firebase.
    Return dict {user_id: data} dan bersihkan pending_dirty.
    """
    dirty_data = {}
    for user_id in list(pending_dirty):
        if user_id in active_users:
            dirty_data[user_id] = active_users[user_id].copy()
    pending_dirty.clear()
    return dirty_data


def increment_daily_count(user_id: int):
    """Tambah hitungan chat harian di RAM."""
    if user_id in active_users:
        active_users[user_id]["daily_count"] = active_users[user_id].get("daily_count", 0) + 1
        active_users[user_id]["chat_count"] = active_users[user_id].get("chat_count", 0) + 1
        pending_dirty.add(user_id)


def get_daily_count(user_id: int) -> int:
    """Ambil hitungan chat harian dari RAM."""
    user = active_users.get(user_id, {})
    return user.get("daily_count", 0)


# ─── STATISTIK ────────────────────────────────────────────────

def get_stats() -> dict:
    """Statistik singkat untuk monitoring."""
    return {
        "waiting": len(waiting_queue),
        "active_chats": len(partner_map) // 2,
        "cached_users": len(active_users),
        "dirty_users": len(pending_dirty),
    }
