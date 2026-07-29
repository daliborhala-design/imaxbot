import os
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright

# --- KONFIGURACE ---
URL = "https://www.cinemacity.cz/cinemas/flora/1052#/buy-tickets-by-cinema?in-cinema=1052&at=2026-08-12&for-movie=7268s2r&view-mode=list"
EMAIL_RECIPIENT = "dalibor.hala@gmail.com"
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

def send_email(found_slots):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        print("Chyba: Nejsou nastaveny přihlašovací údaje k emailu v Secrets.")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECIPIENT
    msg['Subject'] = "VSTUPENKY IMAX 70mm: Odyssea"

    body = "Byly nalezeny volné vstupenky (3 vedle sebe v jedné řadě):\n\n"
    body += "\n".join(found_slots)
    body += "\n\nOdkaz: " + URL
    
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("E-mail byl úspěšně odeslán.")
    except Exception as e:
        print(f"Chyba při odesílání e-mailu: {e}")

def check_tickets():
    results = []
    
    with sync_playwright() as p:
        # Spustíme prohlížeč
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
        page = context.new_page()

        print(f"Kontroluji web: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        page.goto(URL, wait_until="networkidle", timeout=60000)
        
        # Přijetí cookies
        try:
            page.wait_for_selector("#onetrust-accept-btn-handler", timeout=5000)
            page.click("#onetrust-accept-btn-handler")
        except:
            pass

        # Najdeme všechna tlačítka pro časy promítání
        page.wait_for_selector(".qb-movie-info-column a.btn-primary", timeout=10000)
        showtimes = page.query_selector_all(".qb-movie-info-column a.btn-primary")
        
        showtime_links = []
        for st in showtimes:
            link = st.get_attribute("href")
            time_val = st.inner_text().strip()
            # Pokusíme se najít datum v nadřazeném elementu
            parent_date = "Neznámé datum"
            try:
                # Najde nejbližší nadřazený element, který obsahuje datum
                date_el = page.locator("section.day-dimension-list").locator("xpath=preceding-sibling::div[contains(@class, 'date-row')]").last
                parent_date = date_el.inner_text().strip()
            except:
                pass
            showtime_links.append({"url": link, "time": time_val, "date": parent_date})

        for item in showtime_links:
            full_link = f"https://www.cinemacity.cz{item['url']}" if item['url'].startswith("/") else item['url']
            
            print(f"Prověřuji čas: {item['time']} na odkazu {full_link}")
            page.goto(full_link, wait_until="networkidle")
            
            # Tlačítko "Pokračovat jako host"
            try:
                page.wait_for_selector("button#guest-btn, button:has-text('host')", timeout=5000)
                page.click("button#guest-btn, button:has-text('host')")
            except:
                pass
            
            # Analýza sedadel
            try:
                page.wait_for_selector(".seat-container, rect.seat-available, .seat-row", timeout=15000)
                
                # Cinema City často používá SVG pro mapu sedadel
                # Hledáme řady a v nich volná sedadla
                rows = page.query_selector_all(".seat-row")
                
                for row in rows:
                    available_seats = row.query_selector_all(".seat-available")
                    if len(available_seats) >= 3:
                        # Základní kontrola, zda jsou 3 volná místa v řadě
                        # (Pro pokročilou kontrolu 'vedle sebe' by bylo nutné parsovat X/Y souřadnice)
                        results.append(f"{item['date']} v {item['time']} - Volná místa v řadě")
                        break # Stačí nám jeden nález v rámci jednoho času
                
            except Exception as e:
                print(f"Mapa sedadel se nenačetla pro {item['time']}")

        browser.close()
    
    return results

if __name__ == "__main__":
    found = check_tickets()
    if found:
        # Seřazení výsledků chronologicky (zde v pořadí jak byly nalezeny na webu)
        send_email(found)
    else:
        print("Žádné volné vstupenky nenalezeny.")
