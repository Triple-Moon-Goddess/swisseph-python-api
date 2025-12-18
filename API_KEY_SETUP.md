# API Key Setup Instructions

Your API is now protected with API key authentication! Follow these steps to set it up:

## Step 1: Generate a Secure API Key

Generate a random, secure API key. You can use this command:
```bash
openssl rand -hex 32
```

Or generate one online at: https://www.uuidgenerator.net/

Example key: `a7f3e9d2c8b6f1a4e5d7c2b9f8e3a6d1c5b7f2e9a4d8c3f6b1e7a2d5c9f4e8b3`

## Step 2: Set Environment Variable in Railway

1. Go to your Railway dashboard: https://railway.app
2. Select your `swisseph-python-api` project
3. Click on your service
4. Go to the **Variables** tab
5. Click **New Variable**
6. Add:
   - **Variable Name**: `API_KEY`
   - **Value**: Your generated API key (paste it here)
7. Click **Add**
8. Railway will automatically redeploy with the new environment variable

## Step 3: Update Your Google Apps Scripts

### For NatalCharts_SelfHosted.gs:
Replace this line:
```javascript
API_KEY: 'your-secret-key-here',
```

With your actual API key:
```javascript
API_KEY: 'a7f3e9d2c8b6f1a4e5d7c2b9f8e3a6d1c5b7f2e9a4d8c3f6b1e7a2d5c9f4e8b3',
```

### For Transits_SelfHosted_Updated.gs:
Replace this line:
```javascript
API_KEY: 'your-secret-key-here',
```

With your actual API key:
```javascript
API_KEY: 'a7f3e9d2c8b6f1a4e5d7c2b9f8e3a6d1c5b7f2e9a4d8c3f6b1e7a2d5c9f4e8b3',
```

## Step 4: Test the Connection

In Google Sheets, run:
- `Test API Connection` from the menu
- `Test Transit API Connection` from the menu

You should see "API Connected!" if everything is set up correctly.

## Security Notes

✅ **DO:**
- Keep your API key secret
- Don't share it publicly
- Don't commit it to public repositories
- Use different keys for different environments (dev/prod)

❌ **DON'T:**
- Post your API key in public forums
- Share your Google Sheets with the API key visible
- Use simple or guessable keys

## What's Protected

All data endpoints now require the API key:
- `/api/planets` - Get planetary positions
- `/api/houses` - Get house cusps
- `/api/chart` - Get complete chart
- `/api/transits` - Calculate transits

The root endpoint `/` remains public for health checks.

## Troubleshooting

**Error: "API key is missing"**
- Make sure you added the `X-API-Key` header in your scripts
- Check that `TRANSIT_CONFIG.API_KEY` or `CONFIG.API_KEY` is set

**Error: "Invalid API key"**
- The key in your script doesn't match the Railway environment variable
- Check for typos or extra spaces

**Error: "API Connection Failed"**
- Railway might still be deploying (wait 2-3 minutes)
- Check Railway logs for errors
- Verify the API_KEY environment variable is set
