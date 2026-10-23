const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  `${window.location.protocol}//${window.location.hostname}:5000/api`;

const SERVER_BASE_URL =
  import.meta.env.VITE_SERVER_BASE_URL ||
  `${window.location.protocol}//${window.location.hostname}:5000`;

export { API_BASE_URL, SERVER_BASE_URL };