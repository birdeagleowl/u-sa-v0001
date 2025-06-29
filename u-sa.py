import json
import os


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

if __name__ == '__main__':
    print("init")
    kis_api = KisApi("1","1","-")