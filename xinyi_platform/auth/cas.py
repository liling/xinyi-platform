import xml.etree.ElementTree as ET
from urllib.parse import urlencode

import httpx


class CASClient:
    def __init__(self, server_url: str, service_url: str):
        self.server_url = server_url.rstrip("/")
        self.service_url = service_url

    def get_login_url(self) -> str:
        params = urlencode({"service": self.service_url})
        return f"{self.server_url}/login?{params}"

    def get_service_validate_url(self, ticket: str) -> str:
        params = urlencode({"service": self.service_url, "ticket": ticket})
        return f"{self.server_url}/serviceValidate?{params}"

    async def verify_ticket(self, ticket: str) -> str | None:
        url = self.get_service_validate_url(ticket)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            return None
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError:
            return None
        ns = "{http://www.yale.edu/tp/cas}"
        success = root.find(f"{ns}authenticationSuccess")
        if success is None:
            return None
        user_elem = success.find(f"{ns}user")
        if user_elem is None or user_elem.text is None:
            return None
        return user_elem.text
