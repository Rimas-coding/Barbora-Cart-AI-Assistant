import sqlite3
import os
import sys
import re
from typing import List, Dict, Optional, Any

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

DB_FILE = os.path.join(os.path.dirname(__file__), "barbora_products.db")

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def normalize_lt(text: str) -> str:
    """Pašalina lietuviškas diakritines raides ir suvienodina registrą."""
    if not text:
        return ""
    text = text.lower().strip()
    repl = {'ą': 'a', 'č': 'c', 'ę': 'e', 'ė': 'e', 'į': 'i', 'š': 's', 'ų': 'u', 'ū': 'u', 'ž': 'z'}
    for k, v in repl.items():
        text = text.replace(k, v)
    return text

def stem_lt(word: str) -> str:
    """Išskiria lietuviško žodžio šaknį pašalinant linksnių ir daugiskaitos galūnes."""
    w = normalize_lt(word)
    if len(w) <= 3:
        return w
    # Dažniausios lietuviškos galūnės mažėjančia tvarka
    suffixes = [
        'iems', 'iams', 'iems', 'iose', 'uose', 'yje', 'eje', 'oje', 'ose', 'yse',
        'iais', 'omis', 'emis', 'iui', 'iui', 'ias', 'ius', 'ies', 'iui',
        'iai', 'ei', 'is', 'ys', 'os', 'es', 'as', 'us', 'uo', 'ia', 'iu',
        'e', 'a', 'i', 'u'
    ]
    for s in suffixes:
        if len(w) > len(s) + 2 and w.endswith(s):
            return w[:-len(s)]
    return w

def detect_category(name: str) -> str:
    """Automatiškai nustato kategoriją pagal prekės pavadinimą."""
    w = normalize_lt(name)
    # Aliejus turi eiti į Bakalėją, o ne į Vaisius/Daržoves (net jei alyvuogių)
    if 'aliej' in w:
        return "Bakalėja ir prieskoniai"
    if any(k in w for k in ['vistien', 'visciuk', 'broiler', 'jautien', 'kiaulien', 'kalakut', 'paukstien', 'mes', 'zuv', 'lasis', 'tun', 'upetak', 'fars', 'desr', 'kump', 'sonin', 'mesyte']):
        return "Mėsa ir žuvis"
    if any(k in w for k in ['pien', 'varsk', 'kiausin', 'grietin', 'jogurt', 'sur', 'sviest', 'kefyr', 'grietinel']):
        return "Pieno gaminiai ir kiaušiniai"
    if any(k in w for k in ['duon', 'baton', 'bandel', 'pyrag', 'lavash', 'tortilij', 'riestain']):
        return "Duonos gaminiai"
    if any(k in w for k in ['cukinij', 'pomidor', 'agurk', 'citrin', 'banan', 'obuol', 'brokol', 'mork', 'salot', 'paprik', 'uog', 'silauog', 'darzov', 'vais', 'bulv', 'svogun', 'cesnak', 'kopust', 'spinat', 'aviet', 'vynuog', 'kivis', 'apelsin', 'mandarin']):
        return "Daržovės ir vaisiai"
    if any(k in w for k in ['kav', 'arbat', 'vand', 'sult', 'gerim', 'limonad']):
        return "Gėrimai ir kava"
    if any(k in w for k in ['ryz', 'grik', 'makaron', 'dribsn', 'aviz', 'riesut', 'milt', 'cukr', 'drusk', 'pipir', 'sekl', 'pupel', 'lesi']):
        return "Bakalėja ir prieskoniai"
    return "Kita"

def canonical_category(cat: str) -> str:
    """Kanonizuoja kategorijos pavadinimą, nepriklausomai nuo registro ar diakritikos."""
    c = normalize_lt(cat)
    if 'darzov' in c or 'vais' in c:
        return "Daržovės ir vaisiai"
    if 'pien' in c or 'kiausin' in c:
        return "Pieno gaminiai ir kiaušiniai"
    if 'duon' in c:
        return "Duonos gaminiai"
    if 'mes' in c or 'zuv' in c:
        return "Mėsa ir žuvis"
    if 'kav' in c or 'gerim' in c or 'arbat' in c:
        return "Gėrimai ir kava"
    if 'bakal' in c or 'prieskon' in c:
        return "Bakalėja ir prieskoniai"
    return cat.strip() or "Kita"

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Prekių lentelė
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        url TEXT NOT NULL UNIQUE,
        price REAL DEFAULT 0.0,
        unit TEXT DEFAULT 'vnt',
        aliases TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Patikriname ar stulpelis aliases egzistuoja (migracija)
    cursor.execute("PRAGMA table_info(products)")
    columns = [row["name"] for row in cursor.fetchall()]
    if "aliases" not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN aliases TEXT DEFAULT ''")
    
    # Kategorijų lentelė
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
        )
    """)

    # Kliento profilio (anamnezės) lentelė
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS client_profile (
        id INTEGER PRIMARY KEY DEFAULT 1,
        name TEXT DEFAULT 'Vartotojas',
        gender TEXT DEFAULT 'vyras',
        age INTEGER DEFAULT 30,
        height REAL DEFAULT 180.0,
        weight REAL DEFAULT 80.0,
        body_fat_pct REAL DEFAULT 18.0,
        activity_level TEXT DEFAULT 'moderate',
        goal TEXT DEFAULT 'fat_loss',
        training_frequency INTEGER DEFAULT 3,
        training_time TEXT DEFAULT 'evening',
        dietary_preference TEXT DEFAULT 'all',
        allergies_restrictions TEXT DEFAULT '',
        health_notes TEXT DEFAULT '',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Pagrindinių mitybos gairių lentelė (redaguojama bet kada)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nutrition_guidelines (
        id INTEGER PRIMARY KEY DEFAULT 1,
        bmr INTEGER DEFAULT 1800,
        tdee INTEGER DEFAULT 2500,
        target_calories INTEGER DEFAULT 2000,
        meals_per_day INTEGER DEFAULT 4,
        protein_grams INTEGER DEFAULT 160,
        fats_grams INTEGER DEFAULT 65,
        carbs_grams INTEGER DEFAULT 190,
        notes TEXT DEFAULT 'Nuosaikus kalorijų deficitas riebalų mažinimui',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Krepšelio istorijos / poreikių lentelė
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cart_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_agent TEXT DEFAULT 'user',
        status TEXT DEFAULT 'pending',
        raw_input TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Standartinių pirkinių sąrašų lentelė
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS saved_shopping_lists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        items_text TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Išsaugotų patiekalų (receptų) lentelė
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS saved_dishes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT DEFAULT '',
        ingredients_text TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    
    # Užpildom pradines kategorijas
    default_categories = [
        "Pieno gaminiai ir kiaušiniai",
        "Daržovės ir vaisiai",
        "Duonos gaminiai",
        "Mėsa ir žuvis",
        "Gėrimai ir kava",
        "Bakalėja ir prieskoniai",
        "Kita"
    ]
    for cat in default_categories:
        cursor.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat,))
    conn.commit()

    # Patikrinam ar produktų lentelė tuščia, jei taip - sudedam pradinius iš Pirkiniu baze.txt
    cursor.execute("SELECT COUNT(*) as cnt FROM products")
    count = cursor.fetchone()["cnt"]
    if count == 0:
        seed_initial_products(conn)

    conn.close()

def seed_initial_products(conn):
    cursor = conn.cursor()
    initial_items = [
        {
            "name": "Malta kava Pupa Sweet Brazil 100% Arabika, 500 g",
            "category": "Gėrimai ir kava",
            "url": "https://barbora.lt/produktai/malta-kava-pupa-sweet-brazil-100-proc-arabika-500-g",
            "price": 7.99,
            "unit": "vnt"
        },
        {
            "name": "Juoda raikyta duona Well Done, 375 g",
            "category": "Duonos gaminiai",
            "url": "https://barbora.lt/produktai/juoda-raikyta-duona-well-done-375-g",
            "price": 0.89,
            "unit": "vnt"
        },
        {
            "name": "Pomidorai su šakelėmis, 1 kg",
            "category": "Daržovės ir vaisiai",
            "url": "https://barbora.lt/produktai/pomidorai-su-sakelemis-1-kg",
            "price": 3.99,
            "unit": "kg"
        },
        {
            "name": "Lietuviški trumpavaisiai agurkai, 1 kg",
            "category": "Daržovės ir vaisiai",
            "url": "https://barbora.lt/produktai/lietuviski-trumpavaisiai-agurkai-1-kg",
            "price": 2.29,
            "unit": "kg"
        },
        {
            "name": "Ant kraiko laikomų vištų kiaušiniai Well Done, 10 vnt.",
            "category": "Pieno gaminiai ir kiaušiniai",
            "url": "https://barbora.lt/produktai/ant-kraiko-laikomu-vistu-kiausiniai-well-done-10-vnt-10-vnt",
            "price": 1.79,
            "unit": "vnt"
        },
        {
            "name": "Natūrali Žemaitijos grietinė 30% riebumo, 400 g",
            "category": "Pieno gaminiai ir kiaušiniai",
            "url": "https://barbora.lt/produktai/naturali-zemaitijos-grietine-30-proc-rieb-400-g",
            "price": 2.19,
            "unit": "vnt"
        }
    ]
    for item in initial_items:
        cursor.execute("""
        INSERT OR IGNORE INTO products (name, category, url, price, unit)
        VALUES (?, ?, ?, ?, ?)
        """, (item["name"], item["category"], item["url"], item["price"], item["unit"]))
    conn.commit()

def get_all_products(category: Optional[str] = None, search: Optional[str] = None) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM products WHERE 1=1"
    params = []
    
    if category and category != "Visos":
        canon_cat = canonical_category(category)
        query += " AND (category = ? OR category LIKE ?)"
        params.extend([canon_cat, f"%{canon_cat}%"])
        
    if search:
        s_norm = normalize_lt(search)
        query += " AND (name LIKE ? OR url LIKE ? OR aliases LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, f"%{s_norm}%"])
        
    query += " ORDER BY category ASC, name ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    result = [dict(row) for row in rows]
    conn.close()
    return result

def get_categories() -> List[str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM categories ORDER BY name ASC")
    cats = [row["name"] for row in cursor.fetchall()]
    conn.close()
    return cats

def add_product(name: str, category: str, url: str, price: float = 0.0, unit: str = "vnt", alias: Optional[str] = None) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    url = url.strip()
    name = name.strip()
    
    # Kanonizuojame kategoriją arba automatiškai nustatome, jei nenurodyta
    cat = canonical_category(category)
    if cat == "Kita" or not cat:
        cat = detect_category(name)

    # Išsaugome esamus aliasus arba pridedame naują
    cursor.execute("SELECT aliases FROM products WHERE url = ?", (url,))
    existing = cursor.fetchone()
    aliases_set = set()
    if existing and existing["aliases"]:
        aliases_set = set(a.strip() for a in existing["aliases"].split(",") if a.strip())
    if alias:
        aliases_set.add(alias.strip().lower())
    aliases_str = ",".join(aliases_set)

    cursor.execute("""
    INSERT INTO products (name, category, url, price, unit, aliases)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(url) DO UPDATE SET
        name = excluded.name,
        category = excluded.category,
        price = CASE WHEN excluded.price > 0 THEN excluded.price ELSE products.price END,
        unit = excluded.unit,
        aliases = CASE WHEN LENGTH(excluded.aliases) > 0 THEN excluded.aliases ELSE products.aliases END
    """, (name, cat, url, price, unit, aliases_str))
    prod_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return prod_id

def delete_product(product_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def match_products_by_names(item_names: List[str]) -> Dict[str, any]:
    """
    Išmaniai randa prekes pagal pateiktus pavadinimus/raktažodžius:
    1. Tiesioginis atitikimas ir sinonimai (aliases).
    2. Lietuviškų šaknų (stemming) atitikimas su reikšminių žodžių (daiktavardžių) reikalavimu.
    3. Užkerta kelią klaidingiems sutapimams pagal bendrinius būdvardžius (pvz. 'lietuviškas', 'šviežias').
    """
    all_prods = get_all_products()
    matched = []
    missing = []
    
    # Bendriniai būdvardžiai ir pjaustymo formos, kurios vienos pačios negali nulemti prekės atitikimo
    GENERIC_WORDS = {
        'lietuvisk', 'lietuviska', 'lietuviski', 'lietuviskos',
        'sviez', 'sviezia', 'sviezias', 'sviezi',
        'saldyt', 'saldyta', 'saldytas',
        'plaut', 'plauta', 'plauti', 'plautos',
        'ekologisk', 'ekologiska', 'ekologiskas',
        'well', 'done', 'fasuot', 'raikyt', 'trint', 'smulkint', 'gabaliuk',
        'file', 'farsas', 'kumpis', 'krutinele', 'slauneles', 'nugarine', 'pjausnys', 'riekeles', 'gabaleliai'
    }
    GENERIC_STEMS = {stem_lt(w) for w in GENERIC_WORDS}

    # Baltymų / rūšių konfliktai (kad pvz. lašišos filė niekada netaptų vištienos filė)
    PROTEIN_CONFLICTS = {
        'lasis': {'vistien', 'visciuk', 'broiler', 'kiaulien', 'jautien', 'kalakut', 'antis', 'antien', 'tunas'},
        'upetak': {'vistien', 'visciuk', 'broiler', 'kiaulien', 'jautien', 'kalakut'},
        'tunas': {'vistien', 'visciuk', 'broiler', 'kiaulien', 'jautien', 'lasis'},
        'vistien': {'lasis', 'tunas', 'upetak', 'kiaulien', 'jautien'},
        'visciuk': {'lasis', 'tunas', 'upetak', 'kiaulien', 'jautien'},
        'broiler': {'lasis', 'tunas', 'upetak', 'kiaulien', 'jautien'},
        'kiaulien': {'lasis', 'tunas', 'vistien', 'visciuk', 'broiler', 'jautien'},
        'jautien': {'lasis', 'tunas', 'vistien', 'visciuk', 'broiler', 'kiaulien'}
    }
    
    for item in item_names:
        cleaned = item.strip()
        if not cleaned:
            continue
            
        cleaned_norm = normalize_lt(cleaned)
        # Pašaliname kiekius iš užklausos (pvz. '1kg', '500g', '10vnt', '180 g')
        cleaned_no_qty = re.sub(r'\b\d+([.,]\d+)?\s*(kg|g|l|ml|vnt|proc|%)\b', '', cleaned_norm).strip()
        words = [w for w in cleaned_no_qty.split() if len(w) >= 3]
        stems = [stem_lt(w) for w in words]
        
        # Atskiriame reikšminius žodžius (daiktavardžius) nuo bendrinių formų/būdvardžių
        meaningful_stems = [s for s in stems if s not in GENERIC_STEMS]
        if not meaningful_stems:
            meaningful_stems = stems
            
        suggested_cat = detect_category(cleaned)
        
        best_match = None
        best_score = 0
        
        # 1 lygis: Tikriname tiesioginį arba sinonimų (aliases) atitikimą
        for p in all_prods:
            p_name_norm = normalize_lt(p["name"])
            p_url_norm = normalize_lt(p["url"])
            p_aliases = normalize_lt(p.get("aliases", "") or "")
            target_text = f"{p_name_norm} {p_url_norm} {p_aliases}"
            
            if cleaned_no_qty and cleaned_no_qty in target_text:
                best_match = p
                best_score = 100
                break
                
        # 2 lygis: Balais grįstas reitingavimas pagal šaknis ir kategoriją
        if best_score < 100:
            for p in all_prods:
                p_name_norm = normalize_lt(p["name"])
                p_url_norm = normalize_lt(p["url"])
                p_aliases = normalize_lt(p.get("aliases", "") or "")
                target_text = f"{p_name_norm} {p_url_norm} {p_aliases}"

                # Tikriname rūšių konfliktus (pvz. užklausoje lašiša, o prekėje vištiena)
                has_conflict = False
                for req_stem in stems:
                    if req_stem in PROTEIN_CONFLICTS:
                        conflicting = PROTEIN_CONFLICTS[req_stem]
                        if any(c in target_text for c in conflicting):
                            has_conflict = True
                            break
                if has_conflict:
                    continue
                
                score = 0
                has_meaningful_match = False
                
                for st in meaningful_stems:
                    if st in target_text:
                        score += 10
                        has_meaningful_match = True
                        
                for st in stems:
                    if st in GENERIC_STEMS and st in target_text:
                        score += 1
                        
                if has_meaningful_match and p.get("category") == suggested_cat:
                    score += 5
                    
                # Reikalaujame BŪTINAI bent vieno reikšminio daiktavardžio sutapimo
                if has_meaningful_match and score > best_score:
                    best_score = score
                    best_match = p
                    
        if best_match and best_score >= 10:
            matched.append({
                "requested_name": cleaned,
                "product": best_match,
                "status": "found"
            })
        else:
            missing.append({
                "requested_name": cleaned,
                "status": "missing",
                "suggested_category": suggested_cat,
                "message": "Trūksta duomenų bazėje. Reikia įvesti ranka nuorodą."
            })
            
    return {
        "matched": matched,
        "missing": missing,
        "total_requested": len(item_names),
        "total_matched": len(matched),
        "total_missing": len(missing)
    }

def get_client_profile() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM client_profile WHERE id = 1")
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO client_profile (id) VALUES (1)")
        conn.commit()
        cursor.execute("SELECT * FROM client_profile WHERE id = 1")
        row = cursor.fetchone()
    profile = dict(row)
    conn.close()
    return profile

def save_client_profile(data: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO client_profile (
        id, name, gender, age, height, weight, body_fat_pct,
        activity_level, goal, training_frequency, training_time,
        dietary_preference, allergies_restrictions, health_notes, updated_at
    ) VALUES (
        1, :name, :gender, :age, :height, :weight, :body_fat_pct,
        :activity_level, :goal, :training_frequency, :training_time,
        :dietary_preference, :allergies_restrictions, :health_notes, CURRENT_TIMESTAMP
    )
    ON CONFLICT(id) DO UPDATE SET
        name = excluded.name,
        gender = excluded.gender,
        age = excluded.age,
        height = excluded.height,
        weight = excluded.weight,
        body_fat_pct = excluded.body_fat_pct,
        activity_level = excluded.activity_level,
        goal = excluded.goal,
        training_frequency = excluded.training_frequency,
        training_time = excluded.training_time,
        dietary_preference = excluded.dietary_preference,
        allergies_restrictions = excluded.allergies_restrictions,
        health_notes = excluded.health_notes,
        updated_at = CURRENT_TIMESTAMP
    """, data)
    conn.commit()
    conn.close()
    return get_client_profile()

def get_nutrition_guidelines() -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM nutrition_guidelines WHERE id = 1")
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO nutrition_guidelines (id) VALUES (1)")
        conn.commit()
        cursor.execute("SELECT * FROM nutrition_guidelines WHERE id = 1")
        row = cursor.fetchone()
    guidelines = dict(row)
    conn.close()
    return guidelines

def save_nutrition_guidelines(data: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO nutrition_guidelines (
        id, bmr, tdee, target_calories, meals_per_day,
        protein_grams, fats_grams, carbs_grams, notes, updated_at
    ) VALUES (
        1, :bmr, :tdee, :target_calories, :meals_per_day,
        :protein_grams, :fats_grams, :carbs_grams, :notes, CURRENT_TIMESTAMP
    )
    ON CONFLICT(id) DO UPDATE SET
        bmr = excluded.bmr,
        tdee = excluded.tdee,
        target_calories = excluded.target_calories,
        meals_per_day = excluded.meals_per_day,
        protein_grams = excluded.protein_grams,
        fats_grams = excluded.fats_grams,
        carbs_grams = excluded.carbs_grams,
        notes = excluded.notes,
        updated_at = CURRENT_TIMESTAMP
    """, data)
    conn.commit()
    conn.close()
    return get_nutrition_guidelines()

def get_saved_shopping_lists() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM saved_shopping_lists ORDER BY name ASC")
    rows = cursor.fetchall()
    res = [dict(r) for r in rows]
    conn.close()
    return res

def save_shopping_list(name: str, items_text: str) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO saved_shopping_lists (name, items_text)
    VALUES (?, ?)
    ON CONFLICT(name) DO UPDATE SET
        items_text = excluded.items_text,
        created_at = CURRENT_TIMESTAMP
    """, (name.strip(), items_text.strip()))
    list_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return list_id

def delete_shopping_list(list_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM saved_shopping_lists WHERE id = ?", (list_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_saved_dishes() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM saved_dishes ORDER BY name ASC")
    rows = cursor.fetchall()
    res = [dict(r) for r in rows]
    conn.close()
    return res

def save_dish(name: str, ingredients_text: str, description: str = "") -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO saved_dishes (name, description, ingredients_text)
    VALUES (?, ?, ?)
    ON CONFLICT(name) DO UPDATE SET
        description = excluded.description,
        ingredients_text = excluded.ingredients_text,
        created_at = CURRENT_TIMESTAMP
    """, (name.strip(), description.strip(), ingredients_text.strip()))
    dish_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return dish_id

def delete_dish(dish_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM saved_dishes WHERE id = ?", (dish_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def seed_default_lists_and_dishes():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Standartiniai sąrašai
    cursor.execute("SELECT COUNT(*) as cnt FROM saved_shopping_lists")
    if cursor.fetchone()["cnt"] == 0:
        cursor.execute("""
        INSERT INTO saved_shopping_lists (name, items_text) VALUES 
        ('Savaitinis bazinis krepšelis', 'Pomidorai 1kg\nLietuviški trumpavaisiai agurkai 1kg\nKiaušiniai 10vnt\nJuoda duona\nPienas 2.5%\nVarškė 9%\nMalta kava 500g\nNatūrali grietinė 30%'),
        ('Pusryčių ir energijos rinkinys', 'Kiaušiniai 10vnt\nJuoda duona\nVisų grūdo dalių avižiniai dribsniai\nŠaldytos šilauogės\nGraikiniai riešutai\nMalta kava 500g')
        """)
        
    # Patiekalai
    cursor.execute("SELECT COUNT(*) as cnt FROM saved_dishes")
    if cursor.fetchone()["cnt"] == 0:
        cursor.execute("""
        INSERT INTO saved_dishes (name, description, ingredients_text) VALUES
        ('Šakšuka su pomidorais', 'Klasikinis baltyminis pusryčių patiekalas su kiaušiniais ir pomidorais', 'Kiaušiniai 3vnt\nPomidorai su šakelėmis 200g\nJuoda duona 60g\nAlyvuogių aliejus 10ml'),
        ('Citrininė vištiena su cukinija ir ryžiais', 'Sportininkų One-Pan pietūs su liesa vištiena ir daržovėmis', 'Vištienos filė 200g\nBasmati ryžiai 75g\nŽaliosios cukinijos 150g\nCitrinos 1vnt\nAlyvuogių aliejus 10ml'),
        ('Kepta lašiša su brokoliais', 'Omega-3 vakarienė raumenų atsistatymui', 'Lašišos filė 180g\nBrokolis 200g\nCitrinos 1vnt\nAlyvuogių aliejus 10ml'),
        ('Viduržemio jūros tuno salotos', 'Greitas pietų variantas be terminio apdorojimo', 'Tunas savo sultyse 140g\nKiaušiniai 2vnt\nPomidorai su šakelėmis 150g\nLietuviški trumpavaisiai agurkai 100g\nJuoda duona 50g'),
        ('Jautienos troškinys su grikiais', 'Meal Prep sotūs pietūs dėžutėms kelioms dienoms', 'Liesa jautiena 180g\nGrikiai 70g\nLietuviškos plautos morkos 80g\nLietuviški trumpavaisiai agurkai 100g')
        """)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    seed_default_lists_and_dishes()
    print("Duomenų bazė inicializuota. Produktų skaičius:", len(get_all_products()))
    print("Standartinių sąrašų:", len(get_saved_shopping_lists()), "Patiekalų:", len(get_saved_dishes()))
