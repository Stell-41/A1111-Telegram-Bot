# services/a1111_api_service.py
import requests
import base64
import config
from typing import Optional, Tuple

def generate_image(positive_prompt: str, negative_prompt: str) -> Optional[bytes]:
    """
    Отправляет запрос на генерацию изображения в Automatic1111 API.
    Возвращает изображение в виде байтов или None в случае ошибки.
    """
    api_url = f"{config.A1111_API_URL}/sdapi/v1/txt2img"
    
    # Основные параметры для генерации. Их можно вынести в конфиг или дать настраивать пользователю.
    payload = {
        "prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "steps": 25,
        "sampler_name": "DPM++ 2M Karras",
        "cfg_scale": 7,
        "width": 512,
        "height": 768,
    }

    try:
        # Отправляем POST-запрос с таймаутом (например, 5 минут)
        response = requests.post(url=api_url, json=payload, timeout=300)
        # Проверяем, что запрос успешен (код 200)
        response.raise_for_status()
        
        r = response.json()
        
        # Декодируем изображение из формата base64
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