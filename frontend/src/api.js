import axios from "axios";

const api = axios.create({
  baseURL: "/api",
});

export async function scanProduct(file, productName) {
  const formData = new FormData();
  formData.append("file", file);
  const params = productName ? { product_name: productName } : {};
  const res = await api.post("/scan/", formData, {
    params,
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function listScans(statusFilter) {
  const params = statusFilter ? { status_filter: statusFilter } : {};
  const res = await api.get("/scan/", { params });
  return res.data;
}

export async function getScan(id) {
  const res = await api.get(`/scan/${id}`);
  return res.data;
}

export async function getStats() {
  const res = await api.get("/reports/summary/stats");
  return res.data;
}

export function reportPdfUrl(id) {
  return `/api/reports/${id}/pdf`;
}

export default api;
