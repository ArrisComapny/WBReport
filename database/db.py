import time
import logging
from datetime import date

from typing import Type
from functools import wraps

from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from pyodbc import Error as PyodbcError
from sqlalchemy.exc import OperationalError

from config import DB_URL
from database.data_classes import DataWBReportDaily
from database.models import *

logger = logging.getLogger(__name__)


def retry_on_exception(retries=3, delay=10):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            attempt = 0
            while attempt < retries:
                try:
                    result = func(self, *args, **kwargs)
                    return result
                except (OperationalError, PyodbcError) as e:
                    attempt += 1
                    logger.debug(f"Error occurred: {e}. Retrying {attempt}/{retries} after {delay} seconds...")
                    time.sleep(delay)
                    if hasattr(self, 'session'):
                        self.session.rollback()
                except Exception as e:
                    logger.error(f"An unexpected error occurred: {e}. Rolling back...")
                    if hasattr(self, 'session'):
                        self.session.rollback()
                    raise e
            raise RuntimeError("Max retries exceeded. Operation failed.")
        return wrapper
    return decorator


class DbConnection:
    def __init__(self, echo: bool = False) -> None:
        self.engine = create_engine(url=DB_URL, echo=echo, pool_pre_ping=True)
        self.session = Session(self.engine)

    @retry_on_exception()
    def start_db(self) -> None:
        """Создание таблиц."""
        metadata.create_all(self.session.bind, checkfirst=True)

    @retry_on_exception()
    def get_client(self, client_id: str) -> Type[Client]:
        """
            Возвращает данные кабинета, отфильтрованный по ID кабинета.

            Args:
                client_id (str): ID кабинета для фильтрации.

            Returns:
                Type[Client]: данные кабинета, удовлетворяющих условию фильтрации.
        """
        client = self.session.query(Client).filter_by(client_id=client_id).first()
        return client

    @retry_on_exception()
    def get_clients(self, marketplace: str = None) -> list[Type[Client]]:
        """
            Возвращает список данных кабинета, отфильтрованный по заданному рынку.

            Args:
                marketplace (str): Рынок для фильтрации.

            Returns:
                List[Type[Client]]: Список данных кабинета, удовлетворяющих условию фильтрации.
        """
        if marketplace:
            result = self.session.query(Client).filter_by(marketplace=marketplace).all()
        else:
            result = self.session.query(Client).all()
        return result

    @retry_on_exception()
    def add_wb_report_daily_entry(self, client_id: str, list_report: list[DataWBReportDaily], need_date: date,
                                  realizationreport_id: str) -> None:
        self.session.query(WBReportDaily).filter_by(
            operation_date=need_date,
            client_id=client_id,
            realizationreport_id=realizationreport_id.split('№')[-1]).delete()
        self.session.commit()

        type_services = set(self.session.query(WBTypeServices.operation_type,
                                               WBTypeServices.service).all())
        for row in list_report:
            match_found = any(
                row.supplier_oper_name == existing_type[0] and (
                        (existing_type[1] is None and row.bonus_type_name is None) or
                        (existing_type[1] is not None and row.bonus_type_name.startswith(existing_type[1]))
                )
                for existing_type in type_services
            )
            if not match_found:
                new_type = WBTypeServices(operation_type=row.supplier_oper_name,
                                          service=row.bonus_type_name,
                                          type_name='new')
                self.session.add(new_type)
                type_services.add((row.supplier_oper_name, row.bonus_type_name))

            new = WBReportDaily(client_id=client_id,
                                realizationreport_id=row.realizationreport_id,
                                gi_id=row.gi_id,
                                subject_name=row.subject_name,
                                sku=row.sku,
                                brand=row.brand,
                                vendor_code=row.vendor_code,
                                size=row.size,
                                barcode=row.barcode,
                                doc_type_name=row.doc_type_name,
                                quantity=row.quantity,
                                retail_price=row.retail_price,
                                retail_amount=row.retail_amount,
                                sale_percent=row.sale_percent,
                                commission_percent=row.commission_percent,
                                office_name=row.office_name,
                                supplier_oper_name=row.supplier_oper_name,
                                order_date=row.order_date,
                                sale_date=row.sale_date,
                                operation_date=row.operation_date,
                                shk_id=row.shk_id,
                                retail_price_withdisc_rub=row.retail_price_withdisc_rub,
                                delivery_amount=row.delivery_amount,
                                return_amount=row.return_amount,
                                delivery_rub=row.delivery_rub,
                                gi_box_type_name=row.gi_box_type_name,
                                product_discount_for_report=row.product_discount_for_report,
                                supplier_promo=row.supplier_promo,
                                order_id=row.order_id,
                                ppvz_spp_prc=row.ppvz_spp_prc,
                                ppvz_kvw_prc_base=row.ppvz_kvw_prc_base,
                                ppvz_kvw_prc=row.ppvz_kvw_prc,
                                sup_rating_prc_up=row.sup_rating_prc_up,
                                is_kgvp_v2=row.is_kgvp_v2,
                                ppvz_sales_commission=row.ppvz_sales_commission,
                                ppvz_for_pay=row.ppvz_for_pay,
                                ppvz_reward=row.ppvz_reward,
                                acquiring_fee=row.acquiring_fee,
                                acquiring_bank=row.acquiring_bank,
                                ppvz_vw=row.ppvz_vw,
                                ppvz_vw_nds=row.ppvz_vw_nds,
                                ppvz_office_id=row.ppvz_office_id,
                                ppvz_office_name=row.ppvz_office_name,
                                ppvz_supplier_id=row.ppvz_supplier_id,
                                ppvz_supplier_name=row.ppvz_supplier_name,
                                ppvz_inn=row.ppvz_inn,
                                declaration_number=row.declaration_number,
                                bonus_type_name=row.bonus_type_name,
                                sticker_id=row.sticker_id,
                                site_country=row.site_country,
                                penalty=row.penalty,
                                additional_payment=row.additional_payment,
                                rebill_logistic_cost=row.rebill_logistic_cost,
                                rebill_logistic_org=row.rebill_logistic_org,
                                kiz=row.kiz,
                                storage_fee=row.storage_fee,
                                deduction=row.deduction,
                                acceptance=row.acceptance,
                                posting_number=row.posting_number)
            self.session.add(new)
        self.session.commit()
        logger.info(f"Успешное добавление в базу")
