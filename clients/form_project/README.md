# Microsoft Onsite Training Assessment System

A modern web application for managing onsite training assessments.

## Prerequisites

You need to have **Node.js** installed on your computer to run this application.
1. Download Node.js from [https://nodejs.org/](https://nodejs.org/) (Recommended: LTS version).
2. Install it.
3. Restart your terminal (PowerShell, Command Prompt, or VS Code).

## Setup & Running Locally

1. Open a terminal in this project folder (`c:\Users\Ratthabhumi\Desktop\CO-OP_Project\Form_Project`).
2. Install all dependencies:
   ```bash
   npm install
   ```
3. Start the development server (runs both frontend and backend):
   ```bash
   npm run dev
   ```
4. Open your browser and go to:
   - Admin Dashboard: [http://localhost:5173/admin](http://localhost:5173/admin)
   - The API is available at: [http://localhost:3000](http://localhost:3000)

## Features Included

- **Admin Dashboard**: View all training sessions, create new ones.
- **Training Details**: View all employee responses, their average scores, and download an Excel file with all responses.
- **QR Code Generation**: A QR Code is automatically generated for each session pointing to the assessment form.
- **Employee Assessment**: Responsive form pre-filled with the training details for employees to fill out.
- **SQLite Database**: Automatically initializes a `database.sqlite` file inside `server/database/`.

## Note
For this initial setup, we skipped adding authentication to the admin dashboard for easier testing, as requested for the "simple" version. We can add proper login later if needed.
