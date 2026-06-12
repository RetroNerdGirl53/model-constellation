# Agent Tracking System

This directory contains files for tracking agent logic, thinking, decisions, actions, and testing.

## Files Overview

| File | Purpose | Format |
|------|---------|--------|
| `SESSION.md` | Overall session tracking | Markdown |
| `session.json` | Session data for AI context | JSON |
| `ACTIONS.md` | Human-readable action log | Markdown |
| `actions.json` | Action data for AI context | JSON |
| `THINKING.md` | Human-readable thinking log | Markdown |
| `thinking.json` | Thinking data for AI context | JSON |
| `TESTING.md` | Human-readable test results | Markdown |
| `testing.json` | Test data for AI context | JSON |

## Usage

### Markdown Files (Human-Readable)
- `SESSION.md` - Main session tracker with task description, steps, decisions, results, notes
- `ACTIONS.md` - Log of all actions with timestamps, types, descriptions, modified files
- `THINKING.md` - Decision-making process with reasoning and alternatives
- `TESTING.md` - Test results and notes

### JSON Files (AI-Friendly)
- `session.json` - Structured session data including tasks, context, subagents
- `actions.json` - Structured action log with results and subagent info
- `thinking.json` - Structured thinking with confidence levels and related files
- `testing.json` - Structured test results with output snippets and model info

## Updating Files

When the agent performs actions:
1. Add entries to the appropriate markdown files
2. Add corresponding JSON objects to the JSON files
3. Keep markdown and JSON in sync

## Timestamp Format
- ISO 8601 format: `YYYY-MM-DDTHH:MM:SSZ`
