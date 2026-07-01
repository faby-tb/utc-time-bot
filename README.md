# 🕒 UTC Clock Discord Bot

A lightweight Discord bot that displays UTC time using a live voice channel clock, slash commands, and dynamic bot presence.

Designed to be simple, multi-server friendly, and optimized to reduce Discord API usage.

---

## ✨ Features

* 🕒 UTC clock displayed in a voice channel
* ⚡ Automatic channel updates every 15 minutes
* 🎮 Dynamic bot status showing current UTC time
* 🌍 Multi-server support
* 🛠 Slash command controls
* 🔐 Permission-based management
* 🧠 Optimized to reduce rate limits
* ☁️ Ready for Railway deployment

---

# 📸 Preview

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

# 🚀 Commands

## /clock

Enable or disable the UTC clock for the server.

### Enable

```text
/clock enabled:true
```

### Disable

```text
/clock enabled:false
```

Required permission:

```text
Manage Server
```

---

## /clock_refresh

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

## /utc

Displays the current UTC time.

```text
/utc
```

Example:

```text
🕒 UTC time: 21:15 UTC
```

---

# ⚙️ How It Works

When enabled:

1. The bot creates a voice channel:

   ```text
   🕒 UTC • HH:MM
   ```

2. The channel updates automatically every 15 minutes.

3. Bot presence updates every 60 seconds.

4. Each server stores its own configuration independently.

---

# 🌍 Multi Server Support

Every server has:

* Independent clock state
* Independent channel
* Persistent settings

Configuration is stored in:

```text
settings.json
```

---

# 🧠 Rate Limit Friendly Design

This project intentionally avoids excessive Discord API requests.

Optimizations include:

* Channel updates every 15 minutes
* Presence updates only when time changes
* Cached clock channels
* Reduced channel edits

---

# 📦 Installation

## Clone repository

```bash
git clone https://github.com/faby-tb/utc-clock-bot.git
cd utc-clock-bot
```

---

## Install dependencies

```bash
pip install -r requirements.txt
```

---

## Create .env

Create a file called:

```text
.env
```

Insert:

```env
TOKEN=YOUR_DISCORD_BOT_TOKEN
```

---

## Run locally

```bash
python bot.py
```

---

# ☁️ Deploy

Recommended platforms:

* Railway
* Render
* VPS
* Replit (light usage)

---

# 🔐 Required Permissions

Bot permissions:

* View Channels
* Send Messages
* Manage Channels
* Connect

Scopes:

```text
bot
applications.commands
```

Administrator permission is NOT required.

---

# 📁 Project Structure

```text
utc-clock-bot/
│
├── bot.py
├── settings.json
├── .env
├── requirements.txt
└── README.md
```

---

# 💡 Example Use Cases

* International communities
* Global gaming guilds
* Development servers
* UTC event coordination
* Community hubs

---

# 🧩 Future Improvements

* Timezone per server
* Dashboard panel
* SQLite storage
* Web configuration
* Statistics commands
* Rich embeds

---

# 👨‍💻 Author

Created by faby-tb

---

# 📜 License

MIT License

Free to use, modify, and distribute.
