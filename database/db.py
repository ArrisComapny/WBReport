import time
import logging
import datetime

from typing import Type
from functools import wraps
from sqlalchemy.orm import Session
from pyodbc import Error as PyodbcError
from sqlalchemy.exc import OperationalError
from sqlalchemy import create_engine, func as f

from database.models import *
from database.data_classes import DataWBReportDaily

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
    def __init__(self, url: str, echo: bool = False) -> None:
        self.engine = create_engine(url=url,
                                    echo=echo,
                                    pool_size=10,
                                    max_overflow=5,
                                    pool_timeout=30,
                                    pool_recycle=1800,
                                    pool_pre_ping=True,
                                    connect_args={"keepalives": 1,
                                                  "keepalives_idle": 180,
                                                  "keepalives_interval": 60,
                                                  "keepalives_count": 20,
                                                  "connect_timeout": 10})
        self.session = Session(self.engine)

    @retry_on_exception()
    def get_markets(self, marketplace: str = 'WB') -> list[Type[Market]]:
        markets = self.session.query(Market).filter_by(marketplace=marketplace).all()
        return markets

    @retry_on_exception()
    def get_marketplace(self, marketplace: str = 'WB') -> Type[Marketplace]:
        marketplace = self.session.query(Marketplace).filter_by(marketplace=marketplace).first()
        return marketplace

    @retry_on_exception()
    def check_user(self, login: str, password: str):
        user = self.session.query(User).filter(f.lower(User.user) == login.lower(),
                                               User.password == password).first()
        if user is not None:
            return user.group

    @retry_on_exception()
    def get_phone_message(self, user: str, phone: str, marketplace: str) -> str:
        check = None
        for _ in range(20):
            check = self.session.query(PhoneMessage).filter(
                f.lower(PhoneMessage.user) == user.lower(),
                PhoneMessage.phone == phone,
                PhoneMessage.marketplace == marketplace
            ).order_by(PhoneMessage.time_request.desc()).first()

            if check is None:
                raise Exception('Ошибка получения сообщения')

            if check.message is not None:
                return check.message

            self.session.expire(check)
            time.sleep(5)

        self.session.delete(check)
        self.session.commit()
        raise Exception("Превышен лимит ожидания сообщения")

    @retry_on_exception()
    def check_phone_message(self, user: str, phone: str, time_request: datetime.datetime) -> None:
        for _ in range(20):
            check = self.session.query(PhoneMessage).filter(
                PhoneMessage.phone == phone,
                PhoneMessage.time_request >= time_request - datetime.timedelta(minutes=2),
                PhoneMessage.time_response.is_(None)
            ).all()
            if any([row.user.lower() == user.lower() for row in check]):
                raise Exception("Данный пользователь уже ждёт авторизации")

            if not check:
                break
            self.session.expire(check)
            time.sleep(5)
        else:
            raise Exception("Превышен лимит ожидания очереди")

    @retry_on_exception()
    def add_phone_message(self, user: str, phone: str, marketplace: str, time_request: datetime.datetime) -> None:
        user = self.session.query(User).filter(f.lower(User.user) == user.lower()).first()
        if user is None:
            raise Exception("Такого пользователя не существует")
        new = PhoneMessage(user=user.user,
                           phone=phone,
                           marketplace=marketplace,
                           time_request=time_request)
        self.session.add(new)
        self.session.commit()

    @retry_on_exception()
    def update_phone_message(self, user: str, phone: str, marketplace: str, message: str,
                             time_response: datetime.datetime) -> None:
        mes = self.session.query(PhoneMessage).filter(
            f.lower(PhoneMessage.user) == user.lower(),
            PhoneMessage.phone == phone,
            PhoneMessage.marketplace == marketplace,
            PhoneMessage.time_response.is_(None),
            PhoneMessage.message.is_(None),
            PhoneMessage.time_request <= time_response + datetime.timedelta(seconds=2),
            PhoneMessage.time_request >= time_response - datetime.timedelta(minutes=2)
        ).order_by(PhoneMessage.time_request.asc()).first()

        if mes:
            mes.time_response = time_response
            mes.message = message
            self.session.commit()
        else:
            raise Exception("Нет запроса")

    @retry_on_exception()
    def add_wb_report_daily_entry(self, client_id: str, list_report: list[DataWBReportDaily], date: datetime.date,
                                  realizationreport_id: str) -> None:
        self.session.query(WBReportDaily).filter_by(
            operation_date=date,
            client_id=client_id,
            realizationreport_id=realizationreport_id).delete()
        self.session.commit()

        type_services = set(self.session.query(WBTypeServices.operation_type,
                                               WBTypeServices.service).all())
        for row in list_report:
            match_found = any(
                row.supplier_oper_name == existing_type[0] and (
                        (existing_type[1] is None and row.bonus_type_name is None) or
                        (existing_type[1] is not None and row.bonus_type_name is not None
                         and row.bonus_type_name.startswith(existing_type[1]))
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
        logger.info(f"Успешное добавление в базу отчёта {realizationreport_id}")

    @retry_on_exception()
    def get_reports_id(self, client_id: str) -> list[str]:
        report_ids = self.session.query(WBReportDaily.realizationreport_id).filter_by(
            client_id=client_id).distinct().all()
        report_ids = [r.realizationreport_id for r in report_ids]
        return report_ids
