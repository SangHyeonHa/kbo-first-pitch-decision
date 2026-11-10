"""
step1_collect.py — ① 수집 담당
네이버 문자중계에서 2025 정규시즌 경기 목록과 경기별 문자중계(JSON)를 받아 저장한다.

[수업 밖] 이 파일에서 처음 나오는 것들
- curl_cffi : 웹 주소로 요청을 보내고 응답을 받는 외부 라이브러리(사용법은 requests와 같다).
              네이버 API는 '진짜 브라우저'가 아니면 응답을 안 줘서, 크롬처럼 접속하는 이 라이브러리를 쓴다.
              설치: pip install curl_cffi
- JSON     : W07에서 배운 dict·list를 '글자'로 적어 둔 형식. res.json()이 dict로 바꿔 준다
- open/with, json.dump : 파일 쓰기
- try/except : 요청이 실패해도 프로그램이 멈추지 않게 하는 문법
- time.sleep, os.path, os.makedirs : 기다리기, 파일 경로 다루기
"""
import json
import os
import time

from curl_cffi import requests

import config

# impersonate="chrome": 크롬 브라우저와 같은 방식으로 접속한다.
# (일반 requests·curl로 보내면 네이버 API가 응답하지 않고 시간 초과가 난다 — 2026.11 확인)
# 헤더는 config.HEADERS 참고
SESSION = requests.Session(impersonate="chrome")


def make_date_list(start, end):
    """'2025-03-22'부터 '2025-10-31'까지의 날짜 문자열 리스트를 만든다.
    'YYYY-MM-DD' 형식 문자열은 크기 비교(<=)가 날짜 순서와 같아서 그대로 비교할 수 있다."""
    year = int(start[:4])
    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        days_in_month[1] = 29
    dates = []
    for month in range(1, 13):
        for day in range(1, days_in_month[month - 1] + 1):
            text = f"{year}-{month:02d}-{day:02d}"
            if start <= text <= end:
                dates.append(text)
    return dates


def get_json(url, params=None, referer="https://m.sports.naver.com/"):
    """웹 주소에서 JSON을 받아 dict로 돌려준다. 실패하면 None. 요청 뒤에는 항상 잠깐 쉰다.
    referer = '이 요청을 보낸 페이지 주소'. 문자중계는 그 경기의 문자중계 페이지 주소를 넣는다."""
    headers = dict(config.HEADERS)      # 공통 헤더를 복사한 뒤 referer만 추가
    headers["referer"] = referer
    try:
        res = SESSION.get(url, headers=headers, params=params, timeout=20)
        res.raise_for_status()          # 200이 아니면 에러로 처리
        data = res.json()
    except Exception as error:
        print("  요청 실패:", url, params, error)
        data = None
    time.sleep(config.SLEEP_SEC)
    return data


def fetch_games_of_day(date):
    """하루치 경기 목록. 정규시즌(roundCode 'kbo_r')이고 취소되지 않은 KBO 경기만 남긴다.
    요청이 실패하면 None을 돌려준다."""
    params = {"fields": "basic,schedule,baseball", "upperCategoryId": "kbaseball",
              "fromDate": date, "toDate": date, "size": 500}
    data = get_json(config.SCHEDULE_URL, params)
    if data is None:
        return None                     # 요청 실패 (경기 없는 날은 빈 리스트 [])
    games = []
    for g in data["result"]["games"]:
        if g.get("categoryId") != "kbo" or g.get("roundCode") != "kbo_r":
            continue
        status = (g.get("statusCode") or "").upper()
        info = g.get("statusInfo") or ""
        if "CANCEL" in status or "취소" in info:
            continue
        games.append({"game_id": g["gameId"], "date": date,
                      "away": g.get("awayTeamCode"), "home": g.get("homeTeamCode")})
    return games


def last_inning_of(value):
    """'9회말', '연장 11회' 같은 값에서 숫자만 뽑아 정수로 만든다."""
    digits = ""
    for ch in str(value):
        if ch.isdigit():
            digits += ch
    return int(digits) if digits else 9


def fetch_game_relay(game_id):
    """한 경기의 1회~마지막 이닝 문자중계를 받아 리스트 하나로 묶어 data/raw/{game_id}.json 에 저장.
    이미 파일이 있으면 다시 받지 않는다(재수집 금지). 성공하면 파일 경로, 실패하면 None."""
    path = os.path.join(config.RAW_DIR, game_id + ".json")
    if os.path.exists(path):
        return path
    page = f"https://m.sports.naver.com/game/{game_id}/relay"      # 이 경기 문자중계 페이지
    info = get_json(config.GAME_URL.format(game_id=game_id), referer=page)
    if info is None:
        return None
    last_inning = last_inning_of(info["result"]["game"]["currentInning"])
    payloads = []
    for inning in range(1, last_inning + 1):
        data = get_json(config.RELAY_URL.format(game_id=game_id), {"inning": inning}, referer=page)
        if data is None:
            return None                 # 한 이닝이라도 실패하면 저장하지 않음 → 다음에 다시 시도
        payloads.append(data)
    os.makedirs(config.RAW_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payloads, f, ensure_ascii=False)
    return path


def collect_season(start=config.REGULAR_START, end=config.COLLECT_END):
    """시즌 전체 수집. 경기 목록은 data/games.csv 로도 남긴다. 약 2시간 걸림(요청 간격 1초)."""
    all_games = []
    fail_in_a_row = 0
    for date in make_date_list(start, end):
        games = fetch_games_of_day(date)
        if games is None:
            fail_in_a_row += 1
            if fail_in_a_row >= 5:
                print("일정 요청이 5번 연속 실패해서 멈춥니다. python check_naver.py 로 연결부터 확인하세요.")
                return all_games
            continue
        fail_in_a_row = 0
        for g in games:
            g["saved"] = fetch_game_relay(g["game_id"]) is not None
            all_games.append(g)
        if games:
            print(date, len(games), "경기")
    os.makedirs("data", exist_ok=True)
    with open("data/games.csv", "w", encoding="utf-8") as f:
        f.write("game_id,date,away,home,saved\n")
        for g in all_games:
            f.write(",".join([g["game_id"], g["date"], str(g["away"]), str(g["home"]), str(g["saved"])]) + "\n")
    failed = [g["game_id"] for g in all_games if not g["saved"]]
    print("수집한 경기:", len(all_games) - len(failed), "/ 실패:", len(failed), failed)
    return all_games
