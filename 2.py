import telebot
from telebot import types
import psycopg2
import datetime

conn = psycopg2.connect(user="postgres",
                        password="0000",
                        host="127.0.0.1",
                        port="5432",
                        database="stol")
cur = conn.cursor()

bot = telebot.TeleBot("6525136024:AAFpVOa0ClnokyDW5DKR8W9LgMYbMQ1gkaQ")

user_states = {}
admin_password = "123"
admin_requests = {}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id

    cur.execute("SELECT status FROM users WHERE username = %s", (str(user_id),))
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
    full_name = message.text
    user_id = message.from_user.id
    user_states[user_id]['full_name'] = full_name
    msg = bot.reply_to(message, "Введите дату выезда в формате ДД.ММ.ГГГГ (например, 01.01.2024):")
    bot.register_next_step_handler(msg, process_departure_date)

def process_departure_date(message):
    date_text = message.text
    user_id = message.from_user.id
    full_name = user_states[user_id]['full_name'] 

    try:
        departure_date = datetime.datetime.strptime(date_text, '%d.%m.%Y').date()
        today = datetime.datetime.now().date()

        if departure_date < today:
            bot.send_message(message.chat.id,
                             "Вы выбрали прошедшую дату. Пожалуйста, выберите сегодняшнюю дату или будущую.")
            ask_departure_date(message)
            return

        user_id = save_user_info(full_name, departure_date, user_id)  
        bot.send_message(message.chat.id, "Спасибо! Ваша заявка отправлена на рассмотрение.")
    except ValueError:
        bot.send_message(message.chat.id, "Некорректный формат даты.")
        # Предложить пользователю ввести дату выезда заново
        ask_departure_date(message)

def save_user_info(full_name, departure_date, user_id):
    sql = "INSERT INTO users (full_name, departure_date, status, username) VALUES (%s, %s, 'ожидание', %s) RETURNING user_id"
    cur.execute(sql, (full_name, departure_date, user_id))
    user_id = cur.fetchone()[0]
    conn.commit()
    return user_id

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
        bot.send_message(message.chat.id, f"Ошибка при получении меню: {e}")

@bot.message_handler(func=lambda message: message.text == 'Заказать')
def start_ordering(message):
    try:
        cur.execute("SELECT dish_id, dish_name FROM dishes")
        dishes = cur.fetchall()

        if dishes:
            keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
            for dish in dishes:
                dish_id, dish_name = dish
                keyboard.add(types.KeyboardButton(f"{dish_id}. {dish_name}"))

            msg = bot.reply_to(message, "Выберите блюдо из меню:", reply_markup=keyboard)
            bot.register_next_step_handler(msg, select_dish)
        else:
            bot.send_message(message.chat.id, "Меню пусто.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при получении меню: {e}")

def select_dish(message):
    try:
        dish_id = int(message.text.split(".")[0])
        user_id = message.from_user.id

        cur.execute("SELECT dish_name FROM dishes WHERE dish_id = %s", (dish_id,))
        dish_name = cur.fetchone()[0]

        keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        keyboard.add(types.KeyboardButton("Завтрак"), types.KeyboardButton("Обед"), types.KeyboardButton("Ужин"))
        msg = bot.reply_to(message, f"Вы выбрали: {dish_name}. Выберите время подачи:", reply_markup=keyboard)
        bot.register_next_step_handler(msg, confirm_order, dish_id)
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при выборе блюда: {e}")

def confirm_order(message, dish_id):
    try:
        time = message.text.lower()
        user_id = message.from_user.id

        current_date = datetime.datetime.now().date()

        delivery_date = current_date + datetime.timedelta(days=2)

        cur.execute("INSERT INTO orders (username, dish_id, delivery_date, time, status) VALUES (%s, %s, %s, %s, %s)",
                    (user_id, dish_id, delivery_date, time, 'ожидание'))
        conn.commit()

        bot.send_message(message.chat.id, "Ваш заказ успешно оформлен!")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при оформлении заказа: {e}")

bot.polling()