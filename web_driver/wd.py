import os
import time
import random
import shutil
import zipfile
import datetime

import pandas as pd
import undetected_chromedriver as uc

from typing import Type
from functools import wraps
from contextlib import suppress
from seleniumwire import webdriver
from sqlalchemy.exc import IntegrityError
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions
from selenium.common.exceptions import InvalidSessionIdException, WebDriverException
from selenium.common.exceptions import NoSuchWindowException, TimeoutException, ElementClickInterceptedException

from database.models import Market
from database.db import DbConnection
from log_api import logger, get_moscow_time
from database.data_classes import DataWBReportDaily
from .create_extension_proxy import create_proxy_auth_extension

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'


TIME_AWAITED = 25
TIME_SLEEP = (10, 15)


def handle_exceptions(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Ошибка при выполнении функции '{func.__name__}': {e}")

    return wrapper


def modal_exceptions(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except ElementClickInterceptedException:
            logger.warning("Обнаружено модальное окно, закрываю его.")
            try:
                cancel_button = WebDriverWait(self.driver, TIME_AWAITED).until(
                    expected_conditions.element_to_be_clickable((By.CSS_SELECTOR,
                                                                 'button.zYbWaxtcLWbZ0k3fKPTi.llfYEylHL4V2OpZmoDqx'))
                )

                cancel_button.click()
                time.sleep(random.randint(*TIME_SLEEP))
            except TimeoutException:
                logger.error("Не удалось найти кнопку для закрытия модального окна.")
            return func(self, *args, **kwargs)

    return wrapper


class WebDriver:
    def __init__(self, market: Type[Market], user: str, db_conn_admin: DbConnection, db_conn_arris: DbConnection):

        self.user = user
        self.market = market
        self.new_path = None
        self.client_id = market.client_id
        self.db_conn_admin = db_conn_admin
        self.db_conn_arris = db_conn_arris
        self.proxy = market.connect_info.proxy
        self.phone = market.connect_info.phone
        self.browser_id = f"{market.connect_info.phone}_WB"
        self.marketplace = self.db_conn_admin.get_marketplace()

        self.profile_path = os.path.join(os.getcwd(), "chrome_profile", self.browser_id)
        self.reports_path = os.path.join(os.getcwd(), "reports")
        os.makedirs(self.profile_path, exist_ok=True)
        os.makedirs(self.reports_path, exist_ok=True)

        self.chrome_options = uc.ChromeOptions()
        self.chrome_options.add_argument("--lang=ru")
        self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--log-level=3")
        self.chrome_options.add_argument("--disable-automation")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--allow-insecure-localhost")
        self.chrome_options.add_argument("--ignore-certificate-errors")
        self.chrome_options.add_argument(f"--user-data-dir={self.profile_path}")
        self.chrome_options.add_experimental_option("useAutomationExtension", False)
        self.chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        self.chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        self.chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                         "(KHTML, like Gecko) Chrome/119.0.5945.86 Safari/537.36")

        self.service = Service(ChromeDriverManager().install())

        self.proxy_auth_path = os.path.join(os.getcwd(), f"proxy_auth")
        os.makedirs(self.proxy_auth_path, exist_ok=True)

        ext_path = create_proxy_auth_extension(self.proxy_auth_path, self.proxy)
        self.chrome_options.add_argument(f'--load-extension={ext_path}')
        self.driver = webdriver.Chrome(service=self.service, options=self.chrome_options)

        self.driver.maximize_window()

    def check_auth(self):
        try:
            WebDriverWait(self.driver, TIME_AWAITED * 4).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            last_url = None
            while True:
                if last_url == self.driver.current_url:
                    break
                last_url = self.driver.current_url
                WebDriverWait(self.driver, TIME_AWAITED * 4).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
                time.sleep(random.randint(*TIME_SLEEP))

            if self.marketplace.link in last_url:
                logger.info(f"Автоматизация {self.market.name_company} запущена")
                self.wb_auth(self.marketplace)
            if self.marketplace.domain in last_url:
                logger.info(f"Вход в ЛК {self.market.name_company} выполнен")
        except Exception as e:
            self.quit(f"Ошибка автоматизации. {str(e).splitlines()[0]}")

    def wb_auth(self, marketplace):
        logger.info(f"Ввод номера {self.phone}")

        for _ in range(3):
            try:
                time.sleep(random.randint(*TIME_SLEEP))
                input_phone = WebDriverWait(self.driver, TIME_AWAITED * 4).until(
                    expected_conditions.element_to_be_clickable((By.CSS_SELECTOR,
                                                                 '.SimpleInput-JIIQvb037j')))
                input_phone.send_keys(self.phone)
                time.sleep(random.randint(*TIME_SLEEP))
                button_phone = WebDriverWait(self.driver, TIME_AWAITED * 4).until(
                    expected_conditions.element_to_be_clickable((By.XPATH,
                                                                 '//*[@data-testid="submit-phone-button"]')))
                break
            except TimeoutException:
                self.driver.refresh()
        else:
            raise Exception('Страница не получена')

        logger.info(f"Проверка заявки на СМС на номер {self.phone}")

        time_request = get_moscow_time()
        self.db_conn_admin.check_phone_message(user=self.user,
                                               phone=self.phone,
                                               time_request=time_request)
        button_phone.click()

        logger.info(f"Ожидание кода на номер {self.phone}")

        for _ in range(3):
            try:
                self.db_conn_admin.add_phone_message(user=self.user,
                                                     phone=self.phone,
                                                     marketplace=marketplace.marketplace,
                                                     time_request=time_request)
                break
            except IntegrityError:
                time.sleep(random.randint(*TIME_SLEEP))
        else:
            raise Exception('Ошибка параллельных запросов')

        mes = self.db_conn_admin.get_phone_message(user=self.user,
                                                   phone=self.phone,
                                                   marketplace=marketplace.marketplace)

        logger.info(f"Код на номер {self.phone} получен: {mes}")
        logger.info(f"Ввод кода {mes}")

        try:
            time.sleep(random.randint(*TIME_SLEEP))
            inputs_code = WebDriverWait(self.driver, TIME_AWAITED * 4).until(
                expected_conditions.presence_of_all_elements_located((By.CSS_SELECTOR, '.InputCell-PB5beCCt55')))

            if len(mes) == len(inputs_code):
                for i, input_code in enumerate(inputs_code):
                    input_code.send_keys(mes[i])
            else:
                raise Exception('Ошибка ввода кода')
        except TimeoutException:
            raise Exception('Отсутствует поле ввода кода')

        logger.info(f"Вход в ЛК {marketplace.marketplace} {self.market.name_company}")
        for _ in range(10):
            if marketplace.domain in self.driver.current_url:
                logger.info(f"Вход в ЛК {marketplace.marketplace} {self.market.name_company} выполнен")
                return
            time.sleep(random.randint(*TIME_SLEEP))

    def is_browser_active(self):
        try:
            if self.driver.session_id is None:
                return False
            if not self.driver.service.is_connectable():
                return False
            return bool(self.driver.current_url)
        except (NoSuchWindowException, InvalidSessionIdException, WebDriverException):
            return False

    def load_url(self, url: str):
        if self.client_id is None:
            self.quit(f"{self.market.name_company} {self.market.entrepreneur} не обнаружен в client_id")
        else:
            logger.info(f"Авторизация {self.market.name_company}")
            self.driver.get(url)
            self.check_auth()

    def quit(self, text: str = None):
        if text:
            logger.error(f"{text}")
        else:
            logger.info(f"Браузер для {self.market.name_company} закрыт")
        self.driver.quit()

    @modal_exceptions
    def stores_report_daily(self) -> None:
        """Собирает список отчётов."""
        logger.info(f"Сбор доступных отчётов {self.market.name_company}.")
        reports = {}
        for _ in range(5):
            self.driver.get(
                'https://seller.wildberries.ru/suppliers-mutual-settlements/reports-implementations/reports-daily')
            time.sleep(random.randint(*TIME_SLEEP))
            self.driver.refresh()
            time.sleep(random.randint(*TIME_SLEEP))
            try:
                elements = WebDriverWait(self.driver, TIME_AWAITED).until(
                    expected_conditions.presence_of_all_elements_located((By.CSS_SELECTOR,
                                                                          '.Reports-table-row__Z2QO2UwUMF'))
                )
                break
            except TimeoutException:
                continue
        else:
            logger.info(f"Нет отчётов {self.market.name_company}.")
            return

        for element in elements:
            try:
                date_create = datetime.datetime.strptime(
                    element.find_elements(By.TAG_NAME, 'span')[2].text, '%d.%m.%Y').date()
                id_report = element.find_elements(By.TAG_NAME, 'span')[0].text
                if id_report not in self.db_conn_arris.get_reports_id(client_id=self.client_id):
                    reports.setdefault(date_create, [])
                    reports[date_create].append(id_report)
            except (ValueError, IndexError) as e:
                logger.error(f"Ошибка при обработке элемента: {e}")
                continue

        if reports:
            for date, reports_ids in reports.items():
                self.change_path_downloads(date=date.isoformat())
                for report_id in reports_ids:
                    for retry in range(1, 4):
                        if retry != 1:
                            logger.info(f"Повторяем. Осталось {3 - retry} попыток")
                        try:
                            self.driver.get(
                                f'https://seller.wildberries.ru/suppliers-mutual-settlements/reports-implementations/'
                                f'reports-daily/report/{report_id}?isGlobalBalance=false')
                            time.sleep(random.randint(*TIME_SLEEP))
                            self.download_report_daily(report_id)
                            break
                        except Exception as e:
                            logger.error(f"{e}")
                            continue
                    else:
                        logger.error(f"Попытки исчерпаны отчёт {report_id} скачать не удалось")
                self.save_data_in_database(date=date)
        else:
            logger.info(f"Нет новых отчётов {self.market.name_company}.")

    @modal_exceptions
    def download_report_daily(self, report: str) -> None:
        """Скачивание ежедневного отчёта."""
        download_folder = os.path.expanduser("~/Downloads")

        download_wait_time = 120

        for retry in range(6):
            try:
                if retry == 0:
                    raise TimeoutException
                confirm_button = WebDriverWait(self.driver, TIME_AWAITED).until(
                    expected_conditions.element_to_be_clickable((By.CSS_SELECTOR,
                                                                 '.Menu-block-item__button__VDTa2I8Ag7'))
                )
                confirm_button.click()
            except TimeoutException:
                with suppress(TimeoutException):
                    download_button = WebDriverWait(self.driver, TIME_AWAITED).until(
                        expected_conditions.element_to_be_clickable((By.CSS_SELECTOR,
                                                                     '.DownloadButtons__download-button__9EZ4rCwH8c'))
                    )
                    download_button.click()
                    time.sleep(random.randint(*TIME_SLEEP))
                continue
            else:
                logger.info(f"Загрузка файла {self.new_path}\\{report} начата.")
                time.sleep(random.randint(*TIME_SLEEP))
                start_time = time.time()

                while True:
                    downloaded_files = [f for f in os.listdir(download_folder) if
                                        f.endswith(".zip") and report in f and not f.endswith(".crdownload")]

                    if downloaded_files:
                        for file_name in downloaded_files:
                            source_path = os.path.join(download_folder, file_name)
                            destination_path = os.path.join(self.new_path, file_name)

                            shutil.move(source_path, destination_path)
                        logger.info(f"Загрузка файла {self.new_path}\\{report} завершена.")
                        return
                    elif time.time() - start_time > download_wait_time:
                        logger.error(f"Загрузка файла {self.new_path}\\{report} превысила допустимое время.")
                        break
                    time.sleep(1)

        raise Exception(f"Загрузка файла {self.new_path}\\{report} не удалась.")

    def change_path_downloads(self, date: str) -> None:
        """Устанавливанет место скачивания файла."""
        self.new_path = f'{self.reports_path}\\{date}\\{self.client_id}'

        if not os.path.exists(self.new_path):
            os.makedirs(self.new_path)

    @staticmethod
    def excel_to_entry(excel_file: pd.ExcelFile, realizationreport_id: str,
                       date: datetime.date) -> list[DataWBReportDaily]:
        sheet_name = excel_file.sheet_names[0]
        df = pd.read_excel(excel_file, sheet_name=sheet_name, na_values=['', 'NaN'], dtype=str)
        df = df.fillna('')

        entry = []

        rows_as_list = df.values

        for row in rows_as_list:
            entry.append(DataWBReportDaily(realizationreport_id=realizationreport_id,
                                           gi_id=row[1],
                                           subject_name=row[2],
                                           sku=row[3],
                                           brand=row[4],
                                           vendor_code=row[5],
                                           size=row[7],
                                           barcode=row[8],
                                           doc_type_name=row[9],
                                           quantity=int(row[13]),
                                           retail_price=round(float(row[14]), 2),
                                           retail_amount=round(float(row[15]), 2),
                                           sale_percent=int(row[18]),
                                           commission_percent=round(float(row[23]), 2),
                                           office_name=row[49],
                                           supplier_oper_name=row[10],
                                           order_date=datetime.datetime.strptime(row[11], "%Y-%m-%d").date(),
                                           sale_date=datetime.datetime.strptime(row[12], "%Y-%m-%d").date(),
                                           operation_date=date,
                                           shk_id=row[55],
                                           retail_price_withdisc_rub=round(float(row[19]), 2),
                                           delivery_amount=int(row[34]),
                                           return_amount=int(row[35]),
                                           delivery_rub=round(float(row[36]), 2),
                                           gi_box_type_name=row[51],
                                           product_discount_for_report=round(float(row[16]), 2),
                                           supplier_promo=round(float(row[17]), 2) if row[17] else 0,
                                           order_id='0',
                                           ppvz_spp_prc=round(float(row[22]), 2),
                                           ppvz_kvw_prc_base=round(float(row[24]), 2),
                                           ppvz_kvw_prc=round(float(row[25]), 2),
                                           sup_rating_prc_up=round(float(row[20]), 2),
                                           is_kgvp_v2=round(float(row[21]), 2),
                                           ppvz_sales_commission=round(float(row[26]), 2),
                                           ppvz_for_pay=round(float(row[33]), 2),
                                           ppvz_reward=round(float(row[27]), 2),
                                           acquiring_fee=round(float(row[28]), 2),
                                           acquiring_bank=row[44],
                                           ppvz_vw=round(float(row[31]), 2),
                                           ppvz_vw_nds=round(float(row[32]), 2),
                                           ppvz_office_id=row[45] or '0',
                                           ppvz_office_name=row[46],
                                           ppvz_supplier_id='0',
                                           ppvz_supplier_name=row[48],
                                           ppvz_inn=row[47],
                                           declaration_number=row[52],
                                           bonus_type_name=row[42] or None,
                                           sticker_id=row[43] or '0',
                                           site_country=row[50],
                                           penalty=round(float(row[40]), 2),
                                           additional_payment=round(float(row[41]), 2),
                                           rebill_logistic_cost=round(float(row[57]), 2),
                                           rebill_logistic_org=row[58] or None,
                                           kiz=row[54] or None,
                                           storage_fee=round(float(row[59]), 2),
                                           deduction=round(float(row[60]), 2),
                                           acceptance=round(float(row[61]), 2),
                                           posting_number=row[56]))
        return entry

    def save_data_in_database(self, date: datetime.date):
        for zip_file in filter(lambda x: x.endswith('.zip'), os.listdir(self.new_path)):
            zip_file_path = os.path.join(self.new_path, zip_file)

            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                file = zip_ref.namelist()[0]
                zip_ref.extract(file, self.new_path)

                excel_file_path = os.path.join(self.new_path, file)

                with pd.ExcelFile(excel_file_path) as excel_file:
                    realizationreport_id = zip_file.split('.')[0].split('№')[-1]
                    entry = self.excel_to_entry(excel_file=excel_file,
                                                realizationreport_id=realizationreport_id,
                                                date=date)

                os.remove(excel_file_path)

                self.db_conn_arris.add_wb_report_daily_entry(client_id=self.client_id,
                                                             list_report=entry,
                                                             date=date,
                                                             realizationreport_id=realizationreport_id)
