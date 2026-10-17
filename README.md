# SNMflix Media Extraction API

A production-ready, secure, and high-performance media extraction REST API for the **SNMflix** movie and anime streaming platform, built with **FastAPI** and **yt-dlp**.

This service allows the SNMflix frontend to inspect media URLs, extract structured playback streams, resolutions, codecs, and durations without downloading or storing media files on the server.

---

## Table of Contents

- [Features](#features)
- [Architecture & Design](#architecture--design)
- [Supported and Unsupported Use Cases](#supported-and-unsupported-use-cases)
- [Security Implementations](#security-implementations)
- [Project Structure](#project-structure)
- [Local Installation](#local-installation)
- [Environment Variables](#environment-variables)
- [Running Locally](#running-locally)
- [Running Automated Tests](#running-automated-tests)
- [API Endpoints](#api-endpoints)
  - [GET /health](#get-health)
  - [GET /](#get-)
  - [POST /extract](#post-extract)
  - [POST /extract/formats](#post-extractformats)
- [Frontend Integration (SNMflix)](#frontend-integration-snmflix)
- [Media Playback & Token Caveats](#media-playback--token-caveats)
- [Deploying to Render](#deploying-to-render)
- [Troubleshooting & Common Errors](#troubleshooting--common-errors)

---

## Features

- **No Media Downloads**: Performs non-download inspection (`extract_info(url, download=False)`) to preserve bandwidth and storage.
- **Audio/Video Stream Separation Detection**: Reliably distinguishes combined streams from video-only and audio-only streams (e.g. adaptive DASH/HLS tracks).
- **Hardened SSRF Protection**: Blocks access to localhost, private RFC1918 subnets, cloud metadata (AWS/GCP/Azure `169.254.169.254`), IPv6 local/loopback, and internal hostnames.
- **Pre-flight DNS & Scheme Validation**: Ensures only public HTTP/HTTPS URLs are processed.
- **API Key Protection**: Extraction endpoints require an `X-API-Key` header in production, while the `/health` endpoint remains open for uptime monitors.
- **Adaptive Concurrency & Rate Limiting**: Controlled via an async semaphore to prevent CPU/memory exhaustion, with an IP-based sliding window rate limiter.
- **Render-Ready**: Configured for Render Web Services with `render.yaml`, standard Python 3.12 runtime, and `$PORT` dynamic binding.

---

## Architecture & Design

```
                     +---------------------------------------+
                     |         SNMflix Frontend / Web        |
                     +---------------------------------------+
                                         |
                       POST /extract     | (Includes X-API-Key & URL)
                                         v
                     +---------------------------------------+
                     |         FastAPI Gateway Engine        |
                     +---------------------------------------+
                     | - CORS Middleware                     |
                     | - Request Body Size Limiter (64KB)    |
                     | - In-Memory Rate Limiter (60 req/min) |
                     | - X-API-Key Authentication Guard      |
                     +---------------------------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |         Security & SSRF Guard         |
                     | - Scheme Check (http/https only)      |
                     | - Hostname / Suffix Filter            |
                     | - DNS Resolution & IP Range Check     |
                     +---------------------------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |       Worker Threadpool & yt-dlp      |
                     | - Bounded Semaphore Concurrency       |
                     | - Execution Timeout Guard (20s)       |
                     | - Format Parsing & Stream Separation  |
                     | - Header Sanitization (Referer/UA)    |
                     +---------------------------------------+
```

---

## Supported and Unsupported Use Cases

### Supported
- Inspecting publicly accessible media URLs supported by yt-dlp extractors.
- Retrieving direct playback streams (e.g., MP4, HLS `.m3u8`, WebM).
- Extracting metadata (title, duration, thumbnail, resolution, frame rate, audio/video codecs).
- Filtering formats (video-only vs audio-only vs combined).
- Passing necessary HTTP playback headers (e.g. `Referer`, `User-Agent`) required by CDNs.

### Unsupported
- **No DRM Decryption or Paywall Bypasses**: yt-dlp cannot and will not bypass Widevine/FairPlay DRM or private paywalled content.
- **No File Downloads or Server Storage**: The API does not download, transcode, or save `.mp4` or `.mkv` files to disk.
- **No Generic Proxying**: The API does not stream or relay video bytes through the server.
- **No Arbitrary Local File or Network Access**: Local paths (`file://`), FTP (`ftp://`), internal endpoints, or loopback IPs are blocked.

---

## Security Implementations

1. **SSRF Mitigation (`app/services/ssrf_validator.py`)**:
   - Resolves hostnames to all associated IP addresses before invoking yt-dlp.
   - Evaluates each resolved IP against forbidden CIDR ranges (`127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, `100.64.0.0/10`, `0.0.0.0/8`, `::1/128`, `fc00::/7`, `fe80::/10`).
   - Rejects special domain names (`localhost`, `metadata.google.internal`, `instance-data`, `.local`, `.internal`).
   - Restricts schemes strictly to `http` and `https`.
2. **Safe yt-dlp Configuration**:
   - `simulate: True`, `skip_download: True`, `noplaylist: True`, `ignoreconfig: True`.
   - Never loads external configuration files, cookie jars, or custom downloader binaries.
3. **Information Disclosure Prevention**:
   - Internal stack traces, server paths, and exception dumps are trapped by custom FastAPI exception handlers and logged server-side only.
   - Responses always conform to uniform JSON envelopes.
   - Outgoing playback headers are sanitized (sensitive tokens like `Authorization` or `Cookie` are purged).
4. **Denial of Service Prevention**:
   - Concurrency bounded by `MAX_CONCURRENT_EXTRACTIONS`.
   - Timeouts bounded by `EXTRACTION_TIMEOUT_SECONDS`.
   - Payloads limited by `MAX_REQUEST_BODY_SIZE` (default 64 KB).
   - In-memory rate limiting by client IP address (`RATE_LIMIT_PER_MINUTE`).

---

## Project Structure

```
snmflix-media-api/
├── .env.example              # Example environment configuration
├── .gitignore                # Git ignore patterns
├── pytest.ini                # Pytest configuration
├── README.md                 # Complete service documentation
├── render.yaml               # Render Infrastructure-as-Code Blueprint
├── requirements.txt          # Python dependencies
├── app/
│   ├── __init__.py
│   ├── config.py             # Pydantic Settings configuration
│   ├── main.py               # FastAPI application entrypoint & middleware
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py           # API Key authentication dependency
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── health.py     # GET /health
│   │       └── extract.py    # POST /extract & POST /extract/formats
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── rate_limiter.py   # IP sliding-window rate limiter
│   │   └── request_size.py   # Request body size enforcement
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── common.py         # Standard error & root models
│   │   ├── extract.py        # Extraction request/response models
│   │   └── health.py         # Health check model
│   └── services/
│       ├── __init__.py
│       ├── extractor.py      # Threaded yt-dlp service
│       └── ssrf_validator.py # SSRF and URL validation
└── tests/
    ├── __init__.py
    ├── conftest.py           # Pytest fixtures and mock data
    ├── test_auth.py          # API key authentication tests
    ├── test_cors.py          # CORS header tests
    ├── test_extract.py       # Extraction & error handling tests
    ├── test_extract_formats.py # Format extraction tests
    ├── test_health.py        # Health endpoint tests
    ├── test_rate_limiter.py  # Rate limiting tests
    ├── test_request_size.py  # Payload size limit tests
    ├── test_root.py          # Root and documentation tests
    └── test_ssrf.py          # SSRF and network security tests
```

---

## Local Installation

### Prerequisites
- Python 3.11+ (Python 3.12 recommended)
- `pip` and `virtualenv`

### Steps

1. Clone or navigate to the repository directory:
   ```bash
   cd snmflix-media-api
   ```

2. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Upgrade pip and install dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. Create your local environment configuration:
   ```bash
   cp .env.example .env
   ```

---

## Environment Variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `PORT` | integer | `8000` | Port for the Uvicorn server (Render sets this automatically). |
| `HOST` | string | `0.0.0.0` | Network interface to bind to. |
| `ENVIRONMENT` | string | `production` | Runtime mode (`development` or `production`). |
| `LOG_LEVEL` | string | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `API_KEY` | string | `None` | Secret key required in the `X-API-Key` header for extraction. If unset in dev, authentication is bypassed. |
| `REQUIRE_API_KEY` | boolean | `False` | When `True`, forces the server to require `API_KEY` configuration. |
| `CORS_ORIGINS` | string | `https://snmflix.vercel.app,http://localhost:3000,http://localhost:5173` | Comma-separated list of allowed frontend origins. |
| `MAX_CONCURRENT_EXTRACTIONS` | integer | `5` | Maximum simultaneous yt-dlp extractions allowed. |
| `EXTRACTION_TIMEOUT_SECONDS` | integer | `20` | Maximum time allowed per extraction before returning a 504. |
| `RATE_LIMIT_PER_MINUTE` | integer | `60` | Maximum requests per minute per IP address. |
| `MAX_FORMATS_RETURNED` | integer | `100` | Maximum number of stream format records returned in the response. |
| `MAX_REQUEST_BODY_SIZE` | integer | `65536` | Maximum allowed request body size in bytes (64 KB). |

---

## Running Locally

Run Uvicorn in development mode with live reload:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Once running:
- **Interactive Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative ReDoc UI**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## Running Automated Tests

The test suite runs with `pytest` and mocks yt-dlp network calls, ensuring fast, deterministic execution without external network dependencies:

```bash
pytest -v
```

To run with test coverage reporting:
```bash
pytest --cov=app tests/
```

---

## API Endpoints

### GET /health

Returns basic health status and version. Ideal for Render's health check probe.

#### Request
```bash
curl -X GET http://localhost:8000/health
```

#### Response (200 OK)
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": 1729164800.123
}
```

---

### GET /

Returns API metadata and endpoint links.

#### Request
```bash
curl -X GET http://localhost:8000/
```

#### Response (200 OK)
```json
{
  "name": "SNMflix Media Extraction API",
  "version": "1.0.0",
  "description": "SNMflix Media Extraction API using yt-dlp and FastAPI.",
  "docs_url": "http://localhost:8000/docs",
  "endpoints": {
    "health": "http://localhost:8000/health",
    "extract": "http://localhost:8000/extract",
    "formats": "http://localhost:8000/extract/formats",
    "docs": "http://localhost:8000/docs",
    "openapi": "http://localhost:8000/openapi.json"
  }
}
```

---

### POST /extract

Inspects a media URL and resolves metadata along with the best direct stream URL.

#### Headers
| Header | Required | Value |
|---|---|---|
| `Content-Type` | Yes | `application/json` |
| `X-API-Key` | Yes (in prod) | Your configured secret `API_KEY` |

#### Request
```bash
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key-here" \
  -d '{
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "format": "best"
  }'
```

#### Response (200 OK)
```json
{
  "success": true,
  "title": "Rick Astley - Never Gonna Give You Up (Official Music Video)",
  "duration": 213.0,
  "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
  "extractor": "youtube",
  "original_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "media_url": "https://rr3---sn-4g5ednkk.googlevideo.com/videoplayback?...",
  "format_id": "22",
  "resolution": "1280x720",
  "vcodec": "avc1.64001F",
  "acodec": "mp4a.40.2",
  "has_video": true,
  "has_audio": true,
  "is_video_only": false,
  "is_audio_only": false,
  "is_live": false,
  "http_headers": {
    "User-Agent": "Mozilla/5.0 ...",
    "Referer": "https://www.youtube.com/"
  },
  "formats": [
    {
      "format_id": "140",
      "format_note": "audio only",
      "ext": "m4a",
      "resolution": "audio only",
      "width": null,
      "height": null,
      "fps": null,
      "vcodec": null,
      "acodec": "mp4a.40.2",
      "filesize": 3498201,
      "filesize_approx": null,
      "tbr": 128.0,
      "vbr": null,
      "abr": 128.0,
      "has_video": false,
      "has_audio": true,
      "is_video_only": false,
      "is_audio_only": true,
      "protocol": "https",
      "url": "https://rr3---sn-4g5ednkk.googlevideo.com/videoplayback?..."
    },
    {
      "format_id": "137",
      "format_note": "1080p",
      "ext": "mp4",
      "resolution": "1920x1080",
      "width": 1920,
      "height": 1080,
      "fps": 30.0,
      "vcodec": "avc1.640028",
      "acodec": null,
      "filesize": 42104500,
      "filesize_approx": null,
      "tbr": 3150.0,
      "vbr": 3150.0,
      "abr": null,
      "has_video": true,
      "has_audio": false,
      "is_video_only": true,
      "is_audio_only": false,
      "protocol": "https",
      "url": "https://rr3---sn-4g5ednkk.googlevideo.com/videoplayback?..."
    }
  ]
}
```

---

### POST /extract/formats

Lists all available format streams and codec tracks for a supported media URL.

#### Request
```bash
curl -X POST http://localhost:8000/extract/formats \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key-here" \
  -d '{
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  }'
```

#### Response (200 OK)
```json
{
  "success": true,
  "title": "Rick Astley - Never Gonna Give You Up (Official Music Video)",
  "extractor": "youtube",
  "original_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "format_count": 2,
  "formats": [
    {
      "format_id": "140",
      "format_note": "audio only",
      "ext": "m4a",
      "resolution": "audio only",
      "width": null,
      "height": null,
      "fps": null,
      "vcodec": null,
      "acodec": "mp4a.40.2",
      "filesize": 3498201,
      "filesize_approx": null,
      "tbr": 128.0,
      "vbr": null,
      "abr": 128.0,
      "has_video": false,
      "has_audio": true,
      "is_video_only": false,
      "is_audio_only": true,
      "protocol": "https",
      "url": "https://..."
    }
  ]
}
```

---

## Frontend Integration (SNMflix)

Here is a complete, production-ready TypeScript/JavaScript function for your SNMflix frontend (`MeloFlix/src` or Vercel API):

```typescript
interface ExtractMediaResult {
  success: boolean;
  title?: string;
  duration?: number;
  thumbnail?: string;
  extractor: string;
  original_url: string;
  media_url?: string;
  format_id?: string;
  resolution?: string;
  vcodec?: string;
  acodec?: string;
  has_video?: boolean;
  has_audio?: boolean;
  is_video_only?: boolean;
  is_audio_only?: boolean;
  is_live?: boolean;
  http_headers?: Record<string, string>;
  formats: Array<{
    format_id: string;
    resolution?: string;
    ext?: string;
    vcodec?: string;
    acodec?: string;
    has_video: boolean;
    has_audio: boolean;
    url?: string;
  }>;
}

export async function extractMediaFromUrl(
  mediaPageUrl: string,
  formatPreference?: string
): Promise<ExtractMediaResult> {
  const API_ENDPOINT = import.meta.env.VITE_MEDIA_API_URL || 'https://snmflix-media-api.onrender.com';
  const API_KEY = import.meta.env.VITE_MEDIA_API_KEY || '';

  const response = await fetch(`${API_ENDPOINT}/extract`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
    },
    body: JSON.stringify({
      url: mediaPageUrl,
      format: formatPreference,
    }),
  });

  const data = await response.json();

  if (!response.ok || !data.success) {
    const errorCode = data?.error?.code || 'EXTRACTION_ERROR';
    const errorMessage = data?.error?.message || 'Failed to extract media information';
    throw new Error(`[${errorCode}] ${errorMessage}`);
  }

  return data as ExtractMediaResult;
}
```

### Video Player Usage Note (HLS / Direct Stream)
When feeding `data.media_url` into your video player (e.g. `video.js`, `hls.js`, or native `<video>`):
```javascript
const player = document.getElementById('my-video-player');

// Check if format is HLS manifest (.m3u8)
if (data.media_url.includes('.m3u8') && Hls.isSupported()) {
  const hls = new Hls({
    xhrSetup: (xhr) => {
      // If provider requires Referer or custom headers:
      if (data.http_headers?.Referer) {
        // Browsers restrict setting Referer header directly in XHR,
        // but if using a proxy or server player this can be forwarded.
      }
    }
  });
  hls.loadSource(data.media_url);
  hls.attachMedia(player);
} else {
  player.src = data.media_url;
}
```

---

## Media Playback & Token Caveats

When consuming extracted stream URLs in the SNMflix frontend, be aware of standard CDN provider constraints:
1. **URL Expiration**: Many providers issue time-limited signatures or tokens embedded in query parameters (e.g. `expire=...`, `token=...`). These links typically expire within a few hours and should be fetched just before playback rather than cached permanently.
2. **Referer & Origin Checks**: Some CDNs block playback if the `Referer` header does not match the media provider domain. Check the returned `http_headers` field in the response.
3. **Separate Audio/Video Streams (DASH/Adaptive)**: High resolutions (e.g. 1080p/4K) on certain platforms are served as separate video-only and audio-only streams. The API explicitly marks these with `is_video_only: true` and `is_audio_only: true`. For standalone single-URL playback, select a combined format (`has_video: true` AND `has_audio: true`) or an HLS master manifest.

---

## Deploying to Render

This service is pre-configured for **Render Web Services** via the included `render.yaml`.

### Method A: Deploy with Blueprint (Recommended)

1. Push this repository to GitHub:
   ```bash
   git add .
   git commit -m "Initial commit of SNMflix Media Extraction API"
   git remote add origin git@github.com:your-user/snmflix-media-api.git
   git push -u origin main
   ```
2. Log in to the [Render Dashboard](https://dashboard.render.com/).
3. Click **New +** and select **Blueprint**.
4. Connect your GitHub repository.
5. Render will automatically detect `render.yaml` and configure:
   - **Environment**: Python
   - **Build Command**: `pip install --upgrade pip && pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path**: `/health`
6. Render will generate an `API_KEY` for you (or you can specify your own in the dashboard).
7. Click **Apply**.

### Method B: Manual Web Service Setup

If setting up without a Blueprint:
1. Click **New +** -> **Web Service**.
2. Connect your repository.
3. Fill in the service settings:
   - **Name**: `snmflix-media-api`
   - **Language**: `Python`
   - **Build Command**: `pip install --upgrade pip && pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Under **Advanced**:
   - **Health Check Path**: `/health`
5. Under **Environment Variables**, add:
   - `PYTHON_VERSION`: `3.12.3`
   - `ENVIRONMENT`: `production`
   - `API_KEY`: `your-secure-random-token`
   - `CORS_ORIGINS`: `https://snmflix.vercel.app`
   - `MAX_CONCURRENT_EXTRACTIONS`: `5`
   - `EXTRACTION_TIMEOUT_SECONDS`: `20`
   - `RATE_LIMIT_PER_MINUTE`: `60`
6. Click **Deploy Web Service**.

### Note Regarding FFmpeg
Simple metadata extraction and direct stream URL discovery with `yt-dlp` **do not require FFmpeg**. yt-dlp only requires FFmpeg when merging separate audio and video files onto the local server disk or performing format conversions. Because this API is purely an extraction service that does not store or process media files, FFmpeg is omitted, keeping the deployment lightweight, fast, and within Render's standard Python runtime.

---

## Troubleshooting & Common Errors

| Error Code | HTTP Status | Cause | Resolution |
|---|---|---|---|
| `SSRF_VIOLATION` | 400 | The requested URL points to localhost, a private network, or an internal address. | Ensure the target URL is a public web address using `http://` or `https://`. |
| `INVALID_URL` | 400 | The URL format is malformed or the domain name cannot be resolved via DNS. | Verify URL syntax and ensure the domain exists and is active. |
| `UNSUPPORTED_URL` | 422 | The target page is not supported by any yt-dlp extractor. | The website does not provide extractable media or uses unsupported custom players. |
| `MEDIA_UNAVAILABLE` | 404 | The video has been removed, marked private, or requires a login. | Verify that the video is publicly accessible in a web browser without login. |
| `UPSTREAM_RATE_LIMITED` | 429 | The third-party media website is rate-limiting extraction requests. | Reduce extraction frequency for that specific provider. |
| `RATE_LIMIT_EXCEEDED` | 429 | Client IP sent more than `RATE_LIMIT_PER_MINUTE` requests to this API. | Respect the `Retry-After` header before re-sending requests. |
| `EXTRACTION_TIMEOUT` | 504 | Upstream provider took longer than `EXTRACTION_TIMEOUT_SECONDS` to respond. | The target site is slow or hanging. Retry with a faster target or increase timeout. |
| `HTTP_ERROR` (401) | 401 | Missing or incorrect `X-API-Key` header. | Provide the configured secret key in the `X-API-Key` header. |
