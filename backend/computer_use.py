"""
Ombra Computer Use / Desktop Control
=====================================
Screen interaction capabilities via Playwright:
screenshot, click, type, scroll, navigate, and interact with web pages.
Extends existing screenshot tool to full desktop/browser control.
"""

import os
import json
import asyncio
import base64
from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class BrowserSession:
    """Active browser session state."""
    browser: object = None
    context: object = None
    page: object = None
    url: str = ""
    screenshot_dir: str = "/tmp/ombra_screenshots"


class ComputerUseEngine:
    """
    Browser-based computer use via Playwright.
    Provides screenshot, click, type, scroll, and navigate capabilities.
    Runs visible on VNC display :1 so users can watch actions live.
    """

    def __init__(self, screenshot_dir: str = "/tmp/ombra_screenshots"):
        self.screenshot_dir = screenshot_dir
        self._session: BrowserSession | None = None
        self._playwright = None
        self._display = os.environ.get("COMPUTER_USE_DISPLAY", ":1")
        os.makedirs(screenshot_dir, exist_ok=True)

    async def _ensure_session(self) -> BrowserSession:
        """Ensure a browser session is active, create one if needed."""
        if self._session and self._session.page:
            try:
                await self._session.page.title()
                return self._session
            except Exception:
                await self.close()

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError("playwright not installed. pip install playwright && playwright install chromium")

        # Set DISPLAY so the browser opens on the VNC desktop
        os.environ["DISPLAY"] = self._display

        self._playwright = await async_playwright().start()
        browser = await self._playwright.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            java_script_enabled=True,
            locale="en-US",
            timezone_id="Europe/Paris",
        )
        # Hide webdriver flag to reduce bot detection
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        page = await context.new_page()

        self._session = BrowserSession(
            browser=browser,
            context=context,
            page=page,
            screenshot_dir=self.screenshot_dir,
        )
        return self._session

    async def close(self):
        """Close the browser session."""
        if self._session:
            try:
                if self._session.browser:
                    await self._session.browser.close()
            except Exception:
                pass
            self._session = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> dict:
        """Navigate to a URL and return page info + interactive elements."""
        session = await self._ensure_session()
        try:
            resp = await session.page.goto(url, wait_until=wait_until, timeout=30000)
            session.url = url
            # Wait a bit for dynamic content
            await asyncio.sleep(1)

            # Auto-handle consent redirects (e.g., consent.google.com)
            consent_handled = False
            if "consent.google.com" in session.page.url or "consent" in (await session.page.title()).lower():
                consent_result = await self.handle_consent()
                if consent_result.get("success"):
                    consent_handled = True
                    await asyncio.sleep(1)

            # Auto-collect interactive elements so the agent can see the page
            interactive = await self._get_interactive_elements(session.page)
            return {
                "success": True,
                "url": session.page.url,
                "title": await session.page.title(),
                "status": resp.status if resp else None,
                "consent_auto_handled": consent_handled,
                "interactive_elements": interactive,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def screenshot(self, full_page: bool = False, selector: str = None) -> dict:
        """Take a screenshot, return base64-encoded PNG."""
        session = await self._ensure_session()
        try:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            path = os.path.join(self.screenshot_dir, f"screenshot_{ts}.png")

            if selector:
                elem = await session.page.query_selector(selector)
                if elem:
                    await elem.screenshot(path=path)
                else:
                    return {"success": False, "error": f"Selector not found: {selector}"}
            else:
                await session.page.screenshot(path=path, full_page=full_page)

            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")

            return {
                "success": True,
                "path": path,
                "base64": b64[:200] + "..." if len(b64) > 200 else b64,
                "full_base64_length": len(b64),
                "url": session.page.url,
                "title": await session.page.title(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def click(self, selector: str = None, x: int = None, y: int = None,
                    button: str = "left", click_count: int = 1) -> dict:
        """Click on an element by selector or coordinates."""
        session = await self._ensure_session()
        try:
            if selector:
                await session.page.click(selector, button=button, click_count=click_count, timeout=10000)
                return {"success": True, "action": "click", "selector": selector}
            elif x is not None and y is not None:
                await session.page.mouse.click(x, y, button=button, click_count=click_count)
                return {"success": True, "action": "click", "x": x, "y": y}
            else:
                return {"success": False, "error": "Provide selector or x,y coordinates"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def type_text(self, text: str, selector: str = None, delay: int = 50) -> dict:
        """Type text into an element or at current focus."""
        session = await self._ensure_session()
        try:
            if selector:
                await session.page.fill(selector, text)
                return {"success": True, "action": "type", "selector": selector, "length": len(text)}
            else:
                await session.page.keyboard.type(text, delay=delay)
                return {"success": True, "action": "type", "length": len(text)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def press_key(self, key: str) -> dict:
        """Press a keyboard key (Enter, Tab, Escape, etc.)."""
        session = await self._ensure_session()
        try:
            await session.page.keyboard.press(key)
            return {"success": True, "action": "key_press", "key": key}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def scroll(self, direction: str = "down", amount: int = 500,
                     selector: str = None) -> dict:
        """Scroll the page or an element."""
        session = await self._ensure_session()
        try:
            delta_y = amount if direction == "down" else -amount
            if selector:
                elem = await session.page.query_selector(selector)
                if elem:
                    await elem.evaluate(f"el => el.scrollBy(0, {delta_y})")
                else:
                    return {"success": False, "error": f"Selector not found: {selector}"}
            else:
                await session.page.mouse.wheel(0, delta_y)
            return {"success": True, "action": "scroll", "direction": direction, "amount": amount}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_page_content(self, selector: str = None) -> dict:
        """Get text content of the page or an element."""
        session = await self._ensure_session()
        try:
            if selector:
                elem = await session.page.query_selector(selector)
                if elem:
                    text = await elem.inner_text()
                else:
                    return {"success": False, "error": f"Selector not found: {selector}"}
            else:
                text = await session.page.inner_text("body")

            # Truncate to avoid overwhelming
            if len(text) > 10000:
                text = text[:10000] + "\n... [truncated]"

            return {
                "success": True,
                "text": text,
                "url": session.page.url,
                "title": await session.page.title(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def evaluate_js(self, script: str) -> dict:
        """Execute JavaScript on the page and return the result."""
        session = await self._ensure_session()
        try:
            result = await session.page.evaluate(script)
            return {"success": True, "result": str(result)[:5000]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def wait_for(self, selector: str = None, timeout: int = 5000,
                       state: str = "visible") -> dict:
        """Wait for an element to appear/become visible."""
        session = await self._ensure_session()
        try:
            if selector:
                await session.page.wait_for_selector(selector, timeout=timeout, state=state)
                return {"success": True, "action": "wait", "selector": selector}
            else:
                await session.page.wait_for_load_state("networkidle", timeout=timeout)
                return {"success": True, "action": "wait", "state": "networkidle"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_elements(self, selector: str) -> dict:
        """List elements matching a selector with their properties."""
        session = await self._ensure_session()
        try:
            elements = await session.page.query_selector_all(selector)
            results = []
            for i, elem in enumerate(elements[:50]):  # Limit to 50
                tag = await elem.evaluate("el => el.tagName.toLowerCase()")
                text = (await elem.inner_text())[:200] if await elem.is_visible() else ""
                href = await elem.get_attribute("href") or ""
                results.append({
                    "index": i,
                    "tag": tag,
                    "text": text.strip(),
                    "href": href,
                    "visible": await elem.is_visible(),
                })
            return {"success": True, "count": len(elements), "elements": results}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_session_info(self) -> dict:
        """Get current browser session state."""
        if not self._session or not self._session.page:
            return {"active": False}
        try:
            return {
                "active": True,
                "url": self._session.page.url,
                "title": await self._session.page.title(),
            }
        except Exception:
            return {"active": False}

    # ── Smart helpers ─────────────────────────────────────────────────────

    async def _get_interactive_elements(self, page, limit: int = 40) -> list:
        """Extract visible interactive elements (buttons, links, inputs) with text."""
        try:
            elements = await page.evaluate("""() => {
                const results = [];
                const selectors = [
                    'button', 'a[href]', 'input', 'select', 'textarea',
                    '[role="button"]', '[role="link"]', '[onclick]',
                    '[type="submit"]', '[role="tab"]', '[role="menuitem"]'
                ];
                const seen = new Set();
                for (const sel of selectors) {
                    for (const el of document.querySelectorAll(sel)) {
                        if (seen.has(el)) continue;
                        seen.add(el);
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) continue;
                        if (rect.top < -100 || rect.top > window.innerHeight + 100) continue;
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
                        const tag = el.tagName.toLowerCase();
                        const text = (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.getAttribute('title') || '').trim().substring(0, 100);
                        if (!text && tag !== 'input') continue;
                        const type = el.getAttribute('type') || '';
                        const id = el.id || '';
                        const cls = el.className ? (typeof el.className === 'string' ? el.className : '') : '';
                        // Build a reliable CSS selector
                        let cssSelector = tag;
                        if (id) cssSelector = '#' + CSS.escape(id);
                        else if (el.getAttribute('data-testid')) cssSelector = `[data-testid="${el.getAttribute('data-testid')}"]`;
                        else if (el.getAttribute('aria-label')) cssSelector = `[aria-label="${el.getAttribute('aria-label')}"]`;
                        else if (el.getAttribute('name')) cssSelector = `${tag}[name="${el.getAttribute('name')}"]`;
                        results.push({
                            tag, text, type, href: el.getAttribute('href') || '',
                            selector: cssSelector,
                            x: Math.round(rect.x + rect.width/2),
                            y: Math.round(rect.y + rect.height/2),
                        });
                        if (results.length >= LIMIT) break;
                    }
                    if (results.length >= LIMIT) break;
                }
                return results;
            }""".replace('LIMIT', str(limit)))
            return elements
        except Exception:
            return []

    async def find_and_click(self, text: str, tag: str = None, timeout: int = 5000) -> dict:
        """
        Find a visible clickable element whose text matches (case-insensitive)
        and click it. Works for cookie consent buttons, nav links, etc.
        """
        session = await self._ensure_session()
        try:
            search_text = text.lower().strip()
            # Try multiple strategies
            # Strategy 1: XPath text match
            xpath_selectors = [
                f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{search_text}')]",
                f"//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{search_text}')]",
                f"//*[@role='button'][contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{search_text}')]",
                f"//input[@value and contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{search_text}')]",
                f"//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{search_text}')]",
            ]
            if tag:
                xpath_selectors.insert(0, f"//{tag}[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{search_text}')]")

            for xpath in xpath_selectors:
                try:
                    elements = await session.page.query_selector_all(f"xpath={xpath}")
                    for elem in elements:
                        if await elem.is_visible():
                            elem_text = (await elem.inner_text()).strip()[:200]
                            await elem.scroll_into_view_if_needed()
                            await elem.click(timeout=timeout)
                            # Wait for potential navigation/dialog
                            await asyncio.sleep(1)
                            return {
                                "success": True,
                                "action": "find_and_click",
                                "matched_text": elem_text,
                                "url_after": session.page.url,
                                "title_after": await session.page.title(),
                            }
                except Exception:
                    continue

            # Strategy 2: JS-based fuzzy search
            clicked = await session.page.evaluate("""(searchText) => {
                const all = document.querySelectorAll('button, a, [role="button"], input[type="submit"], [onclick]');
                for (const el of all) {
                    const t = (el.innerText || el.value || el.getAttribute('aria-label') || '').toLowerCase();
                    if (t.includes(searchText)) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            el.scrollIntoView({block: 'center'});
                            el.click();
                            return {found: true, text: t.substring(0, 200)};
                        }
                    }
                }
                return {found: false};
            }""", search_text)

            if clicked.get("found"):
                await asyncio.sleep(1)
                return {
                    "success": True,
                    "action": "find_and_click",
                    "matched_text": clicked.get("text", ""),
                    "url_after": session.page.url,
                    "title_after": await session.page.title(),
                }

            return {
                "success": False,
                "error": f"No visible clickable element found containing: '{text}'",
                "hint": "Try get_elements to see what's on the page, or use a CSS selector with click",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def find_and_type(self, label: str, value: str) -> dict:
        """
        Find an input field by its label/placeholder/aria-label text and type into it.
        """
        session = await self._ensure_session()
        try:
            search_label = label.lower().strip()

            # Strategy 1: Find by associated label
            typed = await session.page.evaluate("""({searchLabel, value}) => {
                // Check inputs by placeholder
                for (const inp of document.querySelectorAll('input, textarea, select')) {
                    const ph = (inp.getAttribute('placeholder') || '').toLowerCase();
                    const al = (inp.getAttribute('aria-label') || '').toLowerCase();
                    const nm = (inp.getAttribute('name') || '').toLowerCase();
                    if (ph.includes(searchLabel) || al.includes(searchLabel) || nm.includes(searchLabel)) {
                        inp.scrollIntoView({block: 'center'});
                        inp.focus();
                        inp.value = '';
                        return {found: true, selector: inp.id ? '#' + inp.id : `input[placeholder="${inp.getAttribute('placeholder')}"]`};
                    }
                }
                // Check by label element
                for (const lbl of document.querySelectorAll('label')) {
                    if (lbl.textContent.toLowerCase().includes(searchLabel)) {
                        const forAttr = lbl.getAttribute('for');
                        const inp = forAttr ? document.getElementById(forAttr) : lbl.querySelector('input, textarea, select');
                        if (inp) {
                            inp.scrollIntoView({block: 'center'});
                            inp.focus();
                            inp.value = '';
                            return {found: true, selector: inp.id ? '#' + inp.id : 'input'};
                        }
                    }
                }
                return {found: false};
            }""", {"searchLabel": search_label, "value": value})

            if typed.get("found"):
                selector = typed.get("selector", "input")
                await session.page.fill(selector, value)
                return {
                    "success": True,
                    "action": "find_and_type",
                    "field": label,
                    "typed": value,
                    "selector": selector,
                }

            return {
                "success": False,
                "error": f"No input field found matching: '{label}'",
                "hint": "Try get_elements with selector 'input, textarea' to see available fields",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def handle_consent(self) -> dict:
        """
        Automatically detect and dismiss cookie/consent banners.
        Handles Google consent.google.com redirects, common CMPs, and generic banners.
        """
        session = await self._ensure_session()
        page = session.page
        try:
            current_url = page.url

            # ── Strategy 0: Google consent.google.com redirect (most common blocker) ──
            if "consent.google.com" in current_url:
                # Google consent page uses form submission, not just button clicks
                # We need to find and click "Accept all" then wait for redirect
                accepted = await page.evaluate("""() => {
                    // Google consent "Accept all" buttons by jsname or text
                    const selectors = [
                        'button[jsname="b3VHJd"]',  // "Accept all" jsname
                        'button[jsname="tWT92d"]',  // "Reject all" as fallback
                    ];
                    // Try specific jsname first
                    for (const sel of selectors) {
                        const btn = document.querySelector(sel);
                        if (btn) {
                            btn.scrollIntoView({block: 'center'});
                            btn.click();
                            return {found: true, text: btn.innerText.trim(), method: 'jsname'};
                        }
                    }
                    // Fallback: find by text content
                    const acceptTexts = ['accept all', 'reject all', 'i agree', 'accept'];
                    for (const el of document.querySelectorAll('button')) {
                        const t = el.innerText.toLowerCase().trim();
                        for (const at of acceptTexts) {
                            if (t.includes(at)) {
                                el.scrollIntoView({block: 'center'});
                                el.click();
                                return {found: true, text: el.innerText.trim(), method: 'text'};
                            }
                        }
                    }
                    // Last resort: submit the second form (Accept form)
                    const forms = document.querySelectorAll('form[action*="consent.google.com/save"]');
                    if (forms.length >= 2) {
                        forms[1].submit();
                        return {found: true, text: 'form-submit', method: 'form'};
                    }
                    if (forms.length >= 1) {
                        forms[0].submit();
                        return {found: true, text: 'form-submit-first', method: 'form'};
                    }
                    return {found: false};
                }""")

                if accepted.get("found"):
                    # Wait for navigation after consent
                    try:
                        await page.wait_for_url("**/*", timeout=10000)
                    except Exception:
                        pass
                    await asyncio.sleep(2)
                    return {
                        "success": True,
                        "action": "handle_consent",
                        "method": f"google_consent_{accepted.get('method', '')}",
                        "clicked_text": accepted.get("text", ""),
                        "url_after": page.url,
                        "title_after": await page.title(),
                    }

            # ── Strategy 1: Common CMP selectors (OneTrust, Cookiebot, Didomi, etc.) ──
            cmp_selectors = [
                "#onetrust-accept-btn-handler",
                "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
                "#didomi-notice-agree-button",
                "#accept-cookie", "#cookie-accept", "#cookieAccept",
                ".cookie-accept", ".accept-cookies",
                "[data-action='accept']", "[data-action='accept-all']",
                ".fc-cta-consent", ".fc-button-background",
                "#sp-cc-accept",
                "button[jsname='higCR']",
                "button[jsname='b3VHJd']",
            ]
            for sel in cmp_selectors:
                try:
                    elem = await page.query_selector(sel)
                    if elem:
                        bbox = await elem.bounding_box()
                        if bbox and bbox["width"] > 10:
                            await elem.scroll_into_view_if_needed()
                            await elem.click(timeout=5000)
                            await asyncio.sleep(1.5)
                            return {
                                "success": True,
                                "action": "handle_consent",
                                "clicked_selector": sel,
                                "url_after": page.url,
                                "title_after": await page.title(),
                            }
                except Exception:
                    continue

            # ── Strategy 2: Text-based search for consent buttons ──
            consent_texts = [
                "accept all", "accept cookies", "i agree", "agree",
                "accept", "allow all", "allow cookies", "consent",
                "ok", "got it", "i understand", "continue",
                "accepter tout", "tout accepter", "j'accepte",
                "akzeptieren", "alle akzeptieren",
                "reject all", "decline",
            ]
            for text in consent_texts:
                try:
                    clicked = await page.evaluate("""(searchText) => {
                        for (const el of document.querySelectorAll('button, a, [role="button"], input[type="submit"], span[role="button"]')) {
                            const t = (el.innerText || el.value || el.getAttribute('aria-label') || '').toLowerCase().trim();
                            if (t === searchText || t.includes(searchText)) {
                                const rect = el.getBoundingClientRect();
                                if (rect.width > 10 && rect.height > 10) {
                                    el.scrollIntoView({block: 'center'});
                                    el.click();
                                    return {found: true, text: t.substring(0, 100)};
                                }
                            }
                        }
                        return {found: false};
                    }""", text)
                    if clicked.get("found"):
                        await asyncio.sleep(1.5)
                        return {
                            "success": True,
                            "action": "handle_consent",
                            "clicked_text": clicked.get("text", ""),
                            "url_after": page.url,
                            "title_after": await page.title(),
                        }
                except Exception:
                    continue

            # ── Strategy 3: Check iframes for consent ──
            try:
                for frame in page.frames:
                    if frame == page.main_frame:
                        continue
                    frame_url = frame.url.lower()
                    if any(kw in frame_url for kw in ["consent", "cookie", "gdpr", "privacy", "cmp"]):
                        for text in consent_texts[:8]:
                            try:
                                clicked = await frame.evaluate("""(searchText) => {
                                    for (const el of document.querySelectorAll('button, a, [role="button"]')) {
                                        const t = (el.innerText || '').toLowerCase().trim();
                                        if (t.includes(searchText)) {
                                            el.scrollIntoView({block: 'center'});
                                            el.click();
                                            return {found: true, text: t.substring(0, 100)};
                                        }
                                    }
                                    return {found: false};
                                }""", text)
                                if clicked.get("found"):
                                    await asyncio.sleep(1.5)
                                    return {
                                        "success": True,
                                        "action": "handle_consent",
                                        "clicked_in_frame": frame_url[:100],
                                        "url_after": page.url,
                                        "title_after": await page.title(),
                                    }
                            except Exception:
                                continue
            except Exception:
                pass

            return {
                "success": False,
                "error": "No consent banner found or could not click it",
                "hint": "Try find_and_click with the exact button text you see",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


# ── Global instance ───────────────────────────────────────────────────────────
computer_use = ComputerUseEngine()
