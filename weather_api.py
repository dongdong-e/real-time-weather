# 슬랙과 기상청 API를 연동하는 파이썬 예제 코드입니다.
# requests가 필요합니다. (pip install requests)

import requests
import ssl
import urllib3
from datetime import datetime, timedelta
import time
import schedule
import logging
import sys
import os

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('weather_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 슬랙 Incoming Webhook URL을 환경변수로만 사용
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
if not SLACK_WEBHOOK_URL:
    raise ValueError("SLACK_WEBHOOK_URL 환경변수가 설정되어 있지 않습니다. 보안을 위해 코드에 직접 입력하지 마세요.")

# 기상청 API 기본 URL (시간 매개변수는 동적으로 설정)
KMA_WARNING_API_BASE_URL = "https://apihub.kma.go.kr/api/typ01/url/wrn_met_data.php"
# 기존 인증키 (실제 유효한 인증키로 교체 필요)
AUTH_KEY = "3vOvAIAXRQKzrwCAF7UC2g"

# 특보 필드명 (순서 고정)
WARNING_FIELDS = [
    "TM_FC", "TM_EF", "TM_IN", "STN", "REG_ID", "WRN", "LVL", "CMD", "GRD", "CNT", "RPT"
]

# 특보 코드 해석 (API 문서 기반)
WRN_TYPE = {
    "W": "강풍", "R": "호우", "C": "한파", "D": "건조", "O": "해일", 
    "N": "지진해일", "V": "풍랑", "T": "태풍", "S": "대설", "Y": "황사", 
    "H": "폭염", "F": "안개"
}
LVL_TYPE = {"1": "예비", "2": "주의보", "3": "경보"}
CMD_TYPE = {"1": "발표", "2": "대치", "3": "해제", "4": "대치해제(자동)", "5": "연장", "6": "변경", "7": "변경해제"}

# 이전에 발표된 특보를 추적하기 위한 전역 변수
previous_warnings = set()


def get_current_time_string():
    """현재 시간을 기상청 API 형식(YYYYMMDDHHMM)으로 반환"""
    return datetime.now().strftime("%Y%m%d%H%M")


def get_time_range():
    """최근 1시간 동안의 시간 범위를 반환 (실시간 모니터링용)"""
    now = datetime.now()
    # 1시간 전
    start_time = now - timedelta(hours=1)
    
    start_str = start_time.strftime("%Y%m%d%H%M")
    end_str = now.strftime("%Y%m%d%H%M")
    
    return start_str, end_str


def build_warning_api_url(region=0, warning_type="A", disp_level=0):
    """동적으로 기상특보 API URL을 생성"""
    start_time, end_time = get_time_range()
    
    url = f"{KMA_WARNING_API_BASE_URL}?reg={region}&wrn={warning_type}&tmfc1={start_time}&tmfc2={end_time}&disp={disp_level}&help=0&authKey={AUTH_KEY}"
    return url


def get_warning_info(region=0, warning_type="A", disp_level=0):
    """기상 특보 표 데이터를 파싱해서 사람이 읽기 쉽게 반환"""
    try:
        # 동적으로 URL 생성
        api_url = build_warning_api_url(region, warning_type, disp_level)
        logger.info(f"지역 {region} (특보종류: {warning_type}) API 조회 중...")
        
        response = requests.get(api_url, verify=False, timeout=30)
        response.encoding = 'utf-8'
        text = response.text
        if not text.strip():
            return f"지역 {region} 특보 API 응답이 비어있습니다."

        # 데이터 부분만 추출 (주석/설명 라인 제외)
        lines = [line.strip() for line in text.split('\n') if line.strip() and not line.startswith('#')]
        warning_info = []
        current_warnings = set()
        
        for line in lines:
            # 데이터 라인: 필드 11개 + '='로 끝남
            if not line.endswith('='):
                continue
            parts = [p.strip() for p in line[:-1].split(',')]
            if len(parts) != len(WARNING_FIELDS):
                continue
            data = dict(zip(WARNING_FIELDS, parts))
            
            # 새로운 특보인지 확인하기 위한 고유 키 생성
            warning_key = f"{data['TM_FC']}_{data['REG_ID']}_{data['WRN']}_{data['LVL']}_{data['CMD']}"
            current_warnings.add(warning_key)
            
            # 사람이 읽기 쉬운 메시지로 변환
            msg = (
                f"[지역 {region}] {WRN_TYPE.get(data['WRN'], data['WRN'])} {LVL_TYPE.get(data['LVL'], data['LVL'])} ({CMD_TYPE.get(data['CMD'], data['CMD'])})\n"
                f"발표시각: {data['TM_FC']} / 발효시각: {data['TM_EF']}\n"
                f"구역코드: {data['REG_ID']} / 관서: {data['STN']} / 등급: {data['GRD']}\n"
                f"작업상태: {data['CNT']} / 통보문: {data['RPT']}"
            )
            warning_info.append(msg)
        
        # 새로운 특보가 있는지 확인
        new_warnings = current_warnings - previous_warnings
        if new_warnings:
            logger.info(f"지역 {region}에서 {len(new_warnings)}개의 새로운 특보 발견!")
            previous_warnings.update(new_warnings)
        
        if not warning_info:
            return f"지역 {region}에 현재 발표된 특보가 없습니다."
        return '\n\n'.join(warning_info)
    except Exception as e:
        logger.error(f"지역 {region} 기상특보 API 오류: {e}")
        return f"지역 {region} 기상특보 API 오류: {e}"

def send_warning_to_slack():
    """모든 지역의 특보 정보를 슬랙으로 전송"""
    all_warnings = []
    region_names = {
        0: "전국", 1: "서울/경기", 2: "강원", 3: "충북", 4: "충남", 
        5: "전북", 6: "전남", 7: "경북", 8: "경남", 9: "제주"
    }
    
    for region in range(10):  # 0~9까지 모든 지역
        logger.info(f"=== {region_names[region]} (지역 {region}) 조회 중 ===")
        
        # 전체 특보 조회
        warning_info = get_warning_info(region, "A", 0)
        
        if warning_info and not warning_info.startswith("오류") and not "비어있습니다" in warning_info:
            all_warnings.append(f"📍 **{region_names[region]}**\n{warning_info}")
        else:
            logger.info(f"{region_names[region]}: 특보 없음")
    
    if all_warnings:
        message = f"🌤️ **실시간 기상 특보 정보** (최근 1시간)\n\n" + "\n\n".join(all_warnings)
        send_to_slack(message)
    else:
        logger.info("모든 지역에서 특보 정보를 찾을 수 없습니다.")
        # 실시간 모니터링에서는 특보가 없어도 슬랙에 보내지 않음

def send_to_slack(message):
    try:
        payload = {"text": message}
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("슬랙으로 메시지가 성공적으로 전송되었습니다!")
            return True
        else:
            logger.error(f"슬랙 전송 오류: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"슬랙 전송 오류: {e}")
        return False

def monitor_weather_warnings():
    """실시간 기상특보 모니터링 함수"""
    logger.info("=== 기상특보 실시간 모니터링 시작 ===")
    send_warning_to_slack()
    logger.info("=== 기상특보 모니터링 완료 ===")

def run_scheduler():
    """스케줄러 실행"""
    logger.info("기상특보 모니터링 스케줄러 시작...")
    
    # 매 5분마다 실행
    schedule.every(5).minutes.do(monitor_weather_warnings)
    
    # 매 시간마다 실행 (백업)
    schedule.every().hour.do(monitor_weather_warnings)
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # 1분마다 스케줄 확인

if __name__ == "__main__":
    # 단일 실행
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        send_warning_to_slack()
    else:
        # 실시간 모니터링 시작
        run_scheduler()
