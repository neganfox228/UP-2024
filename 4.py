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
admin_requests = {}

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
                             "Вы выбрали прошедшую дату. Пожалуйста, начните сначала.")
            send_welcome(message)
            return
        user_id = save_user_info(full_name, departure_date, user_id)
        bot.send_message(message.chat.id, "Спасибо! Ваша заявка отправлена на рассмотрение.")
    except ValueError:
        bot.send_message(message.chat.id, "Некорректный формат даты.")
        send_welcome(message)

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

    bot.send_message(user_id, "Ваша заявка одобрена!", reply_markup=create_main_menu_keyboard())

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
        cur.execute("SELECT dish_id, dish_name, dish_description, meal FROM dishes")
        dishes = cur.fetchall()
        if dishes:
            menu_by_meal = {}
            for dish in dishes:
                dish_id, dish_name, dish_description, meal = dish
                if meal not in menu_by_meal:
                    menu_by_meal[meal] = []
                menu_by_meal[meal].append((dish_id, dish_name, dish_description))

            response = "Меню:\n\n"
            for meal, meal_dishes in menu_by_meal.items():
                response += f"{meal.capitalize()}:\n"
                for dish_id, dish_name, dish_description in meal_dishes:
                    response += f"{dish_id}. {dish_name}\n{dish_description}\n"
                response += "\n"
            bot.send_message(message.chat.id, response)
        else:
            bot.send_message(message.chat.id, "Меню пусто.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при получении меню.")

@bot.message_handler(func=lambda message: message.text == 'Заказать')
def select_meal(message):
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Завтрак"), types.KeyboardButton("Обед"), types.KeyboardButton("Ужин"))
    msg = bot.reply_to(message, "Выберите время приема пищи:", reply_markup=keyboard)
    user_states[message.from_user.id] = {'meal': None}
    bot.register_next_step_handler(msg, show_menu_by_meal)

def show_menu_by_meal(message):
    meal = message.text.lower()
    user_id = message.from_user.id
    user_states[user_id]['meal'] = meal
    try:
        cur.execute("SELECT dish_id, dish_name, dish_description FROM dishes WHERE meal = %s", (meal,))
        dishes = cur.fetchall()
        if dishes:
            response = f"Меню на {meal}:\n"
            for dish in dishes:
                dish_id, dish_name, dish_description = dish
                response += f"{dish_id}. {dish_name}\n{dish_description}\n\n"
            bot.send_message(message.chat.id, response)
            msg = bot.reply_to(message, "Введите ID блюда:")
            bot.register_next_step_handler(msg, confirm_order)
        else:
            bot.send_message(message.chat.id, f"Меню на {meal} пусто.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при получении меню на {meal}.")

def confirm_order(message):
    try:
        dish_ids = [int(dish_id.strip()) for dish_id in message.text.split(',')]
        user_id = message.from_user.id
        current_date = datetime.datetime.now().date()
        delivery_date = current_date + datetime.timedelta(days=2)
        time = user_states[user_id]['meal']

        cur.execute("SELECT dish_id FROM dishes WHERE dish_id = ANY(%s)", (dish_ids,))
        existing_dish_ids = [row[0] for row in cur.fetchall()]
        non_existent_dishes = [dish_id for dish_id in dish_ids if dish_id not in existing_dish_ids]

        if non_existent_dishes:
            non_existent_dishes_str = ', '.join(str(dish_id) for dish_id in non_existent_dishes)
            bot.send_message(message.chat.id, f"Блюд с ID {non_existent_dishes_str} не существует.")
            bot.send_message(message.chat.id, "Выберите действие:", reply_markup=create_main_menu_keyboard())
            return

        cur.execute("SELECT dish_id, meal FROM dishes WHERE dish_id = ANY(%s)", (dish_ids,))
        dishes_info = cur.fetchall()
        invalid_dishes = []
        for dish_id, meal in dishes_info:
            if meal != time:
                invalid_dishes.append(dish_id)

        if invalid_dishes:
            invalid_dishes_str = ', '.join(str(dish_id) for dish_id in invalid_dishes)
            bot.send_message(message.chat.id, f"Блюда с ID {invalid_dishes_str} не соответствуют выбранному времени приема пищи.")
            bot.send_message(message.chat.id, "Выберите действие:", reply_markup=create_main_menu_keyboard())
            return

        cur.execute("INSERT INTO orders (user_id, delivery_date, time, status) VALUES (%s, %s, %s, 'активный') RETURNING order_id",
                    (user_id, delivery_date, time))
        order_id = cur.fetchone()[0]
        for dish_id in dish_ids:
            cur.execute("INSERT INTO order_dishes (order_id, dish_id) VALUES (%s, %s)", (order_id, dish_id))
        conn.commit()

        bot.send_message(message.chat.id, "Ваш заказ успешно оформлен!",
                        reply_markup=create_main_menu_keyboard())
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при оформлении заказа: {e}")
        bot.send_message(message.chat.id, "Выберите действие:", reply_markup=create_main_menu_keyboard())

@bot.message_handler(func=lambda message: message.text == 'Отменить заказ')
def cancel_order(message):
    user_id = message.from_user.id
    cur.execute("SELECT order_id, delivery_date, time FROM orders WHERE user_id = %s AND status = 'активный'", (user_id,))
    active_orders = cur.fetchall()
    if active_orders:
        response = "Ваши активные заказы:\n"
        for order in active_orders:
            order_id, delivery_date, time = order
            response += f"ID заказа: {order_id}, Время подачи: {delivery_date}, Время: {time}\n"
        bot.send_message(message.chat.id, response)
        msg = bot.reply_to(message, "Введите ID заказа для отмены:")
        bot.register_next_step_handler(msg, confirm_cancel_order)
    else:
        bot.send_message(message.chat.id, "У вас нет активных заказов.")
        bot.send_message(message.chat.id, "Выберите действие:", reply_markup=create_main_menu_keyboard())

def confirm_cancel_order(message):
    try:
        order_id = int(message.text)
        user_id = message.from_user.id
        cur.execute("SELECT order_id FROM orders WHERE user_id = %s AND order_id = %s AND status = 'активный'", (user_id, order_id))
        order = cur.fetchone()
        if order:
            cur.execute("UPDATE orders SET status = 'отменен' WHERE order_id = %s", (order_id,))
            conn.commit()
            bot.send_message(message.chat.id, f"Заказ с ID {order_id} был успешно отменен.")
            bot.send_message(message.chat.id, "Выберите действие:", reply_markup=create_main_menu_keyboard())
        else:
            bot.send_message(message.chat.id, "Заказ с указанным ID не найден или уже был обработан.")
            bot.send_message(message.chat.id, "Выберите действие:", reply_markup=create_main_menu_keyboard())
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректный ID заказа.")
        bot.send_message(message.chat.id, "Выберите действие:", reply_markup=create_main_menu_keyboard())

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
        button4 = types.KeyboardButton("Сделать отчет")
        keyboard.add(button1, button2, button3, button4)
        msg = bot.reply_to(message, "Вы успешно авторизованы. Выберите действие:", reply_markup=keyboard)
        bot.register_next_step_handler(msg, process_admin_choice)
    else:
        bot.reply_to(message, "Неверный пароль.")

def process_admin_choice(message):
    if message.text == "Просмотр заявок":
        pass
    elif message.text == "Просмотр заказов":
        pass
    elif message.text == "Пользователи":
        pass
    elif message.text == "Сделать отчет":
        pass
    else:
        bot.send_message(message.chat.id, "Некорректный выбор. Пожалуйста, используйте кнопки на клавиатуре.")

bot.polling()