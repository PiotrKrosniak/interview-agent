# about.py
import flet as ft

def about_page(page):
    return ft.Container(
        content=ft.Column(
            [
                ft.Text("About This App", size=24, weight="bold"),
                ft.Text("This application helps with transcriptions and more."),
            ],
            alignment=ft.MainAxisAlignment.START,
            spacing=10,
        ),
        padding=ft.padding.all(20),
        expand=True,
    )
