import undetected_chromedriver as uc

import json
import os
import time
import requests
import random
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

import paramiko
from scp import SCPClient
from dotenv import load_dotenv

load_dotenv()

def exit_with_error(message, driver):
    print(str(message))
    driver.quit()
    exit(1)

def rellenar_campo_react(driver, element, valor):
    actions = ActionChains(driver)
    # Mover el ratón al elemento con un pequeño offset aleatorio
    actions.move_to_element_with_offset(element, random.randint(-5, 5), random.randint(-5, 5))
    actions.pause(random.uniform(0.1, 0.3))
    actions.click()
    actions.perform()

    element.click()
    time.sleep(random.uniform(0.2, 0.5))
    # Limpiamos usando teclas para disparar eventos de cambio
    element.send_keys(Keys.CONTROL + "a")
    element.send_keys(Keys.BACKSPACE)

    # Escribimos el valor como lo haría un humano
    # element.send_keys(valor)
    for letra in valor:
        element.send_keys(letra)
        time.sleep(random.uniform(0.05, 0.25))

    # Forzamos el evento 'input' y 'change' vía JS para que React lo vea
    driver.execute_script("""
        var element = arguments[0];
        var value = arguments[1];
        element.value = value;
        ['input', 'change', 'blur'].forEach(eventName => {
            element.dispatchEvent(new Event(eventName, { bubbles: true }));
        })
    """, element, valor)

def do_login(driver, url):
    wait = WebDriverWait(driver, 15)
    print(f"⏳ Iniciando login en {url} ...")
    try:
        # Lógica de Login en IPVanish

        driver.get(url)
        # Esperar y rellenar usuario
        wait.until(EC.presence_of_element_located((By.NAME, "email"))).send_keys(os.getenv("IPVANISH_USER"))
        user_input = driver.find_element(By.CSS_SELECTOR, "input[name='email']")
        rellenar_campo_react(driver, user_input, os.getenv("IPVANISH_USER"))

        # Rellenar contraseña
        wait.until(EC.presence_of_element_located((By.NAME, "password"))).send_keys(os.getenv("IPVANISH_PASS"))
        pass_input = driver.find_element(By.CSS_SELECTOR, "input[name='password']")
        rellenar_campo_react(driver, pass_input, os.getenv("IPVANISH_PASS"))

        pass_input.send_keys(Keys.ENTER)
        # Hacer clic en el botón "Sign in"
#        boton_login = wait.until(
#           EC.element_to_be_clickable((By.CSS_SELECTOR, "button[tabindex='3'][class^='button_btn']"))
#        )
#        boton_login.click()
#        try:
#            driver.execute_script("arguments[0].click();", boton_login)
#        except:
#            pass_input.send_keys(Keys.ENTER)

        print("🚀 Intento de login enviado. Verificando cambio de URL...")
        # Esperar específicamente a que la URL CAMBIE
        try:
            # Esperamos hasta 15 segundos a que la URL ya no sea la de SSO
            wait.until(lambda d: url not in d.current_url)
            print(f"✅ Redirección exitosa a: {driver.current_url}")
        except TimeoutException:
            exit_with_error(message=f"⚠️ Login unsuccessful, current URL: {driver.current_url}", driver=driver)
            # Aquí es donde el 403 suele ocurrir si detectan bot

        print(f"Login successful, current URL: {driver.current_url}")

    except TimeoutException:
        exit_with_error(message="Could not access login page.", driver=driver)
    except NoSuchElementException:
        exit_with_error(message="Could not find button Login Submit. Exiting.", driver=driver)

def get_auth_token(driver):
    print("⏳ Esperando a que la aplicación realice peticiones a la API...")

    token = None
    max_retries = 30  # Intentar durante 30 segundos

    for i in range(max_retries):
        # Inspeccionar todas las peticiones capturadas hasta el momento
        for request in driver.requests:
            # Filtramos por la URL de la API para ser más precisos
            if "ipvanish" in request.url:
                auth_header = request.headers.get('Authorization')
                if auth_header and "Bearer" in auth_header:
                    token = auth_header
                    print(f"✅ Token interceptado con éxito en la petición a: {request.url}")
                    return token

        for request in reversed(driver.requests):
            # Buscamos en cualquier petición que vaya a la API
            if "/api-v4/" in request.url:
                auth = request.headers.get('Authorization')
                if auth and "Bearer" in auth:
                    token = auth
                    print(f"✅ Token cazado: {token[:30]}...")
                    return token

        # Si no se encuentra, forzamos una navegación o esperamos
        time.sleep(1)
        if i == 5:
            print("💡 Navegando explícitamente al panel para forzar peticiones API...")
            driver.get("https://account.ipvanish.com/api-v4/customer/me")
        if i == 15:
            print("💡 Navegando explícitamente al panel para forzar peticiones API...")
            driver.get("https://account.ipvanish.com/api-v4/impact/token")

    if not token:
        # Depuración total: si falla, listar todas las URLs intentadas
        print("❌ No se encontró token. URLs interceptadas:")
        for r in driver.requests[:10]: print(f" - {r.url}")

    return token

def get_auth_token_js(driver):
    print("🔍 Buscando token en memoria del navegador...")

    # Este script de JS busca en LocalStorage, SessionStorage y variables de Redux/Vuex comunes
    js_script = """
    return (function() {
        // 1. Intentar Local y Session Storage
        for (let i = 0; i < localStorage.length; i++) {
            let key = localStorage.key(i);
            if (key.includes('token') || key.includes('auth')) return localStorage.getItem(key);
        }
        for (let i = 0; i < sessionStorage.length; i++) {
            let key = sessionStorage.key(i);
            if (key.includes('token') || key.includes('auth')) return sessionStorage.getItem(key);
        }
        // 2. Intentar buscar en el objeto global si existe
        return window.token || window.accessToken || null;
    })();
    """

    token = driver.execute_script(js_script)

    if token and not token.startswith("Bearer "):
        token = f"Bearer {token}"

    return token

def get_auth_token_logs(driver):
    print("🔍 Escaneando logs de red...")
    logs = driver.get_log("performance")
    for entry in logs:
        try:
            msg = json.loads(entry["message"])["message"]

            # Solo nos interesan las peticiones que se van a enviar
            if msg["method"] == "Network.requestWillBeSent":
                params = msg.get("params", {})
                request_data = params.get("request", {})
                headers = request_data.get("headers", {})

                # Buscar el token (insensible a mayúsculas/minúsculas)
                auth = next((v for k, v in headers.items() if k.lower() == 'authorization'), None)

                if auth and "Bearer" in auth:
                    print(f"🎯 Token interceptado con éxito.")
                    return auth
        except (KeyError, ValueError, TypeError):
            # Ignorar entradas malformadas o irrelevantes
            continue

    return None

def get_driver():
    chrome_options = uc.ChromeOptions()
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument('--headless=new') # Importante: usar el nuevo motor headless
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = uc.Chrome(options=chrome_options, browser_executable_path="/usr/bin/google-chrome")

    # Bypass manual de la propiedad 'webdriver'
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    })

    return driver

def get_vpn_config():
    driver = get_driver()

    try:
        do_login(driver, "https://sso.ipvanish.com/")

        # Intentar extraer el token de los logs de ejecución
        token = get_auth_token_logs(driver)
        # Intentar extraer el token mediante JavaScript
        if not token:
            token = get_auth_token_js(driver)

        if not token:
            exit_with_error(message="⚠️ No se encontró el token. Revisa el nombre de la clave en el navegador.", driver=driver)
        else:
            print(f"✅ Token de autorización capturado: {token}")

        # Extraer las cookies de Selenium para usarlas con la librería requests
        session = requests.Session()
        cookies = {c['name']: c['value'] for c in driver.get_cookies()}
        user_agent = driver.execute_script("return navigator.userAgent")
        session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json, text/plain, */*",
            "Authorization": f"{token}",
            "Referer": "https://my.ipvanish.com/",
            "Origin": "https://my.ipvanish.com/"
        })

        # Descargar JSON de servidores
        try:
            resp_servers = session.get("https://account.ipvanish.com/api-v4/server")
            resp_servers.raise_for_status()
            servers = resp_servers.json()
        except Exception as e:
            exit_with_error(message=f"Error en lista de servidores: {e}", driver=driver)
            return

        # Filtrar por CountryCode y buscar la mayor Capacity
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

        session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json, text/plain, */*",
            "Authorization": f"{token}",
            "Referer": "https://my.ipvanish.com/",
            "Origin": "https://my.ipvanish.com/"
        })

        # Generar Payload y obtener configuración WireGuard
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
            print(f"📄 Descarga completada en el contenedor.\nContenido del fichero '{local_path}':\n{config_text}")
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
    print(f"🚀 Copiando fichero '{local_path}' al router OpeWrt por SFTP")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            os.getenv("ROUTER_IP"),
            username="root",
            password=os.getenv("ROUTER_PASS"),
            look_for_keys=False,
            allow_agent=False,
            # Forzar algoritmos de intercambio de llaves más compatibles
            disabled_algorithms={'pubkeys': ['rsa-sha2-256', 'rsa-sha2-512']},
            banner_timeout=30 # Dar más tiempo al router para responder
        )

        # Subir archivo
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(local_conf_path, "/root/vpn.conf")

        # Ejecutar script de actualización en OpenWrt
        print("Aplicando actualización de VPN en router OpenWrt")
        ssh.exec_command("/bin/sh /usr/bin/update_wg.sh")
        ssh.close()
        print("✅ Router actualizado correctamente.")
    except Exception as e:
        print(f"Error al aplicar la configuración en el router OpenWRT: {e}")

if __name__ == "__main__":
    path = get_vpn_config()
    upload_to_openwrt(path)
