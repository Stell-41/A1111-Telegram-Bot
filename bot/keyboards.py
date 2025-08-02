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
    builder.adjust(1) # По одной кнопке в ряд для наглядности
    return builder.as_markup()

def get_generation_keyboard(prompt_index: int, total_prompts: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для навигации и запуска генерации."""
    builder = InlineKeyboardBuilder()

    # Кнопки навигации
    prev_index = prompt_index - 1 if prompt_index > 0 else total_prompts - 1
    next_index = prompt_index + 1 if prompt_index < total_prompts - 1 else 0
    
    builder.button(text="⬅️", callback_data=f"nav_{prev_index}")
    builder.button(text=f"{prompt_index + 1}/{total_prompts}", callback_data="ignore")
    builder.button(text="➡️", callback_data=f"nav_{next_index}")
    
    # Кнопка запуска генерации
    builder.button(text="🖼️ Сгенерировать это изображение", callback_data=f"generate_img_{prompt_index}")
    builder.adjust(3, 1) # 3 кнопки навигации в ряд, 1 кнопка генерации под ними
    return builder.as_markup()

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для админ-панели."""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить персонажа", callback_data="admin_add_char")
    builder.button(text="❌ Закрыть", callback_data="admin_cancel")
    return builder.as_markup()