git clone https://github.com/yourusername/calendar-helper-ai.git
   cd calendar-helper-ai
   ```

2. **Set up environment variables**
   Create a `.env` file in the project root:
   ```
   OPENAI_API_KEY=your_api_key
   FLASK_SECRET_KEY=your_secret_key
   DATABASE_URL=postgresql://username:password@localhost:5432/dbname
   DEBUG_LOGGING=false
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python main.py
   ```
   Access the application at `http://localhost:5000`

## 🔄 API Endpoints

- `GET /` - Main application interface
- `POST /process` - Process image/text and generate events
- `POST /correct` - Apply corrections to existing events
- `POST /download-ics` - Generate and download iCalendar file

## 📁 Project Structure

```
├── app.py                 # Flask application setup
├── routes.py             # API endpoints
├── utils/
│   ├── ai_processor.py   # OpenAI integration
│   ├── calendar.py       # iCalendar generation
│   └── location_service.py # Location services
├── static/               # Frontend assets
└── templates/            # HTML templates
```

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Add comprehensive docstrings and comments
- Write unit tests for new features
- Update documentation as needed
- Ensure all tests pass before submitting PRs

## 🔒 Privacy & Security

- All data processing occurs in-memory
- No permanent storage of user data
- GDPR, CCPA, and LGPD compliant
- Regular security audits and updates

## 🙏 Acknowledgements

Built with these amazing technologies:

- [Flask](https://flask.palletsprojects.com/) - Web framework
- [OpenAI](https://openai.com/) - AI processing engine
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database ORM
- [iCalendar](https://icalendar.readthedocs.io/) - Calendar file generation
- [Flask-Login](https://flask-login.readthedocs.io/) - User session management

## 📄 License

This project is licensed under the MIT License:

```
MIT License

Copyright (c) 2024 Calendar Helper AI

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.