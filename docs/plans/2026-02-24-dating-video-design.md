# Dating Video Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a faceless YouTube video (1920x1080, 30fps) illustrating a comedy monologue about dating advice, with dark/moody aesthetic, stock imagery + graphics.

**Architecture:** Generate slide images with Python Pillow -> package as PPTX -> import PNGs into DaVinci Resolve -> build timed timeline synced to transcript.

**Tech Stack:** Python (Pillow, python-pptx), DaVinci Resolve MCP

---

## Scene Breakdown (31 slides)

| # | Scene | Time | Type |
|---|-------|------|------|
| 1 | "Here's what the internet has taught me about dating" | 14.83-18.41 | intro |
| 2 | Silence/tension beat | 18.41-23.08 | black |
| 3 | "DON'T." | 23.08-23.6 | impact |
| 4-11 | Rapid-fire "Don'ts" (friends, online, coworkers, strangers, gym, bars, DMs, organic) | 23.66-55.82 | dont_card |
| 12 | "Alone, I guess, but morally clean" | 58.6-61.94 | punchline |
| 13 | "You think I'm done?" | 62.36-63.48 | transition |
| 14-15 | Age gaps, power differences | 64.28-78.14 | accusation |
| 16-18 | Attracted to success/youth/looks | 78.14-87.36 | attraction |
| 19 | Attracted to mind ("give it time") | 88.22-98.3 | attraction_special |
| 20 | "You think we're done?" | 99.18-102.84 | transition |
| 21-30 | Behavior contradictions (sex, commitment, exclusivity, etc.) | 102.84-132.04 | behavior |
| 31 | Venn diagram finale ("single pixel") | 135.34-145.5 | finale |

## Tasks

### Task 1: Generate Slide Images
- Write Python/Pillow script to create 31 slides at 1920x1080
- Dark moody palette: #0D0D0D bg, #F0F0F0 text, #FF3B3B red accent, #F6AD55 amber
- Save PNGs to output/slides/

### Task 2: Create PPTX
- Package slide PNGs into a presentation using python-pptx

### Task 3: DaVinci Resolve - Project & Timeline
- Create project, create timeline (1920x1080, 30fps)

### Task 4: DaVinci Resolve - Import & Build
- Import all slide PNGs
- Place on timeline with correct timing from transcript
- Add transitions between sections

### Task 5: QA & Polish
- Visual review of slides
- Verify timeline timing
