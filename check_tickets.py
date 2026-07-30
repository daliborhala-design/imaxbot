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

def send_email(found_slots, start_date, end_date, error_msg=None):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("CHYBA: Chybí e-mailové přihlašovací údaje!")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECIPIENT
    
    status_prefix = "⚠️ CHYBA" if error_msg else "✅ OK"
    if found_slots:
        msg['Subject'] = f"🚀 NALEZENO: IMAX Odyssea ({start_date})"
        body = f"Bot našel volné vstupenky (3 vedle sebe) v období {start_date} až {end_date}:\n\n"
        body += "\n".join(found_slots)
        body += f"\n\nRezervace: https://www.cinemacity.cz/cinemas/flora/{CINEMA_ID}#/buy-tickets-by-cinema?in-cinema={CINEMA_ID}&view-mode=list"
    else:
        msg['Subject'] = f"{status_prefix}: IMAX Kontrola ({datetime.datetime.now().strftime('%H:%M')})"
        body = f"Kontrola období: {start_date} - {end_date}\n"
        body += "Stav: Žádná volná místa (3 v řadě) nenalezena.\n"
    
    if error_msg:
        body += f"\n\nUpozornění: Během kontroly došlo k chybě, výsledky nemusí být kompletní:\n{error_msg}"

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("E-mail byl odeslán.")
    except Exception as e:
        print(f"E-mail se nepodařilo odeslat: {e}")

def check_tickets_for_date(page, check_date):
    day_str = check_date.strftime("%Y-%m-%d")
    url = f"https://www.cinemacity.cz/cinemas/flora/{CINEMA_ID}#/buy-tickets-by-cinema?in-cinema={CINEMA_ID}&at={day_str}&for-movie={MOVIE_ID}&view-mode=list"
    daily_results = []
    
    print(f"Prověřuji: {day_str}")
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    time.sleep(3)
    
    showtime_selector = ".qb-movie-info-column a.btn-primary:not(.disabled)"
    count = page.locator(showtime_selector).count()
    
    for i in range(min(count, 5)): # Kontrolujeme max 5 časů denně pro stabilitu
        btn = page.locator(showtime_selector).nth(i)
        time_text = btn.inner_text().strip()
        btn.click()
        time.sleep(3)
        
        # Přeskočení hosta
        try:
            guest_btn = "button#guest-btn, button:has-text('host'), button:has-text('Host')"
            if page.locator(guest_btn).is_visible(timeout=3000):
                page.click(guest_btn)
                time.sleep(3)
        except: pass

        # Kontrola sedadel
        try:
            page.wait_for_selector(".seat-row, rect.seat-available", timeout=10000)
            rows = page.locator(".seat-row").all()
            if not rows:
                if page.locator("rect.seat-available").count() >= 3:
                    daily_results.append(f"{day_str} v {time_text} (volná místa v SVG)")
            else:
                for row in rows:
                    if "available" in (row.inner_html() or "").lower():
                        # Zjednodušená detekce pro rychlost
                        seats = row.locator(".seat.available, .seat-available").count()
                        if seats >= 3:
                            daily_results.append(f"{day_str} v {time_text}")
                            break
        except: pass
        
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(2)
        
    return daily_results

def main():
    start_date = datetime.date.today()
    end_date = start_date + datetime.timedelta(days=DAYS_TO_CHECK-1)
    all_found_slots = []
    error_info = None

    browser_context = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0")
            page = context.new_page()
            
            for i in range(DAYS_TO_CHECK):
                current_date = start_date + datetime.timedelta(days=i)
                all_found_slots.extend(check_tickets_for_date(page, current_date))
            
            browser.close()
    except Exception:
        error_info = traceback.format_exc()
        print(f"Nastala chyba: {error_info}")
    finally:
        # TOTO SE SPUSTÍ VŽDY
        send_email(all_found_slots, start_date, end_date, error_info)

if __name__ == "__main__":
    main()
