import asyncio, json, os, time, pathlib
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiohttp import web

TOKEN = os.getenv("TOKEN") or os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID","5020382411"))
WEBAPP_URL = os.getenv("WEBAPP_URL","https://goofy-box-bot-production.up.railway.app/")
SOLD_HOURS = 10
DB_PATH = os.getenv("DB_PATH","/data/products.json" if pathlib.Path("/data").exists() else "products.json")

bot = Bot(TOKEN)
dp = Dispatcher()
DB = pathlib.Path(DB_PATH)
DB.parent.mkdir(parents=True, exist_ok=True)
if not DB.exists(): DB.write_text("[]", encoding="utf-8")

def load():
    try: return json.loads(DB.read_text(encoding="utf-8"))
    except: return []
def save(d):
    DB.parent.mkdir(parents=True, exist_ok=True)
    DB.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
def status(p):
    if not p.get("sold"): return "active"
    return "expired" if time.time()-(p.get("sold_at")or 0) > SOLD_HOURS*3600 else "sold_recent"

class Add(StatesGroup):
    photos=State(); name=State(); brand=State(); price=State(); size=State(); desc=State(); tag=State()

@dp.message(Command("start"))
async def start(m:Message):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb=InlineKeyboardBuilder(); kb.button(text="📦 ОТКРЫТЬ КОРОБКУ", web_app=WebAppInfo(url=WEBAPP_URL))
    await m.answer("Goofy Culture BOX", reply_markup=kb.as_markup())

@dp.message(Command("add"))
async def a0(m:Message, state:FSMContext):
    if m.from_user.id!=ADMIN_ID: return
    await state.set_state(Add.photos); await state.update_data(photos=[])
    await m.answer("📸 Кидай фото (до 10). Напиши ГОТОВО когда хватит")

@dp.message(Add.photos, F.photo)
async def a_photo(m:Message, state:FSMContext):
    d=await state.get_data(); ph=d.get("photos",[]); ph.append(m.photo[-1].file_id)
    await state.update_data(photos=ph)
    await m.answer(f"✅ {len(ph)} фото. Еще? → ГОТОВО")

@dp.message(Add.photos)
async def a_photos_text(m:Message, state:FSMContext):
    if m.text.lower() not in ["готово","готов","done","ok","все"]: return
    d=await state.get_data()
    if not d.get("photos"): return await m.answer("Кинь фото")
    await state.set_state(Add.name); await m.answer("Название?")
@dp.message(Add.name)
async def a2(m:Message, state:FSMContext):
    await state.update_data(name=m.text.strip()); await state.set_state(Add.brand); await m.answer("Бренд?")
@dp.message(Add.brand)
async def a3(m:Message, state:FSMContext):
    await state.update_data(brand=m.text.strip()); await state.set_state(Add.price); await m.answer("Цена? цифры")
@dp.message(Add.price)
async def a4(m:Message, state:FSMContext):
    try: p=int(''.join(filter(str.isdigit, m.text)))
    except: return await m.answer("Цифры")
    await state.update_data(price=p); await state.set_state(Add.size); await m.answer("Размер?")
@dp.message(Add.size)
async def a5(m:Message, state:FSMContext):
    await state.update_data(size=m.text.strip().upper()); await state.set_state(Add.desc); await m.answer("Описание? - если без")
@dp.message(Add.desc)
async def a6(m:Message, state:FSMContext):
    txt="" if m.text.strip()=="-" else m.text.strip()
    await state.update_data(desc=txt); await state.set_state(Add.tag); await m.answer("Тэг? FRAGILE / -")
@dp.message(Add.tag)
async def a7(m:Message, state:FSMContext):
    d=await state.get_data(); ps=load()
    tag="" if m.text.strip()=="-" else m.text.strip()
    ps.insert(0, {"id":int(time.time()*1000),"name":d["name"],"brand":d["brand"],"price":d["price"],"size":d["size"],"sizes":[d["size"]],"tag":tag,"description":d.get("desc",""),"img":d["photos"][0],"images":d["photos"],"sold":False,"sold_at":0})
    save(ps); await state.clear()
    await m.answer(f"✅ Добавил! Сейчас в базе: {len(ps)}")

@dp.message(Command("list"))
async def lst(m:Message):
    if m.from_user.id!=ADMIN_ID: return
    for p in load()[:10]:
        kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔴 Продано" if not p.get("sold") else "↩️ Вернуть", callback_data=f"{'sold' if not p.get('sold') else 'unsold'}_{p['id']}"), InlineKeyboardButton(text="🗑️", callback_data=f"del_{p['id']}")]])
        await m.answer(f"{p['brand']} {p['name']} {p['price']}₽", reply_markup=kb)
@dp.callback_query(F.data.startswith("unsold_"))
async def cu(c):
    pid=int(c.data.split("_")[1]); ps=load()
    for p in ps:
        if p['id']==pid: p['sold']=False; p['sold_at']=0
    save(ps); await c.message.edit_text("✅ Вернул"); await c.answer()
@dp.callback_query(F.data.startswith("sold_"))
async def cs(c):
    pid=int(c.data.split("_")[1]); ps=load()
    for p in ps:
        if p['id']==pid: p['sold']=True; p['sold_at']=time.time()
    save(ps); await c.message.edit_text("🔥 Продано на 10ч"); await c.answer()
@dp.callback_query(F.data.startswith("del_"))
async def cd(c):
    pid=int(c.data.split("_")[1]); save([p for p in load() if p['id']!=pid]); await c.message.edit_text("🗑️ Удалил"); await c.answer()

async def api_products(r):
    ps=load(); alive=[]; keep=[]
    for p in ps:
        s=status(p)
        if s!="expired": keep.append(p); cp=p.copy(); cp["status"]=s; alive.append(cp)
    if len(keep)!=len(ps): save(keep)
    return web.json_response(alive)
async def api_file(r):
    f=await bot.get_file(r.match_info['file_id']); return web.json_response({"url":f"https://api.telegram.org/file/bot{TOKEN}/{f.file_path}"})

app=web.Application()
app.router.add_get('/api/products', api_products)
app.router.add_get('/api/file/{file_id}', api_file)
app.router.add_get('/', lambda r: web.FileResponse(pathlib.Path(__file__).parent/'static'/'index.html'))
app.router.add_static('/static/', path=pathlib.Path(__file__).parent/'static')

async def main():
    runner=web.AppRunner(app); await runner.setup(); await web.TCPSite(runner,'0.0.0.0',int(os.getenv("PORT",8080))).start()
    await dp.start_polling(bot)
if __name__=="__main__": asyncio.run(main())
