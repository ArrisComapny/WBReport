import logging

from log_api.log import logger
from web_driver.wd import WebDriver
from database.db import DbConnection
from config import DB_ADMIN_URL, DB_ARRIS_URL

logging.getLogger("selenium").setLevel(logging.CRITICAL)


def main():
    db_conn_admin = DbConnection(url=DB_ADMIN_URL)
    db_conn_arris = DbConnection(url=DB_ARRIS_URL)
    try:
        markets = db_conn_admin.get_markets()

        for market in markets:
            chrome_driver = WebDriver(market=market,
                                      user='WBReportBot',
                                      db_conn_admin=db_conn_admin,
                                      db_conn_arris=db_conn_arris)
            chrome_driver.load_url(url=market.marketplace_info.link)
            if chrome_driver.is_browser_active():
                chrome_driver.stores_report_daily()
                chrome_driver.quit()
                logger.info(f"Сбор отчётов компани {market.name_company} завершен")
            else:
                logger.error(f"Сбор отчётов компани {market.name_company} прерван")
        else:
            logger.info(f"Сбор отчётов завершен")
    except Exception as e:
        logger.error(e)
    finally:
        db_conn_admin.session.close()
        db_conn_arris.session.close()


if __name__ == '__main__':
    main()
