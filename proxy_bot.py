import sqlite3
import os
import logging
import requests
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

TOKEN = "8872841970:AAHmcScjJmLi5wsKkX4i93TEnbE4Zue-U-8"
ADMIN_ID = 1091526567

PROXY_PLANS = {
    "1": {"name": "ساعة واحدة", "cost": 8, "duration_hours": 1},
    "3": {"name": "3 ساعات", "cost": 20, "duration_hours": 3},
    "6": {"name": "6 ساعات", "cost": 35, "duration_hours": 6},
    "12": {"name": "12 ساعة", "cost": 60, "duration_hours": 12},
    "24": {"name": "يوم كامل", "cost": 100, "duration_hours": 24},
}

ADS_LINK = "https://stupendous-lebkuchen-69ee61.netlify.app"

PROXY_CHECK_INPUT = 1

def init_db():
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0, username TEXT, first_name TEXT, preferred_currency TEXT DEFAULT 'IQD', views_count INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS proxy_requests
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, plan_name TEXT, cost INTEGER, status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS free_proxies
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, port TEXT, user TEXT, password TEXT, used BOOLEAN DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def create_user(user_id, username, first_name):
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)", (user_id, username, first_name))
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def update_balance(user_id, amount):
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def set_preferred_currency(user_id, currency):
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("UPDATE users SET preferred_currency = ? WHERE user_id=?", (currency, user_id))
    conn.commit()
    conn.close()

def get_preferred_currency(user_id):
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("SELECT preferred_currency FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 'IQD'

def add_proxy_request(user_id, plan_name, cost):
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO proxy_requests (user_id, plan_name, cost) VALUES (?, ?, ?)", (user_id, plan_name, cost))
    conn.commit()
    conn.close()

def get_available_free_proxy():
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("SELECT id, ip, port, user, password FROM free_proxies WHERE used = 0 LIMIT 1")
    result = c.fetchone()
    conn.close()
    return result

def mark_proxy_as_used(proxy_id):
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("UPDATE free_proxies SET used = 1 WHERE id = ?", (proxy_id,))
    conn.commit()
    conn.close()

def add_free_proxy(ip, port, user, password):
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO free_proxies (ip, port, user, password) VALUES (?, ?, ?, ?)", (ip, port, user, password))
    conn.commit()
    conn.close()

def main_keyboard():
    keyboard = [
        [KeyboardButton("📡 طلب بروكسي"), KeyboardButton("👤 حسابي")],
        [KeyboardButton("💰 شراء رصيد"), KeyboardButton("🎁 بروكسي مجاني")],
        [KeyboardButton("💱 تغيير العملة"), KeyboardButton("📊 المزيد")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def more_keyboard():
    keyboard = [
        [KeyboardButton("📖 دليل الاستخدام"), KeyboardButton("🔍 فحص البروكسي")],
        [KeyboardButton("💬 تواصل مع الدعم"), KeyboardButton("🔙 رجوع")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    create_user(user.id, user.username, user.first_name)
    balance = get_balance(user.id)

    if context.args:
        arg = context.args[0]
        if arg == "rewarded":
            user_id = user.id
            proxy = get_available_free_proxy()
            if proxy:
                mark_proxy_as_used(proxy[0])
                await update.message.reply_text(
                    f"🎁 تهانينا! لقد حصلت على بروكسي مجاني لمدة ساعة.\n\n"
                    f"📡 بيانات البروكسي:\n"
                    f"IP: {proxy[1]}\n"
                    f"Port: {proxy[2]}\n"
                    f"User: {proxy[3]}\n"
                    f"Pass: {proxy[4]}\n\n"
                    f"⏳ صلاحية البروكسي: ساعة واحدة."
                )
            else:
                await update.message.reply_text("⚠️ عذراً، لا توجد بروكسيات متاحة حالياً. يرجى المحاولة لاحقاً.")
            return

    await update.message.reply_text(
        f"👋 مرحباً بك في بوت البروكسي!\n"
        f"💰 رصيدك: {balance} نقطة\n\n"
        f"اختر الخدمة من الأزرار أدناه:",
        reply_markup=main_keyboard()
    )

async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    balance = get_balance(user_id)
    currency = get_preferred_currency(user_id)
    usd_value = balance * 0.006
    if currency == 'IQD':
        display_amount = f"{usd_value * 1500:.0f} دينار عراقي"
    else:
        display_amount = f"${usd_value:.2f}"
    await update.message.reply_text(
        f"👤 حسابي:\n\n"
        f"💰 رصيدك: {balance} نقطة\n"
        f"≈ {display_amount}\n\n"
        f"🆔 معرفك: {user_id}"
    )

async def buy_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    create_user(user.id, user.username, user.first_name)
    currency = get_preferred_currency(user.id)

    if currency == 'IQD':
        min_amount = "1500 دينار عراقي = 100 نقطة"
        currency_name = "دينار عراقي"
    else:
        min_amount = "1 دولار أمريكي = 100 نقطة"
        currency_name = "دولار أمريكي"

    await update.message.reply_text(
        f"💳 طريقة شحن الرصيد\n\n"
        f"💰 العملة الحالية: {currency_name}\n"
        f"📌 الحد الأدنى للشحن: {min_amount}\n\n"
        f"🔢 قم بالتحويل إلى أحد الأرقام التالية:\n\n"
        f"Zain Cash ➡️ 9647811418147\n"
        f"superQi ➡️ 910137642518\n\n"
        f"📸 أرسل صورة الإيداع أو رقم العملية.\n"
        f"⏳ سيتم إضافة الرصيد يدوياً خلال 5-10 دقائق.\n\n"
        f"ملاحظة: سعر الصرف ثابت.\n"
        f"1 دولار أمريكي = 1500 دينار عراقي."
    )

async def request_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for key, plan in PROXY_PLANS.items():
        keyboard.append([InlineKeyboardButton(f"{plan['name']} - {plan['cost']} نقطة", callback_data=f"proxy_{key}")])
    keyboard.append([InlineKeyboardButton("🔙 إلغاء", callback_data="cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🕒 اختر المدة التي تريد البروكسي فيها:", reply_markup=reply_markup)

async def proxy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "cancel":
        await query.edit_message_text("❌ تم الإلغاء.", reply_markup=None)
        return

    plan_key = data.split("_")[1]
    plan = PROXY_PLANS[plan_key]

    balance = get_balance(user_id)
    if balance < plan['cost']:
        await query.edit_message_text(f"⚠️ رصيدك غير كافٍ! أنت بحاجة إلى {plan['cost']} نقطة.\nرصيدك الحالي: {balance} نقطة.")
        return

    update_balance(user_id, -plan['cost'])
    add_proxy_request(user_id, plan['name'], plan['cost'])

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📢 طلب بروكسي جديد!\n"
             f"المستخدم: {query.from_user.first_name} (ID: {user_id})\n"
             f"المدة: {plan['name']}\n"
             f"التكلفة: {plan['cost']} نقطة\n"
             f"الرصيد المتبقي: {get_balance(user_id)} نقطة"
    )

    await query.edit_message_text(
        f"✅ تم خصم {plan['cost']} نقطة.\n"
        f"🔄 جارٍ تجهيز بروكسي {plan['name']}...\n"
        f"⏳ سيتم إرسال البيانات خلال دقائق.",
        reply_markup=None
    )

async def free_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🎁 بروكسي مجاني مقابل مشاهدة إعلان:\n\n"
        f"👀 شاهد الفيديو لمدة 30 ثانية من خلال الرابط أدناه.\n"
        f"📌 بعد الانتهاء، سيتم إعادة توجيهك تلقائياً إلى البوت، وستحصل على بروكسي مجاني.\n\n"
        f"🔗 اضغط هنا لمشاهدة الفيديو:\n{ADS_LINK}"
    )

async def change_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    create_user(user.id, user.username, user.first_name)
    current = get_preferred_currency(user.id)
    keyboard = [
        [InlineKeyboardButton("🇮🇶 دينار عراقي", callback_data="cur_IQD")],
        [InlineKeyboardButton("🇺🇸 دولار أمريكي", callback_data="cur_USD")],
    ]
    await update.message.reply_text(
        f"💱 العملة الحالية: {current}\n\nاختر العملة التي تريد العرض بها:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def currency_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    create_user(user.id, user.username, user.first_name)
    currency = query.data.split("_")[1]
    set_preferred_currency(user.id, currency)
    await query.edit_message_text(f"✅ تم تغيير العملة إلى {currency} بنجاح.")

async def more_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 قائمة المزيد\n\n"
        f"اختر من الخيارات أدناه:",
        reply_markup=more_keyboard()
    )

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🔙 تم الرجوع إلى القائمة الرئيسية.",
        reply_markup=main_keyboard()
    )

async def guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📖 دليل استخدام البروكسي\n\n"
        f"1. ما هو البروكسي؟\n"
        f"البروكسي هو وسيط بين جهازك والإنترنت، يخفي عنوان IP الحقيقي ويظهر عنواناً آخر (مثلاً أمريكي). هذا يساعدك في تنفيذ العروض والحصول على أرباح أعلى.\n\n"
        f"2. كيف أستخدم البروكسي على هاتفي؟\n"
        f"• قم بتنزيل تطبيق يدعم البروكسي (مثل: Super proxy للأندرويد).\n"
        f"• أدخل بيانات البروكسي (IP, Port, User, Pass) في التطبيق.\n"
        f"• اختر نوع البروتوكول: SOCKS5 (الأفضل).\n"
        f"• شغّل البروكسي، ثم افتح تطبيق صفور.\n\n"
        f"3. الفرق بين SOCKS5 و HTTP:\n"
        f"• SOCKS5: يعمل مع جميع التطبيقات والألعاب. الأفضل للاستخدام العام.\n"
        f"• HTTP: يعمل فقط مع المتصفح. يستخدم مع العروض الحساسة مثل عروض الاستبيان وعروض المتصفح.\n\n"
        f"4. لماذا لا يعمل البروكسي؟\n"
        f"• تأكد من صحة البيانات (IP, Port, User, Pass).\n"
        f"• تأكد من عدم انتهاء صلاحية البروكسي.\n"
        f"• جرب بروتوكولاً آخر (SOCKS5 أو HTTP).\n"
        f"• إذا استمرت المشكلة، تواصل مع الدعم.",
        reply_markup=more_keyboard()
    )

async def proxy_check_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🔍 فحص البروكسي\n\n"
        f"أرسل بيانات البروكسي بالصيغة التالية:\n\n"
        f"IP:PORT:USER:PASS\n\n"
        f"مثال:\n"
        f"192.168.1.1:1080:user123:pass123\n\n"
        f"أو إذا كان البروكسي بدون اسم مستخدم وكلمة مرور:\n"
        f"IP:PORT\n\n"
        f"مثال:\n"
        f"192.168.1.1:1080\n\n"
        f"📌 اكتب /cancel للإلغاء.",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔙 رجوع")]], resize_keyboard=True)
    )
    return PROXY_CHECK_INPUT

async def proxy_check_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text == "🔙 رجوع" or text == "/cancel":
        await update.message.reply_text("❌ تم ��لإلغاء.", reply_markup=more_keyboard())
        return ConversationHandler.END

    await update.message.reply_text("⏳ جاري فحص البروكسي... قد يستغرق 10-15 ثانية.")

    try:
        parts = text.split(":")
        if len(parts) == 4:
            ip, port, user, password = parts
            auth = f"{user}:{password}@"
        elif len(parts) == 2:
            ip, port = parts
            auth = ""
        else:
            await update.message.reply_text("⚠️ صيغة غير صحيحة. استخدم: IP:PORT:USER:PASS أو IP:PORT")
            return PROXY_CHECK_INPUT

        protocols = [
            ("SOCKS5", f"socks5://{auth}{ip}:{port}"),
            ("SOCKS4", f"socks4://{auth}{ip}:{port}"),
            ("HTTP",   f"http://{auth}{ip}:{port}"),
        ]

        success = False
        new_ip = None
        country = "غير معروف"
        city = ""
        used_protocol = ""

        for proto_name, proxy_url in protocols:
            try:
                proxy_dict = {"http": proxy_url, "https": proxy_url}
                response = requests.get(
                    "https://api.ipify.org?format=json",
                    proxies=proxy_dict,
                    timeout=10
                )
                data = response.json()
                new_ip = data.get("ip", "غير معروف")
                used_protocol = proto_name

                try:
                    geo = requests.get(
                        f"http://ip-api.com/json/{new_ip}?fields=status,country,city",
                        timeout=10
                    ).json()
                    if geo.get("status") == "success":
                        country = geo.get("country", "غير معروف")
                        city = geo.get("city", "")
                except Exception as geo_err:
                    print(f"Geo error: {geo_err}")

                success = True
                break
            except Exception:
                continue

        if success:
            location_text = f"{country}"
            if city:
                location_text += f" - {city}"

            await update.message.reply_text(
                f"✅ البروكسي يعمل بنجاح!\n\n"
                f"🌐 عنوان IP الجديد: {new_ip}\n"
                f"📍 الدولة: {location_text}\n"
                f"🔌 البروتوكول: {used_protocol}",
                reply_markup=more_keyboard()
            )
        else:
            await update.message.reply_text(
                f"❌ البروكسي لا يعمل.\n\n"
                f"الأسباب المحتملة:\n"
                f"• البيانات غير صحيحة (IP أو Port).\n"
                f"• البروكسي منتهي الصلاحية.\n"
                f"• الخادم لا يستجيب.\n\n"
                f"حاول مرة أخرى أو تواصل مع الدعم.",
                reply_markup=more_keyboard()
            )

        return ConversationHandler.END

    except Exception as e:
        await update.message.reply_text(f"⚠️ حدث خطأ: {str(e)}", reply_markup=more_keyboard())
        return ConversationHandler.END

async def cancel_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ تم الإلغاء.", reply_markup=more_keyboard())
    return ConversationHandler.END

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"💬 تواصل مع الدعم\n\n"
        f"لأي استفسار أو مشكلة، تواصل معنا عبر بوت الدعم:\n\n"
        f"👉 @SafforSupportBot\n\n"
        f"⏰ وقت الاستجابة: خلال 24 ساعة.",
        reply_markup=more_keyboard()
    )

async def admin_add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⚠️ هذا الأمر للمدير فقط.")
        return
    try:
        args = context.args
        user_id = int(args[0])
        amount = int(args[1])
        update_balance(user_id, amount)
        await update.message.reply_text(f"✅ تم إضافة {amount} نقطة إلى حساب المستخدم {user_id}.")
    except:
        await update.message.reply_text("⚠️ الاستخدام: /addbalance <user_id> <amount>")

async def admin_add_free_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⚠️ هذا الأمر للمدير فقط.")
        return
    try:
        args = context.args
        ip = args[0]
        port = args[1]
        user = args[2]
        password = args[3]
        add_free_proxy(ip, port, user, password)
        await update.message.reply_text(f"✅ تم إضافة بروكسي مجاني: {ip}:{port}")
    except:
        await update.message.reply_text("⚠️ الاستخدام: /addfreeproxy <IP> <PORT> <USER> <PASS>")

async def admin_list_free_proxies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⚠️ هذا الأمر للمدير فقط.")
        return
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("SELECT id, ip, port, user, password, used FROM free_proxies")
    proxies = c.fetchall()
    conn.close()
    if not proxies:
        await update.message.reply_text("📭 لا توجد بروكسيات مجانية في القائمة.")
        return
    text = "📋 قائمة البروكسيات المجانية:\n\n"
    for p in proxies:
        status = "✅ متاح" if not p[5] else "❌ مستخدم"
        text += f"ID: {p[0]} | {p[1]}:{p[2]} | {p[3]}:{p[4]} | {status}\n"
    await update.message.reply_text(text)

async def admin_delete_free_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⚠️ هذا الأمر للمدير فقط.")
        return
    try:
        args = context.args
        proxy_id = int(args[0])
        conn = sqlite3.connect('proxy_bot.db')
        c = conn.cursor()
        c.execute("DELETE FROM free_proxies WHERE id = ?", (proxy_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ تم حذف البروكسي رقم {proxy_id}.")
    except:
        await update.message.reply_text("⚠️ الاستخدام: /delfreeproxy <id>")

async def admin_reset_used(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⚠️ هذا الأمر للمدير فقط.")
        return
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("UPDATE free_proxies SET used = 0")
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ تم إعادة تعيين جميع البروكسيات (متاحة من جديد).")

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    proxy_check_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔍 فحص البروكسي$"), proxy_check_start)],
        states={
            PROXY_CHECK_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, proxy_check_received),
                CommandHandler("cancel", cancel_check),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_check)],
    )
    app.add_handler(proxy_check_conv)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addbalance", admin_add_balance))
    app.add_handler(CommandHandler("addfreeproxy", admin_add_free_proxy))
    app.add_handler(CommandHandler("listfreeproxy", admin_list_free_proxies))
    app.add_handler(CommandHandler("delfreeproxy", admin_delete_free_proxy))
    app.add_handler(CommandHandler("resetused", admin_reset_used))

    app.add_handler(MessageHandler(filters.Regex("^📡 طلب بروكسي$"), request_proxy))
    app.add_handler(MessageHandler(filters.Regex("^👤 حسابي$"), my_account))
    app.add_handler(MessageHandler(filters.Regex("^💰 شراء رصيد$"), buy_credit))
    app.add_handler(MessageHandler(filters.Regex("^🎁 بروكسي مجاني$"), free_proxy))
    app.add_handler(MessageHandler(filters.Regex("^💱 تغيير العملة$"), change_currency))
    app.add_handler(MessageHandler(filters.Regex("^📊 المزيد$"), more_menu))

    app.add_handler(MessageHandler(filters.Regex("^📖 دليل الاستخدام$"), guide))
    app.add_handler(MessageHandler(filters.Regex("^💬 تواصل مع الدعم$"), support))
    app.add_handler(MessageHandler(filters.Regex("^🔙 رجوع$"), back_to_main))

    app.add_handler(CallbackQueryHandler(proxy_callback, pattern="^(proxy_|cancel)"))
    app.add_handler(CallbackQueryHandler(currency_callback, pattern="^cur_"))

    print("🤖 بوت البروكسي يعمل...")
    app.run_polling()

if __name__ == "__main__":
    main()
