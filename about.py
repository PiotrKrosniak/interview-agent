# about.py
import flet as ft

def about_page(page):
    return ft.Container(
        content=ft.Column(
            [
                ft.Text("Interview - Agent", size=24, weight="bold"),
                ft.Container(
                    content=ft.Text(
                        spans=[
                            ft.TextSpan(
                                "A interview agent built with Flet and OpenAI Whisper.\n\n"
                                "This application is designed to transcribe audio input in real-time, detect questions within the transcriptions, "
                                "and provide answers based on the user's CV and the job position they are applying for. The application leverages "
                                "OpenAI's GPT-4o-mini model for generating responses and Whisper API for transcriptions.\n\n"
                                "Free for personal Non-commercial use.\n\n"
                                
                            ),
                            ft.TextSpan(
                                "Interview Agent GitHub",
                                ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE),
                                url="https://github.com/PiotrKrosniak/interview-agent",
                            ),
                        ]
                    ),
                    expand=True,
                ),
            ],
            alignment=ft.MainAxisAlignment.START,
            spacing=10,
        ),
        padding=ft.padding.all(20),
        expand=True,
    )
