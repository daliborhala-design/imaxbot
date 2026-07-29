import os
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth  # Opravený import

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
        stealth(page) # Opravené volání funkce stealth

        print(f"Otevírám hlavní stránku: {URL}")
        try:
            page.goto(URL, wait_until="networkidle", timeout=60000)
            time.sleep(5)
            
            # Zavření cookies
            try:
                page.click("#onetrust-accept-btn-handler", timeout=5000)
            except:
                pass

            # Kontrola, zda jsou k dispozici nějaké časy
            showtime_selector = ".qb-movie-info-column a.btn-primary:not(.disabled)"
            
            # Počkáme, zda se objeví aspoň jedno tlačítko
            try:
                page.wait_for_selector(showtime_selector, timeout=15000)
            except:
                print("Na stránce nebyla nalezena žádná dostupná představení (časy).")
                return []

            showtimes_count = page.locator(showtime_selector).count()
            print(f"Nalezeno aktivních časů: {showtimes_count}")

            for i in range(showtimes_count):
                # Pokaždé musíme locator definovat znovu
                btn = page.locator(showtime_selector).nth(i)
                time_text = btn.inner_text().strip()
                
                print(f"Prověřuji čas: {time_text}")
                
                # Klikneme na čas
                btn.click()
                
                # Počkáme na tlačítko "Pokračovat jako host"
                try:
                    guest_btn = "button#guest-btn, button:has-text('host'), button:has-text('Host'), button:has-text('POKRAČOVAT JAKO HOST')"
                    page.wait_for_selector(guest_btn, timeout=10000)
                    page.click(guest_btn)
                except:
                    pass

                # Počkáme na mapu sedadel
                try:
                    page.wait_for_selector(".seat-container, .seating-chart, rect.seat-available", timeout=20000)
                    time.sleep(4) 

                    # Najdeme všechny řady
                    rows = page.locator(".seat-row").all()
                    found_in_this_time = False
                    
                    for row in rows:
                        seats_in_row = row.locator(".seat").all()
                        consecutive = 0
                        for seat in seats_in_row:
                            class_attr = seat.get_attribute("class") or ""
                            # Hledáme sedadla, která mají třídu 'seat-available'
                            if "seat-available" in class_attr:
                                consecutive += 1
                                if consecutive >= 3:
                                    results.append(f"Čas {time_text}: nalezeny 3 vstupenky v jedné řadě.")
                                    found_in_this_time = True
                                    break
                            else:
                                consecutive = 0
                        if found_in_this_time:
                            break
                    
                    print(f"Čas {time_text}: {'NALEZENO!' if found_in_this_time else 'Plno nebo málo míst.'}")

                except Exception as e:
                    print(f"Chyba při kontrole sedadel pro čas {time_text}")

                # Vrátíme se na seznam představení
                page.goto(URL, wait_until="networkidle")
                time.sleep(3)

        except Exception as e:
            print(f"Nastala chyba: {e}")
        
        browser.close()
    return results

if __name__ == "__main__":
    found_tickets = check_tickets()
    if found_tickets:
        print("Vstupenky nalezeny! Posílám e-mail.")
        send_email(found_tickets)
    else:
        print("Konec kontroly: Žádné vyhovující lístky nenalezeny.")
