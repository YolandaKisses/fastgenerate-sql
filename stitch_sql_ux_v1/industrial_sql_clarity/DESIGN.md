---
name: Industrial SQL Clarity
colors:
  surface: '#f9f9ff'
  surface-dim: '#d8dae3'
  surface-bright: '#f9f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f1f3fd'
  surface-container: '#ecedf7'
  surface-container-high: '#e6e8f1'
  surface-container-highest: '#e0e2ec'
  on-surface: '#181c22'
  on-surface-variant: '#414753'
  inverse-surface: '#2d3038'
  inverse-on-surface: '#eef0fa'
  outline: '#717785'
  outline-variant: '#c1c6d6'
  surface-tint: '#005db7'
  primary: '#005bb3'
  on-primary: '#ffffff'
  primary-container: '#0073e0'
  on-primary-container: '#fefcff'
  inverse-primary: '#a9c7ff'
  secondary: '#466082'
  on-secondary: '#ffffff'
  secondary-container: '#bcd6fe'
  on-secondary-container: '#435d7f'
  tertiary: '#954500'
  on-tertiary: '#ffffff'
  tertiary-container: '#bb5800'
  on-tertiary-container: '#fffbff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d6e3ff'
  primary-fixed-dim: '#a9c7ff'
  on-primary-fixed: '#001b3d'
  on-primary-fixed-variant: '#00468c'
  secondary-fixed: '#d3e4ff'
  secondary-fixed-dim: '#aec8f0'
  on-secondary-fixed: '#001c38'
  on-secondary-fixed-variant: '#2e4869'
  tertiary-fixed: '#ffdbc8'
  tertiary-fixed-dim: '#ffb68b'
  on-tertiary-fixed: '#321300'
  on-tertiary-fixed-variant: '#753400'
  background: '#f9f9ff'
  on-background: '#181c22'
  surface-variant: '#e0e2ec'
typography:
  h1:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  h2:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  code:
    fontFamily: Monospace
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 12px
  panel-padding: 20px
---

## Brand & Style

The design system is engineered for the professional developer who demands precision and clarity. It adopts a **Minimalist Industrial** aesthetic, drawing heavily from the Naive UI philosophy of "sophisticated simplicity." The interface prioritizes focus by reducing visual noise, replacing heavy shadows with crisp, low-contrast borders and expansive whitespace. 

The emotional response should be one of "quiet competence"—a tool that feels high-quality, reliable, and unobtrusive. The style is strictly flat, utilizing subtle tonal shifts to indicate hierarchy rather than decorative depth.

## Colors

The palette is anchored by a vibrant Primary Blue (#2080f0), used sparingly for action states and indicators to maintain a professional atmosphere. The foundation of the UI is built on a "Pure & Paper" logic:
- **Backgrounds**: Pure white (#ffffff) for primary workspaces (SQL editors, results tables) and a very light gray (#fbfcfd) for utility panels and sidebars.
- **Borders**: All structural separation is handled by a subtle light lilac-gray (#efeff5), ensuring components feel integrated rather than floating.
- **Typography**: High-contrast charcoal (#1f2225) for code and headlines, with a muted slate (#767c82) for secondary metadata and labels.

## Typography

This design system utilizes **Inter** for all interface elements to ensure maximum legibility at small sizes. The hierarchy is established through weight and color rather than drastic size changes. 

For the core SQL editing experience, a system-default monospace font is preferred for its familiarity and performance. Line heights are intentionally generous (e.g., 1.5x) to prevent "code fatigue" during long debugging sessions. Labels use a slightly heavier weight and subtle letter spacing to distinguish them from editable content.

## Layout & Spacing

The layout philosophy follows a **Fluid Panel** model, typical of high-performance IDEs, but with increased breathing room. While density is often prioritized in data tools, this design system mandates an 8px-based grid with a 4px sub-grid for tighter components.

- **Margins**: Sidebar and main panel contents should maintain a 20px padding from container edges.
- **Gaps**: Components within a stack should use 12px or 16px gaps to avoid a "cluttered" industrial look.
- **Data Tables**: Table cells must include horizontal padding of 12px to ensure data points are clearly delineated.

## Elevation & Depth

This design system rejects traditional drop shadows in favor of **Tonal Layering** and **Low-Contrast Outlines**. 

1. **Surface Tiers**: The base layer is #fbfcfd. Active workspace areas (like the Editor) sit "on top" visually by using a #ffffff background and a 1px #efeff5 border.
2. **Contextual Overlays**: Modals and dropdown menus use a very soft, diffused shadow (0px 4px 12px rgba(0,0,0,0.05)) combined with a solid border to ensure they are distinct from the background layers.
3. **Interactive Depth**: Buttons and inputs do not use "inner shadows" or "bezel effects." They remain flat, using color fills and border-color changes to indicate interaction states.

## Shapes

The design system employs a consistent **4px (0.25rem)** corner radius across all interactive elements, including buttons, input fields, and panel headers. This "Soft" radius strikes a balance between the rigid precision of a technical tool and the approachability of a modern web application.

- **Inputs/Buttons**: 4px radius.
- **Large Containers (Cards/Modals)**: 8px (0.5rem) radius.
- **Selection Indicators**: 2px radius for subtle focus states.

## Components

- **Buttons**: Use a flat fill for primary actions (#2080f0 with white text) and a "ghost" style for secondary actions (white background, #efeff5 border).
- **SQL Editor**: The editor should have no internal borders. Line numbers are separated from the code by a subtle vertical line in #efeff5.
- **Data Grids**: Use a "Zebra Striping" method with #fbfcfd on alternate rows. The header row should be slightly darker (#f7f7fa) with a solid bottom border.
- **Chips / Badges**: Used for SQL Keywords or Statuses. These should have a 2px radius and use light-tinted backgrounds (e.g., Primary Blue at 10% opacity) with the full-saturation color for text.
- **Input Fields**: Default state is a #efeff5 border. On focus, the border transitions to Primary Blue with a 2px transparent blue glow (outline).
- **Sidebar Navigation**: Active states are indicated by a 3px vertical "pill" on the left edge in Primary Blue, rather than highlighting the entire background of the menu item.