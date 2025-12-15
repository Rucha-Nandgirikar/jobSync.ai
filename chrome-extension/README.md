# JobSync AI Chrome Extension

Chrome extension for AI-powered job application assistance.

## Installation

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select the `chrome-extension` folder

## Setup

1. Make sure the backend server is running on `http://localhost:8000`
2. Open the extension popup
3. Enter your User ID in Settings
4. Navigate to a job posting page (Ashby, Greenhouse, Lever, LinkedIn)
5. Click the extension icon to capture job and generate answers

## Features

- **Job Capture**: Automatically detects job descriptions and questions
- **Answer Generation**: Uses CrewAI to generate human-like answers
- **User Suggestions**: Add hints/guidance for personalized answers
- **Answer Management**: Copy, regenerate, or submit answers

## Development

- `manifest.json` - Extension configuration
- `popup.html/js` - Extension popup UI
- `content.js` - Content script for page interaction
- `background.js` - Service worker for background tasks




