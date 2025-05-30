# AI Adventures

AI Adventures is a Django-based web application that leverages Google's Gemini AI to create personalized, interactive bedtime stories for children. The application allows users to craft unique adventures by defining characters, settings, and story elements that are then transformed into engaging narratives through AI.

## 🌟 Features

- **Personalized Story Creation**: Create custom stories with characters and settings tailored to your preferences
- **Age-Appropriate Content**: Stories are generated based on selected age groups (3-6, 5-8, 7-11, 10-13, 13+)
- **Rich Customization Options**: Define story genres, tones, character details, and world settings
- **Audio Narration**: Text-to-speech functionality to listen to generated stories
- **Story Illustrations**: AI-generated images to accompany story chapters
- **User Management**: Complete user authentication system with profile management
- **Subscription Tiers**: Different access levels with varying features (Free, Daily, Family, Unlimited)
- **Responsive Design**: Mobile-friendly interface for storytelling on any device

## 🛠️ Technology Stack

- **Backend**: Django 5.1+
- **Database**: PostgreSQL
- **Cloud Infrastructure**: Google Cloud Platform (App Engine, Cloud SQL, Secret Manager)
- **AI Services**: Google Gemini AI for story generation, Google Cloud Text-to-Speech
- **Payment Processing**: Stripe integration for subscription management
- **Storage**: Google Cloud Storage for media files
- **Frontend**: Bootstrap 4, JavaScript, HTML5, CSS3
- **Security**: HTTPS enforcement, secure cookie handling, HSTS implementation

## 🚀 Deployment

The application is configured for deployment on Google Cloud App Engine with the following features:

- PostgreSQL database connection via Cloud SQL
- Secret management using Google Cloud Secret Manager
- Static files served via WhiteNoise
- Media files stored in Google Cloud Storage
- HTTPS enforcement with secure headers

## 🔧 Local Development Setup

1. Clone the repository
2. Create a virtual environment: `python -m venv .venv`
3. Activate the virtual environment:
   - Windows: `.venv\\Scripts\\activate`
   - Unix/MacOS: `source .venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Set up environment variables (see `.env.example`)
6. Run migrations: `python manage.py migrate`
7. Create a superuser: `python manage.py createsuperuser`
8. Run the development server: `python manage.py runserver`

## 📁 Project Structure

- **access**: User authentication and registration
- **bedtime_ai**: Main project settings and configuration
- **custom_admin**: Customized admin interface
- **gemini**: AI integration for story generation
- **landing**: Landing page and marketing content
- **main_app**: Core application functionality
- **user_profile**: User profile management
- **templates**: Global templates
- **staticfiles**: Compiled static assets

## 📝 License

This project is proprietary and not licensed for public use or distribution.

## 👥 Contact

For inquiries about this project, please contact [your contact information].

---

© 2024 AI Adventures. All rights reserved.