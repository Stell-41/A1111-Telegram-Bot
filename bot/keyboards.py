# bot/keyboards.py
from aiogram import types
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services.prompt_logic import load_character_data
from bot.middleware import load_settings
from services.user_data_service import get_user_data

# Константа со списком семплеров для удобства
SAMPLERS = [
    "DPM++ 2M", "DPM++ SDE", "DPM++ 2M SDE", "DPM++ 2M SDE Heun", 
    "DPM++ 2S a", "DPM++ 3M SDE", "Euler a", "Euler", "LMS", 
    "Heun", "DPM2", "DPM2 a", "DPM fast", "DPM adaptive", 
    "Restart", "DDIM", "DDIM CFG++", "PLMS", "UniPC", "LCM"
]

# --- ОБНОВЛЕННАЯ КЛАВИАТУРА ВЫБОРА ПЕРСОНАЖЕЙ ---
def get_character_selection_keyboard(selected_ids: list = None) -> InlineKeyboardMarkup:
    """
    Создает интерактивную клавиатуру для выбора одного или нескольких персонажей.
    Отмечает уже выбранных персонажей галочкой.
    """
    if selected_ids is None:
        selected_ids = []
        
    builder = InlineKeyboardBuilder()
    characters = load_character_data()
    
    for char_id, char_data in characters.items():
        name = char_data.get("name", char_id)
        # Добавляем галочку, если персонаж уже выбран
        text = f"✅ {name}" if char_id in selected_ids else name
        builder.button(
            text=text,
            callback_data=f"toggle_char_{char_id}"
        )
    builder.adjust(1)
    
    # Добавляем кнопку "Готово", только если выбран хотя бы один персонаж
    if selected_ids:
        builder.row(types.InlineKeyboardButton(text="✅ Готово", callback_data="chars_done"))
        
    return builder.as_markup()

# --- НОВЫЕ КЛАВИАТУРЫ ДЛЯ СОХРАНЕННЫХ ПРОМТОВ ---

def get_saved_prompts_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру с сохраненными промтами и опциями."""
    builder = InlineKeyboardBuilder()
    user_data = get_user_data(user_id)
    saved_prompts = user_data.get("saved_prompts", [])
    
    # Создаем кнопки для каждого сохраненного промта
    for i, prompt in enumerate(saved_prompts):
        prompt_short = (prompt[:30] + '...') if len(prompt) > 30 else prompt
        builder.button(text=f"📋 {prompt_short}", callback_data=f"use_prompt_{i}")
    
    builder.adjust(1) # Каждый промт на новой строке
    
    # Кнопки управления
    action_buttons = []
    if len(saved_prompts) > 0:
        action_buttons.append(types.InlineKeyboardButton(
            text="🗑️ Удалить промт", callback_data="manage_prompts_delete"
        ))
    
    action_buttons.append(types.InlineKeyboardButton(
        text="⌨️ Ввести новый/временный", callback_data="manage_prompts_new"
    ))
    builder.row(*action_buttons)
    
    return builder.as_markup()

def get_delete_prompts_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора промта для удаления."""
    builder = InlineKeyboardBuilder()
    user_data = get_user_data(user_id)
    saved_prompts = user_data.get("saved_prompts", [])
    
    for i, prompt in enumerate(saved_prompts):
        prompt_short = (prompt[:30] + '...') if len(prompt) > 30 else prompt
        builder.button(text=f"❌ {prompt_short}", callback_data=f"delete_prompt_{i}")
        
    builder.adjust(1)
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_prompt_menu"))
    return builder.as_markup()

def get_character_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора персонажа."""
    builder = InlineKeyboardBuilder()
    characters = load_character_data()
    for char_id, char_data in characters.items():
        builder.button(
            text=char_data.get("name", char_id),
            callback_data=f"select_char_{char_id}"
        )
    builder.adjust(1)
    return builder.as_markup()

def get_settings_keyboard(settings: dict) -> InlineKeyboardMarkup:
    """Клавиатура настроек."""
    builder = InlineKeyboardBuilder()
    
    model_name = settings.get("model_name")
    if model_name:
        aliases = load_settings().get("model_aliases", {})
        display_name = aliases.get(model_name, model_name) 
    else:
        display_name = "Не выбрана"
    
    display_name_short = (display_name[:25] + '...') if len(display_name) > 25 else display_name

    builder.button(text=f"Model: {display_name_short}", callback_data="edit_setting_model_name")
    builder.button(text=f"Sampler: {settings['sampler_name']}", callback_data="edit_setting_sampler_name")
    builder.button(text=f"Steps: {settings['steps']}", callback_data="edit_setting_steps")
    builder.button(text=f"CFG Scale: {settings['cfg_scale']}", callback_data="edit_setting_cfg_scale")
    builder.button(text=f"Ширина: {settings['width']}", callback_data="edit_setting_width")
    builder.button(text=f"Высота: {settings['height']}", callback_data="edit_setting_height")
    
    builder.button(text="✅ Готово, ввести промт", callback_data="settings_done")
    
    builder.adjust(1, 2, 2, 2, 1)
    return builder.as_markup()

def get_model_selection_keyboard(models: list, aliases: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for model_file in models:
        display_name = aliases.get(model_file, model_file)
        builder.button(
            text=display_name,
            callback_data=f"set_model_{model_file}"
        )
    builder.adjust(1)
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад в настройки", callback_data="back_to_settings"))
    return builder.as_markup()

def get_generation_keyboard(prompt_index: int, total_prompts: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    prev_index = prompt_index - 1 if prompt_index > 0 else total_prompts - 1
    next_index = prompt_index + 1 if prompt_index < total_prompts - 1 else 0
    builder.button(text="⬅️", callback_data=f"nav_{prev_index}")
    builder.button(text=f"{prompt_index + 1}/{total_prompts}", callback_data="ignore")
    builder.button(text="➡️", callback_data=f"nav_{next_index}")
    builder.button(text="🖼️ Сгенерировать это", callback_data=f"generate_img_{prompt_index}")
    builder.button(text="🔢 Указать количество", callback_data="generate_batch_start")
    builder.button(text="💥 Сгенерировать все", callback_data="generate_all")
    builder.adjust(3, 1, 2)
    return builder.as_markup()

def get_sampler_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for sampler in SAMPLERS:
        builder.button(
            text=sampler,
            callback_data=f"set_sampler_{sampler}"
        )
    builder.adjust(2)
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад в настройки", callback_data="back_to_settings"))
    return builder.as_markup()

# --- НОВАЯ КЛАВИАТУРА ДЛЯ ДЕЙСТВИЙ ПОСЛЕ ГЕНЕРАЦИИ ---
def get_post_generation_keyboard(current_index: int, total_prompts: int) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с действиями после успешной генерации одного изображения.
    """
    builder = InlineKeyboardBuilder()
    
    # Проверяем, есть ли еще промты для генерации
    remaining_prompts = total_prompts - (current_index + 1)
    
    builder.button(text="📖 Выбрать другой промт", callback_data="post_gen_show_prompts")
    
    if remaining_prompts > 0:
        builder.button(text=f"💥 Сгенерировать остальные ({remaining_prompts})", callback_data="post_gen_all_remaining")
        builder.button(text="🔢 Сгенерировать еще N...", callback_data="post_gen_batch_start")

    builder.button(text="🏠 Главное меню", callback_data="post_gen_main_menu")
    builder.adjust(1) # Все кнопки в один столбец
    return builder.as_markup()

# --- ИСПРАВЛЕННЫЕ КЛАВИАТУРЫ АДМИН-ПАНЕЛИ ---

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура админ-панели."""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить персонажа", callback_data="admin_add_char")
    builder.button(text="⚙️ Управление ботом", callback_data="admin_bot_control")
    builder.button(text="🖼️ Названия моделей", callback_data="admin_manage_aliases")
    builder.button(text="📊 Лимиты генераций", callback_data="admin_manage_limits") # <-- НОВАЯ КНОПКА
    builder.button(text="📢 Установить канал", callback_data="admin_set_channel")
    builder.button(text="⭐️ Управление Whitelist", callback_data="admin_manage_whitelist")
    builder.button(text="❌ Закрыть", callback_data="admin_cancel")
    builder.adjust(1)
    return builder.as_markup()

def get_bot_control_keyboard(current_status: str) -> InlineKeyboardMarkup:
    """Клавиатура для смены статуса бота со всеми 4-мя режимами."""
    statuses = {
        "active": "✅ Активен",
        "full_stop": "🛑 Полностью выключен",
        "prompts_only": "📝 Только промты",
        "whitelist_only": "⭐️ Только Whitelist"
    }
    builder = InlineKeyboardBuilder()
    for status_code, status_name in statuses.items():
        text = f"▶️ {status_name}" if current_status == status_code else status_name
        builder.button(text=text, callback_data=f"set_status_{status_code}")
    
    builder.button(text="⬅️ Назад", callback_data="admin_back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_whitelist_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить в Whitelist", callback_data="admin_whitelist_add")
    builder.button(text="➖ Удалить из Whitelist", callback_data="admin_whitelist_remove")
    builder.button(text="⬅️ Назад", callback_data="admin_back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_alias_management_keyboard(models: list, aliases: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for model_file in models:
        display_name = aliases.get(model_file, "Не задано")
        model_file_short = (model_file[:20] + '...') if len(model_file) > 20 else model_file
        builder.button(
            text=f"{model_file_short} -> {display_name}",
            callback_data=f"alias_model_{model_file}"
        )
    builder.adjust(1)
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back_to_main_menu"))
    return builder.as_markup()