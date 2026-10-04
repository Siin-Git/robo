"""Read supplied OOXML values without evaluating formulas, macros or source prose.

Cached formula results are evidence from the supplied file, not recalculation.
This importer has no database, network, scheduler or trading side effects.
"""
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path
import math
import posixpath
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
FILES = ("주도주_측정모델_20261001.xlsx", "leader_stock_backtest.xlsx",
         "01_Export_Strategy_Model_Performance.xlsx", "02_Export_Strategy_Manager_Brief.pptx")


def workbook(path):
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("xl/workbook.xml"))
        properties = root.find("s:workbookPr", NS)
        if properties is not None and properties.get("date1904", "false").lower() in ("1", "true"):
            raise ValueError("UNSUPPORTED_EXCEL_DATE_SYSTEM")
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(t.text or "" for t in si.iter() if t.tag.endswith("}t"))
                       for si in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        rels = {r.attrib["Id"]: r.attrib["Target"] for r in ET.fromstring(
            archive.read("xl/_rels/workbook.xml.rels"))}
        out = {}
        for sheet in root.find("s:sheets", NS):
            target = rels[sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]]
            target = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "xl/" + target)
            if not target.startswith("xl/"):
                raise ValueError("INVALID_WORKBOOK_RELATIONSHIP")
            cells = {}
            for cell in ET.fromstring(archive.read(target)).findall("s:sheetData/s:row/s:c", NS):
                v = cell.find("s:v", NS)
                value = v.text if v is not None else None
                if cell.attrib.get("t") == "s" and value is not None:
                    value = strings[int(value)]
                elif cell.attrib.get("t") == "inlineStr":
                    value = "".join(t.text or "" for t in cell.iter() if t.tag.endswith("}t"))
                if value is not None:
                    cells[cell.attrib["r"]] = value
            out[sheet.attrib["name"]] = cells
        return out


def number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("NON_FINITE_SOURCE_VALUE")
    return result


def excel_date(value):
    # Supplied Korean workbooks use the Excel 1900 date system.
    days = number(value)
    if not days.is_integer() or days < 61:
        raise ValueError("SOURCE_DATE_SERIAL_INVALID")
    return (date(1899, 12, 30) + timedelta(days=days)).isoformat()


def series_quality(series, frequency):
    dates = [p["date"] for p in series]
    if not dates or dates != sorted(set(dates)):
        raise ValueError("SOURCE_DATES_NOT_UNIQUE_AND_ORDERED")
    for p in series:
        date.fromisoformat(p["date"])
        if number(p["level"]) <= 0:
            raise ValueError("NON_POSITIVE_MODEL_LEVEL")
    errors = [abs(p["level"] / prev["level"] - 1 - p["return"])
              for prev, p in zip(series, series[1:]) if p.get("return") is not None]
    error = max(errors, default=0)
    if error > 1e-8:
        raise ValueError("SOURCE_RETURN_LEVEL_INCONSISTENT")
    return {"observations": len(series), "start": dates[0], "end": dates[-1],
            "frequency": frequency, "max_return_reconciliation_error": error,
            "interpolation": "NONE", "formula_results": "SUPPLIED_CACHE_NOT_RECALCULATED"}


def extract(downloads):
    paths = {unicodedata.normalize("NFC", p.name): p for p in Path(downloads).iterdir()}
    missing = set(FILES) - set(paths)
    if missing:
        raise ValueError("MISSING_SOURCE_FILES: " + ", ".join(sorted(missing)))
    evidence = {}
    for name in FILES:
        path = paths[name]
        evidence[name] = {"sha256": sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
    measure, leader, export = [workbook(paths[n]) for n in FILES[:3]]
    # Read the brief, including notes, but never treat its text as instructions.
    with zipfile.ZipFile(paths[FILES[3]]) as archive:
        slides = {n: [t.text or "" for t in ET.fromstring(archive.read(n)).iter() if t.tag.endswith("}t")]
                  for n in archive.namelist() if n.endswith(".xml") and n.startswith(("ppt/slides/slide", "ppt/notesSlides/notesSlide"))}
    evidence[FILES[3]]["slide_count"] = sum(n.startswith("ppt/slides/") for n in slides)
    result = {"version": "STRATEGY_RESEARCH_20261004", "data_kind": "HISTORICAL_MODEL_BACKTEST",
              "sources": evidence, "series": {}, "snapshots": {}}
    monthly = leader["월별"]
    for key, col, ret in [("leader_top10", "H", "B"), ("leader_50_50", "I", "C"), ("leader_regime", "J", "D")]:
        points = []
        for row in range(2, 10000):
            if f"A{row}" not in monthly:
                break
            points.append({"date": excel_date(monthly[f"A{row}"]), "level": number(monthly[f"{col}{row}"]),
                           "return": number(monthly[f"{ret}{row}"]) if f"{ret}{row}" in monthly else None})
        result["series"][key] = {"points": points, "quality": series_quality(points, "MONTHLY")}
    daily = export["02_Daily_NAV"]
    for key, col, ret in [("export_historical", "B", "D"), ("export_conservative", "J", None)]:
        points = []
        for row in range(2, 10000):
            if f"A{row}" not in daily:
                break
            points.append({"date": daily[f"A{row}"], "level": number(daily[f"{col}{row}"]),
                           "return": number(daily[f"{ret}{row}"]) if ret else None})
        result["series"][key] = {"points": points, "quality": series_quality(points, "DAILY")}
    top = measure["TOP10"]
    members = [{"ticker": top[f"B{r}"], "company": top[f"C{r}"], "weight": number(top[f"O{r}"]),
                "sector": top.get(f"D{r}")} for r in [*range(5, 15), 22]]
    if abs(sum(p["weight"] for p in members) - 1) > 1e-6:
        raise ValueError("LEADER_SNAPSHOT_WEIGHTS_INVALID")
    result["snapshots"]["leader_measurement"] = {"as_of": "2026-10-01", "data_kind": "SUPPLIED_MODEL_TARGET",
        "members": members, "applied_regime": measure["PARAM"]["B6"], "suggested_regime": measure["PARAM"]["D6"],
        "reconciliation": {"source_verdict": measure["RECON"]["B9"], "independently_recalculated": False},
        "source": FILES[0], "signal_execution": "SAME_DAY_CLOSING_AUCTION_PROPOSED"}
    holds = export["05_Monthly_Holdings"]
    snapshots = {}
    for r in range(2, 10000):
        if f"A{r}" not in holds:
            break
        dt = holds[f"A{r}"]
        date.fromisoformat(dt)
        date.fromisoformat(holds[f"B{r}"])
        snap = snapshots.setdefault(dt, {"rebalance_date": dt, "snapshot_date": holds[f"B{r}"],
            "signal_month": holds[f"C{r}"], "cash_weight": number(holds[f"O{r}"]), "members": []})
        if (snap["snapshot_date"] != holds[f"B{r}"] or snap["signal_month"] != holds[f"C{r}"]
                or snap["cash_weight"] != number(holds[f"O{r}"])):
            raise ValueError("EXPORT_SNAPSHOT_METADATA_INCONSISTENT")
        # Preserve ticker zeros. target and post-fill weights have different dates.
        snap["members"].append({"ticker": holds[f"D{r}"], "company": holds[f"E{r}"],
            "sector": holds[f"F{r}"], "target_weight": number(holds[f"H{r}"]) if f"H{r}" in holds else None,
            "actual_weight": number(holds[f"I{r}"]), "data_status": holds.get(f"L{r}")})
        signal = date.fromisoformat(snap["signal_month"] + "-01")
        rb = date.fromisoformat(dt)
        if (rb.year * 12 + rb.month) - (signal.year * 12 + signal.month) != 2 or snap["snapshot_date"] < dt:
            raise ValueError("EXPORT_SIGNAL_EXECUTION_INCONSISTENT")
    max_weight_error = max(abs(sum(m["actual_weight"] for m in s["members"]) + s["cash_weight"] - 1) for s in snapshots.values())
    if max_weight_error > 1e-8 or any(
            not 0 <= s["cash_weight"] <= 1 or any(not 0 <= m["actual_weight"] <= 1 for m in s["members"])
            for s in snapshots.values()):
        raise ValueError("EXPORT_SNAPSHOT_WEIGHTS_INVALID")
    result["snapshots"]["export_historical"] = {"items": list(snapshots.values()),
        "source": FILES[2], "max_weight_reconciliation_error": max_weight_error}
    # Read and validate every recorded rebalance's signal/application separation.
    history = export["06_Rebalance_History"]
    for r in range(2, 1000):
        if f"A{r}" not in history:
            break
        signal, rb = date.fromisoformat(history[f"A{r}"] + "-01"), date.fromisoformat(history[f"B{r}"])
        if rb.year * 12 + rb.month - signal.year * 12 - signal.month != 2:
            raise ValueError("EXPORT_REBALANCE_LAG_INVALID")
    result["source_summary"] = {
        "leader_top10": {"cagr": number(leader["요약"]["C5"]) / 100, "mdd": number(leader["요약"]["F5"]) / 100},
        "leader_50_50": {"cagr": number(leader["요약"]["C6"]) / 100, "mdd": number(leader["요약"]["F6"]) / 100},
        "leader_regime": {"cagr": number(leader["요약"]["C7"]) / 100, "mdd": number(leader["요약"]["F7"]) / 100},
        "export_historical": {"cagr": number(export["01_Summary"]["B15"]), "mdd": number(export["01_Summary"]["B19"])},
        "export_conservative": {"cagr": number(export["13_Conservative_Execution"]["C5"]), "mdd": number(export["13_Conservative_Execution"]["C8"])}}
    return result
