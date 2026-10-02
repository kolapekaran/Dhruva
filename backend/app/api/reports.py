from __future__ import annotations

import csv
import io
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from app.services.report_service import build_report

router = APIRouter(prefix="/reports", tags=["Reports"])


def _csv_bytes(report: dict) -> bytes:
    """Create a human-readable, spreadsheet-friendly Analytics CSV.

    The backend remains authoritative: values are taken directly from the
    report projection. Column names are operator-friendly rather than Python
    field names, and provenance/status are included so reference data cannot
    be mistaken for live telemetry.
    """
    fields = [
        ("Timestamp (UTC)", "timestamp"),
        ("Horizon (h)", "hour_offset"),
        ("Temperature (°C)", "temperature_celsius"),
        ("Wind Speed (m/s)", "wind_speed_mps"),
        ("Load (kW)", "load_kw"),
        ("Served Load (kW)", "served_load_kw"),
        ("Load Shed (kW)", "shed_load_kw"),
        ("Critical Load (kW)", "critical_load_kw"),
        ("Solar (kW)", "solar_power_kw"),
        ("Wind Generation (kW)", "wind_power_kw"),
        ("Diesel Generation (kW)", "diesel_power_kw"),
        ("Battery SOC (%)", "battery_soc_ratio"),
        ("Battery Charge (kW)", "battery_charge_kw"),
        ("Battery Discharge (kW)", "battery_discharge_kw"),
        ("Fuel Remaining (L)", "fuel_remaining_liters"),
        ("Indoor Temperature (°C)", "indoor_temperature_celsius"),
        ("Operating Mode", "operating_mode"),
        ("Energy Status", "energy_status"),
        ("Diesel Running", "diesel_running"),
        ("Confidence (%)", "confidence"),
        ("Data Status", "data_status"),
    ]
    out = io.StringIO(newline="")
    writer = csv.writer(out)
    writer.writerow([label for label, _ in fields])
    for point in report.get("series", []):
        row = []
        for label, key in fields:
            value = point.get(key, "")
            if key == "battery_soc_ratio" and value != "":
                value = round(float(value) * 100.0, 2)
            elif key == "confidence" and value != "":
                value = round(float(value) * 100.0, 1)
            elif isinstance(value, float):
                value = round(value, 3)
            row.append(value)
        writer.writerow(row)
    return out.getvalue().encode("utf-8-sig")


def _pdf_escape(value: object) -> str:
    return (str(value).replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
            .replace("\n", " "))


def _simple_pdf_bytes(report: dict) -> bytes:
    """Minimal dependency-free fallback PDF for environments without ReportLab."""
    current = report.get("current", {})
    summary = report.get("forecast_summary", {})
    resilience = report.get("resilience", {})
    risk = report.get("risk", {}) or {}
    lines = [
        "DHRUVA - Analytics Report",
        f"Station: {report.get('station', 'Maitri Research Station')}",
        f"Horizon: {report.get('horizon_hours', 24)} hours",
        f"Generated: {report.get('report_generated_at', '')}",
        f"Data status: {report.get('data_status', 'UNKNOWN')}",
        "",
        f"Current load: {float(current.get('load_kw', 0)):.1f} kW",
        f"Served load: {float(current.get('served_load_kw', 0)):.1f} kW",
        f"Renewable share: {float(summary.get('renewable_share_percent', 0)):.1f} %",
        f"Fuel consumed: {float(summary.get('fuel_consumed_liters', resilience.get('fuel_consumed_liters', 0))):.1f} L",
        f"Final fuel: {float(resilience.get('final_fuel_liters', current.get('fuel_remaining_liters', 0))):.1f} L",
        f"Minimum SOC: {float(resilience.get('minimum_soc_percent', current.get('battery_soc_percent', 0))):.1f} %",
        f"Load shed: {float(summary.get('load_shed_energy_kwh', 0)):.2f} kWh",
        f"Blackout risk: {float(resilience.get('blackout_risk_percent', risk.get('blackout_risk_percent', 0))):.1f} %",
        "",
        "This report contains backend Digital Twin projection/reference data.",
        "It does not convert engineering/reference data into field telemetry.",
    ]
    stream = ["BT", "/F1 10 Tf", "50 780 Td"]
    for i, line in enumerate(lines):
        if i:
            stream.append("0 -16 Td")
        stream.append(f"({_pdf_escape(line)}) Tj")
    stream.append("ET")
    content = "\n".join(stream).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode())
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects)+1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(pdf)


def _pdf_bytes(report: dict) -> bytes:
    # Prefer ReportLab when installed. If the operator launches the backend
    # with a system Python that does not have optional PDF dependencies, use a
    # small dependency-free PDF writer instead of returning HTTP 500.
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ModuleNotFoundError as exc:
        if exc.name != "reportlab":
            raise
        return _simple_pdf_bytes(report)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=14 * mm, leftMargin=14 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8, leading=10))
    story = [
        Paragraph("DHRUVA — Analytics Report", styles["Title"]),
        Paragraph(f"Station: {report.get('station', 'Maitri Research Station')}", styles["BodyText"]),
        Paragraph(f"Horizon: {report.get('horizon_hours', 24)} hours", styles["BodyText"]),
        Paragraph(f"Generated: {report.get('report_generated_at', '')}", styles["Small"]),
        Paragraph(f"Data status: {report.get('data_status', 'UNKNOWN')}", styles["Small"]),
        Paragraph(report.get("calibration_note", ""), styles["Small"]),
        Spacer(1, 8),
    ]

    current = report.get("current", {})
    summary = report.get("forecast_summary", {})
    resilience = report.get("resilience", {})
    risk = report.get("risk", {}) or {}

    rows = [
        ["Metric", "Value"],
        ["Current load", f"{current.get('load_kw', 0):.1f} kW"],
        ["Served load", f"{current.get('served_load_kw', 0):.1f} kW"],
        ["Renewable share", f"{summary.get('renewable_share_percent', 0):.1f} %"],
        ["Fuel consumed", f"{summary.get('fuel_consumed_liters', resilience.get('fuel_consumed_liters', 0)):.1f} L"],
        ["Final fuel", f"{resilience.get('final_fuel_liters', current.get('fuel_remaining_liters', 0)):.1f} L"],
        ["Minimum SOC", f"{resilience.get('minimum_soc_percent', current.get('battery_soc_percent', 0)):.1f} %"],
        ["Load shed", f"{summary.get('load_shed_energy_kwh', 0):.2f} kWh"],
        ["Blackout risk", f"{resilience.get('blackout_risk_percent', risk.get('blackout_risk_percent', 0)):.1f} %"],
    ]
    table = Table(rows, colWidths=[70 * mm, 90 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), (0.04, 0.15, 0.25)),
        ("TEXTCOLOR", (0, 0), (-1, 0), (1, 1, 1)),
        ("GRID", (0, 0), (-1, -1), 0.4, (0.25, 0.35, 0.45)),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [(0.96, 0.97, 0.98), (1, 1, 1)]),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([table, Spacer(1, 8), Paragraph("Projection / reference data", styles["Heading2"]),
                   Paragraph("This downloadable report contains the same backend report data used by the Analytics screen. It does not convert engineering/reference data into field telemetry.", styles["Small"])])
    doc.build(story)
    return buf.getvalue()


@router.get("")
def report(hours: int = Query(24, ge=1, le=8760)):
    return build_report(hours)


@router.get("/summary")
def report_summary(hours: int = Query(24, ge=1, le=8760)):
    r = build_report(hours)
    return {k: r[k] for k in ("report_generated_at", "station", "horizon_hours", "current", "forecast_summary", "resilience", "risk")}


@router.get("/export.csv")
def export_csv(hours: int = Query(24, ge=1, le=8760)):
    report_data = build_report(hours)
    filename = f"dhruva-{hours}h.csv"
    return StreamingResponse(
        io.BytesIO(_csv_bytes(report_data)),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export.pdf")
def export_pdf(hours: int = Query(24, ge=1, le=8760)):
    report_data = build_report(hours)
    filename = f"dhruva-{hours}h.pdf"
    return StreamingResponse(
        io.BytesIO(_pdf_bytes(report_data)),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
