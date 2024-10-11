# DevSearch

DevSearch is a web-based platform where developers can create profiles, showcase their projects, manage skills, send and receive messages, and tag their projects. The project is built using Starlette/FastAPI with both rendered HTML pages and API support, featuring asynchronous database interactions and secure authentication.

## Key Features

- JWT Authentication: Secure user authentication with JSON Web Tokens (JWT).
- Email Verification: Users receive an email verification link to activate their account.
- Image Uploads:
  - Upload profile images or project image.
  - Validate image formats and file sizes.
  - Compress images for optimal performance.
- Search and Filtering:
  - Search for projects or developers.
  - Use filters to narrow down results.
- Messaging System:
  - Send and receive messages between users.
  - View unread messages count.

## Tools & Technologies

- FastAPI: High-performance API framework.
- Starlette: Lightweight ASGI framework providing request handling and templating support.
- SQLAlchemy: SQL toolkit and Object-Relational Mapping (ORM).
- Pydantic v2: Data validation and settings management using Python type hints.
- Passlib & Bcrypt: Password hashing for secure authentication.
- aiosmtplib: Asynchronous email sending for user verification.
- Jinja2: Templating engine for rendering HTML emails and responses.
