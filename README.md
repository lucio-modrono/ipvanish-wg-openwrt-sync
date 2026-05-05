# IPVanish WireGuard Sync para OpenWrt 🚀

Este proyecto automatiza la descarga de perfiles de configuración WireGuard desde el portal de IPVanish y su despliegue automático en routers con OpenWrt. Utiliza **Docker**, **Selenium** y **Paramiko** para gestionar todo el flujo de forma externa, evitando sobrecargar los recursos del router.

## ⚖️ Descargo de Responsabilidad (Disclaimer)

**Este proyecto NO es oficial ni está afiliado, asociado, autorizado, respaldado ni conectado de ninguna manera con IPVanish.**

*   **Uso bajo propia responsabilidad:** El autor no se hace responsable de bloqueos de cuenta, fallos en el router o cualquier otro problema derivado del uso de este script.
*   **Cumplimiento de Términos:** Es responsabilidad del usuario asegurarse de que la automatización del portal no infringe los Términos de Servicio de IPVanish.
*   **Seguridad:** Este script maneja credenciales sensibles. Asegúrate de proteger tus variables de entorno y no compartirlas.

---

## 🛠️ Requisitos

1.  **En el Servidor/PC:**
    *   Docker y Docker Compose instalado.
2.  **En el Router (OpenWrt):**
    *   Protocolo WireGuard instalado (`luci-proto-wireguard`).
    *   Script de actualización local (ver sección [Configuración en OpenWrt](#configuración-en-openwrt)).
    *   Acceso SSH habilitado (se recomienda el uso de llaves SSH).

## 🚀 Instalación y Uso

### 1. Clonar el repositorio
```bash
git clone https://github.com
cd ipvanish-wg-openwrt-sync
```

### 2. Configurar variables de entorno
Crea un archivo `.env` basado en el ejemplo (no incluido en el repositorio por seguridad):
```env
IPVANISH_USER=tu_email@ejemplo.com
IPVANISH_PASS=tu_contraseña
ROUTER_IP=192.168.1.1
ROUTER_PASS=contraseña_ssh_router
```

### 3. Ejecución con Docker
Construye y ejecuta el contenedor:
```bash
docker build -t ipvanish-sync .
docker run --env-file .env ipvanish-sync
```

## 🔧 Configuración en OpenWrt

Para que el despliegue funcione, el router debe tener un script en `/usr/bin/update_wg.sh` que procese el archivo `.conf` subido. Puedes encontrar el código del script en la carpeta `scripts/` de este repositorio.

Asegúrate de dar permisos de ejecución:
```bash
chmod +x /usr/bin/update_wg.sh
```

## 📄 Licencia

Este proyecto está bajo la **Licencia MIT**. Consulta el archivo [LICENSE](LICENSE) para más detalles.

---
**Nota:** Las marcas comerciales y nombres de servicios mencionados pertenecen a sus respectivos propietarios.
