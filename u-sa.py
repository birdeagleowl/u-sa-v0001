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
import requests

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
    
    def get_access_token(self) -> bool:
        """
        Name:접근토큰발급
        """
        path = "oauth2/tokenP"
        url = f"{self.base_url}/{path}"

        headers = {"content-type": "application/json"}
        data = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }

        if self.is_expired():

            # 토큰 발급
            resp = requests.post(url, headers=headers, data=json.dumps(data))
            resp_status_code = resp.status_code
            if resp_status_code == 200: # 토큰 정상발급
                # 토큰 추출
                resp_access_token = resp.json()["access_token"]
                self.access_token_token_expired = resp.json()["access_token_token_expired"]
                self.access_token = resp_access_token
                # header에 지정할 때 Bearer를 추가 해야 하는데 여기서 한다.
                # Bearer를 추가하는 경우는 authorization
                # Bearer가 없는 경우는 access_token
                self.authorization = f'Bearer {resp_access_token}'

                with open(self.json_token_path, "w", encoding="utf-8") as f:
                        json.dump({
                            "authorization": self.authorization,
                            "access_token": self.access_token,
                            "access_token_token_expired": self.access_token_token_expired
                        }, f, indent=2, ensure_ascii=False)
                
                
                return True
            else:
                self.authorization = ""
                self.access_token = ""
                self.access_token_token_expired = ""
                return False
        else:
            return True
    
    def is_expired(self) -> bool:
        try:
            if not self.access_token or not self.access_token.strip():
                return True
            
            # 2025-05-20 14:10:40 한국시간이 기준이다.
            now_dt = datetime.now(ZoneInfo("Asia/Seoul"))
            exp_dt = datetime.strptime(self.access_token_token_expired, '%Y-%m-%d %H:%M:%S')
            exp_dt = exp_dt.replace(tzinfo=ZoneInfo("Asia/Seoul"))
            return now_dt > exp_dt
            
        except Exception:
            # 예외 발생 시 만료로 간주
            return True

    # [국내주식] 주문/계좌
    def get_domestic_balance(self, ctx_area_fk100: str = "", ctx_area_nk100: str = "") -> dict:
        """
        Name:주식잔고조회
        Args:
            ctx_area_fk100 (str): 연속조회검색조건100
            공란 : 최초 조회시 
            이전 조회 Output CTX_AREA_FK100 값 : 다음페이지 조회시(2번째부터)
            ctx_areak_nk100 (str): 연속조회키100
        Returns:
            실전: 최대 50건 이후 연속조회
            모의: 최대 20건 이후 연속조회
            dict: _description_
        """
        path = "/uapi/domestic-stock/v1/trading/inquire-balance"
        url = f"{self.base_url}{path}"
        headers = {
           "content-type": "application/json",
           "authorization": self.authorization,
           "appKey": self.app_key,
           "appSecret": self.app_secret,
           "tr_id": "TTTC8434R"
        }
        params = {
            'CANO': self.account_no_prefix,
            'ACNT_PRDT_CD': self.account_no_postfix,
            'AFHR_FLPR_YN': 'N',
            'OFL_YN': 'N',
            'INQR_DVSN': '02', # INQR_DVSN 01: 대출일별, 02:종목별
            'UNPR_DVSN': '01',
            'FUND_STTL_ICLD_YN': 'N',
            'FNCG_AMT_AUTO_RDPT_YN': 'N',
            'PRCS_DVSN': '01',
            'CTX_AREA_FK100': ctx_area_fk100,
            'CTX_AREA_NK100': ctx_area_nk100
        }

        res = requests.get(url, headers=headers, params=params)
        data = res.json()
        # tr_cont 연속 거래 여부
        # F or M : 다음 데이터 있음
        # D or E : 마지막 데이터
        data['tr_cont'] = res.headers['tr_cont']
        return data
    
    def get_domestic_balance_all(self) -> dict:
        """
        Name:주식잔고조회

        Args:

        Returns:
            dict: response data
        """
        output = {}

        data = self.get_domestic_balance()

        output['output1'] = data['output1']
        output['output2'] = data['output2']

        # 연속 조회
        while data['tr_cont'] == 'M':
            fk100 = data['ctx_area_fk100']
            nk100 = data['ctx_area_nk100']

            data = self.get_domestic_balance(fk100, nk100)
            output['output1'].extend(data['output1'])
            output['output2'].extend(data['output2'])

        return output


class Utill:
    '''
    utill 클래스
    기타 보조 도구 클래스
    '''
    def __init__(self):
        pass

    def print_balance(jsonOrDict):
        try:

            # JSON 형식의 문자열인지 확인
            if isinstance(jsonOrDict, str):
                parsed = json.loads(jsonOrDict)
            # 딕셔너리인지 확인
            elif isinstance(jsonOrDict, dict):
                parsed = jsonOrDict
            else:
                raise TypeError("Input must be a JSON string or a dictionary.")
            
            for item in parsed["output1"]:
                print(f"{'종목번호'.ljust(10, chr(12288))}: {item['pdno']}")
                print(f"{'종목명'.ljust(10, chr(12288))}: {item['prdt_name']}")
                print(f"{'보유수량'.ljust(10, chr(12288))}: {int(item['hldg_qty']):,}")
                print(f"{'매입평균가격'.ljust(10, chr(12288))}: {float(item['pchs_avg_pric']):,.2f}")
                print(f"{'매입금액'.ljust(10, chr(12288))}: {int(item['pchs_amt']):,}")
                print(f"{'현재가'.ljust(10, chr(12288))}: {int(item['prpr']):,}")
                print(f"{'평가금액'.ljust(10, chr(12288))}: {int(item['evlu_amt']):,}")
                print(f"{'평가손익금액'.ljust(10, chr(12288))}: {int(item['evlu_pfls_amt']):,}")
                print(f"{'평가손익율'.ljust(10, chr(12288))}: {item['evlu_pfls_rt']}")
                print("----------------")
            print(" ")
            for item in parsed["output2"]:
                print(f"{'D+2 예수금'.ljust(12, chr(12288))}: {int(item['prvs_rcdl_excc_amt']):,}")
                print(f"{'총평가금액'.ljust(10, chr(12288))}: {int(item['tot_evlu_amt']):,}")
                print(f"{'매입금액합계금액'.ljust(10, chr(12288))}: {int(item['pchs_amt_smtl_amt']):,}")
                print(f"{'평가금액합계금액'.ljust(10, chr(12288))}: {int(item['evlu_amt_smtl_amt']):,}")
                print(f"{'평가손익합계금액'.ljust(10, chr(12288))}: {int(item['evlu_pfls_smtl_amt']):,}")


        except json.JSONDecodeError as e:
            print(f"Invalid JSON: {e}")
        except TypeError as e:
            print(f"TypeError: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")


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
        if not self.symbols:
            raise ValueError("종목 코드는 비어 있을 수 없습니다. symbols")
            
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

        # 로그인
        is_valid = self.kis_api.get_access_token()
        
        if not is_valid:
            print("fail get_access_token : do_balance")
            return
        
        time.sleep(1)
        
        # 잔고조회
        balance = self.kis_api.get_domestic_balance_all()
        Utill.print_balance(balance)
        time.sleep(1)

        return

    def do_trading(self):
        # 현재 시간 (서울 기준)
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 자동매매 실행")
        return
        
if __name__ == '__main__':
    print("u-sa-v0001")
    print("__main__")
    try:
        usa_tray = UsaTray()
        usa_tray.run()
    except Exception as e:
        print(f"[오류] 프로그램을 종료합니다: {e}")
        