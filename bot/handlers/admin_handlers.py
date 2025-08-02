# bot/handlers/admin_handlers.py
import json
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
import config
from bot.states import AdminFlow, SettingsFlow
from bot.keyboards import get_admin_keyboard, get_whitelist_keyboard
from services.prompt_logic import load_character_data, save_character_data
from bot.middleware import load_settings

router = Router()
# Применяем фильтр, чтобы команды работали только для админов
router.message.filter(F.from_user.id.in_(config.ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(config.ADMIN_IDS))

@router.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Добро пожаловать в панель администратора!", reply_markup=get_admin_keyboard())

@router.callback_query(F.data == "admin_cancel")
async def cancel_action(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Действие отменено.")
    await callback.answer()

# --- ЛОГИКА ДОБАВЛЕНИЯ ПЕРСОНАЖА ---

@router.callback_query(F.data == "admin_add_char")
async def start_add_character(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminFlow.waiting_for_id)
    await callback.message.edit_text(
        "**Шаг 1/6: ID**\nВведите уникальный ID латиницей (например, `CoolRobot`).",
        parse_mode="Markdown"
    )
    await callback.answer()

@router.message(AdminFlow.waiting_for_id)
async def enter_char_id(message: types.Message, state: FSMContext):
    if not message.text or not message.text.isalnum():
        await message.answer("Ошибка: ID должен состоять только из букв и цифр. Попробуйте снова.")
        return
    if message.text in load_character_data():
        await message.answer("Ошибка: Персонаж с таким ID уже существует.")
        return
    await state.update_data(char_id=message.text)
    await state.set_state(AdminFlow.waiting_for_name)
    await message.answer("**Шаг 2/6: Имя**\nВведите отображаемое имя (например, `Крутой Робот v2`).", parse_mode="Markdown")


@router.message(AdminFlow.waiting_for_name)
async def enter_char_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AdminFlow.waiting_for_mandatory_tags)
    await message.answer(
        "**Шаг 3/6: Обязательные теги**\nПеречислите через запятую (например, `1boy, robot, glowing eyes`).",
        parse_mode="Markdown"
    )
    
@router.message(AdminFlow.waiting_for_mandatory_tags)
async def enter_mandatory_tags(message: types.Message, state: FSMContext):
    await state.update_data(mandatory_tags=[tag.strip() for tag in message.text.split(',')])
    await state.set_state(AdminFlow.waiting_for_poses)
    await message.answer(
        "**Шаг 4/6: Позы**\nПеречислите через запятую. Если нет, напишите `пропустить`.",
        parse_mode="Markdown"
    )

@router.message(AdminFlow.waiting_for_poses)
async def enter_poses(message: types.Message, state: FSMContext):
    if message.text.lower() != 'пропустить':
        await state.update_data(poses=[tag.strip() for tag in message.text.split(',')])
    await state.set_state(AdminFlow.waiting_for_environments)
    await message.answer(
        "**Шаг 5/6: Окружение**\nПеречислите через запятую. Если нет, напишите `пропустить`.",
        parse_mode="Markdown"
    )

@router.message(AdminFlow.waiting_for_environments)
async def enter_environments(message: types.Message, state: FSMContext):
    if message.text.lower() != 'пропустить':
        await state.update_data(environments=[tag.strip() for tag in message.text.split(',')])
    await state.update_data(optional_categories={})
    await state.set_state(AdminFlow.waiting_for_optional_category_name)
    await message.answer(
        "**Шаг 6/6: Опциональные категории**\nВведите название первой категории (например, `weapon`). "
        "Когда закончите, напишите `готово`.",
        parse_mode="Markdown"
    )

@router.message(AdminFlow.waiting_for_optional_category_name)
async def process_optional_category_name(message: types.Message, state: FSMContext):
    if message.text.lower() == 'готово':
        data = await state.get_data()
        all_chars = load_character_data()
        
        new_char_data = {
            "name": data.get("name"),
            "mandatory_tags": data.get("mandatory_tags", []),
            "poses": data.get("poses", []),
            "environments": data.get("environments", []),
            "optional_categories": data.get("optional_categories", {})
        }
        all_chars[data["char_id"]] = new_char_data
        save_character_data(all_chars)
        await message.answer(f"✅ Персонаж `{data['name']}` успешно добавлен!", parse_mode="Markdown")
        await state.clear()
        return

    await state.update_data(current_category_name=message.text)
    await state.set_state(AdminFlow.waiting_for_optional_category_tags)
    await message.answer(f"Отлично. Теперь перечислите теги для категории `{message.text}` через запятую.")

@router.message(AdminFlow.waiting_for_optional_category_tags)
async def process_optional_category_tags(message: types.Message, state: FSMContext):
    tags = [tag.strip() for tag in message.text.split(',')]
    data = await state.get_data()
    
    category_name = data["current_category_name"]
    optional_categories = data.get("optional_categories", {})
    optional_categories[category_name] = tags
    
    await state.update_data(optional_categories=optional_categories)
    await state.set_state(AdminFlow.waiting_for_optional_category_name)
    await message.answer(f"Категория `{category_name}` добавлена. Введите название следующей или напишите `готово`.")


# --- ЛОГИКА УПРАВЛЕНИЯ НАСТРОЙКАМИ ПОДПИСКИ ---

@router.callback_query(F.data == "admin_set_channel")
async def set_channel_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SettingsFlow.waiting_for_channel_id)
    await callback.message.edit_text(
        "Введите ID канала (например, @mychannel или -100123456789).\n"
        "Чтобы убрать проверку, отправьте `0`."
    )
    await callback.answer()

@router.message(SettingsFlow.waiting_for_channel_id)
async def set_channel_finish(message: types.Message, state: FSMContext):
    settings = load_settings()
    if message.text == "0":
        settings["required_channel_id"] = None
        await message.answer("✅ Проверка подписки отключена.")
    else:
        if not (message.text.startswith('@') or (message.text.startswith('-100') and message.text[1:].isdigit())):
            await message.answer("Неверный формат ID. Попробуйте снова.")
            return
        settings["required_channel_id"] = message.text if message.text.startswith('@') else int(message.text)
        await message.answer(f"✅ Установлен обязательный канал: {message.text}")
    
    with open("data/settings.json", "w") as f:
        json.dump(settings, f, indent=2)
        
    await state.clear()

@router.callback_query(F.data == "admin_manage_whitelist")
async def manage_whitelist_menu(callback: types.CallbackQuery, state: FSMContext):
    settings = load_settings()
    whitelist = settings.get("whitelist", [])
    text = f"Текущий Whitelist:\n`{', '.join(map(str, whitelist)) or 'пусто'}`"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_whitelist_keyboard())
    await callback.answer()

@router.callback_query(F.data == "admin_back_to_menu")
async def back_to_admin_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Панель администратора:", reply_markup=get_admin_keyboard())
    await callback.answer()

@router.callback_query(F.data == "admin_whitelist_add")
async def whitelist_add_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SettingsFlow.waiting_for_whitelist_add)
    await callback.message.edit_text("Отправьте числовой ID пользователя для добавления в Whitelist.")
    await callback.answer()

@router.message(SettingsFlow.waiting_for_whitelist_add)
async def whitelist_add_finish(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID должен быть числом. Попробуйте снова.")
        return
        
    user_id = int(message.text)
    settings = load_settings()
    if user_id not in settings["whitelist"]:
        settings["whitelist"].append(user_id)
        with open("data/settings.json", "w") as f:
            json.dump(settings, f, indent=2)
        await message.answer(f"✅ Пользователь `{user_id}` добавлен в Whitelist.")
    else:
        await message.answer(f"⚠️ Пользователь `{user_id}` уже в Whitelist.")
    
    await state.clear()

@router.callback_query(F.data == "admin_whitelist_remove")
async def whitelist_remove_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SettingsFlow.waiting_for_whitelist_remove)
    await callback.message.edit_text("Отправьте числовой ID пользователя для удаления из Whitelist.")
    await callback.answer()

@router.message(SettingsFlow.waiting_for_whitelist_remove)
async def whitelist_remove_finish(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID должен быть числом. Попробуйте снова.")
        return
        
    user_id = int(message.text)
    settings = load_settings()
    if user_id in settings["whitelist"]:
        settings["whitelist"].remove(user_id)
        with open("data/settings.json", "w") as f:
            json.dump(settings, f, indent=2)
        await message.answer(f"✅ Пользователь `{user_id}` удален из Whitelist.")
    else:
        await message.answer(f"⚠️ Пользователя `{user_id}` нет в Whitelist.")
    
    await state.clear()