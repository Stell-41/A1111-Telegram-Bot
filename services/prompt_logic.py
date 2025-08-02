# services/prompt_logic.py
import json
from itertools import product
from typing import List, Dict, Any, Tuple
from pathlib import Path

# --- Определяем абсолютные пути к правильным файлам ---
BASE_DIR = Path(__file__).parent.parent
DATA_FILE_PATH = BASE_DIR / "data" / "characters.json"
EXAMPLE_DATA_FILE_PATH = BASE_DIR / "data" / "characters_example.json"


def load_character_data() -> Dict[str, Any]:
    """Загружает данные о персонажах из JSON-файла."""
    # Загружаем основной файл
    try:
        with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
            # Сразу получаем словарь персонажей
            return json.load(f).get("characters", {})
    except (FileNotFoundError, json.JSONDecodeError):
        # Если не получилось, загружаем пример
        try:
            with open(EXAMPLE_DATA_FILE_PATH, "r", encoding="utf-8") as f:
                # Сразу получаем словарь персонажей
                return json.load(f).get("characters", {})
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"!!! ВНИМАНИЕ: Не удалось загрузить файлы персонажей. Возвращены пустые данные.")
            return {}
        
# --- НОВАЯ ФУНКЦИЯ ГЕНЕРАЦИИ ДЛЯ НЕСКОЛЬКИХ ПЕРСОНАЖЕЙ ---
def generate_prompts_for_characters(character_ids: List[str], base_prompt: str) -> List[Tuple[str, str]]:
    """
    Генерирует комбинации для списка персонажей, объединяя их теги.
    """
    all_characters = load_character_data()
    selected_chars_data = [all_characters.get(cid) for cid in character_ids if cid in all_characters]

    if not selected_chars_data:
        return []

    # 1. Объединяем все теги от всех персонажей
    final_mandatory_tags = []
    all_optional_tags_set = set()
    combinatorics_lists = []

    for char_data in selected_chars_data:
        final_mandatory_tags.extend(char_data.get("mandatory_tags", []))
        
        for category, tags in char_data.get("optional_categories", {}).items():
            if tags:
                all_optional_tags_set.update(tags)
                combinatorics_lists.append(tags + [""])
        
        poses = char_data.get("poses", [])
        if poses:
            all_optional_tags_set.update(poses)
            combinatorics_lists.append(poses + [""])

        environments = char_data.get("environments", [])
        if environments:
            all_optional_tags_set.update(environments)
            combinatorics_lists.append(environments + [""])

    # 2. Генерируем комбинации
    generated_prompts = []
    
    if not combinatorics_lists:
        # Добавляем тег о количестве персонажей, если их больше одного
        if len(selected_chars_data) > 1:
            base_prompt = f"{len(selected_chars_data)}girls, " + base_prompt
        
        positive_parts = [base_prompt] + final_mandatory_tags
        positive_prompt = ", ".join(filter(None, positive_parts))
        generated_prompts.append((positive_prompt, ""))
        return generated_prompts
    
    all_combinations = list(product(*combinatorics_lists))

    for combo in all_combinations:
        current_tags_set = {tag for tag in combo if tag}
        
        # Модифицируем базовый промт, если персонажей несколько
        current_base_prompt = base_prompt
        if len(selected_chars_data) > 1:
            # Умное добавление тега о количестве персонажей
            # (можно заменить на более сложную логику, если нужно)
            current_base_prompt = f"{len(selected_chars_data)}girls, " + base_prompt
            
        positive_parts = [current_base_prompt] + final_mandatory_tags + list(current_tags_set)
        positive_prompt = ", ".join(filter(None, positive_parts))

        negative_tags_set = all_optional_tags_set - current_tags_set
        negative_prompt = ", ".join(sorted(list(negative_tags_set)))
        
        generated_prompts.append((positive_prompt, negative_prompt))
        
    return generated_prompts

def save_character_data(data: Dict[str, Any]):
    """Сохраняет данные о персонажах в JSON-файл."""
    # Сохраняем в правильной структуре с главным ключом "characters"
    full_db = {"characters": data}
    with open(DATA_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(full_db, f, ensure_ascii=False, indent=2)