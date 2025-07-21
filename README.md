# 기상특보 실시간 모니터링 서버

## 개요
기상청 API를 통해 실시간으로 기상특보를 모니터링하고 슬랙으로 알림을 보내는 서버입니다.

## 기능
- 매 5분마다 전국 10개 지역의 기상특보 조회
- 새로운 특보 발표 시 즉시 슬랙 알림
- 로그 파일을 통한 모니터링 기록
- 구글 클라우드에서 24/7 운영

## 로컬 테스트

### 1. 단일 실행
```bash
python weather_api.py --once
```

### 2. 실시간 모니터링 (로컬)
```bash
python weather_api.py
```

### 3. Docker로 실행
```bash
docker-compose up -d
```

## 구글 클라우드 배포

### 1. 프로젝트 설정
```bash
# 구글 클라우드 프로젝트 설정
gcloud config set project YOUR_PROJECT_ID

# 필요한 API 활성화
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
```

### 2. Docker 이미지 빌드 및 배포
```bash
# Cloud Build로 이미지 빌드
gcloud builds submit --config cloudbuild.yaml

# Cloud Run에 배포
gcloud run deploy weather-monitor \
  --image gcr.io/YOUR_PROJECT_ID/weather-monitor:latest \
  --platform managed \
  --region asia-northeast1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 1 \
  --max-instances 1
```

### 3. 환경 변수 설정
```bash
# 슬랙 웹훅 URL 설정
gcloud run services update weather-monitor \
  --set-env-vars SLACK_WEBHOOK_URL=YOUR_SLACK_WEBHOOK_URL
```

## 모니터링

### 로그 확인
```bash
# Cloud Run 로그 확인
gcloud logs read --service=weather-monitor --limit=50

# 로컬 로그 확인
tail -f weather_monitor.log
```

### 상태 확인
```bash
# 서비스 상태 확인
gcloud run services describe weather-monitor --region=asia-northeast1
```

## 설정 옵션

### 모니터링 주기 변경
`weather_api.py`의 `run_scheduler()` 함수에서 스케줄을 수정할 수 있습니다:

```python
# 매 1분마다 실행
schedule.every(1).minutes.do(monitor_weather_warnings)

# 매 10분마다 실행
schedule.every(10).minutes.do(monitor_weather_warnings)
```

### 특보 종류 필터링
특정 특보만 모니터링하려면 `get_warning_info()` 호출 시 `warning_type` 매개변수를 변경하세요:

```python
# 폭염만 모니터링
warning_info = get_warning_info(region, "H", 0)

# 호우만 모니터링
warning_info = get_warning_info(region, "R", 0)
```

## 특보 종류 코드
- **A**: 전체 특보
- **W**: 강풍
- **R**: 호우
- **C**: 한파
- **D**: 건조
- **O**: 해일
- **N**: 지진해일
- **V**: 풍랑
- **T**: 태풍
- **S**: 대설
- **Y**: 황사
- **H**: 폭염
- **F**: 안개

## 지역 코드
- **0**: 전국
- **1**: 서울/경기
- **2**: 강원
- **3**: 충북
- **4**: 충남
- **5**: 전북
- **6**: 전남
- **7**: 경북
- **8**: 경남
- **9**: 제주 