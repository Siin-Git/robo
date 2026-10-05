# Yahoo daily session fixtures

Public chart responses captured on 2026-10-05, with source URL and requested
calendar-date boundaries. They contain public prices and timezone metadata only.
`test_yahoo_session_dates.py` parses the checked-in response and mocks HTTP for
the boundary test; CI does not call Yahoo.

- FX September 18: London midnight BST is September 17 23:00 UTC.
- London spring/autumn DST: 2025-03-30 and 2025-10-26 transitions.
- US spring/autumn DST: 2025-03-09 and 2025-11-02 transitions.
- Korean/US ETFs: session dates and adjusted-close choice remain unchanged.

The IANA zone applies its historical rules; the response's current `gmtoffset`
is deliberately not used to assign historical bars. Daily session labels are
not timestamps at which a real broker executed an order.
