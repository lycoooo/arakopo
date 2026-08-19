import asyncio
import os
import re
import sys
import uuid

import httpx
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

if sys.platform == "win32":
    os.system("")

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"


def _safe(text):
    """Keep special characters (e.g. the peso sign) from crashing old consoles."""
    return str(text).encode("ascii", "replace").decode("ascii")


def ok(msg, *rest):
    print(f"{GREEN}  \u2713 {msg}{RESET}", *rest)


def warn(msg, *rest):
    print(f"{YELLOW}  \u26a0 {msg}{RESET}", *rest)


def err(msg, *rest):
    print(f"{RED}  \u2717 {msg}{RESET}", *rest)


def info(msg, *rest):
    print(f"{CYAN}  \u2022 {msg}{RESET}", *rest)


def section(num, total, title):
    print(f"\n{BOLD}  \u2500\u2500 [{num}/{total}] {title}{RESET}")


BANNER = (
    f"\n{MAGENTA}"
    f"   \u250c{'─' * 30}\u2510\n"
    f"   \u2502  {BOLD}30 Days Trial Detect{RESET}{MAGENTA}      \u2502\n"
    f"   \u2502  {BOLD}Modern Edition{RESET}{MAGENTA}            \u2502\n"
    f"   \u2502  {DIM}by Lyco{RESET}{MAGENTA}                   \u2502\n"
    f"   \u2514{'─' * 30}\u2518{RESET}"
)

# ---------------------------------------------------------------------------
# Endpoints & constants
# ---------------------------------------------------------------------------
GRAPHQL_URL = "https://web.prod.cloud.netflix.com/graphql"
LANDING_URL = "https://www.netflix.com/ph-en/"

RECAPTCHA_SITE_KEY = "6LdqW_EqAAAAAO87Fb_kcZfNzs0IqJRcKiJDYpUv"
INIT_QUERY_ID = "5d76d6a0-ccfe-4c31-b587-b4e1954732ca"
UPDATE_QUERY_ID = "0fd81de7-07af-4c7d-802f-0f4ea4181aa3"

DEFAULT_NFVDID = (
    "BQFmAAEBEHd71oHfkM7FU_oofLECV31AjKJNl9T0lBwR96xzXmWutUqrRdHCkAN1hcHjRlxLI8Eay"
    "T3bVFbyZDu8hLHeBXCz1dcwGebHrzm-7Ty5ckJTvQ%3D%3D"
)


def _describe_screen(text: str) -> str:
    """Ano ang screen na ibinalik ng Netflix (para sa debugging)."""
    if "email-register-send-link" in text:
        return "SEND_LINK_FORM (kailangan pa i-click ang 'Send Link' button bago magpadala ng email)"
    if "email-register-link-sent" in text:
        return "LINK_SENT ('Check your inbox' screen - ini-render lang, hindi tiyak kung na-send ang email)"
    if '"errors"' in text.lower():
        return "ERROR_RESPONSE"
    return "UNKNOWN"


def _extract_error(text: str) -> str:
    """Kunin ang unang GraphQL error message (kung mayroon)."""
    if '"errors"' not in text.lower():
        return ""
    m = re.search(r'"message"\s*:\s*"([^"]*)"', text)
    return m.group(1) if m else text[:300]


class TrialSender:
    """Banner check + CLCS GraphQL signup flow (same payloads as the original)."""

    def __init__(self, email: str, nfvdid: str = None):
        self.email = email
        self.locale = "en-IN"
        # Kapag walang ibinigay na custom nfvdid, gamitin ang default.
        # Hindi na ito hinaharangan: kahit hindi ma-detect, magpapatuloy ang signup.
        self.nfvdid = nfvdid or DEFAULT_NFVDID
        self.flwssn = str(uuid.uuid4())
        self.req_id = str(uuid.uuid4())
        self.top_uuid = str(uuid.uuid4())
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36",
            "Content-Type": "application/json",
            "Origin": "https://www.netflix.com",
            "Referer": "https://www.netflix.com/",
            "Accept-Language": "en-US,en;q=0.9",
            "x-netflix.request.id": self.req_id,
            "x-netflix.request.toplevel.uuid": self.top_uuid,
            "x-netflix.request.clcs.bucket": "high",
            "x-netflix.context.form-factor": "phone",
            "x-netflix.context.app-version": "v38c5b0da",
            "x-netflix.context.locales": "en-in",
        }

    # -- headers ------------------------------------------------------------
    def cookie_header(self) -> str:
        """Build the cookie header from known values (nfvdid + flwssn)."""
        return f"nfvdid={self.nfvdid}; flwssn={self.flwssn}"

    def _headers_with_cookie(self) -> dict:
        headers = self._headers.copy()
        headers["Cookie"] = self.cookie_header()
        return headers

    # -- payloads (unchanged) ------------------------------------------------
    def payload_init(self) -> dict:
        """CLCSWebInitSignup - exactly the original payload."""
        return {
            "operationName": "CLCSWebInitSignup",
            "variables": {
                "inputNode": "WELCOME",
                "locale": self.locale,
                "inputFields": [
                    {"name": "flwssn", "value": {"stringValue": self.flwssn}},
                    {"name": "email", "value": {"stringValue": self.email}},
                    {"name": "recaptchaError", "value": {"stringValue": "LOAD_TIMED_OUT"}},
                    {"name": "recaptchaResponseTime", "value": {}},
                    {"name": "recaptchaSiteKey", "value": {"stringValue": RECAPTCHA_SITE_KEY}},
                    {"name": "recaptchaToken", "value": {}},
                ],
            },
            "extensions": {"persistedQuery": {"id": INIT_QUERY_ID, "version": 102}},
        }

    def payload_update(self) -> dict:
        """CLCSScreenUpdate - exactly the original payload."""
        return {
            "operationName": "CLCSScreenUpdate",
            "variables": {
                "format": "HTML",
                "imageFormat": "PNG",
                "locale": self.locale,
                "serverState": "Bgjru+vcAxLTAf/qOOEwXPLVxW+7Jod9WpjYuKN8j1qfhQpzCK4mmQts5eMSeaP+l7s6NKcNBO4rmYabFFCVnMpCH3ib4AicvXAKm30Z+s5W3Cst0D0BK5x/pwn3QmByi/OgGwU/fzaiR5oxSlZe4fKVexWHISkE4GMzJqLaaXQR0M73ynZB9idNBfqsz3RA5WJN+DGAbVUOZlWl8eZqffvQpp/5MGubeQFpdwKqkAx1nHh7/xI1i9tDU0KLgrvkZrbe6nQ1MX2nc9TBxqnVVxtc3ptHdqydP1wlIu0YBiIOCgydgLg1SvK6tSPOff8=",
                "serverScreenUpdate": "Bgjru+vcAxKSAjDnHOxlaIbFSbwaWzZo/REHFnNG7OtpcXdKTDlcL4/o+huGi/fNW+jrqNDqDSsv1iytiG/ZtvO9ierUE9M1Kc/yEj9JsSiG3XpPciFDzPd6psSaG68XLbos+Qie0wniXCtJyWDLDuLd9ayCMB8qGCxwbov6B41kCQY/zArwlecm0GNoJdd5jvZfBJVtytD6mMCYnPA/9zhX4okj+6IGet9xOCYt76IDiuyESxgKbaOLcd6DQIDSBf4m/lYi2Tasj7olPkCaDIXxjU+0UY+b7eDyhvi2if2vt6510ARrGsSZq8DaazQmrpAbfiCW47s1/1mR59vUMYeT8VCqqAvbNwipqyP1DQMHtoTnCoWns0+x6IgYBiIOCgx9EW4i3i9SUswnHEg=",
                "inputFields": [
                    {"name": "email", "value": {"stringValue": self.email}},
                    {"name": "pipcConsent", "value": {"booleanValue": False}},
                ],
            },
            "extensions": {"persistedQuery": {"id": UPDATE_QUERY_ID, "version": 102}},
        }

    # -- banner check ---------------------------------------------------------
    async def check_banner(self):
        """Fetch the PH landing page and return the trial banner text (or None)."""
        headers = self._headers_with_cookie()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(LANDING_URL, headers=headers)

        if 'data-uia="free-trial-banner"' in resp.text or "Try 30 days" in resp.text:
            banner = ""
            marker = 'data-uia="free-trial-banner-text"'
            i = resp.text.find(marker)
            if i != -1:
                j = resp.text.find("</p>", i)
                if j != -1:
                    banner = resp.text[i:j].split(">", 1)[-1]
            return banner or "30-day trial"
        return None

    # -- GraphQL signup -------------------------------------------------------
    async def send_signup(self):
        """Run CLCSWebInitSignup + CLCSScreenUpdate. Returns (bool, message, debug)."""
        debug = {}
        headers = self._headers_with_cookie()

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp1 = await client.post(GRAPHQL_URL, json=self.payload_init(), headers=headers)
            except Exception as exc:
                msg = f"Init request error: {type(exc).__name__}: {exc}"
                err(msg)
                return False, msg, {"error": msg}

            debug["init_http"] = resp1.status_code
            debug["init_has_errors"] = '"errors"' in resp1.text.lower()
            debug["init_screen"] = _describe_screen(resp1.text)
            debug["init_error_msg"] = _extract_error(resp1.text)

            try:
                resp2 = await client.post(GRAPHQL_URL, json=self.payload_update(), headers=headers)
            except Exception as exc:
                msg = f"Update request error: {type(exc).__name__}: {exc}"
                err(msg)
                return False, msg, {**debug, "error": msg}

            debug["update_http"] = resp2.status_code
            debug["update_has_errors"] = '"errors"' in resp2.text.lower()
            debug["update_screen"] = _describe_screen(resp2.text)
            debug["update_error_msg"] = _extract_error(resp2.text)

            ok_init = '"errors"' not in resp1.text.lower()
            ok_update = resp2.status_code == 200 and '"errors"' not in resp2.text.lower()

            if ok_init and ok_update:
                msg = f"Trial activated for {self.email}"
                ok(msg)
                return True, msg, debug
            msg = f"Signup did not complete (init_ok={ok_init}, update_ok={ok_update})."
            err(msg)
            return False, msg, debug


# ---------------------------------------------------------------------------
# Starlette App (ito ang gagamitin ng Wasmer deployment)
# ---------------------------------------------------------------------------
async def home(request):
    return JSONResponse({"message": "APIsa is running. Send a POST request to /process-trial"})


async def process_trial(request):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"status": "failed", "message": "Invalid JSON payload."}, status_code=400)

    email = (data.get("email") or "").strip()
    if not email or "@" not in email:
        return JSONResponse({"status": "failed", "message": "Invalid email address."}, status_code=400)

    nfvdid = (data.get("nfvdid") or "").strip() or None

    sender = TrialSender(email=email, nfvdid=nfvdid)

    # Hindi na hinihingi ang bagong nfvdid at hindi na hinaharangan:
    # kahit hindi ma-detect ang DEFAULT_NFVDID/trial banner, diretsong mag-send ng signup.
    success, message, debug = await sender.send_signup()
    return JSONResponse({
        "status": "success" if success else "failed",
        "email": email,
        "message": message,
        "debug": debug,
    })


# CORS rules para payagan ang mga requests mula kahit saang website (gaya ng index.html)
middleware = [
    Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
]

app = Starlette(debug=True, routes=[
    Route("/", home, methods=["GET"]),
    Route("/process-trial", process_trial, methods=["POST"]),
], middleware=middleware)


# ---------------------------------------------------------------------------
# CLI mode (opsyonal - kapag manual na "python net.py")
# ---------------------------------------------------------------------------
async def _run_cli():
    print(BANNER)
    print()

    email = input("Enter your email address: ").strip()
    while not email or "@" not in email:
        email = input("Invalid email. Please enter a valid email address: ").strip()
    ok(f"Email locked in: {email}")

    sender = TrialSender(email)

    # Hindi na hinihingi ang bagong nfvdid: diretso na ang signup
    # kahit hindi ma-detect ang DEFAULT_NFVDID o ang trial banner.
    banner = await sender.check_banner()
    if banner and "30" in banner.lower():
        ok("30 Days Trial Detect")
    else:
        warn("30 Days Trial not detected - proceeding with default nfvdid anyway.")

    await sender.send_signup()


if __name__ == "__main__":
    asyncio.run(_run_cli())
