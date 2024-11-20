import os
import time
import shutil
import logging
import zipfile
import random
import schedule
import pandas as pd
import undetected_chromedriver as uc

from functools import wraps
from contextlib import suppress
from datetime import datetime, timedelta, date

from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException, NoAlertPresentException, \
    ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions

from database.db import DbConnection
from database.data_classes import DataWBReportDaily

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s')
logging.getLogger("seleniumwire").setLevel(logging.CRITICAL)
logging.getLogger("selenium").setLevel(logging.CRITICAL)
logger = logging.getLogger(__name__)

TIME_AWAITED = 20
TIME_SLEEP = (5, 10)


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
                    expected_conditions.element_to_be_clickable((By.CSS_SELECTOR, 'button.zYbWaxtcLWbZ0k3fKPTi.llfYEylHL4V2OpZmoDqx'))
                )

                cancel_button.click()
                time.sleep(random.randint(*TIME_SLEEP))
            except TimeoutException:
                logger.error("Не удалось найти кнопку для закрытия модального окна.")
            return func(self, *args, **kwargs)
    return wrapper


class WebDriver:
    def __init__(self, proxy: str = None, need_date: date = None):
        self.need_date = need_date

        if self.need_date is None:
            self.need_date = date.today() - timedelta(days=1)

        self.profile_path = os.path.join(os.getcwd(), "chrome_profile")
        self.reports_path = os.path.join(os.getcwd(), "reports", self.need_date.isoformat())
        self.new_path = self.reports_path

        self.chrome_options = uc.ChromeOptions()

        self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--use-gl=swiftshader")
        self.chrome_options.add_argument("--disable-extensions")
        self.chrome_options.add_argument("--disable-automation")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--allow-insecure-localhost")
        self.chrome_options.add_argument("--ignore-certificate-errors")
        self.chrome_options.add_argument("--enable-unsafe-swiftshader")
        self.chrome_options.add_argument("--disable-software-rasterizer")
        self.chrome_options.add_argument("--disable-usb-keyboard-detect")
        self.chrome_options.add_argument("--disable-features=PageLoadMetrics")
        self.chrome_options.add_argument(f"--user-data-dir={self.profile_path}")
        self.chrome_options.add_experimental_option("useAutomationExtension", False)
        self.chrome_options.add_argument("--app=https://seller-auth.wildberries.ru")
        self.chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        self.chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
        self.chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        self.chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                         "(KHTML, like Gecko) Chrome/119.0.5945.86 Safari/537.36")

        self.service = Service(ChromeDriverManager().install())

        self.driver = None
        self.create_driver()

    @handle_exceptions
    def create_driver(self) -> None:
        """Создаёт или перезапускает webdriver."""
        text = "Запускаю"
        if self.driver:
            text = "Перезапускаю"
            self.driver.quit()
        self.driver = webdriver.Chrome(service=self.service,
                                       options=self.chrome_options)
        self.driver.maximize_window()
        logger.info(f"{text} webdriver")

    @handle_exceptions
    def start(self) -> list:
        """Ожидает входа в кабинет, после сохраняет cookies по каждому магазину."""
        logger.info(f"Ожидаю входа в кабинет. Пожалуйста, войдите в ЛК.")

        time.sleep(10)

        start_time = time.time()
        while True:
            try:
                if self.driver.current_url == 'https://seller.wildberries.ru/':
                    logger.info("Вход осуществлён.")
                    break
            except UnexpectedAlertPresentException:
                with suppress(NoAlertPresentException):
                    alert = self.driver.switch_to.alert
                    alert.accept()

            elapsed_time = time.time() - start_time
            if elapsed_time > 120:
                logger.error("Не удалось войти в систему в течение 120 секунд.")
                raise TimeoutError("Время ожидания входа истекло.")

            time.sleep(1)
        with suppress(TimeoutException):
            accept_button = WebDriverWait(self.driver, TIME_AWAITED).until(
                expected_conditions.presence_of_element_located((By.CSS_SELECTOR,
                                                                 'button[class*="button-primary_fullWidth"]'))
            )
            logger.info(f"Разрешил cookies.")
            accept_button.click()
            time.sleep(random.randint(*TIME_SLEEP))

        if self.click_profile():
            stores = self.find_stores()
            return stores

    @handle_exceptions
    @modal_exceptions
    def click_profile(self) -> bool:
        """Клик по профилю."""
        while True:
            try:
                WebDriverWait(self.driver, TIME_AWAITED).until(
                    expected_conditions.presence_of_element_located((By.CSS_SELECTOR,
                                                                     '.suppliers-item_SuppliersItem__text__sLbvh'))
                )
                return True
            except TimeoutException:
                try:
                    element = WebDriverWait(self.driver, TIME_AWAITED).until(
                        expected_conditions.element_to_be_clickable((By.CSS_SELECTOR, '.ProfileView'))
                    )
                    element.click()
                    time.sleep(random.randint(*TIME_SLEEP))
                except TimeoutException:
                    logger.error(f"Не удалось найти элемент '.ProfileView' для клика.")
                    return False

    @handle_exceptions
    @modal_exceptions
    def find_stores(self) -> list:
        """Сбор ID магазинов в профиле."""
        try:
            elements = WebDriverWait(self.driver, TIME_AWAITED).until(
                expected_conditions.presence_of_all_elements_located((By.CSS_SELECTOR,
                                                                      '.suppliers-item_SuppliersItem__text__sLbvh'))
            )

            stores = [element.find_elements(By.TAG_NAME, 'span')[0].text.split()[-1] for element in elements[2::3]]
            return stores
        except TimeoutException:
            logger.error("Не удалось найти элементы с ID магазинов.")
            return []

    @handle_exceptions
    @modal_exceptions
    def go_store(self, i: int, store: str) -> bool:
        """Переход в ЛК магазина по позиции в списке профиля."""
        logger.info(f"Переход в ЛК магазина ID: {store}.")
        if self.click_profile():
            try:
                elements = WebDriverWait(self.driver, TIME_AWAITED).until(
                    expected_conditions.presence_of_all_elements_located((By.CSS_SELECTOR,
                                                                          '.checkbox_Checkbox--radio__oqtnx'))
                )
                elements[i].click()
                time.sleep(random.randint(*TIME_SLEEP))
                return True
            except TimeoutException:
                logger.error("Элементы выбора магазина не загрузились.")

    @handle_exceptions
    @modal_exceptions
    def download_report_daily(self, report: str) -> None:
        """Скачивание ежедневного отчёта."""
        download_folder = os.path.expanduser("~/Downloads")

        download_wait_time = 60
        retry = 0
        max_retry = 6

        while retry < max_retry:
            try:
                if retry == 0:
                    raise TimeoutException
                confirm_button = WebDriverWait(self.driver, TIME_AWAITED).until(
                    expected_conditions.element_to_be_clickable((By.CSS_SELECTOR,
                                                                 '.Menu-block-item__button__VDTa2I8Ag7'))
                )
                confirm_button.click()
                time.sleep(random.randint(*TIME_SLEEP))
            except TimeoutException:
                with suppress(TimeoutException):
                    download_button = WebDriverWait(self.driver, TIME_AWAITED).until(
                        expected_conditions.element_to_be_clickable((By.CSS_SELECTOR,
                                                                     '.DownloadButtons__download-button__9EZ4rCwH8c'))
                    )
                    download_button.click()
                    time.sleep(random.randint(*TIME_SLEEP))
                retry += 1
                continue
            else:
                logger.info(f"Загрузка файла {self.new_path}\\{report} начата.")
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
                retry += 1

        logger.error(f"Загрузка файла {self.new_path}\\{report} не удалась.")

    @handle_exceptions
    def change_path_downloads(self, store: str) -> None:
        """Устанавливанет место скачивания файла."""
        self.new_path = f'{self.reports_path}\\{store}'

        if not os.path.exists(self.new_path):
            os.makedirs(self.new_path)

    @handle_exceptions
    @modal_exceptions
    def stores_report_daily(self, stores: list) -> None:
        """Собирает список отчётов за вчерашний день для каждого магазина, после чего скачивает."""
        if os.path.exists(self.reports_path):
            shutil.rmtree(self.reports_path)
        os.makedirs(self.reports_path)

        for i, store in enumerate(stores):
            logger.info(f"Сбор доступных отчётов по ID {store}.")
            ids = []

            if self.go_store(i, store):

                self.driver.get(
                    'https://seller.wildberries.ru/suppliers-mutual-settlements/reports-implementations/reports-daily')
                time.sleep(random.randint(*TIME_SLEEP))

                if (date.today() - self.need_date).days > 7:
                    with suppress(TimeoutException):
                        button_more = WebDriverWait(self.driver, TIME_AWAITED).until(
                            expected_conditions.element_to_be_clickable((By.CSS_SELECTOR, '.button__WxukyZSSBr'))
                        )
                        button_more.click()
                        time.sleep(random.randint(*TIME_SLEEP))
                try:
                    elements = WebDriverWait(self.driver, TIME_AWAITED).until(
                                expected_conditions.presence_of_all_elements_located((By.CSS_SELECTOR,
                                                                                      '.Reports-table-row__Z2QO2UwUMF'))
                            )
                except TimeoutException:
                    logger.info(f"Нет отчётов.")
                    continue

                for element in elements:
                    try:
                        date_create = datetime.strptime(element.find_elements(By.TAG_NAME, 'span')[2].text, '%d.%m.%Y')
                        id_report = element.find_elements(By.TAG_NAME, 'span')[0].text
                        if self.need_date == date_create.date():
                            ids.append(id_report)
                    except (ValueError, IndexError) as e:
                        logger.error(f"Ошибка при обработке элемента: {e}")
                        continue

            if ids:
                self.change_path_downloads(store)
            else:
                logger.info(f"Нет отчётов за {self.need_date.isoformat()}.")

            for report in ids:
                self.driver.get(
                    f'https://seller.wildberries.ru/suppliers-mutual-settlements/reports-implementations/'
                    f'reports-daily/report/{report}?isGlobalBalance=false')
                time.sleep(random.randint(*TIME_SLEEP))
                self.download_report_daily(report)

    @handle_exceptions
    def excel_to_entry(self, excel_file: pd.ExcelFile, realizationreport_id: str) -> list[DataWBReportDaily]:
        sheet_name = excel_file.sheet_names[0]
        df = pd.read_excel(excel_file, sheet_name=sheet_name, na_values=['', 'NaN'], dtype=str)
        df = df.fillna('')

        entry = []

        rows_as_list = df.values

        for row in rows_as_list:
            entry.append(DataWBReportDaily(realizationreport_id=realizationreport_id.split('№')[-1],
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
                                           order_date=datetime.strptime(row[11], "%Y-%m-%d").date(),
                                           sale_date=datetime.strptime(row[12], "%Y-%m-%d").date(),
                                           operation_date=self.need_date,
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

    @handle_exceptions
    def save_data_in_database(self):
        if not os.path.exists(self.reports_path):
            return

        db_conn = DbConnection()
        db_conn.start_db()
        clients = db_conn.get_clients(marketplace='WB')

        for client in clients:
            client_reports_path = os.path.join(self.reports_path, client.client_id)
            if os.path.exists(client_reports_path):
                for zip_file in filter(lambda x: x.endswith('.zip'), os.listdir(client_reports_path)):
                    zip_file_path = os.path.join(client_reports_path, zip_file)

                    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                        file = zip_ref.namelist()[0]
                        zip_ref.extract(file, client_reports_path)

                        excel_file_path = os.path.join(client_reports_path, file)

                        with pd.ExcelFile(excel_file_path) as excel_file:
                            realizationreport_id = zip_file.split('.')[0]
                            entry = self.excel_to_entry(excel_file=excel_file,
                                                        realizationreport_id=realizationreport_id)

                        os.remove(excel_file_path)

                        db_conn.add_wb_report_daily_entry(client_id=client.client_id,
                                                          list_report=entry,
                                                          need_date=self.need_date,
                                                          realizationreport_id=realizationreport_id)
            else:
                logger.info(f"Нет отчётов.")


def main():
    web = WebDriver()
    list_stores = None
    while list_stores is None:
        list_stores = web.start()
        if list_stores is None:
            logger.error(f"Ошибка получения данных магазинов")
            logger.info(f"Повторная попытка через {TIME_AWAITED * 6} секунд.")
            time.sleep(TIME_AWAITED * 6)
            web.driver.refresh()
    web.stores_report_daily(stores=list_stores)
    web.driver.quit()
    web.save_data_in_database()


def run_job():
    time_run = "05:00"
    logger.info(f"Выполнение запланировано на {time_run}")
    schedule.every().day.at(time_run).do(main)

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == '__main__':
    run_job()
