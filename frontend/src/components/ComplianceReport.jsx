import React, { useState } from "react";
import { reportPdfUrl } from "../api";

const statusColor = {
  PASS: "#16a34a",
  FAIL: "#dc2626",
  MISSING: "#dc2626",
  INVALID: "#d97706",
  REVIEW: "#d97706",
  FONT_TOO_SMALL: "#d97706",
  INFO: "#6b7280",
};

export default function ComplianceReport({ result }) {
  const [zoom, setZoom] = useState(100);
  const [viewMode, setViewMode] = useState("annotated"); // 'annotated' | 'clean'

  if (!result) return null;

  const fields = result.fields || [];
  const violations = result.violations || fields.filter(f => f.verdict?.toLowerCase() === "fail");
  const overallStatus = result.has_violation ? "VIOLATION DETECTED" : "COMPLIANT";
  const overallColor = result.has_violation ? "#dc2626" : "#16a34a";
  const annotatedImg = result.annotated_image;
  const cleanImg = result.original_image;

  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, padding: 24, marginTop: 24, background: "#ffffff", boxShadow: "0 4px 20px rgba(0,0,0,0.06)" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #f3f4f6", paddingBottom: 16 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 22, color: "#111827" }}>{result.product_name || "Packaged Commodity"}</h2>
          <p style={{ color: "#6b7280", fontSize: 13, margin: "4px 0 0 0" }}>
            Scan ID: {result.id} &nbsp;|&nbsp; Score: <strong>{result.score}%</strong>
          </p>
        </div>
        <span
          style={{
            padding: "6px 16px",
            borderRadius: 999,
            background: overallColor,
            color: "white",
            fontWeight: 700,
            fontSize: 13,
            letterSpacing: "0.03em",
          }}
        >
          {overallStatus}
        </span>
      </div>

      {/* Visual Inspection Studio */}
      {annotatedImg && (
        <div style={{ margin: "20px 0", padding: 16, background: "#0f172a", borderRadius: 10, color: "#f8fafc" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 16 }}>🔍</span>
              <strong style={{ fontSize: 14 }}>Visual Statutory Inspection Studio</strong>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              {cleanImg && (
                <div style={{ display: "inline-flex", background: "#1e293b", borderRadius: 20, padding: 2 }}>
                  <button
                    type="button"
                    onClick={() => setViewMode("annotated")}
                    style={{
                      background: viewMode === "annotated" ? "#3b82f6" : "transparent",
                      color: "#ffffff",
                      border: "none",
                      borderRadius: 16,
                      padding: "4px 10px",
                      fontSize: 12,
                      cursor: "pointer",
                    }}
                  >
                    Overlay
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode("clean")}
                    style={{
                      background: viewMode === "clean" ? "#3b82f6" : "transparent",
                      color: "#ffffff",
                      border: "none",
                      borderRadius: 16,
                      padding: "4px 10px",
                      fontSize: 12,
                      cursor: "pointer",
                    }}
                  >
                    Original
                  </button>
                </div>
              )}
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
                <button
                  type="button"
                  onClick={() => setZoom((z) => Math.max(80, z - 20))}
                  style={{ background: "#334155", color: "white", border: "none", borderRadius: 4, width: 24, height: 24, cursor: "pointer" }}
                >
                  -
                </button>
                <span style={{ width: 40, textAlign: "center", fontFamily: "monospace" }}>{zoom}%</span>
                <button
                  type="button"
                  onClick={() => setZoom((z) => Math.min(250, z + 20))}
                  style={{ background: "#334155", color: "white", border: "none", borderRadius: 4, width: 24, height: 24, cursor: "pointer" }}
                >
                  +
                </button>
                <button
                  type="button"
                  onClick={() => setZoom(100)}
                  style={{ background: "#334155", color: "white", border: "none", borderRadius: 4, padding: "2px 8px", fontSize: 11, cursor: "pointer" }}
                >
                  Reset
                </button>
              </div>
            </div>
          </div>

          <div style={{ overflow: "auto", maxHeight: 520, textAlign: "center", background: "#020617", borderRadius: 8, padding: 12 }}>
            <img
              src={viewMode === "clean" && cleanImg ? `data:image/jpeg;base64,${cleanImg}` : `data:image/png;base64,${annotatedImg}`}
              alt="Packaging visual inspection"
              style={{
                width: `${zoom}%`,
                maxWidth: zoom === 100 ? "100%" : "none",
                maxHeight: zoom === 100 ? 500 : "none",
                borderRadius: 6,
                transition: "width 0.15s ease",
              }}
            />
          </div>

          <div style={{ display: "flex", gap: 16, marginTop: 10, fontSize: 12, color: "#94a3b8", flexWrap: "wrap" }}>
            <span><strong style={{ color: "#22c55e" }}>■ Green Box:</strong> Verified Declaration</span>
            <span><strong style={{ color: "#ef4444" }}>■ Red Box:</strong> Violation / Missing Tax Statement</span>
            <span><strong style={{ color: "#f59e0b" }}>■ Amber Box:</strong> Non-Standard / Review Notice</span>
          </div>
        </div>
      )}

      {/* Checklist Table */}
      <h4 style={{ margin: "20px 0 10px 0", fontSize: 15, color: "#374151" }}>Statutory Compliance Checklist (LMPC 2011)</h4>
      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 8 }}>
        <thead>
          <tr style={{ textAlign: "left", borderBottom: "2px solid #e5e7eb", background: "#f9fafb" }}>
            <th style={{ padding: 10, fontSize: 12, textTransform: "uppercase", color: "#6b7280" }}>Rule ID</th>
            <th style={{ padding: 10, fontSize: 12, textTransform: "uppercase", color: "#6b7280" }}>Declaration</th>
            <th style={{ padding: 10, fontSize: 12, textTransform: "uppercase", color: "#6b7280" }}>Verdict</th>
            <th style={{ padding: 10, fontSize: 12, textTransform: "uppercase", color: "#6b7280" }}>Extracted Evidence</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((f, i) => {
            const v = (f.verdict || "info").toUpperCase();
            const c = statusColor[v] || "#6b7280";
            return (
              <tr key={i} style={{ borderBottom: "1px solid #f3f4f6" }}>
                <td style={{ padding: 10, fontFamily: "monospace", fontSize: 12, color: "#6366f1" }}>{f.rule_id || f.rule_code}</td>
                <td style={{ padding: 10, fontWeight: 600, fontSize: 13 }}>{f.field || f.declaration}</td>
                <td style={{ padding: 10 }}>
                  <span style={{ color: c, fontWeight: 700, fontSize: 12, background: `${c}18`, padding: "3px 10px", borderRadius: 12 }}>
                    {v}
                  </span>
                </td>
                <td style={{ padding: 10, fontSize: 12, color: "#4b5563", fontFamily: "monospace" }}>{f.evidence || f.detail}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* PDF Download Button */}
      <a href={reportPdfUrl(result.id)} target="_blank" rel="noreferrer" style={{ textDecoration: "none" }}>
        <button
          style={{
            marginTop: 20,
            padding: "10px 20px",
            background: "#4f46e5",
            color: "white",
            border: "none",
            borderRadius: 6,
            fontWeight: 600,
            fontSize: 13,
            cursor: "pointer",
            boxShadow: "0 2px 8px rgba(79,70,229,0.3)",
          }}
        >
          📥 Download Official Audit PDF Report
        </button>
      </a>
    </div>
  );
}

