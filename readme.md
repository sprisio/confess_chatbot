\# Anonymous Confession Bot — MVP



Minimal Telegram bot (Aiogram) for anonymous confessions with reaction-based ranking.



\## Features (MVP)

\- /start, /confess (6 categories incl. Random 🎲)

\- Posts anonymously to a public channel and sends a permalink to the submitter

\- Inline reaction buttons + stores reaction counts

\- /leaderboard (today / week / alltime)

\- Basic moderation: strips URLs and phone-like tokens



\## Requirements

\- Python 3.10+

\- PostgreSQL

\- Redis (optional, for scaling)



\## Setup

1\. Clone this repo.

2\. Copy `.env.example` to `.env` and fill in your values.

3\. Create the database and run the migration:

&nbsp;  ```bash

&nbsp;  createdb confessions

&nbsp;  psql confessions < migrations/init.sql



