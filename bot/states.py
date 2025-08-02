# bot/states.py
from aiogram.fsm.state import State, StatesGroup

class GenerateFlow(StatesGroup):
    """Упрощенные состояния для процесса генерации."""
    choosing_character = State()
    settings_menu = State()
    waiting_for_setting_value = State()
    waiting_for_base_prompt = State()
    waiting_for_batch_amount = State()
    viewing_results = State()

class AdminFlow(StatesGroup):
    """Состояния для админ-панели добавления персонажа."""
    waiting_for_id = State()
    waiting_for_name = State()
    waiting_for_mandatory_tags = State()
    waiting_for_poses = State()
    waiting_for_environments = State()
    waiting_for_optional_category_name = State()
    waiting_for_optional_category_tags = State()

class SettingsFlow(StatesGroup):
    """Состояния для управления настройками подписки и белым списком."""
    waiting_for_channel_id = State()
    waiting_for_forward = State()
    waiting_for_custom_name = State()
    waiting_for_user_to_remove = State()

class ModelAliasFlow(StatesGroup):
    """Состояния для управления псевдонимами моделей."""
    choosing_model_to_alias = State()
    waiting_for_alias = State()

class LimitFlow(StatesGroup):
    waiting_for_default_limit = State()
    waiting_for_whitelist_limit = State()