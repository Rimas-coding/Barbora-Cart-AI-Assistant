import os
import sys
import asyncio
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import database
from barbora_service import barbora_service
import nutrition_agent

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BarboraApp")

# Inicializuojame DB
database.init_db()

app = FastAPI(
    title="Barbora Pirkinių Krepšelio & Mitybos AI Valdiklis",
    description="Sistema automatizuotam krepšelio surinkimui Barbora.lt ir asmeniniam mitybos planavimui su AI agentais.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Globali būsena fono užduotims
cart_build_status = {
    "is_running": False,
    "current_step": "Laukiama",
    "progress": 0,
    "logs": [],
    "last_result": None
}

# --- Pydantic modeliai ---
class ClientProfileModel(BaseModel):
    name: str = "Vartotojas"
    gender: str = "vyras"
    age: int = 30
    height: float = 180.0
    weight: float = 80.0
    body_fat_pct: Optional[float] = 18.0
    activity_level: str = "moderate"
    goal: str = "fat_loss"
    training_frequency: int = 3
    training_time: str = "evening"
    dietary_preference: str = "all"
    allergies_restrictions: Optional[str] = ""
    health_notes: Optional[str] = ""

class NutritionGuidelinesModel(BaseModel):
    bmr: int = 1800
    tdee: int = 2500
    target_calories: int = 2000
    meals_per_day: int = 4
    protein_grams: int = 160
    fats_grams: int = 65
    carbs_grams: int = 190
    notes: Optional[str] = ""

class PlanRequestModel(BaseModel):
    days: int = 1  # 1, 3 arba 7

class SavedListCreate(BaseModel):
    name: str
    items_text: str

class SavedDishCreate(BaseModel):
    name: str
    ingredients_text: str
    description: Optional[str] = ""

class CombineSourceItem(BaseModel):
    source_name: str
    items: List[str]

class CombineRequest(BaseModel):
    sources: List[CombineSourceItem]

class ProductCreate(BaseModel):
    name: str
    category: str
    url: str
    price: Optional[float] = 0.0
    unit: Optional[str] = "vnt"
    alias: Optional[str] = None

class ResolveRequest(BaseModel):
    items_text: Optional[str] = None
    items_list: Optional[List[str]] = None

class CartItem(BaseModel):
    name: str
    url: str
    quantity: int = 1
    price: Optional[float] = 0.0

class CartBuildRequest(BaseModel):
    items: List[CartItem]
    source_agent: Optional[str] = "WebUI"

class ScrapeRequest(BaseModel):
    url: str

# --- API Endpoints ---

@app.get("/api/products", summary="Gauti visas prekes")
def get_products(category: Optional[str] = None, search: Optional[str] = None):
    return database.get_all_products(category=category, search=search)

@app.post("/api/products", summary="Pridėti arba atnaujinti prekę")
def create_product(prod: ProductCreate):
    prod_id = database.add_product(
        name=prod.name,
        category=prod.category,
        url=prod.url,
        price=prod.price or 0.0,
        unit=prod.unit or "vnt",
        alias=prod.alias
    )
    return {"success": True, "id": prod_id, "message": "Prekė sėkmingai išsaugota"}

@app.delete("/api/products/{product_id}", summary="Ištrinti prekę")
def delete_product(product_id: int):
    ok = database.delete_product(product_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Prekė nerasta")
    return {"success": True, "message": "Prekė pašalinta"}

@app.get("/api/categories", summary="Gauti prekių kategorijas")
def get_categories():
    return database.get_categories()

@app.post("/api/products/scrape", summary="Nuskaityti prekės duomenis iš Barbora URL")
async def scrape_product(req: ScrapeRequest):
    data = await barbora_service.scrape_product_info(req.url)
    if data.get("success") and data.get("name"):
        data["auto_category"] = database.detect_category(data["name"])
    return data

# --- Standartinių sąrašų ir Patiekalų Endpoints ---

@app.get("/api/lists", summary="Gauti visus išsaugotus pirkinių sąrašus")
def get_saved_lists():
    return database.get_saved_shopping_lists()

@app.post("/api/lists", summary="Išsaugoti standartinį pirkinių sąrašą")
def save_list(item: SavedListCreate):
    list_id = database.save_shopping_list(item.name, item.items_text)
    return {"success": True, "id": list_id, "message": "Pirkinių sąrašas sėkmingai išsaugotas"}

@app.delete("/api/lists/{list_id}", summary="Ištrinti išsaugotą pirkinių sąrašą")
def delete_list(list_id: int):
    ok = database.delete_shopping_list(list_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Sąrašas nerastas")
    return {"success": True, "message": "Sąrašas pašalintas"}

@app.get("/api/dishes", summary="Gauti visus išsaugotus patiekalus")
def get_saved_dishes():
    return database.get_saved_dishes()

@app.post("/api/dishes", summary="Išsaugoti patiekalą su ingredientais")
def save_dish(item: SavedDishCreate):
    dish_id = database.save_dish(item.name, item.ingredients_text, item.description or "")
    return {"success": True, "id": dish_id, "message": "Patiekalas sėkmingai išsaugotas"}

@app.delete("/api/dishes/{dish_id}", summary="Ištrinti išsaugotą patiekalą")
def delete_dish(dish_id: int):
    ok = database.delete_dish(dish_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Patiekalas nerastas")
    return {"success": True, "message": "Patiekalas pašalintas"}

@app.post("/api/cart/combine", summary="Sujungti patiekalų ir standartinius sąrašus su dublikatų patikra")
def combine_sources(req: CombineRequest):
    """
    Priima kelis šaltinius (pvz. 'Šakšuka', 'Tuno salotos', 'Baziniai produktai'),
    sugrupuoja, aptinka besidubliuojančias prekes ir susumuoja kiekius.
    Tiksliai atskiria skirtingas prekes, kad būdvardžiai ('lietuviški', 'švieži' ir pan.)
    nesupainiotų skirtingų produktų (pvz., morkų ir agurkų).
    """
    import re
    # Grupuoti ingredientai
    groups = []
    # Raktas: merge_key -> { 'canonical': name, 'occurrences': [{'source': s, 'raw': item, 'qty': q, 'unit': u}] }
    merged: Dict[str, Dict[str, Any]] = {}

    GENERIC_WORDS = {
        'lietuvisk', 'lietuviska', 'lietuviski', 'lietuviskos',
        'sviez', 'sviezia', 'sviezias', 'sviezi',
        'saldyt', 'saldyta', 'saldytas',
        'plaut', 'plauta', 'plauti', 'plautos',
        'ekologisk', 'ekologiska', 'ekologiskas',
        'well', 'done', 'fasuot', 'raikyt', 'trint', 'smulkint', 'gabaliuk'
    }

    for src in req.sources:
        group_items = []
        for raw in src.items:
            raw_clean = raw.strip()
            if not raw_clean:
                continue
            group_items.append(raw_clean)
            
            # Išskaidome kiekį (pvz. 'Pomidorai 200g', 'Kiaušiniai 3vnt', 'Lietuviškos plautos morkos 80g')
            qty_match = re.search(r'(\d+([.,]\d+)?)\s*(kg|g|l|ml|vnt|vnt\.|pak\.|pakuotė|pakuotės|šaukštas|puodelis)?', raw_clean, re.I)
            qty = float(qty_match.group(1).replace(',', '.')) if qty_match else 1.0
            unit = qty_match.group(3) if qty_match and qty_match.group(3) else 'vnt'

            # Švarus pavadinimas be kiekių
            name_only = re.sub(r'\b\d+([.,]\d+)?\s*(kg|g|l|ml|vnt|vnt\.|pak\.|pakuotė|pakuotės|šaukštas|puodelis)?\b', '', raw_clean, flags=re.I).strip()
            name_only = re.sub(r'\s+', ' ', name_only).strip()

            # 1. Tikriname ar atitinka žinomą prekę duomenų bazėje
            matched_res = database.match_products_by_names([name_only or raw_clean])
            if matched_res.get("matched"):
                matched_p = matched_res["matched"][0]["product"]
                merge_key = f"prod_{matched_p['id']}"
                canonical_name = name_only or matched_p["name"]
            else:
                # 2. Jei bazėje prekės nėra, skaičiuojame raktą pagal visų reikšminių žodžių šaknis
                norm = database.normalize_lt(name_only)
                words = [w for w in re.findall(r'[a-z0-9]+', norm) if len(w) >= 3]
                stems = [database.stem_lt(w) for w in words]
                meaningful = [s for s in stems if s not in GENERIC_WORDS]
                if not meaningful:
                    meaningful = stems
                if meaningful:
                    merge_key = "term_" + "_".join(sorted(set(meaningful)))
                else:
                    merge_key = "raw_" + database.normalize_lt(name_only)
                canonical_name = name_only

            if merge_key not in merged:
                merged[merge_key] = {
                    "canonical_name": canonical_name,
                    "unit": unit,
                    "total_qty": 0.0,
                    "sources": [],
                    "raw_samples": []
                }
            
            merged[merge_key]["total_qty"] += qty
            merged[merge_key]["sources"].append({
                "source_name": src.source_name,
                "raw_item": raw_clean,
                "qty": qty,
                "unit": unit
            })
            merged[merge_key]["raw_samples"].append(f"{src.source_name} ({raw_clean})")

        groups.append({
            "source_name": src.source_name,
            "items_count": len(group_items),
            "items": group_items
        })

    # Paruošiame suvestinę
    combined_list = []
    final_shopping_text_lines = []

    for k, v in merged.items():
        is_dup = len(v["sources"]) > 1
        qty_rounded = round(v["total_qty"], 1)
        if qty_rounded == int(qty_rounded):
            qty_rounded = int(qty_rounded)
            
        combined_list.append({
            "name": v["canonical_name"],
            "total_qty": qty_rounded,
            "unit": v["unit"],
            "display_str": f"{v['canonical_name']} {qty_rounded} {v['unit']}".strip(),
            "is_duplicate": is_dup,
            "duplicate_count": len(v["sources"]),
            "sources_list": [s["source_name"] for s in v["sources"]],
            "details": v["raw_samples"]
        })
        final_shopping_text_lines.append(f"{v['canonical_name']} {qty_rounded} {v['unit']}".strip())

    return {
        "groups": groups,
        "combined_items": combined_list,
        "duplicates_count": sum(1 for c in combined_list if c["is_duplicate"]),
        "total_unique_items": len(combined_list),
        "final_shopping_text": "\n".join(final_shopping_text_lines)
    }

@app.post("/api/cart/resolve", summary="Suderinti poreikį su prekių baze (rasti vs trūkstami)")
def resolve_cart(req: ResolveRequest):
    items = []
    if req.items_list:
        items = req.items_list
    elif req.items_text:
        # Skaidome pagal eilutes arba kablelius
        raw_lines = req.items_text.replace("\n", ",").split(",")
        items = [line.strip() for line in raw_lines if line.strip()]
        
    match_result = database.match_products_by_names(items)
    return match_result

async def _run_cart_build_task(items: List[Dict[str, Any]], source_agent: str):
    global cart_build_status
    cart_build_status["is_running"] = True
    cart_build_status["progress"] = 10
    cart_build_status["logs"] = [f"Pradedamas krepšelio surinkimas iš šaltinio: {source_agent}..."]
    
    async def progress_cb(msg: str):
        cart_build_status["current_step"] = msg
        cart_build_status["logs"].append(msg)
        logger.info(msg)

    try:
        res = await barbora_service.add_products_to_cart(items, progress_callback=progress_cb)
        cart_build_status["last_result"] = res
        cart_build_status["progress"] = 100
        cart_build_status["current_step"] = "Surinkimas baigtas!"
        cart_build_status["logs"].append("Visi veiksmai atlikti sėkmingai.")
    except Exception as e:
        cart_build_status["current_step"] = f"Klaida: {str(e)}"
        cart_build_status["logs"].append(f"Klaida: {str(e)}")
    finally:
        cart_build_status["is_running"] = False

@app.post("/api/cart/build", summary="Surinkti krepšelį Barbora svetainėje")
async def build_cart(req: CartBuildRequest, background_tasks: BackgroundTasks):
    global cart_build_status
    if cart_build_status["is_running"]:
        return JSONResponse(status_code=400, content={"error": "Krepšelio surinkimo procesas jau vykdomas"})

    items_dicts = [item.model_dump() for item in req.items]
    background_tasks.add_task(_run_cart_build_task, items_dicts, req.source_agent or "AI_Agent")
    
    return {
        "success": True,
        "message": f"Krepšelio surinkimas pradėtas ({len(items_dicts)} prekės). Stebėkite būseną per /api/cart/status",
        "total_items": len(items_dicts)
    }

@app.get("/api/cart/status", summary="Tikrinti krepšelio surinkimo būseną realiu laiku")
def get_cart_status():
    return cart_build_status

@app.post("/api/browser/open-login", summary="Atidaryti Chrome naršyklę vartotojo prisijungimui")
async def open_login():
    res = await barbora_service.open_login_window()
    return res

@app.get("/api/browser/status", summary="Tikrinti ar vartotojas prisijungęs prie Barbora")
async def check_browser_status():
    res = await barbora_service.check_login_status()
    return res

@app.post("/api/browser/close", summary="Uždaryti naršyklės langą")
async def close_browser():
    await barbora_service.close_browser()
    return {"success": True, "message": "Naršyklė uždaryta"}

# --- Mitybos Agento API Endpoints ---

@app.get("/api/nutrition/profile", summary="Gauti kliento anketą (anamnezę)")
def get_nutrition_profile():
    return database.get_client_profile()

@app.post("/api/nutrition/profile", summary="Išsaugoti/atnaujinti kliento anketą")
def save_nutrition_profile(profile: ClientProfileModel):
    saved = database.save_client_profile(profile.model_dump())
    # Automatiškai perskaičiuojame ir atnaujiname pradines gaires
    metabolics = nutrition_agent.calculate_metabolics(saved)
    cur_guidelines = database.get_nutrition_guidelines()
    # Atnaujiname gairių BMR, TDEE, ir jei vartotojas nekeite - target_calories
    database.save_nutrition_guidelines({
        "bmr": metabolics["bmr"],
        "tdee": metabolics["tdee"],
        "target_calories": metabolics["target_calories"],
        "meals_per_day": cur_guidelines.get("meals_per_day", 4),
        "protein_grams": metabolics["protein_grams"],
        "fats_grams": metabolics["fats_grams"],
        "carbs_grams": metabolics["carbs_grams"],
        "notes": metabolics["notes"]
    })
    return {"success": True, "profile": saved, "metabolics": metabolics}

@app.get("/api/nutrition/guidelines", summary="Gauti mitybos gaires (redaguojama lentelė)")
def get_nutrition_guidelines_endpoint():
    return database.get_nutrition_guidelines()

@app.post("/api/nutrition/guidelines", summary="Išsaugoti redaguotas mitybos gaires")
def save_nutrition_guidelines_endpoint(guidelines: NutritionGuidelinesModel):
    saved = database.save_nutrition_guidelines(guidelines.model_dump())
    return {"success": True, "guidelines": saved, "message": "Gairės sėkmingai atnaujintos"}

@app.post("/api/nutrition/calculate", summary="Apskaičiuoti metabolinius rodiklius")
def calculate_metabolics_endpoint():
    profile = database.get_client_profile()
    return nutrition_agent.calculate_metabolics(profile)

@app.post("/api/nutrition/plan", summary="Sugeneruoti mitybos planą (1, 3 arba 7 dienoms)")
def generate_plan_endpoint(req: PlanRequestModel):
    profile = database.get_client_profile()
    guidelines = database.get_nutrition_guidelines()
    plan = nutrition_agent.generate_meal_plan(days=req.days, profile=profile, guidelines=guidelines)
    return plan

@app.post("/api/nutrition/plan-to-cart", summary="Perkelti plano pirkinių sąrašą į Barbora suderinimą")
def plan_to_cart_endpoint(req: PlanRequestModel):
    profile = database.get_client_profile()
    guidelines = database.get_nutrition_guidelines()
    plan = nutrition_agent.generate_meal_plan(days=req.days, profile=profile, guidelines=guidelines)
    
    # Ištraukiame visų ingredientų paieškos terminus
    search_terms = [item["search_term"] for item in plan["shopping_list"]]
    match_result = database.match_products_by_names(search_terms)
    
    return {
        "success": True,
        "plan_days": req.days,
        "matched": match_result["matched"],
        "missing": match_result["missing"],
        "shopping_list_raw": plan["shopping_list"]
    }

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    ico_path = os.path.join(os.path.dirname(__file__), "app.ico")
    if os.path.exists(ico_path):
        return FileResponse(ico_path)
    return JSONResponse(status_code=404, content={"detail": "Not found"})

@app.get("/icon.png", include_in_schema=False)
def get_icon():
    png_path = os.path.join(os.path.dirname(__file__), "icon.png")
    if os.path.exists(png_path):
        return FileResponse(png_path)
    return JSONResponse(status_code=404, content={"detail": "Not found"})

# --- Pagrindinis Web UI puslapis ---
@app.get("/", response_class=HTMLResponse, summary="Pagrindinis valdymo pultas")
def get_dashboard():
    with open(os.path.join(os.path.dirname(__file__), "index.html"), "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
