

import flet as ft

def main(page: ft.Page):
    def button_clicked(e):
        page.add(ft.Text("Button clicked!"))

    page.add(ft.ElevatedButton(text="Click me", on_click=button_clicked))

if __name__ == "__main__":
    ft.app(target=main)