import os
import tweepy
import openai
import schedule
import datetime
import time
import re
import random
import google.oauth2.credentials
import elevenlabslib
import io
import librosa
import pydub
import glob
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from moviepy.editor import *
from moviepy.audio.AudioClip import AudioArrayClip

YT_FILE = "yt.json"

YT_SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
YT_API_SERVICE_NAME = "youtube"
YT_API_VERSION = "v3"

TWEET_CONTEXT = ("You are going to pretend to be a Twitter user called AI Warcraft. AI Warcraft is a World of Warcraft player with strong opinions on the game. AI Warcraft's style of tweeting is to quote retweet some WoW news, and give its opinion on the news in the form a short tweet, in a comedic and over-the-top fashion."
           "AI Warcraft always has a contrary opinion to whatever it is quote retweeting, lambasting the news and expressing disappointment. AI Warcraft hates everything. It will often give opinions in a dramatic, exaggerated, and inflammatory fashion, but never engages in an offensive way - all tweets are written in a way that can be understood to be in good fun."
           "AI Warcraft writes tweets in the style you would expect from a World of Warcraft player on Twitter - in a casual way, with hashtags, slang, and emojis. When acting as AI Warcraft, you must not repeat what the original tweet says: you must add a unique perspective. Additionally, your tweets must be varied in their structure. Do not repeat the same formula for each quote retweet."
           "The only exception to AI Warcraft's contrarian nature is when dealing with topics surrounding worker's rights and controversial issues at Blizzard Entertainment. AI Warcraft always supports the workers at Blizzard, and directs all of its anger at the corporate executives and the systems that work against the workers."
           "When I show you a tweet, you will act as AI Warcraft and write the contents of the corresponding quote retweet. You must write only the body of the tweet. Tweets must always remain within Twitter's 280-character limit. You must not enclose the tweet body in quotes. Every tweet must include #Warcraft.")

VIDEO_CONTEXT = ("You are the writer for the AI Warcraft Bi-Weekly News Roundup, a YouTube news should about World of Warcraft hosted by Joe Biden, Barack Obama, and Donald Trump. In each video, the three break down the latest WoW news, but always end up in heated arguments. They are all friends, but their arguments involve extreme banter and insulting humour, often mocking their opponents' political views, actions as President, or other traits."
            "Their arguments should include a good amount of modern internet slang that wouldn't typically be expected from US presidents. Obama is usually the mediator in the arguments."
            "When I give you a prompt for a video, you will write the script. The script should contain exclusively dialogue. Each line should consist of the speaker's name, followed by a colon and a space, followed by their dialogue. The entire script must be less than 3000 characters long."
            "The first line of the script should be the video title, formatted as: 'Title: <short, catchy title goes here> | AI Warcraft Bi-Weekly News Roundup'."
            "The second line of the script should be a short video description, formatted as: 'Description: <short video description goes here>'.")

MS_DELAY = 600
INCLUDE_BACKGROUND_FOOTAGE = True

test_mode = os.environ.get("TEST_MODE", "False").lower() == "true"

# Twitter API credentials
bearer_token = os.environ["TWITTER_BEARER_TOKEN"]
consumer_key = os.environ["TWITTER_CONSUMER_KEY"]
consumer_secret = os.environ["TWITTER_CONSUMER_SECRET"]
access_token = os.environ["TWITTER_ACCESS_TOKEN"]
access_token_secret = os.environ["TWITTER_ACCESS_TOKEN_SECRET"]

# OpenAI API key
openai.api_key = os.environ["OPENAI_API_KEY"]

# ElevenLabs API key
elevenlabs_api_key = os.environ["ELEVENLABS_API_KEY"]

# Set up Tweepy with Twitter credentials
client = tweepy.Client(bearer_token, consumer_key, consumer_secret, access_token, access_token_secret)

# Add global variables to store the last retweeted tweet ID and news episode #
last_retweeted_tweet_id = None
last_news_episode_num = None

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
    global last_retweeted_tweet_id

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
        write_txt_num("last_retweeted_tweet_id.txt", last_retweeted_tweet_id)

    elif tweet_id == last_retweeted_tweet_id:
        # print("Skipping retweet as the latest tweet has already been quote retweeted")
        pass
    else:
        print("No recent tweet found from @Wowhead")

def generate_ai_warcraft_tweet(prompt):
    messages = [
        {"role": "system", "content": TWEET_CONTEXT},
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

def write_txt_num(filename, num):
    with open(filename, "w") as file:
        file.write(str(num))

def read_txt_num(filename):
    try:
        with open(filename, "r") as file:
            return int(file.read())
    except FileNotFoundError:
        return None

def generate_script(topics):
    prompt = "Write a video covering the following news topics:"
    for t in topics:
        prompt += f"\n - {t}"
    prompt += "\n\nThe entire script must be less than 3000 characters long."

    response = openai.ChatCompletion.create(
      model="gpt-3.5-turbo",
      messages=[
            {"role": "user", "content": VIDEO_CONTEXT},
            {"role": "user", "content": f"{prompt}"}
        ]
    )
    return response["choices"][0]["message"]["content"].split("\n")

def clean_script(script):
    global last_news_episode_num

    allowed_speakers = [["Obama", ["Barack: ", "Obama: ", "Barack Obama: "]],
                        ["Biden", ["Joe: ", "Biden: ", "Joe Biden: "]],
                        ["Trump", ["Donald: ", "Trump: ", "Donald Trump: "]]]

    script_ = []
    title = script[0][7:].strip() + f" #{last_news_episode_num + 1}"
    description = script[1][13:].strip()
    for line in script[2:]:
        for speaker in allowed_speakers:
            for header in speaker[1]:
                if line.startswith(header) or line.startswith(header.upper()) or line.startswith(header.lower()):
                    line_ = line.strip().replace(header, "")
                    if line_[0] == '"':
                        line_ = line_[1:]
                    if line_[-1] == '"':
                        line_ = line_[:-1]
                    line_ = "".join(re.split("\(|\) |\)", line_)[::2])
                    if re.search("[a-zA-Z]", line_) is not None:
                        script_.append([speaker[0], line_])
                    break

    return title, description, script_

def generate_recordings(script, save=False):
    user = elevenlabslib.ElevenLabsUser(ELEVENLABS_API_KEY)

    recordings = []
    for i, line in enumerate(script):
        voice = user.get_voices_by_name(line[0])[0]
        audio = voice.generate_audio_bytes(line[1])

        memory_file = io.BytesIO()
        elevenlabslib.helpers.save_bytes_to_file_object(memory_file, audio, "wav")
        recordings.append((memory_file, line[0].lower()))

        if save == True:
            num = str(i)
            while len(num) < 3:
                num = "0" + num
            elevenlabslib.helpers.save_bytes_to_path(f"audio_out/{num}_{line[0].lower()}.wav", audio)

    return recordings

def generate_video(recordings):
    dir = "audio_out"

    if INCLUDE_BACKGROUND_FOOTAGE:
        bg_vids = [os.path.join("video_in", f) for f in os.listdir("video_in") if os.path.isfile(os.path.join("video_in", f))]
        bg_vid_file = random.choice(bg_vids)
        bg_vid = VideoFileClip(bg_vid_file)

        speakers = ["obama", "biden", "trump"]
        bg_vid_start_times = []
        for i in range(3):
            bg_vid_start_times.append(random.randint(i*int((bg_vid.duration-120)/3)+2, (i+1)*int((bg_vid.duration-120)/3)))

        random.shuffle(bg_vid_start_times)
        cumulative_duration = 0

    clips = []
    merged_audio = pydub.AudioSegment.empty()
    for recording in recordings:
        avatar_img = f"img/{recording[1]}.jpg"

        audio_segment = pydub.AudioSegment.from_wav(recording[0])
        merged_audio += audio_segment
        merged_audio += pydub.AudioSegment.silent(duration=MS_DELAY)

        duration = audio_segment.duration_seconds + MS_DELAY / 1000
        avatar_img_clip = ImageClip(avatar_img).resize(width=480).set_duration(duration)

        if INCLUDE_BACKGROUND_FOOTAGE:
            start = bg_vid_start_times[speakers.index(recording[1])] + cumulative_duration
            bg_clip = bg_vid.subclip(start, start + duration)
            clip = CompositeVideoClip([bg_clip, avatar_img_clip])
            clips.append(clip)
            cumulative_duration += duration
        else:
            clips.append(avatar_img_clip)

    concat_clip = concatenate_videoclips(clips, method="compose")
    merged_audio.export("temp/audio_temp.wav", format="wav")
    concat_clip = concat_clip.set_audio(AudioFileClip("temp/audio_temp.wav"))

    concat_clip.write_videofile("video_out/video.mp4", threads=8, fps=24)
    os.remove("temp/audio_temp.wav")

def merge_saved_recordings():
    dir = "audio_out"
    out = pydub.AudioSegment.empty()
    for filename in sorted(os.listdir(dir)):
        f = os.path.join(dir, filename)
        if os.path.isfile(f):
            out += pydub.AudioSegment.from_wav(f)
            out += pydub.AudioSegment.silent(duration=MS_DELAY)

    out.export("audio_out/audio.wav", format="wav")

def yt_get_authenticated_service():
    flow = InstalledAppFlow.from_client_secrets_file(YT_FILE, YT_SCOPES)
    credentials = flow.run_local_server()
    return build(YT_API_SERVICE_NAME, YT_API_VERSION, credentials=credentials)

def upload_video(title, description):
    youtube = yt_get_authenticated_service()
    video_file = "video_out/video.mp4"
    category_id = "20"  # "Gaming" category
    privacy_status = "public"  # "public", "private" or "unlisted"

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": category_id
        },
        "status": {
            "privacyStatus": privacy_status
        }
    }

    media = MediaFileUpload(video_file, mimetype="video/*", resumable=True)
    request = youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print("Uploaded %d%%" % int(status.progress() * 100))
    print("Upload completed!")

    return "https://www.youtube.com/watch?v=" + str(response['id'])

def get_news_topics(n):
    recent_tweets = client.get_users_tweets("17258481", exclude="retweets", max_results=10)[0] # Uses Wowhead user ID
    topics = []
    i = 0
    while len(topics) < n:
        tweet = recent_tweets[i]
        if ("#warcraft" in tweet.text.lower()) or ("#dragonflight" in tweet.text.lower()):
            text = re.sub(r"http\S+", "", tweet.text).strip()
            text = re.sub(r"#\S+", "", text).strip()
            topics.insert(0, text)
        i += 1
    return topics

def make_video():
    global last_news_episode_num

    for dir in ["audio_out", "video_out"]:
        files = glob.glob(f"{dir}/*")
        for f in files:
            os.remove(f)

    topics = get_news_topics(3)
    title, description, script = clean_script(generate_script(topics))
    print(title)
    print(description)
    print(script)

    recordings = generate_recordings(script)
    print("Finished generating recordings.")
    generate_video(recordings)
    print("Finished generating video.")
    url = upload_video("TEST", "WOW")

    print("Sleeping for 3 mins before tweeting...")
    time.sleep(180)  # Sleep for 3 minutes
    try:
        client.create_tweet(text=f"{title}\n\n#Warcraft\n\n{url}")
        print(f"Posted video tweet for f{title}")
    except tweepy.errors.TweepyException as e:
        print(f"Error while posting tweet: {e}")

    last_news_episode_num += 1
    write_txt_num("last_news_episode_num.txt", last_news_episode_num)

def main():
    schedule.every().monday.at("16:30").do(make_video)
    schedule.every().friday.at("16:30").do(make_video)
    while True:
        post_quote_retweet()
        schedule.run_pending()
        time.sleep(60)  # Sleep for 1 minute

if __name__ == "__main__":
    last_retweeted_tweet_id = read_txt_num("last_retweeted_tweet_id.txt")
    last_news_episode_num = read_txt_num("last_news_episode_num.txt")
    main()
