import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_SESSION = None


def get_session() -> requests.Session:
    """Return a singleton requests.Session with sensible retry/backoff for idempotent requests."""
    global _SESSION
    if _SESSION is None:
        session = requests.Session()
        # Retry on transient errors for idempotent methods
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=(500, 502, 503, 504))
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        _SESSION = session
    return _SESSION
