# ArthVani Brand Identity Guidelines

This document outlines the visual identity system, geometric construction, sizing, approved pairings, and usage rules for the ArthVani brand.

---

## 1. Brand Concept & Anatomy

The ArthVani identity merges two primary ideas:
1. **Speech Bubble Silhouette**: Represents voice-first conversational interaction ("बोलिए" / "Speak").
2. **Indian Rupee (`₹`) Inscription**: Represents accurate, instantaneous ledger balancing ("हिसाब हो जाएगा" / "The ledger is done").

Both elements share an identical geometric stroke weight (`28px` on a `512×512` grid) with rounded terminals and smooth corner joins.

---

## 2. Clear Space

To maintain visual impact and prevent interference with neighbouring UI elements:
* **Minimum Clear Space**: $X = \frac{1}{2} \text{ of the mark's total height}$.
* No text, buttons, borders, or competing graphics may enter this exclusion perimeter.

```
       ┌─────────────────────────────┐
       │             X               │
       │     ┌─────────────────┐     │
       │  X  │   [LOGO MARK]   │  X  │
       │     └─────────────────┘     │
       │             X               │
       └─────────────────────────────┘
```

---

## 3. Minimum Sizing

To ensure pixel clarity and avoid illegible details:
* **Standalone Outline Mark (`logo-mark.svg`)**: Minimum height **24px**.
* **Filled Silhouette Mark (`logo-mark-filled.svg` / `favicon.svg`)**: Minimum height **16px** (optimized for browser tabs and micro-chips).
* **Horizontal Lockup (`logo-horizontal.svg`)**: Minimum width **96px** (height 24px).
* **Stacked Lockup (`logo-stacked.svg`)**: Minimum width **80px** (height 70px).

---

## 4. Approved Color Pairings

ArthVani operates with disciplined color tokens (maximum 2 hues in any lockup):

| Surface / Context | Mark Color | Wordmark "Arth" | Wordmark "Vani" | Contrast Ratio |
| :--- | :--- | :--- | :--- | :--- |
| **Maroon Sidebar** (`#2A0E22`) | Pure White (`#FFFFFF`) | Pure White (`#FFFFFF`) | Pure White (`#FFFFFF`) | **16.8:1** (AAA) |
| **White Surface** (`#FFFFFF`) | Deep Maroon (`#2A0E22`) | Dark Charcoal (`#1A1118`) | Magenta Accent (`#B8336A`) | **15.8:1** & **5.56:1** (AA) |
| **Light Page Neutral** (`#FAF8F9`) | Deep Maroon (`#2A0E22`) | Dark Charcoal (`#1A1118`) | Magenta Accent (`#B8336A`) | **14.9:1** & **5.25:1** (AA) |
| **App Icon Tile** | Pure White (`#FFFFFF`) mark centered on Maroon (`#2A0E22`) rounded tile | — | — | **16.8:1** (AAA) |

> **Contrast Rule**: In dark contexts (such as the maroon sidebar), the accent color (`#B8336A`) drops to 2.5:1 against `#2A0E22`. Therefore, on dark backgrounds, the entire lockup uses Pure White (`#FFFFFF`) to strictly uphold WCAG AA accessibility standards (>= 4.5:1).

---

## 5. The Four "Don't" Rules

To preserve brand integrity and professional appearance, never violate these four rules:

1. **Do NOT stretch, distort, or skew**: Always constrain proportions (1:1 aspect ratio for the mark).
2. **Do NOT recolor arbitrarily**: Use only approved brand tokens (`#2A0E22`, `#FFFFFF`, `#B8336A`, `#1A1118`). Never use gradients, gold foils, random neons, or unapproved tints.
3. **Do NOT apply decorative effects**: Never add drop shadows, outer glows, bevels, 3D extrusions, or AI-style sparkles.
4. **Do NOT place on busy or low-contrast backgrounds**: Never place the mark over patterned wallpaper, low-contrast photos, or unapproved colored fills.

---

## 6. Asset Directory Index (`brand/`)

```
brand/
├── logo-mark.svg                 # Base outline vector mark (currentColor)
├── logo-mark-filled.svg          # Solid silhouette with knocked-out rupee
├── logo-mark-on-dark.svg         # White outline mark for dark surfaces
├── logo-mark-on-light.svg        # Maroon outline mark for light surfaces
├── logo-mono-dark.svg            # Pure monochrome white
├── logo-mono-light.svg           # Pure monochrome dark (#1A1118)
├── logo-horizontal.svg           # Horizontal lockup for light surfaces
├── logo-horizontal-on-dark.svg   # Horizontal lockup for maroon sidebar
├── logo-stacked.svg              # Stacked vertical lockup
├── app-icon.svg                  # Rounded squircle app icon tile (512x512)
├── favicon.svg                   # Crisp vector favicon (filled variant)
├── compare.html                  # 100% overlay alignment tool against original
├── preview.html                  # Scale and variant test suite (16px to 128px)
├── GUIDELINES.md                 # Brand identity rules & usage guidelines
└── png/
    ├── favicon-16.png            # 16x16 PNG for standard browser tabs
    ├── favicon-32.png            # 32x32 PNG for high-DPI browser tabs
    ├── apple-touch-icon.png      # 180x180 PNG for iOS home screen
    ├── app-icon.png              # 512x512 PNG for app store / desktop tile
    └── social-card.png           # 1200x630 OpenGraph / Twitter preview card
```

