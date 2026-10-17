"""result.json 스키마 검증 (모집요강 붙임4). 채점기보다 엄격하게 본다.

사용: python eval/validate.py <result.json> [...]   → 문제 없으면 종료 코드 0
파일 이름이 result_extra.json이면 technique "ETC" + extra_finding을 요구한다.
"""
import json
import math
import os
import sys
import urllib.parse
from datetime import datetime

TECH = {"HOMOGLYPH", "JAMO", "TRANSPARENT", "OFFSCREEN"}


def iso(s):
    try:
        return isinstance(s, str) and datetime.fromisoformat(s).tzinfo is not None
    except ValueError:
        return False


def url_key(u):
    """채점 규칙의 같은 페이지: 끝 /, http/https, # 이하 무시, 쿼리 순서 무시 (eval/scorer norm_url과 같음)"""
    s = urllib.parse.urlsplit(str(u).strip())
    return s.netloc.lower() + (s.path.rstrip("/") or "/") + "?" + "&".join(sorted(x for x in s.query.split("&") if x))


def validate(path):
    raw = open(path, "rb").read()
    if raw.startswith(b"\xef\xbb\xbf"):
        return ["BOM 있음"]
    try:
        data = json.loads(raw.decode("utf-8"), parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
    except ValueError as e:  # UnicodeDecodeError·JSONDecodeError 포함
        return ["파싱 불가: %s" % e]
    if not isinstance(data, dict) or set(data) != {"meta", "findings"}:
        return ["최상위 키가 meta·findings 두 개가 아님"]
    p, m, fs = [], data["meta"], data["findings"]
    extra = os.path.basename(path) == "result_extra.json"
    if not isinstance(m, dict):
        return ["meta가 객체가 아님"]
    if m.get("topic") != "TOPIC":
        p.append('meta.topic != "TOPIC"')
    if not (isinstance(m.get("entry_url"), str) and m["entry_url"]):
        p.append("meta.entry_url 누락")
    for k in ("started_at", "finished_at"):
        if not iso(m.get(k)):
            p.append("meta.%s가 시간대 있는 ISO 8601이 아님: %r" % (k, m.get(k)))
    e = m.get("elapsed_sec")
    if isinstance(e, bool) or not isinstance(e, (int, float)) or not math.isfinite(e) or e < 0:
        p.append("meta.elapsed_sec가 0 이상 숫자가 아님: %r" % (e,))
    if "tool_version" in m and not isinstance(m["tool_version"], str):
        p.append("meta.tool_version이 문자열이 아님")
    if not isinstance(fs, list):
        return p + ["findings가 배열이 아님"]
    ids, keys = set(), set()
    for i, f in enumerate(fs):
        w = "findings[%d]" % i
        if not isinstance(f, dict):
            p.append(w + " 객체가 아님")
            continue
        for k in ("id", "url", "location", "evidence_text", "technique"):
            if not (isinstance(f.get(k), str) and f[k].strip()):
                p.append("%s.%s 누락·빈 문자열" % (w, k))
        if f.get("is_violation") is not True:
            p.append(w + ".is_violation이 true가 아님")
        if not str(f.get("url", "")).startswith(("http://", "https://")):
            p.append(w + ".url이 전체 URL이 아님")
        if extra:
            if f.get("technique") != "ETC" or not (isinstance(f.get("extra_finding"), str) and f["extra_finding"]):
                p.append(w + ' technique "ETC"·extra_finding 필요')
        elif f.get("technique") not in TECH:
            p.append("%s.technique이 4종 중 하나가 아님: %r" % (w, f.get("technique")))
        if f.get("id") in ids:
            p.append("%s.id 중복: %r" % (w, f.get("id")))
        ids.add(f.get("id"))
        key = (url_key(f.get("url")), f.get("location"), f.get("technique"), f.get("extra_finding"))
        if key in keys:
            p.append(w + " (url, location, technique) 중복")
        keys.add(key)
    return p


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    bad = 0
    for path in sys.argv[1:] or ["result.json"]:
        p = validate(path)
        bad += bool(p)
        print("%s %s%s" % ("FAIL" if p else "OK  ", path, "".join("\n  - " + x for x in p)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
