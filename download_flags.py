import asyncio, httpx, os

CODES = [
    "mx", "za", "kr", "cz", "ca", "ba", "qa", "ch",
    "br", "ma", "ht", "gb-sct", "us", "py", "au", "tr",
    "de", "cw", "ci", "ec", "nl", "jp", "se", "tn",
    "be", "eg", "ir", "nz", "es", "cv", "sa", "uy",
    "fr", "sn", "iq", "no", "ar", "dz", "at", "jo",
    "pt", "cd", "uz", "co", "gb-eng", "hr", "gh", "pa",
]

async def main():
    os.makedirs("assets/flags", exist_ok=True)
    ok, fail = 0, 0
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
        for code in CODES:
            path = f"assets/flags/{code}.png"
            if os.path.exists(path):
                ok += 1
                continue
            url = f"https://flagcdn.com/w40/{code}.png"
            try:
                r = await c.get(url)
                if r.status_code == 200 and len(r.content) > 100:
                    with open(path, "wb") as f:
                        f.write(r.content)
                    ok += 1
                    print(f"OK {code}")
                else:
                    print(f"FAIL {code}: status={r.status_code}")
                    fail += 1
            except Exception as e:
                print(f"ERR {code}: {e}")
                fail += 1
    print(f"\nTotal: {ok} ok, {fail} fail")

asyncio.run(main())
