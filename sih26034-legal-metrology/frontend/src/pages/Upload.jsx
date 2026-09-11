import React, { useState } from "react";
import { scanProduct } from "../api";
import ComplianceReport from "../components/ComplianceReport";

export default function Upload() {
  const [file, setFile] = useState(null);
  const [productName, setProductName] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await scanProduct(file, productName);
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Scan failed. Try a clearer image.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 700, margin: "0 auto", padding: 24 }}>
      <h1>Scan a Product Label</h1>
      <p style={{ color: "#6b7280" }}>
        Upload a clear photo of a packaged commodity's label to check compliance
        against the Legal Metrology (Packaged Commodities) Rules, 2011.
      </p>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 12 }}>
          <label>Product name (optional)</label>
          <br />
          <input
            type="text"
            value={productName}
            onChange={(e) => setProductName(e.target.value)}
            style={{ width: "100%", padding: 8, marginTop: 4 }}
          />
        </div>

        <div style={{ marginBottom: 12 }}>
          <input
            type="file"
            accept="image/*"
            onChange={(e) => setFile(e.target.files[0])}
            required
          />
        </div>

        <button type="submit" disabled={loading || !file} style={{ padding: "10px 20px", cursor: "pointer" }}>
          {loading ? "Scanning..." : "Scan for Compliance"}
        </button>
      </form>

      {error && <p style={{ color: "#dc2626", marginTop: 12 }}>{error}</p>}

      <ComplianceReport result={result} />
    </div>
  );
}
