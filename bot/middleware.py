# bot/middleware.py
import json
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware, Bot, types
from aiogram.types import TelegramObject, User
from aiogram.exceptions import TelegramBadRequest

import config

SETTINGS_FILE = "data/settings.json"

def load_settings() -> dict:
    """Загружает настройки из JSON-файла."""
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        default_settings = {"required_channel_id": None, "whitelist": {}, "bot_status": "active"}
        with open(SETTINGS_FILE, "w") as f:
            json.dump(default_settings, f, indent=2)
        return default_settings

class AccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user: User = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        settings = load_settings()
        
        bot_status = settings.get("bot_status", "active")
        data["bot_status"] = bot_status
        
        if user.id in config.ADMIN_IDS:
            return await handler(event, data)

        if bot_status == "full_stop":
            if hasattr(event, "answer"):
                await event.answer("Бот временно отключен.", show_alert=True)
            return
        
        if bot_status == "whitelist_only" and str(user.id) not in settings.get("whitelist", {}):
            if hasattr(event, "answer"):
                await event.answer("В данный момент бот доступен только для ограниченного круга пользователей.", show_alert=True)
            return

        channel_id = settings.get("required_channel_id")
        if channel_id and str(user.id) not in settings.get("whitelist", {}):
            bot: Bot = data.get("bot")
            try:
                member = await bot.get_chat_member(chat_id=channel_id, user_id=user.id)
                # Исправлена проверка статуса
                if member.status.value not in ["creator", "administrator", "member"]:
                    raise TelegramBadRequest(message="User is not a member")
            except TelegramBadRequest:
                channel_link = f"https://t.me/{str(channel_id).replace('@', '')}" if '@' in str(channel_id) else "канал"
                text = f"Для использования бота, пожалуйста, подпишитесь на наш {channel_link} и повторите команду."
                
                if isinstance(event, types.Message):
                    await event.answer(text)
                elif isinstance(event, types.CallbackQuery):
                    await event.answer(text, show_alert=True)
                return
        
        return await handler(event, data)