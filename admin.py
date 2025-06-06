from aiogram import Router, types, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from config import ADMINS
from utils.storage import get_buttons, update_button, add_message_to_button, toggle_button, get_users, save_data, remove_message_from_button, get_receipts, update_receipt_status
import html

router = Router()

# Состояния админ-панели
class AdminStates(StatesGroup):
    main_menu = State()
    choose_button = State()
    choose_action = State()
    new_name = State()
    add_message = State()
    add_caption = State()
    confirm_broadcast = State()
    preview_broadcast = State()  # Новое состояние для предпросмотра рассылки
    preview_message = State()    # Новое состояние для предпросмотра сообщения кнопки
    delete_message = State()
    create_button = State()
    check_receipts = State()
    select_receipt = State()
    process_receipt = State()

# Функция для преобразования entities в HTML
def entities_to_html(content: str, entities: list[types.MessageEntity] = None) -> str:
    if not content or not content.strip():
        return ""
    if not entities:
        return html.escape(content)

    print(f"Debug: Processing entities for text: {content}")  # Отладка
    print(f"Debug: Entities: {entities}")

    # Создаём список событий (открытие/закрытие тегов)
    events = []
    for entity in entities:
        if entity.type == "bold":
            tag_open, tag_close = "<b>", "</b>"
        elif entity.type == "italic":
            tag_open, tag_close = "<i>", "</i>"
        elif entity.type == "underline":
            tag_open, tag_close = "<u>", "</u>"
        elif entity.type == "strikethrough":
            tag_open, tag_close = "<s>", "</s>"
        elif entity.type == "spoiler":
            tag_open, tag_close = '<span class="tg-spoiler">', "</span>"
        elif entity.type == "text_link":
            tag_open, tag_close = f'<a href="{html.escape(entity.url)}">', "</a>"
        elif entity.type == "blockquote" or entity.type == "expandable_blockquote":
            tag_open, tag_close = "<blockquote>", "</blockquote>"
        else:
            continue
        events.append((entity.offset, "open", tag_open))
        events.append((entity.offset + entity.length, "close", tag_close))

    # Сортируем события по позиции и типу (закрывающие теги перед открывающими при равной позиции)
    events.sort(key=lambda x: (x[0], x[1] == "open"))

    result = []
    last_pos = 0
    for pos, event_type, tag in events:
        # Добавляем текст до текущей позиции
        if pos > last_pos:
            result.append(html.escape(content[last_pos:pos]))
        # Добавляем тег
        result.append(tag)
        last_pos = pos

    # Добавляем оставшийся текст
    if last_pos < len(content):
        result.append(html.escape(content[last_pos:]))

    final_html = "".join(result)
    print(f"Debug: Generated HTML: {final_html}")  # Отладка
    return final_html

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

@router.message(Command(commands=["admin", "Admin"]))
async def admin_panel(message: types.Message, state: FSMContext):
    print(f"⚡ Команда /admin от {message.from_user.id}, ADMINS: {ADMINS}")
    if not is_admin(message.from_user.id):
        print("🚫 Нет доступа")
        return await message.answer("Нет доступа.")
    print("✅ Доступ разрешён")
    await show_main_menu(message, state)

async def show_main_menu(message: types.Message, state: FSMContext):
    await state.set_state(AdminStates.main_menu)
    await message.answer(
        "👑 <b>Админ-панель</b>\nВыбери действие:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✏️ Редактирование кнопок")],
                [KeyboardButton(text="➕ Создать кнопку")],
                [KeyboardButton(text="📬 Рассылка")],
                [KeyboardButton(text="🔍 Проверка чеков")],
                [KeyboardButton(text="🚪 Выйти"), KeyboardButton(text="❌ Отменить")]
            ],
            resize_keyboard=True
        )
    )

async def show_button_list(message: types.Message, state: FSMContext):
    buttons = list(get_buttons().keys())
    if not buttons:
        await state.clear()
        await message.answer("Нет доступных кнопок.", reply_markup=ReplyKeyboardRemove())
        await show_main_menu(message, state)
        return
    
    keyboard = [[KeyboardButton(text=btn)] for btn in buttons]
    keyboard.append([KeyboardButton(text="🔙 Назад"), KeyboardButton(text="❌ Отменить")])
    markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
    
    await state.set_state(AdminStates.choose_button)
    await message.answer("Выбери кнопку для редактирования:", parse_mode="HTML", reply_markup=markup)

@router.message(Command("cancel"))
async def cancel_action(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return await message.answer("Нет доступа.")
    await cancel_button(message, state)

@router.message(F.text == "❌ Отменить", StateFilter(*AdminStates))
async def cancel_button(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return await message.answer("Нет доступа.")
    
    current_state = await state.get_state()
    data = await state.get_data()
    receipt = data.get("receipt")
    
    if current_state in [AdminStates.select_receipt.state, AdminStates.process_receipt.state] and receipt:
        await message.answer(
            f"❌ Отменена обработка чека от пользователя {receipt['user_id']} (Тип: {receipt['type']}).",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await message.answer("Действие отменено.", reply_markup=ReplyKeyboardRemove())
    
    await state.clear()
    await show_main_menu(message, state)

@router.message(F.text == "🚪 Выйти", StateFilter(AdminStates.main_menu, AdminStates.choose_button, AdminStates.choose_action))
async def exit_admin_panel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Вы вышли из админ-панели.", reply_markup=ReplyKeyboardRemove())

@router.message(AdminStates.main_menu)
async def handle_main_menu(message: types.Message, state: FSMContext):
    if message.text == "✏️ Редактирование кнопок":
        await show_button_list(message, state)
    elif message.text == "➕ Создать кнопку":
        await state.set_state(AdminStates.create_button)
        await message.answer(
            "Введи название новой кнопки:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="❌ Отменить")]],
                resize_keyboard=True
            )
        )
    elif message.text == "📬 Рассылка":
        await state.set_state(AdminStates.confirm_broadcast)
        await message.answer(
            "Отправь текст, голос, кружок, фото или видео для рассылки.\n"
            "Стилизуй текст прямо в Telegram (жирный, курсив, ссылки и т.д.).",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="❌ Отменить")]],
                resize_keyboard=True
            )
        )
    elif message.text == "🔍 Проверка чеков":
        await state.set_state(AdminStates.check_receipts)
        await show_receipts_list(message, state)
    elif message.text == "🚪 Выйти":
        await exit_admin_panel(message, state)
    elif message.text == "❌ Отменить":
        await cancel_button(message, state)
    else:
        await message.answer("Выбери действие из меню.", reply_markup=ReplyKeyboardRemove())
        await show_main_menu(message, state)

async def show_receipts_list(message: types.Message, state: FSMContext):
    receipts = get_receipts()
    pending_receipts = [r for r in receipts if r["status"] == "pending"]
    if not pending_receipts:
        await state.clear()
        await message.answer("Нет чеков на проверку.", reply_markup=ReplyKeyboardRemove())
        await show_main_menu(message, state)
        return
    
    text = "Чеки на проверку:\n"
    for i, receipt in enumerate(pending_receipts):
        text += f"{i + 1}. Пользователь {receipt['user_id']} (Тип: {receipt['type']})\n"
    text += "\nВведи номер чека для обработки (например, 1):"
    
    await state.update_data(receipts=pending_receipts)
    await state.set_state(AdminStates.select_receipt)
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔙 Назад"), KeyboardButton(text="❌ Отменить")]],
            resize_keyboard=True
        )
    )

@router.message(AdminStates.select_receipt, F.text)
async def select_receipt(message: types.Message, state: FSMContext):
    if message.text == "🔙 Назад":
        await state.set_state(AdminStates.check_receipts)
        await show_receipts_list(message, state)
        return
    if message.text == "❌ Отменить":
        await cancel_button(message, state)
        return
    
    if not message.text.isdigit():
        return  # Игнорируем нечисловой ввод
    
    index = int(message.text) - 1
    data = await state.get_data()
    receipts = data.get("receipts", [])
    if 0 <= index < len(receipts):
        receipt = receipts[index]
        await state.update_data(receipt=receipt)
        print(f"Выбран чек: {receipt}")  # Отладочный вывод
        await message.answer(
            f"Чек от пользователя {receipt['user_id']} (Тип: {receipt['type']})."
        )
        if receipt["type"] == "photo":
            await message.bot.send_photo(message.chat.id, receipt["file_id"])
        elif receipt["type"] == "document":
            await message.bot.send_document(message.chat.id, receipt["file_id"])
        await message.answer(
            "Выберите действие:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="✅ Одобрить")],
                    [KeyboardButton(text="❌ Отклонить")],
                    [KeyboardButton(text="🔙 Назад"), KeyboardButton(text="❌ Отменить")]
                ],
                resize_keyboard=True
            )
        )
        await state.set_state(AdminStates.process_receipt)
    else:
        await message.answer(
            "❌ Неверный номер чека. Попробуй снова.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="🔙 Назад"), KeyboardButton(text="❌ Отменить")]],
                resize_keyboard=True
            )
        )

@router.message(AdminStates.process_receipt, F.text.in_(["✅ Одобрить", "❌ Отклонить", "🔙 Назад", "❌ Отменить"]))
async def process_receipt_action(message: types.Message, state: FSMContext, bot: Bot):
    print(f"process_receipt_action сработал: {message.text}")  # Отладочный вывод
    data = await state.get_data()
    receipt = data.get("receipt")
    if not receipt:
        print("Чек не найден в состоянии")  # Отладочный вывод
        await message.answer(
            "❌ Ошибка: чек не выбран.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="🔙 Назад"), KeyboardButton(text="❌ Отменить")]],
                resize_keyboard=True
            )
        )
        return

    if message.text == "🔙 Назад":
        await state.set_state(AdminStates.check_receipts)
        await show_receipts_list(message, state)
        return
    if message.text == "❌ Отменить":
        await cancel_button(message, state)
        return

    if message.text == "✅ Одобрить":
        update_receipt_status(receipt["user_id"], receipt["file_id"], "approved")
        await message.answer(f"✅ Чек от пользователя {receipt['user_id']} одобрен.")
        try:
            await bot.send_message(receipt["user_id"], "Ваш чек одобрен! Добро пожаловать в отряд свободы!")
        except Exception as e:
            print(f"Ошибка уведомления пользователя {receipt['user_id']}: {e}")
    elif message.text == "❌ Отклонить":
        update_receipt_status(receipt["user_id"], receipt["file_id"], "rejected")
        await message.answer(f"❌ Чек от пользователя {receipt['user_id']} отклонён.")
        try:
            await bot.send_message(receipt["user_id"], "Ваш чек отклонён. Пожалуйста, проверьте данные и попробуйте снова.")
        except Exception as e:
            print(f"Ошибка уведомления пользователя {receipt['user_id']}: {e}")

    await state.set_state(AdminStates.check_receipts)
    await show_receipts_list(message, state)

@router.message(AdminStates.choose_button)
async def choose_action(message: types.Message, state: FSMContext):
    btn_name = message.text
    if btn_name == "🔙 Назад":
        await show_main_menu(message, state)
        return
    if btn_name == "❌ Отменить":
        await cancel_button(message, state)
        return
    if btn_name not in get_buttons():
        await state.clear()
        await message.answer("Такой кнопки нет.", reply_markup=ReplyKeyboardRemove())
        await show_button_list(message, state)
        return
    await state.update_data(button=btn_name)
    await state.set_state(AdminStates.choose_action)
    await message.answer(
        f"Выбрана кнопка: <b>{btn_name}</b>\nЧто сделать?",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✏️ Изменить название"), KeyboardButton(text="🧾 Добавить сообщение")],
                [KeyboardButton(text="🗑️ Удалить сообщение"), KeyboardButton(text="🚫 Отключить кнопку")],
                [KeyboardButton(text="✅ Включить кнопку"), KeyboardButton(text="🚪 Выйти")],
                [KeyboardButton(text="❌ Отменить")]
            ],
            resize_keyboard=True
        )
    )

@router.message(F.text == "✏️ Изменить название", AdminStates.choose_action)
async def start_rename(message: types.Message, state: FSMContext):
    await state.set_state(AdminStates.new_name)
    await message.answer(
        "Введи новое название для кнопки:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отменить")]],
            resize_keyboard=True
        )
    )

@router.message(AdminStates.new_name)
async def finish_rename(message: types.Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await cancel_button(message, state)
        return
    new_name = message.text
    if len(new_name) > 50 or not new_name.strip():
        return await message.answer("❌ Название слишком длинное или пустое. Попробуй снова.")
    data = await state.get_data()
    old_name = data.get("button")
    buttons = get_buttons()
    if new_name in buttons:
        return await message.answer("❌ Кнопка с таким названием уже существует.")
    buttons[new_name] = buttons.pop(old_name)
    save_data({"buttons": buttons, "users": get_users(), "receipts": get_receipts()})
    await state.clear()
    await message.answer(f"✅ Кнопка переименована в <b>{new_name}</b>.", parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    await show_button_list(message, state)

@router.message(F.text == "🧾 Добавить сообщение", AdminStates.choose_action)
async def start_add_message(message: types.Message, state: FSMContext):
    await state.set_state(AdminStates.add_message)
    await message.answer(
        "Отправь текст, голосовое, кружок, фото или видео для кнопки.\n"
        "Стилизуй текст прямо в Telegram (жирный, курсив, ссылки и т.д.).",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отменить")]],
            resize_keyboard=True
        )
    )

@router.message(AdminStates.create_button)
async def create_new_button(message: types.Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await cancel_button(message, state)
        return
    new_name = message.text.strip()
    if len(new_name) > 50 or not new_name:
        return await message.answer("❌ Название слишком длинное или пустое. Попробуй снова.")
    buttons = get_buttons()
    if new_name in buttons:
        return await message.answer("❌ Кнопка с таким названием уже существует.")
    
    update_button(new_name, {"messages": [], "active": True})
    save_data({"buttons": get_buttons(), "users": get_users(), "receipts": get_receipts()})
    
    await state.update_data(button=new_name)
    await state.set_state(AdminStates.add_message)
    await message.answer(
        f"✅ Кнопка <b>{new_name}</b> создана.\n"
        "Отправь текст, голосовое, кружок, фото или видео для кнопки.\n"
        "Стилизуй текст прямо в Telegram (жирный, курсив, ссылки и т.д.).",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отменить")]],
            resize_keyboard=True
        )
    )

@router.message(AdminStates.add_message, F.voice)
async def add_voice(message: types.Message, state: FSMContext):
    await state.update_data(
        voice_file_id=message.voice.file_id,
        caption=message.caption,
        caption_entities=message.caption_entities
    )
    await show_message_preview(message, state, "voice")

@router.message(AdminStates.add_message, F.video_note)
async def add_video_note(message: types.Message, state: FSMContext):
    await state.update_data(
        video_note_file_id=message.video_note.file_id,
        caption=message.caption,
        caption_entities=message.caption_entities
    )
    await show_message_preview(message, state, "video_note")

@router.message(AdminStates.add_message, F.photo)
async def add_photo(message: types.Message, state: FSMContext):
    await state.update_data(
        photo_file_id=message.photo[-1].file_id,
        caption=message.caption,
        caption_entities=message.caption_entities
    )
    await show_message_preview(message, state, "photo")

@router.message(AdminStates.add_message, F.video)
async def add_video(message: types.Message, state: FSMContext):
    await state.update_data(
        video_file_id=message.video.file_id,
        caption=message.caption,
        caption_entities=message.caption_entities
    )
    await show_message_preview(message, state, "video")

async def show_message_preview(message: types.Message, state: FSMContext, msg_type: str):
    data = await state.get_data()
    caption = entities_to_html(data.get("caption", ""), data.get("caption_entities", [])) if data.get("caption") else ""
    
    # Отправляем предпросмотр
    try:
        if msg_type == "voice":
            await message.bot.send_voice(message.chat.id, data["voice_file_id"], caption=caption, parse_mode="HTML" if caption else None)
        elif msg_type == "video_note":
            await message.bot.send_video_note(message.chat.id, data["video_note_file_id"])
            if caption:
                await message.answer(caption, parse_mode="HTML")
        elif msg_type == "photo":
            await message.bot.send_photo(message.chat.id, data["photo_file_id"], caption=caption, parse_mode="HTML" if caption else None)
        elif msg_type == "video":
            await message.bot.send_video(message.chat.id, data["video_file_id"], caption=caption, parse_mode="HTML" if caption else None)
    except Exception as e:
        print(f"Ошибка предпросмотра: {e}")
        await message.answer("❌ Ошибка при показе предпросмотра. Попробуй снова.", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        await show_main_menu(message, state)
        return
    
    await state.set_state(AdminStates.preview_message)
    await message.answer(
        "Это предпросмотр сообщения. Подтвердить?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✅ Подтвердить")],
                [KeyboardButton(text="Добавить описание")],
                [KeyboardButton(text="❌ Отменить")]
            ],
            resize_keyboard=True
        )
    )

@router.message(AdminStates.preview_message, F.text)
async def handle_message_preview(message: types.Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await cancel_button(message, state)
        return
    if message.text == "Добавить описание":
        await state.set_state(AdminStates.add_caption)
        await message.answer(
            "Отправь текст описания, стилизованный в Telegram (жирный, курсив, ссылки и т.д.).",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="❌ Отменить")]],
                resize_keyboard=True
            )
        )
        return
    if message.text == "✅ Подтвердить":
        data = await state.get_data()
        button_name = data["button"]
        
        if "voice_file_id" in data:
            file_id = data["voice_file_id"]
            msg_type = "voice"
        elif "video_note_file_id" in data:
            file_id = data["video_note_file_id"]
            msg_type = "video_note"
        elif "photo_file_id" in data:
            file_id = data["photo_file_id"]
            msg_type = "photo"
        elif "video_file_id" in data:
            file_id = data["video_file_id"]
            msg_type = "video"
        else:
            await message.answer("❌ Ошибка: медиа не найдено.", reply_markup=ReplyKeyboardRemove())
            await state.clear()
            await show_button_list(message, state)
            return
        
        caption = entities_to_html(data.get("caption", ""), data.get("caption_entities", [])) if data.get("caption") else ""
        message_data = {
            "type": msg_type,
            "file_id": file_id
        }
        if caption:
            message_data["caption"] = caption
        
        add_message_to_button(button_name, message_data)
        await message.answer(f"✅ {msg_type.capitalize()} добавлено {'с подписью' if caption else 'без подписи'}.", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        await show_button_list(message, state)

@router.message(AdminStates.add_caption, F.text)
async def add_media_caption(message: types.Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await cancel_button(message, state)
        return
    data = await state.get_data()
    await state.update_data(caption=message.text, caption_entities=message.entities)
    await show_message_preview(message, state, data.get("voice_file_id") and "voice" or
                             data.get("video_note_file_id") and "video_note" or
                             data.get("photo_file_id") and "photo" or "video")

@router.message(AdminStates.add_message, F.text)
async def add_text(message: types.Message, state: FSMContext):
    content = entities_to_html(message.text, message.entities or [])
    await state.update_data(text_content=content)
    
    # Показываем предпросмотр
    try:
        await message.answer(content, parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка предпросмотра текста: {e}")
        await message.answer("❌ Ошибка при показе предпросмотра. Попробуй снова.", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        await show_main_menu(message, state)
        return
    
    await state.set_state(AdminStates.preview_message)
    await message.answer(
        "Это предпросмотр сообщения. Подтвердить?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✅ Подтвердить")],
                [KeyboardButton(text="❌ Отменить")]
            ],
            resize_keyboard=True
        )
    )

@router.message(AdminStates.preview_message, F.text == "✅ Подтвердить", F.state == AdminStates.preview_message)
async def confirm_text_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    button_name = data["button"]
    content = data.get("text_content")
    
    if content:
        add_message_to_button(button_name, {"type": "text", "content": content})
        await message.answer("✅ Текст добавлен.", reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer("❌ Ошибка: текст не найден.", reply_markup=ReplyKeyboardRemove())
    
    await state.clear()
    await show_button_list(message, state)

@router.message(AdminStates.add_message)
async def handle_invalid_message(message: types.Message, state: FSMContext):
    await message.answer(
        "❌ Неверный тип сообщения. Отправь текст, голосовое, кружок, фото или видео.\n"
        "Для отмены используй /cancel или нажми «❌ Отменить».",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отменить")]],
            resize_keyboard=True
        )
    )

@router.message(F.text == "🗑️ Удалить сообщение", AdminStates.choose_action)
async def start_delete_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    button_name = data["button"]
    buttons = get_buttons()
    messages = buttons.get(button_name, {}).get("messages", [])
    
    if not messages:
        await state.clear()
        await message.answer(f"У кнопки <b>{button_name}</b> нет сообщений для удаления.", parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
        await show_button_list(message, state)
        return
    
    text = f"Сообщения для кнопки <b>{button_name}</b>:\n"
    for i, msg in enumerate(messages):
        msg_type = msg.get("type")
        if msg_type == "text":
            content = msg.get("content", "Без текста")
        elif msg_type in ["voice", "video_note", "photo", "video"]:
            content = f"{msg_type.capitalize()} (ID: {msg.get('file_id', 'N/A')})"
        else:
            content = "Неизвестный тип"
        caption = msg.get("caption", "")
        if caption:
            content += f"\nПодпись: {caption}"
        text += f"{i + 1}. {content}\n"
    text += "\nВведи номер сообщения для удаления (например, 1):"
    
    await state.set_state(AdminStates.delete_message)
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отменить")]],
            resize_keyboard=True
        )
    )

@router.message(AdminStates.delete_message)
async def finish_delete_message(message: types.Message, state: FSMContext):
    if message.text == "❌ Отменить":
        await cancel_button(message, state)
        return
    data = await state.get_data()
    button_name = data["button"]
    buttons = get_buttons()
    messages = buttons.get(button_name, {}).get("messages", [])
    
    try:
        index = int(message.text) - 1
        if 0 <= index < len(messages):
            remove_message_from_button(button_name, index)
            await message.answer(f"✅ Сообщение удалено из кнопки <b>{button_name}</b>.", parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
        else:
            await message.answer("❌ Неверный номер сообщения. Попробуй снова.", reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="❌ Отменить")]],
                resize_keyboard=True
            ))
    except ValueError:
        await message.answer("❌ Введи число.", reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отменить")]],
            resize_keyboard=True
        ))
    
    if message.text.isdigit():
        await state.clear()
        await show_button_list(message, state)

@router.message(F.text == "✅ Включить кнопку", AdminStates.choose_action)
async def enable_button(message: types.Message, state: FSMContext):
    data = await state.get_data()
    toggle_button(data["button"], True)
    await state.clear()
    await message.answer("Кнопка включена.", reply_markup=ReplyKeyboardRemove())
    await show_button_list(message, state)

@router.message(F.text == "🚫 Отключить кнопку", AdminStates.choose_action)
async def disable_button(message: types.Message, state: FSMContext):
    data = await state.get_data()
    toggle_button(data["button"], False)
    await state.clear()
    await message.answer("Кнопка отключена.", reply_markup=ReplyKeyboardRemove())
    await show_button_list(message, state)

@router.message(AdminStates.confirm_broadcast, F.text | F.voice | F.video_note | F.photo | F.video)
async def prepare_broadcast_preview(message: types.Message, state: FSMContext):
    # Сохраняем данные для предпросмотра
    data = {
        "text": message.text,
        "entities": message.entities,
        "caption": message.caption,
        "caption_entities": message.caption_entities
    }
    if message.voice:
        data["voice_file_id"] = message.voice.file_id
        data["type"] = "voice"
    elif message.video_note:
        data["video_note_file_id"] = message.video_note.file_id
        data["type"] = "video_note"
    elif message.photo:
        data["photo_file_id"] = message.photo[-1].file_id
        data["type"] = "photo"
    elif message.video:
        data["video_file_id"] = message.video.file_id
        data["type"] = "video"
    else:
        data["type"] = "text"
    
    await state.update_data(broadcast_data=data)
    
    # Показываем предпросмотр
    try:
        if data["type"] == "text":
            content = entities_to_html(data["text"], data["entities"] or [])
            await message.answer(content, parse_mode="HTML")
        elif data["type"] == "voice":
            caption = entities_to_html(data["caption"] or "", data["caption_entities"] or [])
            await message.bot.send_voice(message.chat.id, data["voice_file_id"], caption=caption, parse_mode="HTML" if caption else None)
        elif data["type"] == "video_note":
            await message.bot.send_video_note(message.chat.id, data["video_note_file_id"])
            if data["caption"]:
                caption = entities_to_html(data["caption"], data["caption_entities"] or [])
                await message.answer(caption, parse_mode="HTML")
        elif data["type"] == "photo":
            caption = entities_to_html(data["caption"] or "", data["caption_entities"] or [])
            await message.bot.send_photo(message.chat.id, data["photo_file_id"], caption=caption, parse_mode="HTML" if caption else None)
        elif data["type"] == "video":
            caption = entities_to_html(data["caption"] or "", data["caption_entities"] or [])
            await message.bot.send_video(message.chat.id, data["video_file_id"], caption=caption, parse_mode="HTML" if caption else None)
    except Exception as e:
        print(f"Ошибка предпросмотра рассылки: {e}")
        await message.answer("❌ Ошибка при показе предпросмотра. Попробуй снова.", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        await show_main_menu(message, state)
        return
    
    await state.set_state(AdminStates.preview_broadcast)
    await message.answer(
        "Это предпросмотр рассылки. Подтвердить отправку?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✅ Подтвердить")],
                [KeyboardButton(text="❌ Отменить")]
            ],
            resize_keyboard=True
        )
    )

@router.message(AdminStates.preview_broadcast, F.text == "✅ Подтвердить")
async def do_broadcast(message: types.Message, state: FSMContext):
    data = await state.get_data()
    broadcast_data = data.get("broadcast_data", {})
    users = get_users()
    success = 0
    
    for user_id in users:
        try:
            if broadcast_data["type"] == "text":
                content = entities_to_html(broadcast_data["text"], broadcast_data["entities"] or [])
                await message.bot.send_message(
                    user_id,
                    content,
                    parse_mode="HTML"
                )
                success += 1
            elif broadcast_data["type"] == "voice":
                caption = entities_to_html(broadcast_data["caption"] or "", broadcast_data["caption_entities"] or [])
                await message.bot.send_voice(
                    user_id,
                    broadcast_data["voice_file_id"],
                    caption=caption,
                    parse_mode="HTML" if caption else None
                )
                success += 1
            elif broadcast_data["type"] == "video_note":
                await message.bot.send_video_note(user_id, broadcast_data["video_note_file_id"])
                if broadcast_data["caption"]:
                    caption = entities_to_html(broadcast_data["caption"], broadcast_data["caption_entities"] or [])
                    await message.bot.send_message(user_id, caption, parse_mode="HTML")
                success += 1
            elif broadcast_data["type"] == "photo":
                caption = entities_to_html(broadcast_data["caption"] or "", broadcast_data["caption_entities"] or [])
                await message.bot.send_photo(
                    user_id,
                    broadcast_data["photo_file_id"],
                    caption=caption,
                    parse_mode="HTML" if caption else None
                )
                success += 1
            elif broadcast_data["type"] == "video":
                caption = entities_to_html(broadcast_data["caption"] or "", broadcast_data["caption_entities"] or [])
                await message.bot.send_video(
                    user_id,
                    broadcast_data["video_file_id"],
                    caption=caption,
                    parse_mode="HTML" if caption else None
                )
                success += 1
        except Exception as e:
            print(f"Failed to send message to user {user_id}: {e}")
            continue
    
    await state.clear()
    await message.answer(f"✅ Рассылка завершена. Отправлено: {success} сообщений.", reply_markup=ReplyKeyboardRemove())
    await show_main_menu(message, state)

@router.message(AdminStates.preview_broadcast, F.text == "❌ Отменить")
async def cancel_broadcast(message: types.Message, state: FSMContext):
    await cancel_button(message, state)

print("✅ admin.py загружен")