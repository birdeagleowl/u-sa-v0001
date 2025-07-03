import json
import os
from PIL import Image, ImageDraw, UnidentifiedImageError
from pystray import Icon, MenuItem, Menu


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
    def __init__(self, api_key: str, api_secret: str, acc_no: str):
        """
        Name:생성자
        Args:
            api_key (str): 발급받은 API key
            api_secret (str): 발급받은 API secret
            acc_no (str): 계좌번호 체계의 앞 8자리-뒤 2자리
        """
        print("KisApi __init__")

        # 필수 값 검사
        if not api_key:
            raise ValueError("API Key는 비어 있을 수 없습니다.")
        if not api_secret:
            raise ValueError("API Secret은 비어 있을 수 없습니다.")
        if '-' not in acc_no:
            raise ValueError("계좌번호 형식이 잘못되었습니다. 예: '12345678-01'")
        
        # base url
        self.base_url = BASE_URL

        # api key
        self.api_key = api_key
        self.api_secret = api_secret

        # account number
        self.acc_no = acc_no
        self.acc_no_prefix = acc_no.split('-')[0]
        self.acc_no_postfix = acc_no.split('-')[1]

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

        # KisApi 생성
        self.kis_api = KisApi("1","1","-")

        self.app_name = app_name
        self.icon_path = icon_path
        image = self._get_icon_image()

        # 트레이 메뉴 구성
        menu = Menu(
            MenuItem('테스트', self.do_test),
            MenuItem('', None, enabled=False),
            MenuItem('종료', self.stop),
        )

        # 트레이 아이콘 생성
        self.icon = Icon(name=app_name, title=app_name, icon=image, menu=menu)

    def _get_icon_image(self):
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

    def do_test(self, icon, item):
        print("테스트 기능 실행")

    def stop(self, icon, item):
        print("종료합니다.")
        self.icon.stop()

    def run(self):
        print("시작합니다.")
        self.icon.run()
        
if __name__ == '__main__':
    print("u-sa-v0001")
    print("__main__")
    usa_tray = UsaTray()
    usa_tray.run()