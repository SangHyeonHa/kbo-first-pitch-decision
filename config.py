"""
config.py — 프로젝트 전체가 같이 쓰는 설정값
모든 단계 파일이 `import config` 로 불러서 쓴다. (W06 모듈)
"""

SEASON = 2025
REGULAR_START = "2025-03-22"   # 2025 정규시즌 개막일
COLLECT_END = "2025-10-31"     # 일정 조회 마지막 날 (포스트시즌은 roundCode로 걸러냄)

RAW_DIR = "data/raw"           # 경기별 원본 JSON 저장 폴더
RESULT_DIR = "results"         # 분석 결과(csv, 그림) 저장 폴더

# ---- 네이버 문자중계 API (1단계에서 사용) ----
# 네이버 API는 '페이지 안에서 데이터를 요청하는 브라우저'에게만 응답한다(2026.11 확인).
# 그래서 ① curl_cffi로 크롬처럼 접속하고 ② 브라우저가 붙이는 아래 헤더를 똑같이 붙인다.
# User-Agent는 넣지 않는다(curl_cffi가 크롬 값을 자동으로 넣음). referer는 요청마다 따로 붙인다.
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "origin": "https://m.sports.naver.com",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
}
SCHEDULE_URL = "https://api-gw.sports.naver.com/schedule/games"
GAME_URL = "https://api-gw.sports.naver.com/schedule/games/{game_id}"
RELAY_URL = "https://api-gw.sports.naver.com/schedule/games/{game_id}/relay"
SLEEP_SEC = 1.0                # 요청 사이 쉬는 시간(초). 서버에 부담 주지 않기 위해

# ---- 투구 결과 코드 (네이버 pitchResult) ----
PITCH_RESULT = {
    "B": "볼", "T": "루킹 스트라이크", "S": "헛스윙", "F": "파울",
    "H": "타격(인플레이)", "W": "번트 파울", "V": "번트 헛스윙",
}
SWING_CODES = ["S", "F", "H"]  # 스윙 = 헛스윙·파울·타격 (제안서 정의)
BUNT_CODES = ["W", "V"]        # 번트 시도는 스윙/지켜봄 비교에서 뺀다

# ---- 존 분류 ----
BALL_FT = 0.24                 # 공 지름 약 2.9인치 = 0.24피트. '경계' 구역의 폭

# ---- 분석 ----
MIN_N = 100                    # 칸 하나에 초구가 이보다 적으면 결론을 내지 않는다
N_BOOT = 500                   # 부트스트랩 반복 횟수
