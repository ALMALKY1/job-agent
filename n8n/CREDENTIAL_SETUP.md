# Mohamed Job Agent — n8n Credential Setup Guide

## Required Credentials

### 1. Gmail OAuth2

**Where:** n8n UI → Settings (⚙️) → Credentials → Add Credential → Gmail OAuth2

**Steps:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the **Gmail API**:
   - Go to APIs & Services → Library
   - Search "Gmail API" → Enable
4. Create OAuth 2.0 credentials:
   - Go to APIs & Services → Credentials
   - Click "Create Credentials" → "OAuth Client ID"
   - Application type: **Web application**
   - Authorized redirect URIs: `http://localhost:5678/rest/oauth2-credential/callback`
5. Copy the **Client ID** and **Client Secret**
6. In n8n, create the Gmail OAuth2 credential:
   - Paste Client ID and Client Secret
   - Click "Connect my account"
   - Sign in with your Gmail account
   - Grant access

**Gmail Query Used:**
```
from:jobs-noreply@linkedin.com newer_than:1d -subject:"Your application" -subject:"application was sent" -subject:"Problem with your"
```

### 2. OpenAI API Key

**Where:** n8n UI → Settings (⚙️) → Credentials → Add Credential → HTTP Header Auth

**Steps:**
1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create a new API key
3. In n8n, create an HTTP Header Auth credential:
   - **Name:** `OpenAI API Key`
   - **Header Name:** `Authorization`
   - **Header Value:** `Bearer sk-your-actual-key-here`

**Cost estimate:** ~$0.01–0.05 per job analysis with GPT-4o.

### 3. Google Sheets (Optional — for tracker export)

**Where:** n8n UI → Settings (⚙️) → Credentials → Add Credential → Google Sheets OAuth2

**Steps:**
1. Same Google Cloud project as Gmail
2. Enable the **Google Sheets API**
3. Use the same OAuth credentials
4. In n8n, create Google Sheets OAuth2 credential

## Importing the Workflow

1. Open n8n at http://localhost:5678
2. Click the **≡** menu → **Import from File**
3. Select `n8n/workflows/daily_pipeline.json`
4. The workflow will appear with placeholder credentials
5. Click each node that shows ⚠️ and assign the correct credential
6. Click **Save** then **Activate** (toggle in top right)

## Testing

1. In the workflow editor, click **Execute Workflow** (play button)
2. Check each node's output by clicking on it
3. The Parse Emails node should extract jobs from test data
4. The AI Analysis node will fail until OpenAI credentials are set

## Timezone

The workflow schedule and all timestamps use **Africa/Cairo** timezone.
The schedule trigger runs at **8:00 AM Cairo time** daily.
