# bot/keyboards.py
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services.prompt_logic import load_character_data

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
    """Создает клавиатуру для изменения настроек генерации."""
    builder = InlineKeyboardBuilder()
    
    builder.button(text=f"Steps: {settings['steps']}", callback_data="edit_setting_steps")
    builder.button(text=f"CFG Scale: {settings['cfg_scale']}", callback_data="edit_setting_cfg_scale")
    builder.button(text=f"Width: {settings['width']}", callback_data="edit_setting_width")
    builder.button(text=f"Height: {settings['height']}", callback_data="edit_setting_height")
    builder.button(
        text=f"Sampler: {settings['sampler_name']}",
        callback_data="edit_setting_sampler_name"
    )
    
    builder.button(text="✅ Готово, ввести промт", callback_data="settings_done")
    
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()

def get_generation_keyboard(prompt_index: int, total_prompts: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для навигации и запуска генерации."""
    builder = InlineKeyboardBuilder()

    prev_index = prompt_index - 1 if prompt_index > 0 else total_prompts - 1
    next_index = prompt_index + 1 if prompt_index < total_prompts - 1 else 0
    
    builder.button(text="⬅️", callback_data=f"nav_{prev_index}")
    builder.button(text=f"{prompt_index + 1}/{total_prompts}", callback_data="ignore")
    builder.button(text="➡️", callback_data=f"nav_{next_index}")
    
    builder.button(text="🖼️ Сгенерировать это изображение", callback_data=f"generate_img_{prompt_index}")
    builder.adjust(3, 1)
    return builder.as_markup()

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для админ-панели."""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить персонажа", callback_data="admin_add_char")
    builder.button(text="📢 Установить канал", callback_data="admin_set_channel")
    builder.button(text="⭐️ Управление Whitelist", callback_data="admin_manage_whitelist")
    builder.button(text="❌ Закрыть", callback_data="admin_cancel")
    builder.adjust(1) # Все кнопки в один столбец для наглядности
    return builder.as_markup()

def get_whitelist_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для управления белым списком."""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить ID в Whitelist", callback_data="admin_whitelist_add")
    builder.button(text="➖ Удалить ID из Whitelist", callback_data="admin_whitelist_remove")
    builder.button(text="⬅️ Назад", callback_data="admin_back_to_menu")
    builder.adjust(1)
    return builder.as_markup()