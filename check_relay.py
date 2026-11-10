"""
check_relay.py — 문자중계(relay) 주소가 어떤 헤더에서 응답하는지 시험
  python check_relay.py
"""
import time

import requests as plain_requests
from curl_cffi import requests

GID = "20250322HHKT02025"
RELAY = f"https://api-gw.sports.naver.com/schedule/games/{GID}/relay"
SCHEDULE = "https://api-gw.sports.naver.com/schedule/games"
SCHEDULE_PARAMS = {"fields": "basic,schedule,baseball", "upperCategoryId": "kbaseball",
                   "fromDate": "2025-03-22", "toDate": "2025-03-22", "size": 500}

CORS = {   # 페이지 안에서 데이터를 요청할 때 브라우저가 붙이는 헤더 (사용자 정보 제외)
    "accept": "application/json, text/plain, */*",
    "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "origin": "https://m.sports.naver.com",
    "referer": f"https://m.sports.naver.com/game/{GID}/relay",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
}
FULL = dict(CORS)
FULL.update({
    "priority": "u=1, i",
    "sec-ch-ua": '"Not-A.Brand";v="99", "Google Chrome";v="157", "Chromium";v="157"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/157.0.0.0 Safari/537.36",
})


def run(label, getter, url, headers, params):
    start = time.time()
    try:
        res = getter(url, headers=headers, params=params, timeout=12)
        print("%-36s 성공 %d %.1f초 %d글자" % (label, res.status_code, time.time() - start, len(res.text)))
    except Exception as error:
        print("%-36s 실패 %.1f초 %s" % (label, time.time() - start, str(error)[:50]))


chrome = requests.Session(impersonate="chrome")
plain = plain_requests.Session()
plain.trust_env = False
run("E. 크롬흉내 + cors 헤더  (문자중계)", chrome.get, RELAY, CORS, {"inning": 1})
run("F. 크롬흉내 + 브라우저 헤더 전부 (문자중계)", chrome.get, RELAY, FULL, {"inning": 1})
run("G. 일반 requests + 헤더 전부 (문자중계)", plain.get, RELAY, FULL, {"inning": 1})
run("H. 크롬흉내 + cors 헤더  (일정)", chrome.get, SCHEDULE, CORS, SCHEDULE_PARAMS)
