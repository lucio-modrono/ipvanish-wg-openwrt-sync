#!/bin/sh

# Configuración
CONF_FILE="/root/vpn.conf"
INTERFACE="wg0"

[ ! -f "$CONF_FILE" ] && exit 1

# Extraer valores del .conf
NEW_PRIV_KEY=$(grep "PrivateKey" "$CONF_FILE" | cut -d'=' -f2 | tr -d ' ')
NEW_ADDR=$(grep "Address" "$CONF_FILE" | cut -d'=' -f2 | tr -d ' ')
NEW_DNS=$(grep "DNS" "$CONF_FILE" | cut -d'=' -f2 | tr -d ' ')
NEW_PUB_KEY=$(grep "PublicKey" "$CONF_FILE" | cut -d'=' -f2 | tr -d ' ')
NEW_ENDPOINT=$(grep "Endpoint" "$CONF_FILE" | cut -d'=' -f2 | tr -d ' ' | cut -d':' -f1)
NEW_PORT=$(grep "Endpoint" "$CONF_FILE" | cut -d'=' -f2 | tr -d ' ' | cut -d':' -f2)

# Obtener valores actuales de UCI
CURR_PRIV_KEY=$(uci -q get network.$INTERFACE.private_key)
CURR_DNS=$(uci -q get network.$INTERFACE.dns)

# Comparar llaves y DNS
if [ "$NEW_PRIV_KEY" != "$CURR_PRIV_KEY" ] || [ "$NEW_DNS" != "$CURR_DNS" ]; then
    echo "Cambios detectados en keys o DNS. Actualizando..."
    
    # Configurar Interfaz
    uci set network.$INTERFACE=interface
    uci set network.$INTERFACE.proto='wireguard'
    uci set network.$INTERFACE.private_key="$NEW_PRIV_KEY"
    uci set network.$INTERFACE.addresses="$NEW_ADDR"
    
    # Configurar DNS (Borrar lista previa y añadir nueva)
    uci -q delete network.$INTERFACE.dns
    for dns_ip in $(echo $NEW_DNS | tr ',' ' '); do
        uci add_list network.$INTERFACE.dns="$dns_ip"
    done

    # Configurar Peer
    uci -q delete network.@wireguard_$INTERFACE
    uci add network wireguard_$INTERFACE
    uci set network.@wireguard_$INTERFACE[-1].public_key="$NEW_PUB_KEY"
    uci set network.@wireguard_$INTERFACE[-1].endpoint_host="$NEW_ENDPOINT"
    uci set network.@wireguard_$INTERFACE[-1].endpoint_port="$NEW_PORT"
    uci add_list network.@wireguard_$INTERFACE[-1].allowed_ips='0.0.0.0/0'
    uci set network.@wireguard_$INTERFACE[-1].route_allowed_ips='1'

    uci commit network
    /etc/init.d/network reload
else
    echo "Configuración idéntica. No se requieren cambios."
fi
