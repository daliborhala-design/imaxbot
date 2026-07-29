import os
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

# Bezpečný import stealth
try:
    from playwright_stealth import stealth as stealth_func
except ImportError:
    stealth_func = None

# --- KONFIGURACE ---
URL = "https://www.cinemacity.cz/cinemas/flora/1052#/buy-tickets-by-cinema?in-cinema=1052&at=2026-08-12&for-movie=7268s2r&view-mode=list"
EMAIL_RECIPIENT = "dalibor.hala@gmail.com"
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

def send_email(found_slots):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("CHYBA: Chybí e-mailové přihlašovací údaje v Secrets!")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECIPIENT
    msg['Subject'] = "VSTUPENKY IMAX 70mm: Odyssea"

    body = "Byly nalezeny volné vstupenky (3 vedle sebe v jedné řadě):\n\n"
    body += "\n".join(found_slots)
    body += f"\n\nOdkaz na web: {URL}"
    
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

def check_tickets():
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="cs-CZ"
        )
        page = context.new_page()

        # Aplikujeme stealth, pokud je k dispozici
        if stealth_func:
            try:
                stealth_func(page)
            except:
                pass

        print(f"Otevírám hlavní stránku: {URL}")
        try:
            page.goto(URL, wait_until="networkidle", timeout=60000)
            time.sleep(5)
            
            # Zavření cookies
            try:
                page.click("#onetrust-accept-btn-handler", timeout=5000)
            except:
                pass

            # Kontrola dostupných představení
            showtime_selector = ".qb-movie-info-column a.btn-primary:not(.disabled)"
            try:
                page.wait_for_selector(showtime_selector, timeout=15000)
            except:
                print("Na stránce nejsou žádná aktivní představení (časy).")
                return []

            showtimes_count = page.locator(showtime_selector).count()
            print(f"Nalezeno aktivních časů: {showtimes_count}")

            for i in range(showtimes_count):
                btn = page.locator(showtime_selector).nth(i)
                time_text = btn.inner_text().strip()
                print(f"Prověřuji čas: {time_text}")
                
                # Klik na čas (otevře se v novém tabu nebo v aktuálním)
                btn.click()
                time.sleep(3)
                
                # Tlačítko Host
                try:
                    guest_btn = "button#guest-btn, button:has-text('host'), button:has-text('Host'), button:has-text('POKRAČOVAT JAKO HOST')"
                    if page.locator(guest_btn).is_visible():
                        page.click(guest_btn)
                        time.sleep(3)
                except:
                    pass

                # Analýza sedadel
                try:
                    # Počkáme na mapu sedadel (buď SVG rect nebo divy)
                    page.wait_for_selector(".seat-container, .seating-chart, rect.seat-available, .seat-row", timeout=20000)
                    time.sleep(4) 

                    # Najdeme všechny řady sedadel
                    rows = page.locator(".seat-row").all()
                    # Pokud nejsou řady přes .seat-row, zkusíme najít SVG strukturu
                    if not rows:
                        # Fallback pro kina používající SVG recty
                        all_available = page.locator("rect.seat-available, .seat.available").count()
                        if all_available >= 3:
                            results.append(f"Čas {time_text}: nalezeno {all_available} volných míst celkem (zkontroluj řady manuálně).")
                    else:
                        for row in rows:
                            # Hledáme všechna sedadla v řadě
                            seats_in_row = row.locator(".seat, rect").all()
                            consecutive = 0
                            for seat in seats_in_row:
                                class_attr = seat.get_attribute("class") or ""
                                # Pokud je sedadlo volné (available)
                                if "available" in class_attr.lower():
                                    consecutive += 1
                                    if consecutive >= 3:
                                        results.append(f"Čas {time_text}: nalezeny 3 vstupenky v jedné řadě.")
                                        break
                                else:
                                    consecutive = 0
                            if consecutive >= 3: break
                    
                    print(f"Čas {time_text}: hotovo.")

                except Exception as e:
                    print(f"Chyba při kontrole sedadel pro čas {time_text}")

                # Zpět na seznam
                page.goto(URL, wait_until="networkidle")
                time.sleep(3)

        except Exception as e:
            print(f"Nastala chyba: {e}")
        
        browser.close()
    return results

if __name__ == "__main__":
    found_tickets = check_tickets()
    if found_tickets:
        print("Nalezeny výsledky, odesílám e-mail.")
        send_email(found_slots=found_tickets)
    else:
        print("Žádné volné vstupenky nebyly nalezeny.")
