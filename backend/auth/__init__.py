"""
backend/auth
============
Authentication and authorization package for PrivSight.
"""

from backend.auth.routes import auth_router, auth_service

__all__ = ["auth_router", "auth_service"]
