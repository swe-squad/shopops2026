// Baked in at build time (see Dockerfile ARG / deploy.yml build-args). Leave empty to call /api/ on the
// same origin through the nginx proxy; a full URL makes the browser call the API directly and needs CORS.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''
