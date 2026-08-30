import React from "react";
import { reportPdfUrl } from "../api";

const statusColor = {
  PASS: "#16a34a",
  FAIL: "#dc2626",
  MISSING: "#dc2626",
  INVALID: "#d97706",
  FONT_TOO_SMALL: "#d97706",
  INFO: "#6b7280",
};

export default function ComplianceReport({ result }) {
  if (!result) return null;

  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 20, marginTop: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0 }}>{result.product_name || "Scanned Product"}</h3>
        <span
          style={{
            padding: "4px 12px",
            borderRadius: 999,
            background: statusColor[result.overall_status],
            color: "white",
            fontWeight: 600,
            fontSize: 13,
          }}
        >
          {result.overall_status}
        </span>
      </div>

      <p style={{ color: "#6b7280", fontSize: 13 }}>Scan ID: {result.id}</p>

      {result.violations.length === 0 ? (
        <p style={{ color: "#16a34a" }}>✓ No violations detected.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 12 }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "2px solid #e5e7eb" }}>
              <th style={{ padding: 6 }}>Rule</th>
              <th style={{ padding: 6 }}>Declaration</th>
              <th style={{ padding: 6 }}>Status</th>
              <th style={{ padding: 6 }}>Detail</th>
              <th style={{ padding: 6 }}>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {result.violations.map((v, i) => (
              <tr key={i} style={{ borderBottom: "1px solid #f3f4f6" }}>
                <td style={{ padding: 6, fontFamily: "monospace", fontSize: 12 }}>{v.rule_code}</td>
                <td style={{ padding: 6 }}>{v.declaration}</td>
                <td style={{ padding: 6, color: statusColor[v.status] }}>{v.status}</td>
                <td style={{ padding: 6, fontSize: 13 }}>{v.detail}</td>
                <td style={{ padding: 6 }}>{Math.round(v.confidence * 100)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <a href={reportPdfUrl(result.id)} target="_blank" rel="noreferrer">
        <button style={{ marginTop: 16, padding: "8px 16px", cursor: "pointer" }}>
          Download PDF Report
        </button>
      </a>
    </div>
  );
}
