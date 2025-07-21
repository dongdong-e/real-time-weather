# 슬랙과 기상청 API를 연동하는 파이썬 예제 코드입니다.
# requests가 필요합니다. (pip install requests)

import requests
import ssl
import urllib3

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 슬랙 Incoming Webhook URL을 입력하세요
SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/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"

# 기상청 특보 표 데이터 URL (예시)
KMA_WARNING_API_URL = "https://apihub.kma.go.kr/api/typ01/url/wrn_met_data.php?reg=0&wrn=A&tmfc1=201501010000&tmfc2=201502010000&disp=0&help=0&authKey=3vOvAIAXRQKzrwCAF7UC2g"

# 특보 필드명 (순서 고정)
WARNING_FIELDS = [
    "TM_FC", "TM_EF", "TM_IN", "STN", "REG_ID", "WRN", "LVL", "CMD", "GRD", "CNT", "RPT"
]

# 특보 코드 해석 (일부 예시, 필요시 추가)
WRN_TYPE = {"W": "강풍", "S": "호우", "V": "풍랑", "C": "건조", "T": "태풍", "H": "한파", "D": "대설"}
LVL_TYPE = {"1": "예비", "2": "주의보", "3": "경보"}
CMD_TYPE = {"1": "발표", "2": "대치", "3": "해제", "4": "대치해제(자동)", "5": "연장", "6": "변경", "7": "변경해제"}


def get_warning_info():
    """기상 특보 표 데이터를 파싱해서 사람이 읽기 쉽게 반환"""
    try:
        response = requests.get(KMA_WARNING_API_URL, verify=False, timeout=30)
        response.encoding = 'utf-8'
        text = response.text
        if not text.strip():
            return "특보 API 응답이 비어있습니다."

        # 데이터 부분만 추출 (주석/설명 라인 제외)
        lines = [line.strip() for line in text.split('\n') if line.strip() and not line.startswith('#')]
        warning_info = []
        for line in lines:
            # 데이터 라인: 필드 11개 + '='로 끝남
            if not line.endswith('='):
                continue
            parts = [p.strip() for p in line[:-1].split(',')]
            if len(parts) != len(WARNING_FIELDS):
                continue
            data = dict(zip(WARNING_FIELDS, parts))
            # 사람이 읽기 쉬운 메시지로 변환
            msg = (
                f"[특보] {WRN_TYPE.get(data['WRN'], data['WRN'])} {LVL_TYPE.get(data['LVL'], data['LVL'])} ({CMD_TYPE.get(data['CMD'], data['CMD'])})\n"
                f"발표시각: {data['TM_FC']} / 발효시각: {data['TM_EF']}\n"
                f"구역코드: {data['REG_ID']} / 관서: {data['STN']} / 등급: {data['GRD']}\n"
                f"작업상태: {data['CNT']} / 통보문: {data['RPT']}"
            )
            warning_info.append(msg)
        if not warning_info:
            return "현재 발표된 특보가 없습니다."
        return '\n\n'.join(warning_info)
    except Exception as e:
        return f"기상특보 API 오류: {e}"

def send_warning_to_slack():
    """특보 정보를 슬랙으로 전송"""
    warning_info = get_warning_info()
    if warning_info and not warning_info.startswith("오류"):
        message = f"🌤️ 기상 특보 정보입니다.\n\n{warning_info}"
        send_to_slack(message)
    else:
        print(f"특보 정보를 가져올 수 없습니다: {warning_info}")

def send_to_slack(message):
    try:
        payload = {"text": message}
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        if response.status_code == 200:
            print("슬랙으로 메시지가 성공적으로 전송되었습니다!")
            return True
        else:
            print(f"슬랙 전송 오류: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"슬랙 전송 오류: {e}")
        return False

if __name__ == "__main__":
    send_warning_to_slack()
