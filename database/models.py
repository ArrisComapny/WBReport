from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Date, String, Integer, DateTime, Numeric
from sqlalchemy import Column, Identity, MetaData, ForeignKey, UniqueConstraint

metadata = MetaData()
Base = declarative_base(metadata=metadata)


class Market(Base):
    """Модель таблицы clients."""
    __tablename__ = 'markets'

    id = Column(Integer, Identity(), primary_key=True)
    marketplace = Column(String(length=255), ForeignKey('marketplaces.marketplace', onupdate="CASCADE"), nullable=False)
    name_company = Column(String(length=255), nullable=False)
    phone = Column(String(length=255), ForeignKey('connects.phone', onupdate="CASCADE"), nullable=False)
    entrepreneur = Column(String(length=255), nullable=False)

    marketplace_info = relationship("Marketplace", back_populates="markets")
    connect_info = relationship("Connect", back_populates="markets")

    __table_args__ = (
        UniqueConstraint('marketplace', 'name_company', 'phone', name='markets_unique'),
        UniqueConstraint('marketplace', 'name_company', name='market_unique')
    )


class Marketplace(Base):
    """Модель таблицы marketplaces."""
    __tablename__ = 'marketplaces'

    marketplace = Column(String(length=255), primary_key=True, nullable=False)
    link = Column(String(length=1000), nullable=False)
    domain = Column(String(length=255), nullable=False)

    markets = relationship("Market", back_populates="marketplace_info")


class Connect(Base):
    """Модель таблицы connects."""
    __tablename__ = 'connects'

    phone = Column(String(length=255), primary_key=True, nullable=False)
    proxy = Column(String(length=255), nullable=False)
    mail = Column(String(length=255), nullable=False)
    token = Column(String(length=255), nullable=False)

    markets = relationship("Market", back_populates="connect_info")

    __table_args__ = (
        UniqueConstraint('phone', 'proxy', name='connects_unique'),
    )


class User(Base):
    """Модель таблицы connects."""
    __tablename__ = 'users'

    user = Column(String(length=255), primary_key=True, nullable=False)
    password = Column(String(length=255), nullable=False)
    name = Column(String(length=255), default=None, nullable=True)
    group = Column(String(length=255), ForeignKey('group_table.group', onupdate="CASCADE"), nullable=False)


class PhoneMessage(Base):
    """Модель таблицы phone_message."""
    __tablename__ = 'phone_message'

    id = Column(Integer, Identity(), primary_key=True)
    user = Column(String(length=255), ForeignKey('users.user', onupdate="CASCADE"), nullable=False)
    phone = Column(String(length=255), ForeignKey('connects.phone', onupdate="CASCADE"), nullable=False)
    marketplace = Column(String(length=255), ForeignKey('marketplaces.marketplace', onupdate="CASCADE"), nullable=False)
    time_request = Column(DateTime, nullable=False)
    time_response = Column(DateTime, default=None, nullable=True)
    message = Column(String(length=255), default=None, nullable=True)

    __table_args__ = (
        UniqueConstraint('time_request', name='phone_message_time_request_unique'),
        UniqueConstraint('time_response', name='phone_message_time_response_unique'),
    )


class Client(Base):
    """Модель таблицы clients."""
    __tablename__ = 'clients'

    client_id = Column(String(length=255), primary_key=True)
    api_key = Column(String(length=1000), nullable=False)
    marketplace = Column(String(length=255), nullable=False)
    name_company = Column(String(length=255), nullable=False)
    entrepreneur = Column(String(length=255), nullable=False)


class WBReportDaily(Base):
    """Модель таблицы wb_report_daily."""
    __tablename__ = 'wb_report_daily'

    id = Column(Integer, Identity(), primary_key=True)
    client_id = Column(String(length=255), ForeignKey('clients.client_id'), nullable=False)
    realizationreport_id = Column(String(length=255), default=None, nullable=True)
    gi_id = Column(String(length=255), default=None, nullable=True)
    subject_name = Column(String(length=255), default=None, nullable=True)
    sku = Column(String(length=255), nullable=False)
    brand = Column(String(length=255), default=None, nullable=True)
    vendor_code = Column(String(length=255), nullable=False)
    size = Column(String(length=255), default=None, nullable=True)
    barcode = Column(String(length=255), default=None, nullable=True)
    doc_type_name = Column(String(length=255), default=None, nullable=True)
    quantity = Column(Integer, nullable=False)
    retail_price = Column(Numeric(precision=12, scale=2), nullable=False)
    retail_amount = Column(Numeric(precision=12, scale=2), nullable=False)
    sale_percent = Column(Integer, nullable=False)
    commission_percent = Column(Numeric(precision=12, scale=2), nullable=False)
    office_name = Column(String(length=255), default=None, nullable=True)
    supplier_oper_name = Column(String(length=255), nullable=False)
    order_date = Column(Date, nullable=False)
    sale_date = Column(Date, nullable=False)
    operation_date = Column(Date, nullable=False)
    shk_id = Column(String(length=255), default=None, nullable=True)
    retail_price_withdisc_rub = Column(Numeric(precision=12, scale=2), nullable=False)
    delivery_amount = Column(Integer, nullable=False)
    return_amount = Column(Integer, nullable=False)
    delivery_rub = Column(Numeric(precision=12, scale=2), nullable=False)
    gi_box_type_name = Column(String(length=255), default=None, nullable=True)
    product_discount_for_report = Column(Numeric(precision=12, scale=2), nullable=False)
    supplier_promo = Column(Numeric(precision=12, scale=2), nullable=False)
    order_id = Column(String(length=255), default=None, nullable=True)
    ppvz_spp_prc = Column(Numeric(precision=12, scale=2),  nullable=False)
    ppvz_kvw_prc_base = Column(Numeric(precision=12, scale=2), nullable=False)
    ppvz_kvw_prc = Column(Numeric(precision=12, scale=2), nullable=False)
    sup_rating_prc_up = Column(Numeric(precision=12, scale=2), nullable=False)
    is_kgvp_v2 = Column(Numeric(precision=12, scale=2), nullable=False)
    ppvz_sales_commission = Column(Numeric(precision=12, scale=2), nullable=False)
    ppvz_for_pay = Column(Numeric(precision=12, scale=2), nullable=False)
    ppvz_reward = Column(Numeric(precision=12, scale=2), nullable=False)
    acquiring_fee = Column(Numeric(precision=12, scale=2), nullable=False)
    acquiring_bank = Column(String(length=255), default=None, nullable=True)
    ppvz_vw = Column(Numeric(precision=12, scale=2), nullable=False)
    ppvz_vw_nds = Column(Numeric(precision=12, scale=2), nullable=False)
    ppvz_office_id = Column(String(length=255), default=None, nullable=True)
    ppvz_office_name = Column(String(length=255), default=None, nullable=True)
    ppvz_supplier_id = Column(String(length=255), default=None, nullable=True)
    ppvz_supplier_name = Column(String(length=255), default=None, nullable=True)
    ppvz_inn = Column(String(length=255), default=None, nullable=True)
    declaration_number = Column(String(length=255), default=None, nullable=True)
    bonus_type_name = Column(String(length=1000), default=None, nullable=True)
    sticker_id = Column(String(length=255), default=None, nullable=True)
    site_country = Column(String(length=255), default=None, nullable=True)
    penalty = Column(Numeric(precision=12, scale=2), nullable=False)
    additional_payment = Column(Numeric(precision=12, scale=2), nullable=False)
    rebill_logistic_cost = Column(Numeric(precision=12, scale=2), nullable=False)
    rebill_logistic_org = Column(String(length=255), default=None, nullable=True)
    kiz = Column(String(length=255), default=None, nullable=True)
    storage_fee = Column(Numeric(precision=12, scale=2), nullable=False)
    deduction = Column(Numeric(precision=12, scale=2), nullable=False)
    acceptance = Column(Numeric(precision=12, scale=2), nullable=False)
    posting_number = Column(String(length=255), nullable=False)


class WBTypeServices(Base):
    """Модель таблицы wb_type_services."""
    __tablename__ = 'wb_type_services'

    id = Column(Integer, Identity(), primary_key=True)
    operation_type = Column(String(length=255), nullable=False)
    service = Column(String(length=1000), default=None, nullable=True)
    type_name = Column(String(length=255), default=None, nullable=True)
