// Centralized API Base URL configuration for BookNav Client

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api";
const SERVER_BASE_URL = import.meta.env.VITE_SERVER_BASE_URL || "http://localhost:5000";

export { API_BASE_URL, SERVER_BASE_URL };
