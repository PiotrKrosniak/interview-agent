# Interview - Agent 

A interview agent build with Flet and OpenAI Whisper.
[![YouTube](http://i.ytimg.com/vi/Cv_0TmJ9lv0/hqdefault.jpg)](https://www.youtube.com/watch?v=Cv_0TmJ9lv0)
<iframe width="560" height="315" src="https://www.youtube.com/embed/Cv_0TmJ9lv0?si=i_in2TEIsakqXS89" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>



This application is designed to transcribe audio input in real-time, detect questions within the transcriptions, and provide answers based on the user's CV and the job position they are applying for. The application leverages OpenAI's GPT-4o-mini model for generating responses and Whisper API for transcriptions.

## Main Functionalities
1. Real-Time Audio Transcription
Audio Input Selection: Users can select their preferred audio input device from a dropdown menu.
Energy Threshold Adjustment: An energy slider allows users to set the minimum energy level required to start decoding speech, helping to filter out background noise.
Volume Bar: A visual representation of the current audio input energy level, which changes color based on the set threshold.
2. Question Detection and Answering
Question Detection: The application uses heuristic to detect questions within the transcribed text.
Answer Generation: When a question is detected, the application sends the transcription chunk, along with the user's CV and job position, to OpenAI's GPT-4o-mini model to generate answers.
Answer Display: Answers are displayed in a dedicated "Answers" tab, with optional background color based on user preference.
3. User Interface
Tabs for Transcriptions and Answers: The application features two main tabs:
Transcriptions: Displays the transcribed text returned by the Whisper API.
Answers: Displays the answers to detected questions.
Text Background Option: Users can toggle a checkbox to enable or disable background color for the transcribed text and answers.
Always on Top: An option to keep the application window always on top of other windows.
4. File-Based Configuration
CV and Position Loading: The application reads the user's CV and job position from text files (uploaded_cv_text.txt and position_name.txt), ensuring that the latest information is used for generating answers.
5. Asynchronous Processing
Non-Blocking Transcription: The application processes transcription chunks and generates answers on separate threads to ensure smooth and uninterrupted transcription.

## Setting Up An Environment
On Windows:
```
cd transcriber_app
py -3.9 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
flet run main.py
```
On Unix:
```
git clone https://github.com/PiotrKrosniak/interview-agent.git
cd transcriber_app
python3.9 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flet run main.py
```

You also need to setup audio device using BlackHole https://existential.audio/blackhole/support/

## Usage
* Upload Your CV and add Position you are applying too. 
* Select an input source using the dropdown.
* Click "Start Transcribing"

You need to specify the device to which Agent will listen to for example if you have interview overt MS Teams select it as audio source so ONLY the questions asked by the Panel will be answered. 

Application require Open AI API that you can get from their website here https://platform.openai.com/api-keys

**Application only answers questions and ignore all other not relevant discussions.**

You can also make the window transparent and set the text background, this is useful for overlaying on other apps. 



Read more about Whisper here: https://github.com/openai/whisper

Read more about Flet here: https://flet.dev/

Inspiration and parts of the code are implemented based on https://github.com/davabase/transcriber_app

Free for personal None-commercial use. 
[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

