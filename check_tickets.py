import os
import time
import smtplib
import datetime
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

# --- KONFIGURACE ---
MOVIE_ID = "7268s2r"
CINEMA_ID = "1052"
EMAIL_RECIPIENT = "dalibor.hala@gmail.com"
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
DAYS_TO_CHECK = 14

def send_email(found_slots, start_date, end_date, error_log=None):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("CHYBA: Chybí e-mailové přihlašovací údaje v Secrets!")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECIPIENT
    
    timestamp = datetime.datetime.now().strftime("%H:%M")
    if found_slots:
        msg['Subject'] = f"🚀 NALEZENO: IMAX Odyssea ({timestamp})"
        body = f"Bot našel volná místa v období {start_date} až {end_date}:\n\n"
        body += "\n".join(found_slots)
    else:
        status = "⚠️ CHYBA" if error_log else "✅ OK"
        msg['Subject'] = f"{status}: IMAX Kontrola ({timestamp})"
        body = f"Kontrola období: {start_date} - {end_date}\nStav: Žádná volná místa (3 v řadě) nenalezena.\n"

    if error_log:
        body += f"\n\n--- LOG CHYB ---\n{error_log}"

    msg.attach(MIMEText(body, 'plain'))
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("E-mail odeslán.")
    except Exception as e:
        print(f"Selhalo odeslání e-mailu: {e}")

def check_tickets_for_date(page, check_date):
    day_str = check_date.strftime("%Y-%m-%d")
    url = f"https://www.cinemacity.cz/cinemas/flora/{CINEMA_ID}#/buy-tickets-by-cinema?in-cinema={CINEMA_ID}&at={day_str}&for-movie={MOVIE_ID}&view-mode=list"
    daily_results = []

    print(f"Prověřuji: {day_str}")
    page.goto(url, wait_until="load", timeout=60000)
    time.sleep(3)

    # 1. ODSTRANĚNÍ COOKIE LIŠTY (překáží v klikání)
    try:
        cookie_btn = page.locator("#onetrust-accept-btn-handler")
        if cookie_btn.is_visible():
            cookie_btn.click()
            time.sleep(1)
    except: pass

    showtime_selector = ".qb-movie-info-column a.btn-primary:not(.disabled)"
    try:
        page.wait_for_selector(showtime_selector, timeout=10000)
        count = page.locator(showtime_selector).count()
    except:
        return []

    for i in range(count):
        try:
            btn = page.locator(showtime_selector).nth(i)
            time_val = btn.inner_text().strip()
            
            # Používáme force=True, aby kliknul i přes případné neviditelné vrstvy
            btn.click(force=True)
            time.sleep(4)

            # 2. OŠETŘENÍ MODÁLNÍHO OKNA (Přihlášení / Host)
            guest_btn_selector = "button#guest-btn, button:has-text('host'), .btn-secondary:has-text('POKRAČOVAT')"
            try:
                # Pokud okno vyskočilo, klikneme na hosta
                guest_btn = page.locator(guest_btn_selector)
                if guest_btn.is_visible(timeout=5000):
                    guest_btn.click(force=True)
                    time.sleep(4)
            except: pass

            # 3. ANALÝZA SEDADEL
            page.wait_for_selector(".seat-container, rect.seat-available, .seat-row", timeout=15000)
            
            rows = page.locator(".seat-row").all()
            found_in_time = False
            if not rows:
                if page.locator("rect.seat-available").count() >= 3:
                    daily_results.append(f"{day_str} v {time_val} (nalezeno v SVG mapě)")
            else:
                for row in rows:
                    # Hledáme řadu, která má aspoň 3 dostupné elementy
                    available_seats = row.locator(".seat-available, .seat.available").count()
                    if available_count >= 3:
                        daily_results.append(f"{day_str} v {time_val}")
                        break
            
            # Návrat zpět na seznam
            page.goto(url, wait_until="load")
            time.sleep(2)
        except Exception as e:
            print(f"Chyba u času v {day_str}: {str(e)[:100]}")
            page.goto(url, wait_until="load")

    return daily_results

def main():
    start_date = datetime.date.today()
    end_date = start_date + datetime.timedelta(days=DAYS_TO_CHECK-1)
    all_results = []
    full_error_log = ""

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={'width': 1280, 'height': 1024})
            page = context.new_page()
            
            for i in range(DAYS_TO_CHECK):
                current_date = start_date + datetime.timedelta(days=i)
                try:
                    res = check_tickets_for_date(page, current_date)
                    all_results.extend(res)
                except Exception as e:
                    full_error_log += f"\nChyba dne {current_date}: {str(e)}"
            
            browser.close()
    except Exception:
        full_error_log += f"\nKritická chyba: {traceback.format_exc()}"
    
    # E-mail se pošle vždy díky tomu, že je mimo hlavní try blok prohlížeče
    send_email(all_results, start_date, end_date, full_error_log if full_error_log else None)

if __name__ == "__main__":
    main()
