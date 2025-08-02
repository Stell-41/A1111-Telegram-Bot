# bot/states.py
from aiogram.fsm.state import State, StatesGroup

class GenerateFlow(StatesGroup):
    """Состояния для процесса генерации промтов и изображений."""
    choosing_character = State()
    waiting_for_base_prompt = State()
    viewing_results = State()

class AdminFlow(StatesGroup):
    """Состояния для админ-панели."""
    waiting_for_id = State()
    waiting_for_name = State()
    waiting_for_mandatory_tags = State()
    waiting_for_poses = State()
    waiting_for_environments = State()
    waiting_for_optional_category_name = State()
    waiting_for_optional_category_tags = State()