#!/bin/bash

echo "=== TestMeDroid GCP Setup ==="
echo

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Please install it first:"
    echo "   brew install google-cloud-sdk"
    exit 1
fi

# Get current account
current_account=$(gcloud config get-value account 2>/dev/null)
if [ -z "$current_account" ]; then
    echo "📋 No Google account found. Let's login:"
    gcloud auth login
else
    echo "✅ Using account: $current_account"
    echo "   (Run 'gcloud auth login' to use a different account)"
fi

# Get or create project
current_project=$(gcloud config get-value project 2>/dev/null)
if [ -z "$current_project" ]; then
    echo
    echo "📋 No project set. Enter your project ID:"
    read -p "Project ID: " project_id
    gcloud config set project "$project_id"
else
    echo "✅ Using project: $current_project"
    project_id=$current_project
fi

# Enable Vertex AI
echo
echo "🔧 Enabling Vertex AI API..."
gcloud services enable aiplatform.googleapis.com

# Update .env file
echo
echo "📝 Updating .env file..."
sed -i.bak "s/YOUR_PROJECT_ID_HERE/$project_id/g" .env

# Test the connection
echo
echo "🧪 Testing Vertex AI connection..."
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
project = os.getenv('VERTEX_AI_PROJECT_ID')
print(f'✅ Project configured: {project}')
"

echo
echo "✨ Setup complete! You can now use:"
echo "   python -m src analyze 'your goal here'"
echo
echo "💡 Tips:"
echo "   - First 90 days are free with \$300 credits"
echo "   - Gemini 1.5 Flash costs ~\$0.00001 per request"
echo "   - Monitor usage at: https://console.cloud.google.com/billing"