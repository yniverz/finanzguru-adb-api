from dataclasses import dataclass
import datetime
import json
import sys
import threading
import time
import traceback
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import pytz
import requests
import uvicorn
from builtins import print as _print

from finanzguru import FinanzGuruClient

def print(*args, **kwargs):
    """
    Custom print function to add a timestamp to the output
    """
    time_now = datetime.datetime.now(pytz.timezone('Europe/Berlin'))
    time_str = time_now.strftime("%Y-%m-%d %H:%M:%S")
    _print(f"[{time_str}] ", end="")
    _print(*args, **kwargs)



@dataclass
class APIAccount:
    name: str
    balance: float = 0.0

@dataclass
class VirtualAccount:
    name: str
    data_url: str = ""
    json_balance_key_path: list[str] = []
    foreign_currency: str = ""

@dataclass
class Timing:
    start_hour: int = 22
    interval_hours: int = 24

@dataclass
class ServerSettings:
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

class Config:
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.timing: Timing = Timing()
        self.device_pin: str = ""
        self.server_settings: ServerSettings = ServerSettings()
        self.api_accounts: list[APIAccount] = []
        self.last_api_update: float = 0
        self.virtual_accounts: list[VirtualAccount] = []
        self.load()

    def api_accounts_dict(self) -> dict:
        return {account.name: account.balance for account in self.api_accounts}

    def load(self):
        with open(self.config_file, "r") as f:
            data: dict = json.load(f)
            self.timing = Timing(**data.get("timing", {}))
            self.device_pin = data.get("device_pin", "")
            self.server_settings = ServerSettings(**data.get("server_settings", {}))
            self.api_accounts = [APIAccount(name=name) for name in data.get("api_accounts", [])]
            self.virtual_accounts = [VirtualAccount(name=name, **acc) for name, acc in data.get("virtual_accounts", {}).items()]


class AccountManager:
    def __init__(self, config: Config = Config()):
        self.data = config
        self.guru = FinanzGuruClient(device_pin=config.device_pin)

    def update_api_account_balances(self):
        """
        Get the current balance of all API accounts
        :return: dict with account name as key and balance as value
        """

        self.guru.request_bank_update()

        for account in self.data.api_accounts:
            balance, _ = self.guru.get_account_current_app_balance(account.name)
            account.balance = balance
            print(f"Updated {account.name} balance: {balance}")

        self.data.last_api_update = time.time()

    def check_virtual_accounts(self):
        """
        Check if the virtual accounts are up to date
        :return: None
        """
        for account in self.data.virtual_accounts:
            try:
                r = requests.get(account.data_url)

                if r.status_code != 200:
                    raise Exception(f"Error: {r.status_code}")
                
                data = r.json()
                if account.json_balance_key_path:
                    for key in account.json_balance_key_path:
                        data = data[key]
                
                new_balance = data

                self.update_virtual_account(account, new_balance)
            
            except Exception as e:
                print(traceback.format_exc())
                time.sleep(2)
            
    def update_virtual_account(self, account: VirtualAccount, new_balance: float):
        OTHEReur_price = 1
        if account.foreign_currency:
            r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=EUR" + account.foreign_currency)
            if r.status_code != 200:
                raise Exception(f"Error getting foreign price: {r.status_code}")

            eurOTHER_price = float(r.json()["price"])
            OTHEReur_price = 1/eurOTHER_price

        new_balance = round(new_balance * OTHEReur_price, 2)

        self.guru.update_account_balance(account.name, new_balance, threshhold=10)

    def run(self, force_update: bool = False):
        """
        Run the account manager
        :return: None
        """
        
        while True:
            try:
                if not force_update:
                    print(f"Waiting for {self.data.timing.start_hour}:00...")
                    time_now = datetime.datetime.now(pytz.timezone('Europe/Berlin'))
                    while time_now.hour != self.data.timing.start_hour and time_now.minute != 0:
                        time.sleep(1)
                else:
                    print("Force update requested, skipping delay")
                    force_update = False

            except KeyboardInterrupt:
                print("Delay skipped, continuing in 5 seconds")
                time.sleep(5)

            try:
                self.guru.init_app()

                self.check_virtual_accounts()

                self.update_api_account_balances()

            except Exception as e:
                print(traceback.format_exc())
                time.sleep(2)

            time.sleep(120)



def run_server(manager_instance: AccountManager):
    global request_update_done

    app = FastAPI()

    @app.get("/accounts")
    def get_api_accounts():
        accounts = manager_instance.data.api_accounts_dict()
        accounts["last_update"] = manager_instance.data.last_api_update
        return JSONResponse(content=accounts)
    
    request_update_done = True
    @app.get("/request_update")
    def request_update():
        global request_update_done
        if request_update_done:
            request_update_done = False
            def update():
                global request_update_done
                manager_instance.update_api_account_balances()
                request_update_done = True
            
            threading.Thread(target=update, daemon=True).start()
            return JSONResponse(content={"status": "ok"})
        else:
            return JSONResponse(content={"status": "busy"}, status_code=429)
        
    @app.get("/update_running")
    def update_running():
        global request_update_done
        return JSONResponse(content={"status": "busy" if not request_update_done else "ok"})
    
    uvicorn.run(app, 
                host=manager_instance.data.server_settings.host, 
                port=manager_instance.data.server_settings.port, 
                log_level=manager_instance.data.server_settings.log_level)

if __name__ == "__main__":
    manager = AccountManager()

    server_thread = threading.Thread(target=run_server, args=(manager,), daemon=True)
    server_thread.start()

    # get passed argument from command line
    update_on_start = False
    if len(sys.argv) > 1:
        if sys.argv[1] == "force_update":
            update_on_start = True

    manager.run(force_update=update_on_start)


# Example config.json:
#
# {
#     "timing": {
#         "start_hour": 23,
#         "interval_hours": 24
#     },
#     "device_pin": "xxxxx",
#     "api_accounts": [
#         "Main Account",
#         "Online Payments",
#         "Subscriptions"
#     ],
#     "virtual_accounts": {
#         "Bybit Trader": {
#             "data_url": "https://xxxxxxxxxx.com/rawDetails",
#             "json_balance_key_path": ["balance"],
#             "foreign_currency": "USDT"
#         },
#         "IG Trader": {
#             "data_url": "https://xxxxxxxxxx.com/get_balance",
#             "json_balance_key_path": ["account", "balance"]
#         }
#     }
# }