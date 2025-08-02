# services/a1111_api_service.py
import requests
import base64
import config
from typing import Optional

def generate_image(positive_prompt: str, negative_prompt: str, settings: dict) -> Optional[bytes]:
    """
    Отправляет запрос на генерацию изображения в Automatic1111 API,
    используя переданные настройки.
    """
    api_url = f"{config.A1111_API_URL}/sdapi/v1/txt2img"
    
    # Payload формируется на основе переданных настроек.
    # .get() используется для безопасного получения значений с указанием умолчаний.
    payload = {
        "prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "steps": int(settings.get("steps", 25)),
        "sampler_name": settings.get("sampler_name", "DPM++ 2M Karras"),
        "cfg_scale": float(settings.get("cfg_scale", 7.0)),
        "width": int(settings.get("width", 512)),
        "height": int(settings.get("height", 768)),
        "save_images": True  # Сохраняем изображение на ПК
    }

    try:
        response = requests.post(url=api_url, json=payload, timeout=300)
        response.raise_for_status()
        
        r = response.json()
        
        if 'images' in r and r['images']:
            image_data = base64.b64decode(r['images'][0])
            return image_data
        else:
            print("API не вернуло изображение в ответе.")
            return None

    except requests.exceptions.Timeout:
        print(f"Ошибка: Таймаут при подключении к {api_url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при подключении к A1111 по адресу {api_url}: {e}")
        return None
    except Exception as e:
        print(f"Произошла непредвиденная ошибка: {e}")
        return None