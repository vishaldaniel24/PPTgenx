# AI Research PPT Generator - Frontend

Premium Streamlit frontend for the AI-powered research-to-PowerPoint application.

## Features

✨ **Premium UI Design**
- Beautiful gradient headers and card layouts
- Smooth transitions and hover effects
- Professional color scheme

🌓 **Dark & Light Mode**
- Toggle between dark and light themes
- Persistent theme preference

🎨 **Template Selection**
- Choose from built-in professional templates
- Upload custom branded templates

📊 **Real-time Progress**
- Live status updates during generation
- Visual progress bar with stage indicators

📥 **Easy Download**
- One-click PPT download
- Automatic file naming

## Installation

1. **Install dependencies:**
   ```bash
   cd frontend
   pip install -r requirements.txt
   ```

2. **Configure backend URL (optional):**
   - Copy `.env.example` to `.env`
   - Update `BACKEND_URL` if your backend is not on localhost:8000

## Running the App

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## Usage

1. **Enter a research prompt** - Example: "I want to know about Tesla: what they do, their projects, competitors, and contact info"

2. **Select a template** - Choose from 3 built-in professional themes or upload your own

3. **Generate** - Click the generate button and watch the AI agents work

4. **Download** - Get your professional PowerPoint presentation

## Architecture

```
app.py                  # Main Streamlit application with all UI components
requirements.txt        # Python dependencies
.env.example           # Environment variables template
```

## Customization

### Colors
Edit the CSS in `apply_custom_css()` function to change the color scheme:
- Primary gradient: `#667eea` to `#764ba2`
- Status colors: Defined in `.status-*` classes

### Templates
Add more built-in templates in the `render_template_selector()` function by extending the `templates` list.

## Troubleshooting

**Backend connection fails:**
- Make sure the backend is running on `http://localhost:8000`
- Check the `BACKEND_URL` variable in the code or `.env` file

**Theme not switching:**
- Clear browser cache and refresh
- Check browser console for errors

## Technologies

- **Streamlit**: Web framework
- **Requests**: API communication
- **Custom CSS**: Premium styling
