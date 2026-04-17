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
import utils
from handlers import router
from utils import setup_logging
from datetime import datetime

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


async def auto_reminder_task(bot: Bot):
    """
    Background worker untuk mengirimkan pesan pengingat ke user pasif (enggak aktif >= 3 hari).
    Berjalan setiap 24 jam.
    """
    logger.info("🕒 Auto-reminder worker started.")
    await asyncio.sleep(60) # Beri jeda 1 menit setelah bot on sebelum ngecek
    while True:
        try:
            users = await db.get_all_users()
            now = datetime.now()
            count = 0
            
            for u in users:
                if u.get("banned") or u["user_id"] in config.ADMIN_IDS:
                    continue
                    
                updated_at_str = u.get("updated_at")
                if updated_at_str:
                    try:
                        updated_at = datetime.fromisoformat(updated_at_str)
                        days_inactive = (now - updated_at).days
                        
                        if days_inactive >= 3 and days_inactive < 7: # Ingatkan user yang tidak aktif 3-6 hari aja
                            await bot.send_message(
                                u["user_id"],
                                "Halo kak! Malam mingguan atau sendirian aja nih? Yuk mending nyari teman ngobrol di sini! 😁",
                                reply_markup=utils.main_keyboard()
                            )
                            count += 1
                            await asyncio.sleep(0.05) # Prevent Telegram Rate Limit
                    except Exception:
                        pass
            
            if count > 0:
                logger.info(f"🔔 Reminder berhasil dikirim ke {count} user pasif.")
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"❌ Error saat merun auto-reminder: {e}")
            
        await asyncio.sleep(86400) # Loop lagi besok (24 jam)


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


async def on_shutdown(bot: Bot, tasks: list[asyncio.Task]):
    """Fungsi yang dijalankan saat bot dimatikan."""
    logger.info("⚠️ Mematikan bot...")
    
    # Batalkan semua background task
    for t in tasks:
        t.cancel()
    
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
    bg_save = asyncio.create_task(auto_save_task())
    bg_remind = asyncio.create_task(auto_reminder_task(bot))
    bg_tasks = [bg_save, bg_remind]
    
    # Register lifecycle hooks
    dp.startup.register(on_startup)
    
    # Saat dimatikan, batalkan background task
    async def shutdown_wrapper(dispatcher: Dispatcher, bot: Bot):
        await on_shutdown(bot, bg_tasks)
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
