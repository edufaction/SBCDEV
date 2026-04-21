from __future__ import annotations

from typing import Any


class WindowNavigationController:
    """Owns global sidebar navigation and workspace page routing."""

    def __init__(
        self,
        *,
        workspace_stack,
        workspace_header,
        sidebar,
        set_section_key,
        default_page,
        pages_by_key: dict[str, Any],
        header_overrides: dict[str, str] | None = None,
    ) -> None:
        self._workspace_stack = workspace_stack
        self._workspace_header = workspace_header
        self._sidebar = sidebar
        self._set_section_key = set_section_key
        self._default_page = default_page
        self._pages_by_key = dict(pages_by_key)
        self._header_overrides = dict(header_overrides or {})

    def navigate(self, key: str) -> None:
        normalized_key = str(key or "").strip() or "dashboard"
        self._set_section_key(normalized_key)
        self._workspace_header.setText(self._header_text_for(normalized_key))
        self._workspace_stack.setCurrentWidget(self._pages_by_key.get(normalized_key, self._default_page))

    def navigate_to_section(self, key: str) -> None:
        button = self._sidebar.nav_button(key)
        if button is not None:
            button.click()
            return
        self._sidebar.set_active(key)
        self.navigate(key)

    def _header_text_for(self, key: str) -> str:
        override = self._header_overrides.get(key)
        if override is not None:
            return override
        return key.replace("_", " ").upper()
