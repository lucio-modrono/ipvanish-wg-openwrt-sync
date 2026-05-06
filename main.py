import json
import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import paramiko
from dotenv import load_dotenv

load_dotenv()

def exit_with_error(message, driver):
    print(str(message))
    driver.quit()
    exit(1)

def get_vpn_config():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    # Directorio de descarga dentro del contenedor
    prefs = {"download.default_directory": "/tmp/"}
    chrome_options.add_experimental_option("prefs", prefs)
    
    service = Service(executable_path=os.environ.get("CHROMEDRIVER_PATH", "/usr/bin/chromedriver"))
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        try:
            # Lógica de Login en IPVanish
            driver.get("https://sso.ipvanish.com/")
            # Esperar y rellenar usuario
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "email"))
            ).send_keys(os.getenv("IPVANISH_USER"))
            
            # Rellenar contraseña
            driver.find_element(By.NAME, "password").send_keys(os.getenv("IPVANISH_PASS"))
            
            # Hacer clic en el botón "Sign in"
            boton_login = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[tabindex='3'][class^='button_btn']"))
            )
            boton_login.click()
            
            print("Login successful.")

        except TimeoutException:
            exit_with_error(message="Could not access login page.", driver=driver)
        except NoSuchElementException:
            exit_with_error(message="Could not find button Login Submit. Exiting.", driver=driver)

        # Extraer las cookies de Selenium para usarlas con la librería requests
        cookies = {c['name']: c['value'] for c in driver.get_cookies()}
        headers = {
            "User-Agent": driver.execute_script("return navigator.userAgent"),
            "Content-Type": "application/json"
        }
    
        # 2. Descargar JSON de servidores
        response = requests.get("https://account.ipvanish.com/api-v4/server", cookies=cookies)
        servers = response.json()
    
        # 3. Filtrar por CountryCode y buscar la mayor Capacity
        COUNTRY_FILTER = os.getenv("VPN_COUNTRY_CODE", "NL").strip().upper()
        filtered_servers = [s for s in servers if str(s.get("countryCode")).strip().upper() == COUNTRY_FILTER]
        if not filtered_servers:
            # Extraemos códigos únicos para diagnóstico
            codigos_encontrados = sorted(list(set(str(s.get("countryCode")) for s in servers)))
            print(f"❌ No se encontró el código: '{COUNTRY_FILTER}'")
            print(f"🔍 Códigos detectados en el JSON: {codigos_encontrados}")
            exit_with_error(message=f"Could not find server for country: {COUNTRY_FILTER}", driver=driver)
    
        # Ordenar por capacidad descendente y tomar el primero
        best_server = max(filtered_servers, key=lambda x: x['capacity'])
        target_hostname = best_server['hostname']
        print(f"Server selected: {target_hostname} (Capacidad: {best_server['capacity']})")
    
        # 4. Generar Payload y obtener configuración WireGuard
        payload = {
            "server": target_hostname,
            "allowlan": False,
            "as_file": False
        }
    
        config_response = requests.post(
            "https://account.ipvanish.com/api-v4/wireguard/config",
            json=payload,
            cookies=cookies,
            headers=headers
        )
    
        if config_response.status_code == 200:
            config_text = config_response.text
            # Guardar en archivo temporal
            local_path = "/tmp/wireguard_config.conf"
            with open(local_path, "w") as f:
                f.write(config_text)
            return local_path
        else:
            exit_with_error(message=f"Error al obtener config: {config_response.status_code} - {config_response.text}", driver=driver)

        print("Descarga completada en el contenedor.")
        return "/tmp/wireguard_config.conf" 

    except Exception as e:
        exit_with_error(message=f"Error: {e}")
    finally:
        driver.quit()

def upload_to_openwrt(local_path):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    ssh.connect(
        os.getenv("ROUTER_IP"), 
        username="root", 
        password=os.getenv("ROUTER_PASS")
    )

    # Subir archivo
    sftp = ssh.open_sftp()
    sftp.put(local_path, "/root/vpn.conf")
    sftp.close()

    # Ejecutar script de actualización en OpenWrt
    ssh.exec_command("/usr/bin/update_wg.sh")
    ssh.close()
    print("Router actualizado correctamente.")

if __name__ == "__main__":
    path = get_vpn_config()
#    upload_to_openwrt(path)
