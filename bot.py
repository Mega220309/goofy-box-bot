import asyncio, json, os, time
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5020382411"))
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://goofy-culture.vercel.app")

bot = Bot(TOKEN)
dp = Dispatcher()
DB_FILE = "products.json"

if not os.path.exists(DB_FILE):
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump([], f)

def get_products():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return []
def save_products(d):
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=2)

class Add(StatesGroup):
    photo=State(); name=State(); brand=State(); price=State(); size=State(); tag=State()

@dp.message(Command("start"))
async def start(m: Message):
    kb=InlineKeyboardBuilder(); kb.button(text="📦 ОТКРЫТЬ КОРОБКУ", web_app=WebAppInfo(url=WEBAPP_URL))
    await m.answer("Goofy Culture BOX открыт.\nТОЛЬКО ОРИГИНАЛ\n\nАдмин: /add /list /sold 1 /del 1", reply_markup=kb.as_markup())

@dp.message(Command("add"))
async def add_start(m: Message, state: FSMContext):
    if m.from_user.id!=ADMIN_ID: return
    await state.set_state(Add.photo); await m.answer("📦 Кидай фото шмотки")

@dp.message(Add.photo, F.photo)
async def add_photo(m: Message, state: FSMContext):
    await state.update_data(photo=m.photo[-1].file_id); await state.set_state(Add.name); await m.answer("Название?")

@dp.message(Add.name)
async def add_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text); await state.set_state(Add.brand); await m.answer("Бренд?")

@dp.message(Add.brand)
async def add_brand(m: Message, state: FSMContext):
    await state.update_data(brand=m.text); await state.set_state(Add.price); await m.answer("Цена? Цифры")

@dp.message(Add.price)
async def add_price(m: Message, state: FSMContext):
    try: p=int(m.text)
    except: return await m.answer("Только цифры")
    await state.update_data(price=p); await state.set_state(Add.size); await m.answer("Размер? M/L/S/ONE")

@dp.message(Add.size)
async def add_size(m: Message, state: FSMContext):
    await state.update_data(size=m.text.upper()); await state.set_state(Add.tag); await m.answer("Тэг? FRAGILE/USED/1 ШТ или -")

@dp.message(Add.tag)
async def add_tag(m: Message, state: FSMContext):
    d=await state.get_data(); ps=get_products()
    ps.insert(0,{"id":int(time.time()*1000),"name":d["name"],"brand":d["brand"],"price":d["price"],"size":d["size"],"tag":"" if m.text=="-" else m.text,"img":d["photo"],"sold":False,"sold_at":None})
    save_products(ps); await state.clear(); await m.answer(f"✅ Добавил! Всего: {len(ps)} шт.")

@dp.message(Command("sold"))
async def sold_item(m: Message):
    if m.from_user.id!=ADMIN_ID: return
    try:
        idx=int(m.text.split()[1])-1; ps=get_products(); ps[idx]["sold"]=True; ps[idx]["sold_at"]=time.time(); ps[idx]["tag"]="СП*ЗДИЛИ"; save_products(ps)
        await m.answer(f"✅ {ps[idx]['name']} -> СП*ЗДИЛИ на 24ч")
    except: await m.answer("/sold 1")

@dp.message(Command("del"))
async def del_item(m: Message):
    if m.from_user.id!=ADMIN_ID: return
    try:
        if "all" in m.text: save_products([]); return await m.answer("🧹  Очищено")
        idx=int(m.text.split()[1])-1; ps=get_products(); r=ps.pop(idx); save_products(ps); await m.answer(f"🗑️  Удалил {r['name']}")
    except: await m.answer("/del 1 или /del all")

@dp.message(Command("list"))
async def list_prod(m: Message):
    if m.from_user.id!=ADMIN_ID: return
    ps=get_products()
    if not ps: return await m.answer("Пусто")
    txt="\n".join([f"{i+1}. {'❌ СП*ЗДИЛИ' if p.get('sold') else '✅'} {p['brand']} {p['name']} - {p['price']}₽" for i,p in enumerate(ps)])
    await m.answer(f"В коробке {len(ps)}:\n{txt}")

async def api_products(r): return web.json_response(get_products())
async def api_file(r):
    try:
        f=await bot.get_file(r.match_info['file_id']); url=f"https://api.telegram.org/file/bot{TOKEN}/{f.file_path}"; return web.json_response({"url":url})
    except: return web.json_response({"url":""})

async def auto_cleaner():
    while True:
        await asyncio.sleep(600)
        ps=get_products(); now=time.time(); new=[]; rem=0
        for p in ps:
            if p.get("sold") and p.get("sold_at") and now-p["sold_at"]>86400: rem+=1; continue
            new.append(p)
        if rem>0: save_products(new); await bot.send_message(ADMIN_ID, f"🧹  Авто-удалил {rem} шт. (прошло 24ч)")

app=web.Application(); app.router.add_get('/api/products', api_products); app.router.add_get('/api/file/{file_id}', api_file)

async def main():
    asyncio.create_task(auto_cleaner()); runner=web.AppRunner(app); await runner.setup(); site=web.TCPSite(runner,'0.0.0.0',8080); await site.start(); await dp.start_polling(bot)
if __name__=="__main__": asyncio.run(main())
