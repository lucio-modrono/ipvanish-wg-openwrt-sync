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

def exit_with_error(message):
    print(str(message))
    driver.quit()
    exit(1)

def get_vpn_config():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Directorio de descarga dentro del contenedor
    prefs = {"download.default_directory": "/tmp/"}
    chrome_options.add_experimental_option("prefs", prefs)
    
    service = Service(executable_path=os.environ.get("CHROMEDRIVER_PATH"))
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Lógica de Login en IPVanish
        driver.get("https://sso.ipvanish.com/")
        # Wait for main page to load
        try:
            WebDriverWait(driver=driver, timeout=120, poll_frequency=3).until(
                expected_conditions.visibility_of(
                    driver.find_element(by=By.CSS_SELECTOR, value="button[tabindex='3'][class^='button_btn']")
                )
            )
        except TimeoutException:
            exit_with_error(message="Could not access login page.")
        except NoSuchElementException:
            exit_with_error(message="Could not find button Login Submit. Exiting.")

        driver.find_element(By.NAME, "email").send_keys(os.getenv("IPVANISH_USER"))
        driver.find_element(By.NAME, "password").send_keys(os.getenv("IPVANISH_PASS"))
        driver.find_element(By.CSS_SELECTOR, "button[tabindex='3'][class^='button_btn']").click()
        
        # Wait for main page to load
        try:
            WebDriverWait(driver=driver, timeout=120, poll_frequency=3).until(
                expected_conditions.visibility_of(
                    driver.find_element(by=By.CSS_SELECTOR, value="div[class^='app-layout_mainContainer']")
                )
            )
            print("Login successful")
        except TimeoutException:
            exit_with_error(message="Could not login. Check if account is blocked.")
        except NoSuchElementException:
            exit_with_error(message="Could not find element Main Layout. Exiting.")

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
        filtered_servers = [s for s in servers if s.get("countryCode") == COUNTRY_FILTER]
        
        if not filtered_servers:
            exit_with_error(message=f"No se encontraron servidores para el país: {COUNTRY_FILTER}")
    
        # Ordenar por capacidad descendente y tomar el primero
        best_server = max(filtered_servers, key=lambda x: x['capacity'])
        target_hostname = best_server['hostname']
        print(f"Servidor seleccionado: {target_hostname} (Capacidad: {best_server['capacity']})")
    
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
            raise Exception(f"Error al obtener config: {config_response.status_code} - {config_response.text}")        

        print("Descarga completada en el contenedor.")
        return "/tmp/wireguard_config.conf" 
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
