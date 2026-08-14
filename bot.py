import asyncio, json, os, time, pathlib
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiohttp import web

TOKEN = os.getenv("TOKEN") or os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5020382411"))
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://goofy-box-bot-production.up.railway.app/")
SOLD_HOURS = 10

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

def get_status(p):
    if not p.get("sold"):
        return "active"
    sold_at = p.get("sold_at", 0)
    if time.time() - sold_at > SOLD_HOURS * 3600:
        return "expired"
    return "sold_recent"

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
    if m.from_user.id!= ADMIN_ID: return
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
    ps.insert(0, {
        "id": int(time.time()*1000),
        "name": d["name"],
        "brand": d["brand"],
        "price": d["price"],
        "size": d["size"],
        "tag": tag,
        "img": d["photo"],
        "images": [d["photo"]], # для нового index.html
        "sold": False,
        "sold_at": 0
    })
    save_products(ps)
    await state.clear()
    await m.answer(f"✅ Добавил! Всего: {len(ps)}")

# КОМАНДЫ ДЛЯ ОТМЕНЫ
@dp.message(Command("sold"))
async def sold_list(m: Message):
    if m.from_user.id!= ADMIN_ID: return
    ps = get_products()
    sold = [p for p in ps if p.get("sold") and get_status(p)!= "expired"]
    if not sold:
        await m.answer("Нет проданных")
        return
    for p in sold:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ ОТМЕНИТЬ ПРОДАНО", callback_data=f"unsold_{p['id']}")]])
        left = int(SOLD_HOURS - (time.time() - p.get("sold_at",0)) // 3600)
        await m.answer(f"🔴 {p.get('brand')} {p.get('name')} {p.get('price')}₽\nУдалится через {left}ч\nID:{p['id']}", reply_markup=kb)

@dp.message(Command("list"))
async def list_all(m: Message):
    if m.from_user.id!= ADMIN_ID: return
    ps = get_products()
    for p in ps[:15]:
        text = f"{'🔴' if p.get('sold') else '🟢'} {p.get('brand')} {p.get('name')} {p.get('price')}₽ ID:{p['id']}"
        btns = []
        if p.get("sold"):
            btns.append(InlineKeyboardButton(text="↩️ Отменить", callback_data=f"unsold_{p['id']}"))
        else:
            btns.append(InlineKeyboardButton(text="🔴 Продано", callback_data=f"sold_{p['id']}"))
        btns.append(InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"del_{p['id']}"))
        kb = InlineKeyboardMarkup(inline_keyboard=[btns])
        await m.answer(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("unsold_"))
async def cb_unsold(c):
    pid = int(c.data.split("_")[1])
    ps = get_products()
    for p in ps:
        if p['id'] == pid:
            p['sold'] = False; p['sold_at'] = 0
            save_products(ps)
            await c.message.edit_text(f"✅ Вернул в продажу: {p['brand']} {p['name']}")
            await bot.send_message(c.from_user.id, "Теперь снова в каталоге.")
            break
    await c.answer()

@dp.callback_query(F.data.startswith("sold_"))
async def cb_sold(c):
    pid = int(c.data.split("_")[1])
    ps = get_products()
    for p in ps:
        if p['id'] == pid:
            p['sold'] = True; p['sold_at'] = time.time()
            save_products(ps)
            await c.message.edit_text(f"🔥 Продано: {p['brand']} {p['name']}")
            await bot.send_message(ADMIN_ID, f"🔥 Отметил как ПРОДАНО: {p['brand']} {p['name']} {p['price']}₽\nЧерез 10ч удалю и отчитаюсь.")
            break
    await c.answer()

@dp.callback_query(F.data.startswith("del_"))
async def cb_del(c):
    pid = int(c.data.split("_")[1])
    ps = [p for p in get_products() if p['id']!= pid]
    save_products(ps)
    await c.message.edit_text(f"🗑️ Удалил ID {pid}")
    await c.answer()

# API
async def api_products(r):
    ps = get_products()
    # чистим просроченные тут же
    now = time.time()
    alive = []
    changed = False
    for p in ps:
        if get_status(p) == "expired":
            changed = True
            # отчет в тг
            try:
                await bot.send_message(ADMIN_ID, f"🗑️ <b>УШЛО ЧЕРЕЗ 10Ч</b>\nБренд: {p.get('brand')}\nТовар: {p.get('name')}\nЦена: {p.get('price')}₽", parse_mode="HTML")
            except: pass
        else:
            cp = p.copy()
            cp["status"] = get_status(p)
            alive.append(cp)
    if changed:
        # сохраняем только живые + активные
        still = [p for p in ps if get_status(p)!= "expired"]
        save_products(still)
    return web.json_response(alive)

async def api_file(r):
    f = await bot.get_file(r.match_info['file_id'])
    url = f"https://api.telegram.org/file/bot{TOKEN}/{f.file_path}"
    return web.json_response({"url": url})

async def api_toggle_sold(r):
    pid = int(r.match_info['pid'])
    ps = get_products()
    for p in ps:
        if p['id'] == pid:
            if p.get('sold'):
                p['sold'] = False; p['sold_at'] = 0
                save_products(ps)
                return web.json_response(p)
            else:
                p['sold'] = True; p['sold_at'] = time.time()
                save_products(ps)
                try:
                    await bot.send_message(ADMIN_ID, f"🔥 Продано через сайт: {p['brand']} {p['name']} {p['price']}₽\nЧерез 10ч удалю.")
                except: pass
                return web.json_response(p)
    return web.json_response({"error":"not found"}, status=404)

async def api_delete(r):
    pid = int(r.match_info['pid'])
    ps = [p for p in get_products() if p['id']!= pid]
    save_products(ps)
    return web.json_response({"ok": True})

app = web.Application()
app.router.add_get('/api/products', api_products)
app.router.add_get('/api/file/{file_id}', api_file)
app.router.add_post('/api/admin/toggle-sold/{pid}', api_toggle_sold)
app.router.add_delete('/api/admin/delete/{pid}', api_delete)

async def index(r):
    return web.FileResponse(pathlib.Path(__file__).parent / 'static' / 'index.html')

app.router.add_get('/', index)
app.router.add_static('/static/', path=pathlib.Path(__file__).parent / 'static')

# Фоновая проверка каждые 5 минут на случай если никто не заходит в каталог
async def auto_cleaner():
    while True:
        await asyncio.sleep(300)
        ps = get_products()
        expired = [p for p in ps if get_status(p) == "expired"]
        if expired:
            alive = [p for p in ps if get_status(p)!= "expired"]
            save_products(alive)
            for p in expired:
                try:
                    await bot.send_message(ADMIN_ID, f"🗑️ <b>АВТО-УДАЛЕНИЕ 10Ч</b>\n{p.get('brand')} {p.get('name')} {p.get('price')}₽ ушел из каталога.", parse_mode="HTML")
                except: pass

async def main():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 8080)))
    await site.start()
    asyncio.create_task(auto_cleaner())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
