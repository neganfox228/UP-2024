import telebot
from telebot import types
import psycopg2

conn = psycopg2.connect(user="postgres",
                        password="0000",
                        host="127.0.0.1",
                        port="5432",
                        database="shved_stol")
cur = conn.cursor()


bot = telebot.TeleBot("6525136024:AAFpVOa0ClnokyDW5DKR8W9LgMYbMQ1gkaQ")


user_states = {}


@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    if user_states.get(user_id) == "waiting_for_login":
        bot.send_message(message.chat.id, "Введите ваш логин:")
    elif user_states.get(user_id) == "waiting_for_password":
        bot.send_message(message.chat.id, "Введите ваш пароль:")
    elif user_states.get(user_id) == "logged_in":
        show_menu(message.chat.id)
    else:
        show_registration_keyboard(message.chat.id)

def show_registration_keyboard(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item_register = types.KeyboardButton("Зарегистрироваться")
    markup.add(item_register)
    bot.send_message(chat_id, "Добро пожаловать в стол заказов! Нажмите 'Зарегистрироваться', чтобы начать.", reply_markup=markup)

def show_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item_view_menu = types.KeyboardButton("Посмотреть меню")
    item_make_order = types.KeyboardButton("Сделать заказ")
    item_cancel_order = types.KeyboardButton("Отменить заказ")
    markup.add(item_view_menu, item_make_order, item_cancel_order)
    bot.send_message(chat_id, "Выберите действие:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Зарегистрироваться")
def register(message):
    user_id = message.from_user.id
    bot.send_message(message.chat.id, "Введите ваш логин:")
    user_states[user_id] = "waiting_for_login"

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "waiting_for_login")
def process_login(message):
    user_id = message.from_user.id
    global login  # Добавим global для доступа к login за пределами этой функции
    login = message.text

    cur.execute("SELECT * FROM users WHERE login = %s", (login,))
    if cur.fetchone():
        bot.send_message(message.chat.id, "Этот логин уже занят. Пожалуйста, выберите другой.")
        return

    user_states[user_id] = "waiting_for_password"
    bot.send_message(message.chat.id, "Введите ваш пароль:")


@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "waiting_for_password")
def process_password(message):
    user_id = message.from_user.id
    password = message.text

    cur.execute("INSERT INTO users (login, password) VALUES (%s, %s) RETURNING user_id",
                (login, password))
    user_id_in_db = cur.fetchone()[0]
    conn.commit()

    bot.send_message(message.chat.id, "Вы успешно зарегистрированы и вошли в аккаунт.")
    user_states[user_id] = "logged_in"
    show_menu(message.chat.id)

bot.polling()