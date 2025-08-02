# bot/handlers/admin_handlers.py
import json
from typing import Union
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder # <-- ДОБАВЛЕН ИМПОРТ
import config
from bot.states import AdminFlow, SettingsFlow, ModelAliasFlow, LimitFlow
from bot.keyboards import (
    get_admin_keyboard, get_whitelist_keyboard, get_bot_control_keyboard,
    get_alias_management_keyboard
)
from services.prompt_logic import load_character_data, save_character_data
from services.a1111_api_service import get_available_models
from bot.middleware import load_settings

router = Router()
# Фильтр на админов
router.message.filter(F.from_user.id.in_(config.ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(config.ADMIN_IDS))

# --- ОБЩИЕ АДМИНСКИЕ КОМАНДЫ ---
@router.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Добро пожаловать в панель администратора!", reply_markup=get_admin_keyboard())

@router.callback_query(F.data == "admin_cancel")
async def cancel_action(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Действие отменено.")
    await callback.answer()

@router.callback_query(F.data == "admin_back_to_main_menu")
async def back_to_main_admin_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Панель администратора:", reply_markup=get_admin_keyboard())
    await callback.answer()


# --- УПРОЩЕННАЯ ЛОГИКА ДОБАВЛЕНИЯ ПЕРСОНАЖА ---

@router.callback_query(F.data == "admin_add_char")
async def start_add_character(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminFlow.waiting_for_id)
    await callback.message.edit_text(
        "**Шаг 1/6: ID**\nВведите уникальный ID для персонажа (латиницей, без пробелов).",
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
    await message.answer("**Шаг 2/6: Имя**\nВведите отображаемое имя персонажа.", parse_mode="Markdown")

@router.message(AdminFlow.waiting_for_name)
async def enter_char_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AdminFlow.waiting_for_mandatory_tags)
    await message.answer(
        "**Шаг 3/6: Обязательные теги**\nПеречислите через запятую.",
        parse_mode="Markdown"
    )

@router.message(AdminFlow.waiting_for_mandatory_tags)
async def enter_mandatory_tags(message: types.Message, state: FSMContext):
    await state.update_data(mandatory_tags=[tag.strip() for tag in message.text.split(',')])
    await state.set_state(AdminFlow.waiting_for_poses)
    await message.answer(
        "**Шаг 4/6: Позы**\nПеречислите теги поз через запятую. Если их нет, отправьте `0`.",
        parse_mode="Markdown"
    )

@router.message(AdminFlow.waiting_for_poses)
async def enter_poses(message: types.Message, state: FSMContext):
    if message.text.strip() != '0':
        await state.update_data(poses=[tag.strip() for tag in message.text.split(',')])
    else:
        await state.update_data(poses=[])
    await state.set_state(AdminFlow.waiting_for_environments)
    await message.answer(
        "**Шаг 5/6: Окружения**\nПеречислите теги окружений через запятую. Если их нет, отправьте `0`.",
        parse_mode="Markdown"
    )

@router.message(AdminFlow.waiting_for_environments)
async def enter_environments(message: types.Message, state: FSMContext):
    if message.text.strip() != '0':
        await state.update_data(environments=[tag.strip() for tag in message.text.split(',')])
    else:
        await state.update_data(environments=[])
    await state.update_data(optional_categories={})
    await state.set_state(AdminFlow.waiting_for_optional_category_name)
    await message.answer(
        "**Шаг 6/6: Опциональные категории**\nВведите название первой категории (например, `одежда`).\n"
        "Когда закончите, напишите `готово`.",
        parse_mode="Markdown"
    )

@router.message(AdminFlow.waiting_for_optional_category_name)
async def process_optional_category_name(message: types.Message, state: FSMContext):
    if message.text.lower().strip() == 'готово':
        data = await state.get_data()
        all_chars = load_character_data()
        
        new_char_data = {
            "name": data.get("name"),
            "mandatory_tags": data.get("mandatory_tags", []),
            "optional_categories": data.get("optional_categories", {}),
            "poses": data.get("poses", []),
            "environments": data.get("environments", [])
        }
        all_chars[data["char_id"]] = new_char_data
        save_character_data(all_chars)
        await message.answer(f"✅ Персонаж `{data.get('name')}` успешно добавлен!", parse_mode="Markdown")
        await state.clear()
        # Возвращаемся в главное меню
        await cmd_admin(message, state)
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


# --- ЛОГИКА УПРАВЛЕНИЯ СТАТУСОМ БОТА ---
@router.callback_query(F.data == "admin_bot_control")
async def bot_control_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    settings = load_settings()
    current_status = settings.get("bot_status", "active")
    await callback.message.edit_text(
        "Выберите режим работы бота:",
        reply_markup=get_bot_control_keyboard(current_status)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("set_status_"))
async def set_bot_status(callback: types.CallbackQuery, state: FSMContext):
    new_status = callback.data.removeprefix("set_status_")
    settings = load_settings()
    current_status = settings.get("bot_status", "active")
    if new_status == current_status:
        await callback.answer("Этот режим уже активен.")
        return
    settings["bot_status"] = new_status
    with open("data/settings.json", "w") as f:
        json.dump(settings, f, indent=2)
    await callback.message.edit_text(
        f"Статус бота изменен. Текущий режим: `{new_status}`",
        parse_mode="Markdown",
        reply_markup=get_bot_control_keyboard(new_status)
    )
    await callback.answer("Статус обновлен")


# --- ЛОГИКА УПРАВЛЕНИЯ ПСЕВДОНИМАМИ МОДЕЛЕЙ ---
@router.callback_query(F.data == "admin_manage_aliases")
async def manage_aliases_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Загружаю список моделей из A1111...")
    models = get_available_models()
    if not models:
        await callback.message.edit_text("Не удалось получить список моделей. Убедитесь, что A1111 запущен и доступен.")
        await callback.answer()
        return
    settings = load_settings()
    aliases = settings.get("model_aliases", {})
    await callback.message.edit_text(
        "Нажмите на модель, чтобы задать или изменить для нее псевдоним:",
        reply_markup=get_alias_management_keyboard(models, aliases)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("alias_model_"))
async def alias_model_start(callback: types.CallbackQuery, state: FSMContext):
    model_file = callback.data.removeprefix("alias_model_")
    await state.set_state(ModelAliasFlow.waiting_for_alias)
    await state.update_data(model_to_alias=model_file)
    await callback.message.edit_text(
        f"Введите новый псевдоним для модели:\n`{model_file}`\n\nЧтобы удалить псевдоним, отправьте `0`.",
        parse_mode="Markdown"
    )
    await callback.answer()

@router.message(ModelAliasFlow.waiting_for_alias)
async def alias_model_finish(message: types.Message, state: FSMContext):
    alias = message.text
    user_data = await state.get_data()
    model_file = user_data.get("model_to_alias")
    settings = load_settings()
    aliases = settings.get("model_aliases", {})
    if alias == "0":
        if model_file in aliases:
            del aliases[model_file]
        await message.answer(f"Псевдоним для `{model_file}` удален.")
    else:
        aliases[model_file] = alias
        await message.answer(f"✅ Установлен псевдоним: `{model_file}` -> **{alias}**", parse_mode="Markdown")
    settings["model_aliases"] = aliases
    with open("data/settings.json", "w") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
    await state.clear()
    callback_for_menu = types.CallbackQuery(id="return_to_aliases", from_user=message.from_user, chat_instance="fake", message=message, data="admin_manage_aliases")
    await manage_aliases_menu(callback_for_menu, state)

# --- ЛОГИКА УПРАВЛЕНИЯ ЛИМИТАМИ ---
@router.callback_query(F.data == "admin_manage_limits")
async def manage_limits_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    settings = load_settings()
    default_limit = settings.get("generation_limit_default", 10)
    whitelist_limit = settings.get("generation_limit_whitelist", 20)
    
    text = (
        "Настройка лимитов пакетной генерации:\n\n"
        f"• **Обычный пользователь:** `{default_limit}` изобр./раз.\n"
        f"• **Whitelist пользователь:** `{whitelist_limit}` изобр./раз.\n\n"
        "Администраторы не имеют ограничений."
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Изменить лимит для обычных", callback_data="edit_limit_default")
    builder.button(text="Изменить лимит для Whitelist", callback_data="edit_limit_whitelist")
    builder.button(text="⬅️ Назад", callback_data="admin_back_to_main_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("edit_limit_"))
async def edit_limit_start(callback: types.CallbackQuery, state: FSMContext):
    limit_type = callback.data.removeprefix("edit_limit_")
    
    if limit_type == "default":
        await state.set_state(LimitFlow.waiting_for_default_limit)
        await callback.message.edit_text("Введите новый лимит для обычных пользователей (число):")
    elif limit_type == "whitelist":
        await state.set_state(LimitFlow.waiting_for_whitelist_limit)
        await callback.message.edit_text("Введите новый лимит для Whitelist пользователей (число):")
        
    await callback.answer()

async def process_new_limit(message: types.Message, state: FSMContext, limit_key: str):
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer("Ошибка. Введите положительное число.")
        return
        
    new_limit = int(message.text)
    settings = load_settings()
    settings[limit_key] = new_limit
    
    with open("data/settings.json", "w") as f:
        json.dump(settings, f, indent=2)
        
    await message.answer(f"✅ Лимит `{limit_key}` обновлен на значение: {new_limit}")
    await state.clear()
    
    callback_for_menu = types.CallbackQuery(id="return", from_user=message.from_user, chat_instance="fake", message=message, data="admin_manage_limits")
    await manage_limits_menu(callback_for_menu, state)

@router.message(LimitFlow.waiting_for_default_limit)
async def set_default_limit(message: types.Message, state: FSMContext):
    await process_new_limit(message, state, "generation_limit_default")

@router.message(LimitFlow.waiting_for_whitelist_limit)
async def set_whitelist_limit(message: types.Message, state: FSMContext):
    await process_new_limit(message, state, "generation_limit_whitelist")

# --- ЛОГИКА УПРАВЛЕНИЯ НАСТРОЙКАМИ ПОДПИСКИ И WHITELIST ---
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
    await message.answer("Панель администратора:", reply_markup=get_admin_keyboard())

async def show_whitelist_menu(event: Union[types.Message, types.CallbackQuery]):
    settings = load_settings()
    whitelist = settings.get("whitelist", {})
    if not whitelist:
        text = "Белый список пуст."
    else:
        text_lines = ["Текущий Whitelist:\n"]
        for user_id, user_data in whitelist.items():
            line = (f"👤 **{user_data['custom_name']}**\n"
                    f"   *Юзернейм:* `@{user_data['username']}`\n"
                    f"   *ID для удаления:* `{user_id}`")
            text_lines.append(line)
        text = "\n\n".join(text_lines)
    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(text, parse_mode="Markdown", reply_markup=get_whitelist_keyboard())
    else:
        await event.answer(text, parse_mode="Markdown", reply_markup=get_whitelist_keyboard())

@router.callback_query(F.data == "admin_manage_whitelist")
async def manage_whitelist_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_whitelist_menu(callback)
    await callback.answer()

@router.callback_query(F.data == "admin_whitelist_add")
async def whitelist_add_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SettingsFlow.waiting_for_forward)
    await callback.message.edit_text("Перешлите мне любое сообщение от пользователя, которого вы хотите добавить в белый список.")
    await callback.answer()

@router.message(SettingsFlow.waiting_for_forward, F.forward_from)
async def whitelist_add_get_forward(message: types.Message, state: FSMContext):
    forwarded_user = message.forward_from
    if not forwarded_user:
        await message.answer("Не удалось получить информацию о пользователе. Убедитесь, что он не скрыл свой профиль в настройках конфиденциальности 'Пересылка сообщений'.")
        return
    settings = load_settings()
    if str(forwarded_user.id) in settings["whitelist"]:
        await message.answer("Этот пользователь уже находится в белом списке.")
        await state.clear()
        return
    await state.update_data(
        new_whitelist_user_id=forwarded_user.id,
        new_whitelist_username=forwarded_user.username or "N/A"
    )
    await state.set_state(SettingsFlow.waiting_for_custom_name)
    await message.answer(f"Отлично, пользователь @{forwarded_user.username} получен. Теперь введите для него кастомное имя (например, 'Тестировщик').")

@router.message(SettingsFlow.waiting_for_custom_name)
async def whitelist_add_get_name(message: types.Message, state: FSMContext):
    custom_name = message.text
    user_data = await state.get_data()
    user_id = user_data["new_whitelist_user_id"]
    username = user_data["new_whitelist_username"]
    settings = load_settings()
    settings["whitelist"][str(user_id)] = {"username": username, "custom_name": custom_name}
    with open("data/settings.json", "w") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
    await message.answer(f"✅ Пользователь **{custom_name}** (@{username}) успешно добавлен в белый список!", parse_mode="Markdown")
    await state.clear()
    await show_whitelist_menu(message)

@router.callback_query(F.data == "admin_whitelist_remove")
async def whitelist_remove_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SettingsFlow.waiting_for_user_to_remove)
    await callback.message.edit_text("Отправьте ID пользователя для удаления из Whitelist (вы можете скопировать его из списка выше).")
    await callback.answer()

@router.message(SettingsFlow.waiting_for_user_to_remove)
async def whitelist_remove_finish(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("ID должен быть числом. Попробуйте снова.")
        return
    user_id_to_remove = message.text
    settings = load_settings()
    if user_id_to_remove in settings["whitelist"]:
        removed_user_name = settings["whitelist"][user_id_to_remove]["custom_name"]
        del settings["whitelist"][user_id_to_remove]
        with open("data/settings.json", "w") as f:
            json.dump(settings, f, indent=2)
        await message.answer(f"✅ Пользователь **{removed_user_name}** (`{user_id_to_remove}`) удален из Whitelist.", parse_mode="Markdown")
    else:
        await message.answer(f"⚠️ Пользователя с ID `{user_id_to_remove}` нет в Whitelist.")
    await state.clear()
    await show_whitelist_menu(message)