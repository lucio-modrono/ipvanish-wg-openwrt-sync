import json
import os
import time
import requests
from seleniumwire import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
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

        # Esperar a que se realicen las llamadas XHR tras login
        time.sleep(5)

        token = None

        # Intentar extraer el token del LocalStorage (común en apps modernas)
        token = driver.execute_script("return window.localStorage.getItem('auth_token');")
        # Si no está ahí, a veces está bajo otro nombre como 'token' o 'accessToken'
        if not token:
            token = driver.execute_script("return window.localStorage.getItem('token');")
        # Si sigue sin aparecer, podemos interceptarlo del sessionStorage
        if not token:
            token = driver.execute_script("return window.sessionStorage.getItem('auth_token');")
        # Inspeccionar las peticiones realizadas por el navegador
        if not token:
            for request in driver.requests:
                if request.headers.get('Authorization'):
                    auth_header = request.headers['Authorization']
                    if "Bearer" in auth_header:
                        token = auth_header # Ya contiene 'Bearer ...'
                        print("✅ Token interceptado del tráfico XHR")
                        break
        if not token:
            print("⚠️ No se encontró el token en Storage. Revisa el nombre de la clave en el navegador.")
        else:
            print("✅ Token de autorización capturado.")

        # Extraer las cookies de Selenium para usarlas con la librería requests
        session = requests.Session()
        cookies = {c['name']: c['value'] for c in driver.get_cookies()}
        user_agent = driver.execute_script("return navigator.userAgent")
        session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json, text/plain, */*",
            "Authorization": f"Bearer {token}",
            "Referer": "https://my.ipvanish.com/",
            "Origin": "https://my.ipvanish.com/"
        })

        # 2. Descargar JSON de servidores
        try:
            resp_servers = session.get("https://account.ipvanish.com/api-v4/server")
            resp_servers.raise_for_status()
            servers = resp_servers.json()
        except Exception as e:
            exit_with_error(message=f"Error en lista de servidores: {e}", driver=driver)
            return

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

        print(f"Solicitando configuración para {target_hostname}...")

        # Algunas APIs requieren esta cabecera específica para peticiones JSON
        session.headers.update({"Content-Type": "application/json"})

        config_response = session.post(
            "https://account.ipvanish.com/api-v4/wireguard/config",
            json=payload
        )

        if config_response.status_code == 200:
            config_text = config_response.text
            # Guardar en archivo temporal
            local_path = "/tmp/wireguard_config.conf"
            with open(local_path, "w") as f:
                f.write(config_text)
            print("Descarga completada en el contenedor.")
            return local_path
        elif config_response.status_code == 403:
            print("❌ Error 403: Acceso denegado. Posible falta de token o cabecera Referer.")
            # Depuración: ver qué cookies tenemos en este momento
            print(f"Cookies actuales: {session.cookies.get_dict()}")
        else:
            exit_with_error(message=f"Error al obtener config: {config_response.status_code} - {config_response.text}", driver=driver)
    except Exception as e:
        exit_with_error(message=f"Error: {e}", driver=driver)
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
