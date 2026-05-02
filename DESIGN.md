# FairLens Design System

## Aesthetic: Cyber-Legalist (Premium Dark Mode)
- **Primary Background**: `#0A0A0B` (Deep Matte Black)
- **Surface**: `rgba(255, 255, 255, 0.03)` (Glassmorphism)
- **Accent 1**: `#00D1FF` (Cyan - Trust/Data)
- **Accent 2**: `#FF3B30` (Red - Risk/Block)
- **Accent 3**: `#34C759` (Green - Pass/Safety)
- **Typography**: Inter / Outfit (Modern Sans)
- **Effects**: Backdrop blurs, subtle glowing borders, micro-interactions on hover.

## Core Components
### 1. The Audit Gate (Landing)
- Hero section with a glowing "Pulse" animation representing the fairness scan.
- Objective: "Audit your dataset design before it impacts lives."

### 2. Guided Questionnaire
- Step-by-step navigation (12 questions).
- Progress bar with a "Scanning..." animation between sections.

### 3. Conflict Graph
- A force-directed graph (using Framer Motion or D3) showing the three agents.
- Lines between agents glow Red if they are in conflict.

### 4. Simulation Dashboard
- Real-time charting using Recharts.
- Negative bars for underrepresentation.

## Design Tokens
- `bg-glass`: `backdrop-blur-md bg-white/5 border border-white/10 rounded-2xl`
- `text-glow-cyan`: `text-[#00D1FF] drop-shadow-[0_0_8px_rgba(0,209,255,0.5)]`
