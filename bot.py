import asyncio, json, os, time, pathlib
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiohttp import web

TOKEN = os.getenv("TOKEN") or os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Нет TOKEN в Variables")

ADMIN_ID = int(os.getenv("ADMIN_ID", "5020382411"))
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://goofy-box-bot-production.up.railway.app/")
SOLD_HOURS = 10

bot = Bot(TOKEN)
dp = Dispatcher()

# Фикс для Railway - храним в /app и в /tmp одновременно
DB_FILE = pathlib.Path(__file__).parent / "products.json"
if not DB_FILE.exists():
    DB_FILE.write_text("[]", encoding="utf-8")

def get_products():
    try:
        return json.loads(DB_FILE.read_text(encoding="utf-8"))
    except:
        return []

def save_products(d):
    DB_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

def get_status(p):
    if not p.get("sold"):
        return "active"
    sold_at = p.get("sold_at", 0) or 0
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
    if m.from_user.id!= ADMIN_ID:
        return
    await state.set_state(Add.photo)
    await m.answer("📦 Кидай фото товара")

@dp.message(Add.photo, F.photo)
async def add_photo(m: Message, state: FSMContext):
    await state.update_data(photo=m.photo[-1].file_id)
    await state.set_state(Add.name)
    await m.answer("Название?")

@dp.message(Add.name)
async def add_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text.strip())
    await state.set_state(Add.brand)
    await m.answer("Бренд?")

@dp.message(Add.brand)
async def add_brand(m: Message, state: FSMContext):
    await state.update_data(brand=m.text.strip())
    await state.set_state(Add.price)
    await m.answer("Цена? (только цифры)")

@dp.message(Add.price)
async def add_price(m: Message, state: FSMContext):
    try:
        p = int(m.text.strip())
    except:
        return await m.answer("Только цифры, например 7999")
    await state.update_data(price=p)
    await state.set_state(Add.size)
    await m.answer("Размер? (например L или 2)")

@dp.message(Add.size)
async def add_size(m: Message, state: FSMContext):
    await state.update_data(size=m.text.upper().strip())
    await state.set_state(Add.tag)
    await m.answer("Тэг? Напиши FRAGILE / 1 ШТ или - если без тэга")

@dp.message(Add.tag)
async def add_tag(m: Message, state: FSMContext):
    d = await state.get_data()
    ps = get_products()
    tag = "" if m.text.strip() == "-" else m.text.strip()
    new_id = int(time.time() * 1000)
    new_item = {
        "id": new_id,
        "name": d["name"],
        "brand": d["brand"],
        "price": d["price"],
        "size": d["size"],
        "sizes": [d["size"]],
        "tag": tag,
        "img": d["photo"],
        "images": [d["photo"]],
        "description": f"{d['brand']} {d['name']} • {d['size']}",
        "sold": False,
        "sold_at": 0
    }
    ps.insert(0, new_item)
    save_products(ps)
    await state.clear()
    await m.answer(f"✅ Добавил! ID:{new_id}\nВсего: {len(ps)}\nОткрой сайт - товар должен появиться сразу.")

@dp.message(Command("sold"))
async def sold_list(m: Message):
    if m.from_user.id!= ADMIN_ID:
        return
    ps = get_products()
    sold = [p for p in ps if p.get("sold") and get_status(p)!= "expired"]
    if not sold:
        await m.answer("Нет проданных товаров")
        return
    for p in sold:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ ОТМЕНИТЬ ПРОДАНО", callback_data=f"unsold_{p['id']}")]])
        left_h = SOLD_HOURS - int((time.time() - p.get("sold_at", 0)) // 3600)
        await m.answer(f"🔴 {p.get('brand')} {p.get('name')} {p.get('price')}₽\nУдалится через {left_h}ч\nID:{p['id']}", reply_markup=kb)

@dp.message(Command("list"))
async def list_all(m: Message):
    if m.from_user.id!= ADMIN_ID:
        return
    ps = get_products()
    if not ps:
        await m.answer("Каталог пуст. Добавь через /add")
        return
    for p in ps[:15]:
        status = "🔴 ПРОДАНО" if p.get("sold") else "🟢 В ПРОДАЖЕ"
        txt = f"{status}\n{p.get('brand')} {p.get('name')} {p.get('price')}₽\nID:{p['id']}"
        row = []
        if p.get("sold"):
            row.append(InlineKeyboardButton(text="↩️ Отменить", callback_data=f"unsold_{p['id']}"))
        else:
            row.append(InlineKeyboardButton(text="🔴 Продано", callback_data=f"sold_{p['id']}"))
        row.append(InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"del_{p['id']}"))
        kb = InlineKeyboardMarkup(inline_keyboard=[row])
        await m.answer(txt, reply_markup=kb)

@dp.callback_query(F.data.startswith("unsold_"))
async def cb_unsold(c):
    pid = int(c.data.split("_")[1])
    ps = get_products()
    for p in ps:
        if p['id'] == pid:
            p['sold'] = False
            p['sold_at'] = 0
            save_products(ps)
            await c.message.edit_text(f"✅ Вернул в продажу: {p.get('brand')} {p.get('name')}")
            break
    await c.answer()

@dp.callback_query(F.data.startswith("sold_"))
async def cb_sold(c):
    pid = int(c.data.split("_")[1])
    ps = get_products()
    for p in ps:
        if p['id'] == pid:
            p['sold'] = True
            p['sold_at'] = time.time()
            save_products(ps)
            await c.message.edit_text(f"🔥 Отметил продано: {p.get('brand')} {p.get('name')}")
            try:
                await bot.send_message(ADMIN_ID, f"🔥 ПРОДАНО: {p['brand']} {p['name']} {p['price']}₽\nЧерез 10ч удалю и отчитаюсь.")
            except:
                pass
            break
    await c.answer()

@dp.callback_query(F.data.startswith("del_"))
async def cb_del(c):
    pid = int(c.data.split("_")[1])
    ps = [p for p in get_products() if p['id']!= pid]
    save_products(ps)
    await c.message.edit_text(f"🗑️ Удалил ID {pid}")
    await c.answer()

# API ДЛЯ САЙТА
async def api_products(r):
    ps = get_products()
    now = time.time()
    alive_for_file = []
    alive_for_api = []
    need_save = False

    for p in ps:
        if get_status(p) == "expired":
            need_save = True
            try:
                await bot.send_message(ADMIN_ID, f"🗑️ <b>УШЛО ЧЕРЕЗ 10Ч</b>\n{p.get('brand')} {p.get('name')} {p.get('price')}₽ удален из каталога.", parse_mode="HTML")
            except:
                pass
        else:
            alive_for_file.append(p)
            cp = p.copy()
            cp["status"] = get_status(p)
            alive_for_api.append(cp)

    if need_save:
        save_products(alive_for_file)

    return web.json_response(alive_for_api)

async def api_file(r):
    file_id = r.match_info['file_id']
    f = await bot.get_file(file_id)
    url = f"https://api.telegram.org/file/bot{TOKEN}/{f.file_path}"
    return web.json_response({"url": url})

async def api_toggle(r):
    pid = int(r.match_info['pid'])
    ps = get_products()
    for p in ps:
        if p['id'] == pid:
            if p.get("sold"):
                p["sold"] = False
                p["sold_at"] = 0
            else:
                p["sold"] = True
                p["sold_at"] = time.time()
            save_products(ps)
            return web.json_response(p)
    return web.json_response({"error": "not found"}, status=404)

async def api_delete(r):
    pid = int(r.match_info['pid'])
    ps = [p for p in get_products() if p['id']!= pid]
    save_products(ps)
    return web.json_response({"ok": True})

app = web.Application()
app.router.add_get('/api/products', api_products)
app.router.add_get('/api/file/{file_id}', api_file)
app.router.add_post('/api/admin/toggle-sold/{pid}', api_toggle)
app.router.add_delete('/api/admin/delete/{pid}', api_delete)
app.router.add_get('/', lambda r: web.FileResponse(pathlib.Path(__file__).parent / 'static' / 'index.html'))
app.router.add_static('/static/', path=pathlib.Path(__file__).parent / 'static')

async def cleaner():
    while True:
        await asyncio.sleep(300)
        ps = get_products()
        expired = [p for p in ps if get_status(p) == "expired"]
        if expired:
            alive = [p for p in ps if get_status(p)!= "expired"]
            save_products(alive)
            for p in expired:
                try:
                    await bot.send_message(ADMIN_ID, f"🗑️ Авто-удаление: {p.get('brand')} {p.get('name')} {p.get('price')}₽")
                except:
                    pass

async def main():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", 8080)))
    await site.start()
    asyncio.create_task(cleaner())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
