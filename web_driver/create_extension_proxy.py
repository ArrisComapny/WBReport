import os
import json


def create_proxy_auth_extension(proxy_auth_path: str, proxy: str, scheme='http') -> str:
    """
    Создаёт расширения Chrome с прокси-авторизацией.

    Параметры:
    - proxy_auth_path: путь, куда сохранить
    - proxy: строка вида http://<login>:<password>@<host>:<port>
    - scheme: схема подключения (по умолчанию http)

    Возвращает:
    - путь к расширению
    """

    # Разбор прокси-строки на компоненты
    proxy_host, proxy_port = proxy.split('@')[-1].split(':')
    proxy_user, proxy_pass = proxy.replace('http://', '').split('@')[0].split(':')

    ext_path = os.path.join(proxy_auth_path, proxy_user)
    os.makedirs(ext_path, exist_ok=True)

    # Содержимое manifest.json для расширения Chrome
    manifest_json = {
        "name": "Proxy Auth Extension",
        "version": "1.0.0",
        "manifest_version": 3,
        "permissions": [
            "proxy",
            "storage",
            "tabs",
            "webRequest",
            "webRequestAuthProvider"
        ],
        "host_permissions": ["<all_urls>"],
        "background": {
            "service_worker": "background.js"
        }
    }

    # Скрипт background.js, настраивающий прокси и авторизацию
    background_js = f"""
    const config = {{
        mode: "fixed_servers",
        rules: {{
            singleProxy: {{
                scheme: "{scheme}",
                host: "{proxy_host}",
                port: parseInt("{proxy_port}")
            }},
            bypassList: ["localhost"]
        }}
    }};

    chrome.proxy.settings.set({{ value: config, scope: "regular" }}, function() {{}});

    fetch("http://example.com")
      .then(() => console.log("Pre-warmed"))
      .catch(() => {{}});

    chrome.webRequest.onAuthRequired.addListener(
        function(details) {{
            return {{
                authCredentials: {{
                    username: "{proxy_user}",
                    password: "{proxy_pass}"
                }}
            }};
        }},
        {{ urls: ["<all_urls>"] }},
        ["blocking"]
    );
    """

    # сохраняем manifest.json и background.js
    with open(os.path.join(ext_path, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest_json, f, indent=4)
    with open(os.path.join(ext_path, "background.js"), "w", encoding="utf-8") as f:
        f.write(background_js)

    return ext_path
