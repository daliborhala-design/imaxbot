import os
import time
import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

# --- KONFIGURACE ---
MOVIE_ID = "7268s2r" # ID filmu Odyssea
CINEMA_ID = "1052"   # ID kina Flora
EMAIL_RECIPIENT = "dalibor.hala@gmail.com"
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

# Dynamické nastavení: začínáme DNES a kontrolujeme 14 dní dopředu
START_DATE = datetime.date.today() 
DAYS_TO_CHECK = 20   

def apply_stealth_safely(page):
    """Bezpečné aplikování stealth režimu bez pádu skriptu"""
    try:
        import playwright_stealth
        playwright_stealth.stealth(page)
    except Exception as e:
        print(f"Stealth režim nebyl aplikován: {e}")

def send_email(found_slots):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("CHYBA: Chybí e-mailové přihlašovací údaje v Secrets!")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECIPIENT
    msg['Subject'] = "VSTUPENKY IMAX 70mm: Odyssea - NALEZENO"

    body = f"Ahoj, bot našel volné vstupenky (3 vedle sebe) v období od {START_DATE} do {START_DATE + datetime.timedelta(days=DAYS_TO_CHECK-1)}:\n\n"
    body += "\n".join(found_slots)
    body += f"\n\nRezervuj zde: https://www.cinemacity.cz/cinemas/flora/{CINEMA_ID}#/buy-tickets-by-cinema?in-cinema={CINEMA_ID}&view-mode=list"
    
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("E-mail byl úspěšně odeslán.")
    except Exception as e:
        print(f"CHYBA při odesílání e-mailu: {e}")

def check_tickets_for_date(page, check_date):
    day_str = check_date.strftime("%Y-%m-%d")
    url = f"https://www.cinemacity.cz/cinemas/flora/{CINEMA_ID}#/buy-tickets-by-cinema?in-cinema={CINEMA_ID}&at={day_str}&for-movie={MOVIE_ID}&view-mode=list"
    
    daily_results = []
    print(f"Prověřuji: {day_str}")
    
    try:
        # Přejdeme na stránku, čekáme na načtení sítě
        page.goto(url, wait_until="networkidle", timeout=60000)
        time.sleep(4) # Rezerva na dojetí skriptů Cinema City
        
        # Selektor pro aktivní časy (tlačítka)
        showtime_selector = ".qb-movie-info-column a.btn-primary:not(.disabled)"
        count = page.locator(showtime_selector).count()
        
        if count == 0:
            return [] # Ten den se nehraje nebo nejsou lístky

        for i in range(count):
            btn = page.locator(showtime_selector).nth(i)
            time_text = btn.inner_text().strip()
            
            # Klik na nákup
            btn.click()
            time.sleep(4)
            
            # Pokus o přeskočení přihlášení (Koupit jako host)
            guest_btn = "button#guest-btn, button:has-text('host'), button:has-text('Host'), button:has-text('POKRAČOVAT JAKO HOST')"
            try:
                if page.locator(guest_btn).is_visible(timeout=5000):
                    page.click(guest_btn)
                    time_sleep(4)
            except:
                pass

            # Kontrola sedadel (mapa)
            try:
                page.wait_for_selector(".seat-container, .seating-chart, rect.seat-available, .seat-row", timeout=15000)
                time.sleep(2)
                
                rows = page.locator(".seat-row").all()
                found_match = False
                
                if not rows:
                    # Fallback pro SVG zobrazení
                    available_count = page.locator("rect.seat-available, .seat.available").count()
                    if available_count >= 3:
                        daily_results.append(f"{day_str} v {time_text} (nalezeno celkem {available_count} volných míst)")
                else:
                    for row in rows:
                        seats = row.locator(".seat, rect").all()
                        consecutive = 0
                        for seat in seats:
                            cls = seat.get_attribute("class") or ""
                            if "available" in cls.lower():
                                consecutive += 1
                                if consecutive >= 3:
                                    daily_results.append(f"{day_str} v {time_text}")
                                    found_match = True
                                    break
                            else:
                                consecutive = 0
                        if found_match: break
            except:
                print(f"Nepodařilo se analyzovat sedadla pro čas {time_text}")

            # Vrátíme se zpět na seznam dne pro další čas
            page.goto(url, wait_until="networkidle")
            time.sleep(2)
            
    except Exception as e:
        print(f"Chyba při zpracování data {day_str}: {e}")
        
    return daily_results

def main():
    all_found_slots = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="cs-CZ"
        )
        page = context.new_page()
        
        apply_stealth_safely(page)

        print(f"--- START KONTROLY (14 dní od {START_DATE}) ---")
        
        for i in range(DAYS_TO_CHECK):
            current_date = START_DATE + datetime.timedelta(days=i)
            res = check_tickets_for_date(page, current_date)
            all_found_slots.extend(res)
            
        browser.close()

    if all_found_slots:
        print(f"ÚSPĚCH: Nalezeno {len(all_found_slots)} termínů.")
        send_email(all_found_slots)
    else:
        print("KONTROLA DOKONČENA: Žádné volné lístky nenalezeny.")

if __name__ == "__main__":
    main()
