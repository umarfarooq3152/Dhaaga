"""Shared SlowAPI limiter without importing the FastAPI application factory."""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
