import asyncio, json, os, time, pathlib
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiohttp import web

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5020382411"))
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://goofy-box-bot-production.up.railway.app/")

bot = Bot(TOKEN)
dp = Dispatcher()
DB_FILE = "products.json"

if not os.path.exists(DB_FILE):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)

def get_products():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_products(d):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

class Add(StatesGroup):
    photo = State()
    name = State()
    brand = State()
    price = State()
    size = State()
    tag = State()

@dp.message(Command("start"))
async def start(m: Message):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="📦 ОТКРЫТЬ КОРОБКУ", web_app=WebAppInfo(url=WEBAPP_URL))
    await m.answer("Goofy Culture BOX открыт.\nТОЛЬКО ОРИГИНАЛ", reply_markup=kb.as_markup())

@dp.message(Command("add"))
async def add_start(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    await state.set_state(Add.photo)
    await m.answer("📦 Кидай фото")

@dp.message(Add.photo, F.photo)
async def add_photo(m: Message, state: FSMContext):
    await state.update_data(photo=m.photo[-1].file_id)
    await state.set_state(Add.name)
    await m.answer("Название?")

@dp.message(Add.name)
async def add_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await state.set_state(Add.brand)
    await m.answer("Бренд?")

@dp.message(Add.brand)
async def add_brand(m: Message, state: FSMContext):
    await state.update_data(brand=m.text)
    await state.set_state(Add.price)
    await m.answer("Цена?")

@dp.message(Add.price)
async def add_price(m: Message, state: FSMContext):
    try:
        p = int(m.text)
    except:
        return await m.answer("Только цифры")
    await state.update_data(price=p)
    await state.set_state(Add.size)
    await m.answer("Размер?")

@dp.message(Add.size)
async def add_size(m: Message, state: FSMContext):
    await state.update_data(size=m.text.upper())
    await state.set_state(Add.tag)
    await m.answer("Тэг? FRAGILE/1 ШТ или -")

@dp.message(Add.tag)
async def add_tag(m: Message, state: FSMContext):
    d = await state.get_data()
    ps = get_products()
    tag = "" if m.text == "-" else m.text
    ps.insert(0, {"id": int(time.time()*1000), "name": d["name"], "brand": d["brand"], "price": d["price"], "size": d["size"], "tag": tag, "img": d["photo"], "sold": False})
    save_products(ps)
    await state.clear()
    await m.answer(f"✅ Добавил! Всего: {len(ps)}")

async def api_products(r):
    return web.json_response(get_products())

async def api_file(r):
    f = await bot.get_file(r.match_info['file_id'])
    url = f"https://api.telegram.org/file/bot{TOKEN}/{f.file_path}"
    return web.json_response({"url": url})

app = web.Application()
app.router.add_get('/api/products', api_products)
app.router.add_get('/api/file/{file_id}', api_file)

async def index(r):
    return web.FileResponse(pathlib.Path(__file__).parent / 'static' / 'index.html')

app.router.add_get('/', index)
app.router.add_static('/static/', path=pathlib.Path(__file__).parent / 'static')

async def main():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
