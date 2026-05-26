# docs/

This directory holds visual assets referenced in the project README.

## Expected contents

| File | Description |
|------|-------------|
| `hero-demo.gif` | Animated demo showing the paste-URL-to-slides workflow (~720px wide, <5MB) |
| `editor-screenshot.png` | Screenshot of the slide editor UI |
| `presenter-mode.png` | Screenshot of presenter mode |

## Recording the demo GIF

Recommended tools: [Kap](https://getkap.co/) (macOS) or [Peek](https://github.com/phw/peek) (Linux).

1. Start both backend and frontend locally
2. Open http://localhost:8877
3. Record: paste a URL → click Generate → watch slides stream in → show final result
4. Export as GIF, optimize with `gifsicle --optimize=3 -o hero-demo.gif input.gif`
5. Place the file here as `hero-demo.gif`
