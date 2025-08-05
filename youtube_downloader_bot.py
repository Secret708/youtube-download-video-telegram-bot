from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from dotenv import load_dotenv
import os
import asyncio
import re
import yt_dlp
import subprocess
import time

load_dotenv('tokens/TOKEN_BOT.env') # загрузка токена
TOKEN = os.getenv('TOKEN')

bot = Bot(token=TOKEN)
dp = Dispatcher()

mini_db = [] # список словарей вместо бд

inline_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text='Скачать только аудио', callback_data='audio')],
                     [InlineKeyboardButton(text='Скачать видео без звука', callback_data='video')],
                     [InlineKeyboardButton(text='Скачать видео со звуком', callback_data='video_with_audio')]]
) #

def is_youtube_link(text): # проверяет ссылку
    youtube_link_signs = (
        r'(https?://)?(www\.)?'
        r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
        r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
    )
    is_link = re.search(youtube_link_signs, text)
    return is_link is not None

async def link(user_id): # находит человека в мини бд
    for user in mini_db:
        if user['id'] == user_id:
            return user

def download_file(url, params): # загружаем файл и возвращаем путь к нему
    with yt_dlp.YoutubeDL(params) as l:
        print('Download file')
        info_file = l.extract_info(url, download=True)
        path = l.prepare_filename(info_file)
        return path

@dp.message(lambda message: message.text == '/start') # приветствие бота
async def start(message: Message):
    await message.answer('Привет, я бот для того чтобы скачивать видео из YouTube по его url. Напиши мне ссылку и я скачаю видео')

@dp.message(lambda message: 'youtube.com' in message.text or 'youtu.be' in message.text) # проверка на ссылку
async def download(message: Message):
    if is_youtube_link(message.text) == True:
        dict_db = {'id': message.from_user.id, 'link': message.text, 'params': None}
        mini_db.append(dict_db)
        await message.answer('Выбери тип загрузки и нажми на кнопку', reply_markup=inline_keyboard)
    else:
        await message.answer('Это не ссылка на YouTube видео')

@dp.callback_query() # загрузка и отправка аудио и видео
async def callback_buttons(callback: CallbackQuery):
    await callback.answer()
    if callback.data == 'audio':
        params_audio = {
            'format': 'bestaudio/best',
            'outtmpl': 'downloads/audio/%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192'
        }]}
        params = await link(callback.from_user.id)
        params['params'] = params_audio
    elif callback.data == 'video':
        params_video = {
            'format': 'bestvideo',
            'outtmpl': 'downloads/video_only/%(title)s.%(ext)s',
        }
        params = await link(callback.from_user.id)
        params['params'] = params_video
    elif callback.data == 'video_with_audio':
        params_vwa = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'merge_output_format': 'mp4'
        }
        params = await link(callback.from_user.id)
        params['params'] = params_vwa
    else:
        pass
    try:
        print('Get URL')
        url = await link(callback.from_user.id)
        url = url['link']
        if not url:
            await callback.answer('Не удалось взять ссылку')
        await callback.message.edit_text('Началась загрузка файла....')
    except Exception as e:
        print(f'Ошибка: {e}')
    try:
        flow = asyncio.get_event_loop()
        params = await link(callback.from_user.id)
        url = params['link']
        params = params['params']
        times = int(time.time() * 1000)
        file_path = await flow.run_in_executor(None, download_file, url, params)
        if callback.data == 'audio':
            final_path = file_path.rsplit('.', 1)[0] + '.mp3'
            compressed_video = f'compressed_audio_{times}.mp3'
            subprocess.run(['ffmpeg', '-i', final_path, '-vn', '-q:a', '2', '-y', compressed_video])
            file = FSInputFile(compressed_video)
            await callback.message.edit_text('Загрузка завершена..')
            await callback.message.answer_document(document=file, caption='Вот ваше аудио')
        elif callback.data == 'video':
            final_path = file_path
            compressed_video = f'compressed_video_{times}.mp4'
            subprocess.run(['ffmpeg', '-i', final_path, '-an', '-vf', 'scale=640:-2', '-crf', '28', '-preset', 'fast', compressed_video])
            file = FSInputFile(compressed_video)
            await callback.message.edit_text('Загрузка завершена..')
            await callback.message.answer_document(document=file, caption='Вот ваше видео без звука')
        elif callback.data == 'video_with_audio':
            final_path = file_path.rsplit('.', 1)[0] + '.mp4'
            compressed_video = f'compressed_video_with_audio_{times}.mp4'
            subprocess.run(['ffmpeg', '-i', final_path, '-vf', 'scale=640:-2', '-crf', '28', '-preset', 'fast', compressed_video])
            file = FSInputFile(compressed_video)
            await callback.message.edit_text('Загрузка завершена..')
            await callback.message.answer_document(document=file, caption='Вот ваше видео со звуком')
    except Exception as e:
        print(f'Ошибка: {e}')
        print('Progress Stop')
        await callback.message.answer('Ваше видео слишком велико для отправки ботом (ограничения 50 МБ)')

async def main(): # главный цикл бота
    while True:
        try:
            print('Запуск бота')
            await dp.start_polling(bot)
        except Exception as e:
            print(f'Ошибка {e}')
            print('Перезапуск бота')
            await asyncio.sleep(3)

if __name__ == '__main__':
    asyncio.run(main())