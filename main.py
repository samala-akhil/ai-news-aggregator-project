
import requests
import os
import openai
from dotenv import load_dotenv

# Load API keys from .env file
load_dotenv()
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

# Function to summarize the description using OpenAI GPT
def get_ai_summary(text):
    try:
        # Make a request to the OpenAI API for summarization
        response = openai.Completion.create(
            engine="text-davinci-003",  # Using Davinci model for summarization
            prompt=f"Summarize the following news article:\n\n{text}",
            max_tokens=100,  # Limit to a short summary
            n=1,  # Only one completion
            stop=None,
            temperature=0.5
        )
        # Return the AI's summary
        return response.choices[0].text.strip()
    except Exception as e:
        return f"Error summarizing: {e}"

# Request URL for top headlines
url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={NEWS_API_KEY}"
response = requests.get(url)

# Check if the request was successful
if response.status_code == 200:
    data = response.json()  # Get the JSON response
    
    for article in data["articles"][:5]:
        title = article.get("title")
        description = article.get("description")
        url = article.get("url")

        # Print the title and URL
        print("Title:", title)
        print("URL:", url)

        # If description exists, use OpenAI to summarize it
        if description:
            print("Description:", description)
            summary = get_ai_summary(description)
            print("AI Summary:", summary)
        print("-" * 40)
else:
    print("Error fetching data from News API")
    print("Response Code:", response.status_code)