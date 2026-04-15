"""Debug: navigate to Google Travel and dump the consent page structure."""
import asyncio, json, os

os.environ["DISPLAY"] = ":1"

async def main():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=False,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"]
    )
    ctx = await browser.new_context(
        viewport={"width": 1280, "height": 720},
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        locale="en-US",
    )
    await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
    page = await ctx.new_page()

    print("=== Navigating to Google Travel ===")
    resp = await page.goto("https://www.google.com/travel/flights", wait_until="domcontentloaded", timeout=30000)
    print(f"URL: {page.url}")
    print(f"Title: {await page.title()}")
    print(f"Status: {resp.status if resp else 'N/A'}")

    await asyncio.sleep(3)

    print(f"\n=== After wait - URL: {page.url} ===")
    print(f"Title: {await page.title()}")

    # Check for iframes
    frames = page.frames
    print(f"\n=== Frames ({len(frames)}) ===")
    for i, f in enumerate(frames):
        print(f"  [{i}] {f.url[:150]}")

    # Dump all buttons and clickable elements
    print("\n=== Buttons and clickable elements ===")
    elements = await page.evaluate("""() => {
        const results = [];
        const allEls = document.querySelectorAll('button, a, [role="button"], input[type="submit"], [onclick]');
        for (const el of allEls) {
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) continue;
            const style = window.getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden') continue;
            const text = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().substring(0, 120);
            results.push({
                tag: el.tagName.toLowerCase(),
                text: text,
                id: el.id || '',
                cls: (typeof el.className === 'string' ? el.className : '').substring(0, 80),
                type: el.getAttribute('type') || '',
                role: el.getAttribute('role') || '',
                jsname: el.getAttribute('jsname') || '',
                w: Math.round(rect.width),
                h: Math.round(rect.height),
                x: Math.round(rect.x),
                y: Math.round(rect.y),
            });
        }
        return results;
    }""")
    for el in elements:
        print(f"  <{el['tag']}> id={el['id']!r} jsname={el['jsname']!r} text={el['text']!r} [{el['w']}x{el['h']} @ {el['x']},{el['y']}]")

    # Check inside iframes for consent
    print("\n=== Checking iframes for consent buttons ===")
    for i, frame in enumerate(frames):
        if frame == page.main_frame:
            continue
        try:
            btns = await frame.evaluate("""() => {
                const results = [];
                for (const el of document.querySelectorAll('button, a, [role="button"], input[type="submit"]')) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) continue;
                    const text = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().substring(0, 120);
                    if (text) results.push({tag: el.tagName.toLowerCase(), text: text, id: el.id || '', jsname: el.getAttribute('jsname') || ''});
                }
                return results;
            }""")
            if btns:
                print(f"  Frame [{i}] {frame.url[:80]}:")
                for b in btns:
                    print(f"    <{b['tag']}> id={b['id']!r} jsname={b['jsname']!r} text={b['text']!r}")
        except Exception as e:
            print(f"  Frame [{i}] error: {e}")

    # Also check for form actions with consent
    print("\n=== Forms ===")
    forms = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('form')).map(f => ({
            action: f.action || '',
            method: f.method || '',
            id: f.id || '',
        }));
    }""")
    for f in forms:
        print(f"  <form> action={f['action']!r} method={f['method']!r} id={f['id']!r}")

    # Take screenshot
    await page.screenshot(path="/tmp/consent_debug.png")
    print("\nScreenshot saved to /tmp/consent_debug.png")

    await browser.close()
    await pw.stop()

asyncio.run(main())
