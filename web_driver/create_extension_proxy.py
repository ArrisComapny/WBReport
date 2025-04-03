import zipfile


def create_proxy_auth_extension(proxy_auth_path: str, proxy: str, scheme='http'):
    """
    Создаёт ZIP-архив расширения Chrome с прокси-авторизацией.

    Параметры:
    - proxy_auth_path: путь, куда сохранить zip-файл
    - proxy: строка вида http://<login>:<password>@<host>:<port>
    - scheme: схема подключения (по умолчанию http)

    Возвращает:
    - имя созданного zip-файла (например: <login>.zip)
    """

    # Разбор прокси-строки на компоненты
    proxy_host, proxy_port = proxy.split('@')[-1].split(':')
    proxy_user, proxy_pass = proxy.replace('http://', '').split('@')[0].split(':')

    # Содержимое manifest.json для расширения Chrome
    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Proxy",
        "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "<all_urls>",
            "webRequest",
            "webRequestBlocking"
        ],
        "background": {
            "scripts": ["background.js"]
        }
    }
    """

    # Скрипт background.js, настраивающий прокси и авторизацию
    background_js = f"""
    var config = {{
        mode: "fixed_servers",
        rules: {{
            singleProxy: {{
                scheme: "{scheme}",
                host: "{proxy_host}",
                port: parseInt({proxy_port})
            }},
            bypassList: ["localhost", "127.0.0.1"]
        }}
    }};

    chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});

    chrome.webRequest.onAuthRequired.addListener(
        function(details) {{
            return {{
                authCredentials: {{
                    username: "{proxy_user}",
                    password: "{proxy_pass}"
                }}
            }};
        }},
        {{urls: ["<all_urls>"]}},
        ["blocking"]
    );
    """

    # Создание zip-архива с расширением
    with zipfile.ZipFile(f'{proxy_auth_path}/{proxy_user}.zip', 'w') as zp:
        zp.writestr("manifest.json", manifest_json)
        zp.writestr("background.js", background_js)

    return f'{proxy_user}.zip'
