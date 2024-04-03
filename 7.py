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
        sql = "UPDATE users SET full_name = %s, departure_date = %s, status = 'ожидание' WHERE user_id = %s"
        cur.execute(sql, (full_name, departure_date, user_id))
    else:
        sql = "INSERT INTO users (full_name, departure_date, status, user_id) VALUES (%s, %s, 'ожидание', %s) RETURNING user_id"
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

        cur.execute("INSERT INTO orders (user_id, delivery_date, time, status) VALUES (%s, %s, %s, %s) RETURNING order_id",
                    (user_id, delivery_date, time, 'ожидание'))
        order_id = cur.fetchone()[0]
        for dish_id in dish_ids:
            cur.execute("INSERT INTO order_dishes (order_id, dish_id) VALUES (%s, %s)", (order_id, dish_id))
        conn.commit()

        bot.send_message(message.chat.id, "Ваш заказ отправлен на рассмотрение, ожидайте!",
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
            keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
            button1 = types.KeyboardButton("Отменить")
            button2 = types.KeyboardButton("Назад")
            keyboard.add(button1, button2)
            msg = bot.reply_to(message, "Вы уверены, что хотите отменить этот заказ?", reply_markup=keyboard)
            bot.register_next_step_handler(msg, process_cancel_order, order_id)
        else:
            bot.send_message(message.chat.id, "Заказ с указанным ID не найден или уже был обработан.")
            bot.send_message(message.chat.id, "Выберите действие:", reply_markup=create_main_menu_keyboard())
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректный ID заказа.")
        bot.send_message(message.chat.id, "Выберите действие:", reply_markup=create_main_menu_keyboard())

def process_cancel_order(message, order_id):
    choice = message.text
    if choice == "Отменить":
        try:
            cur.execute("UPDATE orders SET status = 'отменен' WHERE order_id = %s", (order_id,))
            conn.commit()
            bot.send_message(message.chat.id, f"Заказ с ID {order_id} был успешно отменен.")
            bot.send_message(message.chat.id, "Выберите действие:", reply_markup=create_main_menu_keyboard())
        except Exception as e:
            bot.send_message(message.chat.id, f"Ошибка при отмене заказа: {e}")
            bot.send_message(message.chat.id, "Выберите действие:", reply_markup=create_main_menu_keyboard())
    elif choice == "Назад":
        bot.send_message(message.chat.id, "Отмена заказа отменена.")
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
        bot.register_next_step_handler(msg, admin_actions)
    else:
        bot.reply_to(message, "Неверный пароль.")

def admin_actions(message):
    if message.text == "Просмотр заявок":
        view_requests(message)
    elif message.text == "Просмотр заказов":
        view_orders(message)
    elif message.text == "Пользователи":
        view_users(message)
    elif message.text == "Сделать отчет":
        generate_report(message)

def generate_report(message):
    try:
        cur.execute("SELECT COUNT(*) FROM users WHERE status = 'активный'")
        new_users_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM orders")
        total_orders_count = cur.fetchone()[0]

        report_message = f"Отчет:\n\nОбщее количество пользователей: {new_users_count}\nОбщее количество заказов: {total_orders_count}"
        bot.send_message(message.chat.id, report_message)
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при создании отчета: {e}")

def view_users(message):
    try:
        cur.execute("SELECT user_id, full_name, departure_date FROM users WHERE status = 'активный'")
        users = cur.fetchall()
        if users:
            for user in users:
                user_id, full_name, departure_date = user
                msg = f"User ID: {user_id}\nФИО: {full_name}\nДата выезда: {departure_date}\n"
                bot.send_message(message.chat.id, msg)
            select_user_action_menu(message)
        else:
            bot.send_message(message.chat.id, "Активных пользователей нет.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при просмотре активных пользователей: {e}")

def select_user_action_menu(message):
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Назад"))
    keyboard.add(types.KeyboardButton("Удалить пользователя"))
    msg = bot.reply_to(message, "Выберите действие:", reply_markup=keyboard)
    bot.register_next_step_handler(msg, handle_user_action_selection)

def handle_user_action_selection(message):
    if message.text == "Назад":
        admin_actions_with_buttons(message)
    elif message.text == "Удалить пользователя":
        select_user_to_delete(message)

def select_user_to_delete(message):
    try:
        msg = bot.reply_to(message, "Введите ID пользователя для удаления или нажмите кнопку 'Назад':")
        bot.register_next_step_handler(msg, delete_user)
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка: {e}")

def delete_user(message):
    try:
        if message.text.lower() == "назад":
            view_users(message)
        else:
            user_id = int(message.text)
            cur.execute("DELETE FROM orders WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
            conn.commit()
            bot.send_message(message.chat.id, f"Пользователь с ID {user_id} был успешно удален из базы данных вместе со всеми его заказами.")
            remove_keyboard = types.ReplyKeyboardRemove()
            bot.send_message(user_id, "Вы были удалены из базы данных. Вы можете авторизоваться, введите /start.",
                             reply_markup=remove_keyboard)
            admin_actions_with_buttons(message)
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при удалении пользователя: {e}")

def view_orders(message):
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Заказы в ожидании"), types.KeyboardButton("Отмененные заказы"), types.KeyboardButton("Назад"))
    msg = bot.reply_to(message, "Выберите тип заказов для просмотра:", reply_markup=keyboard)
    bot.register_next_step_handler(msg, handle_order_type_selection)

def handle_order_type_selection(message):
    if message.text == "Заказы в ожидании":
        view_pending_orders(message)
    elif message.text == "Отмененные заказы":
        view_cancelled_orders(message)
    elif message.text == "Назад":
        admin_actions_with_buttons(message)

def view_cancelled_orders(message):
    try:
        cur.execute("SELECT order_id, user_id, delivery_date, time FROM orders WHERE status = 'отменен'")
        orders = cur.fetchall()
        if orders:
            for order in orders:
                order_id, user_id, delivery_date, time = order
                cur.execute("SELECT dish_id FROM order_dishes WHERE order_id = %s", (order_id,))
                dish_ids = cur.fetchall()
                dish_id_str = ', '.join(str(dish[0]) for dish in dish_ids)
                msg = f"ID заявки: {order_id}\nID клиента: {user_id}\nДата подачи: {delivery_date}\nВремя: {time}\nБлюдо: {dish_id_str}\n"
                bot.send_message(message.chat.id, msg)
            select_order_to_cancel(message)
        else:
            bot.send_message(message.chat.id, "Отмененных заказов нет.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при просмотре отмененных заказов: {e}")

def select_order_to_cancel(message):
    msg = bot.reply_to(message, "Введите ID заказа для удаления из базы данных или нажмите кнопку 'назад':")
    bot.register_next_step_handler(msg, cancel_order)

def cancel_order(message):
    try:
        order_id = int(message.text)
        cur.execute("DELETE FROM order_dishes WHERE order_id = %s", (order_id,))
        cur.execute("DELETE FROM orders WHERE order_id = %s", (order_id,))
        conn.commit()
        bot.send_message(message.chat.id, f"Заказ с ID {order_id} был успешно отменен и удален из базы данных.")
        admin_actions_with_buttons(message)
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при отмене заказа: {e}")

def view_pending_orders(message):
    try:
        cur.execute("SELECT orders.order_id, orders.user_id, string_agg(order_dishes.dish_id::text, ', '), orders.delivery_date, orders.time FROM orders JOIN order_dishes ON orders.order_id = order_dishes.order_id WHERE orders.status = 'ожидание' GROUP BY orders.order_id")
        orders = cur.fetchall()
        if orders:
            for order in orders:
                order_id, user_id, dish_ids, delivery_date, time = order
                msg = f"ID Заявки: {order_id}\nID клиента: {user_id}\nБлюдо: {dish_ids}\nДата подачи: {delivery_date}\nВремя: {time}\n"
                bot.send_message(message.chat.id, msg)
            select_order(message)
        else:
            bot.send_message(message.chat.id, "Заказов в ожидании нет.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при просмотре заказов в ожидании: {e}")

def select_order(message):
    msg = bot.reply_to(message, "Введите ID заказа для одобрения или отклонения:")
    bot.register_next_step_handler(msg, lambda msg: show_order_options(msg))

def show_order_options(message):
    order_id = int(message.text)
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    button1 = types.KeyboardButton("Одобрить")
    button2 = types.KeyboardButton("Отклонить")
    keyboard.add(button1, button2)
    msg = bot.reply_to(message, "Выберите действие:", reply_markup=keyboard)
    bot.register_next_step_handler(msg, lambda msg: process_order_choice(msg, order_id))

def process_order_choice(message, order_id):
    choice = message.text
    if choice == "Одобрить":
        approve_order(message, order_id)
    elif choice == "Отклонить":
        reject_order(message, order_id)

def approve_order(message, order_id):
    try:
        cur.execute("UPDATE orders SET status = 'активный' WHERE order_id = %s", (order_id,))
        conn.commit()
        cur.execute("SELECT user_id FROM orders WHERE order_id = %s", (order_id,))
        user_id = cur.fetchone()[0]
        bot.send_message(user_id, f"Ваш заказ с ID {order_id} был одобрен.")
        bot.send_message(message.chat.id, f"Заказ с ID {order_id} успешно одобрен.")
        admin_actions_with_buttons(message)
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при одобрении заказа: {e}")

def reject_order(message, order_id):
    try:
        cur.execute("SELECT user_id FROM orders WHERE order_id = %s", (order_id,))
        user_id = cur.fetchone()[0]
        bot.send_message(user_id, f"Ваш заказ с ID {order_id} был отклонен и удален из базы данных.")
        cur.execute("DELETE FROM order_dishes WHERE order_id = %s", (order_id,))
        cur.execute("DELETE FROM orders WHERE order_id = %s", (order_id,))
        conn.commit()
        bot.send_message(message.chat.id, f"Заказ с ID {order_id} был отклонен и удален из базы данных.")
        admin_actions_with_buttons(message)
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при отклонении заказа: {e}")

@bot.message_handler(func=lambda message: message.text == 'Назад')
def handle_back(message):
    admin_actions_with_buttons(message)

def view_requests(message):
    if message.text == 'Просмотр заявок':
        cur.execute("SELECT user_id, full_name, departure_date, status FROM users WHERE status != 'активный'")
        requests = cur.fetchall()
        if requests:
            for req in requests:
                user_id, full_name, departure_date, status = req
                msg = f"ID клиента: {user_id}\nФИО: {full_name}\nДата выезда: {departure_date}\nСтатус: {status}\n"
                keyboard = types.InlineKeyboardMarkup()
                approve_button = types.InlineKeyboardButton(text="Одобрить", callback_data=f"approve_{user_id}")
                reject_button = types.InlineKeyboardButton(text="Отклонить", callback_data=f"reject_{user_id}")
                keyboard.row(approve_button, reject_button)
                bot.send_message(message.chat.id, msg, reply_markup=keyboard)

            # Добавляем кнопку "Назад" внизу
            back_button = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
            back_button.add(types.KeyboardButton("Назад"))
            bot.send_message(message.chat.id, "Для возврата к административной панели нажмите кнопку 'Назад'.",
                             reply_markup=back_button)
        else:
            bot.send_message(message.chat.id, "Заявок на рассмотрении нет.")
            admin_actions_with_buttons(message)
    else:
        bot.send_message(message.chat.id, "Пожалуйста, воспользуйтесь кнопкой 'Просмотр заявок'.")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_', 'reject_')))
def handle_request_approval_rejection(call):
    action, user_id = call.data.split('_')
    user_id = int(user_id)
    if action == "approve":
        approve_request(call.message, user_id)
    elif action == "reject":
        reject_request(call.message, user_id)

def approve_request(message, user_id):
    try:
        assign_table(message, user_id)
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при одобрении заявки: {e}")

def reject_request(message, user_id):
    try:
        cancel_request(message, user_id)
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при отклонении заявки: {e}")

def assign_table(message, user_id):
    try:
        cur.execute("SELECT table_number, seats_count, occupied_seats_count FROM tables WHERE occupied_seats_count < seats_count")
        tables = cur.fetchall()
        if tables:
            keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
            for table in tables:
                table_number, seats_count, occupied_seats_count = table
                button_text = f"Стол {table_number} (свободно {seats_count - occupied_seats_count} мест)"
                keyboard.add(types.KeyboardButton(button_text))
            msg = bot.reply_to(message, "Выберите стол:", reply_markup=keyboard)
            bot.register_next_step_handler(msg, assign_seat, user_id)
        else:
            bot.send_message(message.chat.id, "Извините, свободных столов нет.")
            admin_actions_with_buttons(message)
    except ValueError:
        bot.reply_to(message, "Пожалуйста, введите корректный ID пользователя.")

def assign_seat(message, user_id):
    try:
        table_text = message.text
        table_number = int(table_text.split()[1])
        cur.execute("SELECT occupied_seats_count FROM tables WHERE table_number = %s", (table_number,))
        occupied_seats_count = cur.fetchone()[0]
        cur.execute("UPDATE tables SET occupied_seats_count = %s WHERE table_number = %s", (occupied_seats_count + 1, table_number))
        cur.execute("UPDATE users SET table_number = %s, seat_number = %s, status = 'активный' WHERE user_id = %s",
                    (table_number, occupied_seats_count + 1, user_id))
        conn.commit()
        bot.send_message(user_id, f"Ваша заявка на бронирование стола {table_number} и места {occupied_seats_count + 1} была одобрена.",
                         reply_markup=create_main_menu_keyboard())
        bot.send_message(message.chat.id, f"Заявка пользователя с ID {user_id} была успешно одобрена. Стол {table_number}, место {occupied_seats_count + 1}.")
        admin_actions_with_buttons(message)
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при назначении стола.")

def cancel_request(message, user_id):
    try:
        cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        conn.commit()
        bot.send_message(message.chat.id, f"Заявка пользователя с ID {user_id} была успешно отменена и удалена из базы данных.")
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка при отмене заявки.")
    admin_actions_with_buttons(message)

def admin_actions_with_buttons(message):
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    keyboard.add(types.KeyboardButton("Просмотр заявок"), types.KeyboardButton("Просмотр заказов"), types.KeyboardButton("Пользователи"), types.KeyboardButton("Сделать отчет"))
    msg = bot.reply_to(message, "Выберите действие:", reply_markup=keyboard)
    bot.register_next_step_handler(msg, admin_actions)

bot.polling()