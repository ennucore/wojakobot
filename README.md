# Wojak Bot

Telegram bot for transforming photos into Wojak style, with Russian and English interface support.

## Features

- 🆓 First 3 transformations free
- ⭐ Additional transformations for 45 Telegram Stars
- 🌐 Russian and English localization
- 📊 SQLite database for user tracking
- 🎭 Uses fal.ai for image generation
- 🖼️ Automatic @wojakobot watermark
- 👑 Admin commands for stats and credits

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create `.env` file based on `.env.example`:
```bash
cp .env.example .env
```

4. Fill in environment variables:
- `BOT_TOKEN` - your Telegram bot token (get from @BotFather)
- `FAL_KEY` - API key from fal.ai

## Usage

```bash
python main.py
```

## How it works

1. User sends `/start` command
2. Bot sends a sticker and welcome message
3. User sends a photo
4. If it's one of the first 3 photos - processing is free
5. If not - bot requests payment of 45 Telegram Stars
6. After payment or for free photos - processing through fal.ai
7. Bot sends the finished Wojak-style image with watermark

## Project Structure

- `main.py` - main bot file with handlers
- `database.py` - SQLite database operations
- `requirements.txt` - Python dependencies
- `.env.example` - example environment variables file
