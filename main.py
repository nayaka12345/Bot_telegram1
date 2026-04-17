# ============================================================
# main.py - Titik mulai aplikasi (Entry Point)
# Inisialisasi bot, looping utama, dan background task
# ============================================================

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import config
import database as db
import matching as match
from handlers import router
from utils import setup_logging

logger = logging.getLogger(__name__)

async def auto_save_task():
    """
    Background worker untuk menyimpan data RAM ke Firebase.
    Melakukan batch save agar hemat read/write operations.
    """
    logger.info("🕒 Auto-save worker started.")
    while True:
        await asyncio.sleep(config.AUTO_SAVE_INTERVAL)
        try:
            dirty_users = match.get_dirty_users()
            if dirty_users:
                logger.info(f"🔄 Auto-save berjalan: menemukan {len(dirty_users)} user berubah.")
                success = await db.batch_save_users(dirty_users)
                if not success:
                    # Kembalikan ke antrian jika gagal
                    for uid, data in dirty_users.items():
                        match.update_cached_user(uid, data)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"❌ Error saat auto-save: {e}")


async def on_startup(bot: Bot):
    """Fungsi yang dijalankan saat bot pertama kali nyala."""
    logger.info("🚀 Memulai bot Telegram Anonymous Chat...")
    
    # Inisialisasi Database
    try:
        db.init_firebase()
    except Exception as e:
        logger.critical(f"Gagal koneksi Firebase. Pastikan file serviceAccountKey.json ada. Error: {e}")
        # Bisa dinonaktifkan jika ingin lanjut error, atau biarkan crash
        
    logger.info("✅ Bot siap melayani pengguna!")


async def on_shutdown(bot: Bot, bg_task: asyncio.Task):
    """Fungsi yang dijalankan saat bot dimatikan."""
    logger.info("⚠️ Mematikan bot...")
    
    # Batalkan auto-save
    bg_task.cancel()
    
    # Simpan data terakhir sebelum mati
    dirty_users = match.get_dirty_users()
    if dirty_users:
        logger.info(f"💾 Menyimpan {len(dirty_users)} user tersisa ke Firebase sebelum keluar...")
        await db.batch_save_users(dirty_users)
        
    logger.info("🛑 Bot dimatikan secara aman.")


async def main():
    """Fungsi utama untuk set up bot dan dispatcher."""
    setup_logging()
    
    if config.BOT_TOKEN == "MASUKKAN_TOKEN_BOT_KAMU_DISINI":
        logger.error("❌ TOKEN BOT belum disetup!")
        print("\n\n1. Buka config.py")
        print("2. Ubah BOT_TOKEN dengan token dari @BotFather")
        print("3. Jalankan ulang bot.\n\n")
        return
        
    # Inisialisasi Bot dengan HTML/Markdown parse mode default
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()
    dp.include_router(router)
    
    # Jalankan background task
    bg_task = asyncio.create_task(auto_save_task())
    
    # Register lifecycle hooks
    dp.startup.register(on_startup)
    
    # Saat dimatikan, kita pakai shutdown hook khusus yang membawa parameter bg_task
    # Harus di-wrap manual karena parameter extra
    async def shutdown_wrapper(dispatcher: Dispatcher, bot: Bot):
        await on_shutdown(bot, bg_task)
    dp.shutdown.register(shutdown_wrapper)

    try:
        # Hapus webhook (jika ada) dan mulai polling
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        # Cek versi python >= 3.9
        asyncio.run(main())
    except KeyboardInterrupt:
        print("❌ Dibatalkan oleh pengguna (Ctrl+C)")
