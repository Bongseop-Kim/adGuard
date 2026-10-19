"""adGuard 진입점 (골격).

- 명령줄 모드: adguard.exe <URL>  → 창 없이 탐지하고 result.json을 쓴다 (--no-report <URL>: 보고서·캡처 생략)
- 창 모드:     adguard.exe        → WebView2 창(pywebview)에서 URL 입력·탐지 시작
- 검증 모드:   adguard.exe --smoke-gui <URL> → 창을 띄워 자동으로 탐지하고 닫는다 (CI용)
- 예약 점검:   adguard.exe --scheduled <id> → Windows 작업 스케줄러가 부른다. schedules.json의 그 예약을 창 없이 점검
- 결과: exe 폴더에 result.json(채점용), result_extra.json(추가 유형), report.html(단일 파일 보고서), result.csv(Excel용), history.json(최초 발견일), records/(점검 기록)
"""
import asyncio
import base64
import json
import os
import pathlib
import re
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

VERSION = "1.0.0"
KST = timezone(timedelta(hours=9))
# 시간 상한 안에서 크롤 마감 뒤에 남겨 두는 몫(초): 진행 중 페이지 대기 30초·브라우저 닫기, 보고서 단계(진단·캡처·보고서, S2·S3·S7 실측 50~80초)
TAIL_SEC, REPORT_SEC = 45, 150


def base_dir():
    # PyInstaller로 묶이면 exe가 있는 폴더, 아니면 이 파일의 폴더
    return os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))


ENV_NAMES = (".env", ".env.txt")  # 메모장 "확장자 숨기기"로 .env.txt가 되는 경우도 읽는다
AI_MODEL = "gpt-6-luna"


def read_text(p):
    """메모장 BOM·한글 Windows 기본 인코딩(CP949)으로 저장한 .env도 읽는다"""
    raw = open(p, "rb").read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp949", "replace")


def load_env():
    """exe 옆 .env를 읽어 환경변수에 넣는다. PC에 같은 이름이 있어도 .env가 이긴다 (심사위원 키가 확실히 쓰이게)"""
    for name in ENV_NAMES:
        p = os.path.join(base_dir(), name)
        if os.path.isfile(p):
            for line in read_text(p).splitlines():
                k, eq, v = line.strip().partition("=")
                if eq and not k.startswith("#"):
                    os.environ[k.strip().removeprefix("export ")] = v.strip().strip("'\"")
            return p
    return None


def save_key(key):
    """OPENAI_API_KEY 줄만 바꿔 .env에 쓴다 (다른 줄·주석은 그대로). 실패하면 이번 실행에만 쓴다. 반환: 저장 경로 또는 None"""
    if key:
        os.environ["OPENAI_API_KEY"] = key
    else:
        os.environ.pop("OPENAI_API_KEY", None)
    path = next((p for p in (os.path.join(base_dir(), n) for n in ENV_NAMES) if os.path.isfile(p)),
                os.path.join(base_dir(), ".env"))
    try:
        lines = read_text(path).splitlines() if os.path.isfile(path) else []
        lines = [l for l in lines if l.strip().partition("=")[0].strip() != "OPENAI_API_KEY"]
        if key:
            lines.append("OPENAI_API_KEY=" + key)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        return path
    except OSError:
        return None


def ai_status(check=True):
    """화면 표시용 AI 상태. 키 값은 절대 내보내지 않는다 (앞 3자·끝 4자만). check면 키로 모델 조회를 한 번 해 본다(비용 없음)"""
    import urllib.error
    import urllib.request

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("OPENAI_DECISIONS_MODEL", "").strip() or AI_MODEL
    if not key:
        return {"on": False, "model": model, "reason": "키 없음"}
    out = {"on": False, "model": model, "masked": key[:3] + "…" + key[-4:]}
    if not check:
        return dict(out, reason="확인 전")
    req = urllib.request.Request("https://api.openai.com/v1/models/" + model, headers={"Authorization": "Bearer " + key})
    try:
        urllib.request.urlopen(req, timeout=8).close()
        return dict(out, on=True, reason="")
    except urllib.error.HTTPError as e:
        reason = {401: "키가 맞지 않습니다", 403: "이 키로 %s 모델을 쓸 권한이 없습니다(유료 등급 키 필요)" % model,
                  404: "이 키로 %s 모델을 쓸 수 없습니다(유료 등급 키 필요)" % model, 429: "호출 한도 초과 또는 결제 필요"}
        return dict(out, reason="%s (HTTP %d)" % (reason.get(e.code, "확인 실패"), e.code))
    except (urllib.error.URLError, OSError) as e:
        return dict(out, reason="OpenAI에 연결하지 못했습니다 (%s)" % getattr(e, "reason", e))


def fix_url(url):
    """주소에 http(s)://가 없으면 붙인다 (www.x.go.kr). 창 모드·명령줄 공통"""
    url = (url or "").strip()
    return url if "://" in url else "http://" + url


def write_json(path, data):
    # UTF-8(BOM 없음), 임시 파일에 쓴 뒤 교체해서 반쯤 쓰인 파일이 남지 않게 한다
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    for _ in range(10):  # Windows: 백신·인덱서가 잠깐 잡고 있으면 교체가 거부된다 (WinError 5·32)
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.2)
    with open(path, "w", encoding="utf-8", newline="\n") as f:  # 끝내 교체가 안 되면 직접 덮어쓴다 (결과를 잃지 않게)
        json.dump(data, f, ensure_ascii=False, indent=2)
    try:
        os.remove(tmp)
    except OSError:
        pass


def meta_of(url, started, t0):
    return {"topic": "TOPIC", "entry_url": url, "started_at": started.isoformat(timespec="seconds"),
            "finished_at": datetime.now(KST).isoformat(timespec="seconds"), "elapsed_sec": round(time.monotonic() - t0, 2),
            "tool_version": VERSION}


def write_results(meta, findings, extras):
    write_json(os.path.join(base_dir(), "result.json"), {"meta": meta, "findings": findings})
    write_json(os.path.join(base_dir(), "result_extra.json"), {"meta": meta, "findings": extras})


def scan(url, log=print, ctl=None, minutes=20, report=False):
    """탐지하고 result.json을 쓴다. report면 보고서 단계 몫을 남기고 크롤을 마감한다 (보고서까지가 시간 상한 안).
    반환: (meta, 검출 목록(보고서용 근거 포함))"""
    browsers = os.path.join(base_dir(), "browsers")
    if os.path.isdir(browsers):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = browsers  # PC에 같은 환경변수가 있어도 동봉본을 쓴다
    import ai
    from crawler import crawl
    from detect import analyze

    ai.setup()  # .env 키가 있으면 경계 후보만 AI에 묻는다 (없으면 규칙만)
    ctl = {} if ctl is None else ctl
    started, t0 = datetime.now(KST), time.monotonic()
    ctl["t0"], ctl["end"] = t0, t0 + minutes * 60 - 10  # end: 보고서까지 끝낼 시각 (파일 쓰기 여유 10초)
    # 시작하자마자 이번 주소의 빈 결과로 덮는다: 강제 종료돼도 이전 점검(다른 주소)의 결과가 남지 않게
    write_results(meta_of(url, started, t0), [], [])
    try:
        asyncio.run(crawl(url, analyze, log=log, ctl=ctl, time_limit=max(30, minutes * 60 - TAIL_SEC - (REPORT_SEC if report else 0))))
    except Exception as e:
        log("오류로 탐색 중단, 그때까지의 결과를 저장합니다: %r" % e)
    finally:  # 크롤이 죽어도 파싱 가능한 result.json은 남긴다 (파일이 없거나 깨지면 0점)
        ai.save()
        pages = ctl["crawler"].results if "crawler" in ctl else []
        findings, extras, items, seen = [], [], [], set()
        for pg in pages:
            for f in pg["result"] or []:
                key = (pg["url"], f["location"], f["technique"], f.get("extra_finding"))  # 채점 단위. 같은 조합은 1건
                if key in seen:
                    continue
                seen.add(key)
                out = extras if f.get("extra_finding") else findings  # 4종 밖 추가 유형은 result_extra.json으로만
                out.append({"id": "%s_%03d" % ("e" if out is extras else "f", len(out) + 1), "url": pg["url"],
                            "is_violation": True, "location": f["location"],
                            "evidence_text": f["evidence_text"] or f["location"], "technique": f["technique"]})
                if out is extras:
                    out[-1]["extra_finding"] = f["extra_finding"]
                items.append(dict(f, **out[-1], path=pg.get("path") or [], mobile=pg.get("mobile", False)))
        meta = meta_of(url, started, t0)
        write_results(meta, findings, extras)  # 보고서 모드에서는 안전 사본: 보고서가 끝나면 meta만 고쳐 다시 쓴다
    log("%s: %d쪽, %d건(추가 유형 %d건) -> %s" % ("탐지 단계 완료, 보고서 작성" if report else "탐지 완료", len(pages), len(findings),
                                            len(extras), os.path.join(base_dir(), "result.json")))
    if ai.STATS["enabled"]:
        s = ai.STATS
        log("AI 판정: 후보 %d, 캐시 %d, 호출 %d, 거부 %d, 실패 %d, 토큰 %d, 바꾼 판정 %d" % (
            s["candidates"], s["cache"], s["calls"], s["refused"], s["failed"], s["tokens"], len(s["changed"])))
    return meta, items


def run_all(url, log=print, ctl=None, minutes=20, on_done=None):
    """탐지(result.json 안전 사본) → on_done(meta, items) → 보고서(report.html, result.csv) → 탐지 완료.
    검출 시간은 보고서까지 포함한다 (todo/12 결정): 보고서가 끝난 시각으로 result.json·result_extra.json의 meta를 고쳐 쓴다"""
    import report

    ctl = {} if ctl is None else ctl
    meta, items = scan(url, log, ctl, minutes, report=True)
    if on_done:
        on_done(meta, items)
    c = ctl.get("crawler")
    pages = [{"url": r["url"], "path": r.get("path") or []} for r in (c.results if c else [])]
    error = None
    if not pages:  # 한 쪽도 못 열었으면 "광고 없음"이 아니라 점검 실패
        error = "시작 주소를 열지 못했습니다. 주소가 맞는지, 사이트가 켜져 있는지, 이 PC에서 접속되는지 확인하세요."
        if c and c.start_fail:  # 열리긴 했지만 오류 응답이거나 웹 페이지가 아님
            error = "시작 주소가 점검할 수 있는 웹 페이지가 아닙니다 (%s). 누리집이나 게시판 페이지 주소를 넣으세요." % c.start_fail
        elif c and c.errors:
            m = re.search(r"net::\w+|Timeout[^\\]*", c.errors[0][1])
            error += " (오류: %s)" % (m.group(0) if m else c.errors[0][1][:120])
        log("점검 실패: " + error)
    diag = []
    if pages:  # 사이트 진단 (todo/08): 보고서 단계(검출 시간 안, 상한 ctl["end"]에 맞춰 줄임). 클로킹 검출만 result_extra.json에 덧붙인다
        import extra
        try:
            diag, found = asyncio.run(extra.run(url, log, pages, ctl.get("end")))
            if found:
                path = os.path.join(base_dir(), "result_extra.json")
                with open(path, encoding="utf-8") as f:
                    ex = json.load(f)
                seen = {(x["url"], x["location"], x["extra_finding"]) for x in ex["findings"]}
                for f in found:
                    if (f["url"], f["location"], f["extra_finding"]) in seen:
                        continue
                    seen.add((f["url"], f["location"], f["extra_finding"]))
                    out = {"id": "e_%03d" % (len(ex["findings"]) + 1), "url": f["url"], "is_violation": True, "location": f["location"],
                           "evidence_text": f["evidence_text"], "technique": "ETC", "extra_finding": f["extra_finding"]}
                    ex["findings"].append(out)
                    items.append(dict(f, **out, path=next((x["path"] for x in pages if x["url"] == f["url"]), []), mobile=False))
                write_json(path, ex)
                log("진단 검출 %d건을 result_extra.json에 더했습니다" % len(found))
        except Exception as e:
            log("진단 단계 오류(보고서는 진단 없이 만듦): %r" % e)

    def finish(m):
        m.update(finished_at=datetime.now(KST).isoformat(timespec="seconds"), elapsed_sec=round(time.monotonic() - ctl["t0"], 2))
        for name in ("result.json", "result_extra.json"):
            p = os.path.join(base_dir(), name)
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            write_json(p, dict(data, meta=m))  # 읽은 파일을 닫은 뒤 교체: Windows는 열린 파일을 바꾸지 못한다
        log("탐지 완료(보고서 포함): %.1f초" % m["elapsed_sec"])
    return report.make(meta, items, c.visited if c else 0, bool(c and c.deadline == 0), minutes, log, pages, error, ctl, diag, finish)


def open_log():
    """진행 기록을 logs/날짜.log에도 남기는 log 함수와 닫기 함수. 창 모드·예약 점검 공통 (오류가 나면 이 파일로 원인을 본다)"""
    try:
        os.makedirs(os.path.join(base_dir(), "logs"), exist_ok=True)
        f = open(os.path.join(base_dir(), "logs", datetime.now(KST).strftime("%Y%m%d") + ".log"), "a", encoding="utf-8")
    except OSError:
        f = None

    def log(msg):
        print(msg, flush=True)
        try:
            f and (f.write(datetime.now(KST).strftime("%H:%M:%S ") + msg + "\n"), f.flush())
        except (OSError, ValueError):
            pass
    return log, (f.close if f else lambda: None)


def take_lock():
    """점검은 한 번에 하나만 (창 모드와 예약 점검이 같은 결과 파일을 쓴다). 반환: 잠금 파일(close로 풀기) 또는 None.
    프로세스가 죽으면 OS가 풀어 주므로 남은 잠금 파일 때문에 막히지 않는다. 명령줄 모드(채점용)는 잠그지 않는다"""
    try:
        os.makedirs(os.path.join(base_dir(), "logs"), exist_ok=True)
        f = open(os.path.join(base_dir(), "logs", "scan.lock"), "a+")
    except OSError:
        return None
    try:
        f.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f
    except OSError:
        f.close()
        return None


# 예약 점검: 목록은 schedules.json, 실행은 Windows 작업 스케줄러(\adGuard\<id>)가 맡는다. 창을 닫아도·재부팅해도 돈다
# ponytail: schtasks 기본 설정이라 PC가 꺼져 있던 회차는 건너뛰고 배터리로는 시작하지 않는다. 필요하면 /xml로 StartWhenAvailable
DAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
NO_WINDOW = 0x08000000  # 창 모드에서 schtasks를 불러도 콘솔 창이 깜박이지 않게


def schedules():
    try:
        with open(os.path.join(base_dir(), "schedules.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def check_schedule(s):
    """화면에서 받은 예약을 검사해 정리한다. 반환: (예약, 오류 문구)"""
    try:
        s = {"url": fix_url(s.get("url")), "freq": s["freq"], "every": int(s.get("every") or 1), "time": str(s["time"]),
             "days": [d for d in DAYS if d in (s.get("days") or [])], "date": int(s.get("date") or 1),
             "minutes": max(5, min(25, int(s.get("minutes") or 20)))}
    except (KeyError, TypeError, ValueError, AttributeError):
        return None, "예약 값이 올바르지 않습니다"
    if not re.match(r"https?://[^/\s]+", s["url"]):
        return None, "점검할 주소를 입력하세요"
    if s["freq"] not in ("day", "week", "month") or not 1 <= s["every"] <= 12:
        return None, "주기를 고르세요"
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", s["time"]):
        return None, "시각을 고르세요"
    if s["freq"] == "week" and not s["days"]:
        return None, "요일을 하나 이상 고르세요"
    if not 1 <= s["date"] <= 28:  # 29~31일은 짧은 달에 건너뛰어서 받지 않는다
        return None, "날짜는 1~28일 중에서 고르세요"
    return s, None


def schtasks_args(sid, s):
    """schtasks /create 인자. 매일·매주(요일)·매월(날짜) × n일·주·개월마다"""
    me = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, os.path.abspath(__file__)]
    import subprocess
    a = ["/create", "/tn", "adGuard\\" + sid, "/tr", subprocess.list2cmdline(me + ["--scheduled", sid]), "/f",
         "/sc", {"day": "DAILY", "week": "WEEKLY", "month": "MONTHLY"}[s["freq"]], "/mo", str(s["every"]), "/st", s["time"]]
    if s["freq"] == "week":
        a += ["/d", ",".join(s["days"])]
    if s["freq"] == "month":
        a += ["/d", str(s["date"])]
    return a


def schtasks(*args):
    """Windows 작업 스케줄러 호출. 반환: (성공, 출력)"""
    if os.name != "nt":
        return False, "예약 점검은 Windows에서만 쓸 수 있습니다"
    import subprocess
    try:
        p = subprocess.run(["schtasks", *args], capture_output=True, creationflags=NO_WINDOW, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, "작업 스케줄러를 부르지 못했습니다 (%s)" % e
    out = (p.stdout if p.returncode == 0 else p.stderr or p.stdout).decode("oem", "replace").strip()
    return p.returncode == 0, out or "작업 스케줄러 오류 (%d)" % p.returncode


def next_runs():
    """예약 id → 다음 실행 시각(작업 스케줄러가 쓰는 표기 그대로). 작업 스케줄러에 없는 예약은 빠진다"""
    import csv
    ok, out = schtasks("/query", "/fo", "csv", "/nh")
    rows = csv.reader(out.splitlines()) if ok else []
    return {r[0].rsplit("\\", 1)[-1]: r[1] for r in rows if len(r) >= 2 and r[0].lower().startswith("\\adguard\\")}


def add_schedule(s):
    """예약 추가·수정. 사이트(호스트) 하나에 예약 하나: 같은 사이트가 이미 있으면 그 작업을 덮어쓴다 (/f)"""
    import secrets
    from urllib.parse import urlsplit
    s, err = check_schedule(s)
    if err:
        return {"error": err}
    host = urlsplit(s["url"]).netloc.lower()
    old = [x for x in schedules() if urlsplit(x["url"]).netloc.lower() == host]
    sid = old[0]["id"] if old else secrets.token_hex(4)
    ok, out = schtasks(*schtasks_args(sid, s))
    if not ok:
        return {"error": out}
    write_json(os.path.join(base_dir(), "schedules.json"), [dict(s, id=sid) if x in old else x for x in schedules()] if old else schedules() + [dict(s, id=sid)])
    return {}


def del_schedule(sid):
    # 작업 스케줄러에서 못 지워도 목록에서는 뺀다: 남은 작업이 돌아도 --scheduled가 목록에 없는 id라 바로 끝난다
    schtasks("/delete", "/tn", "adGuard\\" + sid, "/f")
    write_json(os.path.join(base_dir(), "schedules.json"), [x for x in schedules() if x["id"] != sid])


def run_scheduled(sid):
    """작업 스케줄러가 부르는 예약 점검. 다른 점검이 돌고 있으면 끝날 때까지 기다린다 (최대 60분)"""
    s = next((x for x in schedules() if x["id"] == sid), None)
    if not s:
        return print("목록에 없는 예약: %s" % sid)
    hide_own_console()
    log, close = open_log()
    log("예약 점검 %s: %s" % (sid, s["url"]))
    for _ in range(120):
        lock = take_lock()
        if lock:
            break
        time.sleep(30)
    else:
        log("예약 점검 건너뜀: 다른 점검이 60분 넘게 끝나지 않았습니다")
        return close()
    try:
        run_all(s["url"], log, None, s["minutes"])
    except Exception as e:
        log("예약 점검 오류: %r" % e)
    finally:
        lock.close()
        close()


def ui_html():
    """화면 HTML. 동봉 글꼴을 data URI로 넣는다: 창 모드·report.html 모두 인터넷 없이, 보고서 파일을 옮겨도 같은 글꼴 (todo/13)"""
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    with open(os.path.join(d, "ui.html"), encoding="utf-8") as f:
        page = f.read()
    try:
        with open(os.path.join(d, "adguard-sans.woff2"), "rb") as f:
            font = base64.b64encode(f.read()).decode()
    except OSError:  # 글꼴이 없으면 시스템 글꼴(맑은 고딕)로
        return page
    return page.replace("/*FONT*/", '@font-face { font-family: "adGuard Sans"; src: url(data:font/woff2;base64,%s) format("woff2"); '
                                    'font-weight: 400 700; font-display: swap; }' % font, 1)


class Api:
    """화면(JS)이 부르는 함수. JS는 state()를 0.5초마다 읽는다 (WebView2·예비 서버 공통)"""

    def __init__(self, smoke=False):
        self._window = None  # 밑줄: JS에 노출하지 않음
        self._smoke = smoke
        self._s, self._ctl, self._t0 = {"phase": "idle", "log": []}, {}, 0

    def start(self, url, minutes=20):
        """반환: 시작하지 못한 이유 (시작하면 None)"""
        if self._s["phase"] in ("running", "report"):
            return None
        self._lock = take_lock()
        if not self._lock:
            return "예약 점검이 진행 중입니다. 끝난 뒤 다시 시작하세요."
        url = fix_url(url)
        minutes = max(1, min(25, int(minutes or 20)))  # 25분: 보고서까지 끝나도 평가 상한 30분에 여유
        self._s, self._ctl, self._t0 = {"phase": "running", "log": [], "url": url, "minutes": minutes}, {}, time.monotonic()
        threading.Thread(target=self._run, args=(url, minutes), daemon=True).start()

    def stop(self):
        c = self._ctl.get("crawler")
        if c and self._s["phase"] == "running":
            c.stop()
            self._s["stopping"] = True

    def state(self):
        s, c = self._s, self._ctl.get("crawler")
        out = {k: v for k, v in s.items() if k != "log"}
        out["log"] = s["log"][-200:]
        if c:
            out.update(visited=c.visited, queue=len(c.heap), found=sum(len(r["result"] or []) for r in c.results),
                       current=c.results[-1]["url"] if c.results else None,
                       # 진행 화면 "방금 찾은 광고": 최근 4건의 유형·페이지만 (원문은 넘기지 않는다)
                       recent=[{"technique": x["technique"], "url": r["url"], "location": x["location"]}
                               for r in reversed(c.results) for x in reversed(r["result"] or [])][:4])
        out["shot"] = self._ctl.get("shot")
        if s["phase"] in ("running", "report"):
            out["elapsed"] = round(time.monotonic() - self._t0, 1)
        return out

    def open(self, what):
        import webbrowser
        name = {"report": "report.html", "csv": "result.csv", "json": "result.json", "folder": ""}[what]
        webbrowser.open(pathlib.Path(base_dir(), name).as_uri())

    def set_status(self, fp, status, memo=""):
        """조치 상태 저장(status.json). 지금 화면 데이터에도 반영해 다시 그려도 남는다"""
        import report
        ok = report.set_status(base_dir(), fp, status, memo)
        for g in (self._s.get("data") or {}).get("groups", []):
            if ok and g["fp"] == fp:
                g["status"] = report.load_status(base_dir())[fp]
        return ok

    def ai(self):
        return ai_status()

    def set_key(self, key):
        """첫 화면에서 넣은 키를 .env에 저장하고 바로 확인한다. 빈 값이면 키를 지운다"""
        key = (key or "").strip()
        saved = save_key(key)
        st = ai_status()
        st["saved"] = os.path.basename(saved) if saved else None
        return st

    def schedules(self):
        nxt = next_runs()
        return [dict(x, next=nxt.get(x["id"])) for x in schedules()]

    def add_schedule(self, s):
        return add_schedule(s)

    def del_schedule(self, sid):
        del_schedule(sid)

    def records(self):
        import report
        return report.records(base_dir())

    def record(self, name):
        import report
        return report.read_record(base_dir(), name)

    def _run(self, url, minutes):
        flog, close = open_log()

        def log(msg):
            flog(msg)
            self._s["log"].append(msg)

        try:
            # 탐지 중 → (on_done) 보고서 작성 중 → (run_all 끝) 탐지 완료. 시계는 보고서까지 간다
            self._s["data"] = run_all(url, log, self._ctl, minutes, lambda meta, items: self._s.update(phase="report", found=len(items)))
            self._s["phase"] = "ready"
        except Exception as e:
            log("오류: %r" % e)
            self._s["phase"] = "error"
        self._lock.close()
        close()
        if self._smoke:
            self._window.destroy()


def serve(api):
    """WebView2 창을 못 띄울 때 예비 경로: 127.0.0.1 임의 포트 + 기본 브라우저. 같은 ui.html, API는 POST로"""
    import secrets
    import webbrowser
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    token = secrets.token_urlsafe(16)  # 다른 웹페이지가 로컬 API를 부르지 못하게 주소에 토큰

    class H(BaseHTTPRequestHandler):
        def reply(self, body, ctype):
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path != "/%s/" % token:
                return self.send_error(404)
            self.reply(ui_html().encode("utf-8"), "text/html; charset=utf-8")

        def do_POST(self):
            name = self.path.rsplit("/", 1)[-1]
            if not self.path.startswith("/%s/api/" % token) or name not in ("start", "stop", "state", "open", "records", "record", "set_status", "ai", "set_key", "schedules", "add_schedule", "del_schedule"):
                return self.send_error(404)
            args = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"[]")
            self.reply(json.dumps(getattr(api, name)(*args), ensure_ascii=False).encode("utf-8"), "application/json")

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    url = "http://127.0.0.1:%d/%s/" % (srv.server_port, token)
    print("UI: 예비 경로(기본 브라우저) %s" % url, flush=True)
    webbrowser.open(url)
    srv.serve_forever()


def hide_own_console():
    # exe를 더블클릭해서 콘솔이 이 프로세스 혼자 것이면 숨긴다 (cmd에서 실행했으면 그대로 둔다)
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32
        if k.GetConsoleProcessList((ctypes.c_uint * 2)(), 2) == 1:
            ctypes.windll.user32.ShowWindow(k.GetConsoleWindow(), 0)


def gui(smoke_url=None):
    api = Api(smoke=bool(smoke_url))
    try:
        import webview

        api._window = webview.create_window("adGuard 불법광고 탐지", html=ui_html(), js_api=api, width=1200, height=860,
                                            min_size=(720, 560))
        if smoke_url:  # 창이 뜨면 URL을 넣고 "탐지 시작"을 누른 것과 같게 한다
            api._window.events.loaded += lambda: api._window.evaluate_js(
                "function go(){document.getElementById('url').value=%s; start();}"
                "if (window.pywebview && pywebview.api && pywebview.api.start) go(); else window.addEventListener('pywebviewready', go);"
                % json.dumps(smoke_url))
        else:
            hide_own_console()
        webview.start(gui="edgechromium")  # IE 엔진으로 넘어가지 않게 WebView2만 허용
        print("UI: WebView2 창 종료", flush=True)
    except Exception as e:
        if smoke_url:
            raise
        print("UI: WebView2 실패(%r), 기본 브라우저로 엽니다" % e, flush=True)
        serve(api)


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # Windows에서 출력을 파일로 돌려도 한글이 깨지지 않게
    args = sys.argv[1:]
    env = load_env()
    print("설정: %s" % (env or ".env 없음, AI 꺼짐"), flush=True)
    if args[:1] in (["--smoke-gui"], ["--no-report"], ["--scheduled"]) and len(args) < 2:
        sys.exit("사용법: adguard.exe %s <URL>" % args[0])
    if args[:1] == ["--smoke-gui"]:
        gui(fix_url(args[1]))
    elif args[:1] == ["--scheduled"]:
        run_scheduled(args[1])
    elif args[:1] == ["--no-report"]:  # 탐지와 결과 파일만 (보고서·캡처 생략). 채점 자동화용
        scan(fix_url(args[1]))
    elif args:
        run_all(fix_url(args[0]))
    else:
        gui()


if __name__ == "__main__":
    main()
