# main.py
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

try:
    import config
except ImportError:
    print("Ошибка: Файл config.py не найден.")
    print("Пожалуйста, скопируйте config_example.py в config.py и заполните его.")
    sys.exit(1)

from bot.handlers import user_handlers, admin_handlers
from bot.middleware import SubscriptionMiddleware # <-- Импортируем Middleware

async def main():
    # Настройка логирования для отладки
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    # Инициализация бота и диспетчера
    dp = Dispatcher(storage=MemoryStorage())
    bot = Bot(token=config.BOT_TOKEN)

    # Регистрируем Middleware для проверки подписки
    # Этот обработчик будет срабатывать на каждое входящее событие
    dp.update.middleware(SubscriptionMiddleware())

    # Регистрация роутеров. Роутер админа должен идти первым
    dp.include_router(admin_handlers.router)
    dp.include_router(user_handlers.router)
    
    # Удаляем вебхуки, если они были установлены ранее
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем polling
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")