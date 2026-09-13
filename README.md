# ores-otel-assets
Versioned product images, CSS, CDN exports, and static assets; app branding is isolated from marketing sites.

## Layout

| Path | Role |
| --- | --- |
| `branding/app-logo.png` | Source authority for the app logo (1254x1254). |
| `exports/png/app-logo-<size>.png` | Static/CDN exports at 16, 32, 48, 64, 128, 180, 192, 256 and 512 px. |
| `asset-manifest.json` | sha256 + dimensions for every file, plus the Flutter launcher source checksum. |

`brandApproval` stays `pending` until the logo is approved by a human; approval is
recorded by changing that field in a reviewed PR, never by a script.

## Regenerating and validating

```sh
# after replacing branding/app-logo.png, rebuild exports (macOS sips shown)
for n in 16 32 48 64 128 180 192 256 512; do
  sips -s format png -z "$n" "$n" branding/app-logo.png --out "exports/png/app-logo-$n.png"
done
python3 scripts/validate.py --write   # refresh asset-manifest.json
python3 scripts/validate.py           # fails on checksum/size drift or unlisted exports
```

Flutter consumers (`ores-otel/ores-otel-flutter`) should compare the launcher
source they generated icons from against `flutterLauncher.sha256`.
