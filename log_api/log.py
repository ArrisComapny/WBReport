import os
import logging
import requests

from datetime import datetime, timezone, timedelta


def get_moscow_time():
    try:
        response = requests.get("https://timeapi.io/api/Time/current/zone?timeZone=Europe/Moscow")
        response.raise_for_status()
        data = response.json()
        moscow_time = datetime.fromisoformat(data['dateTime'].split('.')[0])
        return moscow_time
    except requests.exceptions.RequestException as e:
        logger.error(description=f"Ошибка при получении времени: {e}")
        return datetime.now(tz=timezone(timedelta(hours=3)))


class MoscowFormatter(logging.Formatter):
    def formatTime(self, record, date_fmt=None):
        moscow_time = get_moscow_time()
        if date_fmt:
            return moscow_time.strftime(date_fmt)
        else:
            return moscow_time.isoformat()


class RemoteLogger:
    def __init__(self):
        log_dir = "log"
        os.makedirs(log_dir, exist_ok=True)

        log_file = os.path.join(log_dir, f"{get_moscow_time().strftime('%Y-%m-%d')}.log")

        self.logger = logging.getLogger("RemoteLogger")
        self.logger.setLevel(logging.INFO)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)

        formatter = MoscowFormatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)

    def error(self, description: str = '') -> None:
        self.logger.error(f"{description}")

    def info(self, description: str = '') -> None:
        self.logger.info(f"{description}")


logger = RemoteLogger()