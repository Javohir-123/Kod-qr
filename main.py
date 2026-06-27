#!/usr/bin/env python3
"""
🎵 QR Kod Boti
- 2 ta bepul QR, qolgani pullik
- Chek screenshot → adminga → summa kiritib tasdiqlash
- Admin: @Javoh_1hacker (5492502957)
"""

import logging
import sqlite3
import qrcode
import io
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ──────────────────────────────────────────
# SOZLAMALAR
# ──────────────────────────────────────────
BOT_TOKEN      = "8284600998:AAG7C1gVRRgUV16xhMlAJBwT9RPgBfJ6wWA"
ADMIN_ID       = 5492502957
ADMIN_USERNAME = "@Javoh_1hacker"
KARTA_RAQAMI   = "6262570040359129"
NARX_SOM       = 2000
BEPUL_LIMIT    = 2

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)


# ──────────────────────────────────────────
# MA'LUMOTLAR BAZASI
# ──────────────────────────────────────────
def db():
    conn = sqlite3.connect("bot.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY,
            username   TEXT,
            full_name  TEXT,
            balance    INTEGER DEFAULT 0,
            free_used  INTEGER DEFAULT 0,
            joined_at  TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS transactions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            amount     INTEGER,
            type       TEXT,
            note       TEXT,
            created_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS qr_requests (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            url   TEXT,
            is_free    INTEGER,
            created_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS pending_receipts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            photo_id   TEXT,
            amount     INTEGER DEFAULT 2000,
            status     TEXT DEFAULT 'pending',
            created_at TEXT
        )""")

def get_user(user_id):
    with db() as c:
        return c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()

def upsert_user(user):
    with db() as c:
        if not c.execute("SELECT id FROM users WHERE id=?", (user.id,)).fetchone():
            c.execute("""INSERT INTO users (id,username,full_name,balance,free_used,joined_at)
                         VALUES (?,?,?,0,0,?)""",
                      (user.id, user.username, user.full_name,
                       datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

def upsert_user_by_id(user_id):
    with db() as c:
        if not c.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone():
            c.execute("""INSERT INTO users (id,username,full_name,balance,free_used,joined_at)
                         VALUES (?,?,?,0,0,?)""",
                      (user_id, None, "Unknown",
                       datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

def add_balance(user_id, amount, note=""):
    with db() as c:
        c.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, user_id))
        c.execute("""INSERT INTO transactions (user_id,amount,type,note,created_at)
                     VALUES (?,?,?,?,?)""",
                  (user_id, amount, "credit", note,
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

def spend_balance(user_id, amount):
    with db() as c:
        c.execute("UPDATE users SET balance=balance-? WHERE id=?", (amount, user_id))
        c.execute("""INSERT INTO transactions (user_id,amount,type,note,created_at)
                     VALUES (?,?,?,?,?)""",
                  (user_id, amount, "debit", "QR yaratish",
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

def mark_free_used(user_id):
    with db() as c:
        c.execute("UPDATE users SET free_used=free_used+1 WHERE id=?", (user_id,))

def save_receipt(user_id, photo_id):
    with db() as c:
        c.execute("""INSERT INTO pending_receipts (user_id,photo_id,amount,status,created_at)
                     VALUES (?,?,0,'pending',?)""",
                  (user_id, photo_id,
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        return c.lastrowid

def get_receipt(receipt_id):
    with db() as c:
        return c.execute("SELECT * FROM pending_receipts WHERE id=?",
                         (receipt_id,)).fetchone()

def update_receipt_status(receipt_id, status):
    with db() as c:
        c.execute("UPDATE pending_receipts SET status=? WHERE id=?",
                  (status, receipt_id))

def get_stats():
    with db() as c:
        users     = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_sum = c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='credit'").fetchone()[0]
        qr_count  = c.execute("SELECT COUNT(*) FROM qr_requests").fetchone()[0]
        pending   = c.execute("SELECT COUNT(*) FROM pending_receipts WHERE status='pending'").fetchone()[0]
        return users, total_sum, qr_count, pending


# ──────────────────────────────────────────
# QR KOD YARATISH
# ──────────────────────────────────────────
def make_qr(data: str) -> io.BytesIO:
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# ──────────────────────────────────────────
# KLAVIATURALAR
# ──────────────────────────────────────────
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎵 QR Kod Yaratish", callback_data="create_qr")],
        [InlineKeyboardButton("💰 Balansim",        callback_data="balance"),
         InlineKeyboardButton("💳 Pul Kiritish",    callback_data="deposit")],
    ])

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Pul Berish",     callback_data="adm_give")],
        [InlineKeyboardButton("📨 Xabar Yuborish", callback_data="adm_msg")],
        [InlineKeyboardButton("📈 Statistika",     callback_data="adm_stats")],
        [InlineKeyboardButton("🏠 Asosiy Menyu",   callback_data="back_main")],
    ])

def receipt_keyboard(receipt_id, user_id):
    """Chek kelganda admin uchun tugmalar — summa kiritib tasdiqlash yoki rad etish."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Summa kiritib tasdiqlash",
                                 callback_data=f"asksum_{receipt_id}_{user_id}"),
        ],
        [
            InlineKeyboardButton("❌ Rad etish",
                                 callback_data=f"reject_{receipt_id}_{user_id}"),
        ]
    ])


# ──────────────────────────────────────────
# /start  /admin
# ──────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user)
    await update.message.reply_text(
        f"🎵 *Salom, {user.first_name}!*\n\n"
        "Bu bot istalgan havoladan QR kod yaratadi.\n"
        f"✅ *{BEPUL_LIMIT} ta QR kod — BEPUL!*\n"
        f"💵 Undan keyingi har biri — {NARX_SOM:,} so'm\n\n"
        "Quyidagi tugmalardan birini tanlang:",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Ruxsat yo'q.")
        return
    await update.message.reply_text(
        "👑 *Admin Paneliga xush kelibsiz!*",
        parse_mode="Markdown",
        reply_markup=admin_keyboard()
    )


# ──────────────────────────────────────────
# CALLBACK HANDLER
# ──────────────────────────────────────────
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    uid  = q.from_user.id
    data = q.data
    await q.answer()

    if data == "back_main":
        await q.edit_message_text("🏠 Asosiy Menyu:", reply_markup=main_keyboard())
        return

    if data == "balance":
        u = get_user(uid)
        await q.edit_message_text(
            f"💰 *Balansingiz:* {u['balance']:,} so'm\n"
            f"✅ *Bepul ishlatilgan:* {u['free_used']}/{BEPUL_LIMIT}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")
            ]])
        )
        return

    if data == "deposit":
        await q.edit_message_text(
            "💳 *Balansni to'ldirish:*\n\n"
            f"Karta raqami: `{KARTA_RAQAMI}`\n\n"
            f"🆔 Sizning ID: `{uid}`\n\n"
            "✅ To'lovdan so'ng *chek (screenshot)*ni shu yerga yuboring.\n"
            "Admin chekni ko'rib, summani kiritib tasdiqlaydi — balans *avtomatik* to'ldiriladi!\n\n"
            f"_Savol bo'lsa: {ADMIN_USERNAME}_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")
            ]])
        )
        ctx.user_data["waiting_receipt"] = True
        return

    if data == "create_qr":
        u = get_user(uid)
        free_left = BEPUL_LIMIT - u["free_used"]
        if free_left > 0:
            note = f"✅ Sizda *{free_left}* ta bepul QR qoldi."
        else:
            note = (f"💵 Bepul limitingiz tugadi.\n"
                    f"Balansingiz: *{u['balance']:,}* so'm\n"
                    f"Narx: *{NARX_SOM:,}* so'm")
        await q.edit_message_text(
            f"🔗 *QR Kod Yaratish*\n\n{note}\n\n"
            "Havolani (URL) yuboring:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Bekor qilish", callback_data="back_main")
            ]])
        )
        ctx.user_data["awaiting_qr_url"] = True
        return

    # ── Admin: summani so'rash
    if data.startswith("asksum_") and uid == ADMIN_ID:
        parts      = data.split("_")
        receipt_id = int(parts[1])
        target_id  = int(parts[2])
        ctx.user_data["adm_state"]      = "wait_confirm_sum"
        ctx.user_data["adm_receipt_id"] = receipt_id
        ctx.user_data["adm_target_id"]  = target_id
        await q.message.reply_text(
            f"💵 *{target_id}* uchun qancha so'm qo'shilsin?\n\n"
            "Faqat raqam kiriting (masalan: `4000`):",
            parse_mode="Markdown"
        )
        return

    # ── Admin: rad etish
    if data.startswith("reject_") and uid == ADMIN_ID:
        parts      = data.split("_")
        receipt_id = int(parts[1])
        target_id  = int(parts[2])
        receipt    = get_receipt(receipt_id)

        if receipt and receipt["status"] == "pending":
            update_receipt_status(receipt_id, "rejected")
            await q.edit_message_caption(
                caption=q.message.caption + "\n\n❌ *RAD ETILDI*",
                parse_mode="Markdown"
            )
            try:
                await ctx.bot.send_message(
                    chat_id=target_id,
                    text="❌ *To'lovingiz tasdiqlanmadi.*\n\n"
                         f"Qayta urinib ko'ring yoki {ADMIN_USERNAME} ga yozing.",
                    parse_mode="Markdown",
                    reply_markup=main_keyboard()
                )
            except Exception:
                pass
        else:
            await q.answer("Allaqachon ko'rib chiqilgan!", show_alert=True)
        return

    # ── Admin: statistika
    if data == "adm_give" and uid == ADMIN_ID:
        await q.edit_message_text("👤 Foydalanuvchi ID sini kiriting:")
        ctx.user_data["adm_state"] = "wait_give_id"
        return

    if data == "adm_msg" and uid == ADMIN_ID:
        await q.edit_message_text("👤 Xabar yuboriladigan foydalanuvchi ID:")
        ctx.user_data["adm_state"] = "wait_msg_id"
        return

    if data == "adm_stats" and uid == ADMIN_ID:
        users, total, qrs, pending = get_stats()
        await q.edit_message_text(
            "📈 *Bot Statistikasi:*\n\n"
            f"👥 A'zolar: *{users}* ta\n"
            f"💰 Jami kiritilgan: *{total:,}* so'm\n"
            f"🔗 Yaratilgan QR: *{qrs}* ta\n"
            f"⏳ Kutilayotgan cheklar: *{pending}* ta",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Admin Menyu", callback_data="adm_back")
            ]])
        )
        return

    if data == "adm_back" and uid == ADMIN_ID:
        await q.edit_message_text("👑 Admin Paneli:", reply_markup=admin_keyboard())


# ──────────────────────────────────────────
# XABAR HANDLER
# ──────────────────────────────────────────
async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user)
    uid  = user.id

    # ── Chek screenshot
    if ctx.user_data.get("waiting_receipt") and update.message.photo:
        photo      = update.message.photo[-1]
        receipt_id = save_receipt(uid, photo.file_id)

        caption = (
            f"💳 *Yangi to'lov cheki!*\n\n"
            f"👤 {user.full_name}\n"
            f"🆔 ID: `{uid}`\n"
            f"🔗 @{user.username or 'username yoq'}\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"⬇️ Summani kiritib tasdiqlang yoki rad eting."
        )
        await ctx.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo.file_id,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=receipt_keyboard(receipt_id, uid)
        )
        await update.message.reply_text(
            "✅ *Chekingiz adminga yuborildi!*\n\n"
            "Tez orada tekshirib, balans to'ldiriladi. ⏳",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
        ctx.user_data.pop("waiting_receipt", None)
        return

    # ── Admin: chek summasi kiritish
    if ctx.user_data.get("adm_state") == "wait_confirm_sum" and uid == ADMIN_ID:
        try:
            amount     = int(update.message.text.strip())
            receipt_id = ctx.user_data["adm_receipt_id"]
            target_id  = ctx.user_data["adm_target_id"]
            receipt    = get_receipt(receipt_id)

            if receipt and receipt["status"] == "pending":
                upsert_user_by_id(target_id)
                add_balance(target_id, amount, note=f"Chek #{receipt_id} tasdiqlandi")
                update_receipt_status(receipt_id, "confirmed")

                await update.message.reply_text(
                    f"✅ *{target_id}* ga *{amount:,}* so'm qo'shildi!",
                    parse_mode="Markdown",
                    reply_markup=admin_keyboard()
                )
                try:
                    await ctx.bot.send_message(
                        chat_id=target_id,
                        text=f"✅ *To'lovingiz tasdiqlandi!*\n\n"
                             f"💰 Balansingizga *{amount:,} so'm* qo'shildi!\n"
                             f"Yangi balans: *{get_user(target_id)['balance']:,}* so'm",
                        parse_mode="Markdown",
                        reply_markup=main_keyboard()
                    )
                except Exception:
                    pass
            else:
                await update.message.reply_text("⚠️ Bu chek allaqachon ko'rib chiqilgan.")

            ctx.user_data.pop("adm_state", None)
            ctx.user_data.pop("adm_receipt_id", None)
            ctx.user_data.pop("adm_target_id", None)
        except ValueError:
            await update.message.reply_text("⚠️ Faqat raqam kiriting! Masalan: 4000")
        return

    # ── QR URL
    if ctx.user_data.get("awaiting_qr_url"):
        url = update.message.text.strip() if update.message.text else ""
        if not url.startswith("http"):
            await update.message.reply_text(
                "⚠️ To'g'ri URL kiriting (http... bilan boshlansin)."
            )
            return

        u         = get_user(uid)
        free_left = BEPUL_LIMIT - u["free_used"]
        is_free   = free_left > 0

        if not is_free:
            if u["balance"] < NARX_SOM:
                await update.message.reply_text(
                    f"❌ *Balansingiz yetarli emas!*\n\n"
                    f"Balans: *{u['balance']:,}* so'm\n"
                    f"Narx: *{NARX_SOM:,}* so'm",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("💳 Pul Kiritish", callback_data="deposit")
                    ]])
                )
                ctx.user_data.pop("awaiting_qr_url", None)
                return
            spend_balance(uid, NARX_SOM)
        else:
            mark_free_used(uid)

        qr_buf = make_qr(url)
        with db() as c:
            c.execute("""INSERT INTO qr_requests (user_id,url,is_free,created_at)
                         VALUES (?,?,?,?)""",
                      (uid, url, int(is_free),
                       datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        u2    = get_user(uid)
        label = "🆓 Bepul" if is_free else f"💵 {NARX_SOM:,} so'm"
        await update.message.reply_photo(
            photo=qr_buf,
            caption=(
                f"✅ *QR Kod tayyor!* ({label})\n\n"
                f"🔗 {url}\n\n"
                f"💰 Balans: *{u2['balance']:,}* so'm\n"
                f"✅ Bepul qolgan: *{max(0, BEPUL_LIMIT - u2['free_used'])}* ta"
            ),
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
        ctx.user_data.pop("awaiting_qr_url", None)
        return

    # ── Admin: pul berish — ID
    if ctx.user_data.get("adm_state") == "wait_give_id" and uid == ADMIN_ID:
        try:
            ctx.user_data["adm_target_id"] = int(update.message.text.strip())
            ctx.user_data["adm_state"]     = "wait_give_sum"
            await update.message.reply_text("💵 Summani kiriting:")
        except ValueError:
            await update.message.reply_text("⚠️ Noto'g'ri ID.")
        return

    # ── Admin: pul berish — summa
    if ctx.user_data.get("adm_state") == "wait_give_sum" and uid == ADMIN_ID:
        try:
            amount    = int(update.message.text.strip())
            target_id = ctx.user_data["adm_target_id"]
            upsert_user_by_id(target_id)
            add_balance(target_id, amount, note="Admin qo'shdi")
            await update.message.reply_text(
                f"✅ *{target_id}* ga *{amount:,}* so'm qo'shildi!",
                parse_mode="Markdown",
                reply_markup=admin_keyboard()
            )
            try:
                await ctx.bot.send_message(
                    chat_id=target_id,
                    text=f"✅ *Balansingizga {amount:,} so'm qo'shildi!*",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            ctx.user_data.pop("adm_state", None)
            ctx.user_data.pop("adm_target_id", None)
        except ValueError:
            await update.message.reply_text("⚠️ Noto'g'ri summa.")
        return

    # ── Admin: xabar — ID
    if ctx.user_data.get("adm_state") == "wait_msg_id" and uid == ADMIN_ID:
        try:
            ctx.user_data["adm_target_id"] = int(update.message.text.strip())
            ctx.user_data["adm_state"]     = "wait_msg_text"
            await update.message.reply_text("✍️ Xabar matnini kiriting:")
        except ValueError:
            await update.message.reply_text("⚠️ Noto'g'ri ID.")
        return

    # ── Admin: xabar — matn
    if ctx.user_data.get("adm_state") == "wait_msg_text" and uid == ADMIN_ID:
        target_id = ctx.user_data["adm_target_id"]
        try:
            await ctx.bot.send_message(chat_id=target_id, text=update.message.text)
            await update.message.reply_text("✅ Xabar yuborildi!", reply_markup=admin_keyboard())
        except Exception as e:
            await update.message.reply_text(f"❌ Xatolik: {e}", reply_markup=admin_keyboard())
        ctx.user_data.pop("adm_state", None)
        ctx.user_data.pop("adm_target_id", None)
        return

    await update.message.reply_text("🏠 Asosiy menyu:", reply_markup=main_keyboard())


# ──────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_message))
    log.info("🤖 Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
