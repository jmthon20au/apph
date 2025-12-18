import sqlite3
import os
import logging
from datetime import datetime, time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters, Defaults

# إعداد السجلات
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- الإعدادات الأساسية ---
TOKEN = "8410743999:AAH7_oW6bzEGFXz10Lcte0QiHzmwEH_S-uk"
OWNER_ID = 7769271031 
CHANNEL_ID = "@N_QQ_H"  # اليوزر الصحيح بالشارحات
DB_NAME = 'tasks_bot.db'

def db_query(query, params=(), commit=False):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(query, params)
    if commit:
        conn.commit()
        res = True
    else:
        res = cursor.fetchall()
    conn.close()
    return res

def init_db():
    db_query('''CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, user_id INTEGER, task TEXT, status TEXT, date TEXT, day_only TEXT)''', commit=True)
    db_query('''CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, user_id INTEGER, note TEXT, date TEXT, day_only TEXT)''', commit=True)
    db_query('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, accepted INTEGER, username TEXT, full_name TEXT)''', commit=True)
    db_query('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''', commit=True)
    db_query("INSERT OR IGNORE INTO settings (key, value) VALUES ('force_sub', 'on')", commit=True)

async def check_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == OWNER_ID: return True
    res = db_query("SELECT value FROM settings WHERE key='force_sub'")
    if res and res[0][0] == 'off': return True
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

async def auto_backup_job(context: ContextTypes.DEFAULT_TYPE):
    res = db_query("SELECT value FROM settings WHERE key='backup_group_id'")
    if res:
        try:
            with open(DB_NAME, 'rb') as f:
                await context.bot.send_document(chat_id=int(res[0][0]), document=f, caption=f"🛡 نسخة احتياطية\n⏰ {datetime.now().strftime('%I:%M %p')}")
        except Exception as e: logging.error(f"Backup Error: {e}")

async def daily_reset_job(context: ContextTypes.DEFAULT_TYPE):
    db_query("DELETE FROM tasks", commit=True)

def main_menu(user_id):
    keyboard = [
        [InlineKeyboardButton("➕ إضافة مهمة", callback_data='add_task'), InlineKeyboardButton("📝 إضافة ملاحظة", callback_data='add_note')],
        [InlineKeyboardButton("📋 مهامي", callback_data='list_tasks'), InlineKeyboardButton("📒 ملاحظات اليوم", callback_data='today_notes')],
        [InlineKeyboardButton("✏️ تعديل مهمة", callback_data='edit_task_list'), InlineKeyboardButton("📅 الأرشيف", callback_data='view_archive')],
        [InlineKeyboardButton("ℹ️ آلية عمل البوت", callback_data='how_it_works')]
    ]
    if user_id == OWNER_ID:
        keyboard.append([InlineKeyboardButton("⚙️ إعدادات المسؤول", callback_data='settings')])
    keyboard.append([InlineKeyboardButton("👨‍💻 المطور", url="https://t.me/I_QQ_Q")])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # هنا تم تعديل طريقة عرض اليوزر لضمان ظهور الشارحات
    if not await check_sub(update, context):
        safe_channel = CHANNEL_ID.replace("_", "\\_") # معالجة الشارحات برمجياً
        return await update.message.reply_text(f"⚠️ يجب عليك الاشتراك في القناة أولاً:\n{safe_channel}", 
            parse_mode='MarkdownV2',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("إضغط هنا للاشتراك", url=f"https://t.me/{CHANNEL_ID[1:]}")]]))

    res = db_query("SELECT accepted FROM users WHERE user_id=?", (user.id,))
    if not res:
        welcome_msg = (f"👋 أهلاً بك {user.first_name}\n\n📖 *آلية عمل البوت:*\n"
                       "• المهام يومية وتُحذف 12 ليلاً\.\n• الملاحظات دائمة وتُحفظ بالأرشيف\.\n"
                       "• البوت آمن ويقوم بنسخ بياناتك دورياً\.")
        return await update.message.reply_text(welcome_msg, parse_mode='MarkdownV2',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ نعم، أنا جاهز لاستعمال البوت", callback_data='accept_terms')]]))
    
    await update.message.reply_text(f"مرحباً بك مجدداً 🚀", reply_markup=main_menu(user.id))

# --- معالج الأزرار المطور ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; user_id = query.from_user.id; await query.answer()

    if query.data == 'accept_terms':
        db_query("INSERT OR REPLACE INTO users (user_id, accepted, username, full_name) VALUES (?, 1, ?, ?)", (user_id, query.from_user.username, query.from_user.full_name), commit=True)
        await context.bot.send_message(chat_id=OWNER_ID, text=f"🔔 مستخدم جديد: {query.from_user.full_name}")
        await query.edit_message_text("تم التفعيل بنجاح! إليك القائمة الرئيسية:", reply_markup=main_menu(user_id))

    elif query.data == 'settings' and user_id == OWNER_ID:
        status = db_query("SELECT value FROM settings WHERE key='force_sub'")[0][0]
        kb = [[InlineKeyboardButton(f"🚫 إيقاف الاشتراك" if status == 'on' else "✅ تشغيل الاشتراك", callback_data='toggle_sub')],
              [InlineKeyboardButton("🔄 استرجاع DB", callback_data='ask_db')],
              [InlineKeyboardButton("⚠️ تصفير شامل", callback_data='reset_all')],
              [InlineKeyboardButton("⬅️ رجوع", callback_data='back')]]
        await query.edit_message_text(f"⚙️ لوحة المسؤول | الاشتراك: {status}", reply_markup=InlineKeyboardMarkup(kb))

    elif query.data == 'toggle_sub' and user_id == OWNER_ID:
        current = db_query("SELECT value FROM settings WHERE key='force_sub'")[0][0]
        new_val = 'off' if current == 'on' else 'on'
        db_query("UPDATE settings SET value=? WHERE key='force_sub'", (new_val,), commit=True)
        await query.edit_message_text(f"✅ تم تحويل حالة الاشتراك إلى: {new_val}", reply_markup=main_menu(user_id))

    elif query.data == 'cancel_input':
        context.user_data['state'] = None
        await query.edit_message_text("❌ تم إلغاء العملية.", reply_markup=main_menu(user_id))

    elif query.data == 'list_tasks':
        await show_task_list(query, user_id)

    elif query.data.startswith('tg_'):
        tid = query.data.split('_')[1]
        db_query("UPDATE tasks SET status = CASE WHEN status='pending' THEN 'done' ELSE 'pending' END WHERE id=? AND user_id=?", (tid, user_id), commit=True)
        await show_task_list(query, user_id)

    elif query.data == 'today_notes':
        today = datetime.now().strftime("%Y-%m-%d")
        rows = db_query("SELECT note FROM notes WHERE user_id=? AND day_only=?", (user_id, today))
        msg = f"📒 ملاحظات اليوم:\n\n" + ("\n".join([f"📌 {r[0]}" for r in rows]) if rows else "لا يوجد.")
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data='back')]]))

    elif query.data == 'view_archive':
        days = db_query("SELECT DISTINCT day_only FROM tasks WHERE user_id=? UNION SELECT DISTINCT day_only FROM notes WHERE user_id=? ORDER BY day_only DESC", (user_id, user_id))
        if not days: return await query.edit_message_text("الأرشيف فارغ.", reply_markup=main_menu(user_id))
        kb = [[InlineKeyboardButton(f"🗓 {d[0]}", callback_data=f"arch_{d[0]}")] for d in days if d[0]]
        kb.append([InlineKeyboardButton("⬅️ رجوع", callback_data='back')])
        await query.edit_message_text("🗓 اختر التاريخ المطلوب:", reply_markup=InlineKeyboardMarkup(kb))

    elif query.data.startswith('arch_'):
        day = query.data.split('_')[1]
        t_rows = db_query("SELECT task, status FROM tasks WHERE user_id=? AND day_only=?", (user_id, day))
        n_rows = db_query("SELECT note FROM notes WHERE user_id=? AND day_only=?", (user_id, day))
        msg = f"📅 سجل يوم {day}:\n\n📋 المهام:\n" + ("\n".join([f"{'✅' if r[1]=='done' else '⏳'} {r[0]}" for r in t_rows]) if t_rows else "لا يوجد")
        msg += "\n\n📝 الملاحظات:\n" + ("\n".join([f"📌 {r[0]}" for r in n_rows]) if n_rows else "لا يوجد")
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع للأرشيف", callback_data='view_archive')]]))

    elif query.data == 'edit_task_list':
        rows = db_query("SELECT id, task FROM tasks WHERE user_id=?", (user_id,))
        if not rows: return await query.edit_message_text("لا توجد مهام لتعديلها.", reply_markup=main_menu(user_id))
        kb = [[InlineKeyboardButton(f"✏️ {r[1]}", callback_data=f"pedit_{r[0]}")] for r in rows]
        kb.append([InlineKeyboardButton("⬅️ رجوع", callback_data='back')])
        await query.edit_message_text("اختر المهمة لتعديلها:", reply_markup=InlineKeyboardMarkup(kb))

    elif query.data.startswith('pedit_'):
        context.user_data['state'] = 'editing_task'
        context.user_data['edit_id'] = query.data.split('_')[1]
        await query.message.reply_text("✏️ أرسل النص الجديد للمهمة:")

    elif query.data in ['add_task', 'add_note']:
        context.user_data['state'] = query.data
        await query.message.reply_text("✏️ أرسل النص الذي تريد حفظه:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data='cancel_input')]]))

    elif query.data == 'how_it_works':
        await query.edit_message_text("📖 آلية العمل: المهام يومية تُحذف عند منتصف الليل، الملاحظات دائمة والأرشيف يحفظ تاريخك بكل سهولة.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data='back')]]))

    elif query.data == 'back': await query.edit_message_text("القائمة الرئيسية للبوت:", reply_markup=main_menu(user_id))

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id; state = context.user_data.get('state')
    if not state or not update.message.text: return
    text, now = update.message.text, datetime.now()
    dt_full, dt_day = now.strftime("%Y-%m-%d %I:%M %p"), now.strftime("%Y-%m-%d")
    
    if state == 'editing_task':
        db_query("UPDATE tasks SET task=? WHERE id=? AND user_id=?", (text, context.user_data.get('edit_id'), user_id), commit=True)
    elif state == 'add_task':
        db_query("INSERT INTO tasks (user_id, task, status, date, day_only) VALUES (?, ?, 'pending', ?, ?)", (user_id, text, dt_full, dt_day), commit=True)
    elif state == 'add_note':
        db_query("INSERT INTO notes (user_id, note, date, day_only) VALUES (?, ?, ?, ?)", (user_id, text, dt_full, dt_day), commit=True)

    context.user_data['state'] = None
    await update.message.reply_text("✅ تم تنفيذ العملية بنجاح.", reply_markup=main_menu(user_id))

async def show_task_list(query, user_id):
    rows = db_query("SELECT id, task, status FROM tasks WHERE user_id=?", (user_id,))
    if not rows: return await query.edit_message_text("📋 قائمتك حالياً فارغة.", reply_markup=main_menu(user_id))
    kb = [[InlineKeyboardButton(f"{'✅' if r[2]=='done' else '⏳'} {r[1]}", callback_data=f"tg_{r[0]}")] for r in rows]
    kb.append([InlineKeyboardButton("⬅️ رجوع", callback_data='back')])
    await query.edit_message_text("📋 قائمة مهامك الحالية:", reply_markup=InlineKeyboardMarkup(kb))

async def set_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == OWNER_ID:
        db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('backup_group_id', ?)", (str(update.message.chat_id),), commit=True)
        await update.message.reply_text("✅ تم ربط هذا الكروب بنظام النسخ الاحتياطي.")

if __name__ == '__main__':
    init_db()
    # تم تعديل الـ Defaults لضمان التوافق مع MarkdownV2
    app = Application.builder().token(TOKEN).build()
    
    app.job_queue.run_repeating(auto_backup_job, interval=60, first=10)
    app.job_queue.run_daily(daily_reset_job, time=time(0, 0, 0))

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("n", set_group))
    app.add_handler(CallbackQueryHandler(button_handler, block=False))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg, block=False))
    
    print("🚀 البوت انطلق الآن باليوزر الصحيح وبأقصى سرعة...")
    if __name__ == '__main__':
    application.run_polling()  # تأكد من وجود 4 مسافات قبل هذه الكلمة
