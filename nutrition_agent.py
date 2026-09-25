import math
import sys
from typing import Dict, List, Any, Optional

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Aktyvumo daugikliai pagal Harris-Benedict / Mifflin-St Jeor
ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,      # Sėdimas darbas, minimalus judėjimas
    "light": 1.375,        # Lengvas aktyvumas (1-3 treniruotės/sav.)
    "moderate": 1.55,      # Vidutinis aktyvumas (3-5 treniruotės/sav.)
    "very_active": 1.725,  # Labai aktyvus (6-7 sunkios treniruotės/sav.)
    "athlete": 1.9         # Ypatingai sunkus fizinis darbas arba 2 treniruotės/d.
}

def calculate_metabolics(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apskaičiuoja BMR, TDEE, KMI ir pradines rekomendacijas pagal Mifflin-St Jeor formulę.
    """
    weight = float(profile.get("weight", 80.0))
    height = float(profile.get("height", 180.0))
    age = int(profile.get("age", 30))
    gender = profile.get("gender", "vyras").lower()
    activity = profile.get("activity_level", "moderate")
    goal = profile.get("goal", "fat_loss")
    
    # KMI
    height_m = height / 100.0
    bmi = round(weight / (height_m * height_m), 1)
    
    # BMR (Mifflin-St Jeor)
    if gender == "moteris":
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    bmr = int(round(bmr))
    
    # TDEE
    multiplier = ACTIVITY_MULTIPLIERS.get(activity, 1.55)
    tdee = int(round(bmr * multiplier))
    
    # Tikslinis kalorijų skaičius
    if goal == "fat_loss":
        target_calories = int(round(tdee * 0.80)) # 20% deficitas
        protein_g = int(round(weight * 2.0))      # 2.0g/kg raumenų apsaugai
        fats_g = int(round(weight * 0.85))         # 0.85g/kg hormonams
        notes = "Strategija: Kalorijų deficitas (-20%) riebalų masei mažinti išsaugant raumenis."
    elif goal == "muscle_gain":
        target_calories = int(round(tdee * 1.12)) # 12% perteklius
        protein_g = int(round(weight * 1.9))
        fats_g = int(round(weight * 0.95))
        notes = "Strategija: Nuosaikus kalorijų perteklius (+12%) raumenų masei auginti."
    elif goal == "endurance":
        target_calories = int(round(tdee * 1.05))
        protein_g = int(round(weight * 1.6))
        fats_g = int(round(weight * 0.9))
        notes = "Strategija: Palaikymas su padidintu angliavandenių kiekiu glikogeno atsargoms."
    else: # maintenance
        target_calories = tdee
        protein_g = int(round(weight * 1.7))
        fats_g = int(round(weight * 0.9))
        notes = "Strategija: Izokalorinė mityba esamo svorio ir formos palaikymui."
        
    # Likusios kalorijos - angliavandeniai (1g B = 4 kcal, 1g R = 9 kcal, 1g A = 4 kcal)
    carb_cals = max(0, target_calories - (protein_g * 4 + fats_g * 9))
    carbs_g = int(round(carb_cals / 4.0))
    
    # Hidratacija (ml)
    water_ml = int(round(weight * 38))
    
    # Raudonos vėliavos (rizikų vertinimas pagal sisteminę instrukciją)
    red_flags = []
    if bmi < 18.5:
        red_flags.append("Kūno masės indeksas rodo nepakankamą svorį (<18.5). Deficitas draudžiamas!")
    elif bmi > 32:
        red_flags.append("Padidintas KMI (>32). Rekomenduojamas švelnus, tolygus svorio metimas tausojant sąnarius.")
    if target_calories < bmr and goal == "fat_loss":
        red_flags.append("Perspėjimas: Numatytas kalorijų kiekis artimas baziniai apykaitai (BMR). Nemažinkite labiau!")
    if age > 50:
        red_flags.append("Amžius > 50m. Ypatingas dėmesys baltymų kokybei, leucinui ir kalcio/vitamino D balansui.")

    return {
        "bmi": bmi,
        "bmr": bmr,
        "tdee": tdee,
        "target_calories": target_calories,
        "protein_grams": protein_g,
        "fats_grams": fats_g,
        "carbs_grams": carbs_g,
        "water_ml": water_ml,
        "notes": notes,
        "red_flags": red_flags
    }

# Receptų šablonai iš pateiktų DOCX failų
MEAL_RECIPES = {
    "breakfast": [
        {
            "name": "Avižinė košė su uogomis ir graikiniais riešutais",
            "desc": "Lėto pasisavinimo angliavandeniai ir sveiki riebalai smegenų veiklai.",
            "cals": 480, "protein": 18, "fats": 16, "carbs": 65,
            "ingredients": [
                {"name": "Avižiniai dribsniai", "amount": 60, "unit": "g", "barbora_search": "avižiniai dribsniai"},
                {"name": "Pienas 2.5%", "amount": 150, "unit": "ml", "barbora_search": "pienas 2.5"},
                {"name": "Graikiniai riešutai", "amount": 20, "unit": "g", "barbora_search": "graikiniai riešutai"},
                {"name": "Šilauogės arba uogos", "amount": 60, "unit": "g", "barbora_search": "šilauogės"},
                {"name": "Malta kava Sweet Brazil", "amount": 1, "unit": "puodelis", "barbora_search": "malta kava pupa sweet brazil"}
            ]
        },
        {
            "name": "Šakšuka (Kiaušinienė su pomidorais) ir juoda duona",
            "desc": "Baltymų ir likopeno šaltinis, suteikiantis sotumo jausmą visam rytui.",
            "cals": 460, "protein": 24, "fats": 22, "carbs": 38,
            "ingredients": [
                {"name": "Kiaušiniai Well Done", "amount": 3, "unit": "vnt", "barbora_search": "kiaušiniai well done"},
                {"name": "Pomidorai su šakelėmis", "amount": 150, "unit": "g", "barbora_search": "pomidorai su šakelėmis"},
                {"name": "Juoda raikyta duona Well Done", "amount": 60, "unit": "g", "barbora_search": "juoda raikyta duona well done"},
                {"name": "Alyvuogių aliejus", "amount": 8, "unit": "ml", "barbora_search": "alyvuogių aliejus"}
            ]
        },
        {
            "name": "Grūdėta varškė su agurkais, žolelėmis ir juoda duona",
            "desc": "Lengvas, bet labai sotus pusryčių variantas su kazeino baltymais.",
            "cals": 420, "protein": 30, "fats": 12, "carbs": 44,
            "ingredients": [
                {"name": "Natūrali Žemaitijos grietinė 30%", "amount": 30, "unit": "g", "barbora_search": "natūrali žemaitijos grietinė"},
                {"name": "Varškė 9%", "amount": 180, "unit": "g", "barbora_search": "varškė 9"},
                {"name": "Lietuviški trumpavaisiai agurkai", "amount": 100, "unit": "g", "barbora_search": "lietuviški trumpavaisiai agurkai"},
                {"name": "Juoda raikyta duona Well Done", "amount": 70, "unit": "g", "barbora_search": "juoda raikyta duona well done"}
            ]
        }
    ],
    "lunch": [
        {
            "name": "Citrininė vištienos krūtinėlė su cukinijomis ir ryžiais (One-Pan)",
            "desc": "Greitai paruošiamas sportininkų pietų protokolas su liesais baltymais.",
            "cals": 620, "protein": 48, "fats": 14, "carbs": 72,
            "ingredients": [
                {"name": "Vištienos filė", "amount": 180, "unit": "g", "barbora_search": "vištienos filė"},
                {"name": "Basmati ryžiai", "amount": 75, "unit": "g", "barbora_search": "basmati ryžiai"},
                {"name": "Cukinija", "amount": 120, "unit": "g", "barbora_search": "cukinija"},
                {"name": "Pomidorai su šakelėmis", "amount": 100, "unit": "g", "barbora_search": "pomidorai su šakelėmis"},
                {"name": "Alyvuogių aliejus", "amount": 10, "unit": "ml", "barbora_search": "alyvuogių aliejus"}
            ]
        },
        {
            "name": "Meal-Prep Jautienos troškinys su grikiais ir daržovėmis",
            "desc": "Gausu geležies, cinko ir lėto pasisavinimo energijos aktyviai dienai.",
            "cals": 650, "protein": 46, "fats": 18, "carbs": 68,
            "ingredients": [
                {"name": "Liesa jautiena (troškinimui)", "amount": 160, "unit": "g", "barbora_search": "jautiena"},
                {"name": "Grikiai", "amount": 70, "unit": "g", "barbora_search": "grikiai"},
                {"name": "Morkos", "amount": 80, "unit": "g", "barbora_search": "morkos"},
                {"name": "Lietuviški trumpavaisiai agurkai", "amount": 100, "unit": "g", "barbora_search": "lietuviški trumpavaisiai agurkai"}
            ]
        },
        {
            "name": "Viduržemio jūros tuno salotos su kiaušiniu ir pomidorais",
            "desc": "Omega-3 riebalų rūgštys, greitas paruošimas be papildomo šildymo.",
            "cals": 540, "protein": 42, "fats": 20, "carbs": 42,
            "ingredients": [
                {"name": "Tunas savo sultyse", "amount": 140, "unit": "g", "barbora_search": "tunas savo sultyse"},
                {"name": "Kiaušiniai Well Done", "amount": 2, "unit": "vnt", "barbora_search": "kiaušiniai well done"},
                {"name": "Pomidorai su šakelėmis", "amount": 150, "unit": "g", "barbora_search": "pomidorai su šakelėmis"},
                {"name": "Lietuviški trumpavaisiai agurkai", "amount": 100, "unit": "g", "barbora_search": "lietuviški trumpavaisiai agurkai"},
                {"name": "Juoda raikyta duona Well Done", "amount": 50, "unit": "g", "barbora_search": "juoda raikyta duona well done"}
            ]
        }
    ],
    "snack": [
        {
            "name": "Bananas su graikišku jogurtu ir chia sėklomis (Prieš-treniruotinis)",
            "desc": "Greita energija raumenims be virškinimo apsunkinimo.",
            "cals": 260, "protein": 14, "fats": 5, "carbs": 42,
            "ingredients": [
                {"name": "Bananas", "amount": 120, "unit": "g", "barbora_search": "bananai"},
                {"name": "Graikiškas jogurtas", "amount": 120, "unit": "g", "barbora_search": "graikiškas jogurtas"}
            ]
        },
        {
            "name": "Ryžių trapučiai su riešutų sviestu ir obuoliu",
            "desc": "Subalansuotas energijos užkandis tarp pagrindinių valgymų.",
            "cals": 280, "protein": 8, "fats": 12, "carbs": 38,
            "ingredients": [
                {"name": "Ryžių trapučiai", "amount": 30, "unit": "g", "barbora_search": "ryžių trapučiai"},
                {"name": "Žemės riešutų sviestas", "amount": 20, "unit": "g", "barbora_search": "riešutų sviestas"},
                {"name": "Obuolys", "amount": 150, "unit": "g", "barbora_search": "obuoliai"}
            ]
        }
    ],
    "dinner": [
        {
            "name": "Kepta lašišos filė su garintais brokoliais ir citrina",
            "desc": "Omega-3 ir baltymai naktiniam raumenų audinių atsistatymui ir hormonų balansui.",
            "cals": 520, "protein": 38, "fats": 26, "carbs": 18,
            "ingredients": [
                {"name": "Lašišos filė", "amount": 170, "unit": "g", "barbora_search": "lašišos filė"},
                {"name": "Brokoliai", "amount": 200, "unit": "g", "barbora_search": "brokoliai"},
                {"name": "Citrinos", "amount": 30, "unit": "g", "barbora_search": "citrina"},
                {"name": "Alyvuogių aliejus", "amount": 5, "unit": "ml", "barbora_search": "alyvuogių aliejus"}
            ]
        },
        {
            "name": "Varškės vakarienė su graikišku jogurtu ir uogomis",
            "desc": "Lėtai virškinamas kazeinas aprūpina aminorūgštimis miego metu.",
            "cals": 450, "protein": 36, "fats": 14, "carbs": 38,
            "ingredients": [
                {"name": "Varškė 9%", "amount": 180, "unit": "g", "barbora_search": "varškė 9"},
                {"name": "Natūrali Žemaitijos grietinė 30%", "amount": 25, "unit": "g", "barbora_search": "natūrali žemaitijos grietinė"},
                {"name": "Uogos (avietės arba šilauogės)", "amount": 80, "unit": "g", "barbora_search": "šilauogės"}
            ]
        },
        {
            "name": "Keptos vištienos salotos su pomidorais ir agurkais",
            "desc": "Lengvas mažai angliavandenių turintis vakaro valgymas.",
            "cals": 440, "protein": 42, "fats": 16, "carbs": 18,
            "ingredients": [
                {"name": "Vištienos filė", "amount": 160, "unit": "g", "barbora_search": "vištienos filė"},
                {"name": "Pomidorai su šakelėmis", "amount": 150, "unit": "g", "barbora_search": "pomidorai su šakelėmis"},
                {"name": "Lietuviški trumpavaisiai agurkai", "amount": 120, "unit": "g", "barbora_search": "lietuviški trumpavaisiai agurkai"},
                {"name": "Alyvuogių aliejus", "amount": 10, "unit": "ml", "barbora_search": "alyvuogių aliejus"}
            ]
        }
    ]
}

def generate_meal_plan(days: int = 1, profile: Optional[Dict[str, Any]] = None, guidelines: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Sugeneruoja mitybos planą 1 dienai, kelioms dienoms (3) arba savaitei (7).
    """
    if profile is None:
        import database
        profile = database.get_client_profile()
    if guidelines is None:
        import database
        guidelines = database.get_nutrition_guidelines()

    target_cals = guidelines.get("target_calories", 2000)
    meals_count = guidelines.get("meals_per_day", 4)
    training_time = profile.get("training_time", "evening")

    daily_plans = []
    aggregated_ingredients: Dict[str, Dict[str, Any]] = {}

    for d in range(1, days + 1):
        day_meals = []
        
        # Parinkimas pagal dienotvarkę
        b_idx = (d - 1) % len(MEAL_RECIPES["breakfast"])
        l_idx = (d - 1) % len(MEAL_RECIPES["lunch"])
        s_idx = (d - 1) % len(MEAL_RECIPES["snack"])
        d_idx = (d - 1) % len(MEAL_RECIPES["dinner"])

        breakfast = MEAL_RECIPES["breakfast"][b_idx].copy()
        lunch = MEAL_RECIPES["lunch"][l_idx].copy()
        snack = MEAL_RECIPES["snack"][s_idx].copy()
        dinner = MEAL_RECIPES["dinner"][d_idx].copy()

        # Pridedame laiko žymas pagal treniruočių laiką
        if training_time == "morning":
            day_meals.append({"time": "07:00", "title": "Prieš treniruotę (Lengvas)", "meal": snack})
            day_meals.append({"time": "08:00 - 09:15", "title": "🏋️ TRENIRUOTĖ", "is_workout": True})
            day_meals.append({"time": "09:30", "title": "Po treniruotės (Sotūs pusryčiai)", "meal": breakfast})
            day_meals.append({"time": "13:30", "title": "Pietūs", "meal": lunch})
            if meals_count >= 4:
                day_meals.append({"time": "19:00", "title": "Vakarienė", "meal": dinner})
        elif training_time == "noon":
            day_meals.append({"time": "08:00", "title": "Pusryčiai", "meal": breakfast})
            day_meals.append({"time": "11:30", "title": "Prieš treniruotę (Užkandis)", "meal": snack})
            day_meals.append({"time": "12:15 - 13:30", "title": "🏋️ TRENIRUOTĖ", "is_workout": True})
            day_meals.append({"time": "14:00", "title": "Po treniruotės (Pietūs)", "meal": lunch})
            if meals_count >= 4:
                day_meals.append({"time": "19:30", "title": "Vakarienė", "meal": dinner})
        else: # evening arba none
            day_meals.append({"time": "08:00", "title": "Pusryčiai", "meal": breakfast})
            day_meals.append({"time": "12:30", "title": "Pietūs", "meal": lunch})
            if meals_count >= 4:
                day_meals.append({"time": "16:30", "title": "Pavakariai (Prieš treniruotę)", "meal": snack})
            if training_time == "evening":
                day_meals.append({"time": "18:00 - 19:15", "title": "🏋️ TRENIRUOTĖ", "is_workout": True})
            day_meals.append({"time": "20:00", "title": "Vakarienė (Po treniruotės)", "meal": dinner})

        # Susumuojame dienos makrokomponentus
        day_cals = sum(m["meal"]["cals"] for m in day_meals if "meal" in m)
        day_p = sum(m["meal"]["protein"] for m in day_meals if "meal" in m)
        day_f = sum(m["meal"]["fats"] for m in day_meals if "meal" in m)
        day_c = sum(m["meal"]["carbs"] for m in day_meals if "meal" in m)

        # Agreguojame ingredientus pirkinių krepšeliui
        for m in day_meals:
            if "meal" in m:
                for ing in m["meal"]["ingredients"]:
                    name = ing["name"]
                    amt = ing["amount"]
                    unit = ing["unit"]
                    search = ing.get("barbora_search", name)
                    
                    if name in aggregated_ingredients:
                        aggregated_ingredients[name]["total_amount"] += amt
                    else:
                        aggregated_ingredients[name] = {
                            "name": name,
                            "total_amount": amt,
                            "unit": unit,
                            "barbora_search": search
                        }

        daily_plans.append({
            "day_number": d,
            "day_title": f"{d} Diena",
            "total_calories": day_cals,
            "protein": day_p,
            "fats": day_f,
            "carbs": day_c,
            "meals": day_meals
        })

    # Paruošiame pirkinių sąrašo tekstą
    shopping_list = []
    for ing in aggregated_ingredients.values():
        shopping_list.append({
            "name": ing["name"],
            "amount_str": f"{round(ing['total_amount'], 1)} {ing['unit']}",
            "search_term": ing["barbora_search"],
            "raw_text": f"{ing['barbora_search']} ({round(ing['total_amount'], 1)} {ing['unit']})"
        })

    return {
        "success": True,
        "days_count": days,
        "client_name": profile.get("name", "Vartotojas"),
        "target_calories": target_cals,
        "daily_plans": daily_plans,
        "shopping_list": shopping_list
    }

if __name__ == "__main__":
    import database
    prof = database.get_client_profile()
    meta = calculate_metabolics(prof)
    print("Metabolika:", meta)
    plan = generate_meal_plan(days=3, profile=prof)
    print("Sugeneruotas planas 3 dienoms:", len(plan["daily_plans"]), "dienos")
    print("Pirkinių sąrašas ingredientų:", len(plan["shopping_list"]))
