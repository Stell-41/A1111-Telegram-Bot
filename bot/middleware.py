# bot/middleware.py
import json
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject, User
from aiogram.exceptions import TelegramBadRequest

import config

# Путь к файлу настроек
SETTINGS_FILE = "data/settings.json"

def load_settings() -> dict:
    """Загружает настройки из JSON-файла."""
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Если файла нет или он пуст, создаем его с дефолтными значениями
        default_settings = {"required_channel_id": None, "whitelist": []}
        with open(SETTINGS_FILE, "w") as f:
            json.dump(default_settings, f)
        return default_settings

class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем объект пользователя, от которого пришло событие
        user: User = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        # Проверяем, является ли пользователь админом бота или находится в вайтлисте
        settings = load_settings()
        if user.id in config.ADMIN_IDS or user.id in settings["whitelist"]:
            return await handler(event, data)

        # Проверяем, установлен ли канал для подписки
        channel_id = settings.get("required_channel_id")
        if not channel_id:
            return await handler(event, data)

        # Проверяем подписку
        bot: Bot = data.get("bot")
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user.id)
            # Разрешаем доступ, если статус 'creator', 'administrator' или 'member'
            if member.status.value in ["creator", "administrator", "member"]:
                return await handler(event, data)
        except TelegramBadRequest as e:
            # Обрабатываем случай, если канал не найден или бот не админ
            print(f"Ошибка проверки подписки: {e}")
            await event.answer("Произошла ошибка проверки подписки. Обратитесь к администратору.")
            return

        # Если пользователь не подписан, отправляем ему сообщение
        channel_link = f"https://t.me/{channel_id.replace('@', '')}" if '@' in str(channel_id) else "канал"
        text = (f"Для использования бота, пожалуйста, подпишитесь на наш {channel_link}.\n\n"
                f"После подписки повторите ваше действие.")
        
        # Отвечаем в зависимости от типа события (сообщение или колбэк)
        if hasattr(event, "message") and event.message:
            await event.message.answer(text)
        else:
            await event.answer(text, show_alert=True)
        return