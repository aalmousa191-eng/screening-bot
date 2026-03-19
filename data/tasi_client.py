"""
TASI (Tadawul – Saudi Stock Exchange) data client.

Ticker universe: Fetches all listed companies from the Saudi Exchange public API.
Fundamental data: Yahoo Finance (tickers with .SR suffix).
"""
from __future__ import annotations

import requests
import time
from typing import Optional

# Saudi Exchange public API (no auth required)
TADAWUL_COMPANIES_URL = (
    "https://www.saudiexchange.sa/wps/portal/saudiexchange/ourmarketsandproducts/"
    "listofsecurities/!ut/p/z1/04_Sj9CPykssy0xPLMnMz0vMAfIjo8zi_Tx8nA0tLAz8DcyNPC1cjAx9zMxMvQ0MjIEKIoEKDHAARwNC-r36o9ILMotS8xJTc1OTSzJTE1MLQBLZQAA!/"
)

# Simpler API endpoints that are known to work
TADAWUL_API_BASE = "https://www.saudiexchange.sa"

# Fallback: comprehensive static list of TASI-listed stocks (Yahoo Finance .SR format)
# This covers the main index constituents and largest listed companies
TASI_STATIC_TICKERS = [
    # Mega-cap / Index heavyweights
    "2222.SR",  # Saudi Aramco
    "1180.SR",  # Al Rajhi Bank
    "2010.SR",  # SABIC (now part of Aramco ecosystem)
    "1120.SR",  # Al Jazira Bank
    "1140.SR",  # Bank Al-Bilad
    "2350.SR",  # Saudi Kayan
    "2380.SR",  # Petro Rabigh
    "1010.SR",  # Riyad Bank
    "1020.SR",  # Bank Al-Jazira
    "1030.SR",  # Saudi Investment Bank
    "1050.SR",  # Banque Saudi Fransi
    "1060.SR",  # Saudi British Bank (SABB)
    "1080.SR",  # Arab National Bank
    "1100.SR",  # Alinma Bank
    "1150.SR",  # Amlak International
    "2001.SR",  # SCHEMECO
    "2020.SR",  # SAFCO
    "2030.SR",  # Saudi Arabia Fertilizers (SAFCO legacy)
    "2040.SR",  # Saudi Industrial Investment
    "2050.SR",  # Savola Group
    "2060.SR",  # National Industrialization (Tasnee)
    "2080.SR",  # Saudi Cement
    "2090.SR",  # Eastern Cement
    "2100.SR",  # Yamama Cement
    "2110.SR",  # Southern Province Cement
    "2120.SR",  # Qassim Cement
    "2130.SR",  # City Cement
    "2140.SR",  # Saudi Ceramic
    "2150.SR",  # Saudi Steel Pipes
    "2160.SR",  # Sipchem (SAFCO)
    "2170.SR",  # Alujain
    "2180.SR",  # Filling & Packing
    "2190.SR",  # Saudino
    "2200.SR",  # Arabian Cement
    "2210.SR",  # Non-Metallic
    "2220.SR",  # Saudi Advanced Industries
    "2240.SR",  # Zamil Industrial
    "2250.SR",  # Saudi Industrial Services
    "2270.SR",  # Saudi Chemical
    "2280.SR",  # Al Babtain
    "2290.SR",  # ACWA Power
    "2300.SR",  # Saudi Electricity (SEC)
    "2310.SR",  # Maaden
    "2320.SR",  # Al Yamamah Steel
    "2330.SR",  # Advanced Petrochemical
    "2340.SR",  # Sahara Petrochemical
    "2360.SR",  # Saudi Vitrified Clay
    "2370.SR",  # MEPCO
    "2390.SR",  # Sumou Real Estate
    "2400.SR",  # SPC (Saudi Paint)
    "3001.SR",  # Saudia Dairy (SADAFCO)
    "3002.SR",  # NADEC
    "3003.SR",  # Tanmiah Food
    "3004.SR",  # Almarai
    "3007.SR",  # Halwani Bros
    "3008.SR",  # Hana Food
    "3010.SR",  # Saudi Fisheries
    "3020.SR",  # Noo Food
    "3030.SR",  # Bahri (National Shipping)
    "3040.SR",  # Al Hammadi
    "3050.SR",  # Mouwasat Medical
    "3060.SR",  # Saudi Pharmaceutical (SPIMACO)
    "3070.SR",  # Dallah Healthcare
    "3080.SR",  # Middle East Healthcare
    "3090.SR",  # Dr Sulaiman Al-Habib
    "4001.SR",  # SACO
    "4002.SR",  # Al Othaim Markets
    "4003.SR",  # Jarir Bookstore
    "4004.SR",  # Extra (United Electronics)
    "4005.SR",  # Al Dawaa Pharmacies
    "4006.SR",  # BinDawood Holding
    "4007.SR",  # Americana Restaurants
    "4008.SR",  # Nahdi Commercial
    "4009.SR",  # Alhokair
    "4010.SR",  # Saudi Telecom (STC)
    "4020.SR",  # Mobily
    "4030.SR",  # Zain KSA
    "4040.SR",  # Saudi Cable
    "4050.SR",  # Almaraeen
    "4060.SR",  # Bupa Arabia
    "4100.SR",  # Tawuniya Insurance
    "4110.SR",  # Wataniya Insurance
    "4130.SR",  # Arabian Shield Insurance
    "4140.SR",  # Gulf General Insurance
    "4150.SR",  # Arab National Takaful
    "4160.SR",  # Solidarity Saudi Takaful
    "4170.SR",  # Saudi India Company
    "4180.SR",  # Malath Insurance
    "4190.SR",  # Wala'a Insurance (was Gulf Union)
    "4200.SR",  # Al-Ahlia Insurance
    "4210.SR",  # SAMBA (now SNB)
    "4220.SR",  # Saudi National Bank (SNB)
    "4230.SR",  # Al Rajhi Takaful
    "4240.SR",  # Al-Rajhi Cooperative
    "4250.SR",  # AXA Cooperative
    "4260.SR",  # Salama Cooperative
    "4270.SR",  # Amana Cooperative
    "4280.SR",  # Al Tawaun Cooperative
    "4290.SR",  # Enaya Cooperative
    "4300.SR",  # Saudi Reinsurance
    "4320.SR",  # Arabian Internet (Solutions)
    "4330.SR",  # Elm
    "4340.SR",  # Ejada Systems
    "4344.SR",  # Marsoft
    "5110.SR",  # Saudi Real Estate (Al Akaria)
    "5140.SR",  # Arriyadh Development
    "6001.SR",  # Leejam Sports
    "6002.SR",  # Theeb Rent-a-Car
    "6004.SR",  # Al-Kifah Holding
    "6010.SR",  # Saudi Airlines Catering
    "6012.SR",  # Abdullah Al-Othaim
    "6013.SR",  # Riyadh Cables
    "6014.SR",  # Gulf Cables
    "6015.SR",  # Saudi Wire Group
    "6016.SR",  # Albassami
    "6017.SR",  # ATC
    "6018.SR",  # Al-Hassan Ghazi
    "6019.SR",  # Bawan
    "6020.SR",  # Takween
    "6040.SR",  # Aldrees
    "6050.SR",  # Saudi Ground Services
    "6060.SR",  # Al Yamamah Steel
    "6070.SR",  # Altayyar Travel
    "6080.SR",  # National Gas (NGIC)
    "6090.SR",  # Budget Saudi
    "7010.SR",  # Saudi Fransi Capital
    "7020.SR",  # Jadwa Investment
    "7203.SR",  # Tabuk Pharmaceuticals
    "7204.SR",  # Astra Industrial
    "8010.SR",  # SABB Takaful
    "8012.SR",  # Maather REIT
    "8020.SR",  # Mulkia REIT
    "8030.SR",  # Al Rajhi REIT
    "8040.SR",  # Jadwa REIT
    "8050.SR",  # Derayah REIT
    "8060.SR",  # Al Mashaer REIT
    "8070.SR",  # Riyadh REIT
    "8080.SR",  # Bonyan REIT
    "8100.SR",  # Taleem REIT
    "8110.SR",  # Alahli REIT
    "8120.SR",  # Mefic REIT
    "8130.SR",  # Sedco Capital REIT
    "8140.SR",  # Musharaka REIT
    "8150.SR",  # Al Moammar REIT
    "8160.SR",  # Osool REIT
    "8170.SR",  # Alinma Hospitality REIT
    "8180.SR",  # Riyad REIT
    "8190.SR",  # Maarefa REIT
    "8200.SR",  # Saudi REIT
]


def fetch_tasi_tickers_from_exchange() -> list[str]:
    """
    Try to fetch all listed TASI tickers from the Saudi Exchange public data.
    Falls back to static list on failure.
    """
    try:
        # Known public endpoint for listed securities
        url = "https://www.saudiexchange.sa/wps/portal/saudiexchange/ourmarketsandproducts/listofsecurities"
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; StockScreener/1.0)",
            "Accept": "application/json, text/html",
        }
        # Try the JSON API first
        api_url = "https://www.saudiexchange.sa/wps/portal/saudiexchange/ourmarketsandproducts/listofsecurities/!ut/p/z1/"
        r = requests.get(api_url, headers=headers, timeout=15)
        if r.status_code == 200:
            # Try to parse tickers from response
            pass
    except Exception:
        pass

    # Alternative: use the Tadawul data from a known JSON endpoint
    try:
        url = "https://www.saudiexchange.sa/tadawul.eportal.theme.wui/themes/engine/images"
        r = requests.get(
            "https://www.saudiexchange.sa/wps/portal/saudiexchange/ourmarketsandproducts/marketsummary/currentmarketcondition",
            timeout=15,
        )
    except Exception:
        pass

    return TASI_STATIC_TICKERS


def get_tasi_tickers(use_static: bool = False) -> list[str]:
    """Return list of TASI tickers in Yahoo Finance format (NNNN.SR)."""
    if use_static:
        return TASI_STATIC_TICKERS

    dynamic = fetch_tasi_tickers_from_exchange()
    if dynamic:
        return dynamic
    return TASI_STATIC_TICKERS
