import sqlite3
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

TOKEN = "8872841970:AAHmcScjJmLi5wsKkX4i93TEnbE4Zue-U-8"
ADMIN_ID = 1091526567

CHANNEL_ID = -1004432263733
CHANNEL_LINK = "https://t.me/SafforRewards"
REFERRALS_REQUIRED = 3
DAILY_FREE_LIMIT = 20

PROXY_TYPES = {
    "rotate": {"name": "🔄 روتيت موبايل", "desc": "الأفضل لتكرار العروض. الـ IP يتغير مع كل جلسة. خطر الاكتشاف منخفض."},
    "ultra":  {"name": "⚡ ألترا سوكس",  "desc": "بديل اقتصادي مناسب للعروض. وقت العمل: 1 - 8 ساعات. أحياناً يتوقف في الدقائق الأولى. لا يُرد ثمنه إذا ��وقف في الدقائق الأولى."},
}

PROXY_PLANS = {
    "1":   {"name": "ساعة واحدة",   "cost": 10},
    "3":   {"name": "3 ساعات",      "cost": 25},
    "12":  {"name": "12 ساعة",      "cost": 60},
    "24":  {"name": "يوم كامل",      "cost": 100},
    "72":  {"name": "3 أيام",       "cost": 250},
    "168": {"name": "أسبوع كامل",    "cost": 550},
    "336": {"name": "أسبوعين",      "cost": 1050},
    "720": {"name": "شهر كامل",      "cost": 1900},
}

ULTRA_COST = 10
PROXY_CHECK_INPUT = 1

def init_db():
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0, username TEXT, first_name TEXT,
                 preferred_currency TEXT DEFAULT 'IQD', referral_count INTEGER DEFAULT 0, referred_by INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS proxy_requests
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, proxy_type TEXT, plan_name TEXT,
                 cost INTEGER, status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS free_proxies
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, port TEXT, user TEXT, password TEXT,
                 used BOOLEAN DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS daily_stats
                 (date TEXT PRIMARY KEY, free_proxies_given INTEGER DEFAULT 0)''')
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
    r = c.fetchone()
    conn.close()
    return r[0] if r else 0

def update_balance(user_id, amount):
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def get_referral_count(user_id):
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("SELECT referral_count FROM users WHERE user_id=?", (user_id,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else 0

def increment_referral(user_id):
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("UPDATE users SET referral_count = referral_count + 1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def reset_referral(user_id):
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("UPDATE users SET referral_count = 0 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def is_new_user(user_id):
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("SELECT referred_by FROM users WHERE user_id=?", (user_id,))
    r = c.fetchone()
    conn.close()
    if r is None:
        return True
    return r[0] == 0

def set_referred_by(user_id, referrer_id):
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("UPDATE users SET referred_by = ? WHERE user_id=?", (referrer_id, user_id))
    conn.commit()
    conn.close()

def get_preferred_currency(user_id):
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("SELECT preferred_currency FROM users WHERE user_id=?", (user_id,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else 'IQD'

def set_preferred_currency(user_id, currency):
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("UPDATE users SET preferred_currency = ? WHERE user_id=?", (currency, user_id))
    conn.commit()
    conn.close()

def get_available_free_proxy():
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("SELECT id, ip, port, user, password FROM free_proxies WHERE used = 0 LIMIT 1")
    r = c.fetchone()
    conn.close()
    return r

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

def add_proxy_request(user_id, proxy_type, plan_name, cost):
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO proxy_requests (user_id, proxy_type, plan_name, cost) VALUES (?, ?, ?, ?)", (user_id, proxy_type, plan_name, cost))
    conn.commit()
    conn.close()

def get_today():
    return datetime.now().strftime('%Y-%m-%d')

def get_daily_count():
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    today = get_today()
    c.execute("SELECT free_proxies_given FROM daily_stats WHERE date=?", (today,))
    r = c.fetchone()
    if r is None:
        c.execute("INSERT OR IGNORE INTO daily_stats (date, free_proxies_given) VALUES (?, 0)", (today,))
        conn.commit()
        conn.close()
        return 0
    conn.close()
    return r[0]

def increment_daily_count():
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    today = get_today()
    c.execute("INSERT OR IGNORE INTO daily_stats (date, free_proxies_given) VALUES (?, 0)", (today,))
    c.execute("UPDATE daily_stats SET free_proxies_given = free_proxies_given + 1 WHERE date=?", (today,))
    conn.commit()
    conn.close()

async def check_channel_membership(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Channel check error: {e}")
        return False

async def safe_answer(query):
    try:
        await query.answer()
    except Exception as e:
        print(f"Answer error (ignored): {e}")

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

def sub_section_keyboard():
    keyboard = [[KeyboardButton("⬅️ عودة")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def proxy_types_keyboard():
    keyboard = []
    for key, ptype in PROXY_TYPES.items():
        keyboard.append([InlineKeyboardButton(f"{ptype['name']}", callback_data=f"ptype_{key}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)

def proxy_plans_keyboard(proxy_type):
    keyboard = []
    for key, plan in PROXY_PLANS.items():
        keyboard.append([InlineKeyboardButton(f"{plan['name']} - {plan['cost']} نقطة", callback_data=f"pplan_{proxy_type}_{key}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_types")])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    create_user(user.id, user.username, user.first_name)
    balance = get_balance(user.id)

    if context.args:
        arg = context.args[0]
        if arg.startswith("ref_"):
            try:
                referrer_id = int(arg.split("_")[1])
                if referrer_id != user.id and is_new_user(user.id):
                    set_referred_by(user.id, referrer_id)
                    increment_referral(referrer_id)
                    count = get_referral_count(referrer_id)
                    remaining = REFERRALS_REQUIRED - count
                    try:
                        if count >= REFERRALS_REQUIRED:
                            await context.bot.send_message(
                                chat_id=referrer_id,
                                text=f"🎉 تم تسجيل مستخدم جديد عبر رابطك!\n\n"
                                     f"📊 إحالاتك: {count} من {REFERRALS_REQUIRED}\n\n"
                                     f"✅ لقد أكملت الشرط!\n\n"
                                     f"📌 اضغط على زر (🎁 بروكسي مجاني) في القائمة الرئيسية لاستلام البروكسي."
                            )
                        else:
                            await context.bot.send_message(
                                chat_id=referrer_id,
                                text=f"🎉 تم تسجيل مستخدم جديد عبر رابطك!\n"
                                     f"📊 إحالاتك: {count} من {REFERRALS_REQUIRED}\n"
                                     f"📌 تبقى {max(0, remaining)} للحصول على بروكسي مجاني."
                            )
                    except:
                        pass
            except Exception as e:
                print(f"Referral error: {e}")

    await update.message.reply_text(
        f"👋 مرحباً بك في بوت صفور للبروكسي!\n"
        f"💰 رصيدك: {balance} نقطة\n\n"
        f"اختر الخدمة من الأزرار أدناه:",
        reply_markup=main_keyboard()
    )

async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    balance = get_balance(user_id)
    currency = get_preferred_currency(user_id)
    referrals = get_referral_count(user_id)
    usd_value = balance * 0.006
    if currency == 'IQD':
        display = f"{usd_value * 1500:.0f} دينار عراقي"
    else:
        display = f"${usd_value:.2f}"
    await update.message.reply_text(
        f"👤 حسابي\n\n"
        f"💰 رصيدك: {balance} نقطة\n"
        f"≈ {display}\n\n"
        f"👥 إحالاتك: {referrals} من {REFERRALS_REQUIRED}\n\n"
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
    await update.message.reply_text("🕒 اختر نوع البروكسي:", reply_markup=proxy_types_keyboard())

async def proxy_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    data = query.data

    if data == "back_to_main":
        try:
            await query.message.delete()
        except:
            pass
        await query.message.reply_text("🏠 القائمة الرئيسية", reply_markup=main_keyboard())
        return

    if data == "back_to_types":
        await query.edit_message_text("🕒 اختر نوع البروكسي:", reply_markup=proxy_types_keyboard())
        return

    proxy_type = data.split("_")[1]
    ptype = PROXY_TYPES.get(proxy_type)
    if not ptype:
        await query.edit_message_text("⚠️ حدث خطأ.")
        return

    if proxy_type == "ultra":
        await query.edit_message_text(
            f"{ptype['name']}\n\n"
            f"{ptype['desc']}\n\n"
            f"💰 السعر: {ULTRA_COST} نقطة\n\n"
            f"للتأكيد، اضغط على الزر أدناه:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"✅ تأكيد الشراء ({ULTRA_COST} نقطة)", callback_data="buyultra")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_types")]
            ])
        )
    else:
        await query.edit_message_text(
            f"{ptype['name']}\n\n"
            f"{ptype['desc']}\n\n"
            f"🕒 اختر المدة:",
            reply_markup=proxy_plans_keyboard(proxy_type)
        )

async def buy_ultra_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    user_id = query.from_user.id
    balance = get_balance(user_id)

    if balance < ULTRA_COST:
        await query.edit_message_text(
            f"⚠️ رصيدك غير كافٍ!\n"
            f"أنت بحاجة إلى {ULTRA_COST} نقطة.\n"
            f"رصيدك الحالي: {balance} نقطة."
        )
        return

    update_balance(user_id, -ULTRA_COST)
    add_proxy_request(user_id, "⚡ ألترا سوكس", "جلسة اقتصادية", ULTRA_COST)

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📢 طلب ألترا سوكس جديد!\n\n"
             f"👤 المستخدم: {query.from_user.first_name}\n"
             f"🆔 ID: {user_id}\n"
             f"💰 التكلفة: {ULTRA_COST} نقطة\n"
             f"💵 الرصيد المتبقي: {get_balance(user_id)} نقطة"
    )

    await query.edit_message_text(
        f"✅ تم خصم {ULTRA_COST} نقطة.\n\n"
        f"🔄 جارٍ تجهيز البروكسي...\n"
        f"⏳ سيتم إرسال البيانات خلال دقائق."
    )

async def proxy_plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    user_id = query.from_user.id
    data = query.data

    if data == "back_to_types":
        await query.edit_message_text("🕒 اختر نوع البروكسي:", reply_markup=proxy_types_keyboard())
        return

    if data == "back_to_main":
        try:
            await query.message.delete()
        except:
            pass
        await query.message.reply_text("🏠 القائمة الرئيسية", reply_markup=main_keyboard())
        return

    parts = data.split("_")
    if len(parts) != 3:
        await query.edit_message_text("⚠️ حدث خطأ.")
        return

    proxy_type = parts[1]
    plan_key = parts[2]
    plan = PROXY_PLANS.get(plan_key)
    ptype = PROXY_TYPES.get(proxy_type)

    if not plan or not ptype:
        await query.edit_message_text("⚠️ حدث خطأ.")
        return

    balance = get_balance(user_id)
    if balance < plan['cost']:
        await query.edit_message_text(
            f"⚠️ رصيدك غير كافٍ!\n"
            f"أنت بحاجة إلى {plan['cost']} نقطة.\n"
            f"رصيدك الحالي: {balance} نقطة."
        )
        return

    update_balance(user_id, -plan['cost'])
    add_proxy_request(user_id, ptype['name'], plan['name'], plan['cost'])

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📢 طلب بروكسي جديد!\n\n"
             f"👤 المستخدم: {query.from_user.first_name}\n"
             f"🆔 ID: {user_id}\n"
             f"🔖 النوع: {ptype['name']}\n"
             f"⏱️ المدة: {plan['name']}\n"
             f"💰 التكلفة: {plan['cost']} نقطة\n"
             f"💵 الرصيد المتبقي: {get_balance(user_id)} نقطة"
    )

    await query.edit_message_text(
        f"✅ تم خصم {plan['cost']} نقطة.\n\n"
        f"🔖 النوع: {ptype['name']}\n"
        f"⏱️ المدة: {plan['name']}\n\n"
        f"🔄 جارٍ تجهيز البروكسي...\n"
        f"⏳ سيتم إرسال البيانات خلال دقائق."
    )

async def free_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    is_member = await check_channel_membership(user_id, context)
    if not is_member:
        await update.message.reply_text(
            f"⚠️ للاستفادة من البروكسي المجاني، يجب أن تكون عضواً في قناتنا أولاً.\n\n"
            f"📢 انضم إلى القناة:\n{CHANNEL_LINK}\n\n"
            f"ثم اضغط على زر بروكسي مجاني مرة أخرى.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 انضم إلى القناة", url=CHANNEL_LINK)],
                [InlineKeyboardButton("✅ تحققت من العضوية", callback_data="check_membership")]
            ])
        )
        return

    ref_count = get_referral_count(user_id)
    remaining = REFERRALS_REQUIRED - ref_count
    ref_link = f"https://t.me/SafforProxyBot?start=ref_{user_id}"

    if ref_count >= REFERRALS_REQUIRED:
        await update.message.reply_text(
            f"🎉 لقد أكملت {REFERRALS_REQUIRED} إحالات!\n\n"
            f"اضغط على الزر أدناه للحصول على بروكسي مجاني لمدة ساعة:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎁 استلام البروكسي المجاني", callback_data="claim_free_proxy")]
            ])
        )
    else:
        daily_count = get_daily_count()
        daily_remaining = DAILY_FREE_LIMIT - daily_count
        
        await update.message.reply_text(
            f"🎁 بروكسي مجاني\n\n"
            f"📌 ادعُ {REFERRALS_REQUIRED} أصدقاء للحصول على بروكسي مجاني لمدة ساعة.\n\n"
            f"📊 إحالاتك الحالية: {ref_count} من {REFERRALS_REQUIRED}\n"
            f"📌 تبقى: {remaining}\n\n"
            f"⚠️ الحد اليومي: {DAILY_FREE_LIMIT} بروكسي فقط.\n"
            f"📊 المتبقي اليوم: {daily_remaining}\n\n"
            f"🔗 رابط الإحالة الخاص بك:\n{ref_link}\n\n"
            f"شارك هذا الرابط مع أصدقائك، وعندما يسجلون عبره، ستزيد إحالاتك."
        )

async def check_membership_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    user_id = query.from_user.id
    is_member = await check_channel_membership(user_id, context)
    if is_member:
        await query.edit_message_text(
            f"✅ تم التحقق من عضويتك!\n\n"
            f"اضغط على زر بروكسي مجاني في القائمة الرئيسية للمتابعة."
        )
    else:
        await query.edit_message_text(
            f"⚠️ لم نتمكن من التحقق من عضويتك.\n"
            f"تأكد من انضمامك للقناة ثم حاول مرة أخرى.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 انضم إلى القناة", url=CHANNEL_LINK)],
                [InlineKeyboardButton("✅ تحققت من العضوية", callback_data="check_membership")]
            ])
        )

async def claim_free_proxy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    user_id = query.from_user.id

    daily_count = get_daily_count()
    if daily_count >= DAILY_FREE_LIMIT:
        await query.edit_message_text(
            f"⚠️ عذراً، تم استنفاد الحصة اليومية ({DAILY_FREE_LIMIT} بروكسي).\n"
            f"حاول غداً."
        )
        return

    proxy = get_available_free_proxy()
    if not proxy:
        await query.edit_message_text(
            f"⚠️ عذراً، لا توجد بروكسيات متاحة حالياً.\n"
            f"حاول لاحقاً."
        )
        return

    reset_referral(user_id)
    mark_proxy_as_used(proxy[0])
    increment_daily_count()

    await query.edit_message_text(
        f"🎉 تهانينا! لقد حصلت على بروكسي مجاني لمدة ساعة.\n\n"
        f"📡 بيانات البروكسي:\n"
        f"IP: {proxy[1]}\n"
        f"Port: {proxy[2]}\n"
        f"User: {proxy[3]}\n"
        f"Pass: {proxy[4]}\n\n"
        f"⏳ الصلاحية: ساعة واحدة.\n"
        f"📌 إذا لم يعمل، تواصل مع الدعم."
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
        f"💱 العملة الحالية: {current}\n\nاختر العملة:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def currency_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    user = query.from_user
    create_user(user.id, user.username, user.first_name)
    currency = query.data.split("_")[1]
    set_preferred_currency(user.id, currency)
    await query.edit_message_text(f"✅ تم تغيير العملة إلى {currency} بنجاح.")

async def more_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 قائمة المزيد\n\nاختر من الخيارات:", reply_markup=more_keyboard())

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏠 القائمة الرئيسية:", reply_markup=main_keyboard())

async def back_to_more(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 قائمة المزيد:", reply_markup=more_keyboard())

async def guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📖 دليل استخدام البروكسي\n\n"
        f"1. ما هو البروكسي؟\n"
        f"البروكسي هو وسيط بين جهازك والإنترنت، يخفي عنوان IP الحقيقي ويظهر عنواناً آخر.\n\n"
        f"2. كيف أستخدم البروكسي على هاتفي؟\n"
        f"• قم بتنزيل تطبيق يدعم البروكسي (مثل: Super proxy للأندرويد).\n"
        f"• أدخل بيانات البروكسي (IP, Port, User, Pass) في التطبيق.\n"
        f"• اختر نوع البروتوكول: SOCKS5 (الأفضل).\n"
        f"• شغّل البروكسي، ثم افتح تطبيق صفور.\n\n"
        f"3. الفرق بين SOCKS5 و HTTP:\n"
        f"• SOCKS5: يعمل مع جميع التطبيقات والألعاب.\n"
        f"• HTTP: يعمل فقط مع المتصفح.\n\n"
        f"4. لماذا لا يعمل البروكسي؟\n"
        f"• تأكد من صحة البيانات.\n"
        f"• تأكد من عدم انتهاء الصلاحية.\n"
        f"• جرب بروتوكولاً آخر.",
        reply_markup=sub_section_keyboard()
    )

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"💬 تواصل مع الدعم\n\n"
        f"لأي استفسار أو مشكلة:\n\n"
        f"👉 @SafforSupportBot\n\n"
        f"⏰ وقت الاستجابة: خلال 24 ساعة.",
        reply_markup=sub_section_keyboard()
    )

async def proxy_check_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🔍 فحص البروكسي\n\n"
        f"أرسل بيانات البروكسي:\n\n"
        f"IP:PORT:USER:PASS\n\n"
        f"مثال:\n"
        f"192.168.1.1:1080:user123:pass123\n\n"
        f"أو بدون اسم مستخدم:\n"
        f"IP:PORT\n\n"
        f"مثال:\n"
        f"192.168.1.1:1080",
        reply_markup=sub_section_keyboard()
    )
    return PROXY_CHECK_INPUT

async def proxy_check_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "⬅️ عودة" or text == "/cancel":
        await update.message.reply_text("📊 قائمة المزيد:", reply_markup=more_keyboard())
        return ConversationHandler.END

    await update.message.reply_text("⏳ جاري فحص البروكسي...")

    try:
        parts = text.split(":")
        if len(parts) == 4:
            ip, port, user, password = parts
            auth = f"{user}:{password}@"
        elif len(parts) == 2:
            ip, port = parts
            auth = ""
        else:
            await update.message.reply_text("⚠️ صيغة غير صحيحة.", reply_markup=sub_section_keyboard())
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
                response = requests.get("https://api.ipify.org?format=json", proxies=proxy_dict, timeout=10)
                data = response.json()
                new_ip = data.get("ip", "غير معروف")
                used_protocol = proto_name
                try:
                    geo = requests.get(f"http://ip-api.com/json/{new_ip}?fields=status,country,city", timeout=10).json()
                    if geo.get("status") == "success":
                        country = geo.get("country", "غير معروف")
                        city = geo.get("city", "")
                except:
                    pass
                success = True
                break
            except:
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
                reply_markup=sub_section_keyboard()
            )
        else:
            await update.message.reply_text(
                f"❌ البروكسي لا يعمل.\n\n"
                f"الأسباب المحتملة:\n"
                f"• البيانات غير صحيحة.\n"
                f"• البروكسي منتهي الصلاحية.\n"
                f"• الخادم لا يستجيب.",
                reply_markup=sub_section_keyboard()
            )
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"⚠️ حدث خطأ: {str(e)}", reply_markup=sub_section_keyboard())
        return ConversationHandler.END

async def cancel_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 قائمة المزيد:", reply_markup=more_keyboard())
    return ConversationHandler.END

async def admin_add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        args = context.args
        user_id = int(args[0])
        amount = int(args[1])
        update_balance(user_id, amount)
        await update.message.reply_text(f"✅ تم إضافة {amount} نقطة للمستخدم {user_id}.")
    except:
        await update.message.reply_text("⚠️ الاستخدام: /addbalance <user_id> <amount>")

async def admin_add_free_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        args = context.args
        ip, port, user, password = args[0], args[1], args[2], args[3]
        add_free_proxy(ip, port, user, password)
        await update.message.reply_text(f"✅ تم إضافة بروكسي مجاني: {ip}:{port}")
    except:
        await update.message.reply_text("⚠️ الاستخدام: /addfreeproxy <IP> <PORT> <USER> <PASS>")

async def admin_list_free_proxies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("SELECT id, ip, port, user, password, used FROM free_proxies")
    proxies = c.fetchall()
    conn.close()
    if not proxies:
        await update.message.reply_text("📭 لا توجد بروكسيات مجانية.")
        return
    text = "📋 قائمة البروكسيات المجانية:\n\n"
    for p in proxies:
        status = "✅ متاح" if not p[5] else "❌ مستخدم"
        text += f"ID: {p[0]} | {p[1]}:{p[2]} | {p[3]}:{p[4]} | {status}\n"
    await update.message.reply_text(text)

async def admin_delete_free_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        proxy_id = int(context.args[0])
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
        return
    conn = sqlite3.connect('proxy_bot.db')
    c = conn.cursor()
    c.execute("UPDATE free_proxies SET used = 0")
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ تم إعادة تعيين جميع البروكسيات.")

async def admin_daily_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    count = get_daily_count()
    await update.message.reply_text(
        f"📊 إحصائيات اليوم\n\n"
        f"🎁 البروكسيات المجانية الممنوحة: {count} من {DAILY_FREE_LIMIT}"
    )

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
    app.add_handler(CommandHandler("dailystats", admin_daily_stats))

    app.add_handler(MessageHandler(filters.Regex("^📡 طلب بروكسي$"), request_proxy))
    app.add_handler(MessageHandler(filters.Regex("^👤 حسابي$"), my_account))
    app.add_handler(MessageHandler(filters.Regex("^💰 شراء رصيد$"), buy_credit))
    app.add_handler(MessageHandler(filters.Regex("^🎁 بروكسي مجاني$"), free_proxy))
    app.add_handler(MessageHandler(filters.Regex("^💱 تغيير العملة$"), change_currency))
    app.add_handler(MessageHandler(filters.Regex("^📊 المزيد$"), more_menu))
    app.add_handler(MessageHandler(filters.Regex("^📖 دليل الاستخدام$"), guide))
    app.add_handler(MessageHandler(filters.Regex("^💬 تواصل مع الدعم$"), support))
    app.add_handler(MessageHandler(filters.Regex("^⬅️ عودة$"), back_to_more))
    app.add_handler(MessageHandler(filters.Regex("^🔙 رجوع$"), back_to_main))

    app.add_handler(CallbackQueryHandler(proxy_type_callback, pattern="^ptype_"))
    app.add_handler(CallbackQueryHandler(proxy_plan_callback, pattern="^pplan_"))
    app.add_handler(CallbackQueryHandler(proxy_type_callback, pattern="^back_to_main$"))
    app.add_handler(CallbackQueryHandler(proxy_plan_callback, pattern="^back_to_types$"))
    app.add_handler(CallbackQueryHandler(buy_ultra_callback, pattern="^buyultra$"))
    app.add_handler(CallbackQueryHandler(check_membership_callback, pattern="^check_membership$"))
    app.add_handler(CallbackQueryHandler(claim_free_proxy_callback, pattern="^claim_free_proxy$"))
    app.add_handler(CallbackQueryHandler(currency_callback, pattern="^cur_"))

    print("🤖 بوت صفور للبروكسي يعمل...")
    app.run_polling()

if __name__ == "__main__":
    main()
