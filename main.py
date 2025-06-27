import asyncio
import logging
import os
import fal_client
import requests
import io
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, PhotoSize, LabeledPrice, PreCheckoutQuery, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from database import Database

load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=os.getenv('BOT_TOKEN'))
dp = Dispatcher(storage=MemoryStorage())
db = Database()

# Setup fal_client
fal_client.api_key = os.getenv('FAL_KEY')

# States
class Form(StatesGroup):
    waiting_for_photo = State()

# Constants
WOJAK_PRICE = 45  # Price in Telegram Stars
WOJAK_STICKER = "CAACAgIAAxkBAAEVzNpnesg9UT9hy0XlROZ4BF1siuRjGgACKmcAAs4dwEtnY9gKuu9g9jYE"
FIRE_EFFECT = "5046509860389126442"
STARS_EFFECT = "5104841245755180586"

# Admin usernames
ADMIN_USERNAMES = {'ennucore', 'aleksei_conf'}

# Localized texts
def get_texts(lang='ru'):
    texts = {
        'ru': {
            'start': '''🎭 Добро пожаловать в Войяк Бот!

Отправьте мне своё фото, и я превращу вас в Войяка!

🆓 Первые 3 преобразования - БЕСПЛАТНО
⭐ Следующие преобразования - 45 Telegram Stars

Просто отправьте фото!''',
    
    'photo_processing': '🔄 Обрабатываю ваше фото... Это может занять минуту.',
    
    'first_free': '🎉 Это одно из ваших бесплатных преобразований!',
    
    'need_payment': '''⭐ Ваши бесплатные преобразования закончились.

Стоимость: 45 Telegram Stars
Нажмите кнопку ниже для оплаты:''',
    
    'payment_title': 'Преобразование в Войяка',
    'payment_description': 'Превращение вашего фото в стиле Войяк',
    
    'payment_success': '✅ Оплата прошла успешно! Обрабатываю ваше фото...',
    
            'error_processing': '❌ Ошибка при обработке фото. Попробуйте ещё раз.',
            'error_no_photo': '📷 Пожалуйста, отправьте фото!',
            'error_payment': '❌ Ошибка оплаты. Попробуйте ещё раз.',
        },
        'en': {
            'start': '''🎭 Welcome to Wojak Bot!

Send me your photo, and I'll turn you into a Wojak!

🆓 First 3 transformations - FREE
⭐ Next transformations - 45 Telegram Stars

Just send a photo!''',
            
            'photo_processing': '🔄 Processing your photo... This may take a minute.',
            
            'first_free': '🎉 This is one of your free transformations!',
            
            'need_payment': '''⭐ Your free transformations are finished.

Cost: 45 Telegram Stars
Click the button below to pay:''',
            
            'payment_title': 'Wojak Transformation',
            'payment_description': 'Transform your photo into Wojak style',
            
            'payment_success': '✅ Payment successful! Processing your photo...',
            
            'error_processing': '❌ Error processing photo. Please try again.',
            'error_no_photo': '📷 Please send a photo!',
            'error_payment': '❌ Payment error. Please try again.',
        }
    }
    return texts.get(lang, texts['ru'])

# Get user language (default to Russian for now, can be extended)
def get_user_lang(user):
    # Can be extended to detect user language from Telegram settings
    return 'ru'

# Check if user is admin
def is_admin(user):
    return user.username and user.username.lower() in ADMIN_USERNAMES

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    db.create_user(user.id, user.username, user.first_name, user.last_name)
    
    await bot.send_sticker(
        chat_id=message.chat.id,
        sticker=WOJAK_STICKER,
        message_effect_id=FIRE_EFFECT,
    )
    
    lang = get_user_lang(user)
    texts = get_texts(lang)
    await message.answer(texts['start'])

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    # Check if user is admin
    if not is_admin(message.from_user):
        return
    
    # Get bot statistics
    stats = db.get_bot_stats()
    
    stats_text = f"""📊 Bot Statistics:
    
👥 Total Users: {stats['total_users']}
🆓 Users with Free Generations Left: {stats['users_with_free_left']}
💰 Total Payments: {stats['total_payments']}
⭐ Total Stars Earned: {stats['total_stars']}
🖼️ Total Generations: {stats['total_generations']}"""
    
    await message.answer(stats_text)

@dp.message(Command("give_credits"))
async def cmd_give_credits(message: Message):
    # Check if user is admin
    if not is_admin(message.from_user):
        return
    
    # Parse command arguments
    try:
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer("Usage: /give_credits <user_id>")
            return
        
        user_id = int(parts[1])
        
        # Reset user's free generations
        db.reset_free_generations(user_id)
        
        await message.answer(f"✅ Gave 3 free generations to user {user_id}")
        
    except ValueError:
        await message.answer("❌ Invalid user ID. Please provide a numeric user ID.")
    except Exception as e:
        logger.error(f"Error giving credits: {e}")
        await message.answer("❌ Error giving credits.")

@dp.message(F.photo)
async def handle_photo(message: Message):
    user_id = message.from_user.id
    user_data = db.get_user(user_id)
    
    if not user_data:
        db.create_user(user_id, message.from_user.username, 
                      message.from_user.first_name, message.from_user.last_name)
        user_data = db.get_user(user_id)
    
    # Check if user has free generations left
    if db.has_free_generations_left(user_id):
        # Free processing
        lang = get_user_lang(message.from_user)
        texts = get_texts(lang)
        
        generations_used = user_data['free_generations_used'] if user_data else 0
        remaining = 3 - generations_used
        if remaining > 1:
            await message.answer(f"{texts['first_free']} Осталось: {remaining - 1}")
        else:
            await message.answer("🎉 Это ваша последняя бесплатная генерация!")
        await message.answer(texts['photo_processing'])
        
        # Mark free generation as used
        db.use_free_generation(user_id)
        
        # Process photo
        await process_photo(message)
    else:
        # Payment required
        await send_payment_invoice(message)

async def send_payment_invoice(message: Message):
    lang = get_user_lang(message.from_user)
    texts = get_texts(lang)
    
    await message.answer(texts['need_payment'])
    
    await bot.send_invoice(
        chat_id=message.chat.id,
        title=texts['payment_title'],
        description=texts['payment_description'],
        payload=f"wojak_transform_{message.from_user.id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=texts['payment_title'], amount=WOJAK_PRICE)],
        message_effect_id=STARS_EFFECT,
    )

@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    payment = message.successful_payment
    user_id = message.from_user.id
    
    # Save payment information
    db.add_payment(user_id, payment.telegram_payment_charge_id, payment.total_amount)
    
    lang = get_user_lang(message.from_user)
    texts = get_texts(lang)
    await message.answer(texts['payment_success'])
    
    # Now we need to process photo, but we don't have photo in this message
    # So we ask user to send photo again
    await message.answer("📷 Теперь отправьте фото для преобразования!")

async def process_photo(message: Message):
    try:
        # Get photo with best quality
        photo: PhotoSize = message.photo[-1]
        
        # Get file
        file = await bot.get_file(photo.file_id)
        
        # Create URL for fal.ai
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        
        # Process photo through fal.ai
        result = await process_with_fal(file_url)
        print(result)
        
        if result and 'images' in result and len(result['images']) > 0 and 'url' in result['images'][0]:
            # Add watermark
            watermarked_image = await add_watermark(result['images'][0]['url'])
            
            if watermarked_image:
                # Send result with watermark
                await bot.send_photo(
                    chat_id=message.chat.id,
                    photo=watermarked_image,
                    caption="🎭 Ваш Войяк готов!",
                    message_effect_id=FIRE_EFFECT,
                )
            else:
                # If watermark failed, send original
                await bot.send_photo(
                    chat_id=message.chat.id,
                    photo=result['images'][0]['url'],
                    caption="🎭 Ваш Войяк готов!",
                    message_effect_id=FIRE_EFFECT,
                )
        else:
            lang = get_user_lang(message.from_user)
            texts = get_texts(lang)
            await message.answer(texts['error_processing'])
            
    except Exception as e:
        logger.error(f"Error processing photo: {e}")
        lang = get_user_lang(message.from_user)
        texts = get_texts(lang)
        await message.answer(texts['error_processing'])

async def process_with_fal(image_url: str):
    try:
        def on_queue_update(update):
            if isinstance(update, fal_client.InProgress):
                for log in update.logs:
                    logger.info(f"FAL processing: {log['message']}")
        
        result = fal_client.subscribe(
            "fal-ai/image-editing/wojak-style",
            arguments={
                "image_url": image_url
            },
            with_logs=True,
            on_queue_update=on_queue_update,
        )
        
        return result
        
    except Exception as e:
        logger.error(f"fal.ai error: {e}")
        return None

async def add_watermark(image_url: str) -> Optional[BufferedInputFile]:
    try:
        # Download image
        response = requests.get(image_url)
        response.raise_for_status()
        
        # Open image
        image = Image.open(io.BytesIO(response.content))
        
        # Create drawing object
        draw = ImageDraw.Draw(image)
        
        # Watermark parameters
        watermark_text = "@wojakobot"
        
        # Font size depends on image size (make it prominent but not overwhelming)
        font_size = max(80, min(image.width, image.height) // 8)
        
        # Try to load system font or use built-in
        try:
            # Try to use system fonts
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", font_size)
            except:
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)
                except:
                    try:
                        font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", font_size)
                    except:
                        # If nothing found, use built-in font
                        font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()
        
        # Get text dimensions
        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Watermark position (bottom-right corner with margin)
        margin = 30
        x = image.width - text_width - margin
        y = image.height - text_height - margin
        
        # Convert to RGBA if needed
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        
        # Add text with black stroke
        draw = ImageDraw.Draw(image)
        
        # Increase stroke width for better visibility
        stroke_width = 3
        
        # Draw black stroke
        for adj_x in range(-stroke_width, stroke_width + 1):
            for adj_y in range(-stroke_width, stroke_width + 1):
                if adj_x != 0 or adj_y != 0:
                    draw.text((x + adj_x, y + adj_y), watermark_text, font=font, fill=(0, 0, 0, 255))
        
        # Main white text
        draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255, 255))
        
        # Convert back to RGB if needed
        if image.mode == 'RGBA':
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image = background
        
        # Save to buffer
        output_buffer = io.BytesIO()
        image.save(output_buffer, format='JPEG', quality=95)
        output_buffer.seek(0)
        
        # Return BufferedInputFile for aiogram
        return BufferedInputFile(
            output_buffer.read(),
            filename="wojak_with_watermark.jpg"
        )
        
    except Exception as e:
        logger.error(f"Error adding watermark: {e}")
        return None

@dp.message()
async def handle_other_messages(message: Message):
    lang = get_user_lang(message.from_user)
    texts = get_texts(lang)
    await message.answer(texts['error_no_photo'])

async def main():
    logger.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
