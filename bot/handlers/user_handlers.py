# bot/handlers/user_handlers.py
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile

from bot.states import GenerateFlow
from bot.keyboards import get_character_keyboard, get_generation_keyboard
from services.prompt_logic import generate_prompts_for_character
from services.a1111_api_service import generate_image

router = Router()

def format_prompt_message(prompts: list, index: int) -> str:
    """Форматирует сообщение с позитивным и негативным промтом."""
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

@router.message(Command("generate"))
async def cmd_generate(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(GenerateFlow.choosing_character)
    await message.answer("Выберите персонажа:", reply_markup=get_character_keyboard())

@router.callback_query(GenerateFlow.choosing_character, F.data.startswith("select_char_"))
async def select_character(callback: types.CallbackQuery, state: FSMContext):
    character_id = callback.data.split("_")[2]
    await state.update_data(character_id=character_id)
    await state.set_state(GenerateFlow.waiting_for_base_prompt)
    await callback.message.edit_text("Отлично! Теперь введите базовый промт (например, `masterpiece, best quality`):")
    await callback.answer()

@router.message(GenerateFlow.waiting_for_base_prompt)
async def enter_base_prompt(message: types.Message, state: FSMContext):
    await state.update_data(base_prompt=message.text)
    user_data = await state.get_data()
    character_id = user_data["character_id"]
    
    prompts = generate_prompts_for_character(character_id, message.text)
    if not prompts:
        await message.answer("Не удалось сгенерировать промты. Проверьте данные персонажа.")
        await state.clear()
        return

    await state.update_data(prompts=prompts, current_index=0)
    await state.set_state(GenerateFlow.viewing_results)
    
    await message.answer(
        format_prompt_message(prompts, 0),
        parse_mode="Markdown",
        reply_markup=get_generation_keyboard(0, len(prompts))
    )

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

@router.callback_query(GenerateFlow.viewing_results, F.data.startswith("generate_img_"))
async def generate_image_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("⏳ Ваше изображение генерируется... Это может занять несколько минут.")
    
    user_data = await state.get_data()
    prompts = user_data["prompts"]
    index = int(callback.data.split("_")[2])
    positive_prompt, negative_prompt = prompts[index]

    image_bytes = generate_image(positive_prompt, negative_prompt)
    
    # Возвращаем исходное сообщение с навигацией
    await callback.message.edit_text(
        format_prompt_message(prompts, index),
        parse_mode="Markdown",
        reply_markup=get_generation_keyboard(index, len(prompts))
    )

    if image_bytes:
        photo = BufferedInputFile(image_bytes, filename="generated_image.png")
        await callback.message.answer_photo(photo, caption="✅ Ваше изображение готово!")
    else:
        await callback.message.answer("❌ Не удалось сгенерировать изображение. Проверьте, запущен ли A1111 и доступны ли API.")
    
    await callback.answer()

@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: types.CallbackQuery):
    await callback.answer()