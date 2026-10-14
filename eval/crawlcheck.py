"""크롤러 도달 검사: 크롤러가 analyze를 부르는 시점의 DOM에서 정답·extra location이 정확히 1개 요소를 가리키는지 본다.
(페이지 방문 누락, iframe 미로드, 늦게 삽입·클릭해야 생기는 요소 누락을 한 번에 잡는다)

    python eval/crawlcheck.py [S1-baseline S2-realistic ...]   (기본: S0~S4)
    python eval/crawlcheck.py blind                             (blind는 개수만 출력)
"""
import asyncio
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "app"), os.path.join(ROOT, "eval", "scorer")]
import crawler  # noqa: E402
import score  # noqa: E402


async def count(page, location):
    """score.Resolver.resolve의 비동기판: location이 가리키는 요소 수"""
    parts = [p.strip() for p in location.split(">>>")]
    fr, root = page.main_frame, None
    for p in parts[:-1]:
        scope = root or fr
        m = score.IFRAME_SRC.match(p)
        if m:
            want = score.norm_url(m.group(1))
            hs = [h for h in await scope.query_selector_all("iframe") if score.norm_url(await h.evaluate("e => e.src") or "") == want]
        else:
            hs = await scope.query_selector_all(p)
        if len(hs) != 1:
            return 0
        if await hs[0].evaluate("e => e.tagName") == "IFRAME":
            fr, root = await hs[0].content_frame(), None
            if fr is None:
                return 0
        else:
            root = (await hs[0].evaluate_handle("e => e.shadowRoot")).as_element()
            if root is None:
                return 0
    return len(await root.query_selector_all(parts[-1]) if root else await fr.locator(parts[-1]).element_handles())


def check(name):
    d = score.scenario_dir(name)
    ans = json.load(open(os.path.join(d, "answer.json"), encoding="utf-8"))
    items = ans["answers"] + ans.get("extra", [])
    by_url = {}
    for a in items:
        by_url.setdefault(score.norm_url(a["url"]), []).append(a)

    async def analyze(page, url):
        out = []
        for a in by_url.get(score.norm_url(url), []):
            n = await crawler.with_timeout(count(page, a["location"]), 5)
            out.append((a["location"], n))
        return out

    proc = score.serve(name)
    try:
        t0 = time.monotonic()
        res = asyncio.run(crawler.crawl(ans["entry_url"], analyze, log=lambda m: None))
        sec = time.monotonic() - t0
    finally:
        if proc:
            proc.kill()
    found = {}
    for r in res:
        for loc, n in r["result"] or []:
            found[(score.norm_url(r["url"]), loc)] = n
    miss_page = [a for a in items if score.norm_url(a["url"]) not in {score.norm_url(r["url"]) for r in res}]
    miss_elem = [a for a in items if a not in miss_page and found.get((score.norm_url(a["url"]), a["location"])) != 1]
    print("%-13s 결과 페이지 %4d  %6.1f초  정답·extra %d건 중 페이지 누락 %d, 요소 누락 %d"
          % (name, len(res), sec, len(items), len(miss_page), len(miss_elem)))
    if name != "blind":
        for a in miss_page:
            print("  페이지 누락:", a.get("id", "-"), a["url"])
        for a in miss_elem:
            print("  요소 누락:", a.get("id", "-"), a["url"], a["location"], found.get((score.norm_url(a["url"]), a["location"])))
    return not miss_page and not miss_elem


if __name__ == "__main__":
    names = sys.argv[1:] or ["S0-empty", "S1-baseline", "S2-realistic", "S3-stress", "S4-dynamic"]
    sys.exit(0 if all([check(n) for n in names]) else 1)
