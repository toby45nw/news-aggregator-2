import os
import discord
from dotenv import load_dotenv

load_dotenv()

# Setup and configure the bot client with default intents (permissions)
intents = discord.Intents.default()
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    await client.close()


# Run the bot using the token from the environment variable
client.run(os.environ["DISCORD_BOT_TOKEN"])