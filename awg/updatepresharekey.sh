#!/bin/bash

set -e

WG_CONFIG_FILE="$1"
DOCKER_CONTAINER="$2"
SERVER_CONF_PATH="/tmp/wg_temp.conf"

if [ -z "$WG_CONFIG_FILE" ] || [ -z "$DOCKER_CONTAINER" ]; then
    echo "Usage: $0 <WG_CONFIG_FILE> <DOCKER_CONTAINER>"
    exit 1
fi

# Считать JSON из stdin
JSON_DATA=$(cat)

# Выгружаем конфигурацию
docker exec -i "$DOCKER_CONTAINER" cat "$WG_CONFIG_FILE" > "$SERVER_CONF_PATH"

# Обрабатываем JSON
echo "$JSON_DATA" | jq -c '.[]' | while read -r entry; do
    CLIENT_NAME=$(echo "$entry" | jq -r '.client_name')
    NEW_PSK=$(echo "$entry" | jq -r '.new_preshared_key')

    # Если new_preshared_key == false, генерируем новый PSK
    if [ "$NEW_PSK" == "false" ]; then
        NEW_PSK=$(docker exec -i "$DOCKER_CONTAINER" wg genpsk)
        echo "Generated new PresharedKey for $CLIENT_NAME: $NEW_PSK"
    fi

    # Найти [Peer] блок по комментарию с именем клиента
    PEER_LINES=$(grep -n "^\[Peer\]" "$SERVER_CONF_PATH" | cut -d: -f1)
    FOUND_BLOCK_START=""
    FOUND_BLOCK_END=""
    LINES=($(echo "$PEER_LINES"))

    for i in "${!LINES[@]}"; do
        START=${LINES[$i]}
        END=${LINES[$((i+1))]:-$(wc -l < "$SERVER_CONF_PATH")}

        if sed -n "${START},${END}p" "$SERVER_CONF_PATH" | grep -q "# $CLIENT_NAME"; then
            FOUND_BLOCK_START=$START
            FOUND_BLOCK_END=$END
            break
        fi
    done

    if [ -n "$FOUND_BLOCK_START" ]; then
        echo "Updating PSK for $CLIENT_NAME"
        sed -i "${FOUND_BLOCK_START},${FOUND_BLOCK_END}s|^PresharedKey\s*=.*|PresharedKey = $NEW_PSK|" "$SERVER_CONF_PATH"
    else
        echo "Warning: Client $CLIENT_NAME not found"
    fi
done

# Возврат конфига в контейнер
docker cp "$SERVER_CONF_PATH" "$DOCKER_CONTAINER:$WG_CONFIG_FILE"

# Перезапуск WireGuard
docker exec -i "$DOCKER_CONTAINER" sh -c "wg-quick down $WG_CONFIG_FILE || true && wg-quick up $WG_CONFIG_FILE"

echo "All PresharedKeys updated successfully."
