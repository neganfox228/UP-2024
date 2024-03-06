import telebot
from telebot import types
import psycopg2
import datetime

conn = psycopg2.connect(user="postgres",
                        password="0000",
                        host="127.0.0.1",
                        port="5432",
                        database="shved_stol")
cur = conn.cursor()
bot = telebot.TeleBot("6525136024:AAFpVOa0ClnokyDW5DKR8W9LgMYbMQ1gkaQ")
user_states = {}
admin_password = "123"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    cur.execute("SELECT status FROM users WHERE user_id = %s", (str(user_id),))
    user_status = cur.fetchone()
    if user_status and user_status[0] == 'активный':
        bot.send_message(message.chat.id, "Выберите действие:", reply_markup=create_main_menu_keyboard())
    elif user_status and user_status[0] == 'ожидание':
        bot.send_message(message.chat.id, "Ваша заявка на рассмотрении. Пожалуйста, подождите.")
    else:
        keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        button = types.KeyboardButton("Авторизоваться")
        keyboard.add(button)
        msg = bot.reply_to(message, "Добро пожаловать! Нажмите кнопку 'Авторизоваться' для начала:", reply_markup=keyboard)
        bot.register_next_step_handler(msg, ask_full_name)

def ask_full_name(message):
    if message.text == 'Авторизоваться':
        user_id = message.from_user.id
        user_states[user_id] = {}
        msg = bot.reply_to(message, "Введите ваше ФИО:")
        bot.register_next_step_handler(msg, ask_departure_date)
    else:
        bot.reply_to(message, "Пожалуйста, воспользуйтесь кнопкой 'Авторизоваться'.")

def ask_departure_date(message):
    user_id = message.from_user.id
    user_states[user_id]['full_name'] = message.text
    msg = bot.reply_to(message, "Введите дату выезда в формате ДД.ММ.ГГГГ (например, 01.01.2024):")
    bot.register_next_step_handler(msg, process_departure_date)

def process_departure_date(message):
    user_id = message.from_user.id
    user_states[user_id]['departure_date'] = message.text

    save_user_info(user_states[user_id]['full_name'], user_states[user_id]['departure_date'], user_id)

def save_user_info(full_name, departure_date, user_id):
    cur.execute("SELECT EXISTS (SELECT 1 FROM users WHERE user_id = %s)", (user_id,))
    user_exists = cur.fetchone()[0]

    if user_exists:
        sql = "UPDATE users SET full_name = %s, departure_date = %s, status = 'активный' WHERE user_id = %s"
        cur.execute(sql, (full_name, departure_date, user_id))
    else:
        sql = "INSERT INTO users (full_name, departure_date, status, user_id) VALUES (%s, %s, 'активный', %s) RETURNING user_id"
        cur.execute(sql, (full_name, departure_date, user_id))
        user_id = cur.fetchone()[0]
    conn.commit()

    bot.send_message(user_id, "Ваша заявка одобрена! Теперь вы авторизованы.", reply_markup=create_main_menu_keyboard())

def create_main_menu_keyboard():
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Меню"))
    keyboard.add(types.KeyboardButton("Заказать"))
    keyboard.add(types.KeyboardButton("Отменить заказ"))
    return keyboard

@bot.message_handler(func=lambda message: message.text == 'Меню')
def show_menu(message):
    try:
        cur.execute("SELECT dish_id, dish_name, dish_description FROM dishes")
        dishes = cur.fetchall()
        if dishes:
            response = "Меню:\n"
            for dish in dishes:
                dish_id, dish_name, dish_description = dish
                response += f"{dish_id}. {dish_name}\n{dish_description}\n\n"
            bot.send_message(message.chat.id, response)
        else:
            bot.send_message(message.chat.id, "Меню пусто.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при получении меню.")

@bot.message_handler(func=lambda message: message.text == 'Заказать')
def start_ordering(message):
    try:
        cur.execute("SELECT dish_id, dish_name FROM dishes")
        dishes = cur.fetchall()
        if dishes:
            response = "Выберите блюдо из меню:\n"
            for dish in dishes:
                dish_id, dish_name = dish
                response += f"{dish_id}. {dish_name}\n"
            bot.send_message(message.chat.id, response)
            msg = bot.reply_to(message, "Введите ID блюда:")
            bot.register_next_step_handler(msg, select_dish_by_id)
        else:
            bot.send_message(message.chat.id, "Меню пусто.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при получении меню.")

def select_dish_by_id(message):
    try:
        dish_id = int(message.text)
        user_id = message.from_user.id
        cur.execute("SELECT dish_name FROM dishes WHERE dish_id = %s", (dish_id,))
        dish = cur.fetchone()
        if dish:
            dish_name = dish[0]
            keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
            keyboard.add(types.KeyboardButton("Завтрак"), types.KeyboardButton("Обед"), types.KeyboardButton("Ужин"))
            msg = bot.reply_to(message, f"Вы выбрали: {dish_name}. Выберите время подачи:", reply_markup=keyboard)
            bot.register_next_step_handler(msg, confirm_order, dish_id)
        else:
            bot.send_message(message.chat.id, "Блюдо с указанным ID не найдено.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при выборе блюда.")

def confirm_order(message, dish_id):
    try:
        time = message.text.lower()
        user_id = message.from_user.id
        current_date = datetime.datetime.now().date()
        delivery_date = current_date + datetime.timedelta(days=2)
        cur.execute("INSERT INTO orders (user_id, dish_id, delivery_date, time, status) VALUES (%s, %s, %s, %s, %s)",
                    (user_id, dish_id, delivery_date, time, 'ожидание'))
        conn.commit()
        bot.send_message(message.chat.id, "Заявка с заказом одобрена!", reply_markup=create_main_menu_keyboard())
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при оформлении заказа.")

@bot.message_handler(func=lambda message: message.text == 'Отменить заказ')
def cancel_order(message):
    user_id = message.from_user.id
    cancel_all_pending_orders(user_id)
    bot.send_message(message.chat.id, "Все ваши заказы со статусом 'ожидание' были успешно отменены.")
    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=create_main_menu_keyboard())

def cancel_all_pending_orders(user_id):
    cur.execute("UPDATE orders SET status = 'отменен' WHERE user_id = %s AND status = 'ожидание'", (user_id,))
    conn.commit()


@bot.message_handler(commands=['admin'])
def admin_panel(message):
    msg = bot.reply_to(message, "Введите пароль для доступа к админ панели:")
    bot.register_next_step_handler(msg, check_admin_password)

def check_admin_password(message):
    if message.text == admin_password:
        keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        button1 = types.KeyboardButton("Просмотр заявок")
        button2 = types.KeyboardButton("Просмотр заказов")
        button3 = types.KeyboardButton("Пользователи")
        keyboard.add(button1, button2, button3)
        msg = bot.reply_to(message, "Вы успешно авторизованы. Выберите действие:", reply_markup=keyboard)
    else:
        bot.reply_to(message, "Неверный пароль.")

bot.polling()