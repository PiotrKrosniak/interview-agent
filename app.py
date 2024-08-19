import flet as ft
import pyaudio
import torch
import whisper
import yaml
import wave
import numpy
import io
import os
import audioop
from datetime import datetime, timedelta
from queue import Queue
from threading import Thread
from time import sleep
from whisper.tokenizer import LANGUAGES

def main(page: ft.Page):
    # Settings and constants.
    settings_file = "transcriber_settings.yaml"
    settings = {}

    if os.path.exists(settings_file):
        with open(settings_file, 'r') as f:
            settings = yaml.safe_load(f)

    settings = settings or {}

    transcription_file = "transcription.txt"
    max_energy = 5000
    sample_rate = 16000
    chunk_size = 1024
    max_int16 = 2**15

    # Set window settings.
    page.title = "Transcriber"
    page.window_width = settings.get('window_width', 817)
    page.window_height = settings.get('window_height', 800)

    # Callbacks
    def always_on_top_callback(e):
        page.window_always_on_top = always_on_top_checkbox.value
        page.update()

    def text_background_callback(e):
        bgcolor = ft.colors.BLACK if dark_mode_checkbox.value else ft.colors.WHITE
        for list_item in transcription_list.controls:
            list_item.bgcolor = bgcolor if text_background_checkbox.value else None
        transcription_list.update()

    def dark_mode_callback(e):
        page.theme_mode = ft.ThemeMode.DARK if dark_mode_checkbox.value else ft.ThemeMode.LIGHT
        text_background_callback(e)
        page.update()

    def language_callback(e):
        translate_checkbox.disabled = language_dropdown.value == 'en'
        translate_checkbox.value = not translate_checkbox.disabled
        translate_checkbox.update()

    def text_size_callback(e):
        for list_item in transcription_list.controls:
            list_item.size = int(text_size_dropdown.value)
        transcription_list.update()

    audio_model = None
    loaded_audio_model = None
    currently_transcribing = False
    record_thread = None
    data_queue = Queue()

    def transcribe_callback(e):
        nonlocal currently_transcribing, audio_model, loaded_audio_model, record_thread, run_record_thread

        if not currently_transcribing:
            page.splash = ft.Container(
                content=ft.ProgressRing(),
                alignment=ft.alignment.center
            )
            page.update()

            model = model_dropdown.value
            if model != "large" and language_dropdown.value == 'en':
                model += ".en"

            # Only re-load the audio model if it changed.
            if not audio_model or loaded_audio_model != model:
                device = "cuda" if torch.cuda.is_available() else "cpu"
                audio_model = whisper.load_model(model, device)
                loaded_audio_model = model

            device_index = int(microphone_dropdown.value)
            if not record_thread:
                stream = pa.open(format=pyaudio.paInt16,
                                 channels=1,
                                 rate=sample_rate,
                                 input=True,
                                 frames_per_buffer=chunk_size,
                                 input_device_index=device_index)
                run_record_thread = True
                record_thread = Thread(target=recording_thread, args=[stream])
                record_thread.start()

            transcribe_text.value = "Stop Transcribing"
            transcribe_icon.name = "stop_rounded"
            transcribe_button.bgcolor = ft.colors.RED_800

            # Disable all the controls.
            for control in [model_dropdown, microphone_dropdown, language_dropdown, translate_checkbox]:
                control.disabled = True
            settings_controls.visible = False

            # Make transparent.
            if transparent_checkbox.value:
                page.window_bgcolor = ft.colors.TRANSPARENT
                page.bgcolor = ft.colors.TRANSPARENT
                page.window_title_bar_hidden = True
                page.window_frameless = True
                draggable_area1.visible = True
                draggable_area2.visible = True

            # Save settings.
            settings.update({
                'window_width': page.window_width,
                'window_height': page.window_height,
                'speech_model': model_dropdown.value,
                'microphone_index': microphone_dropdown.value,
                'language': language_dropdown.value,
                'text_size': text_size_dropdown.value,
                'translate': translate_checkbox.value,
                'always_on_top': always_on_top_checkbox.value,
                'dark_mode': dark_mode_checkbox.value,
                'text_background': text_background_checkbox.value,
                'transparent': transparent_checkbox.value,
                'volume_threshold': energy_slider.value,
                'transcribe_rate': transcribe_rate_seconds,
                'max_record_time': max_record_time,
                'seconds_of_silence_between_lines': silence_time,
            })

            with open(settings_file, 'w') as f:
                yaml.dump(settings, f)

            currently_transcribing = True
        else:
            page.splash = ft.Container(
                content=ft.ProgressRing(),
                alignment=ft.alignment.center
            )
            page.update()

            transcribe_text.value = "Start Transcribing"
            transcribe_icon.name = "play_arrow_rounded"
            transcribe_button.bgcolor = ft.colors.BLUE_800
            volume_bar.value = 0.01

            # Stop the record thread.
            if record_thread:
                run_record_thread = False
                record_thread.join()
                record_thread = None

            # Drain remaining data but save the last sample.
            data = None
            while not data_queue.empty():
                data = data_queue.get()
            if data:
                data_queue.put(data)

            # Enable controls.
            for control in [model_dropdown, microphone_dropdown, language_dropdown]:
                control.disabled = False
            translate_checkbox.disabled = language_dropdown.value == 'en'
            settings_controls.visible = True

            # Make opaque.
            page.window_bgcolor = None
            page.bgcolor = None
            page.window_title_bar_hidden = False
            page.window_frameless = False
            draggable_area1.visible = False
            draggable_area2.visible = False

            # Save transcription.
            with open(transcription_file, 'w', encoding='utf-8') as f:
                f.writelines('\n'.join([item.value for item in transcription_list.controls]))

            currently_transcribing = False

        page.splash = None
        page.update()

    # Build controls
    model_dropdown = ft.Dropdown(
        options=[
            ft.dropdown.Option('tiny', text="Tiny (Fastest)"),
            ft.dropdown.Option('base', text="Base"),
            ft.dropdown.Option('small', text="Small"),
            ft.dropdown.Option('medium', text="Medium"),
            ft.dropdown.Option('large', text="Large (Highest Quality)"),
        ],
        label="Speech To Text Model",
        value=settings.get('speech_model', 'base'),
        expand=True,
    )

    pa = pyaudio.PyAudio()
    microphones = {
        i: pa.get_device_info_by_index(i)['name']
        for i in range(pa.get_device_count())
        if pa.get_device_info_by_index(i)['maxInputChannels'] > 0
    }

    selected_mic = int(settings.get('microphone_index', pa.get_default_input_device_info()['index']))

    microphone_dropdown = ft.Dropdown(
        options=[ft.dropdown.Option(index, text=mic) for index, mic in microphones.items()],
        label="Audio Input Device",
        value=selected_mic,
        expand=True,
    )

    language_options = [ft.dropdown.Option("Auto")]
    language_options += [ft.dropdown.Option(abbr, text=lang.capitalize()) for abbr, lang in LANGUAGES.items()]
    language_dropdown = ft.Dropdown(
        options=language_options,
        label="Language",
        value=settings.get('language', "Auto"),
        on_change=language_callback,
    )

    text_size_dropdown = ft.Dropdown(
        options=[ft.dropdown.Option(size) for size in range(8, 66, 2)],
        label="Text Size",
        value=settings.get('text_size', 24),
        on_change=text_size_callback,
    )

    translate_checkbox = ft.Checkbox(label="Translate To English", value=settings.get('translate', False))
    dark_mode_checkbox = ft.Checkbox(label="Dark Mode", value=settings.get('dark_mode', False), on_change=dark_mode_callback)
    text_background_checkbox = ft.Checkbox(label="Text Background", value=settings.get('text_background', False), on_change=text_background_callback)
    always_on_top_checkbox = ft.Checkbox(label="Always On Top", value=settings.get('always_on_top', False), on_change=always_on_top_callback)
    transparent_checkbox = ft.Checkbox(label="Transparent", value=settings.get('transparent', False))

    energy_slider = ft.Slider(min=0, max=max_energy, value=settings.get('volume_threshold', 300), expand=True, height=20)
    volume_bar = ft.ProgressBar(value=0.01, color=ft.colors.RED_800)

    transcription_list = ft.ListView([], spacing=10, padding=20, expand=True, auto_scroll=True)

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

    settings_controls = ft.Column(
        [
            ft.Container(
                content=ft.Row(
                    [
                        model_dropdown,
                        ft.Icon("help_outline", tooltip="Choose which model to transcribe speech with.\nModels are downloaded automatically the first time they are used.")
                    ],
                    spacing=10,
                ),
                padding=ft.padding.only(left=10, right=10, top=15),
            ),
            ft.Container(
                content=microphone_dropdown,
                padding=ft.padding.only(left=10, right=45, top=5)
            ),
            ft.Container(
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                language_dropdown,
                                translate_checkbox,
                            ]
                        ),
                        ft.Container(
                            content=ft.Column(
                                [
                                    text_size_dropdown,
                                    ft.Row(
                                        [
                                            text_background_checkbox,
                                            dark_mode_checkbox,
                                        ]
                                    ),
                                ],
                            ),
                            padding=ft.padding.only(left=10)
                        ),
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        transparent_checkbox,
                                        ft.Icon("help_outline", tooltip="Make the window transparent while transcribing.")
                                    ]
                                ),
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
                        ft.Icon("help_outline", tooltip="Required volume to start decoding speech.\nAdjusts max volume automatically.")
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

    page.add(
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
            content=transcription_list,
            padding=ft.padding.only(left=15, right=45, top=5),
            expand=True,
        ),
    )

    # Set settings that may have been loaded.
    dark_mode_callback(None)
    always_on_top_callback(None)
    text_background_callback(None)

    # Control loops.
    run_record_thread = True

    def recording_thread(stream):
        nonlocal max_energy
        while run_record_thread:
            data = stream.read(chunk_size)
            energy = audioop.rms(data, pa.get_sample_size(pyaudio.paInt16))
            max_energy = max(max_energy, energy)
            energy_slider.max = max_energy
            volume_bar.value = min(energy / max_energy, 1.0)
            volume_bar.color = ft.colors.RED_800 if energy < energy_slider.value else ft.colors.BLUE_800
            data_queue.put(data)
            volume_bar.update()

    next_transcribe_time = None
    transcribe_rate_seconds = float(settings.get('transcribe_rate', 0.5))
    transcribe_rate = timedelta(seconds=transcribe_rate_seconds)
    max_record_time = settings.get('max_record_time', 30)
    silence_time = settings.get('seconds_of_silence_between_lines', 0.5)
    last_sample = bytes()
    samples_with_silence = 0

    while True:
        if currently_transcribing and audio_model and not data_queue.empty():
            now = datetime.utcnow()
            next_transcribe_time = next_transcribe_time or now + transcribe_rate

            if now > next_transcribe_time:
                next_transcribe_time = now + transcribe_rate

                phrase_complete = False
                while not data_queue.empty():
                    data = data_queue.get()
                    energy = audioop.rms(data, pa.get_sample_size(pyaudio.paInt16))
                    samples_with_silence = samples_with_silence + 1 if energy < energy_slider.value else 0
                    if samples_with_silence > sample_rate / chunk_size * silence_time:
                        phrase_complete = True
                        last_sample = bytes()
                    last_sample += data

                wav_file = io.BytesIO()
                with wave.open(wav_file, "wb") as wav_writer:
                    wav_writer.setframerate(sample_rate)
                    wav_writer.setsampwidth(pa.get_sample_size(pyaudio.paInt16))
                    wav_writer.setnchannels(1)
                    wav_writer.writeframes(last_sample)

                wav_file.seek(0)
                with wave.open(wav_file) as wav_reader:
                    samples = wav_reader.getnframes()
                    audio = wav_reader.readframes(samples)

                audio_as_np_int16 = numpy.frombuffer(audio, dtype=numpy.int16)
                audio_as_np_float32 = audio_as_np_int16.astype(numpy.float32) / max_int16

                language = None if language_dropdown.value == 'Auto' else language_dropdown.value
                task = 'translate' if language != 'en' and translate_checkbox.value else 'transcribe'

                result = audio_model.transcribe(audio_as_np_float32, language=language, task=task)
                text = result['text'].strip()

                color = ft.colors.BLACK if dark_mode_checkbox.value else ft.colors.WHITE
                if not phrase_complete and transcription_list.controls:
                    transcription_list.controls[-1].value = text
                else:
                    transcription_list.controls.append(ft.Text(text, selectable=True, size=int(text_size_dropdown.value), bgcolor=color))

                transcription_list.update()

                audio_length_in_seconds = samples / float(sample_rate)
                if audio_length_in_seconds > max_record_time:
                    last_sample = bytes()
                    transcription_list.controls.append(ft.Text('', selectable=True, size=int(text_size_dropdown.value), bgcolor=color))

        sleep(0.1)

if __name__ == "__main__":
    ft.app(target=main)
