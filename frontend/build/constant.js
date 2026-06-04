export const OUTPUT_DIR = 'dist'

export const BACKEND_URL = 'http://localhost:8000'

export const PROXY_CONFIG = {
  '/api': {
    target: BACKEND_URL,
    changeOrigin: true,
  },
}

export const EXTRA_DEV_PROXY = {}
