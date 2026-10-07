# LICENSES.md

> ثبت پروژه‌های متن‌باز، کتابخانه‌ها و منابع استفاده‌شده یا در حال بررسی.
> قبل از استفاده از هر پروژه متن‌باز، موارد **License + Maintenance + Security** بررسی می‌شود.

## خودِ پروژه
| مورد | مقدار |
|---|---|
| Name | GlobalIntelligence |
| License | **هنوز تعیین نشده** (به ADR-0006 در DECISIONS.md مراجعه کنید) |

---

## قالب ثبت هر وابستگی

```
Name:
URL:
License:
Version:
Usage:
Modification:
Attribution:
Restrictions:
Maintenance (آخرین فعالیت):
Security (CVE / وضعیت):
Status: Proposed | Approved | In-Use | Rejected
```

---

## Framework / Runtime (Planned)
| Name | License | Usage | Status |
|---|---|---|---|
| FastAPI | MIT | Backend API | Proposed |
| Uvicorn | BSD-3-Clause | ASGI server | Proposed |
| Pydantic | MIT | Validation / Schemas | Proposed |
| SQLAlchemy | MIT | ORM | Proposed |
| Alembic | MIT | Migrations | Proposed |
| React | MIT | Frontend | Proposed |
| Vite | MIT | Build tool | Proposed |
| PostgreSQL | PostgreSQL License | Database | Proposed |
| n8n | Sustainable Use License (fair-code) | Orchestration | **Needs review** |

> ⚠️ **n8n** تحت «Sustainable Use License» است، نه یک مجوز OSI. باید محدودیت‌های آن پیش از استفاده در محصول تجاری بررسی شود (ADR در آینده).

## Data / Statistics / ML (Planned, only if justified)
| Name | License | Usage | Status |
|---|---|---|---|
| pandas | BSD-3-Clause | Data manipulation | Proposed |
| numpy | BSD-3-Clause | Numerics | Proposed |
| scipy | BSD-3-Clause | Stats | Proposed |
| statsmodels | BSD-3-Clause | Time series / econometrics | Proposed |
| scikit-learn | BSD-3-Clause | ML | Proposed |
| pmdarima / statsforecast | MIT / Apache-2.0 | ARIMA/ETS baselines | Proposed |
| pymc | Apache-2.0 | Bayesian (later) | Proposed |

## Integrations (Planned / To Evaluate)
| Name | License | Usage | Status |
|---|---|---|---|
| OpenBB | AGPL-3.0 (check) | Financial/Economic research layer | **To evaluate** |
| TradingAgents | To verify | Multi-agent financial analysis (optional) | **To evaluate** |
| Investigator-like tools | To verify | Claim/evidence extraction | **To evaluate** |

> هیچ‌کدام از Integrationها نباید وابستگی غیرقابل‌تعویض برای هسته ایجاد کنند. همه از طریق Adapter متصل می‌شوند.

---

## سیاست
- فقط وابستگی‌هایی که در License، Maintenance و Security تأیید شده‌اند به `In-Use` ارتقا می‌یابند.
- Dependency جدید فقط با دلیل (Rule 9) اضافه می‌شود.
- Attribution پروژه‌ها در این فایل و در محل استفاده حفظ می‌شود.
