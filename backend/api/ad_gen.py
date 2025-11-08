# -*- coding: utf-8 -*-
import time
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("VITE_GOOGLE_API_KEY")
if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY is not set. Add it to your environment or .env file."
    )

client = genai.Client(api_key=api_key)
userPrompt = input("Enter Idea: ")
content = userPrompt + """. This is a new brilliant startup idea, this person needs a
                            amazing new ad for the idea and it would be great if you 
                            could generate a 15 second script for their ad to put into 
                            the veo video generator. If a person every talks, make sure
                            to put the text into apostraphies/single quotes sort of like
                            A close up of two people staring at a cryptic drawing on a wall, 
                            torchlight flickering. A man murmurs, 'This must be it. That's 
                            the secret code.' The woman looks at him and whispering excitedly,
                             'What did you find?'"""
#response = client.models.generate_content(
        #model="gemini-2.5-flash",
        #contents=content
#)

#prompt = response.text

operation = client.models.generate_videos(
    model="veo-3.1-generate-preview",
    prompt="Old ladies are arguing over house cats and what color they are. The first lady yells, 'This orange one is mine you dumb old hag!'",
    config={
        "duration_seconds": 8
    }
)

# Poll the operation status until the video is ready.
while not operation.done:
    print("Waiting for video generation to complete...")
    time.sleep(10)
    operation = client.operations.get(operation)

# Download the generated video.
generated_video = operation.response.generated_videos[0]
client.files.download(file=generated_video.video)
generated_video.video.save("dialogue_example.mp4")
print("Generated video saved to dialogue_example.mp4")