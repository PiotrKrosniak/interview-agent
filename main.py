import flet as ft
import pyaudio
import wave
import audioop
from queue import Queue, Empty  # Import Queue and Empty
from threading import Thread, Event
from time import sleep
import logging  
import time  
import os
from openai import OpenAI
import traceback  
import json
from about import about_page
from cvupload import cvupload_page

import asyncio

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CONFIG_FILE = "config.json"

def save_api_key(api_key):
    config = {"OPENAI_API_KEY": api_key}
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def load_api_key():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get("OPENAI_API_KEY", "")
        except (json.JSONDecodeError, IOError):
            return ""
    return ""

OPENAI_API_KEY = load_api_key()
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Audio settings
CHUNK = 4096 
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

# Global variables
audio_queue = Queue()
is_recording = False
p = pyaudio.PyAudio()
stop_event = Event()  # Event to signal stopping the recording thread

# Global list to store transcriptions
transcriptions = []

def start_recording():
    global is_recording
    try:
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)
        is_recording = True
        logger.info("Audio stream opened successfully")
        return stream
    except Exception as e:
        logger.error(f"Error opening audio stream: {str(e)}")
        return None

def stop_recording(stream):
    global is_recording
    if stream is not None and is_recording:
        try:
            stream.stop_stream()
            stream.close()
            logger.info("Audio stream closed successfully")
        except Exception as e:
            logger.error(f"Error closing audio stream: {str(e)}")
    is_recording = False

def get_audio_data():
    audio_data = b''
    while not audio_queue.empty():
        audio_data += audio_queue.get()
    return audio_data

def main(page: ft.Page):
    global stream, is_recording, OPENAI_API_KEY, client, run_record_thread
    stream = None
    is_recording = False
    run_record_thread = False
    
    # Load the API key from the configuration file
    OPENAI_API_KEY = load_api_key()
    client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

    # Settings and constants.
    max_energy = 5000
    currently_transcribing = False
    record_thread = None
    data_queue = Queue()

    def show_splash(page):
        splash = ft.Container(
            content=ft.ProgressRing(),
            alignment=ft.alignment.center
        )
        page.overlay.append(splash)
        page.update()

    def hide_splash(page):
        page.overlay.clear()
        page.update()

    CHUNK_DURATION = 10 # Duration in seconds for each chunk
    CHUNK_SAMPLES = CHUNK_DURATION * RATE

    transcription_queue = Queue()

    def update_transcription_loop():
        while True:
            try:
                transcription = transcription_queue.get(block=False)
                text_control = ft.Text(
                    transcription, 
                    selectable=True, 
                    size=24,
                    bgcolor=ft.colors.BLACK if text_background_checkbox.value else None
                )
                transcription_list.controls.append(text_control)
                transcription_list.update()
                
                # Append transcription to the global list
                transcriptions.append(transcription)
            except Empty:
                pass
            sleep(0.1)

    def save_transcriptions_to_file():
        if transcriptions:
            # Create a filename with the current date and time
            filename = f"transcriptions_{time.strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, 'w') as f:
                for transcription in transcriptions:
                    f.write(transcription + "\n")
            logger.info(f"Transcriptions saved to {filename}")

    def transcribe_callback(e):
        nonlocal currently_transcribing, record_thread
        global stream, is_recording, OPENAI_API_KEY, client, run_record_thread, stop_event

        if not api_key_input.value or not api_key_input.value.startswith("sk"):
            api_key_input.error_text = "Invalid API key. Must start with 'sk'"
            api_key_input.update()
            return

        OPENAI_API_KEY = api_key_input.value
        client = OpenAI(api_key=OPENAI_API_KEY)

        # Save the API key to the configuration file
        save_api_key(OPENAI_API_KEY)

        try:
            if not currently_transcribing:
                logger.info("Starting transcription")
                show_splash(page)

                device_index = int(microphone_dropdown.value)
                logger.info(f"Selected device index: {device_index}")
                if not record_thread:
                    logger.info(f"Opening audio stream with device index: {device_index}")
                    stream = start_recording()
                    if stream is not None:
                        stop_event.clear()  # Clear the stop event
                        run_record_thread = True
                        record_thread = Thread(target=recording_thread, args=(stream,))
                        record_thread.start()
                        logger.info("Recording thread started")

                        # Start API thread
                        api_thread_instance = Thread(target=api_thread, daemon=True)
                        api_thread_instance.start()
                        logger.info("API thread started")

                        # Start transcription update loop in a separate thread
                        transcription_update_thread = Thread(target=update_transcription_loop, daemon=True)
                        transcription_update_thread.start()
                    else:
                        logger.error("Failed to start recording. Audio stream could not be opened.")
                        hide_splash(page)
                        return

                transcribe_text.value = "Stop Transcribing"
                transcribe_icon.name = "stop_rounded"
                transcribe_button.bgcolor = ft.colors.RED_800

                # Disable all the controls
                for control in [api_key_input, microphone_dropdown]:
                    control.disabled = True
                settings_controls.visible = False

                # Transparency Logic: If transparent is checked, make the window transparent
                if transparent_checkbox.value:
                    page.window.bgcolor = ft.colors.TRANSPARENT
                    page.bgcolor = ft.colors.TRANSPARENT
                    page.window.title_bar_hidden = True
                    page.window.frameless = True
                    draggable_area1.visible = True
                    draggable_area2.visible = True
                    navigation_container.visible = False  # Hide the navigation container
                else:
                    navigation_container.visible = True  # Show the navigation container

                currently_transcribing = True
            else:
                logger.info("Stopping transcription")
                show_splash(page)

                # Stop the record thread
                if record_thread:
                    logger.info("Stopping recording thread")
                    stop_event.set()  # Signal the recording thread to stop
                    run_record_thread = False
                    is_recording = False
                    record_thread.join()
                    record_thread = None
                    logger.info("Recording thread stopped")

                # Close the stream properly
                if stream:
                    stream.close()
                    stream = None

                transcribe_text.value = "Start Transcribing"
                transcribe_icon.name = "play_arrow_rounded"
                transcribe_button.bgcolor = ft.colors.BLUE_800
                volume_bar.value = 0.01

                # Enable controls
                for control in [api_key_input, microphone_dropdown]:
                    control.disabled = False
                settings_controls.visible = True

                # Make window opaque again
                page.window.bgcolor = None
                page.bgcolor = None
                page.window.title_bar_hidden = False
                page.window.frameless = False
                draggable_area1.visible = False
                draggable_area2.visible = False
                navigation_container.visible = True  # Show the navigation container

                currently_transcribing = False

                # Save transcriptions to file
                save_transcriptions_to_file()

            hide_splash(page)
            logger.info("Transcription status changed")
        except Exception as e:
            logger.error(f"Error in transcribe_callback: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            hide_splash(page)

    def navigation_rail_change(e):
            selected_index = e.control.selected_index
            if selected_index == 1:
                load_cv_page()
            elif selected_index == 2:
                load_about_page()
            else:
                load_main_page()

    def load_main_page():
        # Set the content for the main container
        main_content_container.content = ft.Column([
            settings_controls,
            draggable_area1,
            ft.Container(
                content=transcribe_button,
                padding=ft.padding.only(left=10, right=45, top=5)
            ),
            ft.Container(
                content=volume_bar,
                padding=ft.padding.only(left=10, right=45, top=0)
            ),
            draggable_area2,
            ft.Container(
                content=tabs,
                padding=ft.padding.only(left=15, right=45, top=5),
                expand=True,
            ),
        ])

        # Clear controls and rebuild the layout with the navigation rail
        page.controls.clear()

        page.add(
            ft.Row(
                [
                    navigation_container,  # Keep the navigation rail
                    ft.VerticalDivider(width=1),
                    main_content_container  # Add the main content container
                ],
                expand=True,
            )
        )

        # Update the page after the layout has been rebuilt
        page.update()


    def load_cv_page():
        # Set the content for the main container from cvupload_page()
        main_content_container.content = cvupload_page(page)

        # Clear the existing controls on the page
        page.controls.clear()

        # Rebuild the layout, keeping the navigation rail and the updated main content
        page.add(
            ft.Row(
                [
                    navigation_container,  # Keep the navigation rail
                    ft.VerticalDivider(width=1),
                    main_content_container  # Add the main content container
                ],
                expand=True,
            )
        )

        # Update the page to reflect the changes
        page.update()


    

    def load_about_page():
        # Set the content for the main_content_container from about_page()
        main_content_container.content = about_page(page)

        # Clear the controls and rebuild the layout, keeping the navigation rail intact
        page.controls.clear()  # Clear the controls on the page

        page.add(
            ft.Row(
                [
                    navigation_container,  # Keep the navigation rail
                    ft.VerticalDivider(width=1),
                    main_content_container  # Add the updated main content container
                ],
                expand=True,
            )
        )

        # Update the page to reflect the changes
        page.update()

    
    
    # Navigation rail creation
    def create_navigation_rail(expanded):
        return ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL if expanded else ft.NavigationRailLabelType.NONE,
            min_width=100,
            min_extended_width=200,
            extended=expanded,
            group_alignment=-0.9,
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.icons.FAVORITE_BORDER, selected_icon=ft.icons.FAVORITE, label="Home"
                ),
                ft.NavigationRailDestination(
                    icon_content=ft.Icon(ft.icons.BOOKMARK_BORDER),
                    selected_icon_content=ft.Icon(ft.icons.BOOKMARK),
                    label="Your CV",
                ),
                ft.NavigationRailDestination(
                    icon=ft.icons.INFO_OUTLINED,
                    selected_icon_content=ft.Icon(ft.icons.INFO),
                    label_content=ft.Text("About"),
                ),
            ],
            on_change=navigation_rail_change,
        )

    def recording_thread(stream):
        logger.info("Recording thread started")
        nonlocal max_energy
        sample_count = 0
        chunk_buffer = b''
        chunk_start_time = time.time()

        try:
            while not stop_event.is_set() and is_recording:
                try:
                    data = stream.read(CHUNK)
                    chunk_buffer += data
                    sample_count += len(data) // 2  # Assuming 16-bit audio

                    energy = audioop.rms(data, p.get_sample_size(FORMAT))
                    max_energy = max(max_energy, energy)
                    energy_slider.max = max_energy
                    volume_bar.value = min(energy / max_energy, 1.0)
                    volume_bar.color = ft.colors.RED_800 if energy < energy_slider.value else ft.colors.BLUE_800
                    page.update()

                    if sample_count >= CHUNK_SAMPLES:
                        chunk_duration = time.time() - chunk_start_time
                        logger.info(f"Chunk duration: {chunk_duration:.2f} seconds")
                        
                        # Create a WAV file on disk
                        filename = f"chunk_{int(time.time())}.wav"
                        with wave.open(filename, 'wb') as wav:
                            wav.setnchannels(CHANNELS)
                            wav.setsampwidth(p.get_sample_size(FORMAT))
                            wav.setframerate(RATE)
                            wav.writeframes(chunk_buffer)

                        # Put the filename into the queue
                        logger.info(f"Putting chunk of {CHUNK_DURATION} seconds into queue")
                        audio_queue.put(filename)

                        # Reset for next chunk
                        chunk_buffer = b''
                        sample_count = 0
                        chunk_start_time = time.time()
                except IOError as e:
                    if e.errno == pyaudio.paInputOverflowed:
                        logger.warning("Audio input overflowed, dropping data")
                        sleep(0.1)  # Introduce a short delay to let the system recover
                        stream.read(stream.get_read_available())  # Clear buffer
                    else:
                        logger.error(f"IOError in recording thread: {str(e)}")
                        break
        except Exception as e:
            logger.error(f"Error in recording thread: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            logger.info(f"Recording thread stopped. Total samples processed: {sample_count}")
            stop_recording(stream)

    def read_file_content(file_path):
        try:
            with open(file_path, 'r') as file:
                return file.read().strip()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return ""

    def detect_question(text):
        # Simple heuristic to detect questions
        return "?" in text or any(q in text.lower() for q in ["what", "how", "why", "who", "which", "when"])

    async def process_transcription_chunk(chunk, cv, position):
        prompt = f"""
        Here is the transcribed conversation: {chunk}
        The user is applying for the position: {position}.
        Their CV is as follows: {cv}.
        Based on the conversation, detect any questions asked and provide answers using the CV and job position.
        Only return the questions and the answers.
        """

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a Interview questions answering assistant."},
                    {"role": "user", "content": prompt}
                ]
            )
            result = response.choices[0].message.content
            return result

        except Exception as e:
            logger.error(f"Error in GPT request: {e}")
            return None

    def api_thread():
        logger.info("API thread started")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Read CV and position from text files
        cv = read_file_content("uploaded_cv_text.txt")
        position = read_file_content("position_name.txt")
        
        while not stop_event.is_set():
            try:
                filename = audio_queue.get(timeout=1)  # Wait for a chunk to be available
                transcription = send_audio_to_api(filename)
                if transcription:
                    logger.info(f"Received transcription: {transcription}")
                    transcription_queue.put(transcription)
                    
                    # Detect questions and process transcription chunk
                    if detect_question(transcription):
                        answer = loop.run_until_complete(process_transcription_chunk(transcription, cv, position))
                        if answer:
                            answer_control = ft.Text(
                                answer, 
                                selectable=True, 
                                size=24,
                                bgcolor=ft.colors.BLACK if text_background_checkbox.value else None
                            )
                            answers_list.controls.append(answer_control)
                            answers_list.update()
                
                audio_queue.task_done()
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error in API thread: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
        logger.info("API thread stopped")

    def send_audio_to_api(filename):
        logger.info("Sending audio data to OpenAI API")
        try:
            # Open the local WAV file in binary mode
            with open(filename, 'rb') as audio_file:
                # Send the file to OpenAI's API
                transcript = client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file,
                    response_format="text"
                )
                
                logger.info(f"API request successful. Transcript: {transcript}")
                return transcript
        except Exception as e:
            logger.error(f"API request failed: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return f"Transcription failed. Error: {str(e)}"
        finally:
            # Clean up the file after sending to the API
            if os.path.exists(filename):
                os.remove(filename)

    pa = pyaudio.PyAudio()
    microphones = {
        i: pa.get_device_info_by_index(i)['name']
        for i in range(pa.get_device_count())
        if pa.get_device_info_by_index(i)['maxInputChannels'] > 0
    }

    selected_mic = 0

    microphone_dropdown = ft.Dropdown(
        options=[ft.dropdown.Option(index, text=mic) for index, mic in microphones.items()],
        label="Audio Input Device",
        value=selected_mic,
        expand=True,
    )

    def always_on_top_callback(e):
            page.window.always_on_top = always_on_top_checkbox.value
            page.update()
    text_background_checkbox = ft.Checkbox(label="Text Background", value=False)
    always_on_top_checkbox = ft.Checkbox(
        label="Always On Top", 
        value=False,
        on_change=always_on_top_callback
    )
    transparent_checkbox = ft.Checkbox(label="Transparent", value=False)

    energy_slider = ft.Slider(min=0, max=max_energy, value=300, expand=True, height=20)
    volume_bar = ft.ProgressBar(value=0.01, color=ft.colors.RED_800)

    transcription_list = ft.ListView([], spacing=10, padding=20, expand=True, auto_scroll=True)
    answers_list = ft.ListView([], spacing=10, padding=20, expand=True, auto_scroll=True)

    tabs = ft.Tabs(
        tabs=[
            ft.Tab(text="Transcriptions", content=transcription_list),
            ft.Tab(text="Answers", content=answers_list)
        ],
        expand=True
    )

    transcribe_text = ft.Text("Start Transcribing")
    transcribe_icon = ft.Icon("play_arrow_rounded")

    transcribe_button = ft.ElevatedButton(
        content=ft.Row(
            [transcribe_icon, transcribe_text],
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=5
        ),
        bgcolor=ft.colors.BLUE_800, color=ft.colors.WHITE,
        on_click=transcribe_callback,
    )

    api_key_input = ft.TextField(
        label="OpenAI API Key",
        password=True,
        can_reveal_password=True,
        expand=True,
        hint_text="Enter your OpenAI API key (starts with 'sk')",
        value=OPENAI_API_KEY  # Set the initial value to the loaded API key
    )

    def validate_api_key(e):
        if not api_key_input.value or not api_key_input.value.startswith("sk"):
            api_key_input.error_text = "Invalid API key. Must start with 'sk'"
        else:
            api_key_input.error_text = None
        api_key_input.update()

    api_key_input.on_blur = validate_api_key


    settings_controls = ft.Column(
        [
            ft.Container(
                content=ft.Row(
                    [
                        api_key_input,
                        ft.Icon("help_outline", tooltip="Enter your OpenAI API key")
                    ],
                    spacing=10,
                ),
                padding=ft.padding.only(left=10, right=10, top=15),
            ),
            ft.Container(
                content=ft.Row(
                    [
                        microphone_dropdown,
                        ft.Icon("help_outline", tooltip="Select your audio input device")
                    ],
                    spacing=10,
                ),
                padding=ft.padding.only(left=10, right=10, top=5),
            ),
            ft.Container(
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                text_background_checkbox,
                              
                            ]
                        ),
                        ft.Container(
                            content=ft.Column(
                                [
                                 transparent_checkbox,
                                
                                ],
                            ),
                            padding=ft.padding.only(left=10)
                        ),
                        ft.Column(
                            [
                                
                                always_on_top_checkbox,
                            ]
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                margin=ft.margin.only(left=10, right=15, top=5),
            ),
            ft.Container(
                content=ft.Row(
                    [
                        energy_slider,
                        ft.Icon("help_outline", tooltip="Required volume to start decoding speech.")
                    ],
                    expand=True,
                ),
                padding=ft.padding.only(left=0, right=15, top=0),
            ),
        ],
        visible=True
    )

    draggable_area1 = ft.Row(
        [
            ft.WindowDragArea(ft.Container(height=30), expand=True),
        ],
        visible=False
    )
    draggable_area2 = ft.Row(
        [
            ft.WindowDragArea(ft.Container(height=30), expand=True),
        ],
        visible=False
    )
    # Toggle Navigation Rail
    navigation_rail_expanded = False

    def toggle_navigation_rail(e):
        nonlocal navigation_rail_expanded
        navigation_rail_expanded = not navigation_rail_expanded
        navigation_rail.extended = navigation_rail_expanded
        navigation_rail.label_type = ft.NavigationRailLabelType.ALL if navigation_rail_expanded else ft.NavigationRailLabelType.NONE
        navigation_container.width = 200 if navigation_rail_expanded else 60
        page.update()

    # Create navigation rail
    navigation_rail = create_navigation_rail(navigation_rail_expanded)

    toggle_button = ft.IconButton(
        icon=ft.icons.MENU,
        on_click=toggle_navigation_rail
    )

    navigation_container = ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=toggle_button,
                    padding=ft.padding.only(left=10)
                ),
                ft.Container(
                    content=navigation_rail,
                    height=600,
                )
            ],
            expand=True,
        ),
        width=200 if navigation_rail_expanded else 60,
        height=600,
        visible=True  # Ensure it is initially visible
    )

    # Create main content container
    main_content_container = ft.Container(expand=True)

    # Initial page setup
    page.add(
        ft.Row(
            [
                navigation_container,
                ft.VerticalDivider(width=1),
                main_content_container
            ],
            expand=True,
        )
    )

    # Load the default page (main page)
    load_main_page()

    def on_exit(e):
        save_transcriptions_to_file()
        logger.info("Application closed")
        page.window.close()

    page.window.on_close = on_exit

if __name__ == "__main__":
    logger.info("Starting application")
    ft.app(target=main)
    logger.info("Application closed")