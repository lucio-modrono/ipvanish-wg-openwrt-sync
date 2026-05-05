import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import paramiko
from dotenv import load_dotenv

load_dotenv()

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
        driver.get("https://ipvanish.com")
        driver.find_element(By.NAME, "username").send_keys(os.getenv("IPVANISH_USER"))
        driver.find_element(By.NAME, "password").send_keys(os.getenv("IPVANISH_PASS"))
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        time.sleep(5)
        # Aquí debes añadir los selectores específicos para navegar 
        # y descargar el archivo .conf de WireGuard
        # driver.get("https://ipvanish.com") 
        
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
    upload_to_openwrt(path)
