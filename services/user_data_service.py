# services/user_data_service.py
import json
from typing import Dict, List

USER_SETTINGS_FILE = "data/user_settings.json"
MAX_SAVED_PROMPTS = 10

# Настройки по умолчанию
DEFAULT_USER_DATA = {
    "settings": {
        "steps": 25,
        "cfg_scale": 7.0,
        "width": 512,
        "height": 768,
        "sampler_name": "DPM++ 2M Karras",
        "model_name": None
    },
    "saved_prompts": []
}

def _load_all_user_data() -> Dict:
    """Загружает данные всех пользователей."""
    try:
        with open(USER_SETTINGS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save_all_user_data(data: Dict):
    """Сохраняет данные всех пользователей."""
    with open(USER_SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user_data(user_id: int) -> Dict:
    """Получает полные данные пользователя (настройки и промты)."""
    all_data = _load_all_user_data()
    user_data = all_data.get(str(user_id))

    if user_data:
        # Убедимся, что все ключи на месте
        user_data.setdefault("settings", DEFAULT_USER_DATA["settings"])
        user_data.setdefault("saved_prompts", DEFAULT_USER_DATA["saved_prompts"])
        return user_data
        
    return DEFAULT_USER_DATA.copy()

def save_user_data(user_id: int, data: Dict):
    """Сохраняет полные данные пользователя."""
    all_data = _load_all_user_data()
    all_data[str(user_id)] = data
    _save_all_user_data(all_data)

# --- Новые функции для управления промтами ---

def add_saved_prompt(user_id: int, prompt: str) -> bool:
    """Добавляет промт, если не превышен лимит. Возвращает True в случае успеха."""
    user_data = get_user_data(user_id)
    if len(user_data["saved_prompts"]) < MAX_SAVED_PROMPTS:
        if prompt not in user_data["saved_prompts"]:
            user_data["saved_prompts"].append(prompt)
            save_user_data(user_id, user_data)
        return True
    return False

def remove_saved_prompt(user_id: int, prompt_index: int):
    """Удаляет сохраненный промт по индексу."""
    user_data = get_user_data(user_id)
    if 0 <= prompt_index < len(user_data["saved_prompts"]):
        del user_data["saved_prompts"][prompt_index]
        save_user_data(user_id, user_data)