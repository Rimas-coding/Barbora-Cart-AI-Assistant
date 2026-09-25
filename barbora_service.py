import asyncio
import os
import sys
import logging
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright, BrowserContext, Page

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BarboraService")

PROFILE_DIR = os.path.join(os.path.dirname(__file__), "chrome_user_data")

class BarboraService:
    def __init__(self):
        self.profile_dir = PROFILE_DIR
        os.makedirs(self.profile_dir, exist_ok=True)
        self.active_context: Optional[BrowserContext] = None
        self.playwright_instance = None
        self._lock = asyncio.Lock()

    async def get_context(self, headless: bool = False) -> BrowserContext:
        """Grąžina arba sukuria naršyklės kontekstą su išsaugotu Chrome profiliu"""
        if self.playwright_instance is None:
            self.playwright_instance = await async_playwright().start()

        if self.active_context is None:
            self.active_context = await self.playwright_instance.chromium.launch_persistent_context(
                user_data_dir=self.profile_dir,
                channel="chrome",
                headless=headless,
                no_viewport=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-infobars",
                    "--no-default-browser-check",
                    "--window-size=1280,950"
                ],
                locale="lt-LT"
            )
        return self.active_context

    async def close_browser(self):
        """Uždaro aktyvią naršyklę ir atlaisvina resursus"""
        async with self._lock:
            if self.active_context:
                try:
                    await self.active_context.close()
                except Exception as e:
                    logger.warning(f"Klaida uždarant kontekstą: {e}")
                self.active_context = None

            if self.playwright_instance:
                try:
                    await self.playwright_instance.stop()
                except Exception as e:
                    logger.warning(f"Klaida stabdant playwright: {e}")
                self.playwright_instance = None

    async def open_login_window(self) -> Dict[str, Any]:
        """Atveria matomą Chrome langą vartotojo prisijungimui prie Barbora.lt"""
        async with self._lock:
            await self.close_browser()
            context = await self.get_context(headless=False)
            page = context.pages[0] if context.pages else await context.new_page()
            
            logger.info("Atidaromas Barbora.lt prisijungimo langas...")
            await page.goto("https://barbora.lt/", wait_until="domcontentloaded", timeout=45000)
            
            # Patikrinam ar jau prisijungęs
            status = await self._check_page_logged_in(page)
            return {
                "success": True,
                "message": "Naršyklės langas atidarytas. Prisijunkite prie Barbora.lt savo paskyroje.",
                "is_logged_in": status
            }

    async def check_login_status(self) -> Dict[str, Any]:
        """Patikrina ar profilyje yra išsaugota aktyvi Barbora.lt sesija"""
        async with self._lock:
            # Paleidžiame laikinai headless arba atvirą langą
            context = await self.get_context(headless=False)
            page = context.pages[0] if context.pages else await context.new_page()
            try:
                await page.goto("https://barbora.lt/", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)
                is_logged_in = await self._check_page_logged_in(page)
                user_email = ""
                if is_logged_in:
                    user_email = await page.evaluate("""() => {
                        const el = document.querySelector('[data-testid="header-user-email"], [class*="user-name"], [class*="user-email"]');
                        return el ? el.innerText.trim() : "Prisijungęs vartotojas";
                    }""")
                return {
                    "is_logged_in": is_logged_in,
                    "user_info": user_email if is_logged_in else "Neprisijungta"
                }
            except Exception as e:
                logger.error(f"Klaida tikrinant prisijungimo būseną: {e}")
                return {"is_logged_in": False, "error": str(e)}

    async def _check_page_logged_in(self, page: Page) -> bool:
        """Vidinė funkcija patikrinti ar puslapyje matomas prisijungusio vartotojo statusas"""
        try:
            # Jei yra mygtukas „Prisijungti arba registruotis“, vartotojas neprisijungęs
            content = await page.content()
            if "Prisijungti arba registruotis" in content or "Norėdamas apsipirkti, prisijunk" in content:
                # Patikrinkime ar nėra vartotojo meniu
                has_user_menu = await page.evaluate("""() => {
                    const profileLink = document.querySelector('a[href*="/mano-paskyra"], [data-testid="user-profile"], button[aria-label*="Mano paskyra"]');
                    return !!profileLink;
                }""")
                return has_user_menu
            return True
        except Exception:
            return False

    async def scrape_product_info(self, url: str) -> Dict[str, Any]:
        """Nuskaito produkto pavadinimą, kainą ir vienetą iš Barbora.lt nuorodos"""
        async with self._lock:
            context = await self.get_context(headless=False)
            page = context.pages[0] if context.pages else await context.new_page()
            try:
                logger.info(f"Nuskaitoma prekės informacija: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=40000)
                await asyncio.sleep(2)

                details = await page.evaluate("""() => {
                    // Pavadinimas
                    const h1 = document.querySelector('h1')?.innerText?.trim() || "";
                    
                    // Kaina
                    let price = 0.0;
                    const priceContainer = document.querySelector('.b-product-prices, [class*="price-main"], [class*="price"]');
                    const priceMatch = (document.body.innerText || "").match(/(\\d+)[.,](\\d{2})\\s*€/);
                    if (priceMatch) {
                        price = parseFloat(priceMatch[1] + "." + priceMatch[2]);
                    }

                    // Mygtukas į krepšelį
                    const hasAddToCart = Array.from(document.querySelectorAll('button')).some(b => b.innerText.includes('Į krepšelį'));
                    
                    // Vienetas
                    let unit = "vnt";
                    if (h1.toLowerCase().includes(" kg") || h1.toLowerCase().endsWith("kg")) {
                        unit = "kg";
                    }

                    return {
                        title: h1,
                        price: price,
                        unit: unit,
                        is_available: hasAddToCart
                    };
                }""")

                if not details["title"]:
                    # Bandome alternatyvų pavadinimo išgavimą iš URL
                    slug = url.rstrip("/").split("/")[-1]
                    details["title"] = slug.replace("-", " ").capitalize()

                return {
                    "success": True,
                    "url": url,
                    "name": details["title"],
                    "price": details["price"],
                    "unit": details["unit"],
                    "is_available": details["is_available"]
                }
            except Exception as e:
                logger.error(f"Klaida nuskaitant prekę {url}: {e}")
                return {
                    "success": False,
                    "url": url,
                    "error": str(e)
                }

    async def add_products_to_cart(self, items: List[Dict[str, Any]], progress_callback=None) -> Dict[str, Any]:
        """
        Surenka krepšelį Barboroje.
        items: [{"url": "...", "name": "...", "quantity": 1}, ...]
        """
        async with self._lock:
            context = await self.get_context(headless=False)
            page = context.pages[0] if context.pages else await context.new_page()
            
            results = []
            total_added = 0
            estimated_price = 0.0

            try:
                for idx, item in enumerate(items):
                    url = item.get("url")
                    name = item.get("name", "Nežinoma prekė")
                    qty = item.get("quantity", 1)

                    if not url:
                        results.append({
                            "name": name,
                            "status": "error",
                            "message": "Nėra Barbora nuorodos (reikia įvesti ranka)"
                        })
                        continue

                    if progress_callback:
                        await progress_callback(f"Apdorojama ({idx+1}/{len(items)}): {name}...")

                    logger.info(f"Dedama į krepšelį: {name} (Kiekis: {qty}) iš {url}")
                    
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=40000)
                        await asyncio.sleep(2)

                        # Ieškome mygtuko „Į krepšelį“
                        add_btn = page.locator("button:has-text('Į krepšelį')").first
                        is_visible = await add_btn.is_visible(timeout=5000)

                        if not is_visible:
                            # Galbūt prekė jau yra krepšelyje (yra pliuso/minuso valdiklis)
                            qty_plus = page.locator("button[aria-label*='Padidinti'], button:has-text('+')").first
                            if await qty_plus.is_visible(timeout=2000):
                                logger.info(f"Prekė {name} jau yra krepšelyje. Didinamas kiekis.")
                                for _ in range(max(0, qty - 1)):
                                    await qty_plus.click()
                                    await asyncio.sleep(0.5)
                                results.append({
                                    "name": name,
                                    "status": "success",
                                    "message": f"Prekė jau buvo krepšelyje. Kiekis atnaujintas į {qty}.",
                                    "url": url
                                })
                                total_added += 1
                                continue
                            else:
                                results.append({
                                    "name": name,
                                    "status": "out_of_stock",
                                    "message": "Prekė šiuo metu neprieinama arba neturi mygtuko „Į krepšelį“.",
                                    "url": url
                                })
                                continue

                        # Spaudžiame „Į krepšelį“
                        await add_btn.scroll_into_view_if_needed()
                        await add_btn.click()
                        await asyncio.sleep(1.5)

                        # Jei reikalingas kiekis > 1, spaudžiame pliuso mygtuką
                        if qty > 1:
                            qty_plus = page.locator("button[aria-label*='Padidinti'], button:has-text('+')").first
                            for _ in range(qty - 1):
                                if await qty_plus.is_visible(timeout=2000):
                                    await qty_plus.click()
                                    await asyncio.sleep(0.5)

                        # Ištraukiame prekės kainą patvirtinimui
                        price_val = 0.0
                        price_match = (await page.content())
                        # bandom surasti kainą
                        import re
                        m = re.search(r'(\d+)[.,](\d{2})\s*€', price_match)
                        if m:
                            price_val = float(f"{m.group(1)}.{m.group(2)}")
                            estimated_price += price_val * qty

                        results.append({
                            "name": name,
                            "status": "success",
                            "message": f"Sėkmingai pridėta į krepšelį ({qty} vnt/kg).",
                            "price": price_val,
                            "url": url
                        })
                        total_added += 1

                    except Exception as item_err:
                        logger.error(f"Klaida dedant {name}: {item_err}")
                        results.append({
                            "name": name,
                            "status": "error",
                            "message": f"Klaida: {str(item_err)}",
                            "url": url
                        })

                if progress_callback:
                    await progress_callback(f"Krepšelio surinkimas baigtas! Pridėta {total_added} iš {len(items)} prekių.")

                return {
                    "success": True,
                    "total_items": len(items),
                    "total_added": total_added,
                    "estimated_total_price": round(estimated_price, 2),
                    "items": results
                }

            except Exception as e:
                logger.error(f"Kritinė klaida renkant krepšelį: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "items": results
                }

barbora_service = BarboraService()
