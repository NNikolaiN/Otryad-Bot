from aiogram import Bot, Dispatcher
from config import TOKEN
from handlers import user
from handlers import admin

bot = Bot(token=TOKEN)
dp = Dispatcher()

dp.include_router(admin.router)
dp.include_router(user.router)

async def main():
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(f"Error starting bot: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())