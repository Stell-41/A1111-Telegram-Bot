# services/prompt_logic.py
import json
from itertools import product
from typing import List, Dict, Any, Tuple

DATA_FILE_PATH = "data/characters.json"

def load_character_data() -> Dict[str, Any]:
    """Загружает данные о персонажах из JSON-файла."""
    try:
        # Пробуем загрузить основной файл. Если его нет, используем пример.
        with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        with open("data/characters_example.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_character_data(data: Dict[str, Any]):
    """Сохраняет данные о персонажах в JSON-файл."""
    with open(DATA_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generate_prompts_for_character(character_id: str, base_prompt: str) -> List[Tuple[str, str]]:
    """
    Генерирует все возможные комбинации промтов для выбранного персонажа.
    """
    all_characters = load_character_data()
    char_data = all_characters.get(character_id)

    if not char_data:
        return []

    # Собираем все опциональные теги в один набор для последующего вычисления negative prompt
    all_optional_tags = set(char_data.get("poses", []))
    all_optional_tags.update(char_data.get("environments", []))
    
    # Собираем списки для комбинаторики
    combinatorics_lists = [
        char_data.get("poses") or [""],  # Если список пуст, добавляем пустую строку, чтобы комбинаторика не ломалась
        char_data.get("environments") or [""]
    ]
    
    optional_categories = char_data.get("optional_categories", {})
    for category, tags in optional_categories.items():
        all_optional_tags.update(tags)
        combinatorics_lists.append(tags)

    # Генерируем все возможные комбинации с помощью itertools.product
    all_combinations = list(product(*combinatorics_lists))
    generated_prompts = []

    for combo in all_combinations:
        # Теги, которые попали в эту конкретную генерацию
        current_tags_set = {tag for tag in combo if tag}
        
        # --- Собираем POSITIVE prompt ---
        positive_parts = [base_prompt]
        positive_parts.extend(char_data.get("mandatory_tags", []))
        positive_parts.extend(list(current_tags_set))
        
        # Объединяем теги, удаляя пустые строки, если они были
        positive_prompt = ", ".join(filter(None, positive_parts))

        # --- Собираем NEGATIVE prompt ---
        negative_tags_set = all_optional_tags - current_tags_set
        negative_prompt = ", ".join(sorted(list(negative_tags_set)))
        
        generated_prompts.append((positive_prompt, negative_prompt))
        
    return generated_prompts