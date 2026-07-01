# 🕒 UTC Clock Discord Bot

A lightweight Discord bot that displays UTC time using a live voice channel clock, slash commands, and dynamic bot presence.

Designed to be simple, multi-server friendly, and optimized for low Discord API usage with persistent cloud storage.

---

## 🔗 Invite the Bot

https://discord.com/oauth2/authorize?client_id=1521608715055403088&permissions=2148600848&integration_type=0&scope=bot+applications.commands

---

## ✨ Features

- 🕒 Live UTC clock in a voice channel  
- ⚡ Automatic channel updates (efficient interval-based system)  
- 🎮 Dynamic bot presence showing current UTC time  
- 🌍 Fully multi-server support  
- 🛠 Slash command system (/clock, /utc, /clock_refresh)  
- 🔐 Permission-based controls (Manage Server required)  
- ☁️ Persistent database storage (Supabase / cloud DB)  
- 📊 Web dashboard for monitoring servers  
- 🧠 Optimized Discord API usage (rate-limit safe)  

---

## 🗄️ Database

This bot uses a **cloud database (Supabase / PostgreSQL)** for persistence.

This ensures:
- No data loss on restart  
- Stable multi-server configuration  
- Reliable channel tracking  

### Stored per server:
- Guild ID  
- Enabled status  
- Channel ID  
- Last update timestamp  

---

## 📸 Preview

Voice channel:
```text
🕒 UTC • 21:15
```

Bot status:
```text
Watching 🕒 UTC 21:15
```

Command:
```text
/utc
```

Response:
```text
🕒 UTC time: 21:15 UTC
```

---

## 🚀 Commands

### /clock
```text
Enable or disable the UTC clock for the server.
```
Enable:
```text
/clock enabled:true
```

Disable:
```text
/clock enabled:false
```

Required permission:
```text
Manage Server
```
---

### /clock_refresh

Force update the UTC clock immediately.

```text
/clock_refresh
```

Example response:
```text
Clock updated → 21:15 UTC ✅
```

Required permission:
```text
Manage Server
```
---

### /utc

Displays the current UTC time.

```text
/utc
```

Example:
```text
🕒 UTC time: 21:15 UTC
```

---

## ⚙️ How It Works

When enabled:

1. The bot creates or reuses a voice channel:
```text
🕒 UTC • HH:MM
```

2. The channel updates automatically at intervals.

3. Bot presence updates every minute.

4. Server configuration is stored in a cloud database to ensure persistence.

---

## 🌍 Multi Server Support

Each server has:

- Independent clock state  
- Dedicated voice channel  
- Persistent settings across restarts  
- Last update tracking

---

## ☁️ Persistence

Unlike local storage versions, this bot uses:

- Supabase (PostgreSQL cloud database)  
- No data loss on restart  
- Fully persistent configuration  

---

## 🧠 Rate Limit Friendly Design

- Minimal channel edits  
- Cached guild configuration  
- Efficient update loops  
- No unnecessary API requests  

---

## 📦 Installation

### Clone repository

```text
git clone https://github.com/faby-tb/utc-clock-bot.git
cd utc-clock-bot
```

---

### Install dependencies

```text
pip install -r requirements.txt
```

---

### Create .env file

```text
TOKEN=YOUR_DISCORD_BOT_TOKEN
SUPABASE_URL=YOUR_SUPABASE_URL
SUPABASE_KEY=YOUR_SUPABASE_KEY
```

---

### Run locally

```text
python bot.py
```

---

## ☁️ Deploy

Recommended platforms:

- Railway  
- Render  
- VPS  
- Replit (light usage only)  

---

## 🔐 Permissions

Bot requires:

- View Channels  
- Send Messages  
- Manage Channels  
- Connect  

Scopes:

```text
bot
applications.commands
```

---

## 📊 Dashboard

The bot includes a web dashboard for monitoring:

- Server list  
- Clock status  
- Channel tracking  
- Last update timestamps  

---

## 📁 Project Structure

```text
utc-clock-bot/
│
├── bot.py
├── requirements.txt
├── .env
└── README.md
```

---

## 💡 Use Cases

- International Discord communities  
- Gaming guilds  
- Event coordination  
- Developer servers  
- MMO / roleplay communities  

---

## 👨‍💻 Author

Created by faby-tb

---

## 📜 License

MIT License  
Free to use, modify, and distribute
