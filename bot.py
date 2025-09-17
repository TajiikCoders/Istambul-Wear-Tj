# -*- coding: utf-8 -*-
import logging
import json
import os
import time
import threading
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
    CallbackQueryHandler,
)
import requests

# --- Конфигуратсияи асосӣ ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# =================================================================================
# +++ ҚИСМИ ТАНЗИМОТИ БЕХАТАР +++
#
# Токен ва суроғаи API аз тағирёбандаҳои муҳити система гирифта мешаванд.
# Ин усули бехатар барои ҷойгиркунии лоиҳа дар интернет аст.
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_TELEGRAM_ID = 7226492351 # ID-и админро метавонед инҷо гузоред

# Агар API_BASE_URL дар муҳит муқаррар нашуда бошад, суроғаи маҳаллӣ (барои тест) истифода мешавад.
# Дар хостинг шумо бояд суроғаи публикии app.py-ро муқаррар кунед.
API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:5000") + "/api"
#
# =================================================================================

BOT_SESSIONS_FILE = 'bot_sessions.json'
SESSION_LOCK = threading.Lock()

# ... (Матнҳо бе тағйирот)
TEXTS = {
    'choose_language': "Забонро интихоб кунед / Выберите язык / Select language:",'welcome': {'tj': "🎉 Хуш омадед!", 'ru': "🎉 Добро пожаловать!", 'en': "🎉 Welcome!"},'main_menu': {'tj': ["🛍️ Каталог", "🛒 Сабад", "📞 Тамос"], 'ru': ["🛍️ Каталог", "🛒 Корзина", "📞 Контакты"], 'en': ["🛍️ Catalog", "🛒 Cart", "📞 Contact"]},'admin_menu': {'tj': ["➕ Иловаи маҳсулот", "📁 Иловаи категория", "📊 Омори фурӯш", "📣 Фиристодани хабарнома"], 'ru': ["➕ Добавить товар", "📁 Добавить категорию", "📊 Статистика продаж", "📣 Сделать рассылку"], 'en': ["➕ Add Product", "📁 Add Category", "📊 Sales Statistics", "📣 Send Newsletter"]},'user_menu_for_admin': {'tj': "⚙️ Ба панели администратор", 'ru': "⚙️ В админ-панель", 'en': "⚙️ To Admin Panel"},'ask_broadcast_message': {'tj': "Паёмеро, ки ба ҳамаи корбарон фиристодан мехоҳед, нависед (метавонад матн, акс бо матн бошад). Барои бекор кардан /cancel -ро пахш кунед.", 'ru': "Введите сообщение для рассылки всем пользователям (можно текст, фото с текстом). Для отмены нажмите /cancel.", 'en': "Enter the message to broadcast to all users (can be text, or a photo with caption). Press /cancel to quit."},'broadcast_confirmation': {'tj': "Шумо мутмаин ҳастед, ки ин паёмро ба ҳамаи корбарон мефиристед?", 'ru': "Вы уверены, что хотите отправить это сообщение всем пользователям?", 'en': "Are you sure you want to send this message to all users?"},'broadcast_started': {'tj': "✅ Рассылка оғоз шуд. Ин метавонад каме вақт гирад...", 'ru': "✅ Рассылка началась. Это может занять некоторое время...", 'en': "✅ Broadcast started. This may take some time..."},'broadcast_report': {'tj': "📈 Ҳисобот: Паём ба {} аз {} корбар бомуваффақият фиристода шуд.", 'ru': "📈 Отчет: Сообщение успешно отправлено {} из {} пользователей.", 'en': "📈 Report: Message successfully sent to {} out of {} users."},'stats_message': {'tj': "📊 **ОМОРИ УМУМИИ ФУРӮШ**\n\n💰 **Даромади умумӣ:** `{total_revenue}` сомонӣ\n🆕 **Фармоишҳои нав:** `{new_orders}` дона\n📦 **Ҳамагӣ фармоишҳо:** `{total_orders}` дона\n👤 **Шумораи мизоҷон:** `{total_customers}` нафар\n👕 **Шумораи маҳсулот:** `{total_products}` дона", 'ru': "📊 **ОБЩАЯ СТАТИСТИКА ПРОДАЖ**\n\n💰 **Общий доход:** `{total_revenue}` сомони\n🆕 **Новые заказы:** `{new_orders}` шт.\n📦 **Всего заказов:** `{total_orders}` шт.\n👤 **Количество клиентов:** `{total_customers}` чел.\n👕 **Количество товаров:** `{total_products}` шт.", 'en': "📊 **OVERALL SALES STATISTICS**\n\n💰 **Total Revenue:** `{total_revenue}` TJS\n🆕 **New Orders:** `{new_orders}`\n📦 **Total Orders:** `{total_orders}`\n👤 **Total Customers:** `{total_customers}`\n👕 **Total Products:** `{total_products}`"},'choose_category': {'tj': "Категорияро интихоб кунед:", 'ru': "Выберите категорию:", 'en': "Choose a category:"},'no_products': {'tj': "Дар ин категория ҳоло маҳсулот нест.", 'ru': "В этой категории пока нет товаров.", 'en': "There are no products in this category yet."},'add_to_cart': {'tj': "🛒 Илова ба сабад", 'ru': "🛒 Добавить в корзину", 'en': "🛒 Add to Cart"},'enter_quantity': {'tj': "Миқдорро ворид кунед (масалан: 1):", 'ru': "Введите количество (например: 1):", 'en': "Enter quantity (e.g., 1):"},'added_to_cart': {'tj': "✅ Маҳсулот ба сабад илова карда шуд!", 'ru': "✅ Товар добавлен в корзину!", 'en': "✅ Product added to cart!"},'cart_is_empty': {'tj': "🛒 Сабади шумо холӣ аст.", 'ru': "🛒 Ваша корзина пуста.", 'en': "🛒 Your cart is empty."},'your_cart': {'tj': "🛒 **Сабади шумо:**", 'ru': "🛒 **Ваша корзина:**", 'en': "🛒 **Your cart:**"},'total_price': {'tj': "💰 **Нархи умумӣ:**", 'ru': "💰 **Общая стоимость:**", 'en': "💰 **Total price:**"},'checkout': {'tj': "✅ Тасдиқи фармоиш", 'ru': "✅ Оформить заказ", 'en': "✅ Checkout"},'clear_cart': {'tj': "🗑️ Тоза кардани сабад", 'ru': "🗑️ Очистить корзину", 'en': "🗑️ Clear Cart"},'enter_address': {'tj': "📍 Суроғаи худро барои расонидан ворид кунед:", 'ru': "📍 Введите ваш адрес для доставки:", 'en': "📍 Please enter your delivery address:"},'enter_phone': {'tj': "📱 Рақами телефони худро ворид кунед (масалан: +992921234567):", 'ru': "📱 Введите ваш номер телефона (например: +992921234567):", 'en': "📱 Please enter your phone number (e.g., +992921234567):"},'order_confirmed': {'tj': "✅ **Фармоиши шумо қабул шуд!**\n\nРақами фармоиши шумо: **#{}**\n\nМенеҷери мо ба наздикӣ бо шумо дар тамос хоҳад шуд.", 'ru': "✅ **Ваш заказ принят!**\n\nНомер вашего заказа: **#{}**\n\nНаш менеджер скоро свяжется с вами.", 'en': "✅ **Your order has been confirmed!**\n\nYour order number is: **#{}**\n\nOur manager will contact you shortly."},'contact_info': {'tj': "📞 **Маълумот барои тамос:**\n\n**Телефон:** +992 92 777 77 77\n**Email:** support@istambulwear.tj", 'ru': "📞 **Контактная информация:**\n\n**Телефон:** +992 92 777 77 77\n**Email:** support@istambulwear.tj", 'en': "📞 **Contact Information:**\n\n**Phone:** +992 92 777 77 77\n**Email:** support@istambulwear.tj"},'back': {'tj': "↩️ Ба қафо", 'ru': "↩️ Назад", 'en': "↩️ Back"},'error_api': {'tj': "🔴 Хатогӣ дар пайвастшавӣ ба сервер. Лутфан, боварӣ ҳосил кунед, ки сервер фаъол аст ва аз нав кӯшиш кунед.", 'ru': "🔴 Ошибка подключения к серверу. Убедитесь, что сервер запущен, и попробуйте снова.", 'en': "🔴 Error connecting to the server. Please ensure the server is running and try again."},'new_order_notification': {'tj': ("🚨 **ФАРМОИШИ НАВ (аз Телеграм-бот)** 🚨\n\n"
                                     "**Рақами фармоиш:** `#{order_id}`\n"
                                     "**Мизоҷ:** {first_name} (@{username})\n"
                                     "**Телефон:** `{phone}`\n"
                                     "**Суроға:** {address}\n\n"
                                     "--- **Рӯйхати маҳсулот** ---\n{products_list}"
                                     "-------------------------\n\n"
                                     "💰 **Нархи умумӣ: {total_price} сомонӣ**")},'add_product_start': {'tj': "Оғози иловаи маҳсулоти нав. Барои бекор кардан /cancel -ро пахш кунед.\n\nКатегорияро интихоб кунед:", 'ru': "Начинаем добавление товара. Для отмены введите /cancel.\n\nВыберите категорию:", 'en': "Starting new product addition. Type /cancel to quit.\n\nChoose a category:"},'ask_product_name': {'tj': "Номи маҳсулотро ворид кунед:", 'ru': "Введите название товара:", 'en': "Enter the product name:"},'ask_price': {'tj': "Нархи маҳсулотро бо сомонӣ ворид кунед (масалан: 120.50):", 'ru': "Введите цену товара в сомони (например: 120.50):", 'en': "Enter the product price in Somoni (e.g., 120.50):"},'ask_photo': {'tj': "Акси асосии маҳсулотро фиристед:", 'ru': "Отправьте основное фото товара:", 'en': "Send the main product photo:"},'ask_inventory': {'tj': "Акнун андоза ва миқдорро ворид кунед. Намуна: S 10 (андозаи S, 10 дона). Пас аз анҷом 'тамом' нависед.", 'ru': "Теперь введите размер и количество. Пример: S 10 (размер S, 10 штук). Когда закончите, напишите 'готово'.", 'en': "Now enter size and quantity. Example: S 10 (size S, 10 units). When finished, type 'done'."},'inventory_added': {'tj': "✅ Андозаи '{}' бо миқдори {} илова шуд. Боз ворид кунед ё 'тамом' нависед.", 'ru': "✅ Размер '{}' с количеством {} добавлен. Введите еще или напишите 'готово'.", 'en': "✅ Size '{}' with quantity {} added. Enter more or type 'done'."},'product_added_success': {'tj': "✅ Маҳсулоти нав бомуваффақият ба база илова карда шуд!", 'ru': "✅ Новый товар успешно добавлен в базу!", 'en': "✅ New product successfully added to the database!"},'operation_cancelled': {'tj': "🚫 Амалиёт бекор карда шуд.", 'ru': "🚫 Операция отменена.", 'en': "🚫 Operation cancelled."},'yes': {'tj': 'Ҳа', 'ru': 'Да', 'en': 'Yes'},'no': {'tj': 'Не', 'ru': 'Нет', 'en': 'No'},'add_category_start': {'tj': "Номи категорияи навро ворид кунед (масалан: Куртаҳо). Барои бекор кардан /cancel -ро пахш кунед.", 'ru': "Введите название новой категории (например: Рубашки). Для отмены нажмите /cancel.", 'en': "Enter the new category name (e.g., Shirts). Press /cancel to quit."},'category_added_success': {'tj': "✅ Категорияи '{}' бомуваффақият илова карда шуд!", 'ru': "✅ Категория '{}' успешно добавлена!", 'en': "✅ Category '{}' successfully added!"},'category_add_failed': {'tj': "🔴 Хатогӣ! Категория илова нашуд. Эҳтимол, чунин ном аллакай мавҷуд аст ё хатогии сервер рух дод.", 'ru': "🔴 Ошибка! Категория не добавлена. Возможно, такое имя уже существует или произошла ошибка сервера.", 'en': "🔴 Error! Category not added. The name might already exist, or a server error occurred."}}

# --- ҲОЛАТҲОИ СУҲБАТ ---
(SELECTING_LANGUAGE, MAIN_MENU, ADMIN_MENU,
 ADD_PRODUCT_CAT, ADD_PRODUCT_NAME, ADD_PRODUCT_PRICE, ADD_PRODUCT_PHOTO, ADD_PRODUCT_INVENTORY,
 ADD_CATEGORY_NAME, 
 SHOWING_CATEGORIES, SHOWING_PRODUCTS, ADDING_TO_CART_QUANTITY,
 CHECKOUT_ADDRESS, CHECKOUT_PHONE, BROADCAST_MESSAGE, BROADCAST_CONFIRM) = range(16)

# ... (Функсияҳои ёрирасон бе тағйирот)
def load_bot_sessions():
    with SESSION_LOCK:
        if not os.path.exists(BOT_SESSIONS_FILE): return {}
        try:
            with open(BOT_SESSIONS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError): return {}
def save_bot_sessions(data):
    with SESSION_LOCK:
        with open(BOT_SESSIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
def get_user_lang(context: CallbackContext):
    return context.user_data.get('lang', 'tj')
def get_text(key, lang, *args, **kwargs):
    node = TEXTS.get(key, {})
    template = node.get(lang, f"_{key}_") if isinstance(node, dict) else node
    try:
        return template.format(*args, **kwargs)
    except (KeyError, IndexError):
        return template
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_TELEGRAM_ID
def notify_admin_new_order(context: CallbackContext, order_details: dict):
    try:
        user = order_details['user']
        products_list_text = "".join([f"  - {item['name']} (x{item['quantity']}) - {item['price']:.2f} сомонӣ\n" for item in order_details['cart_details']])
        notification_text = get_text('new_order_notification', 'tj',
                                     order_id=order_details.get('id', 'N/A'),
                                     first_name=user.first_name, username=user.username or 'N/A',
                                     phone=order_details['phone'], address=order_details['address'],
                                     products_list=products_list_text, total_price=f"{order_details['total']:.2f}")
        context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=notification_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Хатогӣ ҳангоми фиристодани огоҳинома ба админ: {e}")

# ... (Оғози кор ва менюҳо бе тағйирот)
def start(update: Update, context: CallbackContext) -> int:
    user_id = str(update.message.from_user.id)
    sessions = load_bot_sessions()
    if user_id not in sessions:
        sessions[user_id] = {'lang': 'tj', 'cart': []}
        save_bot_sessions(sessions)
    buttons = [KeyboardButton("🇹🇯 Тоҷикӣ"), KeyboardButton("🇷🇺 Русский"), KeyboardButton("🇬🇧 English")]
    reply_markup = ReplyKeyboardMarkup([buttons], resize_keyboard=True, one_time_keyboard=True)
    update.message.reply_text(TEXTS['choose_language'], reply_markup=reply_markup)
    return SELECTING_LANGUAGE
def set_language(update: Update, context: CallbackContext) -> int:
    lang_map = {"🇹🇯 Тоҷикӣ": "tj", "🇷🇺 Русский": "ru", "🇬🇧 English": "en"}
    lang = lang_map.get(update.message.text)
    if not lang: return start(update, context)
    context.user_data['lang'] = lang
    sessions, user_id = load_bot_sessions(), str(update.message.from_user.id)
    if user_id in sessions:
        sessions[user_id]['lang'] = lang
        save_bot_sessions(sessions)
    if is_admin(update.message.from_user.id): return show_admin_menu(update, context)
    return show_main_menu(update, context)
def show_main_menu(update: Update, context: CallbackContext) -> int:
    lang = get_user_lang(context)
    buttons_text = TEXTS['main_menu'][lang]
    buttons = [[KeyboardButton(b) for b in buttons_text]]
    if is_admin(update.effective_user.id):
        buttons.append([KeyboardButton(get_text('user_menu_for_admin', lang))])
    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    if update.callback_query:
        update.callback_query.answer()
        message = update.callback_query.message
        try: message.delete()
        except Exception as e: logger.info(f"Паёми пешина нест карда нашуд: {e}")
        context.bot.send_message(chat_id=message.chat_id, text=get_text('welcome', lang), reply_markup=reply_markup)
    elif update.message:
        update.message.reply_text(get_text('welcome', lang), reply_markup=reply_markup)
    return MAIN_MENU
def show_admin_menu(update: Update, context: CallbackContext) -> int:
    lang = get_user_lang(context)
    buttons_text = TEXTS['admin_menu'][lang]
    buttons = [[KeyboardButton(buttons_text[0]), KeyboardButton(buttons_text[1])], [KeyboardButton(buttons_text[2]), KeyboardButton(buttons_text[3])]]
    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    update.message.reply_text("⚙️ Панели администратор", reply_markup=reply_markup)
    return ADMIN_MENU
def handle_main_menu_choice(update: Update, context: CallbackContext) -> int:
    lang, text = get_user_lang(context), update.message.text
    menu_options = TEXTS['main_menu'][lang]
    if is_admin(update.effective_user.id) and text == get_text('user_menu_for_admin', lang): return show_admin_menu(update, context)
    if text == menu_options[0]: return show_categories(update, context)
    if text == menu_options[1]: return show_cart(update, context)
    if text == menu_options[2]: return contact_us(update, context)
    return MAIN_MENU
def handle_admin_menu_choice(update: Update, context: CallbackContext) -> int:
    lang, text = get_user_lang(context), update.message.text
    menu_options = TEXTS['admin_menu'][lang]
    if text == menu_options[0]: return add_product_start(update, context)
    if text == menu_options[1]: return add_category_start(update, context)
    if text == menu_options[2]: return show_statistics(update, context)
    if text == menu_options[3]: return broadcast_start(update, context)
    return ADMIN_MENU
def cancel_operation(update: Update, context: CallbackContext) -> int:
    lang = get_user_lang(context)
    keys_to_clear = [k for k in context.user_data if k.startswith('new_') or k.startswith('broadcast_')]
    for key in keys_to_clear:
        if 'photo_path' in context.user_data.get(key, {}) and os.path.exists(context.user_data[key]['photo_path']):
            os.remove(context.user_data[key]['photo_path'])
        del context.user_data[key]
    update.message.reply_text(get_text('operation_cancelled', lang))
    if is_admin(update.effective_user.id): return show_admin_menu(update, context)
    return show_main_menu(update, context)

# ... (Функсияҳои админ бе тағйирот)
def show_statistics(update: Update, context: CallbackContext) -> int:
    lang = get_user_lang(context)
    try:
        response = requests.get(f"{API_BASE_URL}/admin/stats")
        response.raise_for_status()
        stats = response.json()
        message = get_text('stats_message', lang, **stats)
        update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    except requests.RequestException as e:
        logger.error(f"Хатогии API ҳангоми гирифтани омор: {e}")
        update.message.reply_text(get_text('error_api', lang))
    return ADMIN_MENU
def broadcast_start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(get_text('ask_broadcast_message', get_user_lang(context)))
    return BROADCAST_MESSAGE
def broadcast_get_message(update: Update, context: CallbackContext) -> int:
    lang = get_user_lang(context)
    context.user_data['broadcast_message_id'] = update.message.message_id
    context.user_data['broadcast_chat_id'] = update.message.chat_id
    buttons = [[InlineKeyboardButton(get_text('yes', lang), callback_data='broadcast_yes'), InlineKeyboardButton(get_text('no', lang), callback_data='broadcast_no')]]
    reply_markup = InlineKeyboardMarkup(buttons)
    update.message.reply_text(get_text('broadcast_confirmation', lang), reply_markup=reply_markup)
    return BROADCAST_CONFIRM
def broadcast_confirm(update: Update, context: CallbackContext) -> int:
    query, lang = update.callback_query, get_user_lang(context)
    query.answer()
    if query.data == 'broadcast_no':
        for key in ['broadcast_message_id', 'broadcast_chat_id']: context.user_data.pop(key, None)
        query.edit_message_text(get_text('operation_cancelled', lang))
        return ADMIN_MENU
    query.edit_message_text(get_text('broadcast_started', lang))
    message_id, chat_id = context.user_data.pop('broadcast_message_id'), context.user_data.pop('broadcast_chat_id')
    user_ids = list(load_bot_sessions().keys())
    success_count = 0
    for user_id in user_ids:
        try:
            context.bot.copy_message(chat_id=int(user_id), from_chat_id=chat_id, message_id=message_id)
            success_count += 1
            time.sleep(0.1)
        except Exception as e:
            logger.warning(f"Паём ба корбари {user_id} фиристода нашуд: {e}")
    context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=get_text('broadcast_report', lang, success_count, len(user_ids)))
    return ADMIN_MENU
def add_category_start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(get_text('add_category_start', get_user_lang(context)))
    return ADD_CATEGORY_NAME
def add_category_get_name(update: Update, context: CallbackContext) -> int:
    lang, category_name = get_user_lang(context), update.message.text.strip()
    if not category_name:
        update.message.reply_text("Номи категория наметавонад холӣ бошад.")
        return ADD_CATEGORY_NAME
    try:
        response = requests.post(f"{API_BASE_URL}/admin/categories", json={'name': category_name})
        if response.status_code == 201:
            update.message.reply_text(get_text('category_added_success', lang, category_name))
        else:
            logger.error(f"Хатогӣ ҳангоми иловаи категория: {response.status_code} - {response.text}")
            update.message.reply_text(get_text('category_add_failed', lang))
    except requests.RequestException as e:
        logger.error(f"Хатогии API: {e}")
        update.message.reply_text(get_text('error_api', lang))
    return show_admin_menu(update, context)
def add_product_start(update: Update, context: CallbackContext) -> int:
    lang = get_user_lang(context)
    context.user_data['new_product'] = {}
    try:
        response = requests.get(f"{API_BASE_URL}/bot/categories", timeout=5)
        response.raise_for_status()
        categories = response.json()
        if not categories:
            update.message.reply_text("Аввал категория илова кунед.")
            return ADMIN_MENU
        
        buttons = []
        for cat in categories:
            # --- ИСЛОҲИ ХАТОГИИ "can't find field 'text'" ---
            # Аввал номро аз полеи нав (name_tj) мегирем, агар набошад, аз полеи кӯҳна (name)
            category_name = cat.get(f'name_{lang}') or cat.get('name')
            if category_name:
                buttons.append(InlineKeyboardButton(text=category_name, callback_data=f"addprod_cat_{cat.get('id')}"))

        if not buttons:
            update.message.reply_text("Ягон категорияи дуруст ёфт нашуд.")
            return ADMIN_MENU

        reply_markup = InlineKeyboardMarkup.from_column(buttons)
        update.message.reply_text(get_text('add_product_start', lang), reply_markup=reply_markup)
        return ADD_PRODUCT_CAT
    except requests.exceptions.RequestException as e:
        logger.error(f"Хатогии API: {e}")
        update.message.reply_text(get_text('error_api', lang))
        return ADMIN_MENU

def add_product_get_category(update: Update, context: CallbackContext) -> int:
    query, lang = update.callback_query, get_user_lang(context)
    query.answer()
    category_id = query.data.split('_')[-1]
    try:
        response = requests.get(f"{API_BASE_URL}/bot/categories", timeout=5)
        response.raise_for_status()
        category = next((c for c in response.json() if c['id'] == category_id), None)
        if not category:
             query.edit_message_text("Хатогӣ: Категория ёфт нашуд.")
             return cancel_operation(update, context)
        # --- ИСЛОҲИ ХАТОГӢ ---
        # Номро аз полеи нав ё кӯҳна мегирем
        context.user_data['new_product']['category'] = category.get(f'name_{lang}') or category.get('name_tj') or category.get('name')
    except requests.exceptions.RequestException as e:
        logger.error(f"Хатогии API: {e}")
        query.edit_message_text(get_text('error_api', lang))
        return cancel_operation(update, context)
    query.edit_message_text(get_text('ask_product_name', lang))
    return ADD_PRODUCT_NAME
def add_product_get_name(update: Update, context: CallbackContext) -> int:
    product_name = update.message.text
    context.user_data['new_product']['name'] = product_name
    context.user_data['new_product']['name_tj'] = product_name
    context.user_data['new_product']['name_ru'] = product_name
    context.user_data['new_product']['name_en'] = product_name
    context.user_data['new_product']['description'] = product_name
    context.user_data['new_product']['description_tj'] = product_name
    context.user_data['new_product']['description_ru'] = product_name
    context.user_data['new_product']['description_en'] = product_name
    update.message.reply_text(get_text('ask_price', get_user_lang(context)))
    return ADD_PRODUCT_PRICE
def add_product_get_price(update: Update, context: CallbackContext) -> int:
    try:
        context.user_data['new_product']['price'] = float(update.message.text.replace(',', '.'))
        update.message.reply_text(get_text('ask_photo', get_user_lang(context)))
        return ADD_PRODUCT_PHOTO
    except ValueError:
        update.message.reply_text("Нархро дар формати рақамӣ ворид кунед.")
        return ADD_PRODUCT_PRICE
def add_product_get_photo(update: Update, context: CallbackContext) -> int:
    if not update.message.photo:
        update.message.reply_text("Лутфан акс фиристед.")
        return ADD_PRODUCT_PHOTO
    photo_file = update.message.photo[-1].get_file()
    os.makedirs('temp_uploads', exist_ok=True)
    file_path = os.path.join('temp_uploads', f"{photo_file.file_id}.jpg")
    photo_file.download(custom_path=file_path)
    context.user_data['new_product']['photo_path'] = file_path
    context.user_data['new_product']['inventory'] = []
    update.message.reply_text(get_text('ask_inventory', get_user_lang(context)))
    return ADD_PRODUCT_INVENTORY
def add_product_get_inventory(update: Update, context: CallbackContext) -> int:
    lang, text = get_user_lang(context), update.message.text.lower().strip()
    if text in ['тамом', 'готово', 'done']: return add_product_confirm_and_send(update, context)
    try:
        size, quantity = text.split()
        context.user_data['new_product']['inventory'].append({"size": size.upper(), "quantity": int(quantity)})
        update.message.reply_text(get_text('inventory_added', lang, size.upper(), int(quantity)))
    except (ValueError, IndexError):
        update.message.reply_text("Формати нодуруст. Намуна: M 5")
    return ADD_PRODUCT_INVENTORY
def add_product_confirm_and_send(update: Update, context: CallbackContext):
    lang = get_user_lang(context)
    product_data = context.user_data.pop('new_product', None)
    if not product_data or 'photo_path' not in product_data:
        return cancel_operation(update, context)
    # --- ИСЛОҲ: Ҳамаи полеҳои номро мефиристем ---
    form_payload = {
        'category': product_data['category'], 
        'name': product_data['name'],
        'name_tj': product_data['name_tj'],
        'name_ru': product_data['name_ru'],
        'name_en': product_data['name_en'],
        'description': product_data['description'],
        'description_tj': product_data['description_tj'],
        'description_ru': product_data['description_ru'],
        'description_en': product_data['description_en'],
        'price': product_data['price'], 
        'inventory': json.dumps(product_data['inventory'])
    }
    photo_path = product_data['photo_path']
    try:
        with open(photo_path, 'rb') as photo_file:
            files = {'image': (os.path.basename(photo_path), photo_file, 'image/jpeg')}
            response = requests.post(f"{API_BASE_URL}/admin/products", data=form_payload, files=files, timeout=10)
            response.raise_for_status()
        update.message.reply_text(get_text('product_added_success', lang))
    except requests.exceptions.RequestException as e:
        logger.error(f"Хатогии API: {e}")
        error_text = e.response.text if e.response else 'Сервер ҷавоб надод'
        update.message.reply_text(f"🔴 Хатогӣ дар сервер: {error_text}")
    finally:
        if os.path.exists(photo_path): os.remove(photo_path)
    return show_admin_menu(update, context)

def show_categories(update: Update, context: CallbackContext) -> int:
    lang = get_user_lang(context)
    try:
        response = requests.get(f"{API_BASE_URL}/bot/categories", timeout=5)
        response.raise_for_status()
        categories = response.json()
        if not categories:
            update.message.reply_text(get_text('no_products', lang))
            return MAIN_MENU
        
        buttons = []
        for cat in categories:
            # --- ИСЛОҲИ ХАТОГИИ "can't find field 'text'" ---
            # Аввал номро аз полеи нав (name_tj) мегирем, агар набошад, аз полеи кӯҳна (name)
            category_name = cat.get(f'name_{lang}') or cat.get('name')
            if category_name:
                buttons.append(InlineKeyboardButton(text=category_name, callback_data=f"cat_{cat.get('id')}"))

        if not buttons:
            update.message.reply_text("Ягон категорияи дуруст ёфт нашуд.")
            return MAIN_MENU

        reply_markup = InlineKeyboardMarkup.from_column(buttons)
        update.message.reply_text(get_text('choose_category', lang), reply_markup=reply_markup)
        return SHOWING_CATEGORIES
    except requests.exceptions.RequestException as e:
        logger.error(f"Хатогии API: {e}")
        update.message.reply_text(get_text('error_api', lang))
        return MAIN_MENU

def show_products(update: Update, context: CallbackContext) -> int:
    query, lang = update.callback_query, get_user_lang(context)
    query.answer()
    category_id = query.data.split('_', 1)[1]
    try:
        response = requests.get(f"{API_BASE_URL}/bot/products?category_id={category_id}", timeout=5)
        response.raise_for_status()
        products = response.json()
        if not products:
            query.message.reply_text(get_text('no_products', lang))
            return SHOWING_CATEGORIES
        for product in products:
            # --- ИСЛОҲ: Истифодаи номи мувофиқ ---
            product_name = product.get(f'name_{lang}') or product.get('name_tj')
            caption = f"**{product_name}**\n\n**Нарх:** {product.get('price')} сомонӣ"
            buttons = [InlineKeyboardButton(get_text('add_to_cart', lang), callback_data=f"add_{product.get('id')}")]
            reply_markup = InlineKeyboardMarkup([buttons])
            image_url = product.get('image_url', 'https://placehold.co/600x400?text=No+Image')
            try:
                query.message.reply_photo(photo=image_url, caption=caption, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
            except Exception as e:
                logger.error(f"Хатогӣ ҳангоми фиристодани акс ({image_url}): {e}")
                error_text = f"Хатогӣ дар нишон додани акси '{product_name}'."
                if '127.0.0.1' in image_url: error_text += "\n\n**Сабаб:** Сервер бояд дар хостинги онлайн бошад."
                query.message.reply_text(f"{error_text}\n\n{caption}", parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return SHOWING_PRODUCTS
    except requests.exceptions.RequestException as e:
        logger.error(f"Хатогии API: {e}")
        query.message.reply_text(get_text('error_api', lang))
        return SHOWING_CATEGORIES
def add_to_cart_start(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    context.user_data['current_product_id'] = int(query.data.split('_')[1])
    query.message.reply_text(get_text('enter_quantity', get_user_lang(context)))
    return ADDING_TO_CART_QUANTITY
def add_to_cart_quantity(update: Update, context: CallbackContext) -> int:
    try:
        quantity = int(update.message.text)
        if quantity <= 0: raise ValueError
    except (ValueError, TypeError):
        update.message.reply_text("Лутфан рақами дуруст ворид кунед.")
        return ADDING_TO_CART_QUANTITY
    product_id, user_id = context.user_data.pop('current_product_id', None), str(update.message.from_user.id)
    if not product_id: return show_main_menu(update, context)
    sessions = load_bot_sessions()
    user_cart = sessions.setdefault(user_id, {'lang': get_user_lang(context), 'cart': []}).setdefault('cart', [])
    item = next((item for item in user_cart if item.get('id') == product_id), None)
    if item: item['quantity'] += quantity
    else: user_cart.append({'id': product_id, 'quantity': quantity})
    save_bot_sessions(sessions)
    update.message.reply_text(get_text('added_to_cart', get_user_lang(context)))
    return show_main_menu(update, context)
def show_cart(update: Update, context: CallbackContext) -> int:
    user_id, lang = str(update.message.from_user.id), get_user_lang(context)
    user_cart = load_bot_sessions().get(user_id, {}).get('cart', [])
    if not user_cart:
        update.message.reply_text(get_text('cart_is_empty', lang))
        return MAIN_MENU
    try:
        response = requests.get(f"{API_BASE_URL}/bot/products", timeout=5)
        response.raise_for_status()
        all_products = {p['id']: p for p in response.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f"Хатогии API: {e}")
        update.message.reply_text(get_text('error_api', lang))
        return MAIN_MENU
    cart_text, total_price = get_text('your_cart', lang) + "\n\n", 0
    for i, item in enumerate(user_cart, 1):
        product = all_products.get(item.get('id'))
        if product:
            price = float(product.get('price', 0)) * item.get('quantity', 0)
            total_price += price
            product_name = product.get(f'name_{lang}') or product.get('name_tj')
            cart_text += f"{i}. {product_name} (x{item.get('quantity')}) - **{price:.2f} сомонӣ**\n"
    cart_text += f"\n{get_text('total_price', lang)} **{total_price:.2f} сомонӣ**"
    buttons = [[InlineKeyboardButton(get_text('checkout', lang), callback_data='checkout'), InlineKeyboardButton(get_text('clear_cart', lang), callback_data='clear_cart')], [InlineKeyboardButton(get_text('back', lang), callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(buttons)
    update.message.reply_text(cart_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    return SHOWING_PRODUCTS
def handle_cart_actions(update: Update, context: CallbackContext) -> int:
    query, user_id, lang = update.callback_query, str(update.callback_query.from_user.id), get_user_lang(context)
    query.answer()
    if query.data == 'clear_cart':
        sessions = load_bot_sessions()
        if user_id in sessions: sessions[user_id]['cart'] = []
        save_bot_sessions(sessions)
        query.edit_message_text(get_text('cart_is_empty', lang))
        return show_main_menu(update, context)
    if query.data == 'checkout':
        query.edit_message_text(get_text('enter_address', lang))
        return CHECKOUT_ADDRESS
    if query.data == 'back_to_menu':
        return show_main_menu(update, context)
    return SHOWING_PRODUCTS
def get_address(update: Update, context: CallbackContext) -> int:
    context.user_data['address'] = update.message.text
    update.message.reply_text(get_text('enter_phone', get_user_lang(context)))
    return CHECKOUT_PHONE
def get_phone_and_confirm(update: Update, context: CallbackContext) -> int:
    user, user_id_str, lang = update.message.from_user, str(update.message.from_user.id), get_user_lang(context)
    user_cart = load_bot_sessions().get(user_id_str, {}).get('cart', [])
    if not user_cart:
        update.message.reply_text(get_text('cart_is_empty', lang))
        return show_main_menu(update, context)
    try:
        response = requests.get(f"{API_BASE_URL}/bot/products", timeout=5)
        response.raise_for_status()
        all_products = {p['id']: p for p in response.json()}
        cart_details = []
        total_price = 0
        for item in user_cart:
            product = all_products.get(item['id'])
            if product:
                price = float(product.get('price', 0)) * item.get('quantity', 0)
                total_price += price
                product_name = product.get(f'name_{lang}') or product.get('name_tj')
                cart_details.append({'name': product_name, 'quantity': item['quantity'], 'price': price})
    except requests.exceptions.RequestException as e:
        logger.error(f"Хатогии API: {e}")
        update.message.reply_text(get_text('error_api', lang))
        return show_main_menu(update, context)
    order_data = {"userId": user_id_str, "userName": user.full_name, "address": context.user_data.pop('address', 'Номаълум'), "phone": update.message.text, "cart": user_cart, "total": total_price}
    try:
        response = requests.post(f"{API_BASE_URL}/orders", json=order_data, timeout=10)
        response.raise_for_status()
        order_id = response.json().get('order_id', 'N/A')
        sessions = load_bot_sessions()
        sessions[user_id_str]['cart'] = []
        save_bot_sessions(sessions)
        update.message.reply_text(get_text('order_confirmed', lang, order_id), parse_mode=ParseMode.MARKDOWN)
        notify_admin_new_order(context, {**order_data, 'id': order_id, 'user': user, 'cart_details': cart_details})
    except requests.exceptions.RequestException as e:
        logger.error(f"Хатогии API ҳангоми сохтани фармоиш: {e}")
        update.message.reply_text(f"🔴 Хатогӣ: {e.response.json().get('error', 'Фармоиш қабул нашуд.')}" if e.response else get_text('error_api', lang))
    return show_main_menu(update, context)
def contact_us(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(get_text('contact_info', get_user_lang(context)), parse_mode=ParseMode.MARKDOWN)
    return MAIN_MENU
def main() -> None:
    # Тафтиш мекунем, ки оё BOT_TOKEN аз муҳити система гирифта шудааст
    if not BOT_TOKEN:
        logger.critical("!!! ХАТОГИИ КРИТИКӢ: BOT_TOKEN дар муҳити система ёфт нашуд!")
        logger.critical("Лутфан, онро дар танзимоти хостинги худ ҳамчун 'Environment Variable' илова кунед.")
        return
        
    if not os.path.exists(BOT_SESSIONS_FILE):
        with open(BOT_SESSIONS_FILE, 'w', encoding='utf-8') as f: json.dump({}, f)
        
    updater = Updater(BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECTING_LANGUAGE: [MessageHandler(Filters.regex('^(🇹🇯 Тоҷикӣ|🇷🇺 Русский|🇬🇧 English)$'), set_language)],
            MAIN_MENU: [MessageHandler(Filters.text & ~Filters.command, handle_main_menu_choice)],
            ADMIN_MENU: [MessageHandler(Filters.text & ~Filters.command, handle_admin_menu_choice)],
            ADD_CATEGORY_NAME: [MessageHandler(Filters.text & ~Filters.command, add_category_get_name)],
            ADD_PRODUCT_CAT: [CallbackQueryHandler(add_product_get_category, pattern='^addprod_cat_')],
            ADD_PRODUCT_NAME: [MessageHandler(Filters.text & ~Filters.command, add_product_get_name)],
            ADD_PRODUCT_PRICE: [MessageHandler(Filters.text & ~Filters.command, add_product_get_price)],
            ADD_PRODUCT_PHOTO: [MessageHandler(Filters.photo, add_product_get_photo)],
            ADD_PRODUCT_INVENTORY: [MessageHandler(Filters.text & ~Filters.command, add_product_get_inventory)],
            BROADCAST_MESSAGE: [MessageHandler(Filters.all & ~Filters.command, broadcast_get_message)],
            BROADCAST_CONFIRM: [CallbackQueryHandler(broadcast_confirm, pattern='^broadcast_')],
            SHOWING_CATEGORIES: [CallbackQueryHandler(show_products, pattern='^cat_')],
            SHOWING_PRODUCTS: [CallbackQueryHandler(add_to_cart_start, pattern='^add_'), CallbackQueryHandler(handle_cart_actions, pattern='^(checkout|clear_cart|back_to_menu)$')],
            ADDING_TO_CART_QUANTITY: [MessageHandler(Filters.text & ~Filters.command, add_to_cart_quantity)],
            CHECKOUT_ADDRESS: [MessageHandler(Filters.text & ~Filters.command, get_address)],
            CHECKOUT_PHONE: [MessageHandler(Filters.text & ~Filters.command, get_phone_and_confirm)],
        },
        fallbacks=[CommandHandler('cancel', cancel_operation), CommandHandler('start', start)],
        name="main_conversation", per_user=True, per_message=False,
    )
    dispatcher.add_handler(conv_handler)
    logger.info("Бот ба кор оғоз мекунад...")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
