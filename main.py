import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, FSInputFile
from docx2pdf import convert
from PIL import Image

from config import BOT_TOKEN, MAX_FILE_SIZE
from texts import TRANSLATIONS

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_languages = {}

def get_language_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz"),
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")
        ]
    ])

def get_main_menu(lang='uz'):
    t = TRANSLATIONS[lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['btn_converter'], callback_data="menu_converter")],
        [InlineKeyboardButton(text=t['btn_tools'], callback_data="menu_tools")],
        [InlineKeyboardButton(text=t['btn_calc'], callback_data="menu_calc")],
        [InlineKeyboardButton(text="🌐 Tilni o'zgartirish / Change language", callback_data="change_lang")]
    ])

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Salom! Iltimos, tilni tanlang:\n"
        "Пожалуйста, выберите язык:\n"
        "Please choose your language:",
        reply_markup=get_language_keyboard()
    )

@dp.callback_query(F.data.startswith("lang_"))
async def set_language(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    user_languages[callback.from_user.id] = lang
    
    t = TRANSLATIONS[lang]
    await callback.message.edit_text(
        t['select_lang'],
        reply_markup=get_main_menu(lang)
    )
    await callback.answer()

@dp.callback_query(F.data == "change_lang")
async def change_language(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Tilni tanlang / Выберите язык / Choose language:",
        reply_markup=get_language_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("menu_"))
async def menu_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang = user_languages.get(user_id, 'uz')
    t = TRANSLATIONS[lang]
    
    action = callback.data.split("_")[1]
    
    if action == "converter":
        await callback.message.edit_text(
            "📄 **Konvertor bo'limi:**\n\nMenga istalgan **Word (.docx)**, **Excel (.xlsx)** yoki **Rasm (.jpg/.png)** faylini yuboring, men uni darhol PDF formatiga o'tkazib beraman!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t['back'], callback_data="back_to_menu")]
            ])
        )
    elif action == "tools":
        await callback.message.edit_text(
            "🛠 **Hujjatlar bilan ishlash bo'limi:**\n\nBu yerda tez kunda hujjatlarni birlashtirish, matnni ajratib olish va tahrirlash funksiyalari ishga tushadi!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t['back'], callback_data="back_to_menu")]
            ])
        )
    elif action == "calc":
        await callback.message.edit_text(
            "🔢 **Kalkulyator bo'limi:**\n\nTez kunda bu yerda buxgalteriya va qulay hisob-kitob vositalari ishlaydi!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t['back'], callback_data="back_to_menu")]
            ])
        )
    await callback.answer()

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang = user_languages.get(user_id, 'uz')
    t = TRANSLATIONS[lang]
    
    await callback.message.edit_text(
        t['select_lang'],
        reply_markup=get_main_menu(lang)
    )
    await callback.answer()

@dp.message(F.document)
async def handle_document(message: Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, 'uz')
    t = TRANSLATIONS[lang]
    
    document = message.document
    file_name = document.file_name

    if document.file_size > MAX_FILE_SIZE:
        await message.answer(t['file_too_large'])
        return

    os.makedirs("downloads", exist_ok=True)
    os.makedirs("converted", exist_ok=True)
    
    input_path = os.path.join("downloads", file_name)
    
    # Word (.docx) to PDF
    if file_name.endswith('.docx'):
        status_msg = await message.answer(t['converting'])
        output_path = os.path.join("converted", file_name.replace('.docx', '.pdf'))
        try:
            file_info = await bot.get_file(document.file_id)
            await bot.download(file_info, destination=input_path)
            convert(input_path, output_path)
            await message.answer_document(FSInputFile(output_path), caption=t['success_convert'])
            await status_msg.delete()
            os.remove(input_path)
            os.remove(output_path)
        except Exception as e:
            logging.error(f"Xatolik: {e}")
            await status_msg.edit_text(t['error_convert'])

    # Excel (.xlsx) haqida xabar
    elif file_name.endswith('.xlsx') or file_name.endswith('.xls'):
        await message.answer("📊 Excel fayllarini PDF ga o'tkazish funksiyasi navbatdagi yangilanishda qo'shiladi!")
    else:
        await message.answer("⚠️ Hozircha faqat **.docx** (Word) fayllarini to'liq PDF ga o'tkaza olaman.")

@dp.message(F.photo)
async def handle_photo(message: Message):
    user_id = message.from_user.id
    lang = user_languages.get(user_id, 'uz')
    t = TRANSLATIONS[lang]
    
    status_msg = await message.answer(t['converting'])
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("converted", exist_ok=True)
    
    photo = message.photo[-1]
    input_path = os.path.join("downloads", f"{photo.file_id}.jpg")
    output_path = os.path.join("converted", f"{photo.file_id}.pdf")
    
    try:
        file_info = await bot.get_file(photo.file_id)
        await bot.download(file_info, destination=input_path)
        
        # Rasmni PDF ga o'tkazish (PIL orqali)
        image = Image.open(input_path)
        rgb_image = image.convert('RGB')
        rgb_image.save(output_path)
        
        await message.answer_document(FSInputFile(output_path), caption=t['success_convert'])
        await status_msg.delete()
        
        os.remove(input_path)
        os.remove(output_path)
    except Exception as e:
        logging.error(f"Rasm konvertatsiya xatoligi: {e}")
        await status_msg.edit_text(t['error_convert'])

async def main():
    print("Bot muvaffaqiyatli ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())