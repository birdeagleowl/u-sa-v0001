import json
import os
from PIL import Image, ImageDraw, UnidentifiedImageError
from pystray import Icon, MenuItem, Menu
import schedule
import threading
import time # sleep
from datetime import datetime
from datetime import time as dtime
from zoneinfo import ZoneInfo

# config.json, token.json, businesdate.json
JSON_CONFIG_PATH = "config.json" 
JSON_TOKEN_PATH = "token.json"
JSON_BUSINESS_DATE_PATH = "businesdate.json"

# 실전투자 url
BASE_URL = "https://openapi.koreainvestment.com:9443"

class KisApi:
    '''
    한국투자증권 REST API
    '''
    def __init__(self, app_key: str, app_secret: str, account_no: str):
        """
        Name:생성자
        Args:
            app_key (str): 발급받은 API key
            app_secret (str): 발급받은 API secret
            account_no (str): 계좌번호 체계의 앞 8자리-뒤 2자리
        """
        print("KisApi __init__")

        # 필수 값 검사
        if not app_key:
            raise ValueError("API Key는 비어 있을 수 없습니다.")
        if not app_secret:
            raise ValueError("API Secret은 비어 있을 수 없습니다.")
        if '-' not in account_no:
            raise ValueError("계좌번호 형식이 잘못되었습니다. 예: '12345678-01'")
        
        # base url
        self.base_url = BASE_URL

        # api key
        self.app_key = app_key
        self.app_secret = app_secret

        # account number
        self.account_no = account_no
        self.account_no_prefix = account_no.split('-')[0]
        self.account_no_postfix = account_no.split('-')[1]

        # json file
        self.json_token_path = JSON_TOKEN_PATH
        self.json_business_date_path = JSON_BUSINESS_DATE_PATH

        self.authorization = ""
        self.access_token = ""
        self.access_token_token_expired = ""
        self.load_json_token()

        # {"output": []}
        self.business_date_data = None
        self.load_json_business_date()

    def load_json_token(self):
        if not os.path.exists(self.json_token_path):
            with open(self.json_token_path, "w", encoding="utf-8") as f:
                # access_token: str # 접근토큰
                # token_type: str # 접근토큰유형 > 사용안함
                # expires_in: float # 접근토큰 유효기간 > 사용안함
                # access_token_token_expired: str #접근토큰 유효기간(일시표시)
                # authorization: str # Bearer + access_token
                token_data = {
                    "authorization": "",
                    "access_token": "",
                    # "token_type": "",
                    # "expires_in": 0.0,
                    "access_token_token_expired": ""
                }
                json.dump(token_data, f, ensure_ascii=False, indent=2)
        else:
            with open(self.json_token_path, "r", encoding="utf-8") as f:
                token_data = json.load(f)
                self.authorization = token_data.get("authorization","")
                self.access_token = token_data.get("access_token","")
                self.access_token_token_expired = token_data.get("access_token_token_expired","")

    def load_json_business_date(self):
        if not os.path.exists(self.json_business_date_path):
            with open(self.json_business_date_path, "w", encoding="utf-8") as f:
                # "output": [
                # bass_dt: str    #기준일자
                # wday_dvsn_cd: str    #요일구분코드
                # bzdy_yn: str    #영업일여부
                # tr_day_yn: str    #거래일여부
                # opnd_yn: str    #개장일여부
                # sttl_day_yn: str    #결제일여부
                #]

                # {"output": []}
                business_date_data = {
                    "output": []
                }
                json.dump(business_date_data, f, ensure_ascii=False, indent=2)
        else:
            with open(self.json_business_date_path, "r", encoding="utf-8") as f:
                self.business_date_data = json.load(f)

class UsaTray:
    '''
    main 클래스
    유저 인터페이스: 시스템 트레이
    매매 자동화
    매매 판단 알고리즘
    '''
    def __init__(self, app_name:str = "u-sa", icon_path: str = "./favicon.ico"):
        """
        Name:생성자
        Args:
            app_name (str): 앱 이름 u-sa
            icon_path (str): 트레이 아이콘 이미지 경로 ./favicon.ico
        """
        print("UsaTray __init__")
        # schedule loop status run or stop
        # False = stop or quit
        # True = run
        self.schedule_is_run = False

        # json file
        self.json_config_path = JSON_CONFIG_PATH
        self.app_key = ""
        self.app_secret = ""
        self.account_no = ""
        self.symbols = None
        self.load_json_config()
        
        # KisApi 생성
        self.kis_api = KisApi(
            app_key=self.app_key,
            app_secret=self.app_secret,
            account_no=self.account_no
        )

        self.app_name = app_name
        self.icon_path = icon_path
        image = self.get_icon_image()

        # 트레이 메뉴 구성
        menu = Menu(
            MenuItem('테스트', self.do_test),
            MenuItem('', None, enabled=False),
            MenuItem('잔고조회', self.do_balance),
            MenuItem('', None, enabled=False),
            MenuItem('종료', self.stop),
        )

        # 트레이 아이콘 생성
        self.icon = Icon(name=app_name, title=app_name, icon=image, menu=menu)

    def load_json_config(self):
        if os.path.exists(self.json_config_path):
            with open(self.json_config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                self.app_key = config_data.get("app_key","")
                self.app_secret = config_data.get("app_secret","")
                self.account_no = config_data.get("account_no","")
                self.symbols = config_data.get("symbols",None)
        else:
            raise FileNotFoundError("config.json 파일이 없습니다.")
        
        # 필수 값 검사
        if not self.app_key or not self.app_key.strip():
            raise ValueError("APP Key는 비어 있을 수 없습니다. app_key")
        if not self.app_secret or not self.app_secret.strip():
            raise ValueError("APP Secret은 비어 있을 수 없습니다. app_secret")
        if not self.account_no or not self.account_no.strip():
            raise ValueError("Account No 계좌번호는 비어 있을 수 없습니다. account_no")
        if '-' not in self.account_no:
            raise ValueError("계좌번호 형식이 잘못되었습니다. account_no 예: '12345678-01'")
        if self.symbols is None or not self.symbols:
            raise KeyError("종목 코드는 비어 있을 수 없습니다. symbols")
            
    def get_icon_image(self):
        try:
            return Image.open(self.icon_path)
        except (FileNotFoundError, UnidentifiedImageError):
            print(f"아이콘 파일을 찾을 수 없어 기본 아이콘을 사용합니다: {self.icon_path}")
            
            # 기본 아이콘 생성 (흰 배경)
            image = Image.new('RGB', (64, 64), (255, 255, 255))
            draw = ImageDraw.Draw(image)

            # 우상향 화살표 (빨간색)
            # 몸통 (대각선)
            draw.line((16, 48, 48, 16), fill=(255, 0, 0), width=5)

            # 화살촉 (역 V자)
            draw.line((40, 16, 48, 16), fill=(255, 0, 0), width=5)
            draw.line((48, 16, 48, 24), fill=(255, 0, 0), width=5)

            return image

    def run(self):
        # 현재 시간 (서울 기준)
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 시작합니다")

        # scheudle에서 실행할 작업 지정
        # 10분마다 작업
        schedule.every(10).minutes.do(self.do_trading)

        # schedule 상태
        self.schedule_is_run = True

        # schedule용 쓰레드 실행
        task_thread = threading.Thread(target=self.run_schedule)
        task_thread.daemon = True # 메인 스레드가 종료되면 함께 종료
        task_thread.start()

        # 트레이
        self.icon.run()

    def run_schedule(self):
        print("스케줄 실행.")
        # schedule 루프: 주기적인 작업을 실행
        while self.schedule_is_run:
            schedule.run_pending() # 실행해야 할 작업이 있는지 확인
            time.sleep(1)  # 반드시 있어야 함 (CPU 낭비 방지)
        

    def stop(self):
        # 현재 시간 (서울 기준)
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 종료합니다")
        self.schedule_is_run = False
        self.icon.stop()

    def do_test(self):
        print("테스트 기능 실행")

    def do_balance(self):
        print("잔고조회 실행")

    def do_trading(self):
        # 현재 시간 (서울 기준)
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 자동매매 실행")
        
if __name__ == '__main__':
    print("u-sa-v0001")
    print("__main__")
    try:
        usa_tray = UsaTray()
        usa_tray.run()
    except Exception as e:
        print(f"[오류] 프로그램을 종료합니다: {e}")
        