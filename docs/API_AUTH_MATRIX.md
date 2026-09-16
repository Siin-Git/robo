# API Auth Matrix (Phase 3C)

`U` = any authenticated login, `O` = owner (or admin), `A` = admin only,
`P` = public. CSRF required on all state-changing calls except login/register.

| Endpoint | P | U | O | A |
|---|:-:|:-:|:-:|:-:|
| `GET /health`, `GET /ready`, `GET /api/v1/version` | ✓ | ✓ | ✓ | ✓ |
| `POST /api/v1/auth/register` | gated | – | – | – |
| `POST /api/v1/auth/login` | ✓ | ✓ | ✓ | ✓ |
| `POST /api/v1/auth/logout`, `/logout-all` | – | ✓ | ✓ | ✓ |
| `GET /api/v1/auth/me`, `/sessions`, `DELETE /sessions/{id}` | – | ✓ | ✓ | ✓ |
| `POST /api/v1/auth/change-password` | – | ✓ | ✓ | ✓ |
| `GET /api/v1/themes*` | – | ✓ | ✓ | ✓ |
| `GET /api/v1/benchmarks*` | – | ✓ | ✓ | ✓ |
| `GET /api/v1/me*` | – | ✓(own) | ✓ | ✓ |
| `GET /api/v1/participants/{id}/*` (views/portfolio/performance) | – | – | ✓ | ✓ |
| `GET/POST /api/v1/participants*` (CRUD) | – | – | – | ✓ |
| `GET /api/v1/rankings` | – | ✓ | ✓ | ✓ |
| `GET /api/v1/system/status` (minimal) | – | ✓ | ✓ | ✓ |
| `GET /api/v1/admin/*` (users/orders/trades/system) | – | – | – | ✓ |

Rankings never expose emails. `/system/status` for users omits DB paths and
operational internals (admin route has the full view).
