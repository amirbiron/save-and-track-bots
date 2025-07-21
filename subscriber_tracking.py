import logging
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
import http.server
import socketserver
import threading
from datetime import datetime, time, timedelta
import pymongo
import re
from bson.objectid import ObjectId

# --- הגדרות בסיסיות ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- קבועים ומשתני סביבה ---
TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URI = os.environ.get("MONGO_URI")
PORT = int(os.environ.get("PORT", 8080))

# --- הגדרת מסד הנתונים ---
client = pymongo.MongoClient(MONGO_URI)
db = client.get_database("SubscriptionBotDB")
subscriptions_collection = db.get_collection("subscriptions")
users_collection = db.get_collection("users")

# --- הגדרת שלבים לשיחה (Conversation) ---
NAME, DAY, COST, CURRENCY = range(4)

# --- שרת Keep-Alive ---
def run_keep_alive_server():
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        logger.info(f"Keep-alive server started on port {PORT}")
        httpd.serve_forever()

# --- פונקציית עזר לשמירת משתמש ---
async def ensure_user_in_db(update: Update):
    """בודקת אם המשתמש קיים ב-DB ומוסיפה אותו אם לא."""
    user = update.effective_user
    if not user:
        return

    user_info = {
        "chat_id": user.id,
        "first_name": user.first_name,
        "username": user.username,
    }
    # $setOnInsert יקבע את התאריך רק כשהמשתמש נוצר לראשונה
    users_collection.update_one(
        {"chat_id": user.id},
        {"$set": user_info, "$setOnInsert": {"first_seen": datetime.now()}},
        upsert=True
    )

# --- פונקציות תפריטים ---
def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("➕ הוספת מנוי חדש", callback_data="add_sub_start")],
        [InlineKeyboardButton("📋 הצגת המנויים שלי", callback_data="my_subs")],
        [InlineKeyboardButton("➖ מחיקת מנוי", callback_data="delete_sub_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

# --- פונקציות הבוט ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user_in_db(update) # בדיקת משתמש
    await update.message.reply_text(
        "שלום! אני בוט שיעזור לך לעקוב אחר המנויים החודשיים שלך.\n"
        "אני אשלח לך תזכורת 4 ימים לפני כל חיוב.\n\n"
        "השתמש בתפריט הכפתורים כדי להתחיל:",
        reply_markup=get_main_menu()
    )

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await ensure_user_in_db(update) # בדיקת משתמש
    await query.answer()
    await query.edit_message_text("תפריט ראשי:", reply_markup=get_main_menu())

async def add_sub_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await ensure_user_in_db(update) # בדיקת משתמש
    await query.answer()
    await query.edit_message_text("בוא נוסיף מנוי חדש. מה שם השירות? (למשל, ChatGPT)")
    return NAME

async def received_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text
    await update.message.reply_text("מצוין. באיזה יום בחודש מתבצע החיוב? (מספר בין 1 ל-31)")
    return DAY

async def received_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        day = int(update.message.text)
        if not 1 <= day <= 31: raise ValueError()
        context.user_data['day'] = day
        await update.message.reply_text("מעולה. מה העלות החודשית?")
        return COST
    except ValueError:
        await update.message.reply_text("זה לא נראה כמו יום תקין בחודש. אנא שלח מספר בין 1 ל-31.")
        return DAY

async def received_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        cost_text = re.sub(r'[^\d.]', '', update.message.text)
        cost = float(cost_text)
        context.user_data['cost'] = cost

        keyboard = [[
            InlineKeyboardButton("₪ ILS", callback_data="currency_ILS"),
            InlineKeyboardButton("$ USD", callback_data="currency_USD"),
            InlineKeyboardButton("€ EUR", callback_data="currency_EUR"),
        ]]
        await update.message.reply_text("באיזה מטבע החיוב?", reply_markup=InlineKeyboardMarkup(keyboard))
        return CURRENCY
    except (ValueError, TypeError):
        await update.message.reply_text("לא הצלחתי להבין את הסכום. אנא שלח רק מספר.")
        return COST

async def received_currency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    currency_symbol_map = {"ILS": "₪", "USD": "$", "EUR": "€"}
    currency_code = query.data.split('_')[1]
    
    subscription_data = {
        "chat_id": update.effective_chat.id,
        "service_name": context.user_data['name'],
        "billing_day": context.user_data['day'],
        "cost": context.user_data['cost'],
        "currency": currency_symbol_map.get(currency_code, currency_code)
    }
    subscriptions_collection.insert_one(subscription_data)
    
    await query.edit_message_text(f"המנוי '{context.user_data['name']}' נוסף בהצלחה!")
    
    context.user_data.clear()
    await context.bot.send_message(chat_id=update.effective_chat.id, text="תפריט ראשי:", reply_markup=get_main_menu())
    return ConversationHandler.END

async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("הפעולה בוטלה.", reply_markup=get_main_menu())
    else:
        await update.message.reply_text("הפעולה בוטלה.")
    context.user_data.clear()
    return ConversationHandler.END

async def my_subs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await ensure_user_in_db(update) # בדיקת משתמש
    await query.answer()
    user_subs = list(subscriptions_collection.find({"chat_id": update.effective_chat.id}))
    
    if not user_subs:
        await query.edit_message_text("לא רשומים לך מנויים.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 חזרה", callback_data="main_menu")]]))
        return

    message = "אלו המנויים הרשומים שלך:\n\n"
    total_costs = {}
    for sub in user_subs:
        currency = sub.get('currency', '')
        cost = sub.get('cost', 0)
        message += f"- **{sub['service_name']}** (חיוב ב-{sub['billing_day']} לחודש, עלות: {cost} {currency})\n"
        if currency not in total_costs: total_costs[currency] = 0
        total_costs[currency] += cost
        
    message += "\n**סה\"כ עלות חודשית:**"
    for currency, total in total_costs.items():
        message += f"\n- {total} {currency}"
        
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 חזרה", callback_data="main_menu")]]))

async def delete_sub_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await ensure_user_in_db(update) # בדיקת משתמש
    await query.answer()
    user_subs = list(subscriptions_collection.find({"chat_id": update.effective_chat.id}))
    if not user_subs:
        await query.edit_message_text("אין לך מנויים למחוק.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 חזרה", callback_data="main_menu")]]))
        return
        
    keyboard = [[InlineKeyboardButton(f"❌ {sub['service_name']}", callback_data=f"delete_{sub['_id']}")] for sub in user_subs]
    keyboard.append([InlineKeyboardButton("🔙 חזרה", callback_data="main_menu")])
    
    await query.edit_message_text("בחר מנוי למחיקה:", reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_sub_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sub_id_str = query.data.split('_')[1]
    
    subscriptions_collection.delete_one({"_id": ObjectId(sub_id_str)})
    
    await query.edit_message_text("המנוי נמחק.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 חזרה לתפריט הראשי", callback_data="main_menu")]]))

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)

async def daily_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Running daily subscription check...")
    reminder_date = datetime.now() + timedelta(days=4)
    reminder_day = reminder_date.day
    
    subs_due = subscriptions_collection.find({"billing_day": reminder_day})
    
    for sub in subs_due:
        currency = sub.get('currency', '')
        cost = sub.get('cost', '')
        message = f"🔔 **תזכורת תשלום** 🔔\n\nבעוד 4 ימים, בתאריך {reminder_date.strftime('%d/%m')}, יתבצע חיוב עבור המנוי שלך ל-**{sub['service_name']}** בסך **{cost} {currency}**."
        try:
            await context.bot.send_message(chat_id=sub['chat_id'], text=message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to send reminder to {sub['chat_id']}: {e}")

def main() -> None:
    if not TOKEN or not MONGO_URI:
        logger.fatal("FATAL: BOT_TOKEN or MONGO_URI environment variables are missing!")
        return

    keep_alive_thread = threading.Thread(target=run_keep_alive_server)
    keep_alive_thread.daemon = True
    keep_alive_thread.start()

    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_sub_start, pattern="^add_sub_start$")],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_name)],
            DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_day)],
            COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_cost)],
            CURRENCY: [CallbackQueryHandler(received_currency, pattern="^currency_")],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
        conversation_timeout=300
    )
    
    application.add_error_handler(error_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(my_subs_callback, pattern="^my_subs$"))
    application.add_handler(CallbackQueryHandler(delete_sub_menu_callback, pattern="^delete_sub_menu$"))
    application.add_handler(CallbackQueryHandler(delete_sub_confirm_callback, pattern="^delete_"))
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"))

    application.job_queue.run_daily(daily_check, time=time(hour=9, minute=0))
    
    logger.info("Bot starting with Polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
