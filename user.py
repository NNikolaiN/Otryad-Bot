# handlers/user.py
from aiogram import Router, types, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import TOKEN, ADMINS
from handlers.admin import AdminStates
import json
import os
import time
import re
import math
import html

router = Router()

# Состояния пользователя
class UserStates(StatesGroup):
    waiting_for_receipt = State()

# Ограничения на отправку чеков
MAX_RECEIPTS = 3
RECEIPT_WINDOW = 7200  # 2 часа в секундах

# Функция для очистки и исправления HTML
def sanitize_html(text: str) -> str:
    if not text:
        return text
    
    # Список разрешенных тегов Telegram
    allowed_tags = {'b', 'i', 'u', 's', 'a', 'code', 'pre', 'span', 'blockquote', 'tg-spoiler'}
    
    try:
        # Разбиваем текст на части: теги и содержимое
        parts = re.split(r'(<[^>]+>)', text)
        cleaned_text = ''
        open_tags = []
        
        for part in parts:
            # Если это тег
            if part.startswith('<'):
                tag_match = re.match(r'</?([a-zA-Z-]+)(?:\s+[^>]*)?>', part)
                if tag_match:
                    tag_name = tag_match.group(1).lower()
                    is_closing = part.startswith('</')
                    
                    if tag_name not in allowed_tags:
                        continue  # Пропускаем недопустимые теги
                    
                    if is_closing:
                        # Удаляем закрывающий тег из стека, если он соответствует
                        if open_tags and open_tags[-1] == tag_name:
                            open_tags.pop()
                            cleaned_text += part
                    else:
                        # Добавляем открывающий тег в стек
                        open_tags.append(tag_name)
                        cleaned_text += part
            else:
                # Экранируем специальные символы в содержимом
                cleaned_text += html.escape(part)
        
        # Закрываем все незакрытые теги
        while open_tags:
            tag_name = open_tags.pop()
            cleaned_text += f'</{tag_name}>'
        
        print(f"Debug: Sanitized HTML: {cleaned_text}")
        return cleaned_text
    
    except Exception as e:
        print(f"Ошибка очистки HTML: {e}")
        # В крайнем случае удаляем все теги
        return html.escape(re.sub(r'<[^>]+>', '', text))

DATA_FILE = "data.json"
BUTTONS_FILE = "button.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data.get("users"), list):
                print("Warning: 'users' is a list, converting to dict")
                data["users"] = {}
            if "receipt_history" not in data:
                data["receipt_history"] = {}
            return data
    return {"buttons": {}, "users": {}, "receipts": [], "receipt_history": {}}

def load_buttons_menu():
    try:
        if os.path.exists(BUTTONS_FILE):
            with open(BUTTONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get("menu", [])
        return []
    except Exception as e:
        print(f"Error loading buttons menu: {e}")
        return []

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_buttons():
    return load_data().get("buttons", {})

def get_users():
    return load_data().get("users", {})

def add_user(user_id):
    data = load_data()
    if not isinstance(data["users"], dict):
        print("Error: 'users' is not a dict, resetting to dict")
        data["users"] = {}
    data["users"][str(user_id)] = {"joined": time.time()}
    save_data(data)

def add_receipt(user_id, file_id, file_type):
    data = load_data()
    data["receipts"].append({
        "user_id": user_id,
        "file_id": file_id,
        "type": file_type,
        "status": "pending",
        "timestamp": time.time()
    })
    save_data(data)

def add_receipt_history(user_id, timestamp):
    data = load_data()
    user_id_str = str(user_id)
    if user_id_str not in data["receipt_history"]:
        data["receipt_history"][user_id_str] = []
    data["receipt_history"][user_id_str].append(timestamp)
    save_data(data)

def get_receipt_history(user_id):
    data = load_data()
    return data["receipt_history"].get(str(user_id), [])

def clean_receipt_history(user_id):
    data = load_data()
    user_id_str = str(user_id)
    if user_id_str not in data["receipt_history"]:
        return
    current_time = time.time()
    data["receipt_history"][user_id_str] = [
        ts for ts in data["receipt_history"][user_id_str]
        if current_time - ts < RECEIPT_WINDOW
    ]
    save_data(data)

def update_button(button_name, button_data):
    data = load_data()
    data["buttons"][button_name] = button_data
    save_data(data)

def add_message_to_button(button_name, message_data):
    data = load_data()
    if button_name not in data["buttons"]:
        data["buttons"][button_name] = {"messages": [], "active": True}
    data["buttons"][button_name]["messages"].append(message_data)
    save_data(data)

def toggle_button(button_name, active):
    data = load_data()
    if button_name in data["buttons"]:
        data["buttons"][button_name]["active"] = active
        save_data(data)

def remove_message_from_button(button_name, index):
    data = load_data()
    if button_name in data["buttons"] and 0 <= index < len(data["buttons"][button_name]["messages"]):
        data["buttons"][button_name]["messages"].pop(index)
        save_data(data)

def get_receipts():
    return load_data().get("receipts", [])

def update_receipt_status(user_id, file_id, status):
    data = load_data()
    for receipt in data["receipts"]:
        if receipt["user_id"] == user_id and receipt["file_id"] == file_id:
            receipt["status"] = status
            break
    save_data(data)

# Функция для создания главного меню
def get_main_menu(user_id: int):
    buttons = get_buttons()
    menu_layout = load_buttons_menu()
    keyboard = []
    users = get_users()
    is_admin = user_id in ADMINS and users.get(str(user_id), {}).get("is_admin_panel_enabled", False)
    
    if is_admin:
        keyboard.append([KeyboardButton(text="Админ Панель")])
    
    if not menu_layout:
        if "ВХОД В ОТРЯД СВОБОДЫ🗽" in buttons and buttons["ВХОД В ОТРЯД СВОБОДЫ🗽"].get("active", True):
            keyboard.append([KeyboardButton(text="ВХОД В ОТРЯД СВОБОДЫ🗽")])
        
        other_buttons = [
            btn_name for btn_name, btn_info in buttons.items()
            if btn_info.get("active", True) and btn_name != "ВХОД В ОТРЯД СВОБОДЫ🗽"
        ]
        
        for i in range(0, len(other_buttons), 2):
            row = [KeyboardButton(text=other_buttons[i])]
            if i + 1 < len(other_buttons):
                row.append(KeyboardButton(text=other_buttons[i + 1]))
            keyboard.append(row)
    else:
        for row in menu_layout:
            row_buttons = []
            for btn_name in row:
                if btn_name in buttons and buttons[btn_name].get("active", True):
                    row_buttons.append(KeyboardButton(text=btn_name))
            if row_buttons:
                keyboard.append(row_buttons)
    
    return ReplyKeyboardMarkup(keyboard=keyboard)

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    add_user(message.from_user.id)
    await message.answer(
        "<b>Приветствую</b>",
        parse_mode="HTML",
        reply_markup=get_main_menu(message.from_user.id)
    )

@router.message(F.text.in_(get_buttons().keys()), ~F.text.in_(["❌ Отменить"]))
async def handle_button(message: types.Message, state: FSMContext):
    btn_name = message.text
    buttons = get_buttons()
    if btn_name not in buttons or not buttons[btn_name].get("active", True):
        await message.answer("❌ Эта кнопка недоступна.", parse_mode="HTML", reply_markup=get_main_menu(message.from_user.id))
        return
    
    messages = buttons[btn_name]["messages"]
    if not messages:
        await message.answer("❌ Нет сообщений для этой кнопки.", parse_mode="HTML", reply_markup=get_main_menu(message.from_user.id))
        return
    
    inline_keyboard = None
    if btn_name == "ВХОД В ОТРЯД СВОБОДЫ🗽":
        inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Я оплатил/прислать чек", callback_data="send_receipt")]
        ])
    
    for msg in messages:
        try:
            msg_type = msg.get("type")
            caption = sanitize_html(msg.get("caption", "")) if msg.get("caption") else None
            content = sanitize_html(msg.get("content", "")) if msg.get("content") else None
            reply_markup = inline_keyboard if (btn_name == "ВХОД В ОТРЯД СВОБОДЫ🗽" and msg == messages[-1]) else None
            
            if msg_type == "text":
                await message.answer(content, parse_mode="HTML", reply_markup=reply_markup)
            elif msg_type == "voice":
                await message.bot.send_voice(message.chat.id, msg["file_id"], caption=caption, parse_mode="HTML" if caption else None, reply_markup=reply_markup)
            elif msg_type == "video_note":
                await message.bot.send_video_note(message.chat.id, msg["file_id"], reply_markup=reply_markup)
                if caption:
                    await message.answer(caption, parse_mode="HTML")
            elif msg_type == "photo":
                await message.bot.send_photo(message.chat.id, msg["file_id"], caption=caption, parse_mode="HTML" if caption else None, reply_markup=reply_markup)
            elif msg_type == "video":
                await message.bot.send_video(message.chat.id, msg["file_id"], caption=caption, parse_mode="HTML" if caption else None, reply_markup=reply_markup)
        except Exception as e:
            print(f"Ошибка отправки сообщения для кнопки {btn_name}: {e}")
            await message.answer("❌ Ошибка при отправке сообщения.", parse_mode="HTML")
            continue
    
    if btn_name == "ВХОД В ОТРЯД СВОБОДЫ🗽":
        await state.set_state(UserStates.waiting_for_receipt)
    else:
        await message.answer(
            "Выбери действие:",
            parse_mode="HTML",
            reply_markup=get_main_menu(message.from_user.id)
        )

@router.callback_query(F.data == "send_receipt")
async def handle_receipt_button(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete_reply_markup()
    await callback.message.answer(
        "Пожалуйста, отправь чек (фото или документ).",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отменить")]],
            resize_keyboard=True
        )
    )
    await callback.answer()

@router.message(UserStates.waiting_for_receipt, F.photo | F.document)
async def handle_receipt(message: types.Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    current_time = time.time()
    
    clean_receipt_history(user_id)
    
    receipt_history = get_receipt_history(user_id)
    recent_receipts = [ts for ts in receipt_history if current_time - ts < RECEIPT_WINDOW]
    
    if len(recent_receipts) >= MAX_RECEIPTS:
        oldest_receipt_time = min(recent_receipts)
        time_left = RECEIPT_WINDOW - (current_time - oldest_receipt_time)
        minutes_left = math.ceil(time_left / 60)
        await message.answer(
            f"❌ Вы достигли лимита ({MAX_RECEIPTS} чека за 2 часа). "
            f"Попробуйте снова через {minutes_left} минут.",
            parse_mode="HTML",
            reply_markup=get_main_menu(user_id)
        )
        await state.clear()
        return
    
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    file_type = "photo" if message.photo else "document"
    
    add_receipt(user_id, file_id, file_type)
    add_receipt_history(user_id, current_time)
    
    for admin_id in ADMINS:
        try:
            await bot.send_message(admin_id, f"Новый чек от пользователя {user_id} (Тип: {file_type})")
            if file_type == "photo":
                await bot.send_photo(admin_id, file_id)
            elif file_type == "document":
                await bot.send_document(admin_id, file_id)
        except Exception as e:
            print(f"Ошибка отправки чека админу {admin_id}: {e}")
    
    await message.answer(
        "Ваш чек отправлен на проверку. Ожидайте подтверждения.",
        parse_mode="HTML",
        reply_markup=get_main_menu(user_id)
    )
    await state.clear()

@router.message(F.text == "❌ Отменить", StateFilter(*UserStates))
async def cancel_action(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Действие отменено.",
        parse_mode="HTML",
        reply_markup=get_main_menu(message.from_user.id)
    )

@router.message()
async def handle_unknown(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state in [s.state for s in AdminStates]:
        return
    print(f"handle_unknown сработал: {message.text}")
    await message.answer(
        "❌ Неизвестная команда. Выбери действие из меню.",
        parse_mode="HTML",
        reply_markup=get_main_menu(message.from_user.id)
    )

print("✅ user.py загружен")