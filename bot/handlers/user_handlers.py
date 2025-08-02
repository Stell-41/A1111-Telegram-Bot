# bot/handlers/user_handlers.py
import asyncio
from typing import Union
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile

import config
from bot.states import GenerateFlow
# --- КЛАВИАТУРЫ: СТАРАЯ get_character_keyboard УДАЛЕНА ---
from bot.keyboards import (
    get_generation_keyboard, get_settings_keyboard, get_sampler_keyboard,
    get_model_selection_keyboard, get_post_generation_keyboard,
    get_saved_prompts_keyboard, get_delete_prompts_keyboard, get_character_selection_keyboard
)
# --- ЛОГИКА: ИСПОЛЬЗУЕТСЯ НОВАЯ ФУНКЦИЯ ДЛЯ НЕСКОЛЬКИХ ПЕРСОНАЖЕЙ ---
from services.prompt_logic import generate_prompts_for_characters
from services.a1111_api_service import generate_image, get_available_models
from services.user_data_service import (
    get_user_data, save_user_data, add_saved_prompt, remove_saved_prompt, MAX_SAVED_PROMPTS
)
from bot.middleware import load_settings

router = Router()

def format_prompt_message(prompts: list, index: int) -> str:
    positive, negative = prompts[index]
    return (
        f"**Вариант {index + 1}/{len(prompts)}**\n\n"
        f"✅ **Prompt:**\n`{positive}`\n\n"
        f"❌ **Negative Prompt:**\n`{negative}`"
    )

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! 👋 Я бот для генерации промтов и изображений через A1111.\n"
        "Используй команду /generate, чтобы начать."
    )

# --- ОБНОВЛЕННЫЙ СЦЕНАРИЙ ГЕНЕРАЦИИ (ЕДИНСТВЕННАЯ ВЕРСИЯ) ---

@router.message(Command("generate"))
async def cmd_generate(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(GenerateFlow.choosing_character)
    # Инициализируем пустой список для выбранных персонажей
    await state.update_data(selected_characters=[])
    await message.answer(
        "Выберите одного или нескольких персонажей:",
        reply_markup=get_character_selection_keyboard()
    )

# Этот обработчик "переключает" персонажей в списке
@router.callback_query(GenerateFlow.choosing_character, F.data.startswith("toggle_char_"))
async def toggle_character(callback: types.CallbackQuery, state: FSMContext):
    character_id = callback.data.removeprefix("toggle_char_")
    
    user_data = await state.get_data()
    selected = user_data.get("selected_characters", [])
    
    if character_id in selected:
        selected.remove(character_id)
    else:
        selected.append(character_id)
        
    await state.update_data(selected_characters=selected)
    
    # Обновляем клавиатуру, не отправляя новое сообщение
    await callback.message.edit_reply_markup(
        reply_markup=get_character_selection_keyboard(selected)
    )
    await callback.answer()

# Этот обработчик срабатывает на кнопку "Готово"
@router.callback_query(GenerateFlow.choosing_character, F.data == "chars_done")
async def characters_selected(callback: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    if not user_data.get("selected_characters"):
        await callback.answer("Пожалуйста, выберите хотя бы одного персонажа.", show_alert=True)
        return

    # Переходим к настройкам
    user_id = callback.from_user.id
    user_settings = get_user_data(user_id)["settings"]
    await state.update_data(settings=user_settings)
    
    await state.set_state(GenerateFlow.settings_menu)
    await callback.message.edit_text(
        "Персонажи выбраны. Теперь настройте параметры генерации.",
        reply_markup=get_settings_keyboard(user_settings)
    )
    await callback.answer()

# --- ЛОГИКА УПРАВЛЕНИЯ НАСТРОЙКАМИ И ПРОМТАМИ ---

@router.callback_query(GenerateFlow.settings_menu, F.data == "settings_done")
async def settings_done(callback: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    if not user_data.get("settings", {}).get("model_name"):
        await callback.answer("Пожалуйста, сначала выберите модель.", show_alert=True)
        return

    await state.set_state(GenerateFlow.waiting_for_base_prompt)
    await callback.message.edit_text(
        "Выберите сохраненный базовый промт или введите новый:",
        reply_markup=get_saved_prompts_keyboard(callback.from_user.id)
    )
    await callback.answer()

@router.callback_query(GenerateFlow.settings_menu, F.data.startswith("edit_setting_"))
async def edit_setting(callback: types.CallbackQuery, state: FSMContext):
    setting_key = callback.data.removeprefix("edit_setting_")

    if setting_key == "model_name":
        await callback.message.edit_text("Загружаю список моделей из A1111...")
        models = get_available_models()
        if not models:
            await callback.answer("Не удалось получить список моделей. Проверьте, что A1111 запущен.", show_alert=True)
            user_data = await state.get_data()
            await callback.message.edit_text(
                "Настройки генерации. Они сохраняются для вашего профиля.",
                reply_markup=get_settings_keyboard(user_data["settings"])
            )
            return
        aliases = load_settings().get("model_aliases", {})
        await callback.message.edit_text(
            "Выберите модель для генерации:",
            reply_markup=get_model_selection_keyboard(models, aliases)
        )
        await callback.answer()
        return

    if setting_key == "sampler_name":
        await callback.message.edit_text(
            "Выберите семплер из списка:",
            reply_markup=get_sampler_keyboard()
        )
        await callback.answer()
        return

    await state.update_data(editing_setting=setting_key)
    await state.set_state(GenerateFlow.waiting_for_setting_value)
    
    message_text = f"Введите новое значение для `{setting_key}`:"
    if setting_key == 'cfg_scale':
        tooltip = (
            "\n\n*Подсказка по CFG Scale:*\n"
            "• *Низкое (2-6):* больше креативности.\n"
            "• *Среднее (7-10):* хороший баланс.\n"
            "• *Высокое (11+):* строгое следование промту."
        )
        message_text += tooltip
        
    await callback.message.edit_text(message_text, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(GenerateFlow.settings_menu, F.data.startswith("set_model_"))
async def select_model(callback: types.CallbackQuery, state: FSMContext):
    model_name = callback.data.removeprefix("set_model_")
    user_data_state = await state.get_data()
    settings = user_data_state.get("settings")
    settings["model_name"] = model_name
    
    user_data_db = get_user_data(callback.from_user.id)
    user_data_db["settings"] = settings
    save_user_data(callback.from_user.id, user_data_db)

    await state.update_data(settings=settings)
    await callback.message.edit_text(
        "Модель выбрана. Можете изменить что-то еще или нажать 'Готово'.",
        reply_markup=get_settings_keyboard(settings)
    )
    await callback.answer()

@router.callback_query(GenerateFlow.settings_menu, F.data.startswith("set_sampler_"))
async def select_sampler(callback: types.CallbackQuery, state: FSMContext):
    sampler_name = callback.data.removeprefix("set_sampler_")
    user_data_state = await state.get_data()
    settings = user_data_state.get("settings")
    settings["sampler_name"] = sampler_name
    
    user_data_db = get_user_data(callback.from_user.id)
    user_data_db["settings"] = settings
    save_user_data(callback.from_user.id, user_data_db)

    await state.update_data(settings=settings)
    await callback.message.edit_text(
        "Семплер обновлен. Можете изменить что-то еще или нажать 'Готово'.",
        reply_markup=get_settings_keyboard(settings)
    )
    await callback.answer()

@router.callback_query(GenerateFlow.settings_menu, F.data == "back_to_settings")
async def back_to_settings(callback: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    settings = user_data["settings"]
    await callback.message.edit_text(
        "Настройки генерации. Они сохраняются для вашего профиля.",
        reply_markup=get_settings_keyboard(settings)
    )
    await callback.answer()

@router.message(GenerateFlow.waiting_for_setting_value)
async def enter_setting_value(message: types.Message, state: FSMContext):
    user_data_state = await state.get_data()
    setting_key = user_data_state.get("editing_setting")
    new_value = message.text
    try:
        if setting_key in ["steps", "width", "height"]:
            new_value = int(new_value)
        elif setting_key == "cfg_scale":
            new_value = float(new_value)
    except ValueError:
        await message.answer("Ошибка формата. Пожалуйста, введите число.")
        return
        
    settings = user_data_state.get("settings")
    settings[setting_key] = new_value
    
    user_data_db = get_user_data(message.from_user.id)
    user_data_db["settings"] = settings
    save_user_data(message.from_user.id, user_data_db)
    
    await state.update_data(settings=settings)
    await state.set_state(GenerateFlow.settings_menu)
    await message.answer(
        "Настройка обновлена и сохранена.",
        reply_markup=get_settings_keyboard(settings)
    )

# --- ИСПРАВЛЕННАЯ ФУНКЦИЯ-ПОМОЩНИК ---
async def generate_and_show_prompts(message_or_callback: Union[types.Message, types.CallbackQuery], state: FSMContext, base_prompt: str):
    user_data = await state.get_data()
    # Получаем СПИСОК персонажей
    character_ids = user_data["selected_characters"]
    # Вызываем НОВУЮ функцию
    prompts = generate_prompts_for_characters(character_ids, base_prompt)
    
    if not prompts:
        await message_or_callback.answer("Не удалось сгенерировать промты.")
        await state.clear()
        return

    settings = load_settings()
    user_id = message_or_callback.from_user.id
    user_limit = float('inf')
    if user_id not in config.ADMIN_IDS:
        if str(user_id) in settings.get("whitelist", {}):
            user_limit = settings.get("generation_limit_whitelist", 20)
        else:
            user_limit = settings.get("generation_limit_default", 10)
    
    if len(prompts) > user_limit:
        text = f"Найдено {len(prompts)} комбинаций, что превышает ваш лимит в {user_limit} изображений."
        if isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.answer(text, show_alert=True)
        else:
            await message_or_callback.answer(text)
        return
        
    await state.update_data(prompts=prompts, current_index=0)
    await state.set_state(GenerateFlow.viewing_results)
    
    target_message = message_or_callback.message if isinstance(message_or_callback, types.CallbackQuery) else message_or_callback
    await target_message.answer(
        format_prompt_message(prompts, 0),
        parse_mode="Markdown",
        reply_markup=get_generation_keyboard(0, len(prompts))
    )

@router.callback_query(GenerateFlow.waiting_for_base_prompt, F.data.startswith("use_prompt_"))
async def use_saved_prompt(callback: types.CallbackQuery, state: FSMContext):
    prompt_index = int(callback.data.removeprefix("use_prompt_"))
    user_data_db = get_user_data(callback.from_user.id)
    saved_prompts = user_data_db.get("saved_prompts", [])
    
    if 0 <= prompt_index < len(saved_prompts):
        base_prompt = saved_prompts[prompt_index]
        await callback.message.edit_text(f"Использую промт: `{base_prompt}`\nГенерирую комбинации...", parse_mode="Markdown")
        await generate_and_show_prompts(callback, state, base_prompt)
    else:
        await callback.answer("Ошибка: промт не найден.", show_alert=True)

@router.callback_query(GenerateFlow.waiting_for_base_prompt, F.data == "manage_prompts_new")
async def request_new_prompt(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите ваш базовый промт. Если он новый и есть место, он будет сохранен автоматически.")
    await callback.answer()

@router.callback_query(GenerateFlow.waiting_for_base_prompt, F.data == "manage_prompts_delete")
async def delete_prompt_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Нажмите на промт, который хотите удалить:",
        reply_markup=get_delete_prompts_keyboard(callback.from_user.id)
    )
    await callback.answer()
    
@router.callback_query(GenerateFlow.waiting_for_base_prompt, F.data.startswith("delete_prompt_"))
async def delete_prompt_action(callback: types.CallbackQuery, state: FSMContext):
    prompt_index = int(callback.data.removeprefix("delete_prompt_"))
    remove_saved_prompt(callback.from_user.id, prompt_index)
    await callback.answer("Промт удален!", show_alert=True)
    await callback.message.edit_text(
        "Нажмите на промт, который хотите удалить:",
        reply_markup=get_delete_prompts_keyboard(callback.from_user.id)
    )

@router.callback_query(GenerateFlow.waiting_for_base_prompt, F.data == "back_to_prompt_menu")
async def back_to_prompt_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Выберите сохраненный базовый промт или введите новый:",
        reply_markup=get_saved_prompts_keyboard(callback.from_user.id)
    )
    await callback.answer()

# --- ЕДИНСТВЕННЫЙ ОБРАБОТЧИК ВВОДА БАЗОВОГО ПРОМТА ---
@router.message(GenerateFlow.waiting_for_base_prompt)
async def enter_base_prompt(message: types.Message, state: FSMContext):
    base_prompt = message.text.strip()
    if not base_prompt: return
    
    user_data = get_user_data(message.from_user.id)
    if base_prompt not in user_data["saved_prompts"]:
        was_added = add_saved_prompt(message.from_user.id, base_prompt)
        if was_added:
            await message.answer("📝 Новый промт сохранен!")
        elif len(user_data["saved_prompts"]) >= MAX_SAVED_PROMPTS:
            await message.answer(f"⚠️ Достигнут лимит в {MAX_SAVED_PROMPTS} сохраненных промтов. Этот промт будет использован, но не сохранен.")
    
    await generate_and_show_prompts(message, state, base_prompt)

# --- ПРОСМОТР РЕЗУЛЬТАТОВ ---
@router.callback_query(GenerateFlow.viewing_results, F.data.startswith("nav_"))
async def navigate_prompts(callback: types.CallbackQuery, state: FSMContext):
    new_index = int(callback.data.split("_")[1])
    await state.update_data(current_index=new_index)
    user_data = await state.get_data()
    prompts = user_data["prompts"]
    await callback.message.edit_text(
        format_prompt_message(prompts, new_index),
        parse_mode="Markdown",
        reply_markup=get_generation_keyboard(new_index, len(prompts))
    )
    await callback.answer()


# --- ЛОГИКА ГЕНЕРАЦИИ ИЗОБРАЖЕНИЙ ---

async def run_generation_task(message: types.Message, state: FSMContext, prompts_to_generate: list, start_index: int):
    user_data = await state.get_data()
    settings = user_data["settings"]
    total_prompts = len(user_data["prompts"])
    
    for i, (positive, negative) in enumerate(prompts_to_generate, start=1):
        current_prompt_index = start_index + i - 1
        await state.update_data(current_index=current_prompt_index)
        
        await message.answer(f"⏳ Генерирую изображение {i}/{len(prompts_to_generate)} (промт №{current_prompt_index + 1})...")
        image_bytes = generate_image(positive, negative, settings)
        
        if image_bytes:
            photo = BufferedInputFile(image_bytes, filename=f"img_{i}.png")
            await message.answer_photo(
                photo, 
                caption=f"✅ Изображение {i}/{len(prompts_to_generate)} готово!",
                reply_markup=get_post_generation_keyboard(current_prompt_index, total_prompts)
            )
        else:
            await message.answer(f"❌ Ошибка при генерации изображения {i}/{len(prompts_to_generate)}.")
        await asyncio.sleep(1)

@router.callback_query(GenerateFlow.viewing_results, F.data.startswith("generate_img_"))
async def generate_single_image(callback: types.CallbackQuery, state: FSMContext, bot_status: str):
    if bot_status == "prompts_only":
        await callback.answer("Генерация изображений временно отключена.", show_alert=True)
        return

    await callback.message.edit_text("⏳ Ваше изображение генерируется...", reply_markup=None)
    
    user_data = await state.get_data()
    prompts = user_data["prompts"]
    settings = user_data["settings"]
    index = int(callback.data.split("_")[2])
    await state.update_data(current_index=index)
    positive_prompt, negative_prompt = prompts[index]

    image_bytes = generate_image(positive_prompt, negative_prompt, settings)
    await callback.message.delete()

    if image_bytes:
        photo = BufferedInputFile(image_bytes, filename="generated_image.png")
        await callback.message.answer_photo(
            photo, 
            caption=f"✅ Изображение по промту №{index + 1} готово!",
            reply_markup=get_post_generation_keyboard(index, len(prompts))
        )
    else:
        await callback.message.answer("❌ Не удалось сгенерировать изображение. Проверьте, запущен ли A1111.")
    
    await callback.answer()

@router.callback_query(GenerateFlow.viewing_results, F.data == "generate_all")
async def generate_all_images(callback: types.CallbackQuery, state: FSMContext, bot_status: str):
    if bot_status == "prompts_only":
        await callback.answer("Генерация изображений временно отключена.", show_alert=True)
        return
        
    await callback.message.delete()
    user_data = await state.get_data()
    prompts = user_data["prompts"]
    await callback.message.answer(f"✅ Принято! Начинаю генерацию всех {len(prompts)} изображений.")
    asyncio.create_task(run_generation_task(callback.message, state, prompts, start_index=0))
    await callback.answer()

@router.callback_query(GenerateFlow.viewing_results, F.data == "generate_batch_start")
async def generate_batch_start(callback: types.CallbackQuery, state: FSMContext, bot_status: str):
    if bot_status == "prompts_only":
        await callback.answer("Генерация изображений временно отключена.", show_alert=True)
        return
    
    await state.set_state(GenerateFlow.waiting_for_batch_amount)
    await callback.message.answer("Введите, сколько изображений сгенерировать с начала (например, `10`):")
    await callback.answer()


# --- ОБРАБОТЧИКИ ДЛЯ КНОПОК ПОСЛЕ ГЕНЕРАЦИИ ---

@router.callback_query(F.data == "post_gen_main_menu")
async def post_gen_main_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete_reply_markup()
    # Отправляем новое сообщение, чтобы избежать конфликтов
    await callback.message.answer("Возврат в главное меню...")
    await cmd_generate(callback.message, state)
    await callback.answer()

@router.callback_query(F.data == "post_gen_show_prompts")
async def post_gen_show_prompts(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    user_data = await state.get_data()
    prompts = user_data.get("prompts", [])
    index = user_data.get("current_index", 0)
    
    if not prompts:
        await callback.answer("Данные о промтах не найдены, начните заново.", show_alert=True)
        return
        
    await callback.message.answer(
        format_prompt_message(prompts, index),
        parse_mode="Markdown",
        reply_markup=get_generation_keyboard(index, len(prompts))
    )
    await callback.answer()

@router.callback_query(F.data == "post_gen_all_remaining")
async def post_gen_all_remaining(callback: types.CallbackQuery, state: FSMContext, bot_status: str):
    if bot_status == "prompts_only":
        await callback.answer("Генерация изображений временно отключена.", show_alert=True)
        return
        
    user_data = await state.get_data()
    prompts = user_data.get("prompts", [])
    current_index = user_data.get("current_index", 0)
    
    remaining_prompts = prompts[current_index + 1:]
    if not remaining_prompts:
        await callback.answer("Больше нет промтов для генерации.", show_alert=True)
        return
        
    await callback.message.delete_reply_markup()
    await callback.message.answer(f"✅ Принято! Начинаю генерацию оставшихся {len(remaining_prompts)} изображений.")
    asyncio.create_task(run_generation_task(callback.message, state, remaining_prompts, start_index=current_index + 1))
    await callback.answer()

@router.callback_query(F.data == "post_gen_batch_start")
async def post_gen_batch_start(callback: types.CallbackQuery, state: FSMContext, bot_status: str):
    if bot_status == "prompts_only":
        await callback.answer("Генерация изображений временно отключена.", show_alert=True)
        return
        
    await state.set_state(GenerateFlow.waiting_for_batch_amount)
    await callback.message.answer("Введите, сколько ЕЩЕ изображений сгенерировать:")
    await callback.answer()

@router.message(GenerateFlow.waiting_for_batch_amount)
async def generate_batch_finish(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer("Пожалуйста, введите положительное число.")
        return
    
    amount = int(message.text)
    user_data = await state.get_data()
    prompts = user_data.get("prompts", [])
    current_index = user_data.get("current_index", 0)
    
    prompts_to_generate = prompts[current_index + 1 : current_index + 1 + amount]
    
    if not prompts_to_generate:
        await message.answer("Больше нет промтов для генерации.")
        await state.set_state(GenerateFlow.viewing_results)
        return

    await message.answer(f"✅ Принято! Начинаю генерацию следующих {len(prompts_to_generate)} изображений.")
    asyncio.create_task(run_generation_task(message, state, prompts_to_generate, start_index=current_index + 1))
    await state.set_state(GenerateFlow.viewing_results)

@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: types.CallbackQuery):
    await callback.answer()