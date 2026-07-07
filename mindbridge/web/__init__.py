"""MindBridge web layer (Milestone 2).

A thin FastAPI backend wrapping the matching engine. The engine stays importable and
web-agnostic; everything here is a wrapper — HTTP, auth, and persistence — around it.
"""
