# Privacy

Placement Dashboard is a student mini-project at NITK. It collects only what it needs.

**Sign-in.** Google sign-in gives the app your email address and name. Only `@nitk.edu.in` accounts (and listed admins) can use it.

**What is stored** (hosted SQLite database, Turso):
- Reviews you submit, with your name, email, optional LinkedIn link and the details you enter. Reviews are shown only after an admin approves them.
- Your email is shown to other signed-in students only if you tick "Show my email".
- One row per Ask AI question (email + time) to enforce the daily limit.

**AI.** Review text and statistics are sent to third-party language models to answer questions and write summaries. Names, emails, LinkedIn links and phone numbers are removed first.

**Not done.** No ads, no tracking, no selling or sharing of data. Reviews older than two years are hidden.

**Removal.** To remove your review or data, open an issue on this repository or ask an admin.
