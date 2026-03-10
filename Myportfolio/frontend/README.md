# Frontend (React + Vite)

## Setup

```bash
cd frontend
npm install
npm run dev
```

Server will start at `http://localhost:5173`

## Build

```bash
npm run build
```

Outputs to `dist/` for production deployment.

## Project Structure

```
src/
├── main.tsx          # React entry point
├── App.tsx           # Main app component
├── ConfigForm.tsx    # Budget input & usage selection form
├── ResultView.tsx    # Configuration result display
├── api.ts            # API client functions
└── index.css         # Global TailwindCSS styles
```

## Features

- **Responsive Design**: Mobile-friendly UI with TailwindCSS
- **Real-time Budget Preview**: Shows formatted currency as user types
- **Quick Presets**: 50k / 100k / 150k / 200k JPY buttons
- **Usage Selection**: Gaming / Video Editing / General purpose
- **Result Display**: Shows PC parts with prices and purchase links
- **Error Handling**: Graceful error messages from API

## API Integration

Frontend communicates with backend at `http://localhost:8000`:

```
POST /generate-config
{
  "budget": 150000,
  "usage": "gaming"
}
```

Proxy configured in `vite.config.ts` for development.

## Styling

TailwindCSS v3 with:
- Gradient backgrounds
- Responsive grid layouts
- Transition animations
- Accessibility-focused color contrasts

## Next Steps

1. Deploy to Vercel or Netlify
2. Add user authentication (optional future)
3. Implement favorites saving
4. Add performance score display
