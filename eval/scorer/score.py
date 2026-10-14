"""자체 적격평가 채점기 (모집요강 6·10~12쪽 규칙).

사용:
  python eval/scorer/score.py <시나리오> <result.json> [--extra result_extra.json] [--json report.json]
  python eval/scorer/score.py --self-test <시나리오>
  <시나리오>: S0-empty, S1-baseline, S2-realistic, S3-stress, blind (blind는 놓친 건의 내용을 보여주지 않는다)

채점 규칙:
- url·location·technique이 모두 일치해야 정답. url은 끝 /, http/https, # 이하를 무시하고 쿼리 순서만 다르면 같은 페이지
- location은 문자열이 아니라 렌더링된 페이지에서 같은 요소를 가리키는지로 비교. 0개나 2개 이상을 가리키면 오답
- iframe 단계 `iframe[src="..."]`의 src는 절대 주소로 바꿔서 비교
- url·location·technique이 같은 항목은 1건으로 합침
- 스키마를 지키지 않은 항목은 오답(정확도 분모에 포함). 파일 전체를 파싱할 수 없으면 0점
- 점수 환산(가정): 검출 개수 45 × 재현율, 정확도 35 × 정밀도,
  시간 20 = 목표 시간 이하면 20, 30분 초과면 0, 그 사이는 선형
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

EVAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TECH = {"HOMOGLYPH", "JAMO", "TRANSPARENT", "OFFSCREEN"}
TIME_TARGET = {"S2-realistic": 180, "S3-stress": 600}  # eval/README.md 통과 기준 (초)
INIT = ("const o=Element.prototype.attachShadow;"
        "Element.prototype.attachShadow=function(i){return o.call(this,Object.assign({},i,{mode:'open'}))}")
IFRAME_SRC = re.compile(r'^iframe\[src="([^"]+)"\]$')


def norm_url(u):
    s = urllib.parse.urlsplit(u.strip())
    path = s.path.rstrip("/") or "/"
    q = "&".join(sorted(x for x in s.query.split("&") if x))
    return "%s%s%s" % (s.netloc.lower(), path, "?" + q if q else "")


def scenario_dir(name):
    d = os.path.join(EVAL, "blind") if name == "blind" else os.path.join(EVAL, "scenarios", name)
    if not os.path.isfile(os.path.join(d, "answer.json")):
        sys.exit("시나리오를 찾을 수 없음: %s" % name)
    return d


# ---------- 스키마 ----------

def load_result(path):
    """(meta, findings, invalid, fatal) — invalid는 스키마 위반 항목 수"""
    try:
        raw = open(path, "rb").read()
    except OSError as e:
        return None, [], 0, "파일 없음: %s" % e
    problems = []
    if raw.startswith(b"\xef\xbb\xbf"):
        problems.append("BOM 있음")
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return None, [], 0, "파싱 불가: %s" % e
    if not isinstance(data, dict) or set(data) != {"meta", "findings"}:
        problems.append("최상위 키가 meta·findings 두 개가 아님: %s" % (list(data) if isinstance(data, dict) else type(data).__name__))
    meta = data.get("meta") if isinstance(data, dict) else None
    fnd = data.get("findings") if isinstance(data, dict) else None
    if not isinstance(fnd, list):
        return meta, [], 0, "findings가 배열이 아님"
    m = meta if isinstance(meta, dict) else {}
    for k, t in (("topic", str), ("entry_url", str), ("started_at", str), ("finished_at", str), ("elapsed_sec", (int, float))):
        if not isinstance(m.get(k), t) or isinstance(m.get(k), bool):
            problems.append("meta.%s 누락·형식 오류" % k)
    if m.get("topic") not in (None, "TOPIC"):
        problems.append('meta.topic이 "TOPIC"이 아님')
    valid, invalid, ids = [], 0, set()
    for f in fnd:
        ok = (isinstance(f, dict)
              and all(isinstance(f.get(k), str) and f.get(k) for k in ("id", "url", "location", "technique"))
              and isinstance(f.get("evidence_text"), str)
              and f.get("is_violation") is True
              and f["technique"] in TECH
              and f["id"] not in ids)
        if ok:
            ids.add(f["id"])
            valid.append(f)
        else:
            invalid += 1
    if invalid:
        problems.append("스키마 위반 항목 %d건 (오답 처리)" % invalid)
    return {"meta": m, "problems": problems}, valid, invalid, None


# ---------- 요소 식별 ----------

class Resolver:
    """url별로 한 번 렌더링하고, location을 (프레임 번호, 요소 번호)로 바꾼다."""

    def __init__(self, ctx, clicks=None):
        self.ctx, self.pages, self.clicks = ctx, {}, clicks or {}

    def page(self, url):
        key = norm_url(url)
        if key not in self.pages:
            pg = self.ctx.new_page()
            try:
                pg.goto(url, wait_until="load", timeout=30000)
                pg.mouse.wheel(0, 400000)  # lazy iframe 로드
                pg.wait_for_timeout(2500)  # 늦게 삽입되는 요소
                for sel in self.clicks.get(key, []):  # 정답의 click: 눌러야 생기는 요소 (예: 댓글 더보기)
                    pg.locator(sel).first.click(timeout=5000)
                    pg.wait_for_timeout(1000)
            except Exception:
                pass
            self.pages[key] = pg
        return self.pages[key]

    def resolve(self, url, location):
        """(키, 사유). 키는 요소 1개를 정확히 가리킬 때만 반환"""
        pg = self.page(url)
        parts = [p.strip() for p in location.split(">>>")]
        fr, root = pg.main_frame, None  # root: Shadow DOM 안으로 들어갔을 때의 shadowRoot
        try:
            for p in parts[:-1]:
                scope = root or fr
                m = IFRAME_SRC.match(p)
                if m:
                    want = norm_url(m.group(1))
                    hs = [h for h in scope.query_selector_all("iframe") if norm_url(h.evaluate("e => e.src") or "") == want]
                else:
                    hs = scope.query_selector_all(p)
                if len(hs) != 1:
                    return None, "%d개를 가리키는 중간 단계: %s" % (len(hs), p)
                if hs[0].evaluate("e => e.tagName") == "IFRAME":  # iframe 안으로
                    fr, root = hs[0].content_frame(), None
                    if fr is None:
                        return None, "iframe 내용 없음: %s" % p
                else:  # Shadow DOM 호스트 안으로
                    sr = hs[0].evaluate_handle("e => e.shadowRoot").as_element()
                    if sr is None:
                        return None, "iframe도 Shadow DOM 호스트도 아님: %s" % p
                    root = sr
            hs = root.query_selector_all(parts[-1]) if root else fr.locator(parts[-1]).element_handles()
        except Exception as e:
            return None, "선택자 오류: %s" % str(e).splitlines()[0][:80]
        if len(hs) != 1:
            return None, "요소 %d개를 가리킴" % len(hs)
        seq = hs[0].evaluate("e => e.__adg || (e.__adg = (window.__adgSeq = (window.__adgSeq || 0) + 1))")
        return (pg.frames.index(fr), seq), None


# ---------- 채점 ----------

def score(name, result_path, extra_path=None):
    from playwright.sync_api import sync_playwright

    d = scenario_dir(name)
    ans = json.load(open(os.path.join(d, "answer.json"), encoding="utf-8"))
    meta, findings, invalid, fatal = load_result(result_path)
    rep = {"scenario": name, "fatal": fatal, "schema_problems": (meta or {}).get("problems", [])}
    if fatal:
        rep.update(recall=0, precision=0, points={"검출 개수": 0, "정확도": 0, "시간": 0, "합계": 0})
        return rep

    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1920, "height": 1080})
        ctx.add_init_script(INIT)
        clicks = {}
        for a in ans["answers"]:
            if a.get("click"):  # 같은 페이지에 click이 여러 정답에 있으면 가장 긴 것 (앞부분이 같다고 가정)
                k = norm_url(a["url"])
                clicks[k] = max(clicks.get(k, []), a["click"], key=len)
        R = Resolver(ctx, clicks)

        def key_of(item):
            k, why = R.resolve(item["url"], item["location"])
            return (norm_url(item["url"]),) + k if k else None, why

        akeys = {}  # (url, frame, seq, tech) -> answer
        for a in ans["answers"]:
            k, why = key_of(a)
            if k is None:
                raise SystemExit("정답표 오류 %s" % (a["id"] if name == "blind" else "%s: %s" % (a["id"], why)))
            akeys[k + (a["technique"],)] = a
        dkeys = {}
        for x in ans.get("decoys", []) + ans.get("extra", []):
            k, _ = key_of(x)
            if k:
                dkeys[k] = x
        answered_elems = {k[:3]: a for k, a in akeys.items()}

        hit, fps, seen = set(), [], set()
        for f in findings:
            k, why = key_of(f)
            if k is None:
                fps.append((f, "location: " + why))
                continue
            full = k + (f["technique"],)
            if full in seen:
                continue  # 중복은 1건으로 합침
            seen.add(full)
            if full in akeys:
                hit.add(full)
            elif k in answered_elems:
                fps.append((f, "기법 불일치 (정답 요소이나 다른 technique)"))
            elif k in dkeys:
                fps.append((f, "미끼 %s: %s" % (",".join(dkeys[k].get("covers", [])), dkeys[k].get("note", ""))))
            else:
                fps.append((f, "정답·미끼에 없는 요소"))
        b.close()

    total_found = len(seen) + len([x for x in fps if x[1].startswith("location")]) + invalid
    recall = len(hit) / len(akeys) if akeys else 1.0
    precision = len(hit) / total_found if total_found else (1.0 if not akeys else 0.0)
    el = (meta or {}).get("meta", {}).get("elapsed_sec")
    target = TIME_TARGET.get(name, 180)
    t_pts = 0.0 if not isinstance(el, (int, float)) or el > 1800 else 20.0 if el <= target else 20.0 * (1800 - el) / (1800 - target)
    pts = {"검출 개수": round(45 * recall, 2), "정확도": round(35 * precision, 2), "시간": round(t_pts, 2)}
    pts["합계"] = round(sum(pts.values()), 2)
    missed = [a for k, a in akeys.items() if k not in hit]
    rep.update(answers=len(akeys), hit=len(hit), findings=total_found, invalid=invalid, recall=round(recall, 4),
               precision=round(precision, 4), elapsed_sec=el, time_target=target, points=pts,
               missed=[{"id": a["id"], "url": a["url"], "location": a["location"], "technique": a["technique"],
                        "covers": a.get("covers"), "note": a.get("note", "")} for a in missed],
               false_positives=[{"url": f["url"], "location": f["location"], "technique": f["technique"], "reason": r} for f, r in fps])
    if extra_path:
        rep["extra"] = check_extra(extra_path, ans.get("extra", []))
    rep["pass"] = {
        "재현율 100%" if name != "blind" else "재현율 95% 이상": recall >= (0.95 if name == "blind" else 1.0),
        "정밀도 98% 이상": precision >= 0.98,
        "스키마 문제 없음": not rep["schema_problems"],
        "목표 시간 이내": isinstance(el, (int, float)) and el <= target,
    }
    return rep


def check_extra(path, expected):
    """result_extra.json: 기대하는 extra 항목이 url 기준으로 몇 건 나왔는지만 본다 (본심사 자료)"""
    try:
        data = json.loads(open(path, "rb").read().decode("utf-8"))
        got = {norm_url(f.get("url", "")) for f in data.get("findings", []) if f.get("technique") == "ETC"}
    except Exception as e:
        return {"error": str(e)}
    want = {norm_url(x["url"]) for x in expected}
    return {"expected_pages": len(want), "found_pages": len(want & got)}


# ---------- 서버·출력 ----------

def serve(name):
    d = scenario_dir(name)
    entry = json.load(open(os.path.join(d, "answer.json"), encoding="utf-8"))["entry_url"]
    try:
        urllib.request.urlopen(entry, timeout=2)
        return None  # 이미 떠 있음
    except Exception:
        pass
    proc = subprocess.Popen([sys.executable, "serve.py"], cwd=d, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            urllib.request.urlopen(entry, timeout=2)
            return proc
        except Exception:
            time.sleep(0.2)
    proc.kill()
    sys.exit("서버를 띄우지 못함: %s" % name)


def show(rep, blind):
    print("== %s ==" % rep["scenario"])
    if rep.get("fatal"):
        print("0점: %s" % rep["fatal"])
        return
    for p in rep["schema_problems"]:
        print("스키마: %s" % p)
    print("정답 %d건 중 %d건 검출 (재현율 %.1f%%), 탐지 %d건 중 정탐 %d건 (정밀도 %.1f%%), 시간 %ss / 목표 %ss"
          % (rep["answers"], rep["hit"], rep["recall"] * 100, rep["findings"], rep["hit"], rep["precision"] * 100,
             rep["elapsed_sec"], rep["time_target"]))
    print("환산 점수: %s" % ", ".join("%s %s" % kv for kv in rep["points"].items()))
    if blind:
        print("놓친 건 %d건, 오탐 %d건 (블라인드: 내용 비공개)" % (len(rep["missed"]), len(rep["false_positives"])))
    else:
        for m in rep["missed"]:
            print("  놓침  %s %s | %s | %s %s" % (m["id"], m["technique"], m["url"], m["location"], m["covers"]))
        for f in rep["false_positives"]:
            print("  오탐  %s | %s | %s | %s" % (f["technique"], f["url"], f["location"], f["reason"]))
    if "extra" in rep:
        print("extra: %s" % rep["extra"])
    print("통과 기준: %s" % ", ".join("%s %s" % (k, "O" if v else "X") for k, v in rep["pass"].items()))


def self_test(name, tmp):
    """정답표를 결과로 넣으면 100%, 빈 결과면 재현율 0, 미끼를 섞으면 정밀도 하락"""
    ans = json.load(open(os.path.join(scenario_dir(name), "answer.json"), encoding="utf-8"))
    meta = {"topic": "TOPIC", "entry_url": ans["entry_url"], "started_at": "2026-10-14T00:00:00+09:00",
            "finished_at": "2026-10-14T00:01:00+09:00", "elapsed_sec": 60}
    full = [dict(id="f_%03d" % i, url=a["url"], is_violation=True, location=a["location"], evidence_text=a["evidence_text"],
                 technique=a["technique"]) for i, a in enumerate(ans["answers"])]
    decoy = [dict(id="d_%03d" % i, url=x["url"], is_violation=True, location=x["location"], evidence_text="",
                  technique="OFFSCREEN") for i, x in enumerate(ans.get("decoys", []))
             if "OUT_OF_SCOPE" not in x.get("covers", [])]
    dup = [dict(f, id="g_%03d" % i) for i, f in enumerate(full)]  # id는 달라야 함 (같으면 스키마 위반)
    cases = {"정답 그대로": full, "빈 결과": [], "정답 + 미끼": full + decoy, "정답 중복 2배": full + dup}
    ok = True
    for label, fs in cases.items():
        path = os.path.join(tmp, "self_test_result.json")
        json.dump({"meta": meta, "findings": fs}, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        r = score(name, path)
        expect = {"정답 그대로": (1.0, 1.0), "빈 결과": (0.0 if full else 1.0, 1.0 if not full else 0.0),
                  "정답 + 미끼": (1.0, len(full) / (len(full) + len(decoy)) if full or decoy else 1.0),
                  "정답 중복 2배": (1.0, 1.0)}[label]
        good = abs(r["recall"] - expect[0]) < 1e-3 and abs(r["precision"] - expect[1]) < 1e-3
        ok &= good
        print("%s %s: 재현율 %.3f 정밀도 %.3f (기대 %.3f / %.3f)" % ("OK " if good else "BAD", label, r["recall"], r["precision"], *expect))
    return ok


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("result", nargs="?")
    ap.add_argument("--extra")
    ap.add_argument("--json")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    proc = serve(a.scenario)
    try:
        if a.self_test:
            ok = self_test(a.scenario, os.path.dirname(os.path.abspath(__file__)))
            os.remove(os.path.join(os.path.dirname(os.path.abspath(__file__)), "self_test_result.json"))
            sys.exit(0 if ok else 1)
        rep = score(a.scenario, a.result, a.extra)
        show(rep, a.scenario == "blind")
        if a.json:
            if a.scenario == "blind":  # 블라인드는 내용 없이 숫자만 저장
                rep = {k: v for k, v in rep.items() if k not in ("missed", "false_positives")}
            json.dump(rep, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    finally:
        if proc:
            proc.terminate()


if __name__ == "__main__":
    main()
