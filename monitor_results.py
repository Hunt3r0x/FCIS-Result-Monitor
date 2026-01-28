import os
import time
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


BASE_URL = "https://myu.mans.edu.eg"


@dataclass
class Config:
    username: str
    password: str
    lang: str
    student_id: str
    app_id: str
    poll_interval_seconds: int
    telegram_bot_token: str
    telegram_chat_id: str
    discord_webhook_url: str


class MyuClient:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) "
                    "Gecko/20100101 Firefox/147.0"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ar,en;q=0.9",
            }
        )

    def get_csrf_token(self) -> str:
        """
        Fetch the login page and extract the CSRF token from the hidden input.
        """
        resp = self.session.get(BASE_URL + "/")
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        token_input = soup.find("input", attrs={"name": "csrfmiddlewaretoken"})
        if not token_input or not token_input.get("value"):
            raise RuntimeError("Could not find csrfmiddlewaretoken on login page.")
        return token_input["value"]

    def login(self) -> None:
        """
        Perform login using username/password/lang from config.
        """
        csrf_token = self.get_csrf_token()

        data = {
            "csrfmiddlewaretoken": csrf_token,
            "txtUserName": self.config.username,
            "txtPassword": self.config.password,
            "hdnLang": self.config.lang,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": BASE_URL + "/",
            "Origin": BASE_URL,
        }

        # Do not follow redirects so we can see the 302 response
        resp = self.session.post(
            BASE_URL + "/login",
            data=data,
            headers=headers,
            allow_redirects=False,
        )

        # Successful login usually returns 302 and sets sessionid cookie
        if resp.status_code not in (302, 301):
            raise RuntimeError(f"Login failed, unexpected status code: {resp.status_code}")

        if "sessionid" not in self.session.cookies:
            # Sometimes the cookie might be set on the response instead of session
            if "sessionid" not in resp.cookies:
                raise RuntimeError("Login failed, no sessionid cookie set.")
            self.session.cookies.update(resp.cookies)

    def fetch_grades_html(self) -> str:
        """
        Fetch the grades page HTML using the current session.
        """
        params = {
            self.config.student_id: "",
            "app_id": self.config.app_id,
            "click_item_id": "",
        }

        # Grades endpoint as seen from captured request
        url = f"{BASE_URL}/education/grades"

        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Lang": self.config.lang,
            "App_id": self.config.app_id,
            "Referer": BASE_URL + "/",
            "Accept": "text/html, */*; q=0.01",
        }

        resp = self.session.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.text


def detect_status(html: str) -> str:
    """
    Extract a concise status string from the grades HTML.
    """
    soup = BeautifulSoup(html, "lxml")

    # Check for explicit session expiry message
    full_text = soup.get_text(separator=" ", strip=True)
    if "انتهت فترة الدخول، يجب تسجيل الدخول مرة أخرى" in full_text:
        return "SESSION_EXPIRED"

    # Look for alert messages
    alert = soup.find("div", class_="alert")
    if alert:
        alert_text = " ".join(alert.get_text(strip=True).split())
        return alert_text

    # Fallback: if there is a card/body with grades, use a hash-like summary
    card_body = soup.find("div", class_="card-body")
    if card_body:
        content = " ".join(card_body.get_text(separator=" ", strip=True).split())
        # Return first 120 chars as a compact summary
        return content[:120]

    return "UNKNOWN_STATUS"


def send_telegram_message(config: Config, text: str) -> None:
    """
    Send a message via Telegram bot.
    """
    if not config.telegram_bot_token or not config.telegram_chat_id:
        print("Telegram config not set, skipping notification.")
        return

    url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": config.telegram_chat_id,
        "text": text,
    }

    try:
        resp = requests.post(url, data=payload, timeout=10)
        if not resp.ok:
            print(f"Failed to send Telegram message: {resp.status_code} {resp.text}")
    except Exception as exc:
        print(f"Error sending Telegram message: {exc}")


def send_discord_message(config: Config, text: str) -> None:
    """
    Send a message to a Discord channel via webhook.
    """
    if not config.discord_webhook_url:
        print("Discord webhook not set, skipping Discord notification.")
        return

    payload = {"content": text}

    try:
        resp = requests.post(config.discord_webhook_url, json=payload, timeout=10)
        if not resp.ok:
            print(f"Failed to send Discord message: {resp.status_code} {resp.text}")
    except Exception as exc:
        print(f"Error sending Discord message: {exc}")


def load_config() -> Config:
    load_dotenv()

    username = os.getenv("MYU_USERNAME", "")
    password = os.getenv("MYU_PASSWORD", "")
    lang = os.getenv("MYU_LANG", "ar")
    student_id = os.getenv("MYU_STUDENT_ID", "").strip()
    app_id = os.getenv("MYU_APP_ID", "4").strip()
    poll_interval_str = os.getenv("POLL_INTERVAL_SECONDS", "120")

    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "")

    if not username or not password:
        raise RuntimeError("MYU_USERNAME and MYU_PASSWORD must be set in the environment.")
    if not student_id:
        raise RuntimeError("MYU_STUDENT_ID must be set in the environment.")

    try:
        poll_interval_seconds = int(poll_interval_str)
    except ValueError:
        poll_interval_seconds = 120

    return Config(
        username=username,
        password=password,
        lang=lang,
        student_id=student_id,
        app_id=app_id,
        poll_interval_seconds=poll_interval_seconds,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        discord_webhook_url=discord_webhook_url,
    )


def monitor_loop(client: MyuClient) -> None:
    """
    Main monitoring loop: periodically checks grades and sends notifications
    when the status changes.
    """
    last_status: Optional[str] = None

    while True:
        try:
            html = client.fetch_grades_html()
            status = detect_status(html)

            if status == "SESSION_EXPIRED":
                print("Session expired, logging in again...")
                client.login()
                # Retry once after re-login
                html = client.fetch_grades_html()
                status = detect_status(html)

            if last_status is None:
                print(f"Initial status: {status}")
                last_status = status
            elif status != last_status:
                print(f"Status changed from '{last_status}' to '{status}'")
                message = f"FCIS result status changed:\nOld: {last_status}\nNew: {status}"
                send_telegram_message(client.config, message)
                send_discord_message(client.config, message)
                last_status = status
            else:
                print(f"No change, status is still: {status}")

        except Exception as exc:
            print(f"Error during monitoring loop: {exc}")

        time.sleep(client.config.poll_interval_seconds)


def main() -> None:
    config = load_config()
    client = MyuClient(config)
    print("Logging in to myu.mans.edu.eg...")
    client.login()
    print("Login successful. Starting monitoring loop...")
    monitor_loop(client)


if __name__ == "__main__":
    main()

