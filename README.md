<div align="center">
  <img src="icon.png" width="110" alt="Barbora AI Ikona" style="border-radius: 24px;" />
  <h1>🛒 Barbora Krepšelio & Mitybos AI Asistentas</h1>
  <p><b>Automatizuota mitybos planavimo ir prekių krepšelio surinkimo sistema el. parduotuvei Barbora.lt</b></p>
</div>

Sistema sujungia du funkcinius modulius:
1. **🥗 Asmeninio mitybos planavimo modulis**: atlieka vartotojo anamnezę, apskaičiuoja metabolinius rodiklius (BMR, TDEE, KMI), pateikia lanksčiai redaguojamą mitybos gairių lentelę ir generuoja subalansuotus dienos, kelių dienų ar savaitės mitybos planus.
2. **🛒 Automatizuotas pirkinių krepšelio robotas**: analizuoja mitybos plano ingredientus, apjungia kiekius, suderina su prekių katalogu ir per naršyklės automatizaciją (`Playwright`) surenka krepšelį Barbora.lt parduotuvėje.

---

## 🌟 Pagrindinės funkcijos

- **Kliento anamnezė ir poreikių profilis**:
  - Lytis, amžius, ūgis, svoris, kūno riebalų %, fizinio aktyvumo lygis, sporto dažnis bei treniruočių laikas paros metu.
  - Tikslai: svorio metimas (kalorijų deficitas), raumenų masės auginimas, ištvermė, palaikymas.
  - Rizikų vertinimas (perspėjimai dėl per didelio deficito, KMI kraštutinumų, hidratacijos normos).
- **Lanksčios mitybos gairės**:
  - Greitas kalorijų parinkimas (-20% deficitas, palaikymas, +12% perteklius).
  - Dienos valgymų skaičiaus nustatymas (3, 4 arba 5 valgymai).
  - Makroelementų (baltymų, riebalų, angliavandenių) gramų ir santykio kontrolė.
- **Mitybos planų generavimas**:
  - 1 dienos (greitas planas šiandienai), 3 dienų (Meal-Prep dėžutėms) arba 7 dienų (visai savaitei).
  - Valgymų pritaikymas pagal treniruočių laiką (prieš treniruotę, treniruotė, atsistatymas po treniruotės).
- **Pirkinių sąrašo suderinimas ir Barbora integracija**:
  - Ingredientų agregavimas ir dublikatų sujungimas.
  - Prekių atpažinimas SQLite duomenų bazėje su lietuviškų žodžių šaknų morfologiniu suderinimu.
  - Galimybė tiesiogiai Web UI įvesti trūkstamų produktų Barbora.lt nuorodas ir išsaugoti į bazę.
  - Automatinis krepšelio pildymas naudojant išsaugotą vietinę Chrome sesiją (nereikia kaskart jungtis iš naujo).

---

## 🛠️ Technologijų stekas

- **Backend**: Python 3.10+, FastAPI, Uvicorn, Pydantic
- **Naršyklės automatizacija**: Playwright (Chromium)
- **Duomenų bazė**: SQLite3
- **Frontend**: HTML5, Tailwind CSS, JavaScript (Vanilla ES6+)

---

## 🚀 Diegimas ir paleidimas

### 1. Reikalavimai
- Įdiegtas [Python 3.10](https://www.python.org/downloads/) arba naujesnė versija.
- Įdiegta Google Chrome naršyklė.

### 2. Repozitorijos klonavimas
```bash
git clone https://github.com/Rimas-coding/barbora-cart-ai-assistant.git
cd barbora-cart-ai-assistant
```

### 3. Priklausomybių diegimas
Rekomenduojama susikurti virtualią aplinką:
```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# Linux / macOS:
source venv/bin/activate

# Įdiegiame reikalingus paketus:
pip install -r requirements.txt

# Įdiegiame naršyklės tvarkykles:
playwright install chromium
```

### 4. Programos paleidimas

#### „Windows“ aplinkoje:
Dukart spustelėkite failą **`paleisti.bat`**.

#### Per terminalą (bet kurioje OS):
```bash
python run.py
```

Sistema automatiškai atvers vartotojo sąsają naršyklėje:
👉 **`http://localhost:8000`**

Interaktyvi Swagger API dokumentacija:
👉 **`http://localhost:8000/docs`**

---

## 🔒 Privatumas ir saugumas

- **Prisijungimo duomenys**: Programa nerenka ir nesiunčia jokių jūsų Barbora slaptažodžių. 
- **Vietinis profilis**: Prisijungimas atliekamas tiesiogiai oficialioje `barbora.lt` svetainėje per atskirą vietinį naršyklės profilį (`chrome_user_data/`), kuris saugomas tik jūsų kompiuteryje ir pagal `.gitignore` taisykles **niekada nekeliamas į GitHub**.
- **Duomenų bazė**: Visi jūsų asmeniniai mitybos nustatymai, patiekalai ir pirkinių sąrašai saugomi lokaliame `barbora_products.db` faile.

---

## 📡 REST API pabaigos taškai (Endpoints)

| Metodas | Endpoint | Aprašymas |
|---|---|---|
| `GET` | `/api/nutrition/profile` | Gauti kliento anketos duomenis |
| `POST` | `/api/nutrition/profile` | Išsaugoti/atnaujinti kliento anketą |
| `GET` | `/api/nutrition/guidelines` | Gauti mitybos gairių lentelę |
| `POST` | `/api/nutrition/guidelines` | Atnaujinti mitybos gaires |
| `POST` | `/api/nutrition/plan` | Sugeneruoti mitybos planą (`days: 1, 3, 7`) |
| `POST` | `/api/nutrition/plan-to-cart` | Perkelti plano ingredientus į pirkinių suderinimą |
| `GET` | `/api/products` | Gauti visų išsaugotų prekių sąrašą |
| `POST` | `/api/products` | Pridėti naują prekę į katalogą |
| `POST` | `/api/products/scrape` | Nuskaityti prekės pavadinimą ir kainą iš Barbora URL |
| `POST` | `/api/cart/combine` | Apjungti kelis sąrašus su kiekių sumavimu |
| `POST` | `/api/cart/resolve` | Suderinti pirkinių sąrašą su esama duomenų baze |
| `POST` | `/api/cart/build` | Paleisti automatinį krepšelio surinkimo robotą |
| `GET` | `/api/cart/status` | Krepšelio surinkimo eigos stebėjimas realiu laiku |
| `POST` | `/api/browser/open-login` | Atidaryti naršyklę rankiniam prisijungimui prie Barbora |

---

## 📄 Licencija

Šis projektas platinamas pagal **MIT** licenciją. Daugiau informacijos rasite [LICENSE](LICENSE) faile.
