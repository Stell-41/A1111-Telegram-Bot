# services/a1111_api_service.py
import requests
import base64
import config
from typing import Optional, List, Dict

def get_available_models() -> List[str]:
    """Получает список доступных моделей (файлов) из A1111."""
    # ИСПОЛЬЗУЕМ ДРУГОЙ, БОЛЕЕ УНИВЕРСАЛЬНЫЙ АДРЕС API
    api_url = f"{config.A1111_API_URL}/sdapi/v1/refresh-checkpoints"
    try:
        # Этот запрос заставляет A1111 обновить список и возвращает его
        response = requests.post(url=api_url, timeout=10)
        response.raise_for_status()
        
        # Теперь получаем сам список моделей
        api_url_get = f"{config.A1111_API_URL}/sdapi/v1/sd-models"
        response_get = requests.get(url=api_url_get, timeout=10)
        response_get.raise_for_status()

        models = response_get.json()
        return [model["model_name"] for model in models]
    except requests.exceptions.RequestException as e:
        print(f"Ошибка получения списка моделей из A1111: {e}")
        return []

def set_active_model(model_filename: str) -> bool:
    """Устанавливает активную модель в A1111."""
    api_url = f"{config.A1111_API_URL}/sdapi/v1/options"
    payload = {"sd_model_checkpoint": model_filename}
    try:
        response = requests.post(url=api_url, json=payload, timeout=60)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Ошибка установки модели {model_filename} в A1111: {e}")
        return False

def generate_image(positive_prompt: str, negative_prompt: str, settings: dict) -> Optional[bytes]:
    """Отправляет запрос на генерацию изображения в Automatic1111 API."""
    # Сначала убедимся, что установлена нужная модель
    model_to_set = settings.get("model_name")
    if not model_to_set or not set_active_model(model_to_set):
        print("Не удалось установить модель перед генерацией.")
        # Можно либо прервать, либо генерировать с текущей моделью
        # Мы продолжим, но в логах будет ошибка
    
    api_url = f"{config.A1111_API_URL}/sdapi/v1/txt2img"
    payload = {
        "prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "steps": int(settings.get("steps", 25)),
        "sampler_name": settings.get("sampler_name", "DPM++ 2M Karras"),
        "cfg_scale": float(settings.get("cfg_scale", 7.0)),
        "width": int(settings.get("width", 512)),
        "height": int(settings.get("height", 768)),
        "save_images": True
    }
    try:
        response = requests.post(url=api_url, json=payload, timeout=300)
        response.raise_for_status()
        r = response.json()
        if 'images' in r and r['images']:
            image_data = base64.b64decode(r['images'][0])
            return image_data
        return None
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при генерации изображения: {e}")
        return None