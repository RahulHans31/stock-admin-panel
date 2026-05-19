# Stock Tracker Backend

Standalone Python Docker container that continuously monitors product stock from your database and sends Telegram alerts when items are in stock.

## Features

- ✅ Runs infinitely with configurable check intervals
- ✅ Direct API calls to all stores (no proxy needed)
- ✅ Connects to PostgreSQL database to fetch products
- ✅ Sends Telegram alerts with topic support
- ✅ Supports: Flipkart, Amazon, Croma, Reliance Digital, Jiomart, Vivo, iQOO, OPPO
- ✅ Docker deployment with auto-restart

## Setup

### 1. Configure Environment

```bash
# Copy the example env file
cp .env.example .env

# Edit .env with your credentials
nano .env
```

**Required variables:**
- `DATABASE_URL` - Your PostgreSQL connection string
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
- `TELEGRAM_GROUP_ID` - Your Telegram group/channel ID

### 2. Build and Run

```bash
# Build the Docker image
docker-compose build

# Start the tracker
docker-compose up -d

# View logs
docker-compose logs -f tracker
```

### 3. Stop the Tracker

```bash
docker-compose down
```

## Configuration

### Check Interval

By default, the tracker checks every 5 minutes (300 seconds). Adjust in `.env`:

```env
CHECK_INTERVAL_SECONDS=300
```

### Pincodes

Specify multiple pincodes to check (for stores that support pincode-based delivery):

```env
PINCODES_TO_CHECK=110016,400001,560001
```

### Telegram Topics

If your Telegram group uses topics/threads, specify topic IDs:

```env
FLIPKART_TOPIC_ID=123
AMAZON_TOPIC_ID=456
```

## Deployment Options

### Local Machine

```bash
docker-compose up -d
```

### Server Deployment

1. Copy the `tracker-backend` folder to your server
2. Configure `.env` file
3. Run `docker-compose up -d`

The container will automatically restart if it crashes or if the server reboots.

## Monitoring

```bash
# View live logs
docker-compose logs -f tracker

# Check container status
docker-compose ps

# Restart the tracker
docker-compose restart
```

## Supported Stores

- 🟣 Flipkart (direct API)
- 🟡 Amazon (PAAPI v5 - requires credentials)
- 🟢 Croma
- 🌐 Reliance Digital
- 🛍️ Jiomart
- 📱 iQOO
- 🤳 Vivo
- 🔵 OPPO

## Troubleshooting

**Container keeps restarting:**
```bash
docker-compose logs tracker
```

**Database connection issues:**
- Ensure `DATABASE_URL` is correct
- Check if database is accessible from Docker network

**No alerts being sent:**
- Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_GROUP_ID`
- Check if products exist in database
- Review logs for errors
