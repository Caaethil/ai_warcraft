import os
import tweepy
import openai
# import schedule
import time
import re
import random

CONTEXT = ("You are going to pretend to be a Twitter user called AI Warcraft. AI Warcraft is a World of Warcraft player with strong opinions on the game. AI Warcraft's style of tweeting is to quote retweet some WoW news, and give its opinion on the news in the form a short tweet, in a comedic and over-the-top fashion."
           "AI Warcraft always has a contrary opinion to whatever it is quote retweeting, lambasting the news and expressing disappointment. AI Warcraft hates everything. It will often give opinions in a dramatic, exaggerated, and inflammatory fashion, but never engages in an offensive way - all tweets are written in a way that can be understood to be in good fun."
           "AI Warcraft writes tweets in the style you would expect from a World of Warcraft player on Twitter - in a casual way, with hashtags, slang, and emojis. When acting as AI Warcraft, you must not repeat what the original tweet says: you must add a unique perspective. Additionally, your tweets must be varied in their structure. Do not repeat the same formula for each quote retweet."
           "The only exception to AI Warcraft's contrarian nature is when dealing with topics surrounding worker's rights and controversial issues at Blizzard Entertainment. AI Warcraft always supports the workers at Blizzard, and directs all of its anger at the corporate executives and the systems that work against the workers."
           "When I show you a tweet, you will act as AI Warcraft and write the contents of the corresponding quote retweet. You must write only the body of the tweet. Tweets must always remain within Twitter's 280-character limit. You must not enclose the tweet body in quotes. Every tweet must include #Warcraft.")

test_mode = os.environ.get("TEST_MODE", "False").lower() == "true"

# Twitter API credentials
bearer_token = os.environ["TWITTER_BEARER_TOKEN"]
consumer_key = os.environ["TWITTER_CONSUMER_KEY"]
consumer_secret = os.environ["TWITTER_CONSUMER_SECRET"]
access_token = os.environ["TWITTER_ACCESS_TOKEN"]
access_token_secret = os.environ["TWITTER_ACCESS_TOKEN_SECRET"]

# OpenAI API key
openai.api_key = os.environ["OPENAI_API_KEY"]

# Set up Tweepy with Twitter credentials
client = tweepy.Client(bearer_token, consumer_key, consumer_secret, access_token, access_token_secret)

# auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
# auth.set_access_token(access_token, access_token_secret)
# api = tweepy.API(auth)

# Add a global variable to store the last retweeted tweet ID
last_retweeted_tweet_id = None

def get_latest_wowhead_tweet():
    recent_tweets = client.get_users_tweets("17258481", exclude="retweets")[0] # Uses Wowhead user ID
    if len(recent_tweets[0]) > 0:
        for i in range(10):
            tweet = recent_tweets[i]
            if ("#warcraft" in tweet.text.lower()) or ("#dragonflight" in tweet.text.lower()):
                text = re.sub(r"http\S+", "", tweet.text).strip()
                return tweet.id, text
    return None, None

def post_quote_retweet():
    global last_retweeted_tweet_id  # Don't forget to add this line

    tweet_id, prompt = get_latest_wowhead_tweet()
    if tweet_id and tweet_id != last_retweeted_tweet_id:
        ai_warcraft_tweet = generate_ai_warcraft_tweet(prompt)

        # Attempt to generate a new tweet if the initial one is too long
        retries = 5
        while len(ai_warcraft_tweet) > 280 and retries > 0:
            ai_warcraft_tweet = generate_ai_warcraft_tweet(prompt)
            retries -= 1

        print(f"Latest @Wowhead tweet: {prompt}")
        if len(ai_warcraft_tweet) <= 280:
            if test_mode:
                print(f"Test mode: Generated tweet for @Wowhead: {ai_warcraft_tweet}")
            else:
                try:
                    client.create_tweet(text=ai_warcraft_tweet, quote_tweet_id=tweet_id)
                    print(f"Quote retweeted @Wowhead: {ai_warcraft_tweet}")
                except tweepy.errors.TweepyException as e:
                    print(f"Error while posting tweet: {e}")

        else:
            print("Generated tweet exceeds 280 characters after 5 attempts")

        last_retweeted_tweet_id = tweet_id
        write_last_retweeted_tweet_id('last_retweeted_tweet_id.txt', last_retweeted_tweet_id)

    elif tweet_id == last_retweeted_tweet_id:
        print("Skipping retweet as the latest tweet has already been quote retweeted")
    else:
        print("No recent tweet found from @Wowhead")

def generate_ai_warcraft_tweet(prompt):
    messages = [
        {"role": "system", "content": CONTEXT},
        {"role": "user", "content": f"@Wowhead: {prompt}"}
    ]

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
        max_tokens=50,
        n=1,
        stop=None,
        temperature=random.randint(70,100)/100,
    )

    return response.choices[0]["message"]["content"].strip()

def write_last_retweeted_tweet_id(filename, tweet_id):
    with open(filename, 'w') as file:
        file.write(str(tweet_id))

def read_last_retweeted_tweet_id(filename):
    try:
        with open(filename, 'r') as file:
            return int(file.read())
    except FileNotFoundError:
        return None

def main():
    # schedule.every().day.at("00:00").do(post_quote_retweet)
    # schedule.every().day.at("06:00").do(post_quote_retweet)
    # schedule.every().day.at("12:00").do(post_quote_retweet)
    # schedule.every().day.at("18:00").do(post_quote_retweet)

    while True:
        # schedule.run_pending()
        post_quote_retweet()
        time.sleep(120)  # Sleep for 2 minutes

if __name__ == "__main__":
    last_retweeted_tweet_id = read_last_retweeted_tweet_id('last_retweeted_tweet_id.txt')
    main()
