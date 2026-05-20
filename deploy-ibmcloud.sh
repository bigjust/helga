#!/bin/bash

# Helga IBM Cloud Deployment Script
# This script helps automate the deployment of Helga to IBM Cloud

set -e

echo "=========================================="
echo "Helga IBM Cloud Deployment Script"
echo "=========================================="
echo ""

# Check if IBM Cloud CLI is installed
if ! command -v ibmcloud &> /dev/null; then
    echo "ERROR: IBM Cloud CLI is not installed."
    echo "Please install it from: https://cloud.ibm.com/docs/cli"
    exit 1
fi

# Check if logged in
if ! ibmcloud target &> /dev/null; then
    echo "You are not logged in to IBM Cloud."
    echo "Please run: ibmcloud login"
    exit 1
fi

# Check if Cloud Foundry is targeted
if ! ibmcloud target --cf &> /dev/null; then
    echo "Cloud Foundry is not targeted."
    echo "Please run: ibmcloud target --cf -r REGION"
    exit 1
fi

echo "Current IBM Cloud target:"
ibmcloud target
echo ""

# Ask if user wants to create MongoDB service
read -p "Do you want to create a MongoDB service? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter MongoDB service name [helga-mongodb]: " MONGO_SERVICE
    MONGO_SERVICE=${MONGO_SERVICE:-helga-mongodb}

    echo "Creating MongoDB service: $MONGO_SERVICE"
    echo "This may take several minutes..."

    # Try to create the service
    if ibmcloud resource service-instance-create "$MONGO_SERVICE" databases-for-mongodb standard us-south; then
        echo "MongoDB service created successfully!"
    else
        echo "Note: Service may already exist or creation failed."
        echo "You can check with: ibmcloud resource service-instances"
    fi
    echo ""
fi

# Ask for IRC configuration
echo "IRC Server Configuration:"
read -p "IRC Server Host [irc.libera.chat]: " IRC_HOST
IRC_HOST=${IRC_HOST:-irc.libera.chat}

read -p "IRC Server Port [6667]: " IRC_PORT
IRC_PORT=${IRC_PORT:-6667}

read -p "Use SSL? (true/false) [false]: " IRC_SSL
IRC_SSL=${IRC_SSL:-false}

read -p "Bot Nickname [helga]: " BOT_NICK
BOT_NICK=${BOT_NICK:-helga}

read -p "Channels to join (comma-separated) [#bots]: " CHANNELS
CHANNELS=${CHANNELS:-#bots}

read -p "Operators (comma-separated, optional): " OPERATORS

echo ""
echo "Configuration Summary:"
echo "  IRC Host: $IRC_HOST"
echo "  IRC Port: $IRC_PORT"
echo "  IRC SSL: $IRC_SSL"
echo "  Bot Nick: $BOT_NICK"
echo "  Channels: $CHANNELS"
echo "  Operators: $OPERATORS"
echo ""

read -p "Proceed with deployment? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

# Update manifest.yml with configuration
echo "Updating manifest.yml with your configuration..."
cat > manifest.yml << EOF
---
applications:
- name: helga-bot
  memory: 512M
  instances: 1
  buildpacks:
    - python_buildpack
  command: helga --settings=/home/vcap/app/ibmcloud_settings.py
  services:
    - ${MONGO_SERVICE:-helga-mongodb}
  env:
    PYTHONUNBUFFERED: true
    HELGA_NICK: $BOT_NICK
    HELGA_LOG_LEVEL: INFO
    HELGA_IRC_HOST: $IRC_HOST
    HELGA_IRC_PORT: $IRC_PORT
    HELGA_IRC_SSL: $IRC_SSL
    HELGA_CHANNELS: "$CHANNELS"
    HELGA_OPERATORS: "$OPERATORS"
  health-check-type: process
  timeout: 180
EOF

echo "manifest.yml updated!"
echo ""

# Deploy
echo "Deploying to IBM Cloud..."
ibmcloud cf push

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "To view logs, run:"
echo "  ibmcloud cf logs helga-bot"
echo ""
echo "To check status, run:"
echo "  ibmcloud cf app helga-bot"
echo ""
echo "To set additional environment variables:"
echo "  ibmcloud cf set-env helga-bot VAR_NAME value"
echo "  ibmcloud cf restage helga-bot"
echo ""

# Made with Bob
