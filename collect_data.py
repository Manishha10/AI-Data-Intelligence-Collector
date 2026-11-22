#!/usr/bin/env python3
"""
One-run AI Data Intelligence collector.
Fetches public startup/product/paper datasets and 24-hour AI news/job records.
Only keeps records with traceable source URLs. No fabricated rows.
"""
import asyncio, csv, io, json, re, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
import feedparser
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

OUT = Path("output")
OUT.mkdir(exist_ok=True)
NOW = datetime.now(timezone.utc)
CUTOFF = NOW - timedelta(hours=24)
HEADERS = {"User-Agent": "AIDataIntelligenceStudentProject/1.0 (educational; contact: add-your-email@example.com)"}
TIMEOUT = aiohttp.ClientTimeout(total=35)
SEM = asyncio.Semaphore(8)

NEWS_FEEDS = {
    "The World of AI Daily": "https://theworldofai.org/ai-news/feed.xml",
    "OpenAI News": "https://openai.com/news/rss.xml",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "Google DeepMind": "https://deepmind.google/blog/rss.xml",
    "The Decoder": "https://the-decoder.com/feed/",
}
JOB_SOURCES = {
    "Himalayas API": "https://himalayas.app/jobs/api?limit=100",
    "MOAI Jobs RSS": "https://www.moaijobs.com/rss",
    "Remotive API": "https://remotive.com/api/remote-jobs?category=software-dev&limit=100",
    "RemoteOK API": "https://remoteok.com/api",
    "Arbeitnow API": "https://www.arbeitnow.com/api/job-board-api",
}
AI_TERMS = re.compile(r"\b(ai|artificial intelligence|machine learning|ml engineer|deep learning|llm|generative ai|nlp|computer vision|data scientist|robotics|MLOps|prompt engineer)\b", re.I)

def parse_dt(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        try: return datetime.fromtimestamp(value, timezone.utc)
        except Exception: return None
    s = str(value).strip()
    try:
        from dateutil import parser
        d = parser.parse(s)
        if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
            return d.astimezone(timezone.utc)
        except Exception:
            return None

async def get_text(session, url):
    async with SEM:
        for attempt in range(4):
            try:
                async with session.get(url, headers=HEADERS) as resp:
                    if resp.status == 429 or resp.status >= 500:
                        await asyncio.sleep(min(2 ** attempt, 12))
                        continue
                    resp.raise_for_status()
                    return await resp.text()
            except Exception:
                if attempt == 3: return None
                await asyncio.sleep(min(2 ** attempt, 8))
    return None

async def get_json(session, url):
    raw = await get_text(session, url)
    if not raw: return None
    try: return json.loads(raw)
    except Exception: return None

def unique_by(rows, key):
    seen, out = set(), []
    for r in rows:
        k = str(r.get(key, "")).strip().lower()
        if k and k not in seen:
            seen.add(k); out.append(r)
    return out

async def collect_products(session):
    url = "https://agipicks.com/data/tools.json"
    data = await get_json(session, url)
    rows = []
    items = data if isinstance(data, list) else (data.get("tools", []) if isinstance(data, dict) else [])
    for x in items:
        name = x.get("name") or x.get("title")
        website = x.get("website") or x.get("url")
        if not name or not website: continue
        rows.append({
            "schemaVersion":"1.0", "recordType":"PRODUCT",
            "source.name":"AGIPicks open dataset", "source.url":url,
            "content.productName":name, "content.startupName":x.get("vendor") or "",
            "content.pricingModel":str(x.get("pricingModel") or "").upper(),
            "content.website":website, "content.category":x.get("category") or "",
            "content.verifiedAt":x.get("verifiedAt") or x.get("pricesCheckedAt") or "",
            "collectedAt":NOW.isoformat()
        })
    return unique_by(rows, "content.website")

async def collect_startups(session):
    """Discover CSV/JSON files in a public GitHub repository and select a company dataset."""
    api = "https://api.github.com/repos/yigitmeteozcan/startups"
    meta = await get_json(session, api)
    if not meta:
        print("WARNING: Startup dataset repository could not be reached.")
        return []
    branch = meta.get("default_branch", "main")
    tree = await get_json(session, f"https://api.github.com/repos/yigitmeteozcan/startups/git/trees/{branch}?recursive=1")
    if not tree: return []
    candidates = [x for x in tree.get("tree", []) if x.get("type") == "blob" and
                  x.get("path","").lower().endswith((".csv",".json")) and
                  any(k in x.get("path","").lower() for k in ("startup","company","portfolio","data"))]
    rows_best = []
    for item in candidates[:15]:
        raw = await get_text(session, item.get("url",""))
        if not raw: continue
        # GitHub blob API is base64 JSON; use download_url when available via contents API.
        contents = await get_json(session, f"https://api.github.com/repos/yigitmeteozcan/startups/contents/{item['path']}?ref={branch}")
        if not contents or not contents.get("download_url"): continue
        body = await get_text(session, contents["download_url"])
        if not body: continue
        parsed = []
        try:
            if item["path"].lower().endswith(".csv"):
                reader = csv.DictReader(io.StringIO(body))
                parsed = list(reader)
            else:
                obj = json.loads(body)
                parsed = obj if isinstance(obj, list) else obj.get("data", obj.get("startups", []))
        except Exception:
            continue
        if len(parsed) > len(rows_best): rows_best = parsed
    out = []
    for x in rows_best:
        if not isinstance(x, dict): continue
        low = {str(k).lower().strip():v for k,v in x.items()}
        def pick(*keys):
            for k in keys:
                for kk,v in low.items():
                    if k in kk and v not in (None, ""): return v
            return ""
        name = pick("startup_name","company_name","company","startup","name")
        website = pick("website","url","domain","homepage")
        if not name: continue
        if isinstance(website, str) and website and not website.startswith(("http://","https://")):
            website = "https://" + website
        source_url = website or f"https://github.com/yigitmeteozcan/startups"
        out.append({
            "schemaVersion":"1.0", "recordType":"STARTUP",
            "source.name":"Startup Portfolios public dataset",
            "source.url":source_url,
            "content.entityName":str(name).strip(),
            "content.data.employeeCount":pick("employee_count","employees","team_size"),
            "content.website":website,
            "content.location":pick("location","headquarters","city"),
            "collectedAt":NOW.isoformat()
        })
    return unique_by(out, "content.entityName")

async def collect_papers(session):
    url = "https://export.arxiv.org/api/query?search_query=(cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL)&start=0&max_results=1000&sortBy=submittedDate&sortOrder=descending"
    raw = await get_text(session, url)
    if not raw: return []
    feed = feedparser.parse(raw)
    rows = []
    for e in feed.entries:
        title = re.sub(r"\s+", " ", e.get("title","")).strip()
        link = e.get("link","")
        if not title or not link: continue
        authors = [a.get("name","") for a in e.get("authors",[])]
        blob = " ".join([e.get("summary",""), e.get("arxiv_comment",""), e.get("comment","")])
        gh = re.search(r"https?://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", blob)
        gh_url, stars = "", ""
        if gh:
            gh_url = "https://github.com/" + gh.group(1).rstrip(".,)")
            repo = await get_json(session, "https://api.github.com/repos/" + gh.group(1).rstrip(".,)"))
            if repo: stars = repo.get("stargazers_count", "")
        published = e.get("published","")
        rows.append({
            "schemaVersion":"1.0","recordType":"RESEARCH_PAPER",
            "source.name":"arXiv API","source.url":link,
            "content.title":title,"content.authors":", ".join(authors),
            "content.paper_url":link,"content.github_url":gh_url,
            "content.github_stars":stars,"content.published_date":published,
            "collectedAt":NOW.isoformat()
        })
    return unique_by(rows, "content.paper_url")

async def extract_fulltext(session, url):
    html = await get_text(session, url)
    if not html: return ""
    try:
        import trafilatura
        return (trafilatura.extract(html, include_comments=False, include_tables=False) or "")[:12000]
    except Exception:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script","style","nav","footer","header"]): tag.decompose()
        return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))[:12000]

async def collect_news(session):
    all_rows = []
    for source, url in NEWS_FEEDS.items():
        raw = await get_text(session, url)
        if not raw: continue
        parsed = feedparser.parse(raw)
        for e in parsed.entries:
            link = e.get("link","")
            title = re.sub(r"\s+"," ",e.get("title","")).strip()
            published = parse_dt(e.get("published_parsed") and time.mktime(e.published_parsed) or e.get("published") or e.get("updated"))
            if not link or not title or not published or published < CUTOFF or published > NOW + timedelta(minutes=10):
                continue
            content = e.get("summary","") or ""
            if not content and e.get("content"): content = e.content[0].get("value","")
            from bs4 import BeautifulSoup
            summary = BeautifulSoup(content,"html.parser").get_text(" ",strip=True)
            full = await extract_fulltext(session, link)
            all_rows.append({
                "schemaVersion":"1.0","recordType":"NEWS",
                "source.name":source,"source.url":link,
                "content.title":title,"content.date":published.isoformat(),
                "content.summary":summary[:2500],"content.fullText":full,
                "collectedAt":NOW.isoformat()
            })
    return unique_by(all_rows, "source.url")

async def collect_jobs(session):
    rows = []
    # Himalayas public JSON API (cursor paging; first 10 pages maximum).
    cursor = None
    for _ in range(10):
        url = "https://himalayas.app/jobs/api?limit=100" + (f"&cursor={cursor}" if cursor else "")
        data = await get_json(session, url)
        if not data: break
        jobs = data if isinstance(data,list) else data.get("jobs",[])
        if not jobs: break
        for j in jobs:
            title = j.get("title","")
            desc = j.get("description","") or j.get("excerpt","")
            if not AI_TERMS.search(title + " " + desc[:1500]): continue
            dt = parse_dt(j.get("pubDate") or j.get("publishedAt") or j.get("createdAt") or j.get("date"))
            if not dt or dt < CUTOFF or dt > NOW + timedelta(minutes=10): continue
            link = j.get("applicationLink") or j.get("url") or j.get("guid")
            if not link: continue
            rows.append(job_row("Himalayas API", j.get("companyName") or j.get("company",""), title, link, dt, j.get("location",""), j.get("isRemote",False), desc))
        cursor = data.get("nextCursor") if isinstance(data,dict) else None
        if not cursor: break

    # MOAI RSS; feed contains a longer window, so strictly filter timestamps here.
    raw = await get_text(session, JOB_SOURCES["MOAI Jobs RSS"])
    if raw:
        for e in feedparser.parse(raw).entries:
            dt = parse_dt(e.get("published") or e.get("updated"))
            title = e.get("title","")
            link = e.get("link","")
            if not dt or dt < CUTOFF or dt > NOW + timedelta(minutes=10) or not AI_TERMS.search(title): continue
            desc = e.get("summary","")
            rows.append(job_row("MOAI Jobs RSS", "", title, link, dt, "", False, desc))

    # Remotive JSON
    data = await get_json(session, "https://remotive.com/api/remote-jobs?category=software-dev&limit=100")
    if data:
        for j in data.get("jobs",[]):
            title, desc = j.get("title",""), j.get("description","")
            if not AI_TERMS.search(title + " " + desc[:1500]): continue
            dt = parse_dt(j.get("publication_date"))
            if not dt or dt < CUTOFF or dt > NOW + timedelta(minutes=10): continue
            rows.append(job_row("Remotive API",j.get("company_name",""),title,j.get("url",""),dt,j.get("candidate_required_location",""),"remote" in str(j.get("job_type","")).lower(),desc))

    # RemoteOK JSON
    data = await get_json(session, "https://remoteok.com/api")
    if isinstance(data,list):
        for j in data:
            title, desc = j.get("position",""), j.get("description","")
            if not title or not AI_TERMS.search(title + " " + desc[:1500]): continue
            dt = parse_dt(j.get("date"))
            link = j.get("url") or (f"https://remoteok.com/remote-jobs/{j.get('id')}" if j.get("id") else "")
            if not dt or dt < CUTOFF or dt > NOW + timedelta(minutes=10) or not link: continue
            rows.append(job_row("RemoteOK API",j.get("company",""),title,link,dt,j.get("location",""),"remote" in str(j.get("location","")).lower(),desc))

    # Arbeitnow public API
    data = await get_json(session, "https://www.arbeitnow.com/api/job-board-api")
    if data:
        for j in data.get("data",[]):
            title, desc = j.get("title",""), j.get("description","")
            if not AI_TERMS.search(title + " " + desc[:1500]): continue
            dt = parse_dt(j.get("created_at"))
            if not dt or dt < CUTOFF or dt > NOW + timedelta(minutes=10): continue
            rows.append(job_row("Arbeitnow API",j.get("company_name",""),title,j.get("url",""),dt,j.get("location",""),j.get("remote",False),desc))
    return unique_by(rows, "source.url")

def job_row(source, company, title, link, dt, location, remote, description):
    from bs4 import BeautifulSoup
    desc = BeautifulSoup(str(description or ""), "html.parser").get_text(" ",strip=True)
    return {
        "schemaVersion":"1.0","recordType":"JOB",
        "source.name":source,"source.url":link,
        "content.company":company,"content.title":title,
        "content.date":dt.isoformat(),"content.is_remote":bool(remote),
        "content.location":location,"content.role_family":"AI/ML",
        "content.description":desc[:12000],"collectedAt":NOW.isoformat()
    }

def entity_log(startups, products):
    out = []
    for kind, rows, key in [("STARTUP",startups,"content.entityName"),("PRODUCT",products,"content.productName")]:
        for r in rows:
            raw = str(r.get(key,""))
            canonical = re.sub(r"\s+(inc\.?|llc|ltd\.?|corp\.?)$", "", raw, flags=re.I).strip()
            out.append({"recordType":kind,"rawName":raw,"canonicalName":canonical,"sourceURL":r.get("source.url",""),"resolution":"normalized suffix only"})
    return out

def write_workbook(tabs):
    path = OUT / "AI_Data_Intelligence_Collected.xlsx"
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in tabs.items():
        ws = wb.create_sheet(name)
        headers = list(rows[0].keys()) if rows else ["status"]
        ws.append(headers)
        for r in rows:
            ws.append([json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for v in r.values()] if rows else ["No verified records found during this run"])
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for c in ws[1]:
            c.font = Font(bold=True,color="FFFFFF")
            c.fill = PatternFill("solid",fgColor="244062")
            c.alignment = Alignment(wrap_text=True)
        for idx, col in enumerate(ws.columns,1):
            width = min(48,max(14,max((len(str(cell.value or "")) for cell in list(col)[:100]),default=12)+2))
            ws.column_dimensions[get_column_letter(idx)].width = width
    wb.save(path)
    return path

async def main():
    connector = aiohttp.TCPConnector(limit=12, ssl=False)
    async with aiohttp.ClientSession(timeout=TIMEOUT, connector=connector) as session:
        print("Collecting startup and product datasets...")
        startups, products = await asyncio.gather(collect_startups(session), collect_products(session))
        print("Collecting arXiv papers (up to 1,000)...")
        papers = await collect_papers(session)
        print("Collecting news published in the last 24 hours...")
        news = await collect_news(session)
        print("Collecting AI jobs published in the last 24 hours...")
        jobs = await collect_jobs(session)
    mapping = entity_log(startups, products)
    tabs = {"Startups":startups,"Products":products,"Research Papers":papers,"Jobs":jobs,"News":news,"Entity Mapping Log":mapping}
    path = write_workbook(tabs)
    summary = {
        "run_time_utc":NOW.isoformat(),"freshness_cutoff_utc":CUTOFF.isoformat(),
        "counts":{k:len(v) for k,v in tabs.items()},
        "targets":{"startups":1000,"products":1000,"research_papers":1000},
        "notes":[
            "Only records with traceable source URLs are exported.",
            "News/jobs are filtered by source publication timestamps within the 24 hours before this run.",
            "If a feed/API has no timestamp, the record is excluded rather than assumed fresh.",
            "GitHub stars are populated only when an explicit GitHub repository URL is present in arXiv metadata.",
            "Startup source repository schema may change; check the run log and source URLs."
        ]
    }
    (OUT/"collection_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print("\nDONE:", path.resolve())
    print(json.dumps(summary,indent=2))
    if len(startups)<1000 or len(products)<1000 or len(papers)<1000:
        print("\nWARNING: At least one 1,000-record target was not reached. Do not submit as complete.")
    if not news: print("NOTE: No news items met the strict 24-hour date filter in this run.")
    if not jobs: print("NOTE: No jobs met the strict 24-hour date filter in this run.")
    print("\nOpen output/AI_Data_Intelligence_Collected.xlsx and review the source URLs.")

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("Stopped by user.")
