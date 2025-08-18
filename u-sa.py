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

APP_VERSION = "0.0.1"

# config.json, token.json, businesdate.json
JSON_CONFIG_PATH = "config.json" 
JSON_TOKEN_PATH = "token.json"
JSON_BUSINESS_DATE_PATH = "businesdate.json"

# 실전투자 url
BASE_URL = "https://openapi.koreainvestment.com:9443"

# 매수용 종목 코드 목록
SIMBOL_LIST = [
    "360750",
] 

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
        # {
        #     "ctx_area_nk": "20250823            ",
        #     "ctx_area_fk": "20250731            ",
        #     "output": 
        #         [
        #                 {
        #                 "bass_dt": "20250731",
        #                 "wday_dvsn_cd": "05",
        #                 "bzdy_yn": "Y",
        #                 "tr_day_yn": "Y",
        #                 "opnd_yn": "Y",
        #                 "sttl_day_yn": "Y"
        #                 },
        #                 {
        #                 "bass_dt": "20250801",
        #                 "wday_dvsn_cd": "06",
        #                 "bzdy_yn": "Y",
        #                 "tr_day_yn": "Y",
        #                 "opnd_yn": "Y",
        #                 "sttl_day_yn": "Y"
        #                 },
        #                 ........
        #                 {
        #                 "bass_dt": "20250823",
        #                 "wday_dvsn_cd": "07",
        #                 "bzdy_yn": "N",
        #                 "tr_day_yn": "Y",
        #                 "opnd_yn": "N",
        #                 "sttl_day_yn": "N"
        #                 }
        #         ],
        #     "rt_cd": "0",
        #     "msg_cd": "KIOK0500",
        #     "msg1": "조회가 계속됩니다..다음버튼을 Click 하십시오.                                   "
        # }
        if not os.path.exists(self.json_business_date_path):
            with open(self.json_business_date_path, "w", encoding="utf-8") as f:
                business_date_data = {
                    "ctx_area_nk": "",
                    "ctx_area_fk": "",
                    "output": [],
                    "rt_cd": "0",
                    "msg_cd": "KIOK0500",
                    "msg1": ""
                }
                json.dump(business_date_data, f, ensure_ascii=False, indent=2)
        else:
            with open(self.json_business_date_path, "r", encoding="utf-8") as f:
                self.business_date_data = json.load(f)

    # OAuth인증
    def get_hashkey(self, data: dict):
        """
        Name:Hashkey
        Args:
            data (dict): POST 요청 데이터
        Returns:
            haskkey
        """
        path = "/uapi/hashkey"
        url = f"{self.base_url}{path}"
        headers = {
           "content-type": "application/json",
           "appKey": self.app_key,
           "appSecret": self.app_secret,
           "User-Agent": "Mozilla/5.0"
        }
        resp = requests.post(url, headers=headers, data=json.dumps(data))
        haskkey = resp.json()["HASH"]
        return haskkey
    
    def get_access_token(self) -> bool:
        """
        Name:접근토큰발급
        """
        path = "/oauth2/tokenP"
        url = f"{self.base_url}{path}"

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
            dict: 
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

    # 24일치 영엽일 확인 가능함
    # {
    #     "ctx_area_nk": "20250611            ",
    #     "ctx_area_fk": "20250519            ",
    #     "output": [
    #         {
    #             "bass_dt": "20250519",        
    #             "wday_dvsn_cd": "02",
    #             "bzdy_yn": "Y",
    #             "tr_day_yn": "Y",
    #             "opnd_yn": "Y",
    #             "sttl_day_yn": "Y"
    #         },
    #         ........
    #         {
    #             "bass_dt": "20250611",
    #             "wday_dvsn_cd": "04",
    #             "bzdy_yn": "Y",
    #             "tr_day_yn": "Y",
    #             "opnd_yn": "Y",
    #             "sttl_day_yn": "Y"
    #         }
    #     ],
    #     "rt_cd": "0",
    #     "msg_cd": "KIOK0500",
    #     "msg1": "조회가 계속됩니다..다음버튼을 Click 하십시오.                                   "
    # }
    def get_domestic_chk_holiday(self, base_dt=None, ctx_area_fk: str = "", ctx_area_nk: str = ""):
        """
        Name:국내휴장일조회
        가능 하면 하루에 한번만 요청
        모의투자 미지원
        default today YYYYMMDD
        Args:
            ctx_area_fk (str): 공란
        """
        print("get_domestic_chk_holiday")
        path = "/uapi/domestic-stock/v1/quotations/chk-holiday"
        url = f"{self.base_url}{path}"
        headers = {
           "content-type": "application/json",
           "authorization": self.authorization,
           "appKey": self.app_key,
           "appSecret": self.app_secret,
           "tr_id": "CTCA0903R"
        }

        if base_dt is None:
            base_dt = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d")   # 시작일자 값이 없으면 현재일자
        
        params = {
            'BASS_DT': base_dt,
            "CTX_AREA_FK": ctx_area_fk,  # 공란
            "CTX_AREA_NK": ctx_area_nk  # 공란
        }

        res = requests.get(url, headers=headers, params=params)
        data = res.json()
        self.business_date_data = data
        
        with open(self.json_business_date_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return data
    
    def get_today_opnd_yn(self) -> str | None:
        """
        Name:오늘 국내휴장일조회 :: 국내휴장일조회 api 응용
        """
        try:
            # 오늘 날짜 (Asia/Seoul 기준) yyyyMMdd 형식으로 구함
            today_str = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d")
            print(f"오늘은 : {today_str} : get_today_opnd_yn")

            # output 리스트를 순회하면서 오늘 날짜에 해당하는 데이터 찾기
            # 메모리 확인
            if not self.business_date_data:
                # 메모리에 없으면 요청 - 오늘 기준
                print("[1] 메모리에 없으면 요청")
                self.get_domestic_chk_holiday(base_dt=today_str,ctx_area_fk="",ctx_area_nk="")

            tmp_data = self.business_date_data
            tmp_output = tmp_data.get("output")
            # output 정보 확인
            # 빈 파일을 로드 한 경우 또는 output 없는 경우
            if not tmp_output:
                # output 정보가 없으면 다시 요청 - 오늘 기준
                print("[2] output 정보가 없으면 다시 요청")
                self.get_domestic_chk_holiday(base_dt=today_str,ctx_area_fk="",ctx_area_nk="")
            else:
                pass
            
            data = self.business_date_data
            for item in data.get("output", []):
                if item.get("bass_dt") == today_str:
                    print("[3] 오늘 정보 있음")
                    return item.get("opnd_yn")
                
            # 오늘에 대한 정보가 없는 경우 - 로드한 data가 오래된 경우
            # 다시 요청
            self.get_domestic_chk_holiday(base_dt=today_str,ctx_area_fk="",ctx_area_nk="")
            
            # 다시 한번 확인
            data = self.business_date_data
            for item in data.get("output", []):
                if item.get("bass_dt") == today_str:
                    print("[4] 오늘 정보 있음")
                    return item.get("opnd_yn")
            
            # 못찾으면 None 리턴
            print("[5] 오늘 정보 없음")
            return None
        except Exception as e:
            # 예외 처리
            print("[6] 예외")
            print(f"{e}")
            return None
    
    """
    {
        'output': 
            {
                'pdno': '360750', 
                'prdt_name': 'TIGER 미국S&P500', 
                'buy_qty': '0', 
                'sll_qty': '0', 
                'cblc_qty': '2', 
                'nsvg_qty': '0', 
                'ord_psbl_qty': '2', 
                'pchs_avg_pric': '22020.0000', 
                'pchs_amt': '44040', 
                'now_pric': '22145', 
                'evlu_amt': '44290', 
                'evlu_pfls_amt': '250', 
                'evlu_pfls_rt': '0.56'
            }, 
        'rt_cd': '0', 
        'msg_cd': 'KIOK0420', 
        'msg1': '정상적으로 조회되었습니다                                                       '
    }
    """
    def get_domestic_psbl_sell(self, symbol: str):
        """
        Name:매도가능수량조회
        Args:
            symbol (str): 종목코드
        """
        path = "/uapi/domestic-stock/v1/trading/inquire-psbl-sell"
        url = f"{self.base_url}{path}"
        headers = {
           "content-type": "application/json",
           "authorization": self.authorization,
           "appKey": self.app_key,
           "appSecret": self.app_secret,
           "tr_id": "TTTC8408R"
        }
        params = {
            'CANO': self.account_no_prefix,
            'ACNT_PRDT_CD': self.account_no_postfix,
            'PDNO': symbol
        }

        res = requests.get(url, headers=headers, params=params)
        data = res.json()
        # ord_psbl_qty 에서 확인 가능

        return data
    
    
    def set_domestic_order_cash(self, side: str, symbol: str, price: int,
                     quantity: int, order_type: str) -> dict:
        """
        Name:주식주문(현금)

        Args:
            side (str): 매수 "buy" 또는 매도(else, "", "sell")
            symbol (str): 종목코드
            price (int): 가격
            quantity (int): 수량
            order_type (str): 00(지정가), 01(시장가)

        Returns:
            dict: 
        """
        path = "/uapi/domestic-stock/v1/trading/order-cash"
        url = f"{self.base_url}{path}"

        # 매수 : TTTC0012U (구버전 TTTC0802U)
        # 매도 : TTTC0011U (구버전 TTTC0801U)
        tr_id = "TTTC0012U" if side == "buy" else "TTTC0011U"

        # 주문 단가 : 시장가 주문시 0으로 설정
        unpr = "0" if order_type == "01" else str(price)

        data = {
            "CANO": self.account_no_prefix,
            "ACNT_PRDT_CD": self.account_no_postfix,
            "PDNO": symbol,
            "ORD_DVSN": order_type,
            "ORD_QTY": str(quantity),
            "ORD_UNPR": unpr
        }
        hashkey = self.get_hashkey(data)
        headers = {
           "content-type": "application/json",
           "authorization": self.authorization,
           "appKey": self.app_key,
           "appSecret": self.app_secret,
           "tr_id": tr_id,
           "custtype": "P",
           "hashkey": hashkey
        }
        resp = requests.post(url, headers=headers, data=json.dumps(data))
        return resp.json()

    def set_market_price_buy_order(self, symbol: str, quantity: int) -> dict:
        """
        Name:시장가 매수

        Args:
            symbol (str): 종목코드
            quantity (int): 수량

        Returns:
            dict: 
        """
        resp = self.set_domestic_order_cash("buy", symbol, 0, quantity, "01")
        return resp


    def set_market_price_sell_order(self, symbol: str, quantity: int) -> dict:
        """
        Name:시장가 매도

        Args:
            symbol (str): 종목코드
            quantity (int): 수량

        Returns:
            dict: 
        """
        resp = self.set_domestic_order_cash("sell", symbol, 0, quantity, "01")
        
        return resp

    def set_limit_price_buy_order(self, symbol: str, price: int, quantity: int) -> dict:
        """
        Name:지정가 매수

        Args:
            symbol (str): 종목코드
            price (int): 가격
            quantity (int): 수량

        Returns:
            dict: 
        """
        resp = self.set_domestic_order_cash("buy", symbol, price, quantity, "00")
        
        return resp

    def set_limit_price_sell_order(self, symbol: str, price: int, quantity: int) -> dict:
        """
        Name:지정가 매도

        Args:
            symbol (str): 종목코드
            price (int): 가격
            quantity (int): 수량

        Returns:
            dict: _description_
        """
        resp = self.set_domestic_order_cash("sell", symbol, price, quantity, "00")
        return resp
    
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
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 테스트 실행")

        # 1. 로그인
        is_valid = self.kis_api.get_access_token()
        
        if not is_valid:
            print("로그인 실패 : do_trading")
            return

        # 2. 매도 가능 수량 확인 테스트
        res_json_psbl_sell = self.kis_api.get_domestic_psbl_sell("360750")
        print("get_domestic_psbl_sell 360750")
        print(res_json_psbl_sell)

        rt_cd = res_json_psbl_sell['rt_cd']
        ord_psbl_qty = 0
        if rt_cd == '0':
            output = res_json_psbl_sell['output']
            ord_psbl_qty = int(output['ord_psbl_qty'])
            print(ord_psbl_qty)

        # 3. 매도 테스트
        # resp_sell_order = self.kis_api.set_market_price_sell_order(symbol="360750",quantity=ord_psbl_qty)
        # rt_cd_sell_order = resp_sell_order['rt_cd']
        # if rt_cd_sell_order == '0':
        #     print("시장가 매도 주문 성공")
        # else:
        #     print("시장가 매도 주문 실패")

        # print(resp_sell_order)

    def do_balance(self):
        print(f"잔고조회 실행 version : {APP_VERSION}")

        # 로그인
        is_valid = self.kis_api.get_access_token()
        
        if not is_valid:
            print("로그인 실패 : do_balance")
            return
        
        time.sleep(1)
        
        # 잔고조회
        balance = self.kis_api.get_domestic_balance_all()
        Utill.print_balance(balance)
        time.sleep(1)

        return

    # 자동매매 실행
    # 1. 로그인
    # 2. 휴일 확인
    # 3. 영엽시간 확인
    # 4. 매도
    # 4-0 익절 5%
    # 4-1 잔고 조회
    # 4-2 익절 종목 선정
    # 4-3 매도 가능 수량 조회
    # 4-4 시장가 매도
    # 5. 매수
    # 5-0 매일 1주 매수 in SIMBOL_LIST
    # 5-1 주문체결 조회
    # 5-2 오늘 매수하지 않은 종목 선정
    # 5-3 시장가 매수
    def do_trading(self):
        # 현재 시간 (서울 기준)
        # now는 Asia/Seoul 타임존 기준
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 자동매매 실행")

        # 1. 로그인
        is_valid = self.kis_api.get_access_token()
        
        if not is_valid:
            print("로그인 실패 : do_trading")
            return
        
        time.sleep(0.5)

        # 2. 휴일 확인
        open_yn = self.kis_api.get_today_opnd_yn()
        if open_yn is None:
            print(f"확인 실패 : open_yn=None")
            return
        elif open_yn != 'Y':
            print(f"휴일 : open_yn={open_yn}")
            return
        else:
            print(f"영업일 : open_yn={open_yn}")
            pass

        time.sleep(0.5)

        # 3. 영업시간 확인
        current_time = now.time()

        start_time = dtime(9, 00)   # 비교값도 타임존 없이 정의
        end_time = dtime(15, 20)

        if start_time < current_time < end_time:
            print("영업시간입니다.")
        else:
            print("영업시간이 아닙니다.")
            return

        # 4. 매도 
        # 4-0 익절 5%
        # 4-1 잔고 조회
        # 4-2 익절 종목 선정
        # 4-3 매도 가능 수량 조회
        # 4-4 시장가 매도

        # 4-1 잔고 조회
        balance = self.kis_api.get_domestic_balance_all()
            
        # 매도 대상 종목 저장용 list
        sell_pdno_list = []
        no_i = 0
        for item in balance["output1"]:
            no_i = no_i + 1
            # print(f"{'NO'.ljust(10, chr(12288))}: {no_i}")
            # print(f"{'종목번호'.ljust(10, chr(12288))}: {item['pdno']}")
            # print(f"{'종목명'.ljust(10, chr(12288))}: {item['prdt_name']}")
            # print(f"{'보유수량'.ljust(10, chr(12288))}: {int(item['hldg_qty']):,}")
            # print(f"{'평가손익율'.ljust(10, chr(12288))}: {item['evlu_pfls_rt']}")
            # print("----------------")

            # 4-2 익절 종목 선정
            evlu_rt = float(item['evlu_pfls_rt'])
            if evlu_rt > 5.0:
                # 5% 이상 종목 저장
                sell_pdno_list.append(item['pdno'])
        
        time.sleep(0.5)

        # 4-3 매도 가능 수량 조회 : 익절 종목을 대상으로
        for i_symbol in sell_pdno_list:
            print(f"{'매도종목'.ljust(10, chr(12288))}: {i_symbol}")
            
            # 4-3 매도 가능 수량 조회
            res_json_psbl_sell = self.kis_api.get_domestic_psbl_sell(i_symbol)

            rt_cd = res_json_psbl_sell['rt_cd']
            ord_psbl_qty = 0
            if rt_cd == '0':
                output = res_json_psbl_sell['output']
                ord_psbl_qty = int(output['ord_psbl_qty'])

            time.sleep(0.5)

            # 4-4 시장가 매도
            # 매도 가능 수량이 있으면 시장가 매도
            if ord_psbl_qty > 0:
                resp_sell_order = self.kis_api.set_market_price_sell_order(symbol=i_symbol,quantity=ord_psbl_qty)
                rt_cd_sell_order = resp_sell_order['rt_cd']
                if rt_cd_sell_order == '0':
                    print("시장가 매도 주문 성공")
                else:
                    print("시장가 매도 주문 실패")

                time.sleep(0.5)

        # 매도 끝

        # 5. 매수
        # 5-0 매일 1주 매수 in SIMBOL_LIST
        # 5-1 주문체결 조회
        # 5-2 오늘 매수하지 않은 종목 선정
        # 5-3 시장가 매수
        return
        
if __name__ == '__main__':
    print("u-sa-v0001")
    print("__main__")
    try:
        usa_tray = UsaTray()
        usa_tray.run()
    except Exception as e:
        print(f"[오류] 프로그램을 종료합니다: {e}")
        